
import asyncio
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from datetime import datetime
import networkx as nx


# Add project root to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP
from core.utils import set_event_callback
from routers import coding as coding_router

app = FastAPI(title="SamyakAgent API")
app.include_router(coding_router.router)

# ─── Models ──────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str # 'user' or 'agent'
    content: Any # Allow strings or dicts/lists for flexibility, but formatted to str in chat
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


# ... (CORS remains same) ...

# ─── Session Manager ────────────────────────────────────────────────

SESSION_DIR = Path("memory/web_sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)

class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self._load_sessions()

    def _load_sessions(self):
        for f in SESSION_DIR.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as f_in:
                    data = json.load(f_in)
                    self.sessions[data['id']] = Session(**data)
            except Exception as e:
                print(f"Failed to load session {f}: {e}")

    def save_session(self, session: Session):
        session.last_updated = datetime.now().isoformat()
        self.sessions[session.id] = session
        f_path = SESSION_DIR / f"{session.id}.json"
        with open(f_path, 'w', encoding='utf-8') as f_out:
            json.dump(session.dict(), f_out, indent=2, default=str)

    def get_session(self, session_id: str) -> Session:
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


# Allow CORS for frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── WebSocket Manager ───────────────────────────────────────────────

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
        # Convert to JSON string once
        text = json.dumps(message, default=str)
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception:
                pass # Handle disconnected clients gracefully

manager = ConnectionManager()

# ─── Global State ───────────────────────────────────────────────────

class GlobalState:
    agent_loop: AgentLoop4 = None
    multi_mcp: MultiMCP = None
    is_running: bool = False

state = GlobalState()

# ─── Event Callback ─────────────────────────────────────────────────

def handle_backend_event(event_type: str, data: dict):
    """Bridge backend events to WebSockets"""
    # We need to schedule this on the event loop
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": event_type, "data": data}),
                loop
            )
    except RuntimeError:
        pass # No event loop running

# Register callback
set_event_callback(handle_backend_event)

# ─── Startup/Shutdown ──────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    print("🚀 Starting SamyakAgent Backend...")
    state.multi_mcp = MultiMCP()
    await state.multi_mcp.start()
    
    state.agent_loop = AgentLoop4(multi_mcp=state.multi_mcp)

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Shutting down...")
    if state.multi_mcp:
        await state.multi_mcp.stop()

# ─── API Endpoints ─────────────────────────────────────────────────

# Removed duplicate ChatRequest


@app.get("/health")
async def health_check():
    return {"status": "ok", "agent_ready": state.agent_loop is not None}

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We just keep the connection open to listen
            # Currently frontend doesn't send messages here, just receives
            data = await websocket.receive_text()
            # Optional: handle ping/pong
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
    """Background task to run the agent loop"""
    if state.is_running:
        await manager.broadcast({"type": "error", "data": {"message": "Agent already running"}})
        return

    state.is_running = True
    await manager.broadcast({"type": "status", "data": {"status": "running", "session_id": session_id}})
    
    # Get or create session
    session = session_store.get_session(session_id)
    if not session:
        session = Session(id=session_id, title=query[:50] + "...")
        session_store.save_session(session)

    # Add user message
    user_msg = Message(role="user", content=query, timestamp=datetime.now().isoformat())
    session.messages.append(user_msg)
    session_store.save_session(session)

    try:
        # Run the agent loop
        context = await state.agent_loop.run(
            query=query,
            file_manifest=[],
            globals_schema={},
            uploaded_files=[]
        )
        
        # Extract final answer
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

            # Fallback to last completed node with output
            for node_id in reversed(list(ctx.plan_graph.nodes)):
                node = ctx.plan_graph.nodes[node_id]
                if node.get("status") == "completed" and node.get("output"):
                    return node.get("output")
            return None

        fallback_used = False

        # Format final answer for chat history
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
            # If there's a primary key like 'answer' or 'response', use it
            found = False
            for k in ['answer', 'response', 'output', 'result', 'formatted_answer']:
                if k in outputs:
                    final_answer = str(outputs[k])
                    found = True
                    break

            if not found:
                if len(outputs) == 1:
                    final_answer = str(next(iter(outputs.values())))
                else:
                    # Clean up: Join all values that look like strings
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

        # Capture graph state
        graph_data = nx.node_link_data(context.plan_graph)
        session.graph_data = graph_data

        # Add agent message
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
        state.is_running = False
        await manager.broadcast({"type": "status", "data": {"status": "idle", "session_id": session_id}})

@app.post("/api/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    if state.is_running:
        return {"status": "error", "message": "Agent is busy"}
    
    session_id = request.session_id or str(uuid.uuid4())
    background_tasks.add_task(run_agent_task, request.message, session_id)
    return {"status": "accepted", "message": "Agent started", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
