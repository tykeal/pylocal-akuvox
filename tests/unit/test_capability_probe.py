# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the capability probe (capability profile runtime side).

Covers tasks T014, T015, T015a, T016, T024 and T025 from
``specs/008-capability-matrix/tasks.md``. The contracts driving these
tests are ``contracts/probe-api.md`` (probe step sequence, response
classification, idempotence, no-write-inference) plus the
``unsupported-action`` recording rules.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox._capability_probe import probe_capabilities as _probe_helper
from pylocal_akuvox._capability_types import (
    Capability,
    CapabilityStatus,
    SchemaShape,
)
from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxParseError,
    AkuvoxRequestError,
)

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import (
        DeviceCapabilities,
        FieldAliases,
    )

BASE_URL = "http://192.168.1.100"


def _make_probe_client(timeout: int = 5) -> AkuvoxHttpClient:
    """Build an AkuvoxHttpClient for direct probe-helper testing.

    Phase 2 changed ``AkuvoxDevice.__aenter__`` to issue its own
    ``/api/system/info`` call before the integrator can call
    :meth:`AkuvoxDevice.probe_capabilities`. The probe contract
    (``contracts/probe-api.md``) is about the helper itself, so probe
    tests exercise the helper directly against a bare HTTP client to
    keep their per-test request log focused on probe traffic.
    """
    return AkuvoxHttpClient(host="192.168.1.100", timeout=timeout, request_delay=0.0)


# A complete X916-shaped /api/system/info payload that DeviceInfo.from_api_response
# can parse without raising.
_X916_SYSTEM_INFO_BODY = {
    "retcode": 0,
    "message": "ok",
    "data": {
        "Status": {
            "Model": "X916S",
            "MAC": "00:11:22:33:44:55",
            "FirmwareVersion": "916.30.10.114",
            "HardwareVersion": "1.0",
            "Uptime": "0d",
            "WebLang": "0",
        }
    },
}

_OK_ENVELOPE = {"retcode": 0, "message": "ok", "data": {}}


