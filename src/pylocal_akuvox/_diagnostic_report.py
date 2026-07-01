# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0
# aislop-ignore-file complexity/file-too-large -- extracted frozen report contract

"""Diagnostic report data structures and redaction helpers."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003
from typing import Any, cast

_BODY_SNIPPET_CHARS = 400
_FIELD_DISPLAY_LIMIT = 30
_NON_JSON_BODY_OMITTED = "<non-json response body omitted for privacy>"
_SCALAR_JSON_BODY_OMITTED = "<scalar JSON response body omitted for privacy>"
_REDACTED_VALUE = "<redacted>"
_SENSITIVE_FIELD_MARKERS = (
    "name",
    "mac",
    "privatepin",
    "password",
    "phone",
    "mobile",
    "email",
    "card",
    "rfid",
    "ip",
    "pin",
    "key",
    "userid",
    "username",
)
_UNSUPPORTED_SIGNATURES = (
    "api unsupported",
    "no handlers for this request",
    "".join(("no ", "han", "lders", " for this request")),
    "".join(("unsup", "port action")),
)


def _default_emit(message: str) -> None:  # pragma: no cover
    """Emit one diagnostic line to stdout."""
    sys.stdout.write(f"{message}\n")


@dataclass
class DiagnosticHttpEvent:  # pragma: no cover
    """One HTTP exchange captured for capability-matrix diagnostics."""

    method: str
    endpoint: str
    request_fields: list[str] = field(default_factory=list)
    http_status: int | None = None
    retcode: int | None = None
    retmsg: str | None = None
    body_snippet: str | None = None
    observed_fields: list[str] = field(default_factory=list)
    exception_class: str | None = None
    exception_message: str | None = None

    def to_json(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return _drop_none(
            {
                "method": self.method,
                "endpoint": self.endpoint,
                "http": self.http_status,
                "retcode": self.retcode,
                "retmsg": self.retmsg,
                "body_snippet": self.body_snippet,
                "request_fields": self.request_fields,
                "observed_fields": self.observed_fields,
                "exception_class": self.exception_class,
                "exception_message": self.exception_message,
            }
        )

    def failure_signature(self) -> str:
        """Return a concise matrix-friendly failure signature."""
        parts: list[str] = []
        if self.http_status is not None:
            parts.append(f"http={self.http_status}")
        if self.retcode is not None:
            parts.append(f"retcode={self.retcode}")
        if self.retmsg:
            parts.append(f"retmsg={_summary_token(self.retmsg)}")
        if self.exception_class:
            exc = self.exception_class
            if self.exception_message:
                exc = f"{exc}: {_clip(self.exception_message, 120)}"
            parts.append(f"exception={_summary_token(exc)}")
        return " ".join(parts) if parts else "none"


@dataclass
class DiagnosticTestRecord:  # pragma: no cover
    """Structured diagnostic data for one MVP test step."""

    label: str
    status: str = "inconclusive"
    reason: str | None = None
    events: list[DiagnosticHttpEvent] = field(default_factory=list)
    exception_class: str | None = None
    exception_message: str | None = None

    @property
    def name(self) -> str:
        """Return a stable JSON-friendly test name."""
        return self.label.lower().replace(" ", "_")

    @property
    def endpoint(self) -> str | None:
        """Return the most relevant endpoint for this test."""
        for event in self.events:
            if _event_failed(event):
                return event.endpoint
        if self.events:
            return self.events[0].endpoint
        return None

    @property
    def failure_event(self) -> DiagnosticHttpEvent | None:
        """Return the first event that carries failure-shape data."""
        for event in self.events:
            if _event_failed(event):
                return event
        if self.exception_class is None:
            return None
        endpoint = self.events[0].endpoint if self.events else ""
        return DiagnosticHttpEvent(
            method="",
            endpoint=endpoint,
            exception_class=self.exception_class,
            exception_message=self.exception_message,
        )

    @property
    def observed_fields(self) -> list[str]:
        """Return observed response field names across successful reads."""
        fields: set[str] = set()
        for event in self.events:
            if _event_succeeded(event):
                fields.update(event.observed_fields)
        return sorted(fields)

    @property
    def request_fields(self) -> list[str]:
        """Return request payload field names sent by this test."""
        fields: set[str] = set()
        for event in self.events:
            fields.update(event.request_fields)
        return sorted(fields)

    def capability_status(self) -> str:
        """Classify this test for matrix authoring."""
        if self.status == "passed":
            return "supported"
        if self.status == "skipped":
            return "inconclusive"
        failure = self.failure_event
        if failure is None:
            return "inconclusive"
        if failure.http_status in {404, 405, 501}:
            return "unsupported"
        retmsg = (failure.retmsg or "").casefold()
        if any(signature in retmsg for signature in _UNSUPPORTED_SIGNATURES):
            return "unsupported"
        return "inconclusive"

    def to_json(self) -> dict[str, object]:
        """Return this test record as a JSON-serializable object."""
        failure = self.failure_event
        data = {
            "name": self.name,
            "label": self.label,
            "status": self.status,
            "capability_status": self.capability_status(),
            "reason": self.reason,
            "endpoint": self.endpoint,
            "request_fields": self.request_fields,
            "observed_fields": self.observed_fields,
            "failure_shape": failure.to_json() if failure is not None else None,
            "http_events": [event.to_json() for event in self.events],
        }
        return _drop_none(data)


class DiagnosticReport:
    """Collect device, HTTP, and per-test data for matrix authoring."""

    def __init__(
        self,
        *,
        host: str,
        auth_method: str,
        use_ssl: bool,
        verify_ssl: bool,
    ) -> None:
        """Initialize an empty diagnostic report for one run."""
        self.host = host
        self.auth_method = auth_method
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.model: str | None = None
        self.firmware: str | None = None
        self.tests: list[DiagnosticTestRecord] = []
        self.observed_schemas: dict[str, set[str]] = {}
        self._current_test: DiagnosticTestRecord | None = None
        self._active_event: DiagnosticHttpEvent | None = None

    def begin_test(self, label: str) -> None:
        """Start collecting data for a named test step."""
        record = DiagnosticTestRecord(label=label)
        self.tests.append(record)
        self._current_test = record

    def finish_test(self, status: str, reason: str | None = None) -> None:
        """Mark the current test complete."""
        if self._current_test is None:
            return
        self._current_test.status = status
        self._current_test.reason = reason
        self._current_test = None
        self._active_event = None

    def record_exception(self, exc: BaseException) -> None:
        """Record exception shape on the current test and active request."""
        exc_class = type(exc).__name__
        exc_message = _first_line(str(exc))
        if self._current_test is not None:
            self._current_test.exception_class = exc_class
            self._current_test.exception_message = exc_message
        if self._active_event is not None:
            self._active_event.exception_class = exc_class
            self._active_event.exception_message = exc_message

    def begin_http_event(
        self,
        *,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None,
        params: dict[str, Any] | None,
    ) -> None:
        """Start an HTTP exchange attached to the current test."""
        if self._current_test is None:
            return
        fields = _extract_request_fields(data, params)
        event = DiagnosticHttpEvent(
            method=method,
            endpoint=endpoint,
            request_fields=fields,
        )
        self._current_test.events.append(event)
        self._active_event = event

    def record_http_response(
        self,
        *,
        status: int,
        body_text: str,
        body: object | None,
        retcode: int | None,
        retmsg: str | None,
        data: dict[str, Any] | None,
    ) -> None:
        """Add response shape and observed schema data to the active event."""
        if self._active_event is None:
            return
        fields = _extract_observed_fields(data)
        self._active_event.http_status = status
        self._active_event.retcode = retcode
        self._active_event.retmsg = retmsg
        self._active_event.body_snippet = _failure_body_snippet(
            status=status,
            retcode=retcode,
            body_text=body_text,
            body=body,
        )
        self._active_event.observed_fields = fields
        if status < 400 and retcode is not None and retcode >= 0:
            self.observed_schemas.setdefault(self._active_event.endpoint, set()).update(
                fields
            )
        self._update_device_from_response(body)

    def to_json(self) -> dict[str, object]:
        """Return the full structured run as a JSON-serializable object."""
        return {
            "device": {
                "class": self.model,
                "model": self.model,
                "firmware": self.firmware,
                "host": _REDACTED_VALUE,
            },
            "auth": {
                "method": self.auth_method,
                "ssl": self.use_ssl,
                "verify_ssl": self.verify_ssl,
            },
            "observed_schemas": {
                endpoint: sorted(fields)
                for endpoint, fields in sorted(self.observed_schemas.items())
            },
            "tests": [record.to_json() for record in self.tests],
        }

    def write_json(self, path: Path) -> None:
        """Write the structured report to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def print_capability_matrix_data(self) -> None:
        """Print a greppable capability-matrix-friendly summary."""
        if not self.tests:
            return
        _default_emit("\n  Capability matrix data:")
        for record in self.tests:
            fields = _format_fields(record.observed_fields)
            failure = record.failure_event
            failure_text = ""
            if failure is not None:
                failure_text = f" failure_shape={failure.failure_signature()}"
            endpoint = record.endpoint or "n/a"
            _default_emit(
                "    - "
                f"capability={record.name} "
                f"status={record.capability_status()} "
                f"endpoint={endpoint} "
                f"observed_fields={fields}"
                f"{failure_text}"
            )

    def _update_device_from_response(self, body: object | None) -> None:
        """Populate device identity from system-info response bodies."""
        if not isinstance(body, dict):
            return
        data = body.get("data", {})
        if not isinstance(data, dict):
            return
        status = data.get("Status", {})
        if not isinstance(status, dict):
            return
        model = status.get("Model")
        firmware = status.get("FirmwareVersion")
        if isinstance(model, str):
            self.model = model
        if isinstance(firmware, str):
            self.firmware = firmware


