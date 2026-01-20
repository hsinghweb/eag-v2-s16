import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.loop import AgentLoop4
from shared.state import get_multi_mcp
from tools.coding_tools import list_files_tool, read_file_tool, write_file


router = APIRouter(prefix="/leetcode", tags=["LeetCode"])

SESSIONS_DIR = Path(__file__).parent.parent / "memory" / "leetcode_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class LeetMessage(BaseModel):
    role: str
    content: Any
    timestamp: Optional[str] = None


class LeetSession(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    model: str
    messages: List[LeetMessage] = []
    problem_context: Optional[str] = None
    problem_url: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    problem_url: Optional[str] = None


class MessageRequest(BaseModel):
    message: str
    mode: Optional[str] = None  # solve | explain
    model: Optional[str] = None
    problem_context: Optional[str] = None
    problem_url: Optional[str] = None


class ContextRequest(BaseModel):
    url: str


class FileRequest(BaseModel):
    path: str
    content: str


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"leetcode_{session_id}.json"


def _workspace_id(session_id: str) -> str:
    return f"leetcode_{session_id}"


def _load_session(session_id: str) -> LeetSession:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return LeetSession(**data)


def _save_session(session: LeetSession):
    session.updated_at = datetime.now().isoformat()
    path = _session_path(session.id)
    path.write_text(json.dumps(session.dict(), indent=2), encoding="utf-8")


async def _ensure_mcp_started():
    multi_mcp = get_multi_mcp()
    try:
        if not multi_mcp.get_connected_servers():
            await multi_mcp.start()
    except Exception:
        pass
    return multi_mcp


def _build_agent_query(mode: str) -> str:
    instruction = "Provide Python code only." if mode == "solve" else "Explain briefly then provide Python code."
    return "You are solving a LeetCode problem. " + instruction


def _extract_summary_fallback(ctx):
    if not ctx or not ctx.plan_graph:
        return None
    summarizer_node = next(
        (n for n in ctx.plan_graph.nodes if ctx.plan_graph.nodes[n].get("agent") == "SummarizerAgent"),
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


def _extract_assistant_text(context):
    if not context:
        return ""
    summary = context.get_execution_summary()
    outputs = summary.get("final_outputs", {})
    if isinstance(outputs, dict):
        return str(
            outputs.get("answer")
            or outputs.get("response")
            or outputs.get("output")
            or outputs.get("formatted_answer")
            or next(iter(outputs.values()), "")
        )
    return str(outputs)


@router.post("/sessions")
async def create_session(request: CreateSessionRequest):
    session_id = str(int(datetime.now().timestamp() * 1000))
    now = datetime.now().isoformat()
    session = LeetSession(
        id=session_id,
        title=request.title or "LeetCode Session",
        created_at=now,
        updated_at=now,
        model=request.model or "gemini-2.5-flash-lite",
        messages=[],
        problem_context=None,
        problem_url=request.problem_url,
    )
    _save_session(session)
    return session


@router.get("/sessions")
async def list_sessions():
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("leetcode_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(data)
        except Exception:
            continue
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    return _load_session(session_id)


@router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, request: MessageRequest):
    session = _load_session(session_id)
    mode = (request.mode or "solve").lstrip("/").lower()
    if mode not in ("solve", "explain"):
        mode = "solve"

    if request.problem_context:
        session.problem_context = request.problem_context
    if request.problem_url:
        session.problem_url = request.problem_url

    session.messages.append(
        LeetMessage(
            role="user",
            content=request.message,
            timestamp=datetime.now().isoformat(),
        )
    )

    multi_mcp = await _ensure_mcp_started()

    problem_context = session.problem_context or ""
    query = _build_agent_query(mode)
    globals_schema = {
        "leetcode_problem_context": problem_context,
        "leetcode_url": session.problem_url or "",
        "leetcode_mode": mode
    }

    agent_loop = AgentLoop4(multi_mcp=multi_mcp)
    context = await agent_loop.run(
        query=query,
        file_manifest=[],
        globals_schema=globals_schema,
        uploaded_files=[],
        session_id=session.id,
        memory_context=problem_context
    )

    assistant_text = _extract_assistant_text(context)
    if not assistant_text:
        fallback = _extract_summary_fallback(context)
        if isinstance(fallback, dict):
            assistant_text = (
                fallback.get("final_answer")
                or fallback.get("answer")
                or fallback.get("markdown_report")
                or str(fallback)
            )
        elif fallback:
            assistant_text = str(fallback)

    assistant_message = LeetMessage(
        role="assistant",
        content=assistant_text,
        timestamp=datetime.now().isoformat(),
    )
    session.messages.append(assistant_message)
    if request.model:
        session.model = request.model
    _save_session(session)
    return {"session": session, "assistant": assistant_message}


@router.post("/context")
async def fetch_context(request: ContextRequest):
    multi_mcp = get_multi_mcp()
    try:
        result = await multi_mcp.route_tool_call("web_extract_text", {"string": request.url})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    text = ""
    if hasattr(result, "content") and result.content:
        content = result.content[0]
        text = getattr(content, "text", str(content))
    else:
        text = str(result)
    return {"url": request.url, "context": text}


@router.get("/sessions/{session_id}/files")
async def list_files(session_id: str, path: str = "."):
    _load_session(session_id)
    return list_files_tool(_workspace_id(session_id), path)


@router.get("/sessions/{session_id}/file")
async def read_file(session_id: str, path: str):
    _load_session(session_id)
    return read_file_tool(_workspace_id(session_id), path)


@router.post("/sessions/{session_id}/file")
async def write_session_file(session_id: str, request: FileRequest):
    _load_session(session_id)
    return write_file(_workspace_id(session_id), request.path, request.content)
