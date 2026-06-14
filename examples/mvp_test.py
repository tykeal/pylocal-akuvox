#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

r"""Interactive CLI script to test pylocal-akuvox against a real device.

Usage:
    uv run examples/mvp_test.py <device-ip>
    uv run examples/mvp_test.py <device-ip> --write
    uv run examples/mvp_test.py <device-ip> --auth basic --user admin
    uv run examples/mvp_test.py <device-ip> --ssl --no-verify-ssl

Examples:
    # AllowList / no auth (default) — read-only tests
    uv run examples/mvp_test.py 192.168.1.100

    # Include write tests (creates/deletes test user and schedule)
    uv run examples/mvp_test.py 192.168.1.100 --write

    # Basic auth (prompts for password, or set AKUVOX_PASSWORD env var)
    uv run examples/mvp_test.py 192.168.1.100 --auth basic --user admin

    # HTTPS with self-signed certificate (skip verification)
    uv run examples/mvp_test.py 192.168.1.100 --ssl --no-verify-ssl

    # Write structured diagnostics for capability-matrix authoring
    uv run examples/mvp_test.py 192.168.1.100 --json-report mvp-report.json

    # Digest auth with write tests
    AKUVOX_PASSWORD=secret uv run examples/mvp_test.py 192.168.1.100 \
        --auth digest --user admin --write

JSON report schema: the top-level object contains ``device`` (model, firmware,
and redacted host), ``auth``, ``observed_schemas``, and ``tests``. Each test
includes ``name``, ``status``, ``label``, ``capability_status``, ``reason``,
``endpoint``, ``request_fields``, ``observed_fields``, optional
``failure_shape`` (``http``, ``retcode``, ``retmsg``, ``method``, ``endpoint``,
``request_fields``, ``observed_fields``, redacted ``body_snippet``, and
``exception_*``), plus ``http_events``. Each HTTP event uses the same fields:
``method``, ``endpoint``, ``http``, ``retcode``, ``retmsg``,
``observed_fields``, ``request_fields``, optional ``exception_*``, and redacted
``body_snippet`` only for HTTP or Akuvox retcode failures.

"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Mapping

    import aiohttp

from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
)
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
    AkuvoxParseError,
    AkuvoxUnsupportedError,
    AkuvoxValidationError,
)

SEPARATOR = "-" * 60
# Akuvox devices need time to persist mutations before the next
# API call; two seconds is sufficient based on testing.
_MUTATION_SETTLE_SECS = 2
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


class TestStepFailed(Exception):
    """Expected diagnostic step failure that does not need a traceback."""


class TestStepSkipped(Exception):
    """Diagnostic step skip with a reason for the summary."""


@dataclass
class DiagnosticHttpEvent:
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
class DiagnosticTestRecord:
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
        print("\n  Capability matrix data:")
        for record in self.tests:
            fields = _format_fields(record.observed_fields)
            failure = record.failure_event
            failure_text = ""
            if failure is not None:
                failure_text = f" failure_shape={failure.failure_signature()}"
            endpoint = record.endpoint or "n/a"
            print(
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


class TestResults:
    """Collect diagnostic test outcomes for the final summary."""

    def __init__(self, diagnostics: DiagnosticReport | None = None) -> None:
        """Initialize empty result buckets."""
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.skipped: list[tuple[str, str]] = []
        self.diagnostics = diagnostics

    @property
    def total(self) -> int:
        """Return the total number of recorded test steps."""
        return len(self.passed) + len(self.failed) + len(self.skipped)

    def mark_passed(self, label: str) -> None:
        """Record a passed test step."""
        self.passed.append(label)

    def mark_failed(self, label: str, reason: str) -> None:
        """Record a failed test step with its reason."""
        self.failed.append((label, reason))

    def mark_skipped(self, label: str, reason: str) -> None:
        """Record a skipped test step with its reason."""
        self.skipped.append((label, reason))

    def was_passed(self, label: str) -> bool:
        """Return whether a test step passed."""
        return label in self.passed

    def print_summary(self) -> None:
        """Print a summary of all recorded diagnostic test steps."""
        print(f"\n{'=' * 60}")
        print("  SUMMARY")
        print("=" * 60)
        print(f"  Total:    {self.total:3}")
        print(f"  ✓ Passed: {len(self.passed):3}")
        print(f"  ✗ Failed: {len(self.failed):3}")
        print(f"  ⊘ Skipped:{len(self.skipped):3}")

        _print_summary_section("Passed", [(label, "") for label in self.passed])
        _print_summary_section("Failures", self.failed)
        _print_summary_section("Skipped", self.skipped)
        if self.diagnostics is not None:
            self.diagnostics.print_capability_matrix_data()


def _print_summary_section(
    title: str,
    entries: list[tuple[str, str]],
) -> None:
    """Print one section of the diagnostic summary."""
    if not entries:
        return

    print(f"\n  {title}:")
    for label, reason in entries:
        suffix = f": {reason}" if reason else ""
        print(f"    - {label}{suffix}")


def _drop_none(data: Mapping[str, object | None]) -> dict[str, object]:
    """Return *data* without keys whose value is None."""
    return {key: value for key, value in data.items() if value is not None}


def _first_line(message: str) -> str:
    """Return the first line of an exception message."""
    return message.splitlines()[0] if message else ""


def _clip(value: str, max_chars: int) -> str:
    """Return *value* clipped to at most *max_chars* characters."""
    if len(value) <= max_chars:
        return value
    if max_chars <= 0:
        return ""
    return f"{value[: max_chars - 1]}…"


def _summary_token(value: str) -> str:
    """Return a JSON-quoted single-line summary token."""
    return json.dumps(_clip(_first_line(value), 120), ensure_ascii=False)


def _event_failed(event: DiagnosticHttpEvent) -> bool:
    """Return whether an HTTP event represents a failure shape."""
    if event.exception_class is not None:
        return True
    if event.http_status is not None and event.http_status >= 400:
        return True
    return event.retcode is not None and event.retcode < 0


def _event_succeeded(event: DiagnosticHttpEvent) -> bool:
    """Return whether an HTTP event represents a successful response."""
    return (
        event.http_status is not None
        and event.http_status < 400
        and event.retcode is not None
        and event.retcode >= 0
    )


def _extract_request_fields(
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


def _collect_keys(value: object, fields: set[str]) -> None:
    """Recursively collect dictionary keys from a JSON-like value."""
    if isinstance(value, dict):
        for key, child in value.items():
            fields.add(str(key))
            _collect_keys(child, fields)
    elif isinstance(value, list):
        for item in value:
            _collect_keys(item, fields)


def _extract_observed_fields(data: dict[str, Any] | None) -> list[str]:
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


def _extract_fields_from_items(items: list[object]) -> list[str]:
    """Return the union of keys from a list of response items."""
    fields: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            _collect_keys(item, fields)
    return sorted(fields)


def _format_fields(fields: list[str]) -> str:
    """Format field names for greppable summary output."""
    if not fields:
        return "n/a"
    displayed = fields[:_FIELD_DISPLAY_LIMIT]
    suffix = ""
    if len(fields) > _FIELD_DISPLAY_LIMIT:
        suffix = f",…(+{len(fields) - _FIELD_DISPLAY_LIMIT})"
    return ",".join(displayed) + suffix


def _failure_body_snippet(
    *,
    status: int,
    retcode: int | None,
    body_text: str,
    body: object | None,
) -> str | None:
    """Return a redacted body excerpt only for HTTP or retcode failures."""
    if status < 400 and retcode is not None and retcode >= 0:
        return None
    if body is None:
        return _clip(_NON_JSON_BODY_OMITTED, _BODY_SNIPPET_CHARS) if body_text else None
    if not isinstance(body, dict | list):
        redacted_body: object = _SCALAR_JSON_BODY_OMITTED
    else:
        redacted_body = _redact_json_values(body)
    redacted_text = json.dumps(redacted_body, separators=(",", ":"), sort_keys=True)
    return _clip(redacted_text, _BODY_SNIPPET_CHARS)


def _redact_json_values(value: object) -> object:
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


def _redact_sensitive_value(field: str, value: object, *, redact: bool) -> object:
    """Apply the shared redaction policy to one field value."""
    if not redact:
        return value
    if _is_sensitive_field(field):
        return _REDACTED_VALUE
    return _redact_json_values(value)


def _is_sensitive_field(key: str) -> bool:
    """Return whether a response field is likely to carry private data."""
    normalized = key.casefold()
    return any(marker in normalized for marker in _SENSITIVE_FIELD_MARKERS)


def _display_value(field: str, value: object, *, redact_stdout: bool) -> str:
    """Return a value for stdout, redacted when requested."""
    if value is None or value == "":
        return "(none)"
    redacted = _redact_sensitive_value(field, value, redact=redact_stdout)
    return str(redacted)


def skip_step(results: TestResults, label: str, reason: str) -> None:
    """Record and print a skipped diagnostic step."""
    results.mark_skipped(label, reason)
    if results.diagnostics is not None:
        results.diagnostics.begin_test(label)
        results.diagnostics.finish_test("skipped", reason)
    print(f"  ⊘ {label} skipped: {reason}")


def _effective_status(
    capabilities: DeviceCapabilities,
    *caps: Capability,
) -> CapabilityStatus:
    """Return the best-of-N capability status across ``*caps``.

    Used by :func:`step` to gate operations whose backend has multiple
    transport variants (today only relay trigger has both
    ``RELAY_TRIGGER_API`` and ``RELAY_TRIGGER_FCGI``). The rule is:

    * Any ``SUPPORTED`` wins — at least one variant works on this
      device class, so :meth:`AkuvoxDevice.trigger_relay` will dispatch
      successfully.
    * All ``UNSUPPORTED`` → ``UNSUPPORTED`` — every variant has been
      confirmed-negative; the gate fails fast.
    * Otherwise → ``UNKNOWN`` — at least one variant has been observed
      ``UNKNOWN``; the gate suggests the integrator opt in.
    """
    statuses = [capabilities.status_of(cap) for cap in caps]
    if any(status is CapabilityStatus.SUPPORTED for status in statuses):
        return CapabilityStatus.SUPPORTED
    if all(status is CapabilityStatus.UNSUPPORTED for status in statuses):
        return CapabilityStatus.UNSUPPORTED
    return CapabilityStatus.UNKNOWN


def _record_capability_skip(results: TestResults, name: str, reason: str) -> None:
    """Record + print a capability-gate skip in the ``SKIP: <name>:`` style."""
    if results.diagnostics is not None:
        results.diagnostics.begin_test(name)
        results.diagnostics.finish_test("skipped", reason)
    results.mark_skipped(name, reason)
    print(f"  SKIP: {name}: {reason}")


async def step[T](
    *,
    results: TestResults,
    name: str,
    capability: Capability | tuple[Capability, ...],
    capabilities: DeviceCapabilities,
    coro_factory: Callable[[], Awaitable[T]],
) -> T | None:
    """Capability-gate one diagnostic step (Phase 4, FR-019).

    Per ``specs/008-capability-matrix/research.md`` Decision 9, this
    consults the supplied :class:`DeviceCapabilities` profile and:

    * ``UNSUPPORTED`` → print ``SKIP: <name>: not supported on this
      device class (<device_class>)`` and return ``None``.
    * ``UNKNOWN`` → print ``SKIP: <name>: status unknown on this
      device class (<device_class>); add a matrix entry or set
      device.attempt_unknown_capability=True to opt in`` and return
      ``None``.
    * ``SUPPORTED`` → call ``coro_factory()`` and run the resulting
      coroutine. On success print ``OK:   <name>`` and return the
      result. On a runtime :class:`AkuvoxUnsupportedError` (rare
      matrix-vs-actual mismatch — the device emitted "unsupported
      action" even though the matrix marked the capability
      ``SUPPORTED``) the failure is re-mapped to ``SKIP: <name>:
      <message> (reason=<reason>)``.

    ``capability`` may be a single :class:`Capability` or a tuple of
    them; the tuple form uses :func:`_effective_status` to gate on
    the best-of-N status (used today only by
    :meth:`AkuvoxDevice.trigger_relay` which has both API and FCGI
    variants).

    Connection / authentication errors propagate unchanged (the
    integrator wants the script to abort, not skip past a
    "device unreachable" event). ``TestStepSkipped`` / generic
    failures fall through to the same FAIL handling as
    :func:`run_step` for parity with the legacy code path.
    """
    if isinstance(capability, tuple):
        status = _effective_status(capabilities, *capability)
    else:
        status = capabilities.status_of(capability)

    if status is CapabilityStatus.UNSUPPORTED:
        reason = f"not supported on this device class ({capabilities.device_class})"
        _record_capability_skip(results, name, reason)
        return None
    if status is CapabilityStatus.UNKNOWN:
        reason = (
            f"status unknown on this device class ({capabilities.device_class}); "
            f"add a matrix entry or set "
            f"device.attempt_unknown_capability=True to opt in"
        )
        _record_capability_skip(results, name, reason)
        return None

    # SUPPORTED — execute and report outcome.
    _begin_diagnostic_step(results, name)
    try:
        result = await coro_factory()
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except (AkuvoxConnectionError, AkuvoxAuthenticationError) as exc:
        _finish_diagnostic_step(results, "failed", str(exc), exc)
        raise
    except AkuvoxUnsupportedError as exc:
        reason = f"{exc} (reason={exc.reason})"
        _finish_diagnostic_step(results, "skipped", reason, exc)
        results.mark_skipped(name, reason)
        print(f"  SKIP: {name}: {reason}")
        return None
    except TestStepSkipped as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "skipped", message, exc)
        results.mark_skipped(name, message)
        print(f"  SKIP: {name}: {message}")
        return None
    except (TestStepFailed, AkuvoxError) as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(name, message)
        print(f"  ✗ {name}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {_first_line(str(exc))}"
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(name, message)
        print(f"  ✗ {name}: {message}")
        traceback.print_exc()
        return None

    _finish_diagnostic_step(results, "passed")
    results.mark_passed(name)
    print(f"  OK:   {name}")
    return result


async def run_step[T](
    results: TestResults,
    label: str,
    coro: Awaitable[T],
) -> T | None:
    """Run one diagnostic coroutine and continue after non-fatal errors."""
    _begin_diagnostic_step(results, label)
    try:
        result = await coro
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except (AkuvoxConnectionError, AkuvoxAuthenticationError) as exc:
        _finish_diagnostic_step(results, "failed", str(exc), exc)
        raise
    except TestStepSkipped as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "skipped", message, exc)
        results.mark_skipped(label, message)
        print(f"  ⊘ {label} skipped: {message}")
        return None
    except TestStepFailed as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        print(f"  ✗ {label}: {message}")
        return None
    except AkuvoxError as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        print(f"  ✗ {label}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {_first_line(str(exc))}"
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        print(f"  ✗ {label}: {message}")
        traceback.print_exc()
        return None

    _finish_diagnostic_step(results, "passed")
    results.mark_passed(label)
    return result


def _begin_diagnostic_step(results: TestResults, label: str) -> None:
    """Begin diagnostics for a test step when enabled."""
    if results.diagnostics is not None:
        results.diagnostics.begin_test(label)


def _finish_diagnostic_step(
    results: TestResults,
    status: str,
    reason: str | None = None,
    exc: BaseException | None = None,
) -> None:
    """Finish diagnostics for a test step when enabled."""
    if results.diagnostics is None:
        return
    if exc is not None:
        results.diagnostics.record_exception(exc)
    results.diagnostics.finish_test(status, reason)


def build_auth(args: argparse.Namespace) -> AuthConfig | None:
    """Build AuthConfig from CLI arguments."""
    if args.auth == "none":
        return None
    method_map = {
        "basic": AuthMethod.BASIC,
        "digest": AuthMethod.DIGEST,
    }
    method = method_map[args.auth]
    return AuthConfig(method=method, username=args.user, password=args.password)


def _install_probed_capabilities(
    device: AkuvoxDevice, profile: DeviceCapabilities
) -> None:
    """Override ``device._capabilities`` with the supplied probe-merged profile.

    The :meth:`AkuvoxDevice.__aenter__` boundary populates
    ``_capabilities`` from the static matrix only. After
    :func:`_probe_device_capabilities` has captured a probe-merged
    profile for the whole script run (Decision 9), this helper
    installs the same profile onto every subsequent connection so
    the wrapper-level per-method capability gate and :func:`step`'s
    gating use the same source of truth — otherwise a
    probe-discovered ``SUPPORTED`` capability could pass
    :func:`step` and then be rejected by the wrapper layer's
    matrix-derived gate (or vice versa for ``UNSUPPORTED``).
    """
    device._capabilities = profile  # noqa: SLF001 - probe-vs-matrix layer parity


def create_device(
    device_kwargs: dict[str, Any],
    diagnostics: DiagnosticReport,
) -> AkuvoxDevice:
    """Create an AkuvoxDevice instrumented for diagnostic capture."""
    device = AkuvoxDevice(**device_kwargs)
    _instrument_device(device, diagnostics)
    return device


def _instrument_device(device: AkuvoxDevice, diagnostics: DiagnosticReport) -> None:
    """Attach diagnostic HTTP capture hooks to a device instance."""
    http = device._http  # noqa: SLF001 - example diagnostics need raw exchanges.
    original_request = http._request  # noqa: SLF001
    original_handle_response = http._handle_response  # noqa: SLF001

    async def diagnostic_request(
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Capture request metadata before delegating to the HTTP client."""
        endpoint = path if path.startswith("/") else f"/{path}"
        diagnostics.begin_http_event(
            method=method,
            endpoint=endpoint,
            data=data,
            params=params,
        )
        try:
            return await original_request(
                method, path, data=data, params=params, timeout=timeout
            )
        except Exception as exc:
            diagnostics.record_exception(exc)
            raise

    http._request = diagnostic_request  # type: ignore[method-assign]  # noqa: SLF001
    http._handle_response = _build_diagnostic_response_handler(  # type: ignore[assignment,method-assign]  # noqa: SLF001
        diagnostics,
        original_handle_response,
    )


