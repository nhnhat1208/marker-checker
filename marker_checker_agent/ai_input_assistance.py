from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from marker_checker_agent.ai_prompts import (
    REQUEST_ACTION_RESULT_SYSTEM_PROMPT,
    REQUEST_CLARIFICATION_SYSTEM_PROMPT,
    REQUEST_CONFIRMATION_SYSTEM_PROMPT,
    REQUEST_HISTORY_SUMMARY_SYSTEM_PROMPT,
    REQUEST_PARSE_SYSTEM_PROMPT,
    REQUEST_STATUS_SUMMARY_SYSTEM_PROMPT,
    build_action_result_user_prompt,
    build_clarification_user_prompt,
    build_confirmation_user_prompt,
    build_history_summary_user_prompt,
    build_request_parse_user_prompt,
    build_status_summary_user_prompt,
)
from marker_checker_agent.config import AIConfig
from marker_checker_agent.request_parser import ParsedRequest, list_missing_required_fields


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssistedParseResult:
    parsed_request: ParsedRequest | None
    guidance_message: str | None = None
    parser_name: str = "pattern"
    missing_fields: list[str] | None = None
    validation_errors: list[str] | None = None
    latency_ms: int | None = None
    model: str | None = None
    prompt_version: str | None = None


class RequestInputAssistant(Protocol):
    def assist_request_text(self, text: str) -> AssistedParseResult:
        ...

    def generate_clarification_message(
        self,
        *,
        original_message: str,
        missing_fields: list[str],
        validation_errors: list[str],
    ) -> str | None:
        ...

    def generate_confirmation_message(self, *, parsed_request_summary: str) -> str | None:
        ...

    def generate_status_summary(self, *, request_summary: str) -> str | None:
        ...

    def generate_history_summary(self, *, request_history: str) -> str | None:
        ...

    def generate_action_result_message(self, *, action_result: str) -> str | None:
        ...


