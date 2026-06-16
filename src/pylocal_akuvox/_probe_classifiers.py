# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Pure response classifiers for the capability probe.

Authored under spec ``010-capability-probe-split`` (issue #141). This
module owns the body-extraction, system-status summary, outcome
classification, and outcome-to-status mapping helpers. Each function
is pure — no I/O, no side effects, no mutation of arguments — so the
probe driver in :mod:`pylocal_akuvox._capability_probe` can compose
them deterministically.
"""

from __future__ import annotations

import json

from pylocal_akuvox._capability_types import CapabilityStatus
from pylocal_akuvox._probe_outcomes import (
    _ACTION_UNSUPPORTED_MARKERS,
    _API_UNSUPPORTED_MARKER,
    _NO_HANDLER_MARKERS,
    _ProbeOutcome,
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


__all__ = [
    "_classify_response",
    "_extract_message",
    "_outcome_to_status",
    "_summarise_system_status",
]