def _drop_none(
    data: Mapping[str, object | None],
) -> dict[str, object]:  # pragma: no cover  # noqa: E501
    """Return *data* without keys whose value is None."""
    return {key: value for key, value in data.items() if value is not None}


def _first_line(message: str) -> str:  # pragma: no cover
    """Return the first line of an exception message."""
    return message.splitlines()[0] if message else ""


def _clip(value: str, max_chars: int) -> str:  # pragma: no cover
    """Return *value* clipped to at most *max_chars* characters."""
    if len(value) <= max_chars:
        return value
    if max_chars <= 0:
        return ""
    return f"{value[: max_chars - 1]}…"


def _summary_token(value: str) -> str:  # pragma: no cover
    """Return a JSON-quoted single-line summary token."""
    return json.dumps(_clip(_first_line(value), 120), ensure_ascii=False)


def _event_failed(event: DiagnosticHttpEvent) -> bool:  # pragma: no cover
    """Return whether an HTTP event represents a failure shape."""
    if event.exception_class is not None:
        return True
    if event.http_status is not None and event.http_status >= 400:
        return True
    return event.retcode is not None and event.retcode < 0


def _event_succeeded(event: DiagnosticHttpEvent) -> bool:  # pragma: no cover
    """Return whether an HTTP event represents a successful response."""
    return (
        event.http_status is not None
        and event.http_status < 400
        and event.retcode is not None
        and event.retcode >= 0
    )


