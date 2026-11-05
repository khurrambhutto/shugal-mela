import pytest
from fastapi.testclient import TestClient

from app.config import load_settings


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_serves_frontend(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Shugal Mela" in response.text


@pytest.mark.parametrize("method", ["get", "post"])
def test_unknown_api_path_is_json_404(client: TestClient, method: str) -> None:
    response = getattr(client, method)("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_public_mode_requires_https_origins() -> None:
    with pytest.raises(ValueError):
        load_settings({"APP_MODE": "public", "ALLOWED_ORIGINS": "http://example.com"})


def test_origins_are_normalized() -> None:
    settings = load_settings({"ALLOWED_ORIGINS": " HTTP://LocalHost:8000/ , https://a.trycloudflare.com"})
    assert settings.allowed_origins == {"http://localhost:8000", "https://a.trycloudflare.com"}
