"""Ludo rules as pure, immutable transitions. See specs/002-ludo-rules/spec.md.

Dice values are inputs: the server rolls, the rules only apply. Nothing here knows about
networking, storage, or the browser, and every transition returns a new Match.

Token progress counts steps from the colour's own start square:
    -1        in the yard
    0..50     on the shared 52-square track (0 is the start square)
    51..55    in the colour's private home column
    56        home (finished)
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Literal

Colour = Literal["red", "green", "yellow", "blue"]
Phase = Literal["awaiting_roll", "awaiting_move", "finished"]
ErrorCode = Literal[
    "INVALID_PLAYERS", "INVALID_DIE", "NOT_YOUR_TURN", "WRONG_PHASE", "ILLEGAL_MOVE", "MATCH_FINISHED"
]
BonusReason = Literal["six", "capture", "home"]

SEAT_ORDER: tuple[Colour, ...] = ("red", "green", "yellow", "blue")
TWO_PLAYER_COLOURS: frozenset[Colour] = frozenset({"red", "yellow"})
TOKENS_PER_COLOUR = 4
TRACK_SQUARES = 52
LAST_TRACK_STEP = 50
HOME = 56
YARD = -1
START: dict[Colour, int] = {"red": 0, "green": 13, "yellow": 26, "blue": 39}
STAR_OFFSET = 8
SAFE_SQUARES = frozenset(s + o for s in START.values() for o in (0, STAR_OFFSET))


class RuleError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


# Events describe what a transition did, in order, for the online feature to report.


@dataclass(frozen=True)
class Rolled:
    colour: Colour
    value: int
    kind: Literal["rolled"] = "rolled"


@dataclass(frozen=True)
class Moved:
    colour: Colour
    token: int
    from_progress: int
    to_progress: int
    kind: Literal["moved"] = "moved"


@dataclass(frozen=True)
class Captured:
    colour: Colour
    token: int
    by: Colour
    kind: Literal["captured"] = "captured"


@dataclass(frozen=True)
class TokenHome:
    colour: Colour
    token: int
    kind: Literal["token_home"] = "token_home"


@dataclass(frozen=True)
class ExtraRoll:
    colour: Colour
    reason: BonusReason
    kind: Literal["extra_roll"] = "extra_roll"


@dataclass(frozen=True)
class SixesForfeited:
    colour: Colour
    kind: Literal["sixes_forfeited"] = "sixes_forfeited"


@dataclass(frozen=True)
class NoLegalMove:
    colour: Colour
    kind: Literal["no_legal_move"] = "no_legal_move"


@dataclass(frozen=True)
class TurnPassed:
    to: Colour
    kind: Literal["turn_passed"] = "turn_passed"


@dataclass(frozen=True)
class Won:
    colour: Colour
    kind: Literal["won"] = "won"


Event = Rolled | Moved | Captured | TokenHome | ExtraRoll | SixesForfeited | NoLegalMove | TurnPassed | Won


@dataclass(frozen=True)
class Match:
    colours: tuple[Colour, ...]  # Turn order.
    tokens: tuple[tuple[int, ...], ...]  # tokens[i] belongs to colours[i].
    current: int = 0
    phase: Phase = "awaiting_roll"
    roll: int | None = None  # The roll waiting for a move.
    sixes: int = 0  # Consecutive sixes rolled this turn.
    winner: Colour | None = None

    @property
    def current_colour(self) -> Colour:
        return self.colours[self.current]

    def tokens_of(self, colour: Colour) -> tuple[int, ...]:
        return self.tokens[self.colours.index(colour)]


@dataclass(frozen=True)
class Transition:
    match: Match
    events: tuple[Event, ...]


def track_square(colour: Colour, progress: int) -> int | None:
    """The shared track square for a token, or None in the yard, home column, or home."""
    if 0 <= progress <= LAST_TRACK_STEP:
        return (START[colour] + progress) % TRACK_SQUARES
    return None


def new_match(colours: Iterable[str], first: str | None = None) -> Match:
    chosen = list(colours)
    unique = set(chosen)
    if len(unique) != len(chosen) or not (unique == TWO_PLAYER_COLOURS or unique == set(SEAT_ORDER)):
        raise RuleError("INVALID_PLAYERS", "Play with red and yellow, or with all four colours.")
    order = tuple(c for c in SEAT_ORDER if c in unique)
    current = 0
    if first is not None:
        if first not in order:
            raise RuleError("INVALID_PLAYERS", "The first player must be one of the colours.")
        current = order.index(first)
    return Match(
        colours=order,
        tokens=tuple((YARD,) * TOKENS_PER_COLOUR for _ in order),
        current=current,
    )


def legal_moves(match: Match) -> tuple[int, ...]:
    if match.phase != "awaiting_move" or match.roll is None:
        return ()
    tokens = match.tokens[match.current]
    return tuple(i for i, p in enumerate(tokens) if _destination(p, match.roll) is not None)


def roll(match: Match, colour: str, value: int) -> Transition:
    _check_turn(match, colour, "awaiting_roll")
    if type(value) is not int or not 1 <= value <= 6:
        raise RuleError("INVALID_DIE", "A die shows 1 to 6.")

    player = match.current_colour
    events: list[Event] = [Rolled(player, value)]
    if value == 6 and match.sixes == 2:
        events.append(SixesForfeited(player))
        return _pass_turn(match, events)

    sixes = match.sixes + 1 if value == 6 else 0
    pending = replace(match, phase="awaiting_move", roll=value, sixes=sixes)
    if legal_moves(pending):
        return Transition(pending, tuple(events))

    events.append(NoLegalMove(player))
    if value == 6:
        events.append(ExtraRoll(player, "six"))
        return Transition(replace(match, sixes=sixes), tuple(events))
    return _pass_turn(match, events)


def move(match: Match, colour: str, token: int) -> Transition:
    _check_turn(match, colour, "awaiting_move")
    if type(token) is not int or token not in legal_moves(match):
        raise RuleError("ILLEGAL_MOVE", "That token cannot move with this roll.")
    assert match.roll is not None

    player = match.current_colour
    me = match.current
    tokens = [list(t) for t in match.tokens]
    start = tokens[me][token]
    dest = _destination(start, match.roll)
    assert dest is not None
    tokens[me][token] = dest
    events: list[Event] = [Moved(player, token, start, dest)]

    captured = False
    square = track_square(player, dest)
    if square is not None and square not in SAFE_SQUARES:
        for other_index, other in enumerate(match.colours):
            if other_index == me:
                continue
            for k, progress in enumerate(tokens[other_index]):
                if track_square(other, progress) == square:
                    tokens[other_index][k] = YARD
                    events.append(Captured(other, k, player))
                    captured = True

    reached_home = dest == HOME
    if reached_home:
        events.append(TokenHome(player, token))

    after = replace(match, tokens=tuple(tuple(t) for t in tokens), roll=None)
    if all(p == HOME for p in tokens[me]):
        events.append(Won(player))
        return Transition(replace(after, phase="finished", winner=player, sixes=0), tuple(events))

    # A move earns at most one extra roll, whatever combination of reasons applies.
    reason: BonusReason | None = (
        "six" if match.roll == 6 else "capture" if captured else "home" if reached_home else None
    )
    if reason is not None:
        events.append(ExtraRoll(player, reason))
        return Transition(replace(after, phase="awaiting_roll"), tuple(events))
    return _pass_turn(after, events)


def _destination(progress: int, value: int) -> int | None:
    if progress == YARD:
        return 0 if value == 6 else None
    if progress == HOME or progress + value > HOME:
        return None
    return progress + value


def _check_turn(match: Match, colour: str, phase: Phase) -> None:
    if match.phase == "finished":
        raise RuleError("MATCH_FINISHED", "The match is over.")
    if colour != match.current_colour:
        raise RuleError("NOT_YOUR_TURN", "It is not your turn.")
    if match.phase != phase:
        expected = "roll" if match.phase == "awaiting_roll" else "move a token"
        raise RuleError("WRONG_PHASE", f"You need to {expected} now.")


def _pass_turn(match: Match, events: list[Event]) -> Transition:
    following = (match.current + 1) % len(match.colours)
    events.append(TurnPassed(match.colours[following]))
    passed = replace(match, current=following, phase="awaiting_roll", roll=None, sixes=0)
    return Transition(passed, tuple(events))
