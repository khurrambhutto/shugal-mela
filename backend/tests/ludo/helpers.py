from dataclasses import replace

from app.ludo.rules import Match, new_match


def match_with(tokens: dict[str, tuple[int, ...]], colours=("red", "yellow"), **fields) -> Match:
    """A match with chosen token positions. Colours not listed keep all tokens in the yard."""
    match = new_match(colours)
    positions = tuple(tuple(tokens.get(c, (-1, -1, -1, -1))) for c in match.colours)
    return replace(match, tokens=positions, **fields)


def kinds(transition) -> list[str]:
    return [event.kind for event in transition.events]