def _ok(extra_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a successful retcode:0 envelope with optional extra data."""
    body = {"retcode": 0, "message": "ok", "data": extra_data or {}}
    return body


def _register_x916_probe_with_step3(
    m: aioresponses, step3_payload: dict[str, Any], step3_status: int = 200
) -> None:
    """Register all 9 probe URLs, with /api/user/get?page=1 overridden."""
    m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
    m.get(f"{BASE_URL}/api/system/status", payload=_ok())
    m.get(
        f"{BASE_URL}/api/user/get?page=1",
        payload=step3_payload,
        status=step3_status,
    )
    m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
    m.get(f"{BASE_URL}/api/group/get", payload=_ok())
    m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/relay/status", payload=_ok())


def _register_x916_probe_with_step4(
    m: aioresponses, step4_payload: dict[str, Any]
) -> None:
    """Register all 9 probe URLs, with /api/contact/get?page=1 overridden."""
    m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
    m.get(f"{BASE_URL}/api/system/status", payload=_ok())
    m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/contact/get?page=1", payload=step4_payload)
    m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
    m.get(f"{BASE_URL}/api/group/get", payload=_ok())
    m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/relay/status", payload=_ok())


# Each probe step's URL, in declared order. The probe MUST issue these in
# this exact order for the non-destructive contract test.
_PROBE_URLS = (
    "/api/system/info",
    "/api/system/status",
    "/api/user/get?page=1",
    "/api/contact/get?page=1",
    "/api/schedule/get",
    "/api/group/get",
    "/api/doorlog/get?page=1",
    "/api/calllog/get?page=1",
    "/api/relay/status",
)


def _register_full_x916_probe(m: aioresponses) -> None:
    """Register all 9 probe URLs against an aioresponses mock as success."""
    m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
    m.get(f"{BASE_URL}/api/system/status", payload=_ok())
    m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
    m.get(f"{BASE_URL}/api/group/get", payload=_ok())
    m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
    m.get(f"{BASE_URL}/api/relay/status", payload=_ok())


def _request_paths(m: aioresponses) -> list[str]:
    """Extract the list of request paths from the aioresponses request log."""
    paths: list[str] = []
    for (_method, url), _calls in m.requests.items():
        # Each (method, url) → list[RequestCall]; one per call.
        for _ in _calls:
            # url is a yarl.URL. Build "<path>[?<query>]" for assertion.
            path_with_q = url.path_qs
            paths.append(path_with_q)
    return paths


# ---------------------------------------------------------------------------
# T014: probe step-sequence + non-destructive guarantee.
# Test function MUST be named test_probe_is_non_destructive (quickstart §1).
# ---------------------------------------------------------------------------


_DESTRUCTIVE_PATTERNS = re.compile(r"/(add|set|del|trig)|action=OpenDoor")


async def test_probe_is_non_destructive() -> None:
    """Probe issues 9 GETs in order and never any destructive request.

    Covers ``contracts/probe-api.md`` §"Probe step sequence" + §"Non-
    destructive guarantee" and SC-001.
    """
    # --- (a) full success path ------------------------------------------
    client = _make_probe_client()
    with aioresponses() as m:
        _register_full_x916_probe(m)
        async with client:
            profile = await _probe_helper(client)

        log = _request_paths(m)
        # Exactly 9 requests, in the documented declared order.
        assert len(log) == 9
        assert log == list(_PROBE_URLS)
        # No destructive URL in the log.
        for entry in log:
            assert not _DESTRUCTIVE_PATTERNS.search(entry), (
                f"destructive URL in probe log: {entry}"
            )
    assert profile.device_class == "X916S"

    # --- (b) step-1 401 aborts after 1 call -----------------------------
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=401, body="Unauthorized")
        async with client:
            with pytest.raises(AkuvoxAuthenticationError):
                await _probe_helper(client)
        log = _request_paths(m)
        assert len(log) == 1
        assert log == ["/api/system/info"]

    # --- (c) step-1 403 aborts after 1 call -----------------------------
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=403, body="Forbidden")
        async with client:
            with pytest.raises(AkuvoxRequestError) as excinfo:
                await _probe_helper(client)
        assert (
            "permissions" in str(excinfo.value).lower()
            or "forbidden" in str(excinfo.value).lower()
        )
        log = _request_paths(m)
        assert len(log) == 1
        assert log == ["/api/system/info"]

    # --- (d) later-step 401 records UNKNOWN and continues ---------------
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        m.get(f"{BASE_URL}/api/system/status", payload=_ok())
        m.get(f"{BASE_URL}/api/user/get?page=1", status=401, body="Unauthorized")
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
        m.get(f"{BASE_URL}/api/group/get", payload=_ok())
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/relay/status", payload=_ok())
        async with client:
            profile = await _probe_helper(client)
        log = _request_paths(m)
        assert len(log) == 9
    assert profile.status_of(Capability.USER_LIST) is CapabilityStatus.UNKNOWN
    assert "401" in profile.notes["user_get_body"]

    # later-step 403 → also UNKNOWN + continue
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        m.get(f"{BASE_URL}/api/system/status", payload=_ok())
        m.get(f"{BASE_URL}/api/user/get?page=1", status=403, body="Forbidden")
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
        m.get(f"{BASE_URL}/api/group/get", payload=_ok())
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/relay/status", payload=_ok())
        async with client:
            profile = await _probe_helper(client)
        log = _request_paths(m)
        assert len(log) == 9
    assert profile.status_of(Capability.USER_LIST) is CapabilityStatus.UNKNOWN
    assert "403" in profile.notes["user_get_body"]


async def test_probe_step_1_invalid_json_raises_parse_error_after_one_call() -> None:
    """Step-1 d1: invalid JSON → AkuvoxParseError, exactly 1 call (T014.d1)."""
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", body="<html>nope</html>", status=200)
        async with client:
            with pytest.raises(AkuvoxParseError) as excinfo:
                await _probe_helper(client)
        assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)
        log = _request_paths(m)
        assert len(log) == 1


async def test_probe_step_1_envelope_missing_fields_raises_parse_error() -> None:
    """Step-1 d2: malformed envelope → AkuvoxParseError, 1 call (T014.d2)."""
    client = _make_probe_client()
    with aioresponses() as m:
        # JSON list (not dict) → envelope check fails.
        m.get(f"{BASE_URL}/api/system/info", payload=[], status=200)
        async with client:
            with pytest.raises(AkuvoxParseError) as excinfo:
                await _probe_helper(client)
        assert "envelope" in str(excinfo.value).lower()
        log = _request_paths(m)
        assert len(log) == 1

    # JSON dict missing 'retcode' key → also envelope-malformed.
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload={"foo": "bar"}, status=200)
        async with client:
            with pytest.raises(AkuvoxParseError) as excinfo:
                await _probe_helper(client)
        assert "envelope" in str(excinfo.value).lower()

    # JSON dict with non-int retcode → also envelope-malformed.
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"retcode": "zero"},
            status=200,
        )
        async with client:
            with pytest.raises(AkuvoxParseError) as excinfo:
                await _probe_helper(client)
        assert "envelope" in str(excinfo.value).lower()


async def test_probe_step_1_device_info_construction_fails() -> None:
    """Step-1 d3: valid envelope but missing DeviceInfo fields (T014.d3)."""
    client = _make_probe_client()
    with aioresponses() as m:
        # Envelope is valid; data is empty → DeviceInfo.from_api_response raises.
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"retcode": 0, "data": {}},
            status=200,
        )
        async with client:
            with pytest.raises(AkuvoxParseError) as excinfo:
                await _probe_helper(client)
        assert "DeviceInfo" in str(excinfo.value)
        # Cause should be the AkuvoxParseError raised by DeviceInfo.from_api_response.
        assert isinstance(excinfo.value.__cause__, AkuvoxParseError)
        log = _request_paths(m)
        assert len(log) == 1


# ---------------------------------------------------------------------------
# T015: response classification (parametrised).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "status", "expected_status"),
    [
        (_ok(), 200, CapabilityStatus.SUPPORTED),
        (
            {"retcode": -1, "message": "No handlers for this request"},
            200,
            CapabilityStatus.UNSUPPORTED,
        ),
        (
            {"retcode": -1, "message": "No hanlders for this request"},  # noqa: E501  device typo (codespell:ignore)
            200,
            CapabilityStatus.UNSUPPORTED,
        ),
        (
            {"retcode": 200, "message": "Api unsupported"},
            200,
            CapabilityStatus.UNSUPPORTED,
        ),
    ],
)
async def test_probe_classification_table_for_user_list(
    payload: dict[str, Any], status: int, expected_status: CapabilityStatus
) -> None:
    """Each classification-table row maps to the expected CapabilityStatus."""
    client = _make_probe_client()
    with aioresponses() as m:
        _register_x916_probe_with_step3(m, payload, step3_status=status)
        async with client:
            profile = await _probe_helper(client)
    assert profile.status_of(Capability.USER_LIST) is expected_status


async def test_probe_records_unsupported_action_on_contact_get() -> None:
    """``unsupported action`` on /api/contact/get → CONTACT_LIST=UNSUPPORTED.

    Validates the per-endpoint note recording AND the strict
    no-write-inference rule (T015 + T024 + T016 contact-domain branch).
    """
    for marker in ("unsupported action", "unsupport action"):  # noqa: E501  device typo (codespell:ignore)
        body = {"retcode": -1, "message": marker}
        client = _make_probe_client()
        with aioresponses() as m:
            _register_x916_probe_with_step4(m, body)
            async with client:
                profile = await _probe_helper(client)

        assert (
            profile.status_of(Capability.CONTACT_LIST) is CapabilityStatus.UNSUPPORTED
        )
        # raw body recorded under contact_get_body
        assert marker in profile.notes["contact_get_body"]
        # No write capability inferred from the read signal.
        assert Capability.CONTACT_ADD not in profile.capabilities
        assert Capability.CONTACT_MODIFY not in profile.capabilities
        assert Capability.CONTACT_DELETE not in profile.capabilities
        assert profile.status_of(Capability.CONTACT_ADD) is CapabilityStatus.UNKNOWN
        assert profile.status_of(Capability.CONTACT_MODIFY) is CapabilityStatus.UNKNOWN
        assert profile.status_of(Capability.CONTACT_DELETE) is CapabilityStatus.UNKNOWN


async def test_probe_records_unsupported_action_on_user_get_no_write_inference() -> (
    None
):
    """``unsupported action`` on /api/user/get does NOT promote USER_ADD.

    Locks the FR-003 strict no-write-inference rule on the user domain
    (T024 / BLOCKER-3).
    """
    for marker in ("unsupported action", "unsupport action"):  # noqa: E501  device typo (codespell:ignore)
        body = {"retcode": -1, "message": marker}
        client = _make_probe_client()
        with aioresponses() as m:
            _register_x916_probe_with_step3(m, body)
            async with client:
                profile = await _probe_helper(client)
        assert profile.status_of(Capability.USER_LIST) is CapabilityStatus.UNSUPPORTED
        for cap in (
            Capability.USER_ADD,
            Capability.USER_MODIFY,
            Capability.USER_DELETE,
        ):
            assert cap not in profile.capabilities
            assert profile.status_of(cap) is CapabilityStatus.UNKNOWN


async def test_probe_records_http_500_on_user_get_as_unknown_with_note() -> None:
    """HTTP 500 on /api/user/get → USER_LIST=UNKNOWN + raw body note."""
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        m.get(f"{BASE_URL}/api/system/status", payload=_ok())
        m.get(f"{BASE_URL}/api/user/get?page=1", status=500, body="server-down")
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
        m.get(f"{BASE_URL}/api/group/get", payload=_ok())
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/relay/status", payload=_ok())
        async with client:
            profile = await _probe_helper(client)
    assert profile.status_of(Capability.USER_LIST) is CapabilityStatus.UNKNOWN
    assert "user_get_body" in profile.notes
    assert "500" in profile.notes["user_get_body"]


async def test_probe_records_http_4xx_other_on_later_step_as_unknown() -> None:
    """HTTP 4xx (other than 401/403) on later step → UNKNOWN + note."""
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        m.get(f"{BASE_URL}/api/system/status", payload=_ok())
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
        m.get(f"{BASE_URL}/api/group/get", payload=_ok())
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/relay/status", status=404, body="not-found")
        async with client:
            profile = await _probe_helper(client)
    assert profile.status_of(Capability.RELAY_STATUS) is CapabilityStatus.UNKNOWN
    assert "404" in profile.notes["relay_status_body"]


# ---------------------------------------------------------------------------
# T015a: probe records observed field_aliases and schema_shapes.
# ---------------------------------------------------------------------------


async def test_probe_records_schedule_relay_field_alias_e18c_style() -> None:
    """E18C-style 'Schedule-Relay' key recorded in field_aliases."""
    client = _make_probe_client()
    user_body = _ok({"Item": [{"ID": 1, "Name": "alice", "Schedule-Relay": "1"}]})
    with aioresponses() as m:
        _register_x916_probe_with_step3(m, user_body)
        async with client:
            profile = await _probe_helper(client)
    aliases = profile.field_aliases["schedule_relay"]
    assert "Schedule-Relay" in aliases.read
    assert aliases.read[0] == "Schedule-Relay"


async def test_probe_records_schedule_relay_field_alias_x915s_style() -> None:
    """X915S-style 'Schedule' key recorded in field_aliases."""
    client = _make_probe_client()
    user_body = _ok({"Item": [{"ID": 1, "Name": "alice", "Schedule": "1"}]})
    with aioresponses() as m:
        _register_x916_probe_with_step3(m, user_body)
        async with client:
            profile = await _probe_helper(client)
    assert profile.field_aliases["schedule_relay"].read == ("Schedule",)


async def test_probe_records_apartment_book_schema_shape() -> None:
    """Apartment-book contact body → schema_shapes['contact']=APARTMENT_BOOK."""
    client = _make_probe_client()
    contact_body = _ok(
        {
            "Item": [
                {
                    "APTName": "Tower 1",
                    "APTNum": "101",
                    "Building": "A",
                    "Landline": "555-0100",
                }
            ]
        }
    )
    with aioresponses() as m:
        _register_x916_probe_with_step4(m, contact_body)
        async with client:
            profile = await _probe_helper(client)
    assert profile.schema_shapes["contact"] is SchemaShape.APARTMENT_BOOK


async def test_probe_records_door_phone_schema_shape() -> None:
    """Door-phone contact body → schema_shapes['contact']=DOOR_PHONE."""
    client = _make_probe_client()
    contact_body = _ok({"Item": [{"Name": "alice", "Phone": "555-0100", "ID": 1}]})
    with aioresponses() as m:
        _register_x916_probe_with_step4(m, contact_body)
        async with client:
            profile = await _probe_helper(client)
    assert profile.schema_shapes["contact"] is SchemaShape.DOOR_PHONE


# ---------------------------------------------------------------------------
# T016: idempotence + no-write-inference.
# Test function MUST be named test_probe_is_idempotent (quickstart §2).
# ---------------------------------------------------------------------------


async def test_probe_is_idempotent() -> None:
    """Two consecutive probes against the same mock produce equal profiles."""
    client = _make_probe_client()
    with aioresponses() as m:
        # Repeat=True so the same fixtures match every probe step in
        # both runs.
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_X916_SYSTEM_INFO_BODY,
            repeat=True,
        )
        m.get(f"{BASE_URL}/api/system/status", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/group/get", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok(), repeat=True)
        m.get(f"{BASE_URL}/api/relay/status", payload=_ok(), repeat=True)
        async with client:
            a = await _probe_helper(client)
            b = await _probe_helper(client)

    # The profiles compare exactly equal (no per-field normalisation).
    assert a == b
    # Provenance is None for probe-derived profiles (no timestamp).
    assert a.provenance is None
    assert b.provenance is None


async def test_probe_does_not_infer_any_write_capability_on_x916() -> None:
    """Fully-responsive X916 → every write capability absent from the profile."""
    client = _make_probe_client()
    with aioresponses() as m:
        _register_full_x916_probe(m)
        async with client:
            profile = await _probe_helper(client)

    write_caps = (
        Capability.USER_ADD,
        Capability.USER_MODIFY,
        Capability.USER_DELETE,
        Capability.CONTACT_ADD,
        Capability.CONTACT_MODIFY,
        Capability.CONTACT_DELETE,
        Capability.SCHEDULE_ADD,
        Capability.SCHEDULE_MODIFY,
        Capability.SCHEDULE_DELETE,
        Capability.GROUP_ADD,
        Capability.GROUP_MODIFY,
        Capability.GROUP_DELETE,
        Capability.RELAY_TRIGGER_API,
        Capability.RELAY_TRIGGER_FCGI,
        Capability.DEVICE_CONFIG_SET,
    )
    for cap in write_caps:
        assert cap not in profile.capabilities, f"{cap.name} unexpectedly inferred"
        assert profile.status_of(cap) is CapabilityStatus.UNKNOWN


async def test_probe_transport_refused_during_step_4_raises_no_partial() -> None:
    """Transport refusal during step 4 → AkuvoxConnectionError, no profile.

    Covers ``contracts/probe-api.md`` Edge case 5: probe aborts and no
    partial DeviceCapabilities is returned.
    """
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        m.get(f"{BASE_URL}/api/system/status", payload=_ok())
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok())
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            exception=aiohttp.ClientError("Connection refused"),
        )
        async with client:
            with pytest.raises(AkuvoxConnectionError):
                await _probe_helper(client)


# ---------------------------------------------------------------------------
# T025: step-1 transport / HTTP edge cases — additional propagation.
# ---------------------------------------------------------------------------


async def test_probe_step_1_http_500_raises_connection_error() -> None:
    """Step-1 HTTP 500 → AkuvoxConnectionError, abort after 1 call."""
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=500, body="boom")
        async with client:
            with pytest.raises(AkuvoxConnectionError) as excinfo:
                await _probe_helper(client)
        assert "500" in str(excinfo.value)
        log = _request_paths(m)
        assert len(log) == 1


async def test_probe_step_1_http_404_raises_connection_error() -> None:
    """Step-1 HTTP 404 (4xx other than 401/403) → AkuvoxConnectionError."""
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=404, body="missing")
        async with client:
            with pytest.raises(AkuvoxConnectionError) as excinfo:
                await _probe_helper(client)
        assert "404" in str(excinfo.value)


async def test_probe_step_1_transport_failure_raises_connection_error() -> None:
    """Transport-level failure on step 1 → AkuvoxConnectionError."""
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=aiohttp.ClientError("refused"),
        )
        async with client:
            with pytest.raises(AkuvoxConnectionError):
                await _probe_helper(client)


async def test_probe_step_1_payload_data_not_dict_treated_as_empty() -> None:
    """Step-1 valid envelope but data is not a dict → treated as empty.

    DeviceInfo.from_api_response raises AkuvoxParseError on the empty
    dict (no 'Status' field), which the probe wraps. Confirms the
    payload coercion path on lines around _step_1_payload.
    """
    client = _make_probe_client()
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"retcode": 0, "data": "not-a-dict"},
            status=200,
        )
        async with client:
            with pytest.raises(AkuvoxParseError):
                await _probe_helper(client)


def test_step_1_payload_rejects_bool_retcode() -> None:
    """Step-1 envelope with bool ``retcode`` (``True`` / ``False``) is rejected.

    ``bool`` is a subclass of ``int`` in Python, so a naïve
    ``isinstance(retcode, int)`` lets ``{"retcode": true}`` through.
    The probe explicitly rejects it for consistency with
    :func:`_summarise_system_status` step-2 handling.
    """
    from pylocal_akuvox._probe_parsers import _step_1_payload

    with pytest.raises(AkuvoxParseError):
        _step_1_payload('{"retcode": true, "data": {}}')
    with pytest.raises(AkuvoxParseError):
        _step_1_payload('{"retcode": false, "data": {}}')


async def test_probe_step_3_aliases_recorded_in_observed_order() -> None:
    """Multiple alias keys in user list recorded in the order observed."""
    client = _make_probe_client()
    user_body = _ok(
        {
            "Item": [
                {"ScheduleRelay": "1"},
                {"Schedule-Relay": "2"},
                {"Schedule": "3"},
                # Duplicate later — should not double-record.
                {"ScheduleRelay": "4"},
            ]
        }
    )
    with aioresponses() as m:
        _register_x916_probe_with_step3(m, user_body)
        async with client:
            profile = await _probe_helper(client)
    assert profile.field_aliases["schedule_relay"].read == (
        "ScheduleRelay",
        "Schedule-Relay",
        "Schedule",
    )


async def test_probe_step_3_no_recognised_keys_no_alias_entry() -> None:
    """User-list with no schedule keys → no field_aliases entry."""
    client = _make_probe_client()
    user_body = _ok({"Item": [{"ID": 1, "Name": "alice"}]})
    with aioresponses() as m:
        _register_x916_probe_with_step3(m, user_body)
        async with client:
            profile = await _probe_helper(client)
    assert "schedule_relay" not in profile.field_aliases


async def test_probe_step_4_empty_item_list_no_shape_entry() -> None:
    """Contact-list with empty Item → no schema_shapes entry."""
    client = _make_probe_client()
    contact_body = _ok({"Item": []})
    with aioresponses() as m:
        _register_x916_probe_with_step4(m, contact_body)
        async with client:
            profile = await _probe_helper(client)
    assert "contact" not in profile.schema_shapes


# ---------------------------------------------------------------------------
# Direct unit tests for module helpers (defensive paths). The probe
# integration tests above exercise the happy paths; these target the
# malformed-body branches in _extract_message, _classify_response,
# _record_user_aliases, and _record_contact_shape.
# ---------------------------------------------------------------------------


def test_classify_response_non_json_body_returns_indeterminate() -> None:
    """200 + non-JSON body falls through to INDETERMINATE."""
    from pylocal_akuvox._probe_classifiers import _classify_response
    from pylocal_akuvox._probe_outcomes import _ProbeOutcome

    assert _classify_response(200, "<html>notjson</html>") is (
        _ProbeOutcome.INDETERMINATE
    )


def test_classify_response_negative_retcode_no_marker_returns_indeterminate() -> None:
    """200 + retcode=-1 + no recognised marker → INDETERMINATE."""
    from pylocal_akuvox._probe_classifiers import _classify_response
    from pylocal_akuvox._probe_outcomes import _ProbeOutcome

    body = '{"retcode": -1, "message": "something else"}'
    assert _classify_response(200, body) is _ProbeOutcome.INDETERMINATE


def test_classify_response_message_field_not_a_string() -> None:
    """200 + non-string message field doesn't crash; treated as no marker."""
    from pylocal_akuvox._probe_classifiers import _classify_response
    from pylocal_akuvox._probe_outcomes import _ProbeOutcome

    body = '{"retcode": -1, "message": 42}'
    # message coerced to "" by _extract_message; body has no recognised
    # marker; retcode is -1 so SUPPORTED is not chosen → INDETERMINATE.
    assert _classify_response(200, body) is _ProbeOutcome.INDETERMINATE


def test_classify_response_payload_is_list_returns_indeterminate() -> None:
    """200 + JSON list (not dict) → INDETERMINATE."""
    from pylocal_akuvox._probe_classifiers import _classify_response
    from pylocal_akuvox._probe_outcomes import _ProbeOutcome

    assert _classify_response(200, "[1, 2, 3]") is _ProbeOutcome.INDETERMINATE


def test_record_user_aliases_tolerates_non_json_body() -> None:
    """Non-JSON body silently leaves the aliases dict unchanged."""
    from pylocal_akuvox._probe_parsers import _record_user_aliases

    aliases: dict[str, FieldAliases] = {}
    _record_user_aliases(aliases, "<html>")
    assert aliases == {}


def test_record_user_aliases_tolerates_non_dict_payload() -> None:
    """JSON list payload silently leaves the aliases dict unchanged."""
    from pylocal_akuvox._probe_parsers import _record_user_aliases

    aliases: dict[str, FieldAliases] = {}
    _record_user_aliases(aliases, "[]")
    assert aliases == {}


def test_record_user_aliases_tolerates_non_dict_data_field() -> None:
    """data field that is not a dict is silently ignored."""
    from pylocal_akuvox._probe_parsers import _record_user_aliases

    aliases: dict[str, FieldAliases] = {}
    _record_user_aliases(aliases, '{"data": "not-a-dict"}')
    assert aliases == {}


def test_record_user_aliases_tolerates_non_list_item_field() -> None:
    """Item field that is not a list is silently ignored."""
    from pylocal_akuvox._probe_parsers import _record_user_aliases

    aliases: dict[str, FieldAliases] = {}
    _record_user_aliases(aliases, '{"data": {"Item": "not-a-list"}}')
    assert aliases == {}


def test_record_user_aliases_skips_non_dict_items() -> None:
    """Non-dict entries inside Item list are skipped without raising."""
    from pylocal_akuvox._probe_parsers import _record_user_aliases

    aliases: dict[str, FieldAliases] = {}
    body = json.dumps({"data": {"Item": [None, 42, {"Schedule": "1"}]}})
    _record_user_aliases(aliases, body)
    # Only the dict item contributed.
    assert aliases["schedule_relay"].read == ("Schedule",)


def test_record_contact_shape_tolerates_non_json_body() -> None:
    """Non-JSON body silently leaves the shapes dict unchanged."""
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    _record_contact_shape(shapes, "<html>")
    assert shapes == {}


def test_record_contact_shape_tolerates_non_dict_payload() -> None:
    """JSON list payload silently leaves the shapes dict unchanged."""
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    _record_contact_shape(shapes, "[]")
    assert shapes == {}


def test_record_contact_shape_tolerates_non_dict_data_field() -> None:
    """data field that is not a dict is silently ignored."""
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    _record_contact_shape(shapes, '{"data": "not-a-dict"}')
    assert shapes == {}


def test_record_contact_shape_tolerates_non_dict_first_item() -> None:
    """First Item entry that is not a dict is silently ignored."""
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    body = json.dumps({"data": {"Item": [None, {"Name": "x"}]}})
    _record_contact_shape(shapes, body)
    # First item is None → returned without recording.
    assert shapes == {}


# ---------------------------------------------------------------------------
# _extract_items helper: tolerates both PascalCase ``Item`` (as historically
# used in the spec) and lowercase ``item`` (as actually returned by Akuvox
# firmware in practice — see users.py / contacts.py / logs.py for parallel
# tolerance in the rest of the library).
# ---------------------------------------------------------------------------


def test_extract_items_returns_pascal_case_item_list() -> None:
    """Standard PascalCase ``Item`` container yields the underlying list."""
    from pylocal_akuvox._probe_parsers import _extract_items

    body = json.dumps({"data": {"Item": [{"Name": "a"}, {"Name": "b"}]}})
    items = _extract_items(body)
    assert items == [{"Name": "a"}, {"Name": "b"}]


def test_extract_items_returns_lowercase_item_list() -> None:
    """Lowercase ``item`` container is recognised (real-firmware shape)."""
    from pylocal_akuvox._probe_parsers import _extract_items

    body = json.dumps({"data": {"item": [{"Name": "a"}]}})
    items = _extract_items(body)
    assert items == [{"Name": "a"}]


def test_extract_items_prefers_pascal_case_when_both_present() -> None:
    """If both ``Item`` and ``item`` are present, ``Item`` wins (deterministic)."""
    from pylocal_akuvox._probe_parsers import _extract_items

    body = json.dumps({"data": {"Item": [{"k": "pascal"}], "item": [{"k": "lower"}]}})
    items = _extract_items(body)
    assert items == [{"k": "pascal"}]


def test_extract_items_returns_none_for_non_json_body() -> None:
    """Non-JSON body returns ``None`` (sentinel for "skip recording")."""
    from pylocal_akuvox._probe_parsers import _extract_items

    assert _extract_items("<html>not-json</html>") is None


def test_extract_items_returns_none_for_non_dict_payload() -> None:
    """JSON list at the top level returns ``None``."""
    from pylocal_akuvox._probe_parsers import _extract_items

    assert _extract_items("[1, 2, 3]") is None


def test_extract_items_returns_none_for_non_dict_data_field() -> None:
    """``data`` present but not a dict returns ``None``."""
    from pylocal_akuvox._probe_parsers import _extract_items

    assert _extract_items('{"data": "not-a-dict"}') is None


def test_extract_items_returns_none_when_no_item_key() -> None:
    """``data`` present and a dict but no ``Item``/``item`` key returns ``None``."""
    from pylocal_akuvox._probe_parsers import _extract_items

    assert _extract_items('{"data": {"other": []}}') is None


def test_extract_items_returns_none_when_item_value_is_not_list() -> None:
    """``data.Item`` present but not a list returns ``None`` (defensive)."""
    from pylocal_akuvox._probe_parsers import _extract_items

    assert _extract_items('{"data": {"Item": "not-a-list"}}') is None
    assert _extract_items('{"data": {"item": {"a": 1}}}') is None


def test_record_user_aliases_accepts_lowercase_item_key() -> None:
    """End-to-end: ``data.item`` (lowercase) populates field_aliases."""
    from pylocal_akuvox._probe_parsers import _record_user_aliases

    aliases: dict[str, FieldAliases] = {}
    body = json.dumps({"data": {"item": [{"ScheduleRelay": "1"}]}})
    _record_user_aliases(aliases, body)
    assert "schedule_relay" in aliases
    assert aliases["schedule_relay"].read == ("ScheduleRelay",)


def test_record_user_schema_keys_accepts_lowercase_item_key() -> None:
    """End-to-end: ``data.item`` (lowercase) populates schema-observed-keys."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    body = json.dumps({"data": {"item": [{"Building": "1", "Room": "101"}]}})
    _record_user_schema_keys(notes, body)
    assert notes["user_schema_observed_keys"] == "Building,Room"


def test_record_contact_shape_accepts_lowercase_item_key() -> None:
    """End-to-end: ``data.item`` (lowercase) populates schema_shapes."""
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    body = json.dumps({"data": {"item": [{"APTName": "Apt 1"}]}})
    _record_contact_shape(shapes, body)
    assert shapes["contact"] is SchemaShape.APARTMENT_BOOK


def test_record_contact_shape_classifies_door_phone_when_only_building() -> None:
    """Distinctive-key tightening: ``Building`` alone is NOT apartment-book.

    Building / Landline are too generic — door-phone schemas may carry
    them too. Only APTName / APTNum should classify as APARTMENT_BOOK
    (see :func:`_record_contact_shape` docstring).
    """
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    body = json.dumps(
        {"data": {"Item": [{"Building": "B1", "Name": "lobby", "ID": "1"}]}}
    )
    _record_contact_shape(shapes, body)
    assert shapes["contact"] is SchemaShape.DOOR_PHONE


def test_record_contact_shape_classifies_apt_book_when_aptnum_present() -> None:
    """``APTNum`` (without APTName) is sufficient evidence of apartment-book."""
    from pylocal_akuvox._probe_parsers import _record_contact_shape

    shapes: dict[str, SchemaShape] = {}
    body = json.dumps({"data": {"Item": [{"APTNum": "101"}]}})
    _record_contact_shape(shapes, body)
    assert shapes["contact"] is SchemaShape.APARTMENT_BOOK


# ---------------------------------------------------------------------------
# Step-2 system_status normalisation: the raw payload contains time-varying
# fields (SystemTime, UpTime). The probe must collapse the response to a
# stable token so SC-002 idempotence holds against real hardware.
# ---------------------------------------------------------------------------


def test_summarise_system_status_returns_ok_for_healthy_envelope() -> None:
    """200 + retcode 0 → ``"ok"`` regardless of any time-varying data fields."""
    from pylocal_akuvox._probe_classifiers import _summarise_system_status

    body_with_drifting_time = json.dumps(
        {
            "retcode": 0,
            "message": "ok",
            "data": {"SystemTime": 1700000000, "UpTime": 12345},
        }
    )
    assert _summarise_system_status(200, body_with_drifting_time) == "ok"


def test_summarise_system_status_returns_retcode_token_for_nonzero() -> None:
    """200 with retcode != 0 → ``"retcode_<n>"`` (no marker matched)."""
    from pylocal_akuvox._probe_classifiers import _summarise_system_status

    body = json.dumps({"retcode": -5, "message": "bad"})
    assert _summarise_system_status(200, body) == "retcode_-5"


def test_summarise_system_status_returns_unparsable_for_invalid_json() -> None:
    """200 + invalid JSON → ``"unparsable"``."""
    from pylocal_akuvox._probe_classifiers import _summarise_system_status

    assert _summarise_system_status(200, "<html>not-json</html>") == "unparsable"


def test_summarise_system_status_returns_unparsable_for_non_dict_payload() -> None:
    """200 + JSON list (not dict) → ``"unparsable"``."""
    from pylocal_akuvox._probe_classifiers import _summarise_system_status

    assert _summarise_system_status(200, "[1, 2, 3]") == "unparsable"


def test_summarise_system_status_returns_unparsable_for_missing_retcode() -> None:
    """200 + JSON dict without ``retcode`` → ``"unparsable"``.

    Avoids emitting awkward tokens like ``"retcode_None"`` when the
    device returns a parseable envelope that simply lacks a retcode
    field. Also covers the related case where ``retcode`` is present
    but a non-int (e.g. string) — same idempotent ``"unparsable"`` token.
    """
    from pylocal_akuvox._probe_classifiers import _summarise_system_status

    # retcode missing entirely
    assert _summarise_system_status(200, '{"data": {"status": "up"}}') == "unparsable"
    # retcode as string
    assert _summarise_system_status(200, '{"retcode": "0"}') == "unparsable"
    # retcode as bool — bool is a subclass of int but is not a valid retcode
    assert _summarise_system_status(200, '{"retcode": true}') == "unparsable"


def test_summarise_system_status_returns_http_token_for_non_2xx() -> None:
    """Non-2xx status → ``f"http_{status}"`` regardless of body content."""
    from pylocal_akuvox._probe_classifiers import _summarise_system_status

    assert _summarise_system_status(500, "Internal Server Error") == "http_500"
    assert _summarise_system_status(404, '{"retcode": 0}') == "http_404"


async def test_probe_is_idempotent_across_time_varying_system_status() -> None:
    """SC-002 regression: probes are equal even when SystemTime/UpTime drift.

    On real Akuvox hardware ``/api/system/status`` returns ``SystemTime``
    and ``UpTime`` fields that change between probes. The probe MUST
    normalise the step-2 response to a stable token so two consecutive
    probes against an unchanged device produce byte-equal
    :class:`DeviceCapabilities`.
    """
    device_a = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        # First probe sees one set of timestamps...
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "message": "ok",
                "data": {"SystemTime": 1700000000, "UpTime": 100},
            },
        )
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
        m.get(f"{BASE_URL}/api/group/get", payload=_ok())
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/relay/status", payload=_ok())
        async with device_a:
            profile_a = await _probe_helper(device_a)

    device_b = _make_probe_client()
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=_X916_SYSTEM_INFO_BODY)
        # ...second probe sees a *different* set of timestamps...
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "message": "ok",
                "data": {"SystemTime": 1700009999, "UpTime": 999999},
            },
        )
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/schedule/get", payload=_ok())
        m.get(f"{BASE_URL}/api/group/get", payload=_ok())
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=_ok())
        m.get(f"{BASE_URL}/api/relay/status", payload=_ok())
        async with device_b:
            profile_b = await _probe_helper(device_b)

    # ...yet the recorded profile must compare exactly equal.
    assert profile_a == profile_b
    # And the normalised token is the stable summary, not the raw body.
    assert profile_a.notes["system_status"] == "ok"


# ---------------------------------------------------------------------------
# Step-3 user-list schema-key recording (probe-api.md §"Probe step sequence"
# row 3): probe records observed presence of Building / Room / EffectiveType
# under notes["user_schema_observed_keys"] for maintainer debugging.
# ---------------------------------------------------------------------------


def test_record_user_schema_keys_records_observed_keys_sorted() -> None:
    """Items carrying Building/Room/EffectiveType → sorted comma-joined note."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    body = json.dumps(
        {
            "data": {
                "Item": [
                    {"ID": "1", "Building": "A", "Room": "101"},
                    {"ID": "2", "EffectiveType": "always"},
                ]
            }
        }
    )
    _record_user_schema_keys(notes, body)
    # Sorted to keep SC-002 byte-equal idempotence regardless of dict order.
    assert notes["user_schema_observed_keys"] == "Building,EffectiveType,Room"


