# Backend Architecture (S16)

This repository contains the FastAPI backend and the multi-agent execution engine used by the web UI and the coding/LeetCode tools.

## Architecture Overview

- **API layer**: `api.py` wires FastAPI, CORS, and core routers.
- **Agent loop**: `core/loop.py` hosts `AgentLoop4` (Planner → Retriever/Thinker → Distiller → Formatter → QA).
- **Agents**: `agents/` contains agent implementations and shared runner logic.
- **Memory + sessions**: `memory/context.py` tracks the execution graph, global variables, and session files.
- **MCP tools**: `mcp_servers/` and `shared/state.py` route tool calls (e.g., web search).
- **Coding tools**: `tools/coding_tools.py` provides safe filesystem access for sessions.
- **Routers**: `routers/` exposes REST endpoints for chat, coding sessions, LeetCode solver, etc.
- **Prompts**: `prompts/` stores system prompts for each agent role.

## Request Flow (High Level)

1. Frontend calls a router endpoint (e.g., `/coding/...` or `/leetcode/solve`).
2. Router builds a prompt + globals and runs `AgentLoop4`.
3. `AgentLoop4` builds a plan graph, executes agents, and stores outputs in `globals_schema`.
4. Router writes output files (coding workspace or LeetCode problem folder).
5. Response is returned to the frontend with file paths and content.

## Key Backend Components

- `api.py`: FastAPI app, lifecycle hooks, WebSocket events.
- `server.py`: Alternative app entry for environments that use it.
- `core/loop.py`: Graph-based multi-agent execution engine.
- `core/model_manager.py`: Model routing and provider configuration.
- `memory/context.py`: Execution graph, globals, tool execution, session storage.
- `routers/coding.py`: Coding sessions, file ops, terminal commands.
- `routers/leetcode.py`: LeetCode solver endpoints and file generation.
- `tools/sandbox.py`: Safe execution of Python code (when enabled).
- `config/settings*.json`: Runtime settings, defaults, allowlists.

## Storage Layout

- `memory/coding_sessions/`: Coding chat/session state (JSON).
- `memory/coding_workspaces/`: Per-session files created by the coding agent.
- `memory/coding_workspaces/leetcode/Problem_XXXX/`: LeetCode outputs.
- `memory/web_sessions/`: Web chat sessions.

## Running the Backend

From repo root:
```bash
uvicorn api:app --reload --port 8000
```

## Configuration

- `config/settings.defaults.json`: Default settings (models, allowlists).
- `config/settings.json`: Local overrides.
- `config/models.json`: Model definitions used by `ModelManager`.

## Testing

```bash
pytest -q
```

## Notes

- The LeetCode solver uses the multi-agent loop and stores outputs in the LeetCode workspace.
- The coding terminal uses a command allowlist to reduce risk.
