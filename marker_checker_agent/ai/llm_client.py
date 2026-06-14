from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from marker_checker_agent.config import AIConfig

LOGGER = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: AIConfig) -> None:
        self._config = config
        # Reuse one client across all calls: avoids per-call TCP/TLS handshake (~100-300ms each).
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._config.timeout_seconds,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def complete_text(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        response = self._http.post(
            f"{self._config.base_url.rstrip('/')}/chat/completions",
            json={
                "model": self._config.model,
                "max_tokens": max_tokens,
                "temperature": self._config.temperature,
                "top_p": self._config.top_p,
                "presence_penalty": self._config.presence_penalty,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("LLM response contained no choices.")
        choice = choices[0]
        message = choice.get("message") or {}
        content = message.get("content")
        if not content:
            finish_reason = choice.get("finish_reason", "unknown")
            raise ValueError(
                f"LLM returned empty content (finish_reason={finish_reason!r}). "
                "The model may have run out of tokens during reasoning — increase max_tokens."
            )
        return str(content)

    def complete_json(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> dict[str, str]:
        content = self.complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )
        return _parse_json_response(content)


def _parse_json_response(content: str) -> dict[str, str]:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```").strip()
        if normalized.endswith("```"):
            normalized = normalized[:-3].strip()
    parsed = json.loads(normalized)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response was not a JSON object.")
    return {str(key): str(value or "") for key, value in parsed.items()}
