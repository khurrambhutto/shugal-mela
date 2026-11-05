import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.connections import Connection

from .conftest import ORIGIN, create_room, new_session, player, ws_headers

# Connection and authentication


def test_session_ready_names_the_session(client: TestClient) -> None:
    credential = new_session(client, "Ali")
    with client.websocket_connect("/ws", headers=ws_headers(credential)) as ws:
        ready = ws.receive_json()
    assert ready["type"] == "session.ready"
    assert ready["version"] == 1
    assert ready["body"]["nickname"] == "Ali"
    assert credential not in json.dumps(ready)


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": ORIGIN},  # No cookie.
        {"origin": ORIGIN, "cookie": "shugal_session=forged"},
    ],
)
def test_rejects_unauthenticated(client: TestClient, headers: dict[str, str]) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers=headers):
            pass


@pytest.mark.parametrize("origin", ["", "http://evil.example", "http://127.0.0.1:8000"])
def test_rejects_untrusted_origin(client: TestClient, origin: str) -> None:
    credential = new_session(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers=ws_headers(credential, origin)):
            pass


def test_session_can_reconnect_after_close(client: TestClient) -> None:
    credential = new_session(client)
    for _ in range(2):
        with client.websocket_connect("/ws", headers=ws_headers(credential)) as ws:
            assert ws.receive_json()["type"] == "session.ready"


# Malformed and unsupported input


@pytest.mark.parametrize("raw", ["not json", "[]", "42", '{"type":"room.create"}'])
def test_malformed_command(client: TestClient, raw: str) -> None:
    with player(client) as p:
        p.ws.send_text(raw)
        result = p.result(None)
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "type_, body",
    [
        ("room.dance", {}),
        ("room.create", {"capacity": 3}),
        ("room.create", {"capacity": "2"}),
        ("room.join", {}),
        ("chat.send", {"text": "hi", "sender_id": "someone-else"}),
        ("room.leave", {"room": "ABCDEF"}),
    ],
)
def test_invalid_command_keeps_its_id(client: TestClient, type_: str, body: dict) -> None:
    with player(client) as p:
        result = p.call(type_, body)
    assert result["error"]["code"] == "VALIDATION_ERROR"


def test_extra_envelope_field_rejected(client: TestClient) -> None:
    with player(client) as p:
        assert p.call("room.create", {"capacity": 2}, sender_id="x")["error"]["code"] == "VALIDATION_ERROR"


def test_unsupported_version(client: TestClient) -> None:
    with player(client) as p:
        command_id = str(uuid.uuid4())
        p.ws.send_json({"version": 2, "command_id": command_id, "type": "room.sync", "body": {}})
        assert p.result(command_id)["error"]["code"] == "UNSUPPORTED_VERSION"


def test_oversized_message_closes_with_1009(client: TestClient) -> None:
    with player(client) as p:
        p.ws.send_text("x" * (8 * 1024 + 1))
        with pytest.raises(WebSocketDisconnect) as exc:
            p.ws.receive_json()
    assert exc.value.code == 1009


# Room journeys


