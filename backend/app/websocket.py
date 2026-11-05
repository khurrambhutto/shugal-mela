"""The /ws endpoint: authentication, command handling, and delivery."""

import json
import logging
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.config import Settings
from app.connections import Connection, ConnectionRegistry
from app.protocol import (
    PROTOCOL_VERSION,
    ChatSend,
    Command,
    RoomCreate,
    RoomJoin,
    RoomLeave,
    RoomSync,
    command_adapter,
    error_result,
    ok_result,
    session_ready,
)
from app.rooms import Outcome, RoomError, RoomRegistry
from app.sessions import COOKIE_NAME, CompletedCommand, Session, SessionStore, check_rate

logger = logging.getLogger("shugal")

CLOSE_MESSAGE_TOO_BIG = 1009
CLOSE_ALREADY_CONNECTED = 4409
RATE_WINDOW_S = 10


class CommandProcessor:
    """Applies one raw command for a session and queues every resulting message.

    Lookup, mutation, and result caching happen without awaiting, so they are
    serialized with every other command on the event loop.
    """

    def __init__(
        self, settings: Settings, sessions: SessionStore, rooms: RoomRegistry, conns: ConnectionRegistry
    ) -> None:
        self.limits = settings.limits
        self.sessions = sessions
        self.rooms = rooms
        self.conns = conns

    def handle(self, session: Session, raw: str) -> None:
        self.sessions.touch(session)
        result, deliveries = self._process(session, raw)
        self.conns.send(session.session_id, result)
        for session_id, message in deliveries:
            self.conns.send(session_id, message)

    def disconnect(self, session: Session) -> None:
        for session_id, message in self.rooms.disconnect(session):
            self.conns.send(session_id, message)

    def _process(self, session: Session, raw: str) -> tuple[dict[str, Any], list[Any]]:
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            return error_result(None, "VALIDATION_ERROR", "Commands must be JSON objects."), []

        command_id = _command_id(data.get("command_id"))
        content = json.dumps({k: v for k, v in data.items() if k != "command_id"}, sort_keys=True)

        if command_id is not None:
            self._prune_completed(session)
            previous = session.completed.get(command_id)
            if previous is not None:
                if previous.content == content:
                    return previous.result, []
                return error_result(
                    command_id, "COMMAND_ID_REUSED", "This command ID was used for a different command."
                ), []

        result, deliveries = self._execute(session, data, command_id)
        if command_id is not None:
            self._remember(session, command_id, content, result)
        return result, deliveries

    def _execute(
        self, session: Session, data: dict[str, Any], command_id: str | None
    ) -> tuple[dict[str, Any], list[Any]]:
        now = self.sessions.clock()
        retry = check_rate(session.command_times, self.limits.commands_per_10s, RATE_WINDOW_S, now)
        if retry is not None:
            return _rate_limited(command_id, retry), []

        version = data.get("version")
        if type(version) is int and version != PROTOCOL_VERSION:
            return error_result(command_id, "UNSUPPORTED_VERSION", "Protocol version 1 is required."), []
        try:
            command = command_adapter.validate_python(data)
        except ValidationError:
            return error_result(command_id, "VALIDATION_ERROR", "The command is invalid."), []
        assert command_id is not None  # A valid command always has a UUID.

        if isinstance(command, ChatSend):
            retry = check_rate(session.chat_times, self.limits.chat_per_10s, RATE_WINDOW_S, now)
            if retry is not None:
                return _rate_limited(command_id, retry), []

        try:
            outcome = self._dispatch(session, command)
        except RoomError as exc:
            return error_result(command_id, exc.code, exc.message), []
        return ok_result(command_id, **outcome.fields), outcome.deliveries

    def _dispatch(self, session: Session, command: Command) -> Outcome:
        match command:
            case RoomCreate(body=body):
                return self.rooms.create(session, body.capacity)
            case RoomJoin(body=body):
                return self.rooms.join(session, body.code)
            case RoomLeave():
                return self.rooms.leave(session)
            case RoomSync():
                return self.rooms.sync(session)
            case ChatSend(body=body):
                return self.rooms.send_chat(session, body.text)

    def _remember(self, session: Session, command_id: str, content: str, result: dict[str, Any]) -> None:
        session.completed[command_id] = CompletedCommand(content, result, self.sessions.clock())
        while len(session.completed) > self.limits.completed_commands_per_session:
            session.completed.popitem(last=False)

    def _prune_completed(self, session: Session) -> None:
        cutoff = self.sessions.clock() - self.limits.completed_command_ttl_s
        while session.completed:
            oldest = next(iter(session.completed.values()))
            if oldest.completed_at >= cutoff:
                break
            session.completed.popitem(last=False)


def _command_id(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        return str(UUID(raw))
    except ValueError:
        return None


def _rate_limited(command_id: str | None, retry_after_ms: int) -> dict[str, Any]:
    return error_result(
        command_id, "RATE_LIMITED", "Too many requests. Wait and try again.", retry_after_ms=retry_after_ms
    )


async def serve_socket(
    ws: WebSocket,
    settings: Settings,
    sessions: SessionStore,
    conns: ConnectionRegistry,
    processor: CommandProcessor,
) -> None:
    origin = ws.headers.get("origin", "").lower()
    if origin not in settings.allowed_origins:
        logger.warning("ws rejected reason=origin")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)  # Sent as HTTP 403 before accept.
        return
    session = sessions.lookup(ws.cookies.get(COOKIE_NAME))
    if session is None:
        logger.warning("ws rejected reason=session")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    conn = Connection(ws, session.session_id, settings.limits.outbound_queue_size)
    if not conns.register(conn):
        logger.info("ws rejected reason=already-connected session=%s", session.session_id)
        await ws.accept()
        await ws.close(code=CLOSE_ALREADY_CONNECTED)
        return

    session.connection_id = conn.id
    await ws.accept()
    conn.start()
    conn.enqueue(session_ready(session.session_id, session.nickname))
    logger.info("ws connected conn=%s session=%s", conn.id, session.session_id)
    close_code: int | None = None
    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                close_code = message.get("code")
                break
            text = message.get("text")
            if text is None:
                text = ""  # Binary frames are not part of the protocol.
            if len(text.encode()) > settings.limits.max_message_bytes:
                close_code = CLOSE_MESSAGE_TOO_BIG
                await conn.close(CLOSE_MESSAGE_TOO_BIG)
                break
            processor.handle(session, text)
    except (WebSocketDisconnect, RuntimeError):
        pass  # The socket closed underneath the reader; clean up below.
    finally:
        await conn.stop_writer()
        conns.unregister(conn)
        if session.connection_id == conn.id:
            session.connection_id = None
        processor.disconnect(session)
        sessions.touch(session)
        logger.info("ws disconnected conn=%s session=%s code=%s", conn.id, session.session_id, close_code)
