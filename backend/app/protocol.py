"""Protocol v1 message models. See specs/001-online-rooms-chat/contracts/protocol.md."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, TypeAdapter

PROTOCOL_VERSION = 1

ErrorCode = Literal[
    "VALIDATION_ERROR",
    "UNSUPPORTED_VERSION",
    "ROOM_NOT_FOUND",
    "ROOM_FULL",
    "ALREADY_IN_ROOM",
    "NOT_IN_ROOM",
    "RATE_LIMITED",
    "COMMAND_ID_REUSED",
    "SERVER_BUSY",
    "NOT_HOST",
    "NOT_READY",
    "WRONG_PLAYER_COUNT",
    "MATCH_IN_PROGRESS",
    "NO_MATCH",
    "STALE_STATE",
    "NOT_YOUR_TURN",
    "WRONG_PHASE",
    "ILLEGAL_MOVE",
    "MATCH_PAUSED",
    "PLAYER_AWAY",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# Incoming commands


class EmptyBody(StrictModel):
    pass


class CreateBody(StrictModel):
    capacity: Literal[2, 4]


class JoinBody(StrictModel):
    code: str = Field(max_length=32)


class ChatBody(StrictModel):
    # The 500 code point limit applies after trimming, so it is checked by the handler.
    text: str = Field(max_length=2000)


class ReadyBody(StrictModel):
    ready: StrictBool


class RollBody(StrictModel):
    match_id: str = Field(max_length=64)
    step: StrictInt = Field(ge=0)


class MoveBody(RollBody):
    token: StrictInt = Field(ge=0, le=3)


class _Command(StrictModel):
    version: Literal[1]
    command_id: UUID


class RoomCreate(_Command):
    type: Literal["room.create"]
    body: CreateBody


class RoomJoin(_Command):
    type: Literal["room.join"]
    body: JoinBody


class RoomLeave(_Command):
    type: Literal["room.leave"]
    body: EmptyBody


class RoomSync(_Command):
    type: Literal["room.sync"]
    body: EmptyBody


class ChatSend(_Command):
    type: Literal["chat.send"]
    body: ChatBody


class MatchReady(_Command):
    type: Literal["match.ready"]
    body: ReadyBody


class MatchStart(_Command):
    type: Literal["match.start"]
    body: EmptyBody


class MatchRoll(_Command):
    type: Literal["match.roll"]
    body: RollBody


class MatchMove(_Command):
    type: Literal["match.move"]
    body: MoveBody


Command = Annotated[
    RoomCreate | RoomJoin | RoomLeave | RoomSync | ChatSend | MatchReady | MatchStart | MatchRoll | MatchMove,
    Field(discriminator="type"),
]
command_adapter: TypeAdapter[Command] = TypeAdapter(Command)


# Outgoing messages


class Member(StrictModel):
    session_id: str
    nickname: str
    away_ms: int | None = None  # Time left to reconnect; None while connected.


class ChatMessage(StrictModel):
    message_id: str
    sender_session_id: str
    sender_nickname: str
    text: str
    sent_at: str


class RoomSnapshot(StrictModel):
    code: str
    capacity: int
    revision: int
    members: tuple[Member, ...]
    messages: tuple[ChatMessage, ...]
    host: str
    ready: tuple[str, ...]
    match: dict[str, Any] | None


def envelope(type_: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"version": PROTOCOL_VERSION, "type": type_, "body": body}


def session_ready(session_id: str, nickname: str, room_code: str | None) -> dict[str, Any]:
    return envelope("session.ready", {"session_id": session_id, "nickname": nickname, "room_code": room_code})


def snapshot_message(snapshot: RoomSnapshot) -> dict[str, Any]:
    return envelope("room.snapshot", snapshot.model_dump(mode="json"))


def ok_result(command_id: str, **fields: Any) -> dict[str, Any]:
    return envelope("command.result", {"command_id": command_id, "ok": True, **fields})


def error_result(
    command_id: str | None, code: ErrorCode, message: str, **extra: Any
) -> dict[str, Any]:
    error = {"code": code, "message": message, **extra}
    return envelope("command.result", {"command_id": command_id, "ok": False, "error": error})
