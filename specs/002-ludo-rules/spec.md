# Feature specification: Ludo rules engine

**Feature:** `002-ludo-rules`.
**Created:** 2026-11-05.
**Status:** Implemented in `backend/app/ludo/rules.py`. Not yet playable online (phase 5).
**Roadmap:** Phase 4 of [the project guide](../../docs/project-guide.md).
**Input:** A deterministic Python rules module that can play a complete two- or four-player
Ludo match without networking, storage, or a browser.

## User scenarios and testing

### US1: Start a match and take turns, priority P1

As the game server, I create a match for two or four colours and apply supplied dice rolls
so that turns advance exactly as the rules say.

**Independent test:** Create a match, roll for each player in turn, and observe turn order,
yard exits, and automatic turn passing.

Acceptance scenarios:

1. Given a new four-player match, then every token is in its yard and red rolls first.
2. Given a roll other than six with all tokens in the yard, then the turn passes to the next colour.
3. Given a six with a token in the yard, then that token may move onto its start square.
4. Given a roll with legal moves, then the match waits for the current player to choose a token.
5. Given a roll from the wrong player, in the wrong phase, or outside 1 through 6,
   then the action is rejected and the state is unchanged.

### US2: Move, capture, and finish, priority P1

As a player, I move tokens around the track, capture opponents, and bring tokens home.

**Independent test:** Place tokens in chosen positions and apply rolls and moves.

Acceptance scenarios:

1. Given a token on the main track, when it moves, then it advances by exactly the roll.
2. Given opponent tokens on an unsafe destination, when a token lands there,
   then every opponent token on that square returns to its yard.
3. Given opponent tokens on a safe square, when a token lands there, then all of them stay.
4. Given a token in its home column, when the roll would pass home, then that move is illegal.
5. Given a token that reaches home exactly, then it is finished and can no longer move.
6. Given a player's fourth token reaching home, then that player wins and the match ends.

### US3: Extra rolls and the three-sixes limit, priority P1

As a player, I get another roll for a six, a capture, or a token reaching home,
but never more than one per move, and a third six in a row ends my turn.

Acceptance scenarios:

1. Given a six, after its move or when no move is legal, then the same player rolls again.
2. Given a capture or a token reaching home with a non-six roll, then the same player rolls again.
3. Given a six that also captures, then the player gets one extra roll, not two.
4. Given two consecutive sixes in a turn, when the third roll is a six,
   then it is discarded, earlier moves stay applied, and the turn passes.
5. Given a non-six roll with no bonus, then the turn passes after the move.

### US4: Play a complete match, priority P1

**Independent test:** Replay a recorded dice-and-choice script from the first roll to a winner,
and play many seeded random matches while checking invariants.

## Confirmed rule variant

The host confirmed these rules on 2026-11-05. They replace the proposed defaults in the project guide
where they differ.

- **R-01 Players:** two players on opposite colours (red and yellow) or four players
  (red, green, yellow, blue). Each colour has four tokens.
- **R-02 Turn order:** clockwise red, green, yellow, blue, skipping absent colours. The first colour
  in seat order rolls first. The online feature seats the room creator first.
- **R-03 Dice:** one six-sided die. The rules accept supplied outcomes; the server generates them.
- **R-04 Yard exit:** only a six moves a token from its yard onto its start square. This uses the roll.
- **R-05 Track:** 52 shared squares. Each colour travels 51 squares from its start, turns into
  its own 5-square home column, then reaches home: 56 steps in total.
- **R-06 Safe squares:** the four start squares and the four star squares eight steps after each start.
  Any colours may share a safe square.
- **R-07 No blockades:** tokens of one colour may share any square and never block other tokens.
- **R-08 Captures:** landing on an unsafe main-track square sends every opponent token there
  back to its yard. Home columns are private to their colour.
- **R-09 Exact home:** a token reaches home only with the exact roll. A finished token cannot move.
- **R-10 Extra rolls:** a six, a capture, or a token reaching home grants another roll.
  A single move grants at most one extra roll.
- **R-11 Three sixes:** a third consecutive six in one turn is discarded and ends the turn.
  Earlier moves stay applied. Any non-six roll resets the count.
- **R-12 No legal move:** the turn resolves automatically. A six still grants another roll
  under R-10 and R-11. Otherwise the turn passes.
- **R-13 Choice:** with at least one legal move the player chooses a token, even if only one is legal.
- **R-14 Winning:** the first colour with all four tokens home wins and the match ends.

## Functional requirements

- **FR-001:** Rule transitions import nothing from FastAPI, WebSockets, storage, or the browser.
- **FR-002:** Dice outcomes are inputs. The rules module contains no random number generation.
- **FR-003:** Match state is immutable. A transition returns a new state and its events.
- **FR-004:** A rejected action raises a defined error code and leaves the original state unchanged.
- **FR-005:** Legal moves are computed by the rules module for the current roll.
- **FR-006:** Token progress is independent of board drawing coordinates.
- **FR-007:** Transitions report events, such as rolls, moves, captures, finishes, forfeited sixes,
  turn changes, and the winner, so a later feature can describe them to players.

Error codes: `INVALID_PLAYERS`, `INVALID_DIE`, `NOT_YOUR_TURN`, `WRONG_PHASE`, `ILLEGAL_MOVE`, `MATCH_FINISHED`.

## Success criteria

- **SC-001:** Tests cover yard entry, safe squares, captures, exact finishing, no legal move,
  extra rolls, consecutive sixes, and the winner.
- **SC-002:** Every rejected action leaves the state equal to the original.
- **SC-003:** A recorded complete match replays to the same winner and final state.
- **SC-004:** Many seeded random two- and four-player matches finish with exactly one winner
  while invariants hold after every transition.

## Exclusions

Networking, rooms, readiness, dice generation, rendering, timers, reconnection, persistence,
and rematches belong to later features. No generic multi-game interface is created now.
