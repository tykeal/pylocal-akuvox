# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Non-destructive capability probe for Akuvox devices.

This module implements the runtime side of the capability profile
introduced in issue #123. The public surface is the module-level
helper :func:`probe_capabilities`; :class:`pylocal_akuvox.AkuvoxDevice`
exposes a thin wrapper as ``device.probe_capabilities()`` per
``contracts/probe-api.md`` §"Public surface".

The probe issues a deterministic 9-call sequence of READ-only requests,
classifies each response with :func:`_classify_response`, and returns
a frozen :class:`pylocal_akuvox.DeviceCapabilities` profile. Write
capabilities are **never** inferred from read signals (FR-003); they
remain absent from the returned mapping.

Probe-derived profiles carry ``provenance=None`` (the absent provenance
is the "this came from a probe" marker) and write no wall-clock
timestamp, so two consecutive probes against an unchanged device
return profiles that compare byte-equal (SC-002 idempotence).
"""

from __future__ import annotations

import enum
import json
from typing import TYPE_CHECKING, Any

from pylocal_akuvox.capabilities import (
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
    FieldAliases,
    SchemaShape,
)
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxParseError,
    AkuvoxRequestError,
)
from pylocal_akuvox.models import DeviceInfo

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient


class _ProbeOutcome(enum.Enum):
    """Discrete classification of a single probe-step response."""

    SUPPORTED = "supported"
    UNSUPPORTED_NO_HANDLER = "unsupported_no_handler"
    UNSUPPORTED_API = "unsupported_api"
    UNSUPPORTED_ACTION = "unsupported_action"
    INDETERMINATE = "indeterminate"


_NO_HANDLER_MARKERS = (
    "no handlers for this request",
    "no hanlders for this request",  # device typo (codespell:ignore)
)
_API_UNSUPPORTED_MARKER = "api unsupported"
_ACTION_UNSUPPORTED_MARKERS = (
    "unsupported action",
    "unsupport action",  # device typo (codespell:ignore)
)


# Step (slug, http_path, capability marker or None for step 1 / step 2)
# Step 1 is handled out-of-band (it must succeed for the probe to
# continue); step 2 is a health probe with no capability marker.
#
# IMPORTANT: the log endpoint paths match what
# :mod:`pylocal_akuvox.logs` actually calls
# (``/api/doorlog/get`` / ``/api/calllog/get``), so the
# ``LOG_DOOR`` / ``LOG_CALL`` capability classification reflects the
# endpoints the public ``AkuvoxDevice.get_door_logs`` /
# ``get_call_logs`` methods invoke. Earlier drafts of
# ``contracts/probe-api.md`` listed ``/api/log/door/get`` /
# ``/api/log/call/get`` — those paths do not exist in the library and
# would have produced misleading capability signals.
_PROBE_STEP_3_PATH = "/api/user/get?page=1"
_PROBE_STEP_4_PATH = "/api/contact/get?page=1"
_PROBE_STEP_5_PATH = "/api/schedule/get"
_PROBE_STEP_6_PATH = "/api/group/get"
_PROBE_STEP_7_PATH = "/api/doorlog/get?page=1"
_PROBE_STEP_8_PATH = "/api/calllog/get?page=1"
_PROBE_STEP_9_PATH = "/api/relay/status"

# (slug, path, capability) for steps 3-9. The slug is used as the
# stem for any ``notes["<slug>_body"]`` recording per the
# response-classification table.
_LATER_STEPS: tuple[tuple[str, str, Capability], ...] = (
    ("user_get", _PROBE_STEP_3_PATH, Capability.USER_LIST),
    ("contact_get", _PROBE_STEP_4_PATH, Capability.CONTACT_LIST),
    ("schedule_get", _PROBE_STEP_5_PATH, Capability.SCHEDULE_LIST),
    ("group_get", _PROBE_STEP_6_PATH, Capability.GROUP_LIST),
    ("doorlog_get", _PROBE_STEP_7_PATH, Capability.LOG_DOOR),
    ("calllog_get", _PROBE_STEP_8_PATH, Capability.LOG_CALL),
    ("relay_status", _PROBE_STEP_9_PATH, Capability.RELAY_STATUS),
)


def _extract_message(body: str) -> str:
    """Return the lowercased ``message`` field from ``body``, or ``""``.

    Tolerates non-JSON or non-dict bodies (returns ``""``); never
    raises. Used by :func:`_classify_response` for case-insensitive
    marker matching.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    message = payload.get("message", "")
    if not isinstance(message, str):
        return ""
    return message.lower()


