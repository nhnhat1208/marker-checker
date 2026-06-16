from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, URLSafeSerializer
from starlette.responses import RedirectResponse, Response

from agent.web.models import WebUser
from agent.web.session import COOKIE_MAX_AGE, COOKIE_NAME, encode_session

if TYPE_CHECKING:
    from starlette.requests import Request

    from agent.config import WebConfig
    from agent.persistence.postgres import PostgresWorkflowStore

LOGGER = logging.getLogger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_STATE_COOKIE = "oauth_state"


def _state_signer(secret: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret, salt="oauth-state")


def _make_redirect_uri(request: Request, configured: str) -> str:
    if configured.strip():
        return configured.strip()
    base = str(request.base_url).rstrip("/")
    return f"{base}/auth/callback"


def make_login_handler(config: WebConfig):
    async def login(request: Request) -> Response:
        state = secrets.token_urlsafe(16)
        signed_state = _state_signer(config.session_secret).dumps(state)

        params = urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": _make_redirect_uri(request, config.redirect_uri),
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "online",
            }
        )

        response = RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}", status_code=302)
        response.set_cookie(
            _STATE_COOKIE, signed_state,
            httponly=True, samesite="lax", max_age=600,
        )
        return response
    return login


def make_callback_handler(
    config: WebConfig,
    pg_store: PostgresWorkflowStore | None,
):
    async def callback(request: Request) -> Response:
        code = request.query_params.get("code", "")
        state_from_google = request.query_params.get("state", "")
        signed_state = request.cookies.get(_STATE_COOKIE, "")

        # CSRF: verify state
        try:
            expected = _state_signer(config.session_secret).loads(signed_state)
        except BadSignature:
            LOGGER.warning("OAuth callback: invalid state cookie")
            return RedirectResponse("/?error=invalid_state", status_code=302)

        if expected != state_from_google:
            LOGGER.warning("OAuth callback: state mismatch")
            return RedirectResponse("/?error=state_mismatch", status_code=302)

        redirect_uri = _make_redirect_uri(request, config.redirect_uri)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post(
                    _GOOGLE_TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": config.client_id,
                        "client_secret": config.client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                token_resp.raise_for_status()
                token_data = token_resp.json()

                userinfo_resp = await client.get(
                    _GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                userinfo_resp.raise_for_status()
                userinfo = userinfo_resp.json()
        except Exception as exc:
            LOGGER.warning("OAuth callback: token exchange failed error=%s", exc)
            return RedirectResponse("/?error=auth_failed", status_code=302)

        user = WebUser(
            email=userinfo.get("email", ""),
            name=userinfo.get("name", ""),
            avatar_url=userinfo.get("picture", ""),
        )

        if pg_store is not None and user.email:
            try:
                pg_store.upsert_user_profile(user.email, user.name, user.avatar_url)
            except Exception as exc:
                LOGGER.warning("OAuth callback: upsert_user_profile failed error=%s", exc)

        session_token = encode_session(user, config.session_secret)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            COOKIE_NAME, session_token,
            httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE,
        )
        response.delete_cookie(_STATE_COOKIE)
        return response

    return callback


async def logout(request: Request) -> Response:
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response