def test_record_user_schema_keys_writes_nothing_when_no_candidate_present() -> None:
    """User items with none of the candidate keys → notes untouched."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    body = json.dumps({"data": {"Item": [{"ID": "1", "Name": "alice"}]}})
    _record_user_schema_keys(notes, body)
    assert notes == {}


def test_record_user_schema_keys_tolerates_non_json_body() -> None:
    """Non-JSON body silently leaves the notes dict unchanged."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    _record_user_schema_keys(notes, "<html>")
    assert notes == {}


def test_record_user_schema_keys_tolerates_non_dict_payload() -> None:
    """JSON list payload silently leaves the notes dict unchanged."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    _record_user_schema_keys(notes, "[]")
    assert notes == {}


def test_record_user_schema_keys_tolerates_non_dict_data_field() -> None:
    """data field that is not a dict is silently ignored."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    _record_user_schema_keys(notes, '{"data": "not-a-dict"}')
    assert notes == {}


def test_record_user_schema_keys_tolerates_non_list_item_field() -> None:
    """Item field that is not a list is silently ignored."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    _record_user_schema_keys(notes, '{"data": {"Item": "not-a-list"}}')
    assert notes == {}


def test_record_user_schema_keys_skips_non_dict_items() -> None:
    """Non-dict entries inside Item list are skipped without raising."""
    from pylocal_akuvox._probe_parsers import _record_user_schema_keys

    notes: dict[str, str] = {}
    body = json.dumps({"data": {"Item": [None, 42, {"Building": "A"}]}})
    _record_user_schema_keys(notes, body)
    # Only the dict item contributed.
    assert notes["user_schema_observed_keys"] == "Building"


# ---------------------------------------------------------------------------
# T041: 9-cell probe-vs-matrix merge contract
# ---------------------------------------------------------------------------


_X916_INFO_FOR_MERGE: dict[str, object] = {
    "retcode": 0,
    "action": "info",
    "message": "",
    "data": {
        "Status": {
            "Model": "X916",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "916.30.10.114",
            "HardwareVersion": "1.0",
        }
    },
}
_IT83_INFO_FOR_MERGE: dict[str, object] = {
    "retcode": 0,
    "action": "info",
    "message": "",
    "data": {
        "Status": {
            "Model": "IT83",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "83.30.10.4",
            "HardwareVersion": "1.0",
        }
    },
}


def _probe_only_responses(
    *, user_list_status: str, relay_status_status: str
) -> dict[str, str]:
    """Build per-endpoint mock dicts keyed by category for the merge harness.

    Each value is one of ``"S"`` (200 keyed payload), ``"U"``
    (``"No handlers"`` body), or ``"K"`` (HTTP 500). Other endpoints
    default to an unrelated 200 keyed payload so they don't accidentally
    flip the merge cell under test.
    """
    return {
        "user_list": user_list_status,
        "relay_status": relay_status_status,
    }


def _register_probe_mocks(
    m: aioresponses,
    *,
    user_list: str,
    relay_status: str,
) -> None:
    """Register a single round of the 9-call probe with the configured signals.

    Endpoints other than the two we vary return a generic 200 keyed
    payload so probe classifies them deterministically (USER_LIST and
    RELAY_STATUS are the test pivots; everything else stays
    SUPPORTED-ish so the merge cell under test isn't masked by an
    unrelated probe-UNSUPPORTED hit).
    """
    keyed_ok = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {"Item": [{"ID": "1"}], "Total": 1},
    }
    no_handlers = {
        "retcode": 0,
        "action": "get",
        "message": "No handlers for this request",
        "data": {},
    }

    def _resolve(signal: str) -> dict[str, object] | int:
        """Map a signal token to its corresponding mock payload or status."""
        if signal == "S":
            return keyed_ok
        if signal == "U":
            return no_handlers
        # signal == "K"
        return 500

    # Step 2 — health probe (always SUPPORTED for the merge harness).
    m.get(
        f"{BASE_URL}/api/system/status",
        payload={
            "retcode": 0,
            "action": "status",
            "message": "",
            "data": {"SystemTime": 1700000000, "UpTime": 86400},
        },
    )

    # User list (GET /api/user/get?page=1)
    user_response = _resolve(user_list)
    if isinstance(user_response, int):
        m.get(f"{BASE_URL}/api/user/get?page=1", status=user_response)
    else:
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=user_response)

    # Relay status (GET /api/relay/status)
    relay_response = _resolve(relay_status)
    if isinstance(relay_response, int):
        m.get(f"{BASE_URL}/api/relay/status", status=relay_response)
    else:
        m.get(f"{BASE_URL}/api/relay/status", payload=relay_response)

    # The other probe endpoints return generic keyed payloads so they
    # don't cross-contaminate the merge cell under test.
    m.get(f"{BASE_URL}/api/contact/get?page=1", payload=keyed_ok)
    m.get(f"{BASE_URL}/api/schedule/get", payload=keyed_ok)
    m.get(f"{BASE_URL}/api/group/get", payload=keyed_ok)
    m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=keyed_ok)
    m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=keyed_ok)


# Matrix-SUPPORTED row: pin to X916 USER_LIST.


@pytest.mark.parametrize(
    ("probe_signal", "expected"),
    [
        ("S", CapabilityStatus.SUPPORTED),
        ("U", CapabilityStatus.UNSUPPORTED),
        ("K", CapabilityStatus.SUPPORTED),  # matrix preserved on probe-UNKNOWN
    ],
    ids=["matrix_S_probe_S", "matrix_S_probe_U", "matrix_S_probe_K"],
)
async def test_merge_matrix_supported_x916_user_list(
    probe_signal: str, expected: CapabilityStatus
) -> None:
    """X916 USER_LIST + each probe outcome → expected merged status."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_X916_INFO_FOR_MERGE,
            repeat=True,
        )
        _register_probe_mocks(m, user_list=probe_signal, relay_status="S")
        async with AkuvoxDevice("192.168.1.100") as device:
            merged = await device.probe_capabilities()
    assert merged.status_of(Capability.USER_LIST) is expected


