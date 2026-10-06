# -*- coding: utf-8 -*-
"""
Security helpers with no web/DB dependencies (easy to unit-test):
signed session tokens, login-code hashing, contact normalisation, rate limiting.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

# ── signed session cookie ────────────────────────────────────────────────────


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())


def make_session_token(customer_id: int, secret: str, days: int = 90, now: Optional[float] = None) -> str:
    issued = int(now if now is not None else time.time())
    body = {"c": int(customer_id), "iat": issued, "exp": issued + days * 86400, "v": 1}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    return f"{payload}.{_sign(payload, secret)}"


def read_session_token(token: Optional[str], secret: str, now: Optional[float] = None) -> Optional[int]:
    """Customer id if the token is authentic and unexpired, else None."""
    if not token or len(token) > 512 or token.count(".") != 1:
        return None
    payload, _, signature = token.partition(".")
    try:
        if not hmac.compare_digest(signature, _sign(payload, secret)):
            return None
        data = json.loads(_unb64(payload))
    except (ValueError, TypeError, UnicodeError):
        return None
    if not isinstance(data, dict) or data.get("v") != 1:
        return None
    current = now if now is not None else time.time()
    if not isinstance(data.get("exp"), (int, float)) or data["exp"] < current:
        return None
    cid = data.get("c")
    return cid if isinstance(cid, int) and not isinstance(cid, bool) and cid > 0 else None


# ── login codes ──────────────────────────────────────────────────────────────


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_code(contact: str, code: str, secret: str) -> str:
    """Codes are stored hashed and bound to the contact they were sent to."""
    return hmac.new(secret.encode("utf-8"), f"{contact}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s.]{2,}$")


def normalize_contact(raw: Optional[str]) -> Tuple[str, str]:
    """('email', 'a@b.com') or ('phone', '+12065550123'). Raises ValueError with a user-facing message."""
    text = (raw or "").strip()
    if "@" in text:
        text = text.lower()
        if len(text) > 254 or not _EMAIL_RE.match(text):
            raise ValueError("Enter a valid email address.")
        return "email", text
    digits = re.sub(r"\D", "", text)
    if text.startswith("+"):
        if 8 <= len(digits) <= 15:
            return "phone", "+" + digits
    elif len(digits) == 10:
        return "phone", "+1" + digits
    elif len(digits) == 11 and digits.startswith("1"):
        return "phone", "+" + digits
    raise ValueError("Enter a phone number with country code (like +1 206 555 0123) or an email address.")


def mask_contact(channel: str, value: str) -> str:
    if channel == "email":
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}"
    return value[:2] + "*" * max(len(value) - 4, 1) + value[-2:]


# ── rate limiting ────────────────────────────────────────────────────────────


class RateLimiter:
    """Sliding-window limiter, thread-safe, in memory (one server process)."""

    def __init__(self, gc_every: float = 300.0) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._windows: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._gc_every = gc_every
        self._last_gc = time.monotonic()

    def check(self, key: str, limit: int, window: float, now: Optional[float] = None) -> Tuple[bool, int]:
        """(allowed, retry_after_seconds). A rejected call is not counted."""
        t = now if now is not None else time.monotonic()
        with self._lock:
            hits = self._hits[key]
            self._windows[key] = window
            cutoff = t - window
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, int(hits[0] + window - t) + 1)
            hits.append(t)
            if t - self._last_gc > self._gc_every:
                self._gc(t)
            return True, 0

    def _gc(self, t: float) -> None:
        self._last_gc = t
        for key in [k for k, q in self._hits.items() if not q or q[-1] <= t - self._windows.get(k, 0)]:
            self._hits.pop(key, None)
            self._windows.pop(key, None)
