# Shugal Mela

A browser multiplayer game project built to learn networking and backend development.
Start with private rooms, live text chat, and Ludo. Add voice calls and more games later.
FastAPI runs on the host's laptop. Friends on different networks connect through a public HTTPS tunnel.

Phases 1 and 2 are built: guest sessions, private rooms of two or four players, and room chat
over WebSockets. Remote hosting through a tunnel (phase 3) and the Ludo game are not done yet.

## Host for friends on other networks

```bash
./scripts/host
```

This builds the app, opens a free Cloudflare Quick Tunnel, and prints a public `https://` link.
Friends open the link in a browser and install nothing. See [the hosting guide](docs/hosting.md).

## Run locally

Requires uv, Python 3.12, and Node.js with npm.

```bash
cd frontend && npm ci && npm run build && cd ..
cd backend && uv sync
APP_MODE=development ALLOWED_ORIGINS=http://localhost:8000 \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000` (not `127.0.0.1`, which is a different origin and is rejected).
Keep the default single Uvicorn worker; room state will live in one process.

For frontend development with hot reload, run the backend with
`ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000`, then `npm run dev` in `frontend/`
and open `http://localhost:5173`. Vite proxies `/api` and `/ws` to the backend.

To test two players on one computer, use two browser profiles or a normal and a private window.
Tabs in the same profile share one session, and the server rejects the second tab.

Checks:

- `uv run pytest` in `backend/`.
- `npm run typecheck`, `npm test`, and `npm run test:browser` in `frontend/`.
  The browser test needs Chromium once: `npx playwright install chromium`.

- Read [the project guide](docs/project-guide.md) for the product scope, architecture, and phased roadmap.
- Read [the Spec Kit guide](docs/spec-kit-guide.md) to use the project-local installation.
- Start implementation with [001: Online rooms and chat](specs/001-online-rooms-chat/spec.md).
- Follow [the first feature's tasks](specs/001-online-rooms-chat/tasks.md) in order.

Spec Kit 1.3.0 is installed in `.venv-spec-kit/`. Its Codex skills are in `.agents/skills/`.
The CLI and its dependencies are pinned in `.tools/spec-kit/requirements.lock`.

Check the installed version from this directory:

```bash
./scripts/specify version
```

To recreate the local environment on a machine with Python 3.12 and uv, run:

```bash
./scripts/setup-spec-kit
```

The setup script installs the CLI. It preserves the existing project specifications and skills.