# Matrix-UNSUPPORTED row: pin to IT83 RELAY_STATUS.


@pytest.mark.parametrize(
    ("probe_signal", "expected"),
    [
        ("S", CapabilityStatus.SUPPORTED),  # probe wins
        ("U", CapabilityStatus.UNSUPPORTED),  # both agree
        ("K", CapabilityStatus.UNSUPPORTED),  # matrix preserved
    ],
    ids=["matrix_U_probe_S", "matrix_U_probe_U", "matrix_U_probe_K"],
)
async def test_merge_matrix_unsupported_it83_relay_status(
    probe_signal: str, expected: CapabilityStatus
) -> None:
    """IT83 RELAY_STATUS + each probe outcome → expected merged status."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_IT83_INFO_FOR_MERGE,
            repeat=True,
        )
        _register_probe_mocks(m, user_list="S", relay_status=probe_signal)
        async with AkuvoxDevice("192.168.1.100") as device:
            merged = await device.probe_capabilities()
    assert merged.status_of(Capability.RELAY_STATUS) is expected


# Matrix-UNKNOWN row: pin to IT83 USER_LIST.


@pytest.mark.parametrize(
    ("probe_signal", "expected"),
    [
        ("S", CapabilityStatus.SUPPORTED),
        ("U", CapabilityStatus.UNSUPPORTED),
        ("K", CapabilityStatus.UNKNOWN),
    ],
    ids=["matrix_K_probe_S", "matrix_K_probe_U", "matrix_K_probe_K"],
)
async def test_merge_matrix_unknown_it83_user_list(
    probe_signal: str, expected: CapabilityStatus
) -> None:
    """IT83 USER_LIST + each probe outcome → expected merged status."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_IT83_INFO_FOR_MERGE,
            repeat=True,
        )
        _register_probe_mocks(m, user_list=probe_signal, relay_status="U")
        async with AkuvoxDevice("192.168.1.100") as device:
            merged = await device.probe_capabilities()
    assert merged.status_of(Capability.USER_LIST) is expected


