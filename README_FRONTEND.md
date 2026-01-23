# Web Frontend (Vite + React)

This folder contains the React web UI that drives the agent system (coding workspace, chat, LeetCode solver, and terminal).

## Tech Stack

- React 19 + Vite
- Tailwind CSS utilities
- Axios for API calls
- ReactFlow for graph visualization

## Project Layout

- `web/src/App.jsx`: Primary UI composition and state management.
- `web/src/main.jsx`: App bootstrap.
- `web/src/index.css`: Base styles.

## Features

- **Sidebar navigation**: Switch between main sections (Coding, LeetCode, etc.).
- **Coding workspace**: File tree, editor, agent chat, and terminal output.
- **LeetCode solver**: Enter a problem number, generate Question/Solution/Explanation files, and run solutions.
- **Theme toggle**: Black/white mode in the top-right.
- **Scrollable panes**: Editor and file previews remain scrollable with terminal docked at bottom.

## Local Development

From repo root:
```bash
cd web
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000`.

If the backend host/port changes, update:
- `API_BASE` in `web/src/App.jsx`
- `WS_URL` in `web/src/App.jsx`

## Build

```bash
cd web
npm run build
```

## Lint

```bash
cd web
npm run lint
```
