# -*- coding: utf-8 -*-
"""
Delivers sign-in codes: email through Resend, SMS through Twilio (plain HTTPS, no extra packages).
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import config

logger = logging.getLogger(__name__)
_UA = "LuxeHome/2.0 (+auth)"  # some providers' CDNs reject Python's default user agent


def is_configured(channel: str) -> bool:
    if channel == "email":
        return bool(config.RESEND_API_KEY and config.MAIL_FROM)
    return bool(
        config.TWILIO_ACCOUNT_SID
        and config.TWILIO_AUTH_TOKEN
        and (config.TWILIO_FROM or config.TWILIO_MESSAGING_SERVICE_SID)
    )


def _post(url: str, data: bytes, headers: dict) -> None:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": _UA, **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"provider returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"provider unreachable: {exc.reason}") from exc


def send_code(channel: str, contact: str, code: str) -> None:
    """Raises RuntimeError if the provider rejects or can't be reached."""
    text = f"Your LuxeHome verification code is {code}. It expires in 10 minutes. If you didn't ask for it, ignore this message."
    if channel == "email":
        body = json.dumps({"from": config.MAIL_FROM, "to": [contact], "subject": f"{code} is your LuxeHome code", "text": text})
        _post(
            "https://api.resend.com/emails",
            body.encode("utf-8"),
            {"Authorization": f"Bearer {config.RESEND_API_KEY}", "Content-Type": "application/json"},
        )
        return
    form = {"To": contact, "Body": text}
    if config.TWILIO_MESSAGING_SERVICE_SID:
        form["MessagingServiceSid"] = config.TWILIO_MESSAGING_SERVICE_SID
    else:
        form["From"] = config.TWILIO_FROM
    token = base64.b64encode(f"{config.TWILIO_ACCOUNT_SID}:{config.TWILIO_AUTH_TOKEN}".encode()).decode()
    _post(
        f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json",
        urllib.parse.urlencode(form).encode("utf-8"),
        {"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"},
    )
