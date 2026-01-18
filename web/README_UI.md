# SamyakAgent Web UI

This project contains the new React-based web interface for the SamyakAgent platform.

## Architecture
- **Backend**: FastAPI (`server.py`) wrapping the `AgentLoop4` logic.
- **Frontend**: React + Vite + React Flow (`web/` directory).

## How to Run

### 1. Start the Backend
Open a terminal in the project root and run:
```bash
uv run server.py
```
The backend will start on `http://localhost:8000`.

### 2. Start the Frontend
Open another terminal in the `web/` directory and run:
```bash
npm run dev
```
The frontend will be available at `http://localhost:5173`.

## Features
- **Live Graph View**: Real-time visualization of agent execution plans using NetworkX data.
- **Detailed Execution Logs**: View backend logs and tool outputs as they happen.
- **Agent Inspector**: Click on any node in the graph to see its inputs, outputs, costs, and status.
- **Modern Dashboard**: High-fidelity UI inspired by premium agent platforms.