def test_create_join_leave_journey(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Sara") as sara:
        code = create_room(ali, 2)

        joined = sara.call("room.join", {"code": code.lower()})
        assert joined == {"command_id": joined["command_id"], "ok": True, "room_code": code, "revision": 2}
        seen_by_sara = sara.snapshot()
        seen_by_ali = ali.snapshot()
        assert seen_by_sara == seen_by_ali
        assert [m["nickname"] for m in seen_by_ali["members"]] == ["Ali", "Sara"]

        left = sara.call("room.leave", {})
        assert left["ok"] and left["room_code"] is None and left["revision"] is None
        after = ali.snapshot()
        assert after["revision"] == 3
        assert [m["nickname"] for m in after["members"]] == ["Ali"]


def test_full_room_over_websocket(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Sara") as sara, player(client, "Omar") as omar:
        code = create_room(ali, 2)
        assert sara.call("room.join", {"code": code})["ok"]
        result = omar.call("room.join", {"code": code})
        assert result["error"]["code"] == "ROOM_FULL"
        assert omar.call("room.sync", {})["error"]["code"] == "NOT_IN_ROOM"


def test_simultaneous_final_seat(client: TestClient) -> None:
    with (
        player(client, "Ali") as ali,
        player(client, "Sara") as sara,
        player(client, "Omar") as omar,
    ):
        code = create_room(ali, 2)
        # Send both joins before reading either result.
        sara_id = sara.send("room.join", {"code": code})
        omar_id = omar.send("room.join", {"code": code})
        results = [sara.result(sara_id), omar.result(omar_id)]

        assert sorted(r["ok"] for r in results) == [False, True]
        assert [r["error"]["code"] for r in results if not r["ok"]] == ["ROOM_FULL"]
        assert len(ali.snapshot()["members"]) == 2


def test_duplicate_command_returns_original_result(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Sara") as sara:
        code = create_room(ali, 4)
        command_id = sara.send("room.join", {"code": code})
        first = sara.result(command_id)
        sara.send("room.join", {"code": code}, command_id=command_id)
        assert sara.result(command_id) == first

        # Reusing the ID with different contents is rejected and changes nothing.
        sara.send("room.create", {"capacity": 2}, command_id=command_id)
        assert sara.result(command_id)["error"]["code"] == "COMMAND_ID_REUSED"
        assert sara.call("room.sync", {})["revision"] == 2


def test_leave_result_follows_old_room_snapshots(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Sara") as sara:
        code = create_room(ali, 2)
        sara.call("room.join", {"code": code})
        ali.snapshot()
        sara.snapshot()

        # Ali's chat is processed before Sara's leave, so its snapshot reaches Sara first.
        ali.send("chat.send", {"text": "bye?"})
        leave_id = sara.send("room.leave", {})
        assert sara.result(leave_id)["ok"]
        types = [m["type"] for m in sara.inbox]
        assert types == ["room.snapshot"]
        assert sara.inbox[0]["body"]["messages"][0]["text"] == "bye?"
        sara.inbox.clear()
        # Nothing from the old room arrives after the leave result.
        assert sara.drain() == []


# Chat


def test_chat_reaches_members_in_order(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Sara") as sara:
        code = create_room(ali, 2)
        sara.call("room.join", {"code": code})

        for i in range(20):
            sender = ali if i % 2 == 0 else sara
            result = sender.call("chat.send", {"text": f"message {i}"})
            assert result["ok"] and result["message_id"]
            if i % 5 == 4:
                # Stay within 5 chats per 10 seconds without waiting in the test.
                for p in (ali, sara):
                    client.app.state.sessions.get(p.session_id).chat_times.clear()

        expected = [f"message {i}" for i in range(20)]
        for p in (ali, sara):
            snapshots = [m["body"] for m in p.inbox if m["type"] == "room.snapshot"]
            revisions = [s["revision"] for s in snapshots]
            assert revisions == sorted(set(revisions))  # Increasing, never repeated.
            assert [m["text"] for m in p.sync()["messages"]] == expected


def test_concurrent_chat_order_is_shared(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Sara") as sara:
        code = create_room(ali, 2)
        sara.call("room.join", {"code": code})

        # Both players send without waiting for any result.
        ids = []
        for i in range(4):
            ids.append((ali, ali.send("chat.send", {"text": f"ali {i}"})))
            ids.append((sara, sara.send("chat.send", {"text": f"sara {i}"})))
        assert all(p.result(command_id)["ok"] for p, command_id in ids)

        ali_history = [m["text"] for m in ali.sync()["messages"]]
        sara_history = [m["text"] for m in sara.sync()["messages"]]
        assert ali_history == sara_history
        assert sorted(ali_history) == sorted(f"{n} {i}" for n in ("ali", "sara") for i in range(4))
        # Each sender's own messages keep the order they were sent in.
        assert [t for t in ali_history if t.startswith("ali")] == [f"ali {i}" for i in range(4)]


def test_chat_sender_comes_from_session(client: TestClient) -> None:
    with player(client, "Ali") as ali:
        create_room(ali)
        ali.call("chat.send", {"text": "  <img src=x onerror=alert(1)>  "})
        message = ali.snapshot()["messages"][0]
    assert message["sender_session_id"] == ali.session_id
    assert message["sender_nickname"] == "Ali"
    assert message["text"] == "<img src=x onerror=alert(1)>"
    assert message["sent_at"].endswith("Z")


def test_rooms_are_isolated(client: TestClient) -> None:
    with (
        player(client, "Ali") as ali,
        player(client, "Sara") as sara,
        player(client, "Omar") as omar,
    ):
        code = create_room(ali, 2)
        sara.call("room.join", {"code": code})
        create_room(omar, 2)
        omar.drain()

        ali.call("chat.send", {"text": "secret"})
        sara.call("chat.send", {"text": "reply"})
        assert omar.drain() == []


def test_outsider_cannot_chat(client: TestClient) -> None:
    with player(client, "Ali") as ali, player(client, "Eve") as eve:
        create_room(ali)
        assert eve.call("chat.send", {"text": "hello"})["error"]["code"] == "NOT_IN_ROOM"
        assert ali.drain() == []


def test_duplicate_chat_is_not_appended(client: TestClient) -> None:
    with player(client) as ali:
        create_room(ali)
        command_id = ali.send("chat.send", {"text": "once"})
        first = ali.result(command_id)
        ali.send("chat.send", {"text": "once"}, command_id=command_id)
        assert ali.result(command_id) == first
        assert len(ali.sync()["messages"]) == 1


@pytest.mark.parametrize("text", ["", "   ", "x" * 501])
def test_invalid_chat_text(client: TestClient, text: str) -> None:
    with player(client) as ali:
        create_room(ali)
        assert ali.call("chat.send", {"text": text})["error"]["code"] == "VALIDATION_ERROR"


def test_chat_rate_limit(client: TestClient) -> None:
    with player(client) as ali:
        create_room(ali)
        for i in range(5):
            assert ali.call("chat.send", {"text": f"m{i}"})["ok"]
        result = ali.call("chat.send", {"text": "too many"})
        assert result["error"]["code"] == "RATE_LIMITED"
        assert 0 < result["error"]["retry_after_ms"] <= 10_000


def test_general_command_rate_limit(client: TestClient) -> None:
    with player(client) as ali:
        results = [ali.call("room.leave", {}) for _ in range(31)]
    assert all(r["ok"] for r in results[:30])
    assert results[30]["error"]["code"] == "RATE_LIMITED"


# Outbound queue


class StalledSocket:
    def __init__(self) -> None:
        self.closed_with: int | None = None
        self.release = asyncio.Event()

    async def send_text(self, data: str) -> None:
        await self.release.wait()

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed_with = code


def test_full_outbound_queue_closes_slow_client() -> None:
    async def scenario() -> StalledSocket:
        ws = StalledSocket()
        conn = Connection(ws, "session", queue_size=3)
        conn.start()
        await asyncio.sleep(0)
        accepted = [conn.enqueue({"n": i}) for i in range(5)]
        await asyncio.sleep(0.01)
        # Three messages fill the queue before the writer runs; the next one overflows.
        assert accepted == [True, True, True, False, False]
        assert conn.enqueue({"n": "after"}) is False
        return ws

    ws = asyncio.run(scenario())
    assert ws.closed_with == 1013
