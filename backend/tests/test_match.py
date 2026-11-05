from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import load_settings
from app.ludo.rules import HOME

from .conftest import Player, create_room, player


def script_dice(app: FastAPI, *values: int) -> list[int]:
    """Make the server roll these values in order. Returns the list so tests can extend it."""
    queue = list(values)
    app.state.rooms.dice = lambda: queue.pop(0)
    return queue


@contextmanager
def room_of(client: TestClient, count: int, capacity: int | None = None) -> Iterator[list[Player]]:
    names = ["Ali", "Sara", "Omar", "Zara"][:count]
    with ExitStack() as stack:
        players = [stack.enter_context(player(client, n)) for n in names]
        code = create_room(players[0], capacity or (2 if count <= 2 else 4))
        for p in players[1:]:
            assert p.call("room.join", {"code": code})["ok"]
        yield players


def ready_all(players: list[Player]) -> None:
    for p in players[1:]:
        assert p.call("match.ready", {"ready": True})["ok"]


def start(players: list[Player]) -> dict:
    ready_all(players)
    result = players[0].call("match.start", {})
    assert result["ok"], result
    return players[0].sync()["match"]


def act(p: Player, match: dict, type_: str, **body) -> tuple[dict, dict]:
    result = p.call(type_, {"match_id": match["match_id"], "step": match["step"], **body})
    return result, (p.sync()["match"] if result["ok"] else match)


# Ready and start


def test_ready_is_shared_with_members(client: TestClient) -> None:
    with room_of(client, 2) as (ali, sara):
        assert sara.call("match.ready", {"ready": True})["ok"]
        assert ali.sync()["ready"] == [sara.session_id]
        assert sara.call("match.ready", {"ready": False})["ok"]
        assert ali.sync()["ready"] == []


def test_host_starts_two_player_match(client: TestClient) -> None:
    with room_of(client, 2) as (ali, sara):
        match = start([ali, sara])
        assert match["status"] == "playing"
        assert match["seats"] == [
            {"session_id": ali.session_id, "colour": "red"},
            {"session_id": sara.session_id, "colour": "yellow"},
        ]
        assert match["current"] == "red" and match["phase"] == "awaiting_roll"
        assert match["tokens"] == {"red": [-1] * 4, "yellow": [-1] * 4}
        assert sara.sync()["match"] == match


def test_four_player_seats_follow_join_order(client: TestClient) -> None:
    with room_of(client, 4) as players:
        match = start(players)
        assert [s["colour"] for s in match["seats"]] == ["red", "green", "yellow", "blue"]
        assert [s["session_id"] for s in match["seats"]] == [p.session_id for p in players]


def test_two_players_in_a_four_seat_room_can_play(client: TestClient) -> None:
    with room_of(client, 2, capacity=4) as players:
        assert start(players)["colours"] == ["red", "yellow"]


def test_only_host_can_start(client: TestClient) -> None:
    with room_of(client, 2) as (ali, sara):
        sara.call("match.ready", {"ready": True})
        assert sara.call("match.start", {})["error"]["code"] == "NOT_HOST"
        assert ali.sync()["match"] is None


def test_start_needs_everyone_ready(client: TestClient) -> None:
    with room_of(client, 2) as (ali, _sara):
        assert ali.call("match.start", {})["error"]["code"] == "NOT_READY"


def test_three_players_cannot_start(client: TestClient) -> None:
    with room_of(client, 3) as players:
        ready_all(players)
        assert players[0].call("match.start", {})["error"]["code"] == "WRONG_PLAYER_COUNT"


def test_cannot_join_or_ready_during_a_match(client: TestClient) -> None:
    with room_of(client, 2, capacity=4) as (ali, sara), player(client, "Omar") as omar:
        start([ali, sara])
        code = ali.sync()["code"]
        assert omar.call("room.join", {"code": code})["error"]["code"] == "MATCH_IN_PROGRESS"
        assert sara.call("match.ready", {"ready": True})["error"]["code"] == "MATCH_IN_PROGRESS"
        assert ali.call("match.start", {})["error"]["code"] == "MATCH_IN_PROGRESS"


# Turns


def test_server_rolls_and_everyone_sees_it(client: TestClient, app: FastAPI) -> None:
    script_dice(app, 6)
    with room_of(client, 2) as (ali, sara):
        match = start([ali, sara])
        result, match = act(ali, match, "match.roll")
        assert result["ok"]
        assert match["roll"] == 6 and match["phase"] == "awaiting_move"
        assert match["legal_moves"] == [0, 1, 2, 3]
        assert match["events"] == [{"colour": "red", "value": 6, "kind": "rolled"}]
        assert sara.sync()["match"] == match

        result, match = act(ali, match, "match.move", token=2)
        assert match["tokens"]["red"] == [-1, -1, 0, -1]
        assert [e["kind"] for e in match["events"]] == ["moved", "extra_roll"]
        assert match["step"] == 2


def test_wrong_player_cannot_roll(client: TestClient, app: FastAPI) -> None:
    dice = script_dice(app, 3)
    with room_of(client, 2) as (ali, sara):
        match = start([ali, sara])
        result, after = act(sara, match, "match.roll")
        assert result["error"]["code"] == "NOT_YOUR_TURN"
        assert sara.sync()["match"] == match
        assert dice == [3]  # The rejected roll drew nothing from the dice.