# --- Write-capability non-regression (FR-003 / BLOCKER 3) ---------------


async def test_merge_preserves_matrix_write_aliases_when_probe_refines_read() -> None:
    """Probe-observed reads must not erase matrix-curated write aliases."""
    from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
    from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases
    from pylocal_akuvox.device import _merge_probe_with_matrix

    matrix_only_aliases = FieldAliases(read=("MatrixOnly",), write=("MatrixOnly",))
    matrix = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={Capability.USER_ADD: CapabilityStatus.SUPPORTED},
        field_aliases={
            "schedule_relay": DEFAULT_USER_FIELD_ALIASES,
            "matrix_only": matrix_only_aliases,
            "custom": FieldAliases(read=("MatrixRead",), write=("MatrixWrite",)),
        },
        schema_shapes={},
    )
    probe_only_aliases = FieldAliases(read=("ProbeOnly",), write=())
    probe = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={},
        field_aliases={
            "schedule_relay": FieldAliases(read=("Schedule",), write=()),
            "custom": FieldAliases(read=("ProbeRead",), write=("ProbeWrite",)),
            "probe_only": probe_only_aliases,
        },
        schema_shapes={},
    )

    merged = _merge_probe_with_matrix(matrix, probe)

    schedule_aliases = merged.field_aliases["schedule_relay"]
    assert schedule_aliases.read == ("Schedule",)
    assert schedule_aliases.write == DEFAULT_USER_FIELD_ALIASES.write
    assert merged.field_aliases["custom"] == FieldAliases(
        read=("ProbeRead",),
        write=("ProbeWrite",),
    )
    assert merged.field_aliases["matrix_only"] == matrix_only_aliases
    assert merged.field_aliases["probe_only"] == probe_only_aliases


