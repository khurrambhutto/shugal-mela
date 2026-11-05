import ast
from pathlib import Path

import pytest

from app.ludo import rules
from app.ludo.rules import (
    HOME,
    SAFE_SQUARES,
    YARD,
    Captured,
    ExtraRoll,
    RuleError,
    legal_moves,
    move,
    new_match,
    roll,
    track_square,
)

from .helpers import kinds, match_with


def rejects(code: str, fn, *args) -> None:
    match = args[0]
    before = repr(match)
    with pytest.raises(RuleError) as exc:
        fn(*args)
    assert exc.value.code == code
    assert repr(match) == before  # Rejected actions never change the state.


# Setup and turn order


def test_new_four_player_match() -> None:
    match = new_match(["blue", "red", "yellow", "green"])
    assert match.colours == ("red", "green", "yellow", "blue")
    assert match.current_colour == "red"
    assert match.phase == "awaiting_roll"
    assert all(t == (YARD,) * 4 for t in match.tokens)


def test_two_players_use_opposite_colours() -> None:
    assert new_match(["yellow", "red"]).colours == ("red", "yellow")


def test_first_player_can_be_chosen() -> None:
    assert new_match(["red", "yellow"], first="yellow").current_colour == "yellow"


@pytest.mark.parametrize(
    "colours", [["red"], ["red", "green"], ["red", "red"], ["red", "green", "yellow"], ["red", "purple"]]
)
def test_invalid_players(colours: list[str]) -> None:
    with pytest.raises(RuleError) as exc:
        new_match(colours)
    assert exc.value.code == "INVALID_PLAYERS"


def test_turns_go_clockwise_and_wrap() -> None:
    match = new_match(["red", "green", "yellow", "blue"])
    seen = []
    for _ in range(5):
        seen.append(match.current_colour)
        match = roll(match, match.current_colour, 3).match  # No legal move: turn passes.
    assert seen == ["red", "green", "yellow", "blue", "red"]


# Rejected actions


def test_wrong_player_cannot_roll() -> None:
    rejects("NOT_YOUR_TURN", roll, new_match(["red", "yellow"]), "yellow", 6)


def test_unknown_colour_cannot_roll() -> None:
    rejects("NOT_YOUR_TURN", roll, new_match(["red", "yellow"]), "green", 6)


@pytest.mark.parametrize("value", [0, 7, -1, 2.0, True, "6", None])
def test_invalid_die(value) -> None:
    rejects("INVALID_DIE", roll, new_match(["red", "yellow"]), "red", value)


def test_cannot_roll_while_a_move_is_pending() -> None:
    match = roll(new_match(["red", "yellow"]), "red", 6).match
    rejects("WRONG_PHASE", roll, match, "red", 4)


def test_cannot_move_before_rolling() -> None:
    rejects("WRONG_PHASE", move, match_with({"red": (5, -1, -1, -1)}), "red", 0)


@pytest.mark.parametrize("token", [1, 4, -1, "0", None])
def test_illegal_token_choice(token) -> None:
    match = roll(match_with({"red": (5, -1, -1, -1)}), "red", 3).match
    rejects("ILLEGAL_MOVE", move, match, "red", token)


def test_nothing_is_allowed_after_the_match_ends() -> None:
    match = match_with({"red": (HOME,) * 4}, phase="finished", winner="red")
    rejects("MATCH_FINISHED", roll, match, "red", 6)
    rejects("MATCH_FINISHED", move, match, "red", 0)


# Leaving the yard


def test_only_a_six_leaves_the_yard() -> None:
    for value in range(1, 6):
        t = roll(new_match(["red", "yellow"]), "red", value)
        assert kinds(t) == ["rolled", "no_legal_move", "turn_passed"]
        assert t.match.current_colour == "yellow"


def test_six_moves_a_token_to_its_start_and_rolls_again() -> None:
    t = roll(new_match(["red", "yellow"]), "red", 6)
    assert t.match.phase == "awaiting_move"
    assert legal_moves(t.match) == (0, 1, 2, 3)

    t = move(t.match, "red", 2)
    assert t.match.tokens_of("red") == (YARD, YARD, 0, YARD)
    assert t.events[-1] == ExtraRoll("red", "six")
    assert t.match.current_colour == "red" and t.match.phase == "awaiting_roll"


