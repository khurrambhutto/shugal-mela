# Tasks: Play Ludo online

**Status:** T001–T007 complete on 2026-11-05: backend 272 passed, frontend 27 unit tests passed,
5 Chromium browser tests passed, including a full two-player match to a win and a rematch.
T008 needs real players.

- [x] T001 Add `backend/app/match.py` and extend rooms with host, readiness, start, roll, move, and abort on leave.
- [x] T002 Extend protocol models and fixtures with the new commands, snapshot fields, and error codes.
- [x] T003 Add `backend/tests/test_match.py` for start conditions, turn authorization, stale and duplicate
  commands, joining during play, abort on leave or disconnect, rematch identity, and room isolation.
- [x] T004 Add the board, tokens, a die and name seat at each colour's corner, and game controls in the frontend.
- [x] T005 Animate dice rolls, token hops, captures, and the win, with reduced-motion variants.
- [x] T006 Extend frontend state tests for match snapshots.
- [x] T007 Add a browser test that plays a two-player match to a win through the real server (`frontend/tests/browser/ludo.e2e.ts`, seeded with `DICE_SEED` in development mode).
- [ ] T008 Play a two-player match across different networks and a four-player match. Record results.
