from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WebUser:
    email: str
    name: str
    avatar_url: str