def test_player_must_choose_even_with_one_legal_move() -> None:
    t = roll(match_with({"red": (10, -1, -1, -1)}), "red", 4)
    assert t.match.phase == "awaiting_move"
    assert legal_moves(t.match) == (0,)


# Movement and the board


def test_move_advances_by_the_roll_and_passes_turn() -> None:
    match = roll(match_with({"red": (10, -1, -1, -1)}), "red", 4).match
    t = move(match, "red", 0)
    assert t.match.tokens_of("red")[0] == 14
    assert kinds(t) == ["moved", "turn_passed"]
    assert t.match.current_colour == "yellow"


def test_track_wraps_and_enters_the_home_column() -> None:
    assert track_square("yellow", 0) == 26
    assert track_square("yellow", 30) == 4  # Wrapped past square 51.
    assert track_square("yellow", 50) == 24  # Last shared square before its home column.
    assert track_square("yellow", 51) is None  # Private home column.
    assert track_square("red", YARD) is None and track_square("red", HOME) is None


def test_safe_squares_are_starts_and_stars() -> None:
    assert SAFE_SQUARES == {0, 8, 13, 21, 26, 34, 39, 47}


# Captures


def test_landing_on_an_opponent_captures_it() -> None:
    # Red at progress 10 is square 10. Yellow progress 36 is square (26 + 36) % 52 = 10.
    match = match_with({"red": (7, -1, -1, -1), "yellow": (36, 5, -1, -1)})
    t = move(roll(match, "red", 3).match, "red", 0)
    assert t.match.tokens_of("yellow") == (YARD, 5, -1, -1)
    assert Captured("yellow", 0, "red") in t.events
    assert t.events[-1] == ExtraRoll("red", "capture")
    assert t.match.current_colour == "red"


def test_capture_sends_every_opponent_token_on_the_square_home() -> None:
    match = match_with(
        {"red": (7, -1, -1, -1), "green": (49, 49, 2, -1), "yellow": (36, -1, -1, -1)},
        colours=("red", "green", "yellow", "blue"),
    )
    # Green progress 49 is square (13 + 49) % 52 = 10, the same square as yellow's token.
    t = move(roll(match, "red", 3).match, "red", 0)
    assert t.match.tokens_of("green") == (YARD, YARD, 2, -1)
    assert t.match.tokens_of("yellow") == (YARD, -1, -1, -1)
    assert sum(e.kind == "captured" for e in t.events) == 3


@pytest.mark.parametrize("square", sorted(SAFE_SQUARES))
def test_no_capture_on_safe_squares(square: int) -> None:
    # The mover lands on the square by a roll of 1; the victim already sits there.
    mover, victim = ("yellow", "red") if square == 0 else ("red", "yellow")
    to = (square - rules.START[mover]) % 52
    there = (square - rules.START[victim]) % 52
    match = match_with({mover: (to - 1, -1, -1, -1), victim: (there, -1, -1, -1)})
    if mover == "yellow":
        match = match_with({mover: (to - 1, -1, -1, -1), victim: (there, -1, -1, -1)}, current=1)
    t = move(roll(match, mover, 1).match, mover, 0)
    assert t.match.tokens_of(victim)[0] == there
    assert "captured" not in kinds(t)


def test_entering_onto_a_start_square_with_an_opponent_is_safe() -> None:
    # Yellow progress 26 sits on red's start square 0.
    t = move(roll(match_with({"yellow": (26, -1, -1, -1)}), "red", 6).match, "red", 0)
    assert t.match.tokens_of("yellow")[0] == 26
    assert "captured" not in kinds(t)


def test_own_tokens_share_squares_without_blocking() -> None:
    match = roll(match_with({"red": (10, 12, -1, -1), "yellow": (40, -1, -1, -1)}), "red", 2).match
    t = move(match, "red", 0)
    assert t.match.tokens_of("red")[:2] == (12, 12)
    # A stack of two does not block an opponent passing or landing on it.
    stacked = match_with({"red": (12, 12, -1, -1), "yellow": (36, -1, -1, -1)}, current=1)
    t = move(roll(stacked, "yellow", 4).match, "yellow", 0)  # Yellow 40 is square 14, past 12.
    assert t.match.tokens_of("yellow")[0] == 40
    captured = move(roll(match_with({"red": (12, 12, -1, -1), "yellow": (36, -1, -1, -1)}, current=1), "yellow", 2).match, "yellow", 0)
    assert captured.match.tokens_of("red")[:2] == (YARD, YARD)  # Square 12 is unsafe.


