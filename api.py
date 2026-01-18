import sys
import os
import asyncio
import subprocess
import json
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import networkx as nx

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from core.graph_adapter import nx_to_reactflow
from memory.context import ExecutionContextManager
from remme.utils import get_embedding
from config.settings_loader import settings, save_settings, reset_settings, reload_settings
from core.utils import set_event_callback


# Import shared state
from shared.state import (
    active_loops,
    get_multi_mcp,
    get_remme_store,
    get_remme_extractor,
    PROJECT_ROOT,
)
from routers.remme import background_smart_scan  # Needed for lifespan startup

from contextlib import asynccontextmanager

# Get shared instances
multi_mcp = get_multi_mcp()
remme_store = get_remme_store()
remme_extractor = get_remme_extractor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting up...")
    await multi_mcp.start()
    chat_state.agent_loop = AgentLoop4(multi_mcp=multi_mcp)
    chat_state.is_running = False
    
    # Check git
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git found.")
    except Exception:
        print("⚠️ Git NOT found. GitHub explorer features will fail.")
    
    # 🧠 Start Smart Sync in background
    asyncio.create_task(background_smart_scan())
    
    yield
    
    await multi_mcp.stop()

app = FastAPI(lifespan=lifespan)

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://."], # Explicitly allow frontend
    allow_origin_regex=r"http://localhost:(517\d|5555)", 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Web UI Chat/Session Models ===

class Message(BaseModel):
    role: str  # 'user' or 'agent'
    content: Any
    timestamp: Optional[str] = None


class Session(BaseModel):
    id: str
    title: str
    messages: List[Message] = []
    graph_data: Optional[Dict[str, Any]] = None
    last_updated: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


SESSION_DIR = PROJECT_ROOT / "memory" / "web_sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self._load_sessions()

    def _load_sessions(self):
        for f in SESSION_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                    self.sessions[data["id"]] = Session(**data)
            except Exception as e:
                print(f"Failed to load session {f}: {e}")

    def save_session(self, session: Session):
        session.last_updated = datetime.now().isoformat()
        self.sessions[session.id] = session
        f_path = SESSION_DIR / f"{session.id}.json"
        with open(f_path, "w", encoding="utf-8") as f_out:
            json.dump(session.dict(), f_out, indent=2, default=str)

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[Session]:
        return sorted(self.sessions.values(), key=lambda x: x.last_updated, reverse=True)

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            f_path = SESSION_DIR / f"{session_id}.json"
            if f_path.exists():
                f_path.unlink()


session_store = SessionStore()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        text = json.dumps(message, default=str)
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception:
                pass


manager = ConnectionManager()


def handle_backend_event(event_type: str, data: dict):
    """Bridge backend events to WebSockets."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": event_type, "data": data}),
                loop
            )
    except RuntimeError:
        pass


set_event_callback(handle_backend_event)


class ChatState:
    agent_loop: Optional[AgentLoop4] = None
    is_running: bool = False


chat_state = ChatState()

# Global State is now managed in shared/state.py
# active_loops, multi_mcp, remme_store, remme_extractor are imported from there

# === Import and Include Routers ===
from routers import runs as runs_router
from routers import remme as remme_router
from routers import settings as settings_router
from routers import metrics as metrics_router
app.include_router(runs_router.router)
app.include_router(remme_router.router)
app.include_router(settings_router.router)
app.include_router(metrics_router.router)

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/sessions")
async def get_sessions():
    return session_store.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    session_store.delete_session(session_id)
    return {"status": "ok"}


async def run_agent_task(query: str, session_id: str):
    """Background task to run the agent loop."""
    if chat_state.is_running:
        await manager.broadcast({"type": "error", "data": {"message": "Agent already running"}})
        return

    chat_state.is_running = True
    await manager.broadcast({"type": "status", "data": {"status": "running", "session_id": session_id}})

    session = session_store.get_session(session_id)
    if not session:
        session = Session(id=session_id, title=query[:50] + "...")
        session_store.save_session(session)

    user_msg = Message(role="user", content=query, timestamp=datetime.now().isoformat())
    session.messages.append(user_msg)
    session_store.save_session(session)

    try:
        context = await chat_state.agent_loop.run(
            query=query,
            file_manifest=[],
            globals_schema={},
            uploaded_files=[]
        )

        summary = context.get_execution_summary()
        outputs = summary.get("final_outputs", {})

        def extract_summary_fallback(ctx):
            """Fallback to summarizer or last completed node output."""
            if not ctx or not ctx.plan_graph:
                return None

            summarizer_node = next(
                (n for n in ctx.plan_graph.nodes
                 if ctx.plan_graph.nodes[n].get("agent") == "SummarizerAgent"),
                None
            )
            if summarizer_node:
                summarizer_output = ctx.plan_graph.nodes[summarizer_node].get("output")
                if summarizer_output:
                    return summarizer_output

            for node_id in reversed(list(ctx.plan_graph.nodes)):
                node = ctx.plan_graph.nodes[node_id]
                if node.get("status") == "completed" and node.get("output"):
                    return node.get("output")
            return None

        fallback_used = False
        if not outputs:
            fallback_output = extract_summary_fallback(context)
            if fallback_output is None:
                final_answer = "No final output found."
            else:
                fallback_used = True
                final_answer = (
                    fallback_output
                    if isinstance(fallback_output, str)
                    else json.dumps(fallback_output, indent=2)
                )
        elif isinstance(outputs, dict):
            found = False
            for k in ["answer", "response", "output", "result", "formatted_answer"]:
                if k in outputs:
                    final_answer = str(outputs[k])
                    found = True
                    break
            if not found:
                if len(outputs) == 1:
                    final_answer = str(next(iter(outputs.values())))
                else:
                    parts = []
                    for k, v in outputs.items():
                        if isinstance(v, (str, int, float, bool)):
                            parts.append(str(v))
                        else:
                            parts.append(json.dumps(v, indent=2))
                    final_answer = "\n\n".join(parts)
        else:
            final_answer = str(outputs)

        if fallback_used:
            final_answer = "(fallback output)\n\n" + final_answer

        graph_data = nx.node_link_data(context.plan_graph)
        session.graph_data = graph_data

        agent_msg = Message(role="agent", content=final_answer, timestamp=datetime.now().isoformat())
        session.messages.append(agent_msg)
        session_store.save_session(session)

        await manager.broadcast({
            "type": "finish",
            "data": {
                "success": True,
                "output": final_answer,
                "session_id": session_id,
                "messages": session.messages
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        await manager.broadcast({
            "type": "finish",
            "data": {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
        })
    finally:
        chat_state.is_running = False
        await manager.broadcast({"type": "status", "data": {"status": "idle", "session_id": session_id}})


@app.post("/api/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    if chat_state.is_running:
        return {"status": "error", "message": "Agent is busy"}

    session_id = request.session_id or str(uuid.uuid4())
    background_tasks.add_task(run_agent_task, request.message, session_id)
    return {"status": "accepted", "message": "Agent started", "session_id": session_id}





@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "mcp_ready": True # Since lifespan finishes multi_mcp.start()
    }

if __name__ == "__main__":
    import uvicorn
    # Enable reload=True for development if needed, but here we'll just keep it simple
    # or actually enable it to avoid these restart issues.
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
