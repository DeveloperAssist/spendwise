"""Passwords and login tokens.

Passwords: hashed with Argon2 (the current best-practice algorithm). We never store or log them.
Tokens: a signed JWT that says "this is user 7, valid until X". The server checks the signature,
so a token can't be forged or edited without the secret.
"""

import datetime as dt
import threading
import time
from collections import defaultdict, deque

import jwt
from pwdlib import PasswordHash

from .config import get_settings

_hasher = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception:  # a malformed hash is just a failed login
        return False


def create_token(user_id: int, token_salt: str) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "ts": token_salt,  # must match the account's salt (see deps.get_current_user)
        "iat": now,
        "exp": now + dt.timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def read_token(token: str) -> tuple[int, str] | None:
    """(user id, token salt) from a valid token, or None (bad signature, expired, malformed)."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        return int(payload["sub"]), str(payload["ts"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


class RateLimiter:
    """At most `limit` events per `window` seconds per key (a user id, an email...).

    In memory, per process: fine for one server. Behind several servers you'd keep this in Redis.
    """

    MAX_KEYS = 50_000

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._events: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _sweep(self, now: float) -> None:
        """Forget keys with no recent events, so random keys can't grow memory forever."""
        for k in [k for k, q in self._events.items() if not q or now - q[-1] > self.window]:
            del self._events[k]

    def hit(self, key: str) -> bool:
        """Record one event. False when the key is over its limit (the event is not counted)."""
        now = time.monotonic()
        key = key[:300]
        with self._lock:
            if len(self._events) >= self.MAX_KEYS:
                self._sweep(now)
            q = self._events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