def _summarise_system_status(status: int, body: str) -> str:
    """Collapse the ``/api/system/status`` response to an idempotent summary.

    The raw response payload contains wall-clock fields
    (``SystemTime`` / ``UpTime``) that drift between probes; recording
    them verbatim would break the SC-002 idempotence contract. This
    helper reduces the response to a small stable token so two probes
    against an unchanged device produce byte-equal
    :class:`DeviceCapabilities` instances.

    The token vocabulary is:

    * ``"ok"`` — HTTP 2xx with a parseable JSON envelope and integer
      ``retcode == 0``.
    * ``"retcode_<n>"`` — HTTP 2xx with a parseable JSON envelope
      whose ``retcode`` is an int but non-zero.
    * ``"unparsable"`` — HTTP 2xx whose body is not a JSON object or
      whose ``retcode`` is missing / not an integer (so the helper
      never emits awkward tokens like ``retcode_None`` or
      ``retcode_{...}``).
    * ``f"http_{status}"`` — any non-2xx response.
    """
    if not (200 <= status < 300):
        return f"http_{status}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "unparsable"
    if not isinstance(payload, dict):
        return "unparsable"
    retcode = payload.get("retcode")
    if not isinstance(retcode, int) or isinstance(retcode, bool):
        return "unparsable"
    if retcode == 0:
        return "ok"
    return f"retcode_{retcode}"


def _classify_response(status: int, body: str) -> _ProbeOutcome:
    """Classify a probe-step response per ``contracts/probe-api.md``.

    Maps the (HTTP status, raw body) tuple to a :class:`_ProbeOutcome`
    discriminator that the probe driver translates to a recorded
    :class:`pylocal_akuvox.CapabilityStatus` for the step's read marker.

    Step 1 (``/api/system/info``) handles its own auth / parse gates
    and does not call this helper. Steps 2-9 do.
    """
    if 200 <= status < 300:
        message = _extract_message(body)
        for marker in _NO_HANDLER_MARKERS:
            if marker in message:
                return _ProbeOutcome.UNSUPPORTED_NO_HANDLER
        if _API_UNSUPPORTED_MARKER in message:
            return _ProbeOutcome.UNSUPPORTED_API
        for marker in _ACTION_UNSUPPORTED_MARKERS:
            if marker in message:
                return _ProbeOutcome.UNSUPPORTED_ACTION
        # Try to read retcode for the SUPPORTED-vs-INDETERMINATE
        # discrimination. A successful read returns retcode 0; any
        # other shape (negative retcode without a recognised marker,
        # malformed envelope) is recorded as INDETERMINATE so a
        # maintainer can review the body.
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return _ProbeOutcome.INDETERMINATE
        if isinstance(payload, dict) and payload.get("retcode") == 0:
            return _ProbeOutcome.SUPPORTED
        return _ProbeOutcome.INDETERMINATE
    # Non-2xx: HTTP 4xx (other than 401/403 — those are out-of-band on
    # step 1; later-step 401/403 also classifies INDETERMINATE here)
    # and HTTP 5xx both record the body verbatim under the slug note.
    return _ProbeOutcome.INDETERMINATE


def _outcome_to_status(outcome: _ProbeOutcome) -> CapabilityStatus:
    """Map a :class:`_ProbeOutcome` to the recorded :class:`CapabilityStatus`."""
    if outcome is _ProbeOutcome.SUPPORTED:
        return CapabilityStatus.SUPPORTED
    if outcome is _ProbeOutcome.INDETERMINATE:
        return CapabilityStatus.UNKNOWN
    # All three UNSUPPORTED_* outcomes record UNSUPPORTED.
    return CapabilityStatus.UNSUPPORTED


