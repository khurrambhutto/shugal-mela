# Feature specification: Play Ludo online

**Feature:** `003-online-ludo`.
**Created:** 2026-11-05.
**Status:** Implemented. Cross-network and four-player play checks pending (T008).
**Roadmap:** Phase 5 of [the project guide](../../docs/project-guide.md).
**Depends on:** [001 rooms and chat](../001-online-rooms-chat/spec.md) and [002 Ludo rules](../002-ludo-rules/spec.md).

## User scenarios

### US1: Ready up and start, priority P1

The room host starts a match once the other members are ready.

1. Given a room member who is not the host, when they press Ready, then every member sees them as ready.
2. Given two or four members with every non-host member ready, when the host presses Start,
   then a match begins with seats in join order: two players get red and yellow, four get red,
   green, yellow, and blue. The host is red and rolls first.
3. Given three members, a missing ready, or a non-host pressing Start, then the start is rejected
   with `WRONG_PLAYER_COUNT`, `NOT_READY`, or `NOT_HOST`, and nothing changes.
4. Given a match in progress, when someone tries to join, then they receive `MATCH_IN_PROGRESS`.

### US2: Take turns online, priority P1

1. Given my turn, when I press Roll, then the server generates the die value and every member
   sees the same value and the same resulting state.
2. Given legal moves, when I pick a highlighted token, then every member sees it move along the track.
3. Given a roll or move from the wrong player, in the wrong phase, for an illegal token,
   or carrying an old step number, then it is rejected and the match does not change.
4. Given a double click on Roll, then the roll happens once.
5. Given a capture, finish, extra roll, forfeited third six, or win, then every member sees what happened.

### US3: Finish and rematch, priority P1

1. Given a winner, then every member sees the result and the board stays visible.
2. Given a finished or ended match, when members ready up again and the host starts,
   then a new match with a new identity begins from the yard.
3. Given a seated player leaving mid-match, then the match ends with a reason naming that player.
   A disconnect pauses the match instead; see [004 reconnect](../004-reconnect/spec.md).

### US4: Board and feedback, priority P1

1. The board shows the 52-square track, coloured yards, home columns, start and star safe squares,
   and the centre home, with tokens positioned from server state.
2. Each player has their own die and name at their colour's corner of the board. The seat whose
   turn it is is bright; the others are dimmed. Each player sees which of their tokens can move.
3. Everyone watches each roll tumble on the roller's own die, and tokens hop square by square,
   so play is shown on the board rather than in a written log. With reduced motion, state
   changes without movement. Chat has the side panel to itself and keeps working during play.

## Functional requirements

- **FR-001:** Only the server generates dice values, from a cryptographically secure source.
- **FR-002:** Game commands are authorized from the session's seat, never from a client-supplied colour.
- **FR-003:** Roll and move commands include the match ID and step number they were made against.
  A mismatch returns `STALE_STATE` without changing anything.
- **FR-004:** Snapshots include the full public match state and the events of the latest step.
- **FR-005:** Seats and colours freeze when a match starts. A new match has a new ID.
- **FR-006:** The rules module from feature 002 decides every transition.

## Success criteria

- **SC-001:** Automated checks cover start conditions, turn authorization, stale and duplicate commands,
  room isolation, joining during a match, and abort on leave.
- **SC-002:** A browser test plays a two-player match to a win through the real server.
- **SC-003:** A two-player match is completed by two people on different networks.
- **SC-004:** A four-player match is completed with four separate sessions.

## Exclusions

Seat reservation and pausing on disconnect (phase 6), persistence (phase 7), spectators,
turn timers, bots, and voice.
