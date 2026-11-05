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
from app.ludo.rules import RuleError
from app.match import Dice, OnlineMatch, secure_die, start_match
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
    ready: set[str] = field(default_factory=set)
    match: OnlineMatch | None = None
    # Members whose connection dropped, with the clock time their seat is released.
    away: dict[str, float] = field(default_factory=dict)

    @property
    def host(self) -> str:
        return self.members[0]

    @property
    def playing(self) -> bool:
        return self.match is not None and self.match.status == "playing"


def normalize_code(raw: str) -> str:
    return raw.strip().upper()


class RoomRegistry:
    def __init__(self, sessions: SessionStore, limits: Limits, dice: Dice = secure_die) -> None:
        self.sessions = sessions
        self.limits = limits
        self.dice = dice
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
        if room.playing:
            raise RoomError("MATCH_IN_PROGRESS", "A match is being played in this room. Try again after it ends.")
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

    def set_ready(self, session: Session, ready: bool) -> Outcome:
        room = self._current_room(session)
        if room.playing:
            raise RoomError("MATCH_IN_PROGRESS", "The match has already started.")
        if (session.session_id in room.ready) != ready:
            if ready:
                room.ready.add(session.session_id)
            else:
                room.ready.discard(session.session_id)
            room.revision += 1
        return Outcome(self._result(room), self._broadcast(room))

    def start_match(self, session: Session) -> Outcome:
        room = self._current_room(session)
        if session.session_id != room.host:
            raise RoomError("NOT_HOST", "Only the host can start the match.")
        if room.playing:
            raise RoomError("MATCH_IN_PROGRESS", "The match has already started.")
        if len(room.members) not in (2, 4):
            raise RoomError("WRONG_PLAYER_COUNT", "Ludo needs two or four players.")
        if any(m not in room.ready for m in room.members if m != room.host):
            raise RoomError("NOT_READY", "Everyone else needs to be ready first.")
        if room.away:
            raise RoomError("PLAYER_AWAY", "Wait for everyone to reconnect.")

        room.match = start_match(list(room.members))
        room.ready.clear()
        room.revision += 1
        return Outcome(self._result(room), self._broadcast(room))

    def play(
        self, session: Session, match_id: str, step: int, action: str, token: int = -1
    ) -> Outcome:
        room = self._current_room(session)
        match = room.match
        if match is None or match.status != "playing":
            raise RoomError("NO_MATCH", "No match is being played.")
        if match.match_id != match_id or match.step != step:
            raise RoomError("STALE_STATE", "The board changed. Look again and retry.")
        if any(match.is_seated(m) for m in room.away):
            raise RoomError("MATCH_PAUSED", "The match is paused until everyone reconnects.")
        try:
            match.apply(session.session_id, "roll" if action == "roll" else "move", self.dice, token)
        except RuleError as exc:
            raise RoomError(exc.code, str(exc)) from exc
        room.revision += 1
        return Outcome(self._result(room), self._broadcast(room))

    def disconnect(self, session: Session) -> list[Delivery]:
        """Hold the member's seat until the reconnect deadline instead of releasing it."""
        room = self._rooms.get(session.room_code) if session.room_code else None
        if room is None:
            return []
        room.away[session.session_id] = self.sessions.clock() + self.limits.reconnect_grace_s
        room.revision += 1
        return self._broadcast(room)

    def reconnect(self, session: Session) -> list[Delivery]:
        """Return a reconnected member to their seat and send them the full room."""
        room = self._rooms.get(session.room_code) if session.room_code else None
        if room is None:
            session.room_code = None
            return []
        if room.away.pop(session.session_id, None) is None:
            return [(session.session_id, self._snapshot(room))]
        room.revision += 1
        return self._broadcast(room)

    def expire_away(self) -> list[Delivery]:
        """Release every seat whose reconnect deadline has passed."""
        now = self.sessions.clock()
        deliveries: list[Delivery] = []
        for room in list(self._rooms.values()):
            for session_id, deadline in list(room.away.items()):
                session = self.sessions.get(session_id)
                if deadline <= now and session is not None:
                    deliveries += self._remove_member(session, "did not come back")
        return deliveries

    def _remove_member(self, session: Session, why: str = "left") -> list[Delivery]:
        code = session.room_code
        session.room_code = None
        room = self._rooms.get(code) if code else None
        if room is None:
            return []
        room.members.remove(session.session_id)
        room.ready.discard(session.session_id)
        room.away.pop(session.session_id, None)
        if room.playing and room.match is not None and room.match.is_seated(session.session_id):
            room.match.end(f"{session.nickname} {why}, so the match ended.")
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
        now = self.sessions.clock()
        members = []
        for session_id in room.members:
            member = self.sessions.get(session_id)
            nickname = member.nickname if member else "?"
            deadline = room.away.get(session_id)
            away_ms = None if deadline is None else max(0, int((deadline - now) * 1000))
            members.append(Member(session_id=session_id, nickname=nickname, away_ms=away_ms))
        snapshot = RoomSnapshot(
            code=room.code,
            capacity=room.capacity,
            revision=room.revision,
            members=tuple(members),
            messages=tuple(room.messages),
            host=room.host,
            ready=tuple(m for m in room.members if m in room.ready),
            match=room.match.public() if room.match else None,
        )
        return snapshot_message(snapshot)

    def _broadcast(self, room: Room) -> list[Delivery]:
        message = self._snapshot(room)
        return [(session_id, message) for session_id in room.members if session_id not in room.away]

    @staticmethod
    def _result(room: Room) -> dict[str, Any]:
        return {"room_code": room.code, "revision": room.revision}