def _step_1_payload(body: str) -> dict[str, Any]:
    """Decode and validate the ``/api/system/info`` envelope.

    Mirrors :meth:`pylocal_akuvox._http.AkuvoxHttpClient._parse_envelope`
    semantics so the probe accepts exactly what regular API calls
    accept. Returns the inner ``data`` dict. Raises
    :class:`AkuvoxParseError` (with ``__cause__`` chained for the JSON
    sub-case) on every failure mode.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        msg = "step-1 body is not valid JSON"
        raise AkuvoxParseError(msg) from exc
    if (
        not isinstance(payload, dict)
        or "retcode" not in payload
        or not isinstance(payload["retcode"], int)
    ):
        msg = f"step-1 envelope missing fields: {payload!r}"
        raise AkuvoxParseError(msg)
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return {}
    return data


def _extract_items(body: str) -> list[Any] | None:
    """Return the list of records under ``data.{Item|item}`` or ``None``.

    Real Akuvox responses have used both PascalCase ``"Item"`` (older
    firmware references in the spec contract) and lowercase ``"item"``
    (the form actually used by the rest of this library — see
    :mod:`pylocal_akuvox.users` / :mod:`pylocal_akuvox.contacts` /
    :mod:`pylocal_akuvox.logs`). The probe-side helpers accept either
    so they record observed schema details regardless of the device's
    case convention. Returns ``None`` for non-JSON bodies, non-dict
    payloads, or payloads where neither key holds a list.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None
    for key in ("Item", "item"):
        items = data.get(key)
        if isinstance(items, list):
            return items
    return None


def _record_user_aliases(field_aliases: dict[str, FieldAliases], body: str) -> None:
    """Update ``field_aliases["schedule_relay"]`` from a user-list body.

    Inspects the user records in ``data.{Item|item}`` (the standard
    list container shape — both case conventions accepted, see
    :func:`_extract_items`) for any of the three observed
    schedule-field aliases (``ScheduleRelay`` / ``Schedule-Relay`` /
    ``Schedule``) and records them in observed order. Tolerates
    malformed or minimal bodies — never raises.
    """
    items = _extract_items(body)
    if items is None:
        return

    candidates = ("ScheduleRelay", "Schedule-Relay", "Schedule")
    observed: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in candidates:
            if key in item and key not in observed:
                observed.append(key)
    if observed:
        field_aliases["schedule_relay"] = FieldAliases(
            read=tuple(observed),
            write=(),
        )


def _record_user_schema_keys(notes: dict[str, str], body: str) -> None:
    """Record observed schema-variant keys from a user-list body.

    Per ``contracts/probe-api.md`` §"Probe step sequence" row 3, the
    probe records the *presence* of ``Building`` / ``Room`` /
    ``EffectiveType`` keys on user items so a maintainer can debug
    schema variants across firmware. Records the comma-joined sorted
    list of observed keys under
    ``notes["user_schema_observed_keys"]`` (sorted to keep SC-002
    byte-equal idempotence). Accepts both ``data.Item`` and
    ``data.item`` per :func:`_extract_items`. Tolerates malformed or
    minimal bodies — never raises and writes nothing if no candidate
    key is observed.
    """
    items = _extract_items(body)
    if items is None:
        return

    candidates = ("Building", "Room", "EffectiveType")
    observed: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in candidates:
            if key in item:
                observed.add(key)
    if observed:
        notes["user_schema_observed_keys"] = ",".join(sorted(observed))


def _record_contact_shape(schema_shapes: dict[str, SchemaShape], body: str) -> None:
    """Update ``schema_shapes["contact"]`` from a contact-list body.

    Detects the apartment-book shape (the *distinctive* keys
    ``APTName`` / ``APTNum`` are unique to the apartment-book schema,
    so either of those alone is sufficient evidence; ``Building`` and
    ``Landline`` are too generic to be diagnostic on their own) vs
    the door-phone shape (every other shape — typically ``Name`` /
    ``Phone`` / ``ID``). Accepts both ``data.Item`` and ``data.item``
    per :func:`_extract_items`. Never raises on malformed input.
    """
    items = _extract_items(body)
    if not items:
        return
    first = items[0]
    if not isinstance(first, dict):
        return

    distinctive_apt_keys = {"APTName", "APTNum"}
    if any(k in first for k in distinctive_apt_keys):
        schema_shapes["contact"] = SchemaShape.APARTMENT_BOOK
    else:
        schema_shapes["contact"] = SchemaShape.DOOR_PHONE


