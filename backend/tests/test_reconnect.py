"""Seats survive dropped connections for the reconnect window."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from .conftest import create_room, player, reconnect, ws_headers
from .test_match import act, script_dice, start


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(app: FastAPI) -> Iterator[Clock]:
    fake = Clock()
    app.state.sessions.clock = fake
    yield fake


def away(snapshot: dict) -> dict[str, int | None]:
    return {m["nickname"]: m["away_ms"] for m in snapshot["members"]}


def test_disconnect_keeps_seat(client: TestClient, clock: Clock) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali, 2)
        with player(client, "Sara") as sara:
            sara.call("room.join", {"code": code})
            ali.snapshot()
        assert away(ali.snapshot()) == {"Ali": None, "Sara": 60_000}
        with player(client, "Omar") as omar:
            assert omar.call("room.join", {"code": code})["error"]["code"] == "ROOM_FULL"


def test_reconnect_restores_seat_with_a_full_snapshot(client: TestClient, clock: Clock) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali, 2)
        with player(client, "Sara") as sara:
            sara.call("room.join", {"code": code})
            sara.call("chat.send", {"text": "brb"})
        ali.sync()
        with reconnect(client, sara) as back:
            assert back.room_code == code
            snapshot = back.snapshot()
            assert away(snapshot) == {"Ali": None, "Sara": None}
            assert [m["text"] for m in snapshot["messages"]] == ["brb"]
            assert away(ali.snapshot()) == {"Ali": None, "Sara": None}
            assert back.call("chat.send", {"text": "back"})["ok"]


def test_session_ready_reports_no_room_when_seat_is_gone(client: TestClient, clock: Clock) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali, 2)
        with player(client, "Sara") as sara:
            sara.call("room.join", {"code": code})
        ali.sync()
        clock.now += 61
        assert away(ali.snapshot()) == {"Ali": None}  # Released by the background sweep.
        with reconnect(client, sara) as back:
            assert back.room_code is None


def test_room_closes_when_everyone_stays_away(client: TestClient, app: FastAPI, clock: Clock) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali)
    with player(client, "Sara") as sara:  # Keep the server busy while the sweep runs.
        assert app.state.rooms.get(code) is not None
        clock.now += 61
        app.state.rooms.expire_away()
        assert app.state.rooms.get(code) is None
        assert sara.call("room.join", {"code": code})["error"]["code"] == "ROOM_NOT_FOUND"


def test_newer_connection_takes_over(client: TestClient) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali, 2)
        with reconnect(client, ali) as second:
            assert second.room_code == code
            second.snapshot()
            with pytest.raises(WebSocketDisconnect) as exc:
                while True:
                    ali.ws.receive_json()
            assert exc.value.code == 4000
            # The old socket's cleanup did not mark Ali away.
            assert away(second.sync()) == {"Ali": None}


def test_match_pauses_until_player_returns(client: TestClient, app: FastAPI, clock: Clock) -> None:
    dice = script_dice(app, 5)
    with player(client, "Ali") as ali:
        code = create_room(ali, 2)
        with player(client, "Sara") as sara:
            sara.call("room.join", {"code": code})
            match = start([ali, sara])
        result, _ = act(ali, match, "match.roll")
        assert result["error"]["code"] == "MATCH_PAUSED"
        assert dice == [5]
        with reconnect(client, sara) as back:
            back.snapshot()
            result, match = act(ali, match, "match.roll")
            assert result["ok"] and match["events"][0] == {"colour": "red", "value": 5, "kind": "rolled"}
            assert back.sync()["match"] == match


def test_seat_expiry_ends_the_match(client: TestClient, clock: Clock) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali, 2)
        with player(client, "Sara") as sara:
            sara.call("room.join", {"code": code})
            start([ali, sara])
        ali.sync()
        clock.now += 61
        snapshot = ali.snapshot()
        assert snapshot["match"]["status"] == "ended"
        assert snapshot["match"]["ended_reason"] == "Sara did not come back, so the match ended."


def test_cannot_start_while_someone_is_away(client: TestClient, clock: Clock) -> None:
    with player(client, "Ali") as ali:
        code = create_room(ali, 4)
        with player(client, "Sara") as sara:
            sara.call("room.join", {"code": code})
            sara.call("match.ready", {"ready": True})
        ali.sync()
        assert ali.call("match.start", {})["error"]["code"] == "PLAYER_AWAY"


def test_retried_roll_after_reconnect_rolls_once(client: TestClient, app: FastAPI) -> None:
    dice = script_dice(app, 4, 6)
    with player(client, "Sara") as sara:
        with player(client, "Ali") as ali:
            code = create_room(ali, 2)
            sara.call("room.join", {"code": code})
            match = start([ali, sara])
            body = {"match_id": match["match_id"], "step": match["step"]}
            command_id = ali.send("match.roll", body)
            # The connection drops before Ali reads the result.
        sara.sync()
        with client.websocket_connect("/ws", headers=ws_headers(ali.credential)) as ws:
            ws.receive_json()  # session.ready
            ws.receive_json()  # The room snapshot.
            ws.send_json({"version": 1, "command_id": command_id, "type": "match.roll", "body": body})
            result = ws.receive_json()
            while result["type"] != "command.result":
                result = ws.receive_json()
            assert result["body"]["ok"]
        assert dice == [6]  # One die was drawn, not two.
        assert sara.sync()["match"]["step"] == 1
