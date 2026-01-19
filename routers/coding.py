import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config.settings_loader import reload_settings

from core.coding_loop import CodingLoop
from tools.coding_tools import ensure_workspace, list_files_tool, read_file_tool, write_file, edit_file_tool


router = APIRouter(prefix="/coding", tags=["Coding"])

SESSIONS_DIR = Path(__file__).parent.parent / "memory" / "coding_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class CodingMessage(BaseModel):
    role: str
    content: Any
    timestamp: Optional[str] = None


class CodingSession(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    model: str
    messages: List[CodingMessage] = []


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None


class MessageRequest(BaseModel):
    message: str
    model: Optional[str] = None


class TerminalRequest(BaseModel):
    command: str


class WriteFileRequest(BaseModel):
    path: str
    content: str


class ApplyEditRequest(BaseModel):
    path: str
    old_str: str
    new_str: str


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"coding_{session_id}.json"


def _load_session(session_id: str) -> CodingSession:
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return CodingSession(**data)


def _save_session(session: CodingSession):
    session.updated_at = datetime.now().isoformat()
    path = _session_path(session.id)
    path.write_text(json.dumps(session.dict(), indent=2), encoding="utf-8")


@router.post("/sessions")
async def create_session(request: CreateSessionRequest):
    session_id = str(int(datetime.now().timestamp() * 1000))
    now = datetime.now().isoformat()
    title = request.title or "New Coding Session"
    model = request.model or "gemini-2.5-flash-lite"
    session = CodingSession(
        id=session_id,
        title=title,
        created_at=now,
        updated_at=now,
        model=model,
        messages=[]
    )
    _save_session(session)
    ensure_workspace(session_id)
    return session


@router.get("/sessions")
async def list_sessions():
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("coding_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(data)
        except Exception:
            continue
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = _load_session(session_id)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    path = _session_path(session_id)
    if path.exists():
        path.unlink()
    return {"status": "deleted", "id": session_id}


@router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, request: MessageRequest):
    session = _load_session(session_id)
    session.messages.append(
        CodingMessage(
            role="user",
            content=request.message,
            timestamp=datetime.now().isoformat()
        )
    )
    loop = CodingLoop(session_id=session_id, model_name=request.model or session.model)
    result = await loop.run_message([m.dict() for m in session.messages])
    assistant_message = CodingMessage(
        role="assistant",
        content=result.get("assistant", ""),
        timestamp=datetime.now().isoformat()
    )
    session.messages.append(assistant_message)
    if request.model:
        session.model = request.model
    _save_session(session)
    return {
        "session": session,
        "assistant": assistant_message,
        "tool_trace": result.get("tool_trace", []),
        "warning": result.get("warning")
    }


@router.get("/sessions/{session_id}/files")
async def list_files(session_id: str, path: str = "."):
    return list_files_tool(session_id, path)


@router.get("/sessions/{session_id}/file")
async def read_file(session_id: str, path: str):
    return read_file_tool(session_id, path)


@router.post("/sessions/{session_id}/file")
async def write_workspace_file(session_id: str, request: WriteFileRequest):
    return write_file(session_id, request.path, request.content)


@router.post("/sessions/{session_id}/apply")
async def apply_edit(session_id: str, request: ApplyEditRequest):
    return edit_file_tool(session_id, request.path, request.old_str, request.new_str)


@router.post("/sessions/{session_id}/terminal")
async def run_terminal(session_id: str, request: TerminalRequest):
    workspace = ensure_workspace(session_id)
    command = request.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command is empty")

    settings = reload_settings()
    allowed = set(settings.get("coding", {}).get("terminal_allowlist", []))
    lowered = command.lower()
    if any(op in lowered for op in [">", ">>", "|", "&&", "||", "&"]):
        raise HTTPException(status_code=400, detail="Command chaining or redirection blocked")
    first_token = lowered.split()[0] if lowered.split() else ""
    if first_token not in allowed:
        raise HTTPException(status_code=400, detail=f"Command '{first_token}' is not allowed")

    try:
        result = subprocess.run(
            command,
            cwd=str(workspace),
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "stdout": "", "stderr": "Command timed out"}

    return {
        "status": "completed",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


@router.get("/models")
async def list_models():
    settings = reload_settings()
    agent_settings = settings.get("agent", {})
    default_model = agent_settings.get("default_model", "gemini-2.5-flash-lite")
    overrides = agent_settings.get("overrides", {})
    models = [default_model]
    for override in overrides.values():
        model = override.get("model")
        if model and model not in models:
            models.append(model)
    return {"models": models, "default": default_model}
