"""Live WebSocket connections and their outbound queues.

Each connection has one writer task, so sends never interleave. Messages are queued
without awaiting, which keeps network waits out of room state changes. A full queue
means the client is too slow; it is closed with 1013 instead of stalling other players.
"""

import asyncio
import json
import logging
import secrets
from typing import Any, Protocol

logger = logging.getLogger("shugal")

CLOSE_TRY_AGAIN_LATER = 1013


class Socket(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


class Connection:
    def __init__(self, ws: Socket, session_id: str, queue_size: int) -> None:
        self.id = secrets.token_hex(4)
        self.ws = ws
        self.session_id = session_id
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_size)
        self.closing = False
        self._writer: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._writer = asyncio.create_task(self._write_loop())

    def enqueue(self, message: dict[str, Any]) -> bool:
        if self.closing:
            return False
        try:
            self.queue.put_nowait(json.dumps(message, separators=(",", ":")))
        except asyncio.QueueFull:
            logger.warning("ws queue overflow conn=%s session=%s", self.id, self.session_id)
            asyncio.get_running_loop().create_task(self.close(CLOSE_TRY_AGAIN_LATER))
            return False
        return True

    async def close(self, code: int) -> None:
        if self.closing:
            return
        self.closing = True
        await self.stop_writer()
        try:
            await self.ws.close(code)
        except RuntimeError:
            pass  # Already closed by the peer.

    async def stop_writer(self) -> None:
        if self._writer is not None and self._writer is not asyncio.current_task():
            self._writer.cancel()
            try:
                await self._writer
            except asyncio.CancelledError:
                pass
            self._writer = None

    async def _write_loop(self) -> None:
        try:
            while True:
                await self.ws.send_text(await self.queue.get())
        except asyncio.CancelledError:
            raise
        except Exception:
            # The reader notices the broken socket and runs cleanup.
            logger.info("ws write failed conn=%s", self.id)


class ConnectionRegistry:
    def __init__(self) -> None:
        self._by_session: dict[str, Connection] = {}

    def __len__(self) -> int:
        return len(self._by_session)

    def register(self, conn: Connection) -> bool:
        if conn.session_id in self._by_session:
            return False
        self._by_session[conn.session_id] = conn
        return True

    def unregister(self, conn: Connection) -> None:
        # Only remove this exact connection, never a replacement for the same session.
        if self._by_session.get(conn.session_id) is conn:
            del self._by_session[conn.session_id]

    def send(self, session_id: str, message: dict[str, Any]) -> None:
        conn = self._by_session.get(session_id)
        if conn is not None:
            conn.enqueue(message)
