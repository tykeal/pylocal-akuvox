# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Diagnostic report redaction and field-extraction helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

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
