# Feature specification: Recover from connection loss

**Feature:** `004-reconnect`.
**Created:** 2026-11-05.
**Status:** Implemented. Manual cross-network check pending (T009).
**Roadmap:** Phase 6 of [the project guide](../../docs/project-guide.md).
**Depends on:** [001 rooms and chat](../001-online-rooms-chat/spec.md) and [003 online Ludo](../003-online-ludo/spec.md).

A refresh, a sleeping phone, or a short Wi-Fi drop no longer costs a player their seat or the match.

## User scenarios

### US1: Keep my seat, priority P1

1. Given I am in a room, when my connection drops, then the server keeps my seat for 60 seconds
   and everyone else sees that I am reconnecting, with the time left.
2. Given my connection drops, then my browser retries on its own with growing delays (about 0.5 s
   up to 8 s) and shows "Reconnecting…" until it is back. While offline, my controls are disabled.
3. Given I refresh the page while in a room, then the page reconnects with my existing session
   and puts me back in my seat without asking for my nickname again.
4. Given I return within the window, then I get a fresh full snapshot and everyone sees me as back.
   The board, chat, and turn are exactly as the server has them.
5. Given I leave on purpose with Leave room, then my seat is released immediately, as before.

### US2: Pause the match, priority P1

1. Given a match in progress, when a seated player disconnects, then the match pauses:
   every roll and move is rejected with `MATCH_PAUSED` until they return. Everyone sees who
   the match is waiting for and the seconds left.
2. Given the player returns within the window, then play resumes from the same step.
3. Given the window expires, then the player loses their seat and the match ends with a reason
   naming them. The server never invents a move or a result for them.
4. Given someone in the lobby does not return within the window, then they are removed from the room.
   The host cannot start a match while anyone is reconnecting (`PLAYER_AWAY`).

### US3: Never act twice, priority P1

1. Given I rolled and my connection dropped before the result arrived, when the same command
   is retried with its command ID after reconnecting, then the server returns the original
   result and the die is rolled once.
2. Given I open the game in a second tab or the browser reconnects before the server noticed the
   old socket died, then the newest connection takes over the seat. The old one is closed with
   `4000` and does not mark the player as away.

## Functional requirements

- **FR-001:** Disconnecting marks a room member as away with a 60-second deadline instead of removing them.
- **FR-002:** Snapshots list each member's `away_ms`: `null` when connected, else the milliseconds left.
- **FR-003:** After `session.ready`, a session that is still in a room receives that room's snapshot.
  `session.ready` includes `room_code` so the client knows whether a seat is waiting.
- **FR-004:** `match.roll` and `match.move` are rejected with `MATCH_PAUSED` while any seated player is away.
- **FR-005:** A sweep at least once a second removes members whose deadline passed, ending a playing match
  with "{nickname} did not come back, so the match ended."
- **FR-006:** A newer connection for the same session replaces the older one, which closes with `4000`.
  Cleanup of a replaced connection never changes room state.
- **FR-007:** Command deduplication spans connections of the same session.

## Success criteria

- Refresh during a turn, briefly disable networking, and retry an accepted roll with the same command ID:
  the seat returns, the board matches the other players, and the roll happens once.
- A longer outage visibly ends the match with the reason.

## Out of scope

Surviving a server restart (phase 7). A server restart or a new tunnel address still ends every room.
