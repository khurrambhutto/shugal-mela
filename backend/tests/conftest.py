import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.config import load_settings
from app.main import create_app
from app.sessions import COOKIE_NAME

ORIGIN = "http://localhost:8000"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<!doctype html><title>Shugal Mela</title>")
    return tmp_path


@pytest.fixture
def app(dist: Path) -> FastAPI:
    return create_app(load_settings({"ALLOWED_ORIGINS": ORIGIN, "FRONTEND_DIST": str(dist)}))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def new_session(client: TestClient, nickname: str = "Ali") -> str:
    """Create a guest session and return its credential, leaving the cookie jar empty."""
    client.cookies.clear()
    response = client.post("/api/sessions", json={"nickname": nickname}, headers={"origin": ORIGIN})
    assert response.status_code == 201, response.text
    credential = response.cookies[COOKIE_NAME]
    client.cookies.clear()
    return credential


def ws_headers(credential: str, origin: str = ORIGIN) -> dict[str, str]:
    return {"origin": origin, "cookie": f"{COOKIE_NAME}={credential}"}


class Player:
    def __init__(self, ws: WebSocketTestSession, session_id: str, credential: str) -> None:
        self.ws = ws
        self.session_id = session_id
        self.credential = credential
        self.inbox: list[dict[str, Any]] = []

    def send(self, type_: str, body: dict[str, Any], command_id: str | None = None, **extra: Any) -> str:
        command_id = command_id or str(uuid.uuid4())
        self.ws.send_json({"version": 1, "command_id": command_id, "type": type_, "body": body, **extra})
        return command_id

    def result(self, command_id: str | None) -> dict[str, Any]:
        """Read until the result for command_id, keeping other messages in the inbox."""
        while True:
            message = self.ws.receive_json()
            if message["type"] == "command.result" and message["body"]["command_id"] == command_id:
                return message["body"]
            self.inbox.append(message)

    def call(self, type_: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.result(self.send(type_, body, **kwargs))

    def snapshot(self) -> dict[str, Any]:
        """Return the next room snapshot, from the inbox first."""
        while True:
            message = self.inbox.pop(0) if self.inbox else self.ws.receive_json()
            if message["type"] == "room.snapshot":
                return message["body"]

    def sync(self) -> dict[str, Any]:
        """Return the current room snapshot and discard anything older."""
        result = self.call("room.sync", {})
        assert result["ok"], result
        self.inbox = []
        return self.snapshot()

    def drain(self) -> list[dict[str, Any]]:
        """Return everything delivered before a fresh sync round trip."""
        result = self.call("room.sync", {})
        messages, self.inbox = self.inbox, []
        if result["ok"]:
            self.ws.receive_json()  # The snapshot answering this sync.
        return messages


@contextmanager
def player(client: TestClient, nickname: str = "Ali") -> Iterator[Player]:
    credential = new_session(client, nickname)
    with client.websocket_connect("/ws", headers=ws_headers(credential)) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "session.ready"
        yield Player(ws, ready["body"]["session_id"], credential)


def create_room(p: Player, capacity: int = 2) -> str:
    result = p.call("room.create", {"capacity": capacity})
    assert result["ok"], result
    p.snapshot()
    return result["room_code"]
