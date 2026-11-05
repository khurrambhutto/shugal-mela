"""An online Ludo match: seats, identity, and step tracking around the pure rules.

No transport code lives here. Dice come from an injected function so tests are deterministic.
"""

import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.ludo import rules
from app.ludo.rules import Colour, Event, Match

MatchStatus = Literal["playing", "finished", "ended"]
Dice = Callable[[], int]

TWO_SEATS: tuple[Colour, ...] = ("red", "yellow")
FOUR_SEATS: tuple[Colour, ...] = ("red", "green", "yellow", "blue")


def secure_die() -> int:
    return secrets.randbelow(6) + 1


@dataclass(eq=False)
class OnlineMatch:
    match_id: str
    seats: tuple[tuple[str, Colour], ...]  # (session_id, colour) in join order.
    state: Match
    step: int = 0
    events: tuple[Event, ...] = ()
    status: MatchStatus = "playing"
    ended_reason: str | None = None
    _colour_by_session: dict[str, Colour] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._colour_by_session = dict(self.seats)

    def colour_of(self, session_id: str) -> Colour | None:
        return self._colour_by_session.get(session_id)

    def is_seated(self, session_id: str) -> bool:
        return session_id in self._colour_by_session

    def apply(self, session_id: str, action: Literal["roll", "move"], dice: Dice, token: int = -1) -> None:
        """Apply one roll or move for the session's seat. Raises rules.RuleError unchanged."""
        colour = self.colour_of(session_id)
        if colour is None:
            raise rules.RuleError("NOT_YOUR_TURN", "You are not playing in this match.")
        if action == "roll":
            transition = rules.roll(self.state, colour, _checked_roll(self.state, colour, dice))
        else:
            transition = rules.move(self.state, colour, token)
        self.state = transition.match
        self.events = transition.events
        self.step += 1
        if self.state.phase == "finished":
            self.status = "finished"

    def end(self, reason: str) -> None:
        self.status = "ended"
        self.ended_reason = reason
        self.events = ()
        self.step += 1

    def public(self) -> dict[str, Any]:
        state = self.state
        return {
            "match_id": self.match_id,
            "status": self.status,
            "seats": [{"session_id": s, "colour": c} for s, c in self.seats],
            "colours": list(state.colours),
            "tokens": {c: list(state.tokens_of(c)) for c in state.colours},
            "current": state.current_colour,
            "phase": state.phase,
            "roll": state.roll,
            "legal_moves": list(rules.legal_moves(state)) if self.status == "playing" else [],
            "winner": state.winner,
            "step": self.step,
            "events": [asdict(e) for e in self.events],
            "ended_reason": self.ended_reason,
        }


def _checked_roll(state: Match, colour: Colour, dice: Dice) -> int:
    # Validate turn and phase with a harmless value first, so an invalid roll attempt
    # is rejected without drawing from the dice source.
    rules.roll(state, colour, 1)
    return dice()


def start_match(member_ids: list[str]) -> OnlineMatch:
    colours = TWO_SEATS if len(member_ids) == 2 else FOUR_SEATS
    seats = tuple(zip(member_ids, colours, strict=True))
    state = rules.new_match(colours, first=colours[0])
    return OnlineMatch(match_id=secrets.token_hex(8), seats=seats, state=state)