def test_home_column_is_private() -> None:
    # Red progress 52 and yellow progress 52 are both in private columns; no interaction.
    match = match_with({"red": (50, -1, -1, -1), "yellow": (52, -1, -1, -1)})
    t = move(roll(match, "red", 2).match, "red", 0)
    assert t.match.tokens_of("yellow")[0] == 52
    assert "captured" not in kinds(t)


# Finishing


def test_exact_roll_is_needed_to_reach_home() -> None:
    match = match_with({"red": (53, -1, -1, -1)})
    t = roll(match, "red", 4)  # 53 + 4 overshoots 56.
    assert kinds(t) == ["rolled", "no_legal_move", "turn_passed"]

    t = move(roll(match, "red", 3).match, "red", 0)
    assert t.match.tokens_of("red")[0] == HOME
    assert kinds(t) == ["moved", "token_home", "extra_roll"]
    assert t.events[-1] == ExtraRoll("red", "home")


def test_finished_tokens_cannot_move() -> None:
    match = roll(match_with({"red": (HOME, 20, -1, -1)}), "red", 1).match
    assert legal_moves(match) == (1,)


def test_last_token_home_wins() -> None:
    match = match_with({"red": (HOME, HOME, HOME, 55)})
    t = move(roll(match, "red", 1).match, "red", 3)
    assert t.match.phase == "finished"
    assert t.match.winner == "red"
    assert kinds(t) == ["moved", "token_home", "won"]
    assert legal_moves(t.match) == ()


# Extra rolls and sixes


def test_six_with_no_legal_move_still_rolls_again() -> None:
    match = match_with({"red": (HOME, HOME, HOME, 53)})
    t = roll(match, "red", 6)
    assert kinds(t) == ["rolled", "no_legal_move", "extra_roll"]
    assert t.match.current_colour == "red" and t.match.sixes == 1


def test_six_and_capture_grant_only_one_extra_roll() -> None:
    match = match_with({"red": (4, -1, -1, -1), "yellow": (36, -1, -1, -1)})
    t = move(roll(match, "red", 6).match, "red", 0)
    assert "captured" in kinds(t)
    assert [e for e in t.events if e.kind == "extra_roll"] == [ExtraRoll("red", "six")]
    # One more roll, then a non-six without a bonus ends the turn.
    t = move(roll(t.match, "red", 2).match, "red", 0)
    assert t.match.current_colour == "yellow"


def test_capture_bonus_resets_the_six_count() -> None:
    match = match_with({"red": (7, 20, -1, -1), "yellow": (36, -1, -1, -1)}, sixes=0)
    t = move(roll(match, "red", 3).match, "red", 0)
    assert t.match.sixes == 0


def test_third_consecutive_six_is_forfeited() -> None:
    match = match_with({"red": (10, -1, -1, -1)})
    match = move(roll(match, "red", 6).match, "red", 0).match  # 16
    match = move(roll(match, "red", 6).match, "red", 0).match  # 22
    assert match.sixes == 2
    t = roll(match, "red", 6)
    assert kinds(t) == ["rolled", "sixes_forfeited", "turn_passed"]
    assert t.match.tokens_of("red")[0] == 22  # Earlier moves stay.
    assert t.match.current_colour == "yellow" and t.match.sixes == 0


def test_non_six_resets_the_count() -> None:
    match = match_with({"red": (10, -1, -1, -1), "yellow": (40, -1, -1, -1)})
    match = move(roll(match, "red", 6).match, "red", 0).match
    # Red 16 + 4 = 20, square 20; yellow 40 is square 14, so no capture: turn passes.
    t = move(roll(match, "red", 4).match, "red", 0)
    assert t.match.current_colour == "yellow" and t.match.sixes == 0


def test_bonus_after_two_sixes_still_forfeits_a_third_six() -> None:
    match = match_with({"red": (4, 30, -1, -1), "yellow": (36, -1, -1, -1)})
    match = move(roll(match, "red", 6).match, "red", 1).match  # Six one.
    match = move(roll(match, "red", 6).match, "red", 0).match  # Six two: 4 -> 10 captures yellow.
    assert match.sixes == 2
    assert roll(match, "red", 6).match.current_colour == "yellow"


# Module boundary


def test_rules_module_has_no_transport_or_storage_imports() -> None:
    tree = ast.parse(Path(rules.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"collections", "dataclasses", "typing"}
    assert "random" not in imported
