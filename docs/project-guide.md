# Shugal Mela project guide

**Status:** Proposed product and implementation roadmap. Application implementation has not started.
**Updated:** 2026-11-05.

## Product goal

Build a browser game that you can host on your laptop while friends play from different
Wi-Fi or mobile networks. Start with private rooms, text chat, and Ludo. Add voice and
other games after the first game works reliably. Use the project to learn backend design,
network protocols, concurrency, sessions, and recovery through working features.

The first playable release supports two or four friends in a private Ludo room, room chat,
and recovery from a short connection loss. Account registration and paid hosting are outside
that release. Voice and saved matches are later milestones.

## Agreed constraints and proposed defaults

The user has experience with FastAPI and TypeScript. Keep Python on the backend and
TypeScript in the browser. The host's laptop remains on during play. Remote players need
only a supported browser and an internet connection.

Use these implementation defaults unless a feature needs a different choice:

- Python 3.12, FastAPI, Pydantic, Uvicorn, and native WebSockets on the backend.
- TypeScript with strict checking and Vite in the frontend. Start with vanilla TypeScript.
  React remains an optional frontend choice before application setup.
- One backend process with rooms in memory initially. Add SQLite in phase 7.
- Cloudflare Quick Tunnel for temporary public HTTPS access without a purchased domain.
- Browser WebRTC for voice. Add relay infrastructure only when testing demonstrates the need.
- Pytest for Python behavior, frontend unit tests for state handling, and browser tests for complete journeys.

These are planning choices, not claims that application dependencies are installed.
The separate Spec Kit environment is installed already.

## Runtime architecture

During a play session, the following components run:

1. FastAPI runs on the laptop at `127.0.0.1:8000` with one Uvicorn worker.
2. FastAPI serves the compiled frontend, HTTP endpoints under `/api`, and `/ws`.
3. `cloudflared` connects outward from the laptop and provides a public HTTPS address.
4. Friends load the frontend from that address. Their browsers connect to `/ws` using `wss://`.
5. FastAPI validates commands, changes room or match state, and broadcasts updates to room members.

Use relative HTTP URLs and derive the WebSocket URL from the page's origin.
The public frontend must never connect to a hardcoded `localhost` address.
During development, Vite proxies `/api` and `/ws` to FastAPI. During remote testing,
serve the built frontend from FastAPI so only one tunnel and origin are needed.

The tunnel removes the usual need for a public home IP address or inbound router port forwarding.
It does not keep the laptop awake, preserve state after a crash, or relay WebRTC audio.
Quick Tunnel addresses change after a restart and have no uptime guarantee.

## Domain and ownership

- A **session** identifies a guest browser. A private credential establishes that identity.
- A **player** is a session's participation in a room. A nickname is a display label, not identity.
- A **room** groups players, chat, and a selected game. A room code is shareable, not a session credential.
- A **match** is one game played in a room. A rematch creates a new match identity.
- A **command** requests an action. The server authorizes and validates it.
- A **snapshot** contains the current public room or match state and its revision.

The room creator can start a match but has no power to choose dice results or bypass rules.
The laptop operator controls the server itself. This design assumes trusted friends and
does not promise fairness against an operator who modifies the server.

Keep rule transitions independent of HTTP, WebSockets, and storage.
Serialize commands for a room before updating state. Broadcast outside the critical section
and use revisions so browsers cannot replace newer state with an older snapshot.

## Phased roadmap

Complete each phase's exit check before taking on the next dependent phase.
Phase numbers describe the product roadmap. Spec Kit feature numbers describe bounded features.
Feature `001-online-rooms-chat` covers phases 1 through 3.

### Phase 1: Run the application locally

**Deliverable:** A browser page connects to a FastAPI server on your laptop.

Tasks:

1. Create the Python application and TypeScript frontend with separate dependency lockfiles.
2. Add a health endpoint and a small WebSocket connection-status view.
3. Add development proxy configuration and serve the frontend build from FastAPI.
4. Add structured connection logs without cookies, tokens, or message contents.
5. Document how to run the backend and build the frontend.

**Learn:** HTTP versus WebSockets, the opening handshake, ports, origins, async handlers,
and the difference between listening on loopback and exposing a public endpoint.

**Exit check:** The built page loads from FastAPI, connects through `/ws`, and visibly reports
a disconnect when the backend stops. The health endpoint returns a successful response.

### Phase 2: Create private rooms and text chat

**Deliverable:** Separate browser sessions can join a room and exchange messages.

Tasks:

1. Issue guest sessions with private cookies and validate connection origins.
2. Create rooms with a six-character code and capacity of two or four.
3. Add join, leave, player-list, and plain-text chat behavior.
4. Validate incoming messages and return structured errors.
5. Isolate broadcasts by room and handle concurrent joins to the final seat.
6. Add command IDs, bounded duplicate detection, and full room snapshots with revisions.

