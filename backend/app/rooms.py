"""Room membership and chat rules, independent of HTTP and WebSockets.

Every method runs to completion without awaiting, so on the single event loop each
command is applied atomically: no other command can observe a half-applied change.
Methods return the result for the caller and the snapshot deliveries for room members.
"""

import secrets
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.config import Limits
from app.protocol import ChatMessage, ErrorCode, Member, RoomSnapshot, snapshot_message
from app.sessions import Session, SessionStore

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
CHAT_MAX = 500

Delivery = tuple[str, dict[str, Any]]


class RoomError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Outcome:
    fields: dict[str, Any]
    deliveries: list[Delivery] = field(default_factory=list)


@dataclass(eq=False)
class Room:
    code: str
    capacity: int
    members: list[str]
    revision: int = 1
    messages: deque[ChatMessage] = field(default_factory=deque)


def normalize_code(raw: str) -> str:
    return raw.strip().upper()


class RoomRegistry:
    def __init__(self, sessions: SessionStore, limits: Limits) -> None:
        self.sessions = sessions
        self.limits = limits
        self._rooms: dict[str, Room] = {}

    def __len__(self) -> int:
        return len(self._rooms)

    def get(self, code: str) -> Room | None:
        return self._rooms.get(code)

    def create(self, session: Session, capacity: int) -> Outcome:
        if session.room_code is not None:
            raise RoomError("ALREADY_IN_ROOM", "Leave your current room first.")
        if len(self._rooms) >= self.limits.max_rooms:
            raise RoomError("SERVER_BUSY", "The server has reached its room limit.")

        room = Room(code=self._new_code(), capacity=capacity, members=[session.session_id])
        self._rooms[room.code] = room
        session.room_code = room.code
        return Outcome(self._result(room), self._broadcast(room))

    def join(self, session: Session, raw_code: str) -> Outcome:
        code = normalize_code(raw_code)
        if session.room_code == code:
            room = self._rooms[code]
            return Outcome(self._result(room), [(session.session_id, self._snapshot(room))])
        if session.room_code is not None:
            raise RoomError("ALREADY_IN_ROOM", "Leave your current room first.")
        room = self._rooms.get(code)
        if room is None:
            raise RoomError("ROOM_NOT_FOUND", "No active room has that code.")
        if len(room.members) >= room.capacity:
            raise RoomError("ROOM_FULL", "This room has no available seats.")

        room.members.append(session.session_id)
        room.revision += 1
        session.room_code = code
        return Outcome(self._result(room), self._broadcast(room))

    def leave(self, session: Session) -> Outcome:
        deliveries = self._remove_member(session)
        return Outcome({"room_code": None, "revision": None}, deliveries)

    def sync(self, session: Session) -> Outcome:
        room = self._current_room(session)
        return Outcome(self._result(room), [(session.session_id, self._snapshot(room))])

    def send_chat(self, session: Session, raw_text: str) -> Outcome:
        room = self._current_room(session)
        text = raw_text.strip()
        if not 1 <= len(text) <= CHAT_MAX:
            raise RoomError("VALIDATION_ERROR", f"Messages must be 1 to {CHAT_MAX} characters.")

        message = ChatMessage(
            message_id=secrets.token_hex(8),
            sender_session_id=session.session_id,
            sender_nickname=session.nickname,
            text=text,
            sent_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        )
        room.messages.append(message)
        while len(room.messages) > self.limits.chat_history:
            room.messages.popleft()
        room.revision += 1
        return Outcome(
            {**self._result(room), "message_id": message.message_id}, self._broadcast(room)
        )

    def disconnect(self, session: Session) -> list[Delivery]:
        return self._remove_member(session)

    def _remove_member(self, session: Session) -> list[Delivery]:
        code = session.room_code
        session.room_code = None
        room = self._rooms.get(code) if code else None
        if room is None:
            return []
        room.members.remove(session.session_id)
        if not room.members:
            del self._rooms[room.code]
            return []
        room.revision += 1
        return self._broadcast(room)

    def _current_room(self, session: Session) -> Room:
        room = self._rooms.get(session.room_code) if session.room_code else None
        if room is None:
            raise RoomError("NOT_IN_ROOM", "Join a room first.")
        return room

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self._rooms:
                return code

    def _snapshot(self, room: Room) -> dict[str, Any]:
        members = []
        for session_id in room.members:
            member = self.sessions.get(session_id)
            nickname = member.nickname if member else "?"
            members.append(Member(session_id=session_id, nickname=nickname))
        snapshot = RoomSnapshot(
            code=room.code,
            capacity=room.capacity,
            revision=room.revision,
            members=tuple(members),
            messages=tuple(room.messages),
        )
        return snapshot_message(snapshot)

    def _broadcast(self, room: Room) -> list[Delivery]:
        message = self._snapshot(room)
        return [(session_id, message) for session_id in room.members]

    @staticmethod
    def _result(room: Room) -> dict[str, Any]:
        return {"room_code": room.code, "revision": room.revision}