async def test_probe_refined_aliases_still_emit_schedule_relay_on_add() -> None:
    """A recognised device can add users after probe read-alias refinement."""
    import aiohttp

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_X916_INFO_FOR_MERGE,
            repeat=True,
        )
        m.get(
            f"{BASE_URL}/api/system/status",
            payload={
                "retcode": 0,
                "action": "status",
                "message": "",
                "data": {"SystemTime": 1700000000, "UpTime": 86400},
            },
        )
        keyed_ok = {
            "retcode": 0,
            "action": "get",
            "message": "",
            "data": {"Item": [{"ID": "1"}], "Total": 1},
        }
        m.get(
            f"{BASE_URL}/api/user/get?page=1",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "",
                "data": {
                    "Item": [{"ID": "1", "Schedule": "1001-1"}],
                    "Total": 1,
                },
            },
        )
        m.get(f"{BASE_URL}/api/relay/status", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/schedule/get", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/group/get", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=keyed_ok)
        m.post(f"{BASE_URL}/api/user/set", payload={"retcode": 0, "message": "ok"})

        async with AkuvoxDevice("192.168.1.100", request_delay=0.0) as device:
            merged = await device.probe_capabilities()
            schedule_aliases = merged.field_aliases["schedule_relay"]
            assert schedule_aliases.read == ("Schedule",)

            await device.add_user(
                name="Alice",
                user_id="1",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )

    url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
    item = m.requests[url_key][0].kwargs.get("json")["data"]["item"][0]
    assert item["ScheduleRelay"] == "1001-1"
    assert item["Schedule-Relay"] == "1001-1"