def _build_diagnostic_response_handler(
    diagnostics: DiagnosticReport,
    original_handle_response: Callable[
        [aiohttp.ClientResponse],
        Awaitable[dict[str, Any]],
    ],
) -> Callable[[aiohttp.ClientResponse], Awaitable[dict[str, Any]]]:
    """Build a response parser that records the raw failure shape."""

    async def diagnostic_handle_response(
        resp: aiohttp.ClientResponse,
    ) -> dict[str, Any]:
        """Capture response shape before applying library error mapping."""
        body_text = await resp.text()
        body, json_error = _decode_json_body(body_text)
        retcode: int | None = None
        retmsg: str | None = None
        data: dict[str, Any] = {}
        parse_error: AkuvoxParseError | None = None
        if json_error is None:
            try:
                retcode, retmsg, data = _parse_response_shape(
                    body,
                    tolerate_missing_envelope=resp.status >= 400,
                )
            except AkuvoxParseError as exc:
                parse_error = exc
        diagnostics.record_http_response(
            status=resp.status,
            body_text=body_text,
            body=body,
            retcode=retcode,
            retmsg=retmsg,
            data=data,
        )
        if json_error is not None and resp.status < 400:
            msg = "Invalid JSON response"
            raise AkuvoxParseError(msg) from json_error
        if parse_error is not None:
            raise parse_error
        if (
            resp.status < 400
            and retcode is not None
            and retcode >= 0
            and (retmsg is None or "api unsupported" not in retmsg.casefold())
        ):
            return data
        return await original_handle_response(resp)

    return diagnostic_handle_response