async def probe_capabilities(
    http: AkuvoxHttpClient,
    *,
    timeout: float = 5.0,
) -> DeviceCapabilities:
    """Run a deterministic 9-call non-destructive capability probe.

    Args:
        http: The shared :class:`AkuvoxHttpClient` for the connection.
            All calls use :meth:`AkuvoxHttpClient._request_raw` so the
            classifier can see HTTP status codes and response bodies
            exactly as the wire delivered them.
        timeout: Per-request timeout in seconds (default 5.0).

    Returns:
        A new :class:`DeviceCapabilities` populated from observed
        responses. ``provenance`` is ``None``; no wall-clock timestamp
        is written into ``notes`` (preserving SC-002 byte-equal
        idempotence across consecutive runs).

    Raises:
        AkuvoxAuthenticationError: HTTP 401 on step 1
            (``/api/system/info``). The probe aborts cleanly after
            exactly 1 call.
        AkuvoxRequestError: HTTP 403 on step 1. Treated as
            insufficient permissions; the probe aborts after 1 call.
        AkuvoxConnectionError: HTTP 5xx (or HTTP 4xx other than
            401 / 403) on step 1, or any transport-level failure.
        AkuvoxParseError: Step 1 returned an unparsable body
            (invalid JSON, missing envelope fields, or a payload
            from which a :class:`DeviceInfo` cannot be constructed).

    """
    # --- Step 1: /api/system/info ---------------------------------------
    status, body = await http._request_raw(  # noqa: SLF001
        "GET", "/api/system/info", timeout=timeout
    )
    if status == 401:
        msg = "step-1 unauthenticated: /api/system/info"
        raise AkuvoxAuthenticationError(msg)
    if status == 403:
        msg = "step-1 forbidden: insufficient permissions for /api/system/info"
        raise AkuvoxRequestError(msg)
    if status >= 400:
        msg = f"step-1 returned HTTP {status}"
        raise AkuvoxConnectionError(msg)

    data = _step_1_payload(body)
    try:
        device_info = DeviceInfo.from_api_response(data)
    except (AkuvoxParseError, KeyError, TypeError, ValueError) as exc:
        msg = "step-1 DeviceInfo construction failed"
        raise AkuvoxParseError(msg) from exc

    # Buckets that the rest of the probe accumulates into. Plain dicts
    # here; DeviceCapabilities.__post_init__ wraps them in
    # MappingProxyType on construction below.
    capabilities: dict[Capability, CapabilityStatus] = {
        # Step 1 succeeded → device class is identifiable.
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    }
    field_aliases: dict[str, FieldAliases] = {}
    schema_shapes: dict[str, SchemaShape] = {}
    notes: dict[str, str] = {}

    # --- Step 2: /api/system/status (health probe; no capability) ------
    # Note: this endpoint returns a payload containing wall-clock fields
    # (``SystemTime``, ``UpTime``). Recording the raw body would break
    # the SC-002 idempotence contract — two consecutive probes against
    # the same unchanged device would produce non-equal
    # ``DeviceCapabilities`` because the timestamps drift. Instead,
    # collapse the response to a stable summary: ``"ok"`` for a healthy
    # 2xx + ``retcode == 0``, ``f"http_{status}"`` for any other HTTP
    # status, ``"unparsable"`` if the 2xx body is not valid JSON, and
    # ``"retcode_<n>"`` for a 2xx envelope with a non-zero retcode.
    status2, body2 = await http._request_raw(  # noqa: SLF001
        "GET", "/api/system/status", timeout=timeout
    )
    notes["system_status"] = _summarise_system_status(status2, body2)

    # --- Steps 3-9: read endpoints with capability markers --------------
    for slug, path, capability in _LATER_STEPS:
        step_status, step_body = await http._request_raw(  # noqa: SLF001
            "GET", path, timeout=timeout
        )

        if step_status == 401 or step_status == 403:
            # Later-step 401/403 records UNKNOWN and continues.
            capabilities[capability] = CapabilityStatus.UNKNOWN
            notes[f"{slug}_body"] = f"{step_status}: {step_body}"
            continue

        outcome = _classify_response(step_status, step_body)
        recorded = _outcome_to_status(outcome)
        capabilities[capability] = recorded
        # Record the raw body for any non-SUPPORTED outcome so a
        # maintainer can review.
        if outcome is not _ProbeOutcome.SUPPORTED:
            notes[f"{slug}_body"] = f"{step_status}: {step_body}"

        # Step-specific side effects beyond the capability marker:
        if path == _PROBE_STEP_3_PATH and outcome is _ProbeOutcome.SUPPORTED:
            _record_user_aliases(field_aliases, step_body)
            _record_user_schema_keys(notes, step_body)
        if path == _PROBE_STEP_4_PATH and outcome is _ProbeOutcome.SUPPORTED:
            _record_contact_shape(schema_shapes, step_body)

    return DeviceCapabilities(
        device_class=device_info.model,
        firmware_version=device_info.firmware_version,
        capabilities=capabilities,
        field_aliases=field_aliases,
        schema_shapes=schema_shapes,
        notes=notes,
        provenance=None,
    )


__all__ = [
    "probe_capabilities",
]
