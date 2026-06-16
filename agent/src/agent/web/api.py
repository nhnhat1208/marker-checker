from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import JSONResponse, Response

from agent.web.session import get_current_user

if TYPE_CHECKING:
    from starlette.requests import Request

    from agent.config import WebConfig


def make_me_handler(config: WebConfig):
    async def me(request: Request) -> Response:
        user = get_current_user(dict(request.cookies), config.session_secret)
        if user is None:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return JSONResponse(
            {
                "email": user.email,
                "name": user.name,
                "avatar_url": user.avatar_url,
            }
        )

    return me
