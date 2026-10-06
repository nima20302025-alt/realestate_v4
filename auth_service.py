# -*- coding: utf-8 -*-
"""
Sign-in with a one-time code. The repository and the sender are passed in, so the
whole flow can be unit-tested without a database or a network.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Optional

import security

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 60


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def start_login(
    repo: Any,
    contact_raw: str,
    secret: str,
    *,
    is_configured: Callable[[str], bool],
    send: Callable[[str, str, str], None],
    dev_mode: bool = False,
    daily_cap: int = 6,
) -> Dict[str, Any]:
    try:
        channel, value = security.normalize_contact(contact_raw)
    except ValueError as exc:
        raise AuthError(400, str(exc))

    configured = is_configured(channel)
    if not configured and not dev_mode:
        label = "Email" if channel == "email" else "SMS"
        raise AuthError(503, f"{label} sign-in isn't set up on this server yet.")

    stats = repo.auth_code_stats(value)
    since: Optional[float] = stats.get("seconds_since_last")
    if since is not None and since < COOLDOWN_SECONDS:
        raise AuthError(429, f"Please wait {int(COOLDOWN_SECONDS - since) + 1}s before asking for another code.")
    if stats.get("sent_24h", 0) >= daily_cap:
        raise AuthError(429, "Too many codes requested today. Try again tomorrow.")

    code = security.new_code()
    repo.store_auth_code(value, channel, security.hash_code(value, code, secret), 10)

    out: Dict[str, Any] = {"ok": True, "channel": channel, "sent_to": security.mask_contact(channel, value)}
    if configured:
        try:
            send(channel, value, code)
        except Exception:
            logger.exception("Could not deliver sign-in code via %s", channel)
            raise AuthError(502, "We couldn't send the code. Please try again in a moment.")
    else:  # development only
        logger.warning("AUTH_DEV_MODE: code for %s is %s", security.mask_contact(channel, value), code)
        out["dev_code"] = code
    return out


def verify_login(
    repo: Any, contact_raw: str, code_raw: str, current_customer_id: Optional[int], secret: str
) -> Dict[str, Any]:
    try:
        channel, value = security.normalize_contact(contact_raw)
    except ValueError as exc:
        raise AuthError(400, str(exc))
    code = re.sub(r"\D", "", code_raw or "")
    if len(code) != 6:
        raise AuthError(400, "Enter the 6-digit code.")

    result = repo.check_auth_code(value, security.hash_code(value, code, secret))
    if result == "bad":
        raise AuthError(400, "That code isn't right.")
    if result == "expired":
        raise AuthError(400, "That code has expired. Ask for a new one.")
    if result == "locked":
        raise AuthError(429, "Too many wrong attempts. Ask for a new code.")

    existing = repo.find_customer_by_contact(channel, value)
    current = repo.get_customer(current_customer_id) if current_customer_id else None
    switched = merged = False

    if existing:
        target = existing["customer_id"]
        if current and current["customer_id"] != target:
            switched = True
            if not (current.get("phone_verified") or current.get("email_verified")):
                repo.merge_customers(current["customer_id"], target)  # keep what the guest collected
                merged = True
        repo.set_customer_contact(target, channel, value)  # also normalises legacy values
    elif current:
        target = current["customer_id"]
        repo.set_customer_contact(target, channel, value)
    else:
        target = repo.create_verified_customer("Guest", channel, value)
    return {"customer_id": target, "switched": switched, "merged": merged}
