import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, Response, WebSocket, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, field_validator

from app.config import Settings, load_settings
from app.connections import ConnectionRegistry
from app.protocol import PROTOCOL_VERSION
from app.rooms import RoomRegistry
from app.sessions import (
    COOKIE_NAME,
    CreationRateLimited,
    SessionLimitError,
    SessionStore,
    normalize_nickname,
)
from app.websocket import CommandProcessor, serve_socket

logger = logging.getLogger("shugal")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

EXPIRY_SWEEP_INTERVAL_S = 60


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str

    @field_validator("nickname")
    @classmethod
    def _valid_nickname(cls, value: str) -> str:
        return normalize_nickname(value)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    sessions = SessionStore(settings.limits)
    rooms = RoomRegistry(sessions, settings.limits)
    conns = ConnectionRegistry()
    processor = CommandProcessor(settings, sessions, rooms, conns)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async def sweep() -> None:
            while True:
                await asyncio.sleep(EXPIRY_SWEEP_INTERVAL_S)
                if expired := sessions.expire_idle():
                    logger.info("expired idle sessions count=%d", expired)

        task = asyncio.create_task(sweep())
        yield
        task.cancel()

    app = FastAPI(
        title="Shugal Mela", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.rooms = rooms
    app.state.connections = conns

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/sessions")
    async def create_session(request: Request, body: SessionRequest, response: Response) -> object:
        if request.headers.get("origin", "").lower() not in settings.allowed_origins:
            return _error(status.HTTP_403_FORBIDDEN, "FORBIDDEN_ORIGIN", "Untrusted origin.")

        session = sessions.lookup(request.cookies.get(COOKIE_NAME))
        if session is not None:
            if body.nickname != session.nickname:
                if session.room_code is not None:
                    return _error(
                        status.HTTP_409_CONFLICT, "ALREADY_IN_ROOM", "Leave the room to change nickname."
                    )
                session.nickname = body.nickname
            sessions.touch(session)
            response.status_code = status.HTTP_200_OK
        else:
            try:
                session, credential = sessions.create(body.nickname)
            except SessionLimitError:
                return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVER_BUSY", "Too many players.")
            except CreationRateLimited:
                return _error(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "RATE_LIMITED", "Too many new sessions. Try again soon."
                )
            response.set_cookie(
                COOKIE_NAME,
                credential,
                httponly=True,
                samesite="lax",
                path="/",
                secure=settings.secure_cookies,
            )
            response.status_code = status.HTTP_201_CREATED
            logger.info("session created session=%s", session.session_id)

        return {
            "session_id": session.session_id,
            "nickname": session.nickname,
            "protocol_version": PROTOCOL_VERSION,
        }

    # Unknown API paths must stay JSON errors instead of falling through to the frontend.
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def api_not_found(path: str) -> JSONResponse:
        return JSONResponse({"detail": "Not Found"}, status_code=status.HTTP_404_NOT_FOUND)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await serve_socket(ws, settings, sessions, conns, processor)

    if settings.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    else:
        logger.warning("frontend build not found at %s; serving API only", settings.frontend_dist)

    return app


app = create_app()
