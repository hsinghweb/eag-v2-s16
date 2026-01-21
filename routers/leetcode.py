import json
import re
from pathlib import Path
from typing import Any, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.loop import AgentLoop4
from shared.state import get_multi_mcp
from tools.coding_tools import list_files_tool, read_file_tool, write_file
from tools.coding_tools import ensure_workspace


router = APIRouter(prefix="/leetcode", tags=["LeetCode"])

WORKSPACE_ID = "leetcode"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "leetcode_solve.md"


class SolveRequest(BaseModel):
    number: int
    model: Optional[str] = None


class TerminalRequest(BaseModel):
    command: str


def _format_problem_id(number: int) -> str:
    if number <= 0:
        raise HTTPException(status_code=400, detail="Problem number must be positive")
    return f"{number:04d}"


async def _ensure_mcp_started():
    multi_mcp = get_multi_mcp()
    try:
        if not multi_mcp.get_connected_servers():
            await multi_mcp.start()
    except Exception:
        pass
    return multi_mcp


def _extract_tool_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        content = result.content[0]
        return getattr(content, "text", str(content))
    return str(result)


async def _web_search_urls(query: str, count: int = 5) -> list:
    multi_mcp = await _ensure_mcp_started()
    try:
        result = await multi_mcp.route_tool_call("web_search", {"string": query, "integer": count})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    text = _extract_tool_text(result)
    try:
        urls = json.loads(text)
        if isinstance(urls, list):
            return urls
    except Exception:
        pass
    return []


def _select_problem_url(urls: list) -> str:
    for url in urls:
        if "leetcode.com/problems/" in url:
            return url
    return ""


def _extract_problem_slug(url: str) -> str:
    match = re.search(r"leetcode\.com/problems/([^/]+)/", url)
    return match.group(1) if match else ""


def _build_description_url(slug: str) -> str:
    return f"https://leetcode.com/problems/{slug}/description/"


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


def _parse_solution_payload(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    trimmed = text.strip()
    try:
        parsed = json.loads(trimmed)
        if isinstance(parsed, dict):
            solution_code = str(parsed.get("solution_code") or "").strip()
            explanation = str(parsed.get("explanation_markdown") or "").strip()
            return solution_code, explanation
    except Exception:
        pass

    code_block = ""
    explanation = trimmed
    match = re.search(r"```(?:python)?\n([\s\S]*?)```", trimmed)
    if match:
        code_block = match.group(1).strip()
        explanation = trimmed.replace(match.group(0), "").strip()
    return code_block, explanation


def _ensure_typing_imports(code: str) -> str:
    if not code:
        return code
    needed = []
    for name in ["Optional", "List", "Tuple", "Dict", "Set"]:
        if name in code and f"from typing import {name}" not in code and "import typing" not in code:
            needed.append(name)
    if not needed:
        return code
    import_line = f"from typing import {', '.join(sorted(set(needed)))}"
    lines = code.splitlines()
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    lines.insert(insert_at, import_line)
    return "\n".join(lines)


@router.post("/solve")
async def solve_problem(request: SolveRequest):
    problem_id = _format_problem_id(request.number)
    query = f"LeetCode problem {request.number} site:leetcode.com/problems"
    urls = await _web_search_urls(query, count=5)
    problem_url = _select_problem_url(urls)
    if not problem_url:
        raise HTTPException(status_code=404, detail="LeetCode problem URL not found")

    slug = _extract_problem_slug(problem_url)
    if not slug:
        raise HTTPException(status_code=404, detail="LeetCode problem slug not found")
    description_url = _build_description_url(slug)

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""
    if not prompt_template.strip():
        prompt_template = (
            "You are a LeetCode coding assistant.\n\n"
            "Problem Context:\n{problem_context}\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON with two keys: \"solution_code\" and \"explanation_markdown\".\n"
            "- \"solution_code\" must be a complete Python program with a main() function and stdin parsing.\n"
            "- \"explanation_markdown\" should be concise and in Markdown.\n"
            "- Do NOT wrap the JSON in code fences.\n"
        )
    problem_context = (
        f"LeetCode Problem #{request.number}\n"
        f"URL: {description_url}\n"
        "Use your knowledge of this problem and provide a correct Python solution."
    )
    query_text = prompt_template.format(problem_context=problem_context)

    agent_loop = AgentLoop4(multi_mcp=await _ensure_mcp_started())
    context = await agent_loop.run(
        query=query_text,
        file_manifest=[],
        globals_schema={
            "leetcode_problem_number": request.number,
            "leetcode_problem_url": description_url,
        },
        uploaded_files=[],
        session_id=f"leetcode_{problem_id}",
        memory_context=problem_context,
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

    solution_code, explanation = _parse_solution_payload(assistant_text)
    if not solution_code:
        raise HTTPException(status_code=500, detail="Failed to extract solution code")
    solution_code = _ensure_typing_imports(solution_code)

    folder = f"Problem_{problem_id}"
    question_path = f"{folder}/Question_{problem_id}.md"
    solution_path = f"{folder}/Solution_{problem_id}.py"
    explanation_path = f"{folder}/Explanation_{problem_id}.md"

    question_md = (
        f"# LeetCode {request.number}\n\n"
        f"Source: [{description_url}]({description_url})\n"
    )
    write_file(WORKSPACE_ID, question_path, question_md)
    write_file(WORKSPACE_ID, solution_path, solution_code.strip() + "\n")
    write_file(WORKSPACE_ID, explanation_path, explanation.strip() + "\n")

    return {
        "problem_number": request.number,
        "problem_id": problem_id,
        "problem_url": description_url,
        "folder": folder,
        "files": {
            "question": question_path,
            "solution": solution_path,
            "explanation": explanation_path,
        },
        "question": question_md,
        "solution": solution_code,
        "explanation": explanation,
    }


@router.post("/terminal")
async def run_terminal(request: TerminalRequest):
    workspace = ensure_workspace(WORKSPACE_ID)
    command = request.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command is empty")

    from config.settings_loader import reload_settings

    settings = reload_settings()
    allowed = set(settings.get("coding", {}).get("terminal_allowlist", []))
    lowered = command.lower()
    if any(op in lowered for op in [">", ">>", "|", "&&", "||", "&"]):
        raise HTTPException(status_code=400, detail="Command chaining or redirection blocked")
    first_token = lowered.split()[0] if lowered.split() else ""
    if first_token not in allowed:
        raise HTTPException(status_code=400, detail=f"Command '{first_token}' is not allowed")

    import asyncio
    import subprocess

    try:
        result = await asyncio.to_thread(
            subprocess.run,
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


@router.get("/files")
async def list_files(path: str = "."):
    return list_files_tool(WORKSPACE_ID, path)


@router.get("/file")
async def read_file(path: str):
    return read_file_tool(WORKSPACE_ID, path)