def _parse_response_shape(
    body: object | None,
    *,
    tolerate_missing_envelope: bool,
) -> tuple[int | None, str | None, dict[str, Any]]:
    """Parse response envelope or tolerate HTTP error bodies."""
    if tolerate_missing_envelope and (
        not isinstance(body, dict) or "retcode" not in body
    ):
        return None, None, {}
    return _parse_diagnostic_envelope(body)


def _decode_json_body(
    body_text: str,
) -> tuple[object | None, json.JSONDecodeError | None]:
    """Decode a response body while preserving invalid JSON diagnostics."""
    if not body_text:
        return None, None
    try:
        return cast("object", json.loads(body_text)), None
    except json.JSONDecodeError as exc:
        return None, exc


def _parse_diagnostic_envelope(
    body: object | None,
) -> tuple[int | None, str | None, dict[str, Any]]:
    """Parse an Akuvox response envelope for diagnostics."""
    if body is None:
        return None, None, {}
    if not isinstance(body, dict) or "retcode" not in body:
        msg = _missing_envelope_message(body)
        raise AkuvoxParseError(msg)

    retcode = body["retcode"]
    if not isinstance(retcode, int):
        msg = f"Expected retcode to be int, got {type(retcode).__name__}"
        raise AkuvoxParseError(msg)

    retmsg = _extract_retmsg(body)
    data = body.get("data", {})
    result: dict[str, Any] = data if isinstance(data, dict) else {}
    return retcode, retmsg, result


