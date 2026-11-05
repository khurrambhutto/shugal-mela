# Implementation plan: Play Ludo online

**Feature:** `003-online-ludo` | **Date:** 2026-11-05. **Specification:** [spec.md](spec.md).

## Design

- `backend/app/match.py` holds the online match: seats, ID, step counter, last events, and
  ending reasons. It calls `app.ludo.rules` and takes an injected dice function so tests are deterministic.
  Production uses `secrets.randbelow(6) + 1`.
- `backend/app/rooms.py` adds host, readiness, and match commands. Every command still runs
  without awaiting, so a roll or move is serialized with all other room changes.
- Leaving or disconnecting while seated in a playing match ends the match with a reason.
- `frontend/src/board.ts` maps rules progress to a 15 × 15 grid. Red's yard is top-left and movement
  is clockwise: red, green, yellow, blue. The static board is SVG; tokens are buttons positioned with
  `transform: translate()` in cell units so they animate on the compositor.
- `frontend/src/dice.ts` renders a 3D CSS die.
- Animations follow Emil Kowalski's guidance: transform and opacity only, strong ease-out and
  ease-in-out curves, short durations, press feedback, and reduced-motion variants.

## Constitution check

- **III:** The server rolls and authorizes every command from the session's seat.
- **IV:** The protocol additions define commands, step numbers, events, and error codes.
- **V:** Rules stay in `app.ludo`; `match.py` adapts them to rooms without transport code.
- **VI:** Backend tests and a browser test that plays a match to a win.

## Visual direction

A night fair. Deep indigo page, a painted wooden board with a truck-art-style border as the single
bold element, glossy domed tokens, and a tumbling die. Type: Rozha One for the wordmark and
Baloo 2 for the interface.
