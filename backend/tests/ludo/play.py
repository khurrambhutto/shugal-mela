"""Play seeded random matches, and regenerate the recorded complete-match fixture.

    uv run python -m tests.ludo.play   # rewrites tests/fixtures/ludo/complete-match.json
"""

import json
import random
from pathlib import Path
from typing import Any

from app.ludo.rules import Match, Transition, legal_moves, move, new_match, roll

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/ludo/complete-match.json"
MAX_ACTIONS = 50_000


def play(seed: int, colours: tuple[str, ...], on_step=None) -> tuple[Match, list[dict[str, Any]]]:
    """Play random legal actions until someone wins. Returns the final match and the actions."""
    rng = random.Random(seed)
    match = new_match(colours)
    actions: list[dict[str, Any]] = []
    for _ in range(MAX_ACTIONS):
        if match.phase == "finished":
            return match, actions
        colour = match.current_colour
        if match.phase == "awaiting_roll":
            value = rng.randint(1, 6)
            t: Transition = roll(match, colour, value)
            actions.append({"colour": colour, "roll": value})
        else:
            token = rng.choice(legal_moves(match))
            t = move(match, colour, token)
            actions.append({"colour": colour, "move": token})
        if on_step:
            on_step(match, t)
        match = t.match
    raise AssertionError(f"seed {seed} did not finish within {MAX_ACTIONS} actions")


def record(seed: int = 2026, colours: tuple[str, ...] = ("red", "green", "yellow", "blue")) -> dict[str, Any]:
    final, actions = play(seed, colours)
    return {
        "description": "A complete four-player match from random legal play. Regenerate with "
        "`uv run python -m tests.ludo.play`.",
        "seed": seed,
        "colours": list(colours),
        "actions": actions,
        "winner": final.winner,
        "final_tokens": {c: list(final.tokens_of(c)) for c in final.colours},
    }


if __name__ == "__main__":
    data = record()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {len(data['actions'])} actions, winner {data['winner']}, to {FIXTURE}")
