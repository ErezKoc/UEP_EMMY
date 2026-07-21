"""Password hashing and session tokens, standard library only.

Deliberately simple for the MVP ("just enough to make the flow work"):
- Passwords: PBKDF2-HMAC-SHA256 with a per-user random salt.
- Tokens: `<user_id>.<expires_ts>.<hmac>` signed with SECRET_KEY — an opaque
  bearer token the frontend stores and sends as `Authorization: Bearer ...`.

For production this would move to a vetted stack (e.g. passlib/bcrypt and JWTs
via a maintained library, or Amazon Cognito), but the API contract — signup/
login return a token, protected routes require the Bearer header — stays the
same, so swapping it later touches only this file.
"""

import base64
import hashlib
import hmac
import os
import time
import uuid

from app.core.config import get_settings

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    signature = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode().rstrip("=")


def create_token(user_id: uuid.UUID) -> str:
    expires = int(time.time()) + get_settings().token_ttl_hours * 3600
    payload = f"{user_id}.{expires}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> uuid.UUID | None:
    """Return the user id for a valid, unexpired token; None otherwise."""
    try:
        user_id_str, expires_str, signature = token.rsplit(".", 2)
    except ValueError:
        return None
    payload = f"{user_id_str}.{expires_str}"
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    if int(expires_str) < time.time():
        return None
    try:
        return uuid.UUID(user_id_str)
    except ValueError:
        return None
