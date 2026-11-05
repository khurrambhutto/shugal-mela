# Implementation plan: Online rooms and chat

**Feature:** `001-online-rooms-chat` | **Date:** 2026-11-05.
**Status:** Implemented through US2. US3 remote verification pending.
**Specification:** [spec.md](spec.md).

## Summary

Build a FastAPI application and TypeScript browser client with guest sessions,
private room membership, and text chat over native WebSockets. Serve the built frontend
from FastAPI and expose that single service through a Cloudflare Quick Tunnel.
This feature implements project roadmap phases 1 through 3.

## Technical context

- **Runtime:** Python 3.12 and a supported Node.js LTS release selected during setup.
- **Backend:** FastAPI, Pydantic, Uvicorn, and standard-library room state and async locks.
- **Frontend:** Vite and strict TypeScript, with vanilla DOM components as the proposed default.
- **Storage:** In-memory maps and bounded lists. No application database in this feature.
- **Testing:** Pytest with a WebSocket-capable test client, frontend state tests, and browser journey tests.
- **Platform:** Linux host laptop. Modern desktop and mobile browsers as clients.
- **Scope:** A friends-only application. Default limits are 20 active rooms and 100 live sessions.
- **Performance:** Keep room updates responsive during normal conversation. Measure actual latency
  during remote verification; this plan makes no unmeasured latency or capacity claim.
- **Hosting:** One Uvicorn worker on loopback, plus `cloudflared`. HTTPS and WSS at the public origin.

Pin compatible dependency versions and lockfiles when implementation begins.
Spec Kit's `.venv-spec-kit/` is tooling, not the application environment.

## Constitution check

- **I, learning:** Each implementation checkpoint produces a visible connection, room, chat, or remote session.
- **II, laptop hosting:** One local service, free temporary tunnel, and no paid storage dependency.
- **III, server authority:** The server derives the sender from the session and serializes room updates.
- **IV, contracts:** [Protocol](contracts/protocol.md) specifies validation, IDs, errors, and snapshots.
- **V, module boundaries:** Rooms and transport are separate. Ludo remains a later pure rules module.
- **VI, verification:** Tasks include behavior checks and a real different-network test.

No exceptions are proposed. Recheck these gates after implementation changes the design.

## Proposed source layout

These are future paths, not existing application files:

```text
backend/
  pyproject.toml
  uv.lock
  app/
    main.py
    config.py
    protocol.py
    sessions.py
    rooms.py
    connections.py
    websocket.py
  tests/
    test_sessions.py
    test_rooms.py
    test_websocket.py
frontend/
  package.json
  src/
    main.ts
    protocol.ts
    connection.ts
    state.ts
    ui.ts
  tests/
    state.test.ts
  tests/
    browser/
      rooms-chat.e2e.ts
tests/
  fixtures/
    protocol/
      v1.json
docs/
  hosting.md
```

Keep room rules and state changes in `rooms.py`. Keep socket lifecycle, bounded queues,
and broadcasting in `connections.py` and `websocket.py`. Avoid a generic game framework now.

## Design decisions

1. Create or restore a guest session through `POST /api/sessions`. Set an opaque HttpOnly cookie.
   Require same-origin HTTP mutations and validate the WebSocket `Origin` against configured allowed origins.
   Set Secure cookies for HTTPS and allow an explicit local HTTP development mode.
2. Validate every command with Pydantic discriminated message models. Keep the TypeScript
   protocol aligned through checked fixtures initially. Consider schema generation when the protocol grows.
3. Use one active socket per session. Reject a competing socket instead of allowing two writers for one identity.
4. Serialize state changes on the single event loop. Each command's deduplication lookup,
   membership or chat mutation, result caching, and outbound enqueueing run without an `await`,
   so no other command can observe or interleave with a partial change. This covers the
   registry and every room with no explicit locks. Introduce per-room `asyncio.Lock`s, acquiring
   the registry before room locks, when a state change first needs to await, such as SQLite in phase 7.
5. Build immutable public snapshots and enqueue results and snapshots without network waits
   in the serialized state change. Use one writer task per socket to send outside the locks.
   Bound each queue at 32 messages. Schedule slow-client cleanup outside the locks with close code 1013.
6. Include the last 50 messages in each full room snapshot. The client replaces this history
   rather than appending repeated snapshots. Ignore lower revisions for the same room.
7. Bind a connection to the room after joining. Chat bodies cannot name a sender or target another room.
8. Keep the last 100 completed command outcomes per session for ten minutes.
   An identical retry returns the cached result. A different request with that ID fails.
   Cache lookup, mutation, and result registration are serialized for the same session.
9. Release membership on detected disconnect. End this feature at manual reconnect and rejoin.
   Do not queue offline actions. A later feature reserves seats and restores matches.
10. Expire disconnected sessions after 30 minutes of inactivity. Keep active sessions alive.
    Bound sessions and rooms, and delete empty rooms and their locks.

## Delivery sequence and verification

Follow [tasks.md](tasks.md) in order. Complete the setup and shared foundation first,
then US1 rooms, US2 chat, and US3 remote access. End each story with its independent check.

Use [quickstart.md](quickstart.md) as the manual acceptance procedure after the application exists.
Record manual results there with date and devices. Automated tests cover authorization,
serialization, duplicate handling, invalid input, queue overflow, and room isolation.

## Risks and limits

- A changed tunnel hostname creates a new browser origin and therefore a new cookie context.
- A server restart destroys all state in this feature. Do not imply otherwise in the UI.
- Cloudflare can interrupt long-lived connections. Detect closure and explain the rejoin path.
- Browser tabs share cookies. Use separate browser contexts or profiles to simulate distinct players.
- Static frontend fallbacks must not turn unknown `/api` routes or `/ws` requests into HTML responses.
- A public tunnel permits strangers to reach the service. Enforce origin, room, session,
  message, and rate checks before accepting commands.
