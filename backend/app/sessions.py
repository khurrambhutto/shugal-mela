"""Guest sessions identified by an opaque cookie credential.

Only a SHA-256 hash of each credential is kept. The public session_id is safe to show
other players and to log; the credential never leaves the cookie.
"""

import hashlib
import secrets
import time
import unicodedata
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import Limits

COOKIE_NAME = "shugal_session"
NICKNAME_MAX = 24


class SessionLimitError(Exception):
    pass


class CreationRateLimited(Exception):
    pass


@dataclass
class CompletedCommand:
    content: str
    result: dict[str, Any]
    completed_at: float


@dataclass(eq=False)
class Session:
    session_id: str
    credential_hash: str
    nickname: str
    last_active: float
    room_code: str | None = None
    connection_id: str | None = None
    completed: OrderedDict[str, CompletedCommand] = field(default_factory=OrderedDict)
    command_times: deque[float] = field(default_factory=deque)
    chat_times: deque[float] = field(default_factory=deque)


def normalize_nickname(raw: str) -> str:
    nickname = raw.strip()
    if not 1 <= len(nickname) <= NICKNAME_MAX:
        raise ValueError(f"nickname must be 1 to {NICKNAME_MAX} characters")
    if any(unicodedata.category(ch) == "Cc" for ch in nickname):
        raise ValueError("nickname must not contain control characters")
    return nickname


def hash_credential(credential: str) -> str:
    return hashlib.sha256(credential.encode()).hexdigest()


def check_rate(times: deque[float], limit: int, window_s: float, now: float) -> int | None:
    """Record an event in a rolling window. Return a retry delay in ms when over the limit."""
    while times and now - times[0] >= window_s:
        times.popleft()
    if len(times) >= limit:
        return max(1, int((window_s - (now - times[0])) * 1000))
    times.append(now)
    return None


class SessionStore:
    def __init__(self, limits: Limits, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits
        self.clock = clock
        self._by_hash: dict[str, Session] = {}
        self._by_id: dict[str, Session] = {}
        self._creation_times: deque[float] = deque()

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, session_id: str) -> Session | None:
        return self._by_id.get(session_id)

    def lookup(self, credential: str | None) -> Session | None:
        if not credential:
            return None
        session = self._by_hash.get(hash_credential(credential))
        if session is not None and self._is_expired(session):
            self._remove(session)
            return None
        return session

    def create(self, nickname: str) -> tuple[Session, str]:
        self.expire_idle()
        if len(self._by_id) >= self.limits.max_sessions:
            raise SessionLimitError
        if check_rate(self._creation_times, self.limits.session_creations_per_minute, 60, self.clock()):
            raise CreationRateLimited

        credential = secrets.token_urlsafe(32)
        session_id = secrets.token_urlsafe(12)
        while session_id in self._by_id:
            session_id = secrets.token_urlsafe(12)
        session = Session(
            session_id=session_id,
            credential_hash=hash_credential(credential),
            nickname=nickname,
            last_active=self.clock(),
        )
        self._by_hash[session.credential_hash] = session
        self._by_id[session_id] = session
        return session, credential

    def touch(self, session: Session) -> None:
        session.last_active = self.clock()

    def expire_idle(self) -> int:
        expired = [s for s in self._by_id.values() if self._is_expired(s)]
        for session in expired:
            self._remove(session)
        return len(expired)

    def _is_expired(self, session: Session) -> bool:
        # Connected sessions stay alive. Disconnected ones have already left their room.
        return (
            session.connection_id is None
            and self.clock() - session.last_active > self.limits.session_idle_expiry_s
        )

    def _remove(self, session: Session) -> None:
        self._by_hash.pop(session.credential_hash, None)
        self._by_id.pop(session.session_id, None)
