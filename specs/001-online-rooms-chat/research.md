# Research and decisions: Online rooms and chat

**Checked:** 2026-11-05. This document records design evidence, not application test results.

## FastAPI supports the required transport

The [official WebSocket guide](https://fastapi.tiangolo.com/advanced/websockets/)
shows accepting connections, sending and receiving messages, and handling disconnects.
It warns that an in-memory connection list works only within one running process.

**Decision:** Use native browser WebSockets and FastAPI with one Uvicorn worker.
Implement explicit rooms, authorization, acknowledgements, and reconnection behavior.
The developer already knows FastAPI and TypeScript, and implementing these pieces supports the learning goal.
Socket.IO remains an alternative, but its protocol requires compatible clients and server support.
It cannot connect directly to a plain FastAPI WebSocket endpoint.

## A tunnel exposes the laptop without a purchased domain

[Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
provides a temporary address for a local HTTP service without an account or domain.
The hostname changes on restart, and uptime is not guaranteed.
Quick Tunnels have a documented limit of 200 in-flight requests and do not support SSE.
That limit is a provider constraint, not a measured player capacity for this application.
[Cloudflare supports WebSockets](https://developers.cloudflare.com/network/websockets/)
and notes that connections can close during infrastructure updates.

**Decision:** Use the tunnel for friends-only remote testing, with visible offline behavior.
Expose the built application and its WebSocket endpoint through one origin.
Do not make a production uptime promise or treat an HTTP tunnel as a voice relay.

## Spec Kit can stay inside this project

[Release 1.3.0](https://github.com/github/spec-kit/releases/tag/v1.3.0)
is the current release checked during setup. The
[Codex integration](https://github.github.io/spec-kit/integrations/codex.html)
installs project skills under `.agents/skills/` and uses `$speckit-...` invocations.

**Decision:** Pin the release commit and runtime dependencies in a separate project environment.
Keep initialization templates, agent skills, and authored specs in the project.
Use the local wrapper instead of installing a global executable.

## Follow-up research belongs to later features

Select and lock application dependency versions when implementing feature 001.
Confirm Ludo rules when specifying phase 4. Research TURN providers and browser media
behavior when specifying voice. Free quotas and browser behavior may change before that work begins.
