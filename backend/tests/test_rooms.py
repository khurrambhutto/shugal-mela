"""Room rules tested directly, without a network connection."""

import pytest

from app.config import Limits
from app.rooms import CODE_ALPHABET, RoomError, RoomRegistry
from app.sessions import Session, SessionStore


@pytest.fixture
def store() -> SessionStore:
    return SessionStore(Limits())


@pytest.fixture
def rooms(store: SessionStore) -> RoomRegistry:
    return RoomRegistry(store, Limits(max_rooms=3))


def make(store: SessionStore, nickname: str = "Ali") -> Session:
    return store.create(nickname)[0]


def error_code(fn, *args) -> str:
    with pytest.raises(RoomError) as exc:
        fn(*args)
    return exc.value.code


def test_create_assigns_code_and_first_seat(store: SessionStore, rooms: RoomRegistry) -> None:
    ali = make(store)
    outcome = rooms.create(ali, 2)
    code = outcome.fields["room_code"]

    assert len(code) == 6 and set(code) <= set(CODE_ALPHABET)
    assert outcome.fields["revision"] == 1
    assert ali.room_code == code
    [(recipient, snapshot)] = outcome.deliveries
    assert recipient == ali.session_id
    assert snapshot["body"]["members"] == [{"session_id": ali.session_id, "nickname": "Ali"}]


def test_join_accepts_lowercase_code(store: SessionStore, rooms: RoomRegistry) -> None:
    ali, sara = make(store), make(store, "Sara")
    code = rooms.create(ali, 2).fields["room_code"]
    outcome = rooms.join(sara, f"  {code.lower()} ")

    assert outcome.fields == {"room_code": code, "revision": 2}
    assert {r for r, _ in outcome.deliveries} == {ali.session_id, sara.session_id}


def test_full_room_rejects_without_change(store: SessionStore, rooms: RoomRegistry) -> None:
    ali, sara, omar = make(store), make(store, "Sara"), make(store, "Omar")
    code = rooms.create(ali, 2).fields["room_code"]
    rooms.join(sara, code)

    assert error_code(rooms.join, omar, code) == "ROOM_FULL"
    room = rooms.get(code)
    assert room is not None and room.members == [ali.session_id, sara.session_id]
    assert room.revision == 2
    assert omar.room_code is None


def test_unknown_code(store: SessionStore, rooms: RoomRegistry) -> None:
    assert error_code(rooms.join, make(store), "ZZZZZZ") == "ROOM_NOT_FOUND"


def test_repeated_join_is_unchanged(store: SessionStore, rooms: RoomRegistry) -> None:
    ali, sara = make(store), make(store, "Sara")
    code = rooms.create(ali, 4).fields["room_code"]
    rooms.join(sara, code)
    again = rooms.join(sara, code)

    assert again.fields["revision"] == 2
    assert [r for r, _ in again.deliveries] == [sara.session_id]
    room = rooms.get(code)
    assert room is not None and room.members.count(sara.session_id) == 1


def test_cannot_be_in_two_rooms(store: SessionStore, rooms: RoomRegistry) -> None:
    ali, sara = make(store), make(store, "Sara")
    first = rooms.create(ali, 2).fields["room_code"]
    rooms.create(sara, 2)

    assert error_code(rooms.create, ali, 2) == "ALREADY_IN_ROOM"
    assert error_code(rooms.join, sara, first) == "ALREADY_IN_ROOM"


def test_room_limit(store: SessionStore, rooms: RoomRegistry) -> None:
    for i in range(3):
        rooms.create(make(store, f"p{i}"), 2)
    assert error_code(rooms.create, make(store), 2) == "SERVER_BUSY"


def test_disconnect_removes_member_and_notifies_others(store: SessionStore, rooms: RoomRegistry) -> None:
    ali, sara = make(store), make(store, "Sara")
    code = rooms.create(ali, 2).fields["room_code"]
    rooms.join(sara, code)

    deliveries = rooms.disconnect(sara)
    assert sara.room_code is None
    [(recipient, snapshot)] = deliveries
    assert recipient == ali.session_id
    assert snapshot["body"]["revision"] == 3
    assert [m["session_id"] for m in snapshot["body"]["members"]] == [ali.session_id]


def test_empty_room_is_deleted(store: SessionStore, rooms: RoomRegistry) -> None:
    ali, sara = make(store), make(store, "Sara")
    code = rooms.create(ali, 2).fields["room_code"]
    assert rooms.leave(ali).deliveries == []

    assert rooms.get(code) is None
    assert error_code(rooms.join, sara, code) == "ROOM_NOT_FOUND"


def test_leave_outside_room_succeeds(store: SessionStore, rooms: RoomRegistry) -> None:
    outcome = rooms.leave(make(store))
    assert outcome.fields == {"room_code": None, "revision": None}


def test_chat_requires_membership(store: SessionStore, rooms: RoomRegistry) -> None:
    assert error_code(rooms.send_chat, make(store), "hi") == "NOT_IN_ROOM"


def test_chat_history_is_bounded(store: SessionStore, rooms: RoomRegistry) -> None:
    ali = make(store)
    code = rooms.create(ali, 2).fields["room_code"]
    for i in range(55):
        rooms.send_chat(ali, f"m{i}")
    room = rooms.get(code)
    assert room is not None
    assert [m.text for m in room.messages] == [f"m{i}" for i in range(5, 55)]
    assert room.revision == 56


@pytest.mark.parametrize("text", ["", "   ", "x" * 501])
def test_chat_text_limits(store: SessionStore, rooms: RoomRegistry, text: str) -> None:
    ali = make(store)
    code = rooms.create(ali, 2).fields["room_code"]
    assert error_code(rooms.send_chat, ali, text) == "VALIDATION_ERROR"
    room = rooms.get(code)
    assert room is not None and room.revision == 1
