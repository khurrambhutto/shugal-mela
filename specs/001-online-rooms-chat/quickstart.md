# Verify online rooms and chat

**Status:** Future acceptance procedure. The application does not exist yet.
Commands below describe the expected application layout. They have not been run against a working game.

## Prepare the application after implementation

From the project root, install the locked backend and frontend dependencies using the
commands documented by T001 and T019. Build the frontend with its selected package manager.
The backend must serve `frontend/dist/` and run with one Uvicorn worker.

For the local HTTP check, configure `APP_MODE=development` and
`ALLOWED_ORIGINS=http://localhost:8000`, then run the backend from `backend/`:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The implementation must accept `ALLOWED_ORIGINS` as a comma-separated list of exact origins.
Use `http://localhost:8000` consistently in the browser. `127.0.0.1` and `localhost`
are different origins for browser validation, even when they reach the same server.

## Check local behavior

1. Open `http://localhost:8000` in one browser profile and an independent private window or profile.
2. Choose different nicknames. Create a two-player room and join it using its code.
3. Verify both member lists agree. Attempt a third join using another browser context and expect `ROOM_FULL`.
4. Exchange 20 sequential messages and compare order and count in both browsers.
5. Create another room from a separate session and verify messages do not cross rooms.
6. Send text that resembles HTML and verify the browser displays the text without executing it.
7. Leave, reconnect, and rejoin. Feature 001 releases disconnected seats and does not restore a match.
8. Stop the backend and verify an offline state prevents further chat submission.

## Check different-network access

Install `cloudflared` using the provider's instructions. Start the application, then run
this command in a separate terminal from the project root:

```bash
cloudflared tunnel --url http://localhost:8000
```

1. Copy the generated HTTPS origin. Keep the tunnel process running.
2. Restart the backend with `APP_MODE=public` and `ALLOWED_ORIGINS` set to that exact origin.
   Public mode requires Secure cookies and exact origin checks.
3. Open the public address on the host device and a phone with Wi-Fi disabled,
   or ask a friend using another internet connection to open it.
4. Create and join a room, compare member lists, and exchange messages both ways.
5. Inspect browser networking where available. HTTP requests use the public host and `/ws` uses `wss://`.
6. Stop the tunnel. Verify both clients eventually report disconnection and disable submission.
7. Restarting a Quick Tunnel creates a new origin. Update allowed origins and open the new address.
   Do not claim that old-origin cookies or in-memory rooms recover automatically.

The phone must actually use mobile data. Two devices on the same Wi-Fi do not verify this requirement.

## Record actual results

Results from 2026-11-05 on the Linux host laptop:

- Automated backend behavior checks: `cd backend && uv run pytest` passed 104 tests.
- Frontend type check, tests, and build: `cd frontend && npm run typecheck && npm test && npm run build`
  passed, with 15 state tests.
- Automated browser journey: `cd frontend && npm run test:browser` passed 3 Chromium tests five runs in a row.
  It covers separate-context create and join, a full-room rejection, 10 ordered messages,
  room isolation, markup shown as text, the chat rate limit, leave, a rejected second tab,
  and the offline state with disabled chat after the server stops.
- Local room and chat journey by hand in two browser profiles: not run.
- Remote device and browser: a friend's own device and browser, miles away from the host.
- Networks used by each participant: host laptop on its home connection; the friend on their own separate internet connection. Exact providers not recorded.
- Remote room and chat journey: passed on 2026-11-05 through `./scripts/host` and a Quick Tunnel. The friend joined the room and messages were exchanged in both directions, as reported by the host.
- Tunnel interruption behavior: not observed on the remote device. Offline after server stop is verified locally by the browser journey.
- Date and unresolved failures: 2026-11-05. No failures reported. Before the remote test, the public origin was probed from the host: HTTPS page, Secure cookie, 403 for other origins, and a two-session `wss://` chat.

The implementation phase must add exact executable test commands and observed results here.