**Learn:** Authentication versus authorization, message contracts, fan-out, locks,
input validation, duplicate requests, and resource cleanup.

**Exit check:** Two browser profiles exchange chat in one room. A third profile in a separate
room sees none of it. A full room rejects another join. Invalid requests leave state unchanged.
Feature 001 deliberately releases a seat on disconnect. Seat recovery arrives in phase 6.

### Phase 3: Connect from different networks

**Deliverable:** You and a friend use the laptop-hosted application over the internet.

Tasks:

1. Build the frontend and run FastAPI locally with one worker.
2. Start a Quick Tunnel and configure the application to accept its exact public origin.
3. Restart the application with that configuration while keeping the tunnel running.
4. Share the public address and a room code.
5. Test from home Wi-Fi and a phone with Wi-Fi disabled, or from a friend's separate connection.
6. Document startup, shutdown, URL changes, and reconnecting after a tunnel interruption.

**Learn:** Private and public addresses, NAT, CGNAT, outbound tunnels, TLS, HTTPS,
secure cookies, and secure WebSockets.

**Exit check:** Two devices on different networks join the same room and exchange messages
in both directions. Stopping the tunnel produces an understandable offline state.
Record the networks used and actual results. A localhost-only test does not complete this phase.

### Phase 4: Implement the Ludo rules

**Deliverable:** A deterministic Python rules module can play a complete match without networking.

Tasks:

1. Specify the rule variant using the proposed defaults below.
2. Represent token progress independently from board drawing coordinates.
3. Implement match creation, rolling transitions, legal moves, captures, home entry, and winning.
4. Accept supplied dice outcomes in rules tests. Generate actual dice in the server layer.
5. Cover rule boundaries with focused tests and a scripted complete-match fixture.

**Learn:** State machines, invariants, deterministic transitions, and domain modeling.

**Exit check:** Tests cover yard entry, safe squares, captures, exact finishing,
no legal move, consecutive sixes, and the winner. An invalid move leaves the state unchanged.

### Phase 5: Play Ludo online

**Deliverable:** Two players, then four players, can complete a match through the tunnel.

Tasks:

1. Add readiness and creator-only start controls. Freeze seats and rules when a match starts.
2. Connect roll and move commands to the rules module. Generate dice only on the server.
3. Reject requests from the wrong player, requests in the wrong phase, and stale commands.
4. Render the board, current turn, dice, legal token choices, and result screen.
5. Keep room chat working during play. Add a rematch that creates a new match identity.
6. Add integration checks for room isolation, double clicks, and two commands racing for one turn.

**Learn:** Authoritative state, revision checks, per-room serialization, and rendering from snapshots.

**Exit check:** Complete a two-player and a four-player match using separate sessions.
At least one complete two-player match must cross different networks.
Every browser agrees on token positions, turn, dice, and winner.

### Phase 6: Recover from connection loss

**Deliverable:** A short Wi-Fi interruption or page refresh does not lose a player's seat or change the board.

Tasks:

1. Retain the player's seat during a proposed 60-second reconnect window.
2. Resume using the private session credential and send a fresh full snapshot.
3. Pause match actions while a player is disconnected. Display the remaining reconnect window.
4. If the window expires, abort the match with a reason rather than silently inventing a result.
5. Retry with bounded backoff. Restore state before accepting fresh user actions.
6. Test lost acknowledgements and retries so a roll or move cannot execute twice.
7. Handle an old connection's cleanup without disconnecting its replacement.

**Learn:** Connection lifecycle, liveness, idempotency, timers, stale connections,
and the difference between a session and a WebSocket.

**Exit check:** Refresh during a turn, briefly disable networking, and retry a previously
accepted roll with the same command ID. The seat returns, the board converges,
and the roll happens once. A longer outage visibly aborts the match.

This completes the first playable release. Server restarts still end in-memory matches until phase 7.

### Phase 7: Save state with SQLite

**Deliverable:** A controlled backend restart preserves a match and recent chat.

Tasks:

1. Specify persistence for sessions, membership, match snapshots, accepted game commands,
   and bounded chat history. Store credential hashes rather than usable session secrets.
2. Add migrations and a transaction that saves the accepted command, dice result, and resulting state together.
3. Restore saved matches as paused after startup. Let players rejoin before resuming.
4. Keep the same public tunnel alive during the restart to preserve the browser origin and cookies.
5. Add retention cleanup and a documented backup and restore procedure.

**Learn:** Transactions, schema changes, consistency, crash recovery, and retention.

**Exit check:** Restart after a move but before its acknowledgement is received.
The saved match and retry produce one accepted move. Restore a backup into a fresh data directory.
If the tunnel hostname changes, old cookies belong to the old origin. Automatic recovery
across a new hostname requires a separately designed recovery method.