async def test_user_list_unsupported_does_not_regress_user_add() -> None:
    """Read-side UNSUPPORTED MUST NOT propagate to the corresponding write.

    X916 matrix has ``USER_ADD = SUPPORTED``. Even if the probe
    classifies ``USER_LIST`` as UNSUPPORTED (``"No handlers"`` body
    on the read endpoint), the merged profile MUST keep
    ``USER_ADD`` SUPPORTED — read signals never imply write
    capability per FR-003.
    """
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload=_X916_INFO_FOR_MERGE,
            repeat=True,
        )
        _register_probe_mocks(m, user_list="U", relay_status="S")
        async with AkuvoxDevice("192.168.1.100") as device:
            merged = await device.probe_capabilities()
    assert merged.status_of(Capability.USER_LIST) is CapabilityStatus.UNSUPPORTED
    assert merged.status_of(Capability.USER_ADD) is CapabilityStatus.SUPPORTED


# --- Probe with no matrix entry (probe-only flow) -----------------------


async def test_merge_with_no_matrix_returns_probe_unchanged() -> None:
    """Probe-only flow (no matrix entry) returns the probe profile as-is."""
    from pylocal_akuvox.device import _merge_probe_with_matrix

    probe_only = await _probe_run_minimal()
    merged = _merge_probe_with_matrix(None, probe_only)
    assert merged is probe_only