def test_cannot_move_before_rolling_or_an_illegal_token(client: TestClient, app: FastAPI) -> None:
    script_dice(app, 6)
    with room_of(client, 2) as (ali, sara):
        match = start([ali, sara])
        result, _ = act(ali, match, "match.move", token=0)
        assert result["error"]["code"] == "WRONG_PHASE"
        _, match = act(ali, match, "match.roll")
        _, match = act(ali, match, "match.move", token=0)  # Token 0 to start; red rolls again.
        script_dice(app, 2)
        _, match = act(ali, match, "match.roll")
        result, _ = act(ali, match, "match.move", token=1)  # Token 1 is in the yard.
        assert result["error"]["code"] == "ILLEGAL_MOVE"


def test_stale_step_is_rejected(client: TestClient, app: FastAPI) -> None:
    script_dice(app, 6, 4)
    with room_of(client, 2) as (ali, sara):
        old = start([ali, sara])
        _, current = act(ali, old, "match.roll")
        result, _ = act(ali, old, "match.move", token=0)  # Made against the old step.
        assert result["error"]["code"] == "STALE_STATE"
        result = ali.call("match.roll", {"match_id": "someone-else", "step": current["step"]})
        assert result["error"]["code"] == "STALE_STATE"
        assert ali.sync()["match"] == current


def test_double_click_rolls_once(client: TestClient, app: FastAPI) -> None:
    dice = script_dice(app, 2, 5)
    with room_of(client, 2) as (ali, sara):
        match = start([ali, sara])
        body = {"match_id": match["match_id"], "step": match["step"]}
        first = ali.send("match.roll", body)
        second = ali.send("match.roll", body)  # Same step: a second click.
        assert ali.result(first)["ok"]
        assert ali.result(second)["error"]["code"] in ("STALE_STATE", "NOT_YOUR_TURN")
        assert dice == [5]
        # A retried command ID returns the original result without rolling again.
        ali.send("match.roll", body, command_id=first)
        assert ali.result(first)["ok"]
        assert dice == [5]


def test_turn_passes_without_legal_move(client: TestClient, app: FastAPI) -> None:
    script_dice(app, 3)
    with room_of(client, 2) as (ali, sara):
        _, match = act(ali, start([ali, sara]), "match.roll")
        assert match["current"] == "yellow"
        assert [e["kind"] for e in match["events"]] == ["rolled", "no_legal_move", "turn_passed"]


def test_game_commands_are_room_isolated(client: TestClient, app: FastAPI) -> None:
    script_dice(app, 6)
    with room_of(client, 2) as (ali, sara), player(client, "Omar") as omar:
        match = start([ali, sara])
        create_room(omar)
        omar.drain()
        result = omar.call("match.roll", {"match_id": match["match_id"], "step": match["step"]})
        assert result["error"]["code"] == "NO_MATCH"
        act(ali, match, "match.roll")
        assert omar.drain() == []


# Ending and rematch


def test_leaving_mid_match_ends_it(client: TestClient) -> None:
    with room_of(client, 2, capacity=4) as (ali, sara):
        start([ali, sara])
        sara.call("room.leave", {})
        match = ali.sync()["match"]
        assert match["status"] == "ended"
        assert match["ended_reason"] == "Sara left, so the match ended."
        assert match["legal_moves"] == []


def test_win_then_rematch_gets_a_new_match(client: TestClient, app: FastAPI) -> None:
    script_dice(app, 1)
    with room_of(client, 2) as (ali, sara):
        first = start([ali, sara])
        # Put red one step from winning, then roll the 1.
        room = app.state.rooms.get(ali.sync()["code"])
        state = room.match.state
        room.match.state = type(state)(**{**state.__dict__, "tokens": ((HOME, HOME, HOME, 55), (-1,) * 4)})
        first = ali.sync()["match"]
        _, rolled = act(ali, first, "match.roll")
        _, won = act(ali, rolled, "match.move", token=3)
        assert won["status"] == "finished" and won["winner"] == "red"
        assert won["events"][-1] == {"colour": "red", "kind": "won"}

        # Nothing more can be played; the lobby opens again.
        result, _ = act(sara, won, "match.roll")
        assert result["error"]["code"] == "NO_MATCH"
        rematch = start([ali, sara])
        assert rematch["match_id"] != won["match_id"]
        assert rematch["tokens"] == {"red": [-1] * 4, "yellow": [-1] * 4}
        assert rematch["step"] == 0


def test_host_moves_to_next_member(client: TestClient) -> None:
    with room_of(client, 3, capacity=4) as (ali, sara, omar):
        ali.call("room.leave", {})
        assert sara.sync()["host"] == sara.session_id
        omar.call("match.ready", {"ready": True})
        assert sara.call("match.start", {})["ok"]


def test_dice_seed_is_refused_outside_development() -> None:
    with pytest.raises(ValueError):
        load_settings(
            {"APP_MODE": "public", "ALLOWED_ORIGINS": "https://a.trycloudflare.com", "DICE_SEED": "1"}
        )