### Phase 8: Make hosting and play dependable

**Deliverable:** The host can start a session using documented commands, and players understand failures.

Tasks:

1. Add a repeatable build and run command, health checks, bounded queues, and graceful shutdown.
2. Check phone layouts, touch targets, keyboard controls, connection status, and actionable errors.
3. Add limits for sessions, rooms, chat, and join attempts. Validate HTTPS and WebSocket origins.
4. Verify that a slow or disconnected browser does not stall other players.
5. Record one complete play session and resolve observed failures.

**Learn:** Backpressure, operational logs, resource limits, and integration testing.

**Exit check:** Follow the hosting instructions from a stopped application, complete a remote match,
and shut down cleanly. The logs explain failures without exposing player credentials.

### Phase 9: Add two-player voice

**Deliverable:** Two room members can opt into a voice call while the game continues.

Tasks:

1. Specify join-call, leave-call, microphone permission, mute, and call status behavior.
2. Request audio through browser media APIs under HTTPS.
3. Exchange offers, answers, and ICE candidates through authenticated room signaling.
4. Attach audio tracks to a peer connection and stop tracks when a player leaves.
5. Test same-network and cross-network calls. Add a TURN configuration only when available.
6. Report a failed call without interrupting gameplay or text chat.

**Learn:** WebRTC signaling, SDP, ICE, STUN, TURN, NAT traversal, and media permissions.

**Exit check:** Two devices exchange audio, mute, and leave without retaining an active microphone.
If TURN is configured, test relay-only mode to verify the relay itself.
Record network combinations that fail when no relay is available.

Voice reliability across arbitrary networks is conditional on a reachable relay.
Self-hosting TURN on a laptop behind CGNAT does not automatically make it reachable.
Check service quotas and terms before relying on a free relay. The HTTP tunnel is not TURN.

### Phase 10: Extend voice to the Ludo room

**Deliverable:** Up to four room members can opt into the same call.

Tasks:

1. Use a small peer mesh, with one connection to each other voice participant.
2. Add participants, independent mute state, join and leave cleanup, and reconnect handling.
3. Test headphones, background tabs, mobile browsers, and a participant changing networks.
4. Document device and network limits. Evaluate an SFU only if real tests require one.

**Learn:** Multi-peer connection management and the upload cost of sending audio to each peer.

**Exit check:** Four participants can hear each other in the tested setup while playing.
Leaving and rejoining creates no duplicate audio or abandoned microphone tracks.

### Phase 11: Add another game

**Deliverable:** A second game reuses rooms, chat, sessions, hosting, and voice.

Tasks:

1. Choose a small turn-based game and write its own feature specification.
2. Compare its actual lifecycle with Ludo's lifecycle.
3. Extract only the shared game registration, start, command, snapshot, and result behavior.
4. Keep game-specific state and rules in separate modules.
5. Verify both games using the same room and connection infrastructure.

**Learn:** Module boundaries and generalization from two working implementations.

**Exit check:** A room can choose either game before a match. Each game completes independently,
and the existing Ludo, chat, and voice checks still pass.

## Proposed Ludo rule defaults for phase 4

These defaults define a starting variant. Confirm or revise them when creating the Ludo feature spec.

- Support two players on opposite colors or four players, with four tokens per player.
- Use a six to move a token from the yard onto its start square. This consumes the roll.
- Use a six-sided die. A six grants another roll after its move, even if no move is legal.
- A third consecutive six discards that roll and ends the turn. Earlier moves remain applied.
- When no move is legal, resolve the turn automatically under the six rule above.
- Use the four start squares as safe squares. Different colors may share a safe square.
- Allow same-color tokens to share squares without creating a blockade.
- On an unsafe square, capture all opponent tokens on the destination and return them to their yards.
- Captures and entering home grant no additional turn beyond a six.
- Require the exact roll to reach the final home position. Finished tokens cannot move.
- The first player with all four tokens home wins and ends the match.
- Use clockwise turns, with the creator's seat first. Show the rules before players ready up.

## Feature specification process

Use [the Spec Kit guide](spec-kit-guide.md) for the exact commands.
Keep this document as the product roadmap. Create a separate feature directory when its phase begins.
Specify behavior in `spec.md`, architecture in `plan.md`, and implementation work in `tasks.md`.
Write enough detail for the next feature. Revisit later features using what the earlier phases reveal.

## Sources

The sources below informed the design. Provider limits and free plans can change.

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
- [Cloudflare WebSockets](https://developers.cloudflare.com/network/websockets/)
- [WebRTC TURN servers](https://webrtc.org/getting-started/turn-server)
- [Browser microphone requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [GitHub Spec Kit](https://github.com/github/spec-kit)
