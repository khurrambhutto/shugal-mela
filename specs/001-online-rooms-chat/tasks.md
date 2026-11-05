# Tasks: Online rooms and chat

**Status:** Setup, foundation, US1, and US2 (T001–T018) and the browser journey (T020) are complete. US3 hosting and cross-cutting verification are pending.
**Inputs:** [specification](spec.md), [plan](plan.md), [data model](data-model.md), and [protocol](contracts/protocol.md).

Run these tasks sequentially unless independent work is explicitly requested.
Paths below are proposed application paths. Completing this planning setup does not complete them.
Focused behavior checks are required by the specification. No test-first workflow is imposed.

## Setup

- [x] T001 Create `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/__init__.py`, `frontend/package.json`, a frontend package lockfile, `frontend/tsconfig.json`, and `frontend/index.html`. Select compatible versions, keep TypeScript strict, and keep application dependencies separate from `.venv-spec-kit/`.
- [x] T002 Add `backend/app/main.py` and `backend/app/config.py` with `GET /api/health`, configuration for exact allowed origins, resource limits, local HTTP mode, and one-worker hosting. Verify a health request succeeds.
- [x] T003 Add `frontend/vite.config.ts` with HTTP and WebSocket proxies, `frontend/src/main.ts`, and FastAPI static-build serving in `backend/app/main.py`. Verify the built page loads from FastAPI and unknown API paths remain API errors.

## Shared foundation

- [x] T004 Define the Pydantic envelopes and messages in `backend/app/protocol.py` and corresponding TypeScript messages in `frontend/src/protocol.ts` from `contracts/protocol.md`. Add shared JSON fixtures under `tests/fixtures/protocol/` covering valid and invalid envelopes.
- [x] T005 Implement guest session creation, restoration, cookie settings, expiry, capacity, and request-origin validation in `backend/app/sessions.py`. Add `POST /api/sessions` in `backend/app/main.py`. Keep credentials out of public responses and logs.
- [x] T006 Add `backend/tests/test_sessions.py` for cookie restoration, invalid origins, nickname validation, session limits, expired credentials, and room-bound nickname changes.
- [x] T007 Implement authenticated connection registration, single-session connection enforcement, bounded outbound queues, one writer per socket, and cleanup in `backend/app/connections.py` and `backend/app/websocket.py`. Wire `/ws` in `backend/app/main.py`.
- [x] T008 Implement connection status, session bootstrap, command correlation, and offline submission prevention in `frontend/src/connection.ts` and `frontend/src/state.ts`. Render connection state in `frontend/src/ui.ts`.
- [x] T009 Add foundation checks in `backend/tests/test_websocket.py` for session authentication, untrusted origins, competing connections, malformed commands, unsupported versions, and oversized messages.

**Checkpoint:** A browser displays an authenticated live connection and an offline state after server shutdown. Explain the handshake and cookie behavior using the observed requests.

## US1: Create and join rooms

- [x] T010 Implement room codes, capacity, membership transitions, command serialization on the single event loop, revision increments, and empty-room cleanup in `backend/app/rooms.py` using `data-model.md`.
- [x] T011 Implement create, join, leave, and sync handling in `backend/app/websocket.py`. Add bounded per-session command-result caching serialized with command execution. Enqueue ordered snapshots through `backend/app/connections.py`.
- [x] T012 Implement nickname entry, room capacity selection, create and join controls, room code display, member list, and leave behavior in `frontend/src/ui.ts` and `frontend/src/state.ts`.
- [x] T013 Add `backend/tests/test_rooms.py` for full rooms, unknown codes, repeated joins, cross-room membership attempts, simultaneous final-seat joins, disconnect removal, and empty-room deletion.
- [x] T014 Extend `backend/tests/test_websocket.py` for successful room journeys, unchanged duplicate commands, reused IDs with changed contents, and leave-versus-broadcast ordering.

**Checkpoint:** Two separate browser profiles agree on room membership. A third player cannot take an occupied final seat. No chat implementation is required to demonstrate this story.

## US2: Send room chat

- [x] T015 Add server-derived sender identity, message IDs, accepted order, 50-message retention, text limits, and session rate limits in `backend/app/rooms.py` and `backend/app/websocket.py`.
- [x] T016 Add the chat composer and bounded plain-text history in `frontend/src/ui.ts`. Replace history from snapshots in `frontend/src/state.ts` and ignore older revisions.
- [x] T017 Extend `backend/tests/test_websocket.py` for room isolation, outsiders, duplicate sends, retained history, blank and oversized text, spoofed extra fields, rate limits, and concurrent message order.
- [x] T018 Add `frontend/tests/state.test.ts` for reordered snapshots, pending join and create snapshots, successful leave, chat replacement, offline actions, and error results. Verify unsafe-looking text renders as text in a browser test.

**Checkpoint:** Twenty sequential messages appear once and in the same order for both members. A separate room receives none of them.

## US3: Host across networks

- [ ] T019 Write `docs/hosting.md` with application installation, build, one-worker startup, exact allowed-origin configuration, HTTPS cookie mode, Quick Tunnel startup, hostname changes, and shutdown. Add matching scripts to `backend/pyproject.toml` or project shell scripts only where useful.
- [x] T020 Add `frontend/tests/browser/rooms-chat.e2e.ts` for separate browser contexts creating and joining a room, chat exchange, leave, connection loss, and public-origin URL construction. Document the command that runs this journey (`npm run test:browser` in `frontend/`). Public-origin URL construction is covered by `frontend/tests/state.test.ts`.
- [ ] T021 Run the application and tunnel, then execute `quickstart.md` on two real devices on different networks. Record actual results, or explicitly mark this task pending if a second device or tester is unavailable.

**Checkpoint:** A remote friend or a phone using mobile data exchanges room messages with the host. Local automated tests alone do not satisfy this story.

## Cross-cutting verification

- [ ] T022 Verify general rate limits, session-creation limits, queue overflow, expiry cleanup, and slow-client isolation in `backend/tests/test_websocket.py` and `backend/tests/test_sessions.py`.
- [ ] T023 Check `backend/app/connections.py`, `backend/app/websocket.py`, and runtime logs for cleanup leaks, deadlock paths, credential exposure, and unbounded state. Fix findings and add focused checks where needed.
- [ ] T024 Run Python checks, frontend type checking, frontend tests, the production build, and the browser journey. Record exact commands and observed outcomes in `quickstart.md`. Keep failed or unrun acceptance work unchecked.
- [ ] T025 Update `README.md` with actual application startup commands. Reconcile `spec.md`, `plan.md`, `data-model.md`, and `contracts/protocol.md` with implemented behavior.

## Dependencies and completion

Setup precedes the shared foundation. US1 depends on the foundation. US2 depends on
US1 for membership. US3 depends on both room and chat behavior. Each story has its own
demonstration after those prerequisites. Cross-cutting checks complete the feature.

T021 requires real access to a second network and device. If unavailable, complete the
remaining independent tasks and report that remote acceptance is pending.
Feature 001 is complete only after every required check, including T021, has passed.
