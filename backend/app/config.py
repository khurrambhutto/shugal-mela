"""Application settings read from environment variables.

APP_MODE is either "development" (local HTTP, non-Secure cookies allowed) or
"public" (HTTPS tunnel origin, Secure cookies required). ALLOWED_ORIGINS is a
comma-separated list of exact origins, such as "http://localhost:8000".
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

AppMode = Literal["development", "public"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Limits:
    max_rooms: int = 20
    max_sessions: int = 100
    commands_per_10s: int = 30
    chat_per_10s: int = 5
    session_creations_per_minute: int = 20
    max_message_bytes: int = 8 * 1024
    outbound_queue_size: int = 32
    completed_commands_per_session: int = 100
    completed_command_ttl_s: int = 600
    chat_history: int = 50
    session_idle_expiry_s: int = 30 * 60


@dataclass(frozen=True)
class Settings:
    mode: AppMode
    allowed_origins: frozenset[str]
    frontend_dist: Path
    limits: Limits = field(default_factory=Limits)

    @property
    def secure_cookies(self) -> bool:
        return self.mode == "public"


def _normalize_origin(raw: str) -> str:
    parts = urlsplit(raw.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"invalid origin: {raw!r}")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError(f"origin must not contain a path or query: {raw!r}")
    return f"{parts.scheme}://{parts.netloc}".lower()


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ) if env is None else env

    mode = env.get("APP_MODE", "development")
    if mode not in ("development", "public"):
        raise ValueError(f"APP_MODE must be 'development' or 'public', got {mode!r}")

    raw_origins = env.get("ALLOWED_ORIGINS", "http://localhost:8000")
    origins = frozenset(_normalize_origin(o) for o in raw_origins.split(",") if o.strip())
    if not origins:
        raise ValueError("ALLOWED_ORIGINS must list at least one origin")
    if mode == "public" and any(not o.startswith("https://") for o in origins):
        raise ValueError("public mode requires https:// origins")

    dist = Path(env.get("FRONTEND_DIST", PROJECT_ROOT / "frontend" / "dist"))
    return Settings(mode=mode, allowed_origins=origins, frontend_dist=dist)