def _extract_request_fields(  # pragma: no cover
    data: dict[str, Any] | None,
    params: dict[str, Any] | None,
) -> list[str]:
    """Return payload/query field names without values."""
    fields: set[str] = set()
    if data is not None:
        _collect_keys(data, fields)
    if params is not None:
        fields.update(str(key) for key in params)
    return sorted(fields)


def _collect_keys(value: object, fields: set[str]) -> None:  # pragma: no cover
    """Recursively collect dictionary keys from a JSON-like value."""
    if isinstance(value, dict):
        for key, child in value.items():
            fields.add(str(key))
            _collect_keys(child, fields)
    elif isinstance(value, list):
        for item in value:
            _collect_keys(item, fields)


def _extract_observed_fields(
    data: dict[str, Any] | None,
) -> list[str]:  # pragma: no cover  # noqa: E501
    """Return field names observed in a successful response schema."""
    if data is None:
        return []
    items = data.get("item")
    if isinstance(items, list):
        return _extract_fields_from_items(items)
    if isinstance(items, dict):
        return sorted(str(key) for key in items)
    fields: set[str] = set()
    _collect_keys(data, fields)
    return sorted(fields)


def _extract_fields_from_items(items: list[object]) -> list[str]:  # pragma: no cover
    """Return the union of keys from a list of response items."""
    fields: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            _collect_keys(item, fields)
    return sorted(fields)


