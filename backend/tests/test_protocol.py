import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.protocol import RoomSnapshot, command_adapter

from .conftest import player

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/protocol/v1.json").read_text()
)


@pytest.mark.parametrize("name", FIXTURES["commands"])
def test_valid_command_fixtures_parse(name: str) -> None:
    command_adapter.validate_python(FIXTURES["commands"][name])


@pytest.mark.parametrize("name", FIXTURES["invalid_commands"])
def test_invalid_command_fixtures_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        command_adapter.validate_python(FIXTURES["invalid_commands"][name]["message"])


@pytest.mark.parametrize("name", FIXTURES["invalid_commands"])
def test_invalid_command_fixtures_error_codes(client: TestClient, name: str) -> None:
    fixture = FIXTURES["invalid_commands"][name]
    with player(client) as p:
        p.ws.send_json(fixture["message"])
        result = p.ws.receive_json()
    assert result["body"]["ok"] is False
    assert result["body"]["error"]["code"] == fixture["error"]


def test_snapshot_fixture_matches_model() -> None:
    body = FIXTURES["server_messages"]["room.snapshot"]["body"]
    assert RoomSnapshot.model_validate(body).model_dump(mode="json") == body
