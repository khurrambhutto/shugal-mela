<!--
Sync impact report
Version: template -> 1.0.0
Principles: learning through complete features; laptop hosting; server authority;
explicit network contracts; independent game rules; observable verification.
Templates reviewed: spec-template.md, plan-template.md, tasks-template.md.
Template changes required: none. Feature plans supply concrete constitution gates.
Follow-up work: application implementation remains pending.
-->

# Shugal Mela constitution

## Core principles

### I. Learn through complete features

Each phase produces behavior that a player can use or a developer can demonstrate.
Document the networking or backend concept exercised by that phase and how to verify it.
Prefer one working feature at a time. Keep explanations connected to observed behavior.

### II. Run on the host's laptop

FastAPI and TypeScript are the project stack. The core game and text chat must run
without a paid hosting service or paid database. Use one backend process and one public
HTTPS origin for the first playable release. A tunnel connects remote browsers to the laptop.
The host keeps the laptop awake during play. Document external service limits and failure modes.
Treat reliable internet voice relay as a separate dependency with explicit cost and reachability limits.

### III. Let the server decide game outcomes

The backend owns seats, match state, dice results, turns, legal moves, and winners.
Authenticate player identity from the session and authorize every room or game command.
Serialize changes within a room. A rejected command leaves the game unchanged.
The browser requests actions and renders server state.

### IV. Make network behavior explicit

Validate incoming messages with Pydantic and give TypeScript clients a documented,
versioned protocol. Use structured error codes, command IDs, and state revisions.
Specify disconnect, retry, duplicate-command, and stale-state behavior for each feature.
Separate a room's join code from the credential that identifies its players.
Keep session credentials out of application logs and shareable links.

### V. Keep game rules separate from transport

Implement Ludo rules without FastAPI, WebSockets, database access, or browser state.
Supply dice outcomes to deterministic rule transitions from a server-owned random source.
Share rooms, sessions, chat, and later voice between games.
Extract a common game interface when the second game demonstrates what must be shared.

### VI. Verify observable behavior

Use focused tests for rules, authorization, room isolation, concurrent commands,
and reconnect behavior. Test the browser and backend together at feature boundaries.
Verify internet access with two devices on different networks before declaring laptop hosting complete.
Keep automated checks repeatable and record manual results separately from planned checks.
Compilation alone does not prove multiplayer behavior.

## Implementation constraints

- Start with native WebSockets and in-memory state. Add SQLite in its own feature.
- Use one Uvicorn worker while room state is process-local.
- Serve the built frontend and backend through one origin. Use a development proxy locally.
- Keep voice opt-in. Voice failure must not prevent gameplay or text chat.
- Keep accounts, matchmaking, rankings, payments, spectators, and horizontal scaling outside the first release.
- Keep Spec Kit's executable environment and agent integration within this project.

## Development workflow

Write or update a feature specification before planning its implementation.
Use `spec.md` for player-visible behavior, `plan.md` for the technical approach,
and `tasks.md` for ordered work and verification. Resolve routine choices with
documented defaults. Flag a change to the agreed product scope before implementing it.
Update affected contracts and checks when changing behavior.

## Governance

Feature plans include a constitution check against every principle above.
Record exceptions with their reason and simpler alternatives considered.
Update this document when a project constraint changes, then review affected feature artifacts.
Use semantic versions for constitution changes. Routine wording fixes increment the patch version.

**Version**: 1.0.0 | **Ratified**: 2026-11-05 | **Last amended**: 2026-11-05
