"""M2 · Identity as a service. Same design as Project 1's identity.py:
short-lived tokens, and authentication (is this token valid) kept
separate from authorization (may this tenant touch this resource).
"""
import os
import time
import jwt

_ALGO = "HS256"
_TTL_SECONDS = 900


def _signing_key() -> str:
    key = os.environ.get("CRA_JWT_SIGNING_KEY")
    if not key:
        raise RuntimeError(
            "CRA_JWT_SIGNING_KEY is not set. This service refuses to mint "
            "or verify tokens against a default key."
        )
    return key


def issue_token(agent_id: str, scopes: list[str]) -> str:
    now = int(time.time())
    payload = {"sub": f"agent:{agent_id}", "agent_id": agent_id, "scopes": scopes,
                "iat": now, "exp": now + _TTL_SECONDS}
    return jwt.encode(payload, _signing_key(), algorithm=_ALGO)


def verify_token(token: str) -> dict:
    return jwt.decode(token, _signing_key(), algorithms=[_ALGO])


def check_scope(token: str, required_scope: str) -> tuple[bool, str]:
    try:
        claims = verify_token(token)
    except jwt.ExpiredSignatureError:
        return False, "token_expired"
    except jwt.InvalidTokenError as e:
        return False, f"token_invalid: {e}"
    if required_scope not in claims["scopes"]:
        return False, f"scope_missing: {required_scope} not in {claims['scopes']}"
    return True, "ok"
