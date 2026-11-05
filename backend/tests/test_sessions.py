from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Limits, load_settings
from app.main import create_app
from app.sessions import COOKIE_NAME, SessionStore

from .conftest import ORIGIN, create_room, new_session, player


def post(client: TestClient, nickname: object, origin: str | None = ORIGIN, credential: str | None = None):
    headers = {"origin": origin} if origin else {}
    if credential:
        headers["cookie"] = f"{COOKIE_NAME}={credential}"
    return client.post("/api/sessions", json={"nickname": nickname}, headers=headers)


def test_creates_session_with_private_cookie(client: TestClient) -> None:
    response = post(client, "  Ali  ")
    assert response.status_code == 201
    body = response.json()
    assert body["nickname"] == "Ali"
    assert body["protocol_version"] == 1

    cookie = response.headers["set-cookie"]
    credential = response.cookies[COOKIE_NAME]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie or "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie  # Development mode over local HTTP.
    assert credential != body["session_id"]
    assert credential not in response.text


def test_public_mode_sets_secure_cookie(dist: Path) -> None:
    origin = "https://example.trycloudflare.com"
    app = create_app(load_settings({"APP_MODE": "public", "ALLOWED_ORIGINS": origin, "FRONTEND_DIST": str(dist)}))
    with TestClient(app, base_url=origin) as client:
        response = post(client, "Ali", origin=origin)
    assert response.status_code == 201
    assert "Secure" in response.headers["set-cookie"]


def test_cookie_restores_same_session(client: TestClient) -> None:
    credential = new_session(client, "Ali")
    first = post(client, "Ali", credential=credential)
    second = post(client, "Ali B", credential=credential)
    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"]
    assert second.json()["nickname"] == "Ali B"
    assert "set-cookie" not in second.headers


def test_unknown_cookie_creates_new_session(client: TestClient) -> None:
    response = post(client, "Ali", credential="not-a-real-credential")
    assert response.status_code == 201
    assert response.cookies[COOKIE_NAME] != "not-a-real-credential"


@pytest.mark.parametrize("origin", [None, "http://evil.example", "http://127.0.0.1:8000"])
def test_rejects_untrusted_origin(client: TestClient, origin: str | None) -> None:
    response = post(client, "Ali", origin=origin)
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("nickname", ["", "   ", "x" * 25, "a\nb", 42, None])
def test_rejects_invalid_nickname(client: TestClient, nickname: object) -> None:
    assert post(client, nickname).status_code == 422


def test_nickname_counts_code_points(client: TestClient) -> None:
    assert post(client, "😀" * 24).status_code == 201


def test_rejects_extra_fields(client: TestClient) -> None:
    response = client.post(
        "/api/sessions", json={"nickname": "Ali", "session_id": "x"}, headers={"origin": ORIGIN}
    )
    assert response.status_code == 422


def test_session_limit(dist: Path) -> None:
    settings = replace(
        load_settings({"ALLOWED_ORIGINS": ORIGIN, "FRONTEND_DIST": str(dist)}),
        limits=Limits(max_sessions=2),
    )
    with TestClient(create_app(settings)) as client:
        new_session(client)
        new_session(client)
        response = post(client, "Third")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVER_BUSY"


def test_session_creation_rate_limit(dist: Path) -> None:
    settings = replace(
        load_settings({"ALLOWED_ORIGINS": ORIGIN, "FRONTEND_DIST": str(dist)}),
        limits=Limits(session_creations_per_minute=3),
    )
    with TestClient(create_app(settings)) as client:
        for _ in range(3):
            new_session(client)
        client.cookies.clear()
        assert post(client, "Four").status_code == 503


def test_expired_session_is_not_restored() -> None:
    now = [0.0]
    store = SessionStore(Limits(session_idle_expiry_s=60), clock=lambda: now[0])
    session, credential = store.create("Ali")
    assert store.lookup(credential) is session

    now[0] = 61
    assert store.lookup(credential) is None
    assert len(store) == 0


def test_connected_session_does_not_expire() -> None:
    now = [0.0]
    store = SessionStore(Limits(session_idle_expiry_s=60), clock=lambda: now[0])
    session, credential = store.create("Ali")
    session.connection_id = "conn"
    now[0] = 1000
    assert store.expire_idle() == 0
    assert store.lookup(credential) is session


def test_nickname_change_rejected_while_in_room(client: TestClient) -> None:
    with player(client, "Ali") as p:
        create_room(p)
        assert post(client, "Other", credential=p.credential).status_code == 409
        assert post(client, "Ali", credential=p.credential).status_code == 200
        p.call("room.leave", {})
        assert post(client, "Other", credential=p.credential).status_code == 200
