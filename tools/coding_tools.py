import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


WORKSPACES_DIR = Path(__file__).parent.parent / "memory" / "coding_workspaces"


def ensure_workspace(session_id: str) -> Path:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    workspace = WORKSPACES_DIR / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_workspace_path(session_id: str, path_str: str) -> Path:
    workspace = ensure_workspace(session_id)
    requested = Path(path_str).expanduser()
    resolved = (workspace / requested).resolve()
    if workspace not in resolved.parents and resolved != workspace:
        raise ValueError("Path escapes workspace root")
    return resolved


def read_file_tool(session_id: str, filename: str) -> Dict[str, Any]:
    """
    Gets the full content of a file within the coding workspace.
    :param filename: The relative file path to read from the workspace.
    :return: The full content of the file.
    """
    full_path = resolve_workspace_path(session_id, filename)
    if not full_path.exists() or not full_path.is_file():
        return {"file_path": str(full_path), "error": "File not found"}
    content = full_path.read_text(encoding="utf-8")
    return {"file_path": str(full_path), "content": content}


def list_files_tool(session_id: str, path: str = ".") -> Dict[str, Any]:
    """
    Lists the files in a workspace directory.
    :param path: The relative directory path within the workspace.
    :return: A list of files in the directory.
    """
    full_path = resolve_workspace_path(session_id, path)
    if not full_path.exists() or not full_path.is_dir():
        return {"path": str(full_path), "error": "Directory not found"}
    entries = []
    for item in sorted(full_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        entries.append(
            {
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "path": str(item.relative_to(ensure_workspace(session_id)))
            }
        )
    return {"path": str(full_path), "entries": entries}


def edit_file_tool(session_id: str, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """
    Replaces first occurrence of old_str with new_str in file. If old_str is empty,
    create/overwrite file with new_str.
    :param path: The relative file path within the workspace.
    :param old_str: The string to replace.
    :param new_str: The string to replace with.
    :return: A dictionary with the path to the file and the action taken.
    """
    full_path = resolve_workspace_path(session_id, path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    if old_str == "":
        full_path.write_text(new_str, encoding="utf-8")
        return {"path": str(full_path), "action": "created_file"}
    if not full_path.exists():
        return {"path": str(full_path), "action": "file_not_found"}
    original = full_path.read_text(encoding="utf-8")
    if original.find(old_str) == -1:
        return {"path": str(full_path), "action": "old_str_not_found"}
    edited = original.replace(old_str, new_str, 1)
    full_path.write_text(edited, encoding="utf-8")
    return {"path": str(full_path), "action": "edited"}


def write_file(session_id: str, path: str, content: str) -> Dict[str, Any]:
    """
    Writes full content to a file within the workspace.
    :param path: The relative file path within the workspace.
    :param content: Full file contents to write.
    :return: A dictionary with the path to the file and the action taken.
    """
    full_path = resolve_workspace_path(session_id, path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return {"path": str(full_path), "action": "written"}


def get_tool_registry(session_id: str):
    return {
        "read_file": lambda filename: read_file_tool(session_id, filename),
        "list_files": lambda path=".": list_files_tool(session_id, path),
        "edit_file": lambda path, old_str="", new_str="": edit_file_tool(session_id, path, old_str, new_str),
    }


def tool_descriptions() -> str:
    tools = [
        {
            "name": "read_file",
            "description": read_file_tool.__doc__,
            "signature": "(filename: str)"
        },
        {
            "name": "list_files",
            "description": list_files_tool.__doc__,
            "signature": "(path: str = '.')"
        },
        {
            "name": "edit_file",
            "description": edit_file_tool.__doc__,
            "signature": "(path: str, old_str: str, new_str: str)"
        },
    ]
    chunks = []
    for tool in tools:
        chunks.append(
            "\n".join(
                [
                    "TOOL",
                    "===",
                    f"Name: {tool['name']}",
                    f"Description: {tool['description']}",
                    f"Signature: {tool['signature']}",
                    "===============",
                ]
            )
        )
    return "\n".join(chunks)


def parse_tool_invocations(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    invocations: List[Tuple[str, Dict[str, Any]]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("tool:"):
            continue
        try:
            after = line[len("tool:"):].strip()
            name, rest = after.split("(", 1)
            name = name.strip()
            if not rest.endswith(")"):
                continue
            json_str = rest[:-1].strip()
            args = json.loads(json_str)
            invocations.append((name, args))
        except Exception:
            continue
    return invocations
