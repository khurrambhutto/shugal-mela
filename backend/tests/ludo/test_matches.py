import json

import pytest

from app.ludo.rules import HOME, SAFE_SQUARES, YARD, Match, Transition, move, new_match, roll, track_square

from .play import FIXTURE, play


def check_invariants(before: Match, t: Transition) -> None:
    m = t.match
    assert len(m.tokens) == len(m.colours)
    for colour, tokens in zip(m.colours, m.tokens):
        assert len(tokens) == 4
        assert all(YARD <= p <= HOME for p in tokens), (colour, tokens)

    # No two colours share an unsafe track square.
    owners: dict[int, str] = {}
    for colour, tokens in zip(m.colours, m.tokens):
        for p in tokens:
            square = track_square(colour, p)
            if square is None or square in SAFE_SQUARES:
                continue
            assert owners.setdefault(square, colour) == colour, f"{colour} shares square {square}"

    assert (m.roll is not None) == (m.phase == "awaiting_move")
    assert 0 <= m.sixes <= 2
    assert (m.winner is not None) == (m.phase == "finished")
    if m.winner:
        assert all(p == HOME for p in m.tokens_of(m.winner))
    # Only the mover's own tokens can advance; opponents can only be sent back to the yard.
    for colour, old, new in zip(m.colours, before.tokens, m.tokens):
        for o, n in zip(old, new):
            if colour != before.current_colour:
                assert n == o or n == YARD


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("colours", [("red", "yellow"), ("red", "green", "yellow", "blue")])
def test_random_matches_finish_with_one_winner(seed: int, colours: tuple[str, ...]) -> None:
    final, actions = play(seed, colours, on_step=check_invariants)
    assert final.phase == "finished"
    assert sum(all(p == HOME for p in t) for t in final.tokens) == 1
    assert any(a.get("move") is not None for a in actions)


def test_recorded_match_replays_to_the_same_result() -> None:
    data = json.loads(FIXTURE.read_text())
    match = new_match(data["colours"])
    for i, action in enumerate(data["actions"]):
        assert match.phase != "finished", f"match ended early at action {i}"
        assert action["colour"] == match.current_colour
        if "roll" in action:
            match = roll(match, action["colour"], action["roll"]).match
        else:
            match = move(match, action["colour"], action["move"]).match

    assert match.phase == "finished"
    assert match.winner == data["winner"]
    assert {c: list(match.tokens_of(c)) for c in match.colours} == data["final_tokens"]
