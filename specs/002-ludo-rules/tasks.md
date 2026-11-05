# Tasks: Ludo rules engine

**Status:** Complete. Backend suite: 240 passed on 2026-11-05.
**Inputs:** [specification](spec.md) and [plan](plan.md).

- [x] T001 Add `backend/app/ludo/__init__.py` and `backend/app/ludo/rules.py` with board constants,
  the immutable match model, error codes, events, and `new_match`. Check that it imports
  nothing from FastAPI, Starlette, or other `app` modules.
- [x] T002 Implement `legal_moves`, `roll`, and `move` for R-01 through R-14.
- [x] T003 Add `backend/tests/ludo/test_rules.py` for setup, turn order, yard entry, movement,
  safe squares, captures, exact finishing, no legal move, extra rolls, the one-bonus limit,
  three sixes, winning, and unchanged state after each rejected action.
- [x] T004 Add seeded random two- and four-player matches that check invariants after every transition
  and finish with exactly one winner.
- [x] T005 Record a complete match in `backend/tests/fixtures/ludo/complete-match.json`
  with a regeneration script (`uv run python -m tests.ludo.play` in `backend/`), and replay it in a test to the same winner and final state.
- [x] T006 Run the full backend suite. Update the project guide's rule defaults to point at this spec.

**Checkpoint:** All rules tests pass, the recorded match replays to its winner,
and the module still has no transport or storage dependency.