class OpenAICompatibleInputAssistant:
    _APPROVER_HANDLE_PATTERN = re.compile(r"^@[\w_]+$")

    def __init__(self, config: AIConfig) -> None:
        self._config = config

    def assist_request_text(self, text: str) -> AssistedParseResult:
        started_at = time.perf_counter()
        try:
            payload = self._invoke_model(text)
        except Exception as exc:  # pragma: no cover
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            LOGGER.warning(
                "LLM input assistance failed model=%s prompt_version=%s latency_ms=%s error=%s",
                self._config.model,
                self._config.prompt_version,
                latency_ms,
                exc,
            )
            return AssistedParseResult(
                parsed_request=None,
                parser_name="llm_assisted",
                latency_ms=latency_ms,
                model=self._config.model,
                prompt_version=self._config.prompt_version,
            )

        parsed = ParsedRequest(
            target_label=payload.get("target_label", "").strip(),
            change_from_summary=payload.get("change_from_summary", "").strip(),
            change_to_summary=payload.get("change_to_summary", "").strip(),
            approver_handle=self._normalize_approver_handle(
                payload.get("approver_handle", "")
            ),
        )
        parsed, validation_errors = self._validate_parsed_request(parsed)
        missing_fields = list_missing_required_fields(parsed)
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        if missing_fields:
            guidance_message = payload.get("guidance_message") or self._build_guidance_message(
                missing_fields,
                validation_errors,
            )
            LOGGER.info(
                "LLM input assistance incomplete model=%s prompt_version=%s latency_ms=%s missing_fields=%s validation_errors=%s",
                self._config.model,
                self._config.prompt_version,
                latency_ms,
                ",".join(missing_fields),
                validation_errors,
            )
            return AssistedParseResult(
                parsed_request=parsed,
                guidance_message=guidance_message,
                parser_name="llm_assisted",
                missing_fields=missing_fields,
                validation_errors=validation_errors,
                latency_ms=latency_ms,
                model=self._config.model,
                prompt_version=self._config.prompt_version,
            )

        LOGGER.info(
            "LLM input assistance succeeded model=%s prompt_version=%s latency_ms=%s target=%s approver=%s",
            self._config.model,
            self._config.prompt_version,
            latency_ms,
            parsed.target_label,
            parsed.approver_handle,
        )
        return AssistedParseResult(
            parsed_request=parsed,
            parser_name="llm_assisted",
            missing_fields=[],
            validation_errors=validation_errors,
            latency_ms=latency_ms,
            model=self._config.model,
            prompt_version=self._config.prompt_version,
        )

    def generate_clarification_message(
        self,
        *,
        original_message: str,
        missing_fields: list[str],
        validation_errors: list[str],
    ) -> str | None:
        return self._generate_text_message(
            system_prompt=REQUEST_CLARIFICATION_SYSTEM_PROMPT,
            user_prompt=build_clarification_user_prompt(
                original_message=original_message,
                missing_fields=missing_fields,
                validation_errors=validation_errors,
            ),
            max_tokens=min(self._config.max_tokens, 120),
        )

    def generate_confirmation_message(self, *, parsed_request_summary: str) -> str | None:
        return self._generate_text_message(
            system_prompt=REQUEST_CONFIRMATION_SYSTEM_PROMPT,
            user_prompt=build_confirmation_user_prompt(
                parsed_request_summary=parsed_request_summary
            ),
            max_tokens=min(self._config.max_tokens, 160),
        )

    def generate_status_summary(self, *, request_summary: str) -> str | None:
        return self._generate_text_message(
            system_prompt=REQUEST_STATUS_SUMMARY_SYSTEM_PROMPT,
            user_prompt=build_status_summary_user_prompt(request_summary=request_summary),
            max_tokens=min(self._config.max_tokens, 120),
        )

    def generate_history_summary(self, *, request_history: str) -> str | None:
        return self._generate_text_message(
            system_prompt=REQUEST_HISTORY_SUMMARY_SYSTEM_PROMPT,
            user_prompt=build_history_summary_user_prompt(request_history=request_history),
            max_tokens=min(self._config.max_tokens, 120),
        )

    def generate_action_result_message(self, *, action_result: str) -> str | None:
        return self._generate_text_message(
            system_prompt=REQUEST_ACTION_RESULT_SYSTEM_PROMPT,
            user_prompt=build_action_result_user_prompt(action_result=action_result),
            max_tokens=min(self._config.max_tokens, 120),
        )

    def _invoke_model(self, text: str) -> dict[str, str]:
        content = self._invoke_completion_content(
            system_prompt=REQUEST_PARSE_SYSTEM_PROMPT,
            user_prompt=build_request_parse_user_prompt(text),
            max_tokens=self._config.max_tokens,
        )
        return self._parse_json_content(content)

    def _generate_text_message(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str | None:
        try:
            content = self._invoke_completion_content(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # pragma: no cover
            LOGGER.warning(
                "LLM UX message generation failed model=%s prompt_version=%s error=%s",
                self._config.model,
                self._config.prompt_version,
                exc,
            )
            return None
        return content.strip() or None

    def _invoke_completion_content(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        response = httpx.post(
            f"{self._config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
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
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def _parse_json_content(self, content: str) -> dict[str, str]:
        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = normalized.removeprefix("```json").removeprefix("```").strip()
            if normalized.endswith("```"):
                normalized = normalized[:-3].strip()
        parsed = json.loads(normalized)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response was not a JSON object.")
        return {str(key): str(value or "") for key, value in parsed.items()}

    def _normalize_approver_handle(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""
        if normalized.startswith("@"):
            return normalized
        if normalized.startswith("#"):
            return f"@{normalized[1:]}"
        return f"@{normalized}"

    def _validate_parsed_request(
        self,
        parsed_request: ParsedRequest,
    ) -> tuple[ParsedRequest, list[str]]:
        validation_errors: list[str] = []
        target_label = " ".join(parsed_request.target_label.split())
        change_from_summary = " ".join(parsed_request.change_from_summary.split())
        change_to_summary = " ".join(parsed_request.change_to_summary.split())
        approver_handle = parsed_request.approver_handle.strip()

        if target_label and len(target_label) > 120:
            validation_errors.append("target_label is too long")
            target_label = ""

        if approver_handle and not self._APPROVER_HANDLE_PATTERN.match(approver_handle):
            validation_errors.append("approver_handle format is invalid")
            approver_handle = ""

        if (
            change_from_summary
            and change_to_summary
            and change_from_summary.casefold() == change_to_summary.casefold()
        ):
            validation_errors.append("change_from_summary and change_to_summary are identical")
            change_from_summary = ""
            change_to_summary = ""

        return (
            ParsedRequest(
                target_label=target_label,
                change_from_summary=change_from_summary,
                change_to_summary=change_to_summary,
                approver_handle=approver_handle,
            ),
            validation_errors,
        )

    def _build_guidance_message(
        self,
        missing_fields: list[str],
        validation_errors: list[str],
    ) -> str:
        guidance_parts: list[str] = []
        if validation_errors:
            guidance_parts.append("; ".join(validation_errors))
        if missing_fields:
            guidance_parts.append(f"Missing fields: {', '.join(missing_fields)}")
        return ". ".join(guidance_parts) if guidance_parts else "Request needs clarification."


def build_input_assistant(config: AIConfig) -> RequestInputAssistant | None:
    if not config.enabled:
        return None
    return OpenAICompatibleInputAssistant(config)
