# Implementation plan: Recover from connection loss

**Feature:** `004-reconnect` | **Date:** 2026-11-05. **Specification:** [spec.md](spec.md).

## Design

- `Room.away` maps a session ID to a monotonic deadline. `RoomRegistry.disconnect` adds the
  member there instead of removing them; `reconnect` removes them and returns the snapshot
  deliveries; `expire_away(now)` releases expired seats through the same path as leaving.
- The deadline comes from `Limits.reconnect_grace_s` (60). A lifespan task calls
  `CommandProcessor.expire_away()` every second and queues the resulting snapshots.
- `ConnectionRegistry.register` returns the connection it replaced. `serve_socket` closes it with `4000`.
  A connection's cleanup only marks the session away when it is still the session's current connection.
- `RoomRegistry.play` checks for an away seat before applying a roll or move; `start_match` checks every member.
- Deduplication already lives on the session, so a retried command ID after reconnecting returns the
  stored result.
- Client: `Connection` reports the close code. `main.ts` retries with backoff (500 ms doubling to 8 s,
  with jitter, for up to two minutes) unless the close was `4000`, an origin or session refusal, or a
  deliberate close. The state keeps the room while reconnecting; `sessionReady` keeps it when the server
  says the seat is still there and drops it with a notice otherwise. A tab that was in a room stores a
  flag in `sessionStorage`, so a refresh reconnects without the welcome form.
- UI: an away seat shows a countdown; a paused match shows a banner naming who it waits for; tokens and
  Roll are disabled while paused or while this browser is reconnecting.

## Constitution check

- **III:** The server owns the deadline and the pause; clients only display it.
- **IV:** The protocol additions define `away_ms`, `room_code`, the new codes, and close code `4000`.
- **V:** Rules are untouched; pausing lives in rooms.
- **VI:** Backend tests drive the clock for expiry; a browser test refreshes mid-match and stops the network.