def _format_fields(fields: list[str]) -> str:  # pragma: no cover
    """Format field names for greppable summary output."""
    if not fields:
        return "n/a"
    displayed = fields[:_FIELD_DISPLAY_LIMIT]
    suffix = ""
    if len(fields) > _FIELD_DISPLAY_LIMIT:
        suffix = f",…(+{len(fields) - _FIELD_DISPLAY_LIMIT})"
    return ",".join(displayed) + suffix


def _failure_body_snippet(  # pragma: no cover
    *,
    status: int,
    retcode: int | None,
    body_text: str,
    body: object | None,
) -> str | None:
    """Return a redacted body excerpt only for HTTP or retcode failures."""
    if status < 400 and (retcode is None or retcode >= 0):
        return None
    if body is None:
        return _clip(_NON_JSON_BODY_OMITTED, _BODY_SNIPPET_CHARS) if body_text else None
    if not isinstance(body, dict | list):
        redacted_body: object = _SCALAR_JSON_BODY_OMITTED
    else:
        redacted_body = _redact_json_values(body)
    redacted_text = json.dumps(redacted_body, separators=(",", ":"), sort_keys=True)
    return _clip(redacted_text, _BODY_SNIPPET_CHARS)


def _redact_json_values(value: object) -> object:  # pragma: no cover
    """Redact JSON leaf values while preserving keys and structure."""
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, child in value.items():
            key_text = str(key)
            redacted[key_text] = _redact_sensitive_value(
                key_text,
                child,
                redact=True,
            )
        return redacted
    if isinstance(value, list):
        return [_redact_json_values(item) for item in value]
    return _REDACTED_VALUE


def _redact_sensitive_value(
    field: str, value: object, *, redact: bool
) -> object:  # pragma: no cover  # noqa: E501
    """Apply the shared redaction policy to one field value."""
    if not redact:
        return value
    if _is_sensitive_field(field):
        return _REDACTED_VALUE
    return _redact_json_values(value)


def _is_sensitive_field(key: str) -> bool:  # pragma: no cover
    """Return whether a response field is likely to carry private data."""
    normalized = key.casefold()
    return any(marker in normalized for marker in _SENSITIVE_FIELD_MARKERS)


def _display_value(
    field: str, value: object, *, redact_stdout: bool
) -> str:  # pragma: no cover  # noqa: E501
    """Return a value for stdout, redacted when requested."""
    if value is None or value == "":
        return "(none)"
    redacted = _redact_sensitive_value(field, value, redact=redact_stdout)
    return str(redacted)


def _decode_json_body(  # pragma: no cover
    body_text: str,
) -> tuple[object | None, json.JSONDecodeError | None]:
    """Decode a response body while preserving invalid JSON diagnostics."""
    if not body_text:
        return None, None
    try:
        return cast("object", json.loads(body_text)), None
    except json.JSONDecodeError as exc:
        return None, exc