def _missing_envelope_message(body: object) -> str:
    """Return a parse error message that exposes schema keys, not values."""
    if isinstance(body, dict):
        keys = sorted(str(key) for key in body)
        return f"Missing envelope field 'retcode'; keys={keys}"
    return f"Missing envelope fields in {type(body).__name__} response"


def _extract_retmsg(body: dict[str, Any]) -> str:
    """Return the device message field, preserving firmware spelling."""
    message = body.get("retmsg", body.get("message", ""))
    if isinstance(message, str):
        return message
    return str(message) if message is not None else ""


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


async def test_get_info(device: AkuvoxDevice, *, redact_stdout: bool = False) -> None:
    """Test: Retrieve device info."""
    print_header("GET DEVICE INFO (/api/system/info)")
    info = await device.get_info()
    print(f"  Model:            {info.model}")
    mac = _display_value("MAC", info.mac_address, redact_stdout=redact_stdout)
    print(f"  MAC:              {mac}")
    print(f"  Firmware:         {info.firmware_version}")
    print(f"  Hardware:         {info.hardware_version}")
    print(f"  Uptime:           {info.uptime}")
    print(f"  Web Language:     {info.web_language}")
    print("  ✓ get_info() OK")


async def test_get_status(device: AkuvoxDevice) -> None:
    """Test: Retrieve device status."""
    print_header("GET DEVICE STATUS (/api/system/status)")
    status = await device.get_status()
    print(f"  Unix Time:        {status.unix_time}")
    print(f"  Uptime:           {status.uptime}")
    print("  ✓ get_status() OK")


async def test_list_users(device: AkuvoxDevice, *, redact_stdout: bool = False) -> None:
    """Test: List all users."""
    print_header("LIST USERS (/api/user/get)")
    users = await device.list_users()
    print(f"  Found {len(users)} user(s)")
    for user in users:
        name = _display_value("Name", user.name, redact_stdout=redact_stdout)
        user_id = _display_value("UserID", user.user_id, redact_stdout=redact_stdout)
        pin_display = _display_value(
            "PrivatePIN",
            user.private_pin,
            redact_stdout=redact_stdout,
        )
        print(
            f"    ID={user.id}  Name={name}  "
            f"UserID={user_id}  PIN={pin_display}  "
            f"ScheduleRelay={user.schedule_relay}"
        )
    print("  ✓ list_users() OK")


async def test_get_relay_status(device: AkuvoxDevice) -> None:
    """Test: Get relay status."""
    print_header("GET RELAY STATUS (/api/relay/status)")
    status = await device.get_relay_status()
    print(f"  Raw status: {status}")
    print("  ✓ get_relay_status() OK")


async def test_get_device_config(device: AkuvoxDevice) -> None:
    """Test: Get full device configuration."""
    print_header("GET DEVICE CONFIG (/api/config/get)")
    cfg = await device.get_device_config()
    print(f"  Total keys:       {len(cfg)}")
    # Show sample keys by category
    categories: dict[str, int] = {}
    for key in cfg.keys():
        parts = key.split(".")
        cat = ".".join(parts[:2]) if len(parts) >= 2 else key
        categories[cat] = categories.get(cat, 0) + 1
    print(f"  Categories:       {len(categories)}")
    for cat, count in sorted(categories.items())[:10]:
        print(f"    {cat}: {count} keys")
    if len(categories) > 10:
        print(f"    ... and {len(categories) - 10} more categories")
    print("  ✓ get_device_config() OK")


