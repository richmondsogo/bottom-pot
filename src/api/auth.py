"""
Authentication utilities and session token management for Bottom Pot admin.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import Request
from loguru import logger
from pydantic import BaseModel

from src.config import settings

_ephemeral_secret: Optional[str] = None


def get_session_secret() -> str:
    """
    Returns the active session secret for signing tokens.
    If ADMIN_SESSION_SECRET is unset, an ephemeral 32-byte secret is generated at startup.
    """
    global _ephemeral_secret
    if settings.admin_session_secret:
        return settings.admin_session_secret
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(32)
        logger.warning(
            "ADMIN_SESSION_SECRET is unset. Generated ephemeral secret; admin sessions will reset on server restart."
        )
    return _ephemeral_secret


def create_session_token(max_age_seconds: Optional[int] = None) -> str:
    """
    Creates an HMAC-SHA256 signed session token for an authenticated administrator.
    Token structure: {base64_payload}.{base64_hmac_signature}
    """
    ttl = (
        max_age_seconds
        if max_age_seconds is not None
        else settings.admin_cookie_max_age_seconds
    )
    now = int(time.time())
    exp = now + ttl
    payload = {"admin": True, "iat": now, "exp": exp}
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = (
        base64.urlsafe_b64encode(payload_json.encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )

    secret = get_session_secret().encode("utf-8")
    sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = (
        base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    )
    return f"{payload_b64}.{sig_b64}"


def verify_session_token(token: Optional[str]) -> bool:
    """
    Validates an HMAC-SHA256 signed session token.
    Checks signature integrity, payload structure, and expiration timestamp.
    """
    if not token or "." not in token:
        return False

    parts = token.split(".")
    if len(parts) != 2:
        return False

    payload_b64, sig_b64 = parts
    secret = get_session_secret().encode("utf-8")
    expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

    if not secrets.compare_digest(
        sig_b64.encode("utf-8"), expected_sig_b64.encode("utf-8")
    ):
        return False

    try:
        padding = 4 - (len(payload_b64) % 4)
        padded = payload_b64 + ("=" * padding) if (padding and padding < 4) else payload_b64
        raw_json = base64.urlsafe_b64decode(padded).decode("utf-8")
        payload = json.loads(raw_json)
        if not payload.get("admin"):
            return False
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return False
        return True
    except Exception as exc:
        logger.debug(f"Session token verification error: {exc}")
        return False


def verify_admin_cookie(request: Request) -> bool:
    """Checks whether the request contains a valid, signed admin session cookie."""
    token = request.cookies.get(settings.admin_cookie_name)
    return verify_session_token(token)


class AdminLoginRequest(BaseModel):
    password: str
