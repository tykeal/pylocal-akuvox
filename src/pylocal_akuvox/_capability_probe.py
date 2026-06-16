# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Orchestration of the 9-call capability probe sequence.

Authored under spec ``010-capability-probe-split`` (issue #141). This
module owns the seven step-path constants, the ``_LATER_STEPS``
sequencing tuple, and the :func:`probe_capabilities` driver that
sequences the 9 read-only HTTP calls, classifies each response via
:mod:`pylocal_akuvox._probe_classifiers`, and accumulates the results
into a frozen :class:`pylocal_akuvox.DeviceCapabilities` profile.

The public consumer-facing handle is the
:meth:`pylocal_akuvox.AkuvoxDevice.probe_capabilities` method on
:class:`pylocal_akuvox.AkuvoxDevice`, which delegates to the
:func:`probe_capabilities` function defined here.

The probe issues a deterministic 9-call sequence of READ-only requests,
classifies each response with
:func:`pylocal_akuvox._probe_classifiers._classify_response`, and
returns a frozen :class:`pylocal_akuvox.DeviceCapabilities` profile.
Write capabilities are **never** inferred from read signals (FR-003);
they remain absent from the returned mapping.

Probe-derived profiles carry ``provenance=None`` (the absent provenance
is the "this came from a probe" marker) and write no wall-clock
timestamp, so two consecutive probes against an unchanged device
return profiles that compare byte-equal (SC-002 idempotence).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._capability_profile import (
    DeviceCapabilities,
    FieldAliases,
)
from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox._probe_classifiers import (
    _classify_response,
    _outcome_to_status,
    _summarise_system_status,
)
from pylocal_akuvox._probe_outcomes import _ProbeOutcome
from pylocal_akuvox._probe_parsers import (
    _record_contact_shape,
    _record_user_aliases,
    _record_user_schema_keys,
    _step_1_payload,
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

    status2, body2 = await http._request_raw(  # noqa: SLF001
        "GET", "/api/system/status", timeout=timeout
    )
    notes["system_status"] = _summarise_system_status(status2, body2)

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