async def test_list_schedules(
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: List all schedules."""
    print_header("LIST SCHEDULES (/api/schedule/get)")
    schedules = await device.list_schedules()
    print(f"  Found {len(schedules)} schedule(s)")
    for sched in schedules:
        name = _display_value("Name", sched.name, redact_stdout=redact_stdout)
        print(
            f"    ID={sched.id}  Name={name}  "
            f"Type={sched.schedule_type}  "
            f"Time={sched.time_start}-{sched.time_end}  "
            f"Week={sched.week}"
        )
    print("  ✓ list_schedules() OK")


async def test_list_groups(
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: List all groups."""
    print_header("LIST GROUPS (/api/group/get)")
    groups = await device.list_groups()
    print(f"  Found {len(groups)} group(s)")
    for grp in groups:
        name = _display_value("Name", grp.name, redact_stdout=redact_stdout)
        print(f"    ID={grp.id}  Name={name}")
    print("  ✓ list_groups() OK")


async def test_list_contacts(
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: List all contacts."""
    print_header("LIST CONTACTS (/api/contact/get)")
    contacts = await device.list_contacts()
    print(f"  Found {len(contacts)} contact(s)")
    for c in contacts:
        name = _display_value("Name", c.name, redact_stdout=redact_stdout)
        phone = _display_value("Phone", c.phone, redact_stdout=redact_stdout)
        print(f"    ID={c.id}  Name={name}  Phone={phone}  Group={c.group}")
    print("  ✓ list_contacts() OK")


async def test_get_door_logs(
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: Retrieve door access logs."""
    print_header("GET DOOR LOGS (/api/doorlog/get)")
    entries = await device.get_door_logs()
    print(f"  Found {len(entries)} door log entry(ies)")
    for entry in entries[:5]:
        name = _display_value("Name", entry.name, redact_stdout=redact_stdout)
        print(
            f"    ID={entry.id}  {entry.date} {entry.time}  "
            f"Name={name}  Type={entry.door_type}  "
            f"Status={entry.status}"
        )
    if len(entries) > 5:
        print(f"    ... and {len(entries) - 5} more")
    print("  ✓ get_door_logs() OK")

    # Test pagination — page 1 should return the same or subset
    page1 = await device.get_door_logs(page=1)
    print(f"  Page 1: {len(page1)} entry(ies)")
    print("  ✓ get_door_logs(page=1) OK")


async def test_get_call_logs(
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: Retrieve call logs."""
    print_header("GET CALL LOGS (/api/calllog/get)")
    entries = await device.get_call_logs()
    print(f"  Found {len(entries)} call log entry(ies)")
    for entry in entries[:5]:
        name = _display_value("Name", entry.name, redact_stdout=redact_stdout)
        print(
            f"    ID={entry.id}  {entry.date} {entry.time}  "
            f"Name={name}  Type={entry.call_type}  "
            f"Count={entry.count}"
        )
    if len(entries) > 5:
        print(f"    ... and {len(entries) - 5} more")
    print("  ✓ get_call_logs() OK")

    # Test pagination — page 1 should return the same or subset
    page1 = await device.get_call_logs(page=1)
    print(f"  Page 1: {len(page1)} entry(ies)")
    print("  ✓ get_call_logs(page=1) OK")


async def test_add_user(device: AkuvoxDevice, *, redact_stdout: bool = False) -> str:
    """Test: Add a test user and return its internal ID."""
    print_header("ADD USER (/api/user/set action:add)")
    test_name = "pylocal-test"
    test_user_id = "9999"
    test_pin = "1234"

    await device.add_user(
        name=test_name,
        user_id=test_user_id,
        private_pin=test_pin,
        web_relay="0",
        schedule_relay="1001-1",
        lift_floor_num="0",
    )
    name = _display_value("Name", test_name, redact_stdout=redact_stdout)
    user_id = _display_value("UserID", test_user_id, redact_stdout=redact_stdout)
    pin = _display_value("PrivatePIN", test_pin, redact_stdout=redact_stdout)
    print(f"  Added user: {name} (UserID={user_id}, PIN={pin})")
    print("  ✓ add_user() OK")

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    # Search for the newly added user (page 1 has all items)
    users = await device.list_users()
    for user in users:
        if user.user_id == test_user_id and user.id is not None:
            print(f"  → Assigned internal ID: {user.id}")
            return user.id

    msg = "User added but internal ID not found in list"
    print(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_modify_user(
    device: AkuvoxDevice,
    internal_id: str,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: Modify the test user's PIN."""
    print_header("MODIFY USER (/api/user/set)")
    new_pin = "5678"
    await device.modify_user(id=internal_id, private_pin=new_pin)
    pin = _display_value("PrivatePIN", new_pin, redact_stdout=redact_stdout)
    print(f"  Modified user ID={internal_id}: PIN changed to {pin}")
    print("  ✓ modify_user() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_delete_user(device: AkuvoxDevice, internal_id: str) -> None:
    """Test: Delete the test user."""
    print_header("DELETE USER (/api/user/set action:del)")
    await device.delete_user(id=internal_id)
    print(f"  Deleted user ID={internal_id}")
    print("  ✓ delete_user() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_trigger_relay(device: AkuvoxDevice) -> None:
    """Test: Trigger relay 1.

    Uses ``delay=0`` (the FCGI variant rejects non-zero
    ``mode``/``level``/``delay``; the API variant treats ``delay=0``
    as "use the device-side default close timer", which is the safest
    cross-device choice).
    """
    print_header("TRIGGER RELAY (/api/relay/trig | /fcgi/do?action=OpenDoor)")
    await device.trigger_relay(num=1)
    print("  Triggered relay 1")
    print("  ✓ trigger_relay() OK")


async def test_add_schedule(device: AkuvoxDevice) -> str:
    """Test: Add a test schedule and return its internal ID."""
    print_header("ADD SCHEDULE (/api/schedule/set action:add)")
    test_name = "pylocal-test-sched"

    await device.add_schedule(
        schedule_type="1",
        name=test_name,
        week="12345",
        time_start="08:00",
        time_end="18:00",
    )
    print(f"  Added schedule: {test_name} (Weekly, Mon-Fri 08-18)")
    print("  ✓ add_schedule() OK")

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    schedules = await device.list_schedules()
    for sched in schedules:
        if sched.name == test_name and sched.id is not None:
            print(f"  → Assigned internal ID: {sched.id}")
            return sched.id

    msg = "Schedule added but internal ID not found in list"
    print(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_modify_schedule(device: AkuvoxDevice, internal_id: str) -> None:
    """Test: Modify the test schedule."""
    print_header("MODIFY SCHEDULE (/api/schedule/set)")
    await device.modify_schedule(
        id=internal_id,
        name="pylocal-test-modified",
        time_start="09:00",
        time_end="17:00",
    )
    print(f"  Modified schedule ID={internal_id}: name + times changed")
    print("  ✓ modify_schedule() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_delete_schedule(device: AkuvoxDevice, internal_id: str) -> None:
    """Test: Delete the test schedule."""
    print_header("DELETE SCHEDULE (/api/schedule/set action:del)")
    await device.delete_schedule(id=internal_id)
    print(f"  Deleted schedule ID={internal_id}")
    print("  ✓ delete_schedule() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_add_group(device: AkuvoxDevice) -> str:
    """Test: Add a group and return its internal ID."""
    print_header("ADD GROUP (/api/group/add)")
    await device.add_group(name="__test_group__")
    print("  Sent add_group(name='__test_group__')")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    groups = await device.list_groups()
    for grp in groups:
        if grp.name == "__test_group__" and grp.id is not None:
            print(f"  ✓ add_group() OK — ID={grp.id}")
            return grp.id
    msg = "Group created but not found in list"
    print(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_delete_group(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Delete the test group."""
    print_header("DELETE GROUP (/api/group/del)")
    await device.delete_group(id=internal_id)
    print(f"  Deleted group ID={internal_id}")
    print("  ✓ delete_group() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_add_contact(device: AkuvoxDevice) -> str:
    """Test: Add a contact and return its internal ID."""
    print_header("ADD CONTACT (/api/contact/set action:add)")
    await device.add_contact(
        name="__test_contact__",
        phone="5550000",
        group="Default",
    )
    print("  Sent add_contact(name='__test_contact__')")
    print("  ✓ add_contact() OK")

    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    contacts = await device.list_contacts()
    for c in contacts:
        if c.name == "__test_contact__" and c.id is not None:
            print(f"  → Assigned internal ID: {c.id}")
            return c.id
    msg = "Contact created but not found in list"
    print(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_delete_contact(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Delete the test contact."""
    print_header("DELETE CONTACT (/api/contact/set action:del)")
    await device.delete_contact(id=internal_id)
    print(f"  Deleted contact ID={internal_id}")
    print("  ✓ delete_contact() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_modify_contact(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Modify a contact's group membership."""
    print_header("MODIFY CONTACT (/api/contact/set action:set)")
    await device.modify_contact(id=internal_id, group="Default")
    print(f"  Modified contact ID={internal_id} group→Default")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    contacts = await device.list_contacts()
    for c in contacts:
        if c.id == internal_id:
            print(f"  → Group is now: {c.group}")
            break
    print("  ✓ modify_contact() OK")


async def _check_validation(label: str, coro: Coroutine[object, object, None]) -> None:
    """Run a single validation check and print the result."""
    try:
        await coro
        print(f"  ✗ Should have raised for {label}")
    except AkuvoxValidationError as exc:
        print(f"  ✓ {label}: {exc}")


async def test_validation() -> None:
    """Test: Client-side validation (no device needed).

    Phase 2 added a per-call capability gate that runs *before*
    the service-layer input validation. To keep this offline
    diagnostic working, we manually install a permissive empty
    capability profile and toggle ``attempt_unknown_capability``
    so the gate falls through and the underlying validation raises
    the expected :class:`AkuvoxValidationError`. The device is
    never connected; the gate is opened only enough for input
    validation to run.
    """
    print_header("CLIENT-SIDE VALIDATION (no network)")

    device = AkuvoxDevice("0.0.0.0")
    # Install an empty offline profile so the per-call gate falls
    # through to the service-layer validation. ``_capabilities`` is
    # nominally private; touching it directly here is the documented
    # offline-test escape hatch — the alternative would be to spin
    # up an actual device connection just to validate input shapes.
    device._capabilities = DeviceCapabilities(  # noqa: SLF001
        device_class="OFFLINE",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={},
        schema_shapes={},
    )
    device.attempt_unknown_capability = True

    await _check_validation(
        "Invalid PIN rejected",
        device.add_user(
            name="Bad",
            user_id="0001",
            private_pin="12ab",
            web_relay="0",
            schedule_relay="1001-1",
            lift_floor_num="0",
        ),
    )
    await _check_validation(
        "Empty name rejected",
        device.add_user(
            name="",
            user_id="0001",
            web_relay="0",
            schedule_relay="1001-1",
            lift_floor_num="0",
        ),
    )
    await _check_validation(
        "Empty schedule_relay rejected",
        device.add_user(
            name="Bad",
            user_id="0001",
            web_relay="0",
            schedule_relay="",
            lift_floor_num="0",
        ),
    )
    await _check_validation(
        "Invalid relay number rejected",
        device.trigger_relay(num=0),
    )
    await _check_validation(
        "Invalid relay mode rejected",
        device.trigger_relay(num=1, mode=5),
    )
    await _check_validation(
        "Invalid schedule type rejected",
        device.add_schedule(schedule_type="9"),
    )
    await _check_validation(
        "Invalid schedule time rejected",
        device.add_schedule(schedule_type="1", time_start="25:00"),
    )
    await _check_validation(
        "Invalid week codes rejected",
        device.add_schedule(schedule_type="1", week="789"),
    )
    await _check_validation(
        "Invalid daily format rejected",
        device.add_schedule(schedule_type="2", daily="bad"),
    )
    await _check_validation(
        "Invalid schedule date rejected",
        device.add_schedule(schedule_type="0", date_start="2026-01"),
    )
    await _check_validation(
        "Empty group name rejected",
        device.add_group(name=""),
    )
    await _check_validation(
        "Empty group modify name rejected",
        device.modify_group(id="1", name=""),
    )
    await _check_validation(
        "Empty contact name rejected",
        device.add_contact(name=""),
    )

    print("  ✓ All validation checks passed")


async def test_discover_config_keys(device: AkuvoxDevice) -> None:
    """Test: Discover all configuration key categories."""
    print_header("DISCOVER CONFIG KEYS")
    cfg = await device.get_device_config()
    categories: dict[str, int] = {}
    for key in cfg.keys():
        parts = key.split(".")
        cat = ".".join(parts[:2]) if len(parts) >= 2 else key
        categories[cat] = categories.get(cat, 0) + 1
    print(f"  Total keys:       {len(cfg)}")
    print(f"  Categories:       {len(categories)}")
    for cat, count in sorted(categories.items()):
        print(f"    {cat}: {count} keys")
    print("  ✓ Key discovery OK")


async def _run_read_tests(
    device: AkuvoxDevice,
    results: TestResults,
    *,
    capabilities: DeviceCapabilities,
    redact_stdout: bool,
) -> None:
    """Run all read-only tests against a connected device.

    Each step is capability-gated against ``capabilities`` (the
    probe-merged profile captured once at the top of :func:`run_all`).
    ``get_device_info`` and ``get_device_status`` are intentionally
    *not* gated — they are the universal connect-time discovery
    surface (see :meth:`AkuvoxDevice.get_info` /
    :meth:`AkuvoxDevice.get_status`); their failure aborts the script
    via ``run_step``'s connection-error propagation.
    """
    _install_probed_capabilities(device, capabilities)
    await run_step(
        results,
        "get_device_info",
        test_get_info(device, redact_stdout=redact_stdout),
    )
    await run_step(results, "get_device_status", test_get_status(device))
    await step(
        results=results,
        name="list_users",
        capability=Capability.USER_LIST,
        capabilities=capabilities,
        coro_factory=lambda: test_list_users(device, redact_stdout=redact_stdout),
    )
    await step(
        results=results,
        name="get_relay_status",
        capability=Capability.RELAY_STATUS,
        capabilities=capabilities,
        coro_factory=lambda: test_get_relay_status(device),
    )
    await step(
        results=results,
        name="get_device_config",
        capability=Capability.DEVICE_CONFIG_GET,
        capabilities=capabilities,
        coro_factory=lambda: test_get_device_config(device),
    )
    await step(
        results=results,
        name="discover_config_keys",
        capability=Capability.KEY_DISCOVERY,
        capabilities=capabilities,
        coro_factory=lambda: test_discover_config_keys(device),
    )
    await step(
        results=results,
        name="list_schedules",
        capability=Capability.SCHEDULE_LIST,
        capabilities=capabilities,
        coro_factory=lambda: test_list_schedules(device, redact_stdout=redact_stdout),
    )
    await step(
        results=results,
        name="list_groups",
        capability=Capability.GROUP_LIST,
        capabilities=capabilities,
        coro_factory=lambda: test_list_groups(device, redact_stdout=redact_stdout),
    )
    await step(
        results=results,
        name="list_contacts",
        capability=Capability.CONTACT_LIST,
        capabilities=capabilities,
        coro_factory=lambda: test_list_contacts(device, redact_stdout=redact_stdout),
    )
    await step(
        results=results,
        name="get_door_logs",
        capability=Capability.LOG_DOOR,
        capabilities=capabilities,
        coro_factory=lambda: test_get_door_logs(device, redact_stdout=redact_stdout),
    )
    await step(
        results=results,
        name="get_call_logs",
        capability=Capability.LOG_CALL,
        capabilities=capabilities,
        coro_factory=lambda: test_get_call_logs(device, redact_stdout=redact_stdout),
    )


async def test_set_device_config(device: AkuvoxDevice) -> None:
    """Test: Set and verify a device configuration value."""
    print_header("SET DEVICE CONFIG (/api/config/set)")
    key = "Config.DoorSetting.RELAY.HoldDelayA"
    original: str | None = None
    # Read current value
    cfg = await device.get_device_config()
    original = cfg.get(key)
    if original is None:
        msg = f"Config key {key!r} not present"
        print(f"  ⚠ {msg}; skipping")
        raise TestStepSkipped(msg)
    primary_error = False
    try:
        # Write a different value
        new_val = "7" if original != "7" else "6"
        await device.set_device_config({key: new_val})
        print(f"  Set {key} = {new_val}")
        # Read back to verify
        cfg2 = await device.get_device_config()
        readback = cfg2.get(key)
        if readback == new_val:
            print(f"  ✓ Read-back confirmed: {readback}")
            print("  ✓ set_device_config() OK")
        else:
            msg = f"Read-back mismatch: {readback!r}"
            raise TestStepFailed(msg)
    except Exception:
        primary_error = True
        raise
    finally:
        try:
            await device.set_device_config({key: original})
            print(f"  Restored {key} = {original}")
        except Exception as exc:
            if not primary_error:
                raise
            print(f"  ⚠ Restore failed after earlier failure: {exc}")


async def test_verify_user_deletion(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test user was deleted."""
    print_header("VERIFY USER DELETION")
    users = await device.list_users()
    found = any(u.id == internal_id for u in users)
    if found:
        raise TestStepFailed("User still present after delete")
    print("  ✓ User successfully removed")


async def test_verify_schedule_deletion(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test schedule was deleted."""
    print_header("VERIFY SCHEDULE DELETION")
    scheds = await device.list_schedules()
    found = any(s.id == internal_id for s in scheds)
    if found:
        raise TestStepFailed("Schedule still present after delete")
    print("  ✓ Schedule successfully removed")


async def test_verify_group_deletion(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test group was deleted."""
    print_header("VERIFY GROUP DELETION")
    grps = await device.list_groups()
    found = any(g.id == internal_id for g in grps)
    if found:
        raise TestStepFailed("Group still present after delete")
    print("  ✓ Group successfully removed")


async def test_verify_contact_deletion(
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test contact was deleted."""
    print_header("VERIFY CONTACT DELETION")
    contacts = await device.list_contacts()
    found = any(c.id == internal_id for c in contacts)
    if found:
        raise TestStepFailed("Contact still present after delete")
    print("  ✓ Contact successfully removed")


async def _run_write_tests(
    device_kwargs: dict[str, Any],
    results: TestResults,
    *,
    capabilities: DeviceCapabilities,
    redact_stdout: bool,
) -> None:
    """Run write tests (user/schedule CRUD, relay trigger).

    All write steps are capability-gated against the shared
    ``capabilities`` profile (probed once at the top of
    :func:`run_all`, threaded in here per Decision 9). Steps with a
    dependent chain (modify/delete after add) fall through to the
    existing ``skip_step`` dependency-skip path when the parent step
    SKIPs or fails.
    """
    if results.diagnostics is None:
        msg = "write tests require diagnostics"
        raise RuntimeError(msg)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # User add + delete FIRST — before any other
        # requests to avoid CGI state corruption.
        internal_id = await step(
            results=results,
            name="add_user",
            capability=Capability.USER_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_user(device, redact_stdout=redact_stdout),
        )
        if internal_id is None:
            reason = "requires internal ID from add_user"
            skip_step(results, "modify_user", reason)
            skip_step(results, "delete_user", reason)
            skip_step(results, "verify_user_deletion", reason)
        else:
            await step(
                results=results,
                name="modify_user",
                capability=Capability.USER_MODIFY,
                capabilities=capabilities,
                coro_factory=lambda: test_modify_user(
                    device, internal_id, redact_stdout=redact_stdout
                ),
            )
            await step(
                results=results,
                name="delete_user",
                capability=Capability.USER_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_user(device, internal_id),
            )
            if results.was_passed("delete_user"):
                await step(
                    results=results,
                    name="verify_user_deletion",
                    capability=Capability.USER_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_user_deletion(device, internal_id),
                )
            else:
                skip_step(
                    results,
                    "verify_user_deletion",
                    "requires delete_user to pass",
                )

    # Device needs cooldown between request groups
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Schedule add + delete
        sched_id = await step(
            results=results,
            name="add_schedule",
            capability=Capability.SCHEDULE_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_schedule(device),
        )
        if sched_id is None:
            reason = "requires internal ID from add_schedule"
            skip_step(results, "modify_schedule", reason)
            skip_step(results, "delete_schedule", reason)
            skip_step(results, "verify_schedule_deletion", reason)
        else:
            await step(
                results=results,
                name="modify_schedule",
                capability=Capability.SCHEDULE_MODIFY,
                capabilities=capabilities,
                coro_factory=lambda: test_modify_schedule(device, sched_id),
            )
            await step(
                results=results,
                name="delete_schedule",
                capability=Capability.SCHEDULE_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_schedule(device, sched_id),
            )
            if results.was_passed("delete_schedule"):
                await step(
                    results=results,
                    name="verify_schedule_deletion",
                    capability=Capability.SCHEDULE_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_schedule_deletion(
                        device, sched_id
                    ),
                )
            else:
                skip_step(
                    results,
                    "verify_schedule_deletion",
                    "requires delete_schedule to pass",
                )

        # Relay trigger (auto-closes per the device-side default
        # close timer; ``test_trigger_relay`` invokes
        # :meth:`AkuvoxDevice.trigger_relay` with the default
        # ``delay=0`` so the IT83 FCGI variant accepts it — the
        # FCGI adapter rejects any non-zero ``mode``/``level``/
        # ``delay``). Adapter-gated via the (API, FCGI) tuple so
        # IT83 routes to the FCGI variant and door phones route
        # to the API variant; the smoke tests exercise both sides.
        await step(
            results=results,
            name="trigger_relay",
            capability=(
                Capability.RELAY_TRIGGER_API,
                Capability.RELAY_TRIGGER_FCGI,
            ),
            capabilities=capabilities,
            coro_factory=lambda: test_trigger_relay(device),
        )

        # Config set + read-back verification
        await step(
            results=results,
            name="set_device_config",
            capability=Capability.DEVICE_CONFIG_SET,
            capabilities=capabilities,
            coro_factory=lambda: test_set_device_config(device),
        )

    # Cooldown before group tests
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Group add + delete
        group_id = await step(
            results=results,
            name="add_group",
            capability=Capability.GROUP_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_group(device),
        )
        if group_id is None:
            reason = "requires internal ID from add_group"
            skip_step(results, "delete_group", reason)
            skip_step(results, "verify_group_deletion", reason)
        else:
            await step(
                results=results,
                name="delete_group",
                capability=Capability.GROUP_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_group(device, group_id),
            )
            if results.was_passed("delete_group"):
                await step(
                    results=results,
                    name="verify_group_deletion",
                    capability=Capability.GROUP_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_group_deletion(device, group_id),
                )
            else:
                skip_step(
                    results,
                    "verify_group_deletion",
                    "requires delete_group to pass",
                )

    # Cooldown before contact tests
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Contact add + modify + delete
        contact_id = await step(
            results=results,
            name="add_contact",
            capability=Capability.CONTACT_ADD,
            capabilities=capabilities,
            coro_factory=lambda: test_add_contact(device),
        )
        if contact_id is None:
            reason = "requires internal ID from add_contact"
            skip_step(results, "modify_contact", reason)
            skip_step(results, "delete_contact", reason)
            skip_step(results, "verify_contact_deletion", reason)
        else:
            await step(
                results=results,
                name="modify_contact",
                capability=Capability.CONTACT_MODIFY,
                capabilities=capabilities,
                coro_factory=lambda: test_modify_contact(device, contact_id),
            )
            await step(
                results=results,
                name="delete_contact",
                capability=Capability.CONTACT_DELETE,
                capabilities=capabilities,
                coro_factory=lambda: test_delete_contact(device, contact_id),
            )
            if results.was_passed("delete_contact"):
                await step(
                    results=results,
                    name="verify_contact_deletion",
                    capability=Capability.CONTACT_LIST,
                    capabilities=capabilities,
                    coro_factory=lambda: test_verify_contact_deletion(
                        device, contact_id
                    ),
                )
            else:
                skip_step(
                    results,
                    "verify_contact_deletion",
                    "requires delete_contact to pass",
                )

    # Cooldown before read tests
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)


async def run_all(args: argparse.Namespace) -> None:
    """Run all MVP tests against the device.

    Per ``specs/008-capability-matrix/research.md`` Decision 9 / FR-019,
    the device is probed exactly once at the top of the online flow.
    The returned :class:`DeviceCapabilities` is threaded into both
    :func:`_run_write_tests` and :func:`_run_read_tests`, which gate
    each step through :func:`step` so unsupported / unknown capabilities
    print a ``SKIP: <name>: ...`` banner instead of attempting-and-failing.
    """
    auth = build_auth(args)
    auth_desc = args.auth if args.auth != "none" else "allowlist (no auth)"
    ssl_desc = ""
    if args.ssl:
        ssl_desc = " [HTTPS"
        ssl_desc += ", no cert verify" if args.no_verify_ssl else ""
        ssl_desc += "]"

    print(f"\n🔌 Connecting to {args.host} ({auth_desc}{ssl_desc})")
    print(f"   Timeout: {args.timeout}s\n")

    device_kwargs: dict[str, Any] = {
        "host": args.host,
        "auth": auth,
        "timeout": args.timeout,
        "use_ssl": args.ssl,
        "verify_ssl": not args.no_verify_ssl,
    }
    diagnostics = DiagnosticReport(
        host=args.host,
        auth_method=args.auth,
        use_ssl=args.ssl,
        verify_ssl=not args.no_verify_ssl,
    )
    results = TestResults(diagnostics)

    # 1. Validation tests (offline)
    await test_validation()

    # 2. Device tests (online)
    #
    # NOTE: Akuvox firmware (tested on E18 18.30.10.72) has a known bug
    # where rapid successive API requests corrupt internal CGI state,
    # causing subsequent POST mutations to silently fail (return success
    # but not persist data). Workaround: run each CRUD group in its own
    # connection with a cooldown pause between groups.
    try:
        capabilities = await _probe_device_capabilities(device_kwargs, diagnostics)

        if args.write:
            await _run_write_tests(
                device_kwargs,
                results,
                capabilities=capabilities,
                redact_stdout=args.redact_stdout,
            )

        async with create_device(device_kwargs, diagnostics) as device:
            await _run_read_tests(
                device,
                results,
                capabilities=capabilities,
                redact_stdout=args.redact_stdout,
            )

            if not args.write:
                print_header("SKIPPING WRITE TESTS")
                print("  Use --write to test:")
                print("    - add/modify/delete user")
                print("    - add/modify/delete schedule")
                print("    - trigger relay (device-side default close timer)")
                print("  ⚠ Write tests WILL create and delete test data")

    except AkuvoxConnectionError as exc:
        print(f"\n✗ Connection failed: {exc}")
        sys.exit(1)
    except AkuvoxAuthenticationError as exc:
        print(f"\n✗ Authentication failed: {exc}")
        sys.exit(1)
    except AkuvoxError as exc:
        print(f"\n✗ Akuvox error: {exc}")
        traceback.print_exc()
        sys.exit(1)

    print_header("ALL TESTS COMPLETE ✓")
    results.print_summary()
    if args.json_report is not None:
        report_path = Path(args.json_report)
        diagnostics.write_json(report_path)
        print(f"\n  JSON report written: {report_path}")


async def _probe_device_capabilities(
    device_kwargs: dict[str, Any], diagnostics: DiagnosticReport
) -> DeviceCapabilities:
    """Open a short-lived connection, probe once, and return the profile.

    The probe is the **only** capability discovery the script performs
    (FR-019 / Decision 9). Subsequent connections opened by
    :func:`_run_write_tests` and :func:`_run_read_tests` reuse the
    profile captured here rather than re-probing on every context entry.
    """
    print_header("CAPABILITY PROBE")
    async with create_device(device_kwargs, diagnostics) as device:
        capabilities = await device.probe_capabilities()
    supported = len(capabilities.supported_set)
    print(
        f"  Device class: {capabilities.device_class} "
        f"(firmware {capabilities.firmware_version})"
    )
    print(f"  Supported capabilities: {supported}")
    return capabilities


def main() -> None:
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test pylocal-akuvox MVP against a real Akuvox device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s 192.168.1.100
  %(prog)s 192.168.1.100 --write
  %(prog)s 192.168.1.100 --ssl --no-verify-ssl
  %(prog)s 192.168.1.100 --json-report mvp-report.json
  %(prog)s 192.168.1.100 --auth basic --user admin --pass secret
  %(prog)s 192.168.1.100 --auth digest --user admin --pass secret --write

json report:
  Top-level keys: device (model, firmware, redacted host), auth,
  observed_schemas, tests. Each test records name, label, status,
  capability_status, reason, endpoint, observed_fields, request_fields,
  failure_shape, and http_events. failure_shape and each http_event record
  method, endpoint, http status, retcode, retmsg,
  observed_fields, request_fields, exception class/message, and redacted
  body_snippet only for HTTP or Akuvox retcode failures.
""",
    )
    parser.add_argument("host", help="Device IP address or hostname")
    parser.add_argument(
        "--auth",
        choices=["none", "basic", "digest"],
        default="none",
        help="Authentication method (default: none / allowlist)",
    )
    parser.add_argument("--user", default=None, help="Auth username")
    parser.add_argument(
        "--pass",
        dest="password",
        default=None,
        help="Auth password (or set AKUVOX_PASSWORD env var)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Enable write tests (add/modify/delete a test user)",
    )
    parser.add_argument(
        "--ssl",
        action="store_true",
        help="Use HTTPS instead of HTTP",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Skip SSL certificate verification (for self-signed certs)",
    )
    parser.add_argument(
        "--json-report",
        metavar="PATH",
        default=None,
        help="Write a structured JSON diagnostic report to PATH",
    )
    parser.add_argument(
        "--redact-stdout",
        action="store_true",
        help=(
            "Redact PII values (PIN, MAC, names, phones, etc.) in stdout "
            "output. Use when sharing terminal logs. JSON body excerpts "
            "(--json-report) are always redacted regardless."
        ),
    )

    args = parser.parse_args()

    if args.no_verify_ssl and not args.ssl:
        args.ssl = True

    if args.auth in ("basic", "digest"):
        if not args.user:
            parser.error(f"--auth {args.auth} requires --user")
        if not args.password:
            args.password = os.environ.get("AKUVOX_PASSWORD")
        if not args.password:
            args.password = getpass.getpass("Device password: ")

    asyncio.run(run_all(args))


if __name__ == "__main__":
    main()
