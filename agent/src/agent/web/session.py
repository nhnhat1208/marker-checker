from __future__ import annotations

from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from agent.web.models import WebUser

_COOKIE_NAME = "web_session"
_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def make_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="web-session")


def encode_session(user: WebUser, secret: str) -> str:
    s = make_serializer(secret)
    return s.dumps({"email": user.email, "name": user.name, "avatar_url": user.avatar_url})


def decode_session(token: str, secret: str) -> WebUser | None:
    s = make_serializer(secret)
    try:
        data: dict[str, Any] = s.loads(token, max_age=_MAX_AGE)
        return WebUser(
            email=data.get("email", ""),
            name=data.get("name", ""),
            avatar_url=data.get("avatar_url", ""),
        )
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(cookies: dict[str, str], secret: str) -> WebUser | None:
    token = cookies.get(_COOKIE_NAME, "")
    if not token:
        return None
    return decode_session(token, secret)


COOKIE_NAME = _COOKIE_NAME
COOKIE_MAX_AGE = _MAX_AGE
