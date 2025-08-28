Dashboard (Vite) Development

Overview
- The legacy dashboard (`dashboard/dashboard.html`) remains available as a fallback.
- A new Vite + React app now lives under `dashboard/` and builds into `dashboard/dist`.
- FastAPI serves `dashboard/dist/index.html` if it exists, otherwise the legacy HTML.

Commands
- Install: `cd dashboard && npm install`
- Dev server: `npm run dev` (opens on http://localhost:5173)
  - Proxy is configured for `/api` and `/ws` to `http://localhost:8001` (WebSocket supported).
- Build: `npm run build` (outputs to `dashboard/dist`)
- Preview build: `npm run preview`

Serving
- When `dashboard/dist/index.html` exists, FastAPI `/` returns the compiled dashboard.
- Vite assets are served under `/assets` by the FastAPI app.

Notes
- The Vite app is scaffolded with a minimal UI and a test WebSocket connection.
- The full legacy UI will be migrated incrementally. Until then, you can keep using the legacy page by not building the Vite app, or by removing `dashboard/dist`.
- Error boundaries are included in both the legacy and Vite dashboards to improve resilience.

