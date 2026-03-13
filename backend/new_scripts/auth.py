from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def _secret_key() -> str:
    return os.getenv("API_AUTH_SECRET", "novarisk-dev-secret")


def _token_ttl_seconds() -> int:
    return int(os.getenv("API_TOKEN_TTL_SECONDS", "28800"))


def authenticate_credentials(username: str, password: str) -> bool:
    expected_username = os.getenv("DASHBOARD_USERNAME", "investor")
    expected_password = os.getenv("DASHBOARD_PASSWORD", "novarisk-demo")
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + _token_ttl_seconds(),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")

    signature = hmac.new(_secret_key().encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{payload_b64}.{signature_b64}"


def _decode_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format") from exc

    expected_signature = hmac.new(
        _secret_key().encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).digest()
    expected_signature_b64 = base64.urlsafe_b64encode(expected_signature).decode("utf-8").rstrip("=")

    if not hmac.compare_digest(signature_b64, expected_signature_b64):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    padding = "=" * (-len(payload_b64) % 4)
    payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
    payload = json.loads(payload_json)

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return _decode_token(credentials.credentials)
