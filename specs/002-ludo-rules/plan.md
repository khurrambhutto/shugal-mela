# Implementation plan: Ludo rules engine

**Feature:** `002-ludo-rules` | **Date:** 2026-11-05.
**Specification:** [spec.md](spec.md).

## Summary

Add a pure Python module that represents a Ludo match as immutable data and applies
`roll` and `move` transitions with supplied dice values. Phase 5 will connect it to rooms.

## Technical context

- **Language:** Python 3.12 in the existing `backend/` project. No new dependencies.
- **Testing:** pytest, a recorded complete-match fixture, and seeded random matches.
- **Location:** `backend/app/ludo/`. It must not import `fastapi`, `starlette`, or other `app` modules.

## Constitution check

- **I, learning:** The rules are demonstrated by tests and a replayed complete match.
- **II, laptop hosting:** No new services.
- **III, server authority:** The server will own the state and dice; rules accept dice as inputs.
- **IV, contracts:** Error codes and events are defined here for the phase 5 protocol.
- **V, module boundaries:** The rules module has no transport or storage dependency. A test enforces this.
- **VI, verification:** Focused rule tests, invariants, and a full-match replay.

No exceptions.

## Data model

```text
Colour = "red" | "green" | "yellow" | "blue"
Phase  = "awaiting_roll" | "awaiting_move" | "finished"

Match (frozen)
  colours: tuple[Colour, ...]          # turn order
  tokens: dict-like Colour -> tuple[int, int, int, int]
  current: int                         # index into colours
  phase: Phase
  roll: int | None                     # the roll awaiting a move
  sixes: int                           # consecutive sixes this turn
  winner: Colour | None
```

Token progress: `-1` in the yard, `0` on the start square, `0..50` on the shared track,
`51..55` in the home column, and `56` home. The shared square is `(START[colour] + progress) % 52`
for progress `0..50`, with `START = red 0, green 13, yellow 26, blue 39`.
Safe squares are `{0, 8, 13, 21, 26, 34, 39, 47}`.

## Transitions

- `new_match(colours)` validates two opposite or all four colours.
- `legal_moves(match)` returns token indices legal for the pending roll.
- `roll(match, colour, value)` checks turn, phase, and value. A third six forfeits the turn.
  With no legal move it resolves automatically; otherwise it waits for a move.
- `move(match, colour, token)` checks legality, moves, captures, and finishes,
  then grants at most one extra roll or passes the turn.

Each returns `Transition(match, events)`. Errors raise `RuleError(code)` and never mutate input.

## Verification

- Rule tests construct states with chosen token positions through a test helper.
- A recorded match in `backend/tests/fixtures/ludo/complete-match.json` stores rolls and choices
  and its expected winner and final positions. A script regenerates it from a seed.
- Seeded random matches check invariants after every transition: four tokens per colour,
  progress within `-1..56`, no opponent sharing an unsafe track square, consistent phase,
  and termination with exactly one winner.