async def _probe_run_minimal() -> DeviceCapabilities:
    """Helper: run the probe against a minimal mock to get a real profile."""
    info_payload: dict[str, object] = {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "UnknownDevice",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "1.0.0.0",
                "HardwareVersion": "1.0",
            }
        },
    }
    keyed_ok = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {"Item": [{"ID": "1"}], "Total": 1},
    }
    status_payload = {
        "retcode": 0,
        "action": "status",
        "message": "",
        "data": {"SystemTime": 1700000000, "UpTime": 86400},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=info_payload)
        m.get(f"{BASE_URL}/api/system/status", payload=status_payload)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/contact/get?page=1", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/schedule/get", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/group/get", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/relay/status", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/doorlog/get?page=1", payload=keyed_ok)
        m.get(f"{BASE_URL}/api/calllog/get?page=1", payload=keyed_ok)
        async with AkuvoxHttpClient(host="192.168.1.100", timeout=5) as client:
            return await _probe_helper(client, timeout=5.0)


# --- Conservative-empty + probe merge drops the discriminator note ---------


async def test_merge_strips_device_not_in_matrix_note_from_conservative_empty() -> None:
    """Probing an unrecognised device should clear the discriminator note.

    A conservative-empty profile (matrix-side) carries the
    ``"device_not_in_matrix"`` notes key that ``DeviceCapabilities.require``
    uses to choose ``reason="device_unrecognized"``. Once the probe has
    enumerated the device, that condition no longer applies: a remaining
    UNKNOWN capability should now raise ``reason="capability_unknown"``
    (probed but indeterminate), not ``device_unrecognized`` (never probed).
    """
    from types import MappingProxyType

    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox.device import (
        _DEVICE_NOT_IN_MATRIX_NOTE,
        _merge_probe_with_matrix,
    )

    matrix_conservative = DeviceCapabilities(
        device_class="UnknownDevice",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={},
        schema_shapes={},
        notes={"device_not_in_matrix": _DEVICE_NOT_IN_MATRIX_NOTE},
        provenance=None,
    )
    probe = await _probe_run_minimal()
    merged = _merge_probe_with_matrix(matrix_conservative, probe)
    assert "device_not_in_matrix" not in merged.notes
    # Sanity: merged is a fresh DeviceCapabilities (not the matrix object)
    # so the matrix entry's read-only notes are untouched.
    assert isinstance(merged.notes, MappingProxyType)
