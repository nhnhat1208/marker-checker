from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from uuid import uuid4

from cachetools import TTLCache

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1

from marker_checker_agent.config import GoogleSheetsConfig
from marker_checker_agent.domain.models import (
    AuditEventRecord,
    RequestConversationRecord,
    RequestRecord,
)
from marker_checker_agent.persistence.google_sheets_mapper import (
    AUDIT_HEADERS,
    CONVERSATION_HEADERS,
    REQUEST_HEADERS,
    audit_from_row,
    audit_to_row,
    conversation_to_row,
    request_from_row,
    request_to_row,
)


class GoogleSheetsWorkflowStore:
    _SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, config: GoogleSheetsConfig) -> None:
        self._config = config
        # RLock: write methods hold the lock then call _iter_rows internally (reentrant).
        self._lock = threading.RLock()
        # Cache raw worksheet values for 15s; maxsize=3 (one per worksheet).
        # Invalidated immediately after every write so reads post-write are always fresh.
        self._sheet_cache: TTLCache[str, list[list[str]]] = TTLCache(maxsize=3, ttl=15)
        self._client = self._build_client()
        self._spreadsheet = self._open_spreadsheet()

    def initialize(self) -> None:
        if not self._config.enabled:
            raise ValueError("Google Sheets persistence is disabled.")

        if not self._config.auto_create_worksheets:
            return

        with self._lock:
            self._ensure_worksheet(
                self._config.worksheets.requests,
                REQUEST_HEADERS,
            )
            self._ensure_worksheet(
                self._config.worksheets.audit_events,
                AUDIT_HEADERS,
            )
            self._ensure_worksheet(
                self._config.worksheets.request_conversations,
                CONVERSATION_HEADERS,
            )

    def create_request(self, request: RequestRecord) -> RequestRecord:
        with self._lock:
            worksheet = self._requests_worksheet()
            worksheet.append_row(request_to_row(request), value_input_option="RAW")
            self._sheet_cache.pop(worksheet.title, None)
        return request

    def update_request(self, request: RequestRecord) -> RequestRecord:
        with self._lock:
            worksheet = self._requests_worksheet()
            row_number = self._find_row_number(worksheet, "request_id", request.request_id)
            if row_number is None:
                raise LookupError(f"Request {request.request_id} was not found")

            end_cell = rowcol_to_a1(row_number, len(REQUEST_HEADERS))
            worksheet.update(
                f"A{row_number}:{end_cell}",
                [request_to_row(request)],
            )
            self._sheet_cache.pop(worksheet.title, None)
        return request

    def get_request(self, request_id: str) -> RequestRecord | None:
        worksheet = self._requests_worksheet()
        for row in self._iter_rows(worksheet):
            if row.get("request_id") == request_id:
                return request_from_row(row)
        return None

    def list_requests(self) -> list[RequestRecord]:
        worksheet = self._requests_worksheet()
        return [request_from_row(row) for row in self._iter_rows(worksheet)]

    def create_request_conversation(
        self,
        conversation: RequestConversationRecord,
    ) -> RequestConversationRecord:
        if not conversation.row_id:
            conversation.row_id = uuid4().hex

        with self._lock:
            worksheet = self._conversations_worksheet()
            worksheet.append_row(
                conversation_to_row(conversation),
                value_input_option="RAW",
            )
            self._sheet_cache.pop(worksheet.title, None)
        return conversation

    def create_audit_event(self, event: AuditEventRecord) -> AuditEventRecord:
        with self._lock:
            worksheet = self._audit_worksheet()
            if not event.event_id:
                event.event_id = uuid4().hex

            if event.event_sequence <= 0:
                event.event_sequence = self._next_event_sequence_locked(event.request_id)

            worksheet.append_row(audit_to_row(event), value_input_option="RAW")
            self._sheet_cache.pop(worksheet.title, None)
        return event

    def list_audit_events(self, request_id: str) -> list[AuditEventRecord]:
        worksheet = self._audit_worksheet()
        events = [
            audit_from_row(row)
            for row in self._iter_rows(worksheet)
            if row.get("request_id") == request_id
        ]
        return sorted(events, key=lambda event: event.event_sequence)

    def _build_client(self) -> gspread.Client:
        if not self._config.enabled:
            raise ValueError("Google Sheets persistence is disabled.")

        if self._config.service_account_json_base64:
            decoded = base64.b64decode(
                self._config.service_account_json_base64.encode("utf-8")
            )
            info = json.loads(decoded.decode("utf-8"))
            credentials = Credentials.from_service_account_info(
                info,
                scopes=self._SCOPES,
            )
            return gspread.authorize(credentials)

        if self._config.service_account_file:
            service_account_path = Path(self._config.service_account_file).expanduser()
            credentials = Credentials.from_service_account_file(
                service_account_path,
                scopes=self._SCOPES,
            )
            return gspread.authorize(credentials)

        raise ValueError(
            "Google Sheets credentials are missing. Set "
            "google_sheets.service_account_file or "
            "google_sheets.service_account_json_base64 in runtime.yaml, "
            "or provide GOOGLE_SERVICE_ACCOUNT_FILE / GOOGLE_SERVICE_ACCOUNT_JSON_BASE64."
        )

    def _open_spreadsheet(self) -> gspread.Spreadsheet:
        if not self._config.spreadsheet_id:
            raise ValueError(
                "Google Sheets spreadsheet ID is missing. Set google_sheets.spreadsheet_id "
                "in runtime.yaml."
            )
        return self._client.open_by_key(self._config.spreadsheet_id)

    def _requests_worksheet(self) -> gspread.Worksheet:
        return self._get_worksheet(self._config.worksheets.requests, REQUEST_HEADERS)

    def _audit_worksheet(self) -> gspread.Worksheet:
        return self._get_worksheet(self._config.worksheets.audit_events, AUDIT_HEADERS)

    def _conversations_worksheet(self) -> gspread.Worksheet:
        return self._get_worksheet(
            self._config.worksheets.request_conversations,
            CONVERSATION_HEADERS,
        )

    def _get_worksheet(
        self,
        title: str,
        headers: list[str],
    ) -> gspread.Worksheet:
        try:
            return self._spreadsheet.worksheet(title)
        except WorksheetNotFound as exc:
            if not self._config.auto_create_worksheets:
                raise LookupError(f"Worksheet {title} was not found") from exc
            return self._ensure_worksheet(title, headers)

    def _ensure_worksheet(self, title: str, headers: list[str]) -> gspread.Worksheet:
        try:
            worksheet = self._spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(
                title=title,
                rows=1000,
                cols=max(len(headers), 12),
            )

        values = worksheet.get_all_values()
        if not values:
            worksheet.append_row(headers, value_input_option="RAW")
            return worksheet

        if values[0] != headers:
            end_cell = rowcol_to_a1(1, len(headers))
            worksheet.update(f"A1:{end_cell}", [headers])

        return worksheet

    def _iter_rows(self, worksheet: gspread.Worksheet) -> list[dict[str, str]]:
        with self._lock:
            if worksheet.title not in self._sheet_cache:
                self._sheet_cache[worksheet.title] = worksheet.get_all_values()
            values = self._sheet_cache[worksheet.title]

        if not values:
            return []

        headers = values[0]
        rows: list[dict[str, str]] = []
        for row in values[1:]:
            normalized_row = row + [""] * (len(headers) - len(row))
            rows.append(dict(zip(headers, normalized_row, strict=False)))
        return rows

    def _find_row_number(
        self,
        worksheet: gspread.Worksheet,
        key: str,
        expected_value: str,
    ) -> int | None:
        for index, row in enumerate(self._iter_rows(worksheet), start=2):
            if row.get(key) == expected_value:
                return index
        return None

    def _next_event_sequence_locked(self, request_id: str) -> int:
        events = self.list_audit_events(request_id)
        if not events:
            return 1
        return max(event.event_sequence for event in events) + 1
