# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the example MVP diagnostic runner helpers."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import aiohttp
import examples.mvp_test as mvp_test
import pytest
from aioresponses import aioresponses

import pylocal_akuvox._capability_report as _capability_report
import pylocal_akuvox._report_steps as _report_steps
from pylocal_akuvox import (
    AkuvoxDevice,
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
)
from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_profile import FieldAliases
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
)
from pylocal_akuvox.models import CallLogEntry, Contact, DeviceInfo, DoorLogEntry, User
from tests.unit._helpers import register_default_info

BASE_URL = "http://192.168.1.100"
_CONFIG_SET_URL = aiohttp.client.URL(f"{BASE_URL}/api/config/set")
_SET_SUCCESS_RESPONSE = {
    "retcode": 0,
    "action": "config",
    "message": "set successfully!",
    "data": {},
}


class _FakeResponse:
    """Small response double for diagnostic response-handler tests."""

    def __init__(self, status: int, body: str) -> None:
        """Initialize the fake response status and body text."""
        self.status = status
        self._body = body

    async def text(self) -> str:
        """Return the configured response body."""
        return self._body


async def _fake_original_success_handler(resp: _FakeResponse) -> dict[str, Any]:
    """Return the response data like the library handler would on success."""
    body = json.loads(await resp.text())
    data = body.get("data", {})
    return cast("dict[str, Any]", data if isinstance(data, dict) else {})


async def _fake_original_device_error_handler(resp: _FakeResponse) -> dict[str, Any]:
    """Raise a device error like the library handler would on retcode failure."""
    body = json.loads(await resp.text())
    message = body.get("message", body.get("retmsg", ""))
    if not isinstance(message, str):
        message = str(message) if message is not None else ""
    raise AkuvoxDeviceError(message)


async def _fake_original_unsupported_handler(resp: _FakeResponse) -> dict[str, Any]:
    """Raise unsupported when the library handler would catch that message."""
    await resp.text()
    raise AkuvoxDeviceError("Api unsupported")


class _FakePrintDevice:
    """Device double that returns sample PII for stdout redaction tests."""

    async def get_info(self) -> DeviceInfo:
        """Return device identity with a sample MAC address."""
        return DeviceInfo(
            model="X916",
            mac_address="00:11:22:33:44:55",
            firmware_version="916.30.10.114",
            hardware_version="1.0",
        )

    async def list_users(self, *, page: int | None = None) -> list[User]:
        """Return one user containing sample private values."""
        return [
            User(
                id="42",
                name="Alice Resident",
                user_id="user-1234",
                private_pin="123456",
                schedule_relay="1001-1",
            )
        ]

    async def list_contacts(self, *, page: int | None = None) -> list[Contact]:
        """Return one contact containing sample private values."""
        return [
            Contact(
                id="7",
                name="Bob Visitor",
                phone="555-0100",
                group="Default",
            )
        ]

    async def get_door_logs(self, *, page: int | None = None) -> list[DoorLogEntry]:
        """Return one door log containing a sample private name."""
        return [
            DoorLogEntry(
                id="99",
                date="2026-06-13",
                time="08:00",
                name="Carol Door",
                code="card",
                door_type="1",
                status="OK",
            )
        ]

    async def get_call_logs(self, *, page: int | None = None) -> list[CallLogEntry]:
        """Return one call log containing a sample private name."""
        return [
            CallLogEntry(
                id="100",
                date="2026-06-13",
                time="08:01",
                name="Dave Caller",
                call_type="incoming",
                local_identity="100",
                count="1",
            )
        ]


class _FakeOpenDoorDevice:
    """Device double that records OpenDoor HTTP calls."""

    def __init__(self) -> None:
        """Initialize the recorded call list."""
        self.calls: list[tuple[str, str, int]] = []
        self.cleanup_calls: list[tuple[str, str]] = []
        self.discoverable_cleanup = True

    async def open_door_http(
        self,
        *,
        user: str,
        password: str,
        door_num: int = 1,
    ) -> None:
        """Record one OpenDoor HTTP call."""
        self.calls.append((user, password, door_num))

    async def delete_user(self, *, id: str) -> None:
        """Record one direct user cleanup call."""
        self.cleanup_calls.append(("user", id))

    async def delete_schedule(self, *, id: str) -> None:
        """Record one direct schedule cleanup call."""
        self.cleanup_calls.append(("schedule", id))

    async def delete_group(self, *, id: str) -> None:
        """Record one direct group cleanup call."""
        self.cleanup_calls.append(("group", id))

    async def delete_contact(self, *, id: str) -> None:
        """Record one direct contact cleanup call."""
        self.cleanup_calls.append(("contact", id))

    async def list_users(self) -> list[Any]:
        """Return a cleanup-discoverable user."""
        if not self.discoverable_cleanup:
            return [SimpleNamespace(user_id="other", id="other-id")]
        return [SimpleNamespace(user_id="9999", id="user-id")]

    async def list_schedules(self) -> list[Any]:
        """Return a cleanup-discoverable schedule."""
        if not self.discoverable_cleanup:
            return [SimpleNamespace(name="other", id="other-id")]
        return [SimpleNamespace(name="pylocal-test-sched", id="schedule-id")]

    async def list_groups(self) -> list[Any]:
        """Return a cleanup-discoverable group."""
        if not self.discoverable_cleanup:
            return [SimpleNamespace(name="other", id="other-id")]
        return [SimpleNamespace(name="__test_group__", id="group-id")]

    async def list_contacts(self) -> list[Any]:
        """Return a cleanup-discoverable contact."""
        if not self.discoverable_cleanup:
            return [SimpleNamespace(name="other", id="other-id")]
        return [SimpleNamespace(name="__test_contact__", id="contact-id")]


class _FakeReportTemplate:
    """Device template double for capability-report orchestration tests."""

    def __init__(self, *, attempt_unknown_capability: bool) -> None:
        """Store whether UNKNOWN capability probes should run."""
        self.attempt_unknown_capability = attempt_unknown_capability

    def _connection_spec(self) -> dict[str, Any]:
        """Return enough connection data for report orchestration."""
        return {
            "host": "192.0.2.10",
            "auth": None,
            "request_delay": 0.0,
            "use_ssl": False,
            "verify_ssl": True,
        }


class _FakeDeviceContext:
    """Async context manager returning a fake device."""

    def __init__(self, device: _FakeOpenDoorDevice) -> None:
        """Store the fake device returned from ``__aenter__``."""
        self.device = device

    async def __aenter__(self) -> _FakeOpenDoorDevice:
        """Return the fake device."""
        return self.device

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the fake context manager."""


async def _successful_step() -> str:
    """Return a value from a successful diagnostic step."""
    return "ok"


async def _device_error_step() -> None:
    """Raise a non-fatal device error."""
    raise AkuvoxDeviceError("No handlers for this request")


async def _skipped_step() -> None:
    """Raise an expected diagnostic skip."""
    raise mvp_test.TestStepSkipped("missing prerequisite")


async def _connection_error_step() -> None:
    """Raise a fatal connection error."""
    raise AkuvoxConnectionError("connection refused")


async def _authentication_error_step() -> None:
    """Raise a fatal authentication error."""
    raise AkuvoxAuthenticationError("bad credentials")


def _all_supported_capabilities() -> DeviceCapabilities:
    """Return a capability profile that lets every write step run."""
    return DeviceCapabilities(
        device_class="Test",
        firmware_version="1",
        capabilities={
            capability: CapabilityStatus.SUPPORTED for capability in Capability
        },
        field_aliases={},
        schema_shapes={},
    )


def _patch_fast_write_steps(
    monkeypatch: pytest.MonkeyPatch,
    device: _FakeOpenDoorDevice,
) -> None:
    """Patch write-test dependencies so OpenDoor gating can be tested quickly."""

    async def return_user_id(*_args: object, **_kwargs: object) -> str:
        """Return a fake user ID for the add-user step."""
        return "user-id"

    async def return_schedule_id(*_args: object, **_kwargs: object) -> str:
        """Return a fake schedule ID for the add-schedule step."""
        return "schedule-id"

    async def return_group_id(*_args: object, **_kwargs: object) -> str:
        """Return a fake group ID for the add-group step."""
        return "group-id"

    async def return_contact_id(*_args: object, **_kwargs: object) -> str:
        """Return a fake contact ID for the add-contact step."""
        return "contact-id"

    async def succeed(*_args: object, **_kwargs: object) -> None:
        """Pretend a patched write step succeeded."""
        return None

    async def no_sleep(_delay: float) -> None:
        """Skip write-test cooldown sleeps."""
        return None

    monkeypatch.setattr(
        _report_steps,
        "create_device",
        lambda _kwargs, _diagnostics: _FakeDeviceContext(device),
    )
    monkeypatch.setattr(cast("Any", _report_steps).asyncio, "sleep", no_sleep)
    monkeypatch.setattr(_report_steps, "test_add_user", return_user_id)
    monkeypatch.setattr(_report_steps, "test_modify_user", succeed)
    monkeypatch.setattr(_report_steps, "test_delete_user", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_user_deletion", succeed)
    monkeypatch.setattr(_report_steps, "test_add_schedule", return_schedule_id)
    monkeypatch.setattr(_report_steps, "test_modify_schedule", succeed)
    monkeypatch.setattr(_report_steps, "test_delete_schedule", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_schedule_deletion", succeed)
    monkeypatch.setattr(_report_steps, "test_trigger_relay", succeed)
    monkeypatch.setattr(_report_steps, "test_set_device_config", succeed)
    monkeypatch.setattr(_report_steps, "test_add_group", return_group_id)
    monkeypatch.setattr(_report_steps, "test_delete_group", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_group_deletion", succeed)
    monkeypatch.setattr(_report_steps, "test_add_contact", return_contact_id)
    monkeypatch.setattr(_report_steps, "test_modify_contact", succeed)
    monkeypatch.setattr(_report_steps, "test_delete_contact", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_contact_deletion", succeed)


def _patch_non_user_write_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch non-user write steps so report tests can focus on user CRUD."""

    async def return_id(*_args: object, **_kwargs: object) -> str:
        """Return a fake ID for non-user add steps."""
        return "resource-id"

    async def succeed(*_args: object, **_kwargs: object) -> None:
        """Pretend a patched write step succeeded."""
        return None

    async def no_sleep(_delay: float) -> None:
        """Skip diagnostic cooldown sleeps."""
        return None

    monkeypatch.setattr(cast("Any", _report_steps).asyncio, "sleep", no_sleep)
    monkeypatch.setattr(_report_steps, "test_add_schedule", return_id)
    monkeypatch.setattr(_report_steps, "test_modify_schedule", succeed)
    monkeypatch.setattr(_report_steps, "test_delete_schedule", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_schedule_deletion", succeed)
    monkeypatch.setattr(_report_steps, "test_trigger_relay", succeed)
    monkeypatch.setattr(_report_steps, "test_set_device_config", succeed)
    monkeypatch.setattr(_report_steps, "test_add_group", return_id)
    monkeypatch.setattr(_report_steps, "test_delete_group", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_group_deletion", succeed)
    monkeypatch.setattr(_report_steps, "test_add_contact", return_id)
    monkeypatch.setattr(_report_steps, "test_modify_contact", succeed)
    monkeypatch.setattr(_report_steps, "test_delete_contact", succeed)
    monkeypatch.setattr(_report_steps, "test_verify_contact_deletion", succeed)


def _run_parser_coroutine_without_loop(coro: Any) -> Any:
    """Drive a no-await parser-test coroutine without touching event loops."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    msg = "parser test coroutine unexpectedly yielded"
    raise AssertionError(msg)


def _config_get_payload(data: dict[str, str]) -> dict[str, object]:
    """Build a device-config get response envelope."""
    return {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": data,
    }


def _request_json(request: Any) -> dict[str, Any]:
    """Return the JSON request body captured by aioresponses."""
    return cast("dict[str, Any]", request.kwargs["json"])


async def test_set_device_config_prefers_toggle_restore() -> None:
    """Keep the legacy HoldDelayA toggle and restore probe unchanged."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "7"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "6"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert _request_json(posts[0])["data"] == {
        "Config.DoorSetting.RELAY.HoldDelayA": "6"
    }
    assert _request_json(posts[1])["data"] == {
        "Config.DoorSetting.RELAY.HoldDelayA": "7"
    }


async def test_set_device_config_noop_fallback_attempts_set() -> None:
    """Probe config.set with a same-value fallback instead of skipping."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload(
                {"Config.DoorSetting.RELAY.TriggerDelayA": "0"}
            ),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert len(posts) == 1
    assert _request_json(posts[0])["data"] == {
        "Config.DoorSetting.RELAY.TriggerDelayA": "0"
    }


async def test_set_device_config_noop_prefers_web_title_anchor() -> None:
    """Lead with benign UI settings before model-specific keys."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload(
                {
                    "Config.Settings.GENERAL.WebTitle": "Door Phone",
                    "Config.Settings.LANGUAGE.WebLang": "English",
                    "Config.DoorSetting.GENERAL.DeviceName": "Door",
                    "Config.DoorSetting.RELAY.TriggerDelayA": "0",
                }
            ),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert len(posts) == 1
    assert _request_json(posts[0])["data"] == {
        "Config.Settings.GENERAL.WebTitle": "Door Phone"
    }


async def test_set_device_config_device_name_only_fallback() -> None:
    """Probe config.set on non-relay devices via a device-name fallback."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload(
                {"Config.DoorSetting.GENERAL.DeviceName": "Indoor Monitor"}
            ),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert len(posts) == 1
    assert _request_json(posts[0])["data"] == {
        "Config.DoorSetting.GENERAL.DeviceName": "Indoor Monitor"
    }


async def test_set_device_config_rejected_key_tries_next() -> None:
    """Continue past a rejected same-value candidate until one is accepted."""
    unsupported_response = {
        "retcode": 0,
        "action": "config",
        "message": "Api unsupported",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload(
                {
                    "Config.Settings.GENERAL.WebTitle": "Door Phone",
                    "Config.Settings.LANGUAGE.WebLang": "English",
                }
            ),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=unsupported_response)
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert len(posts) == 2
    assert _request_json(posts[0])["data"] == {
        "Config.Settings.GENERAL.WebTitle": "Door Phone"
    }
    assert _request_json(posts[1])["data"] == {
        "Config.Settings.LANGUAGE.WebLang": "English"
    }


async def test_set_device_config_all_rejected_records_unsupported() -> None:
    """All rejected fallback writes are failures, not skips or false passes."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)
    device_kwargs = {
        "host": "192.168.1.100",
        "auth": None,
        "request_delay": 0.0,
        "use_ssl": False,
        "verify_ssl": True,
    }
    reject_response = {
        "retcode": -1,
        "action": "config",
        "message": "unsupported action",
        "data": {},
    }

    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload(
                {
                    "Config.Settings.GENERAL.WebTitle": "Door Phone",
                    "Config.Settings.LANGUAGE.WebLang": "English",
                }
            ),
        )
        m.post(f"{BASE_URL}/api/config/set", status=501, payload=reject_response)
        m.post(f"{BASE_URL}/api/config/set", status=501, payload=reject_response)

        async with _report_steps.create_device(device_kwargs, diagnostics) as device:
            await _report_steps.step(
                results=results,
                name="set_device_config",
                capability=Capability.DEVICE_CONFIG_SET,
                capabilities=_all_supported_capabilities(),
                coro_factory=lambda: _report_steps.test_set_device_config(device),
            )

    tests = cast("list[dict[str, Any]]", diagnostics.to_json()["tests"])
    assert len(results.failed) == 1
    assert results.failed[0][0] == "set_device_config"
    assert (
        "All safe config.set fallback candidates were rejected" in results.failed[0][1]
    )
    assert tests[0]["status"] == "failed"
    assert tests[0]["capability_status"] == "unsupported"
    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert len(posts) == 2
    assert _request_json(posts[0])["data"] == {
        "Config.Settings.GENERAL.WebTitle": "Door Phone"
    }
    assert _request_json(posts[1])["data"] == {
        "Config.Settings.LANGUAGE.WebLang": "English"
    }


async def test_set_device_config_transport_error_propagates() -> None:
    """Do not treat transport failures as rejected fallback candidates."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload(
                {
                    "Config.Settings.GENERAL.WebTitle": "Door Phone",
                    "Config.Settings.LANGUAGE.WebLang": "English",
                }
            ),
        )
        m.post(
            f"{BASE_URL}/api/config/set",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            with pytest.raises(AkuvoxConnectionError):
                await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert len(posts) == 1


async def test_set_device_config_restores_after_readback_mismatch() -> None:
    """Restore the original HoldDelayA value when read-back verification fails."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "5"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "5"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            with pytest.raises(_report_steps.TestStepFailed, match="mismatch"):
                await _report_steps.test_set_device_config(device)

    posts = m.requests[("POST", _CONFIG_SET_URL)]
    assert _request_json(posts[0])["data"] == {
        "Config.DoorSetting.RELAY.HoldDelayA": "7"
    }
    assert _request_json(posts[1])["data"] == {
        "Config.DoorSetting.RELAY.HoldDelayA": "5"
    }


async def test_set_device_config_suppresses_restore_failure_after_error() -> None:
    """Keep reporting the primary failure when restore also fails afterward."""
    restore_error = {
        "retcode": -1,
        "action": "config",
        "message": "restore failed",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "5"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "5"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=restore_error)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            with pytest.raises(_report_steps.TestStepFailed, match="mismatch"):
                await _report_steps.test_set_device_config(device)


async def test_set_device_config_restore_failure_after_success_raises() -> None:
    """Surface restore failures when the value-changing probe otherwise passed."""
    restore_error = {
        "retcode": -1,
        "action": "config",
        "message": "restore failed",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "5"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=_SET_SUCCESS_RESPONSE)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.DoorSetting.RELAY.HoldDelayA": "7"}),
        )
        m.post(f"{BASE_URL}/api/config/set", payload=restore_error)

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            with pytest.raises(AkuvoxDeviceError, match="restore failed"):
                await _report_steps.test_set_device_config(device)


async def test_set_device_config_last_resort_skip_without_safe_key() -> None:
    """Skip only when neither the legacy key nor any safe fallback exists."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/config/get",
            payload=_config_get_payload({"Config.Network.LAN.IPAddress": "192.0.2.1"}),
        )

        async with AkuvoxDevice("192.168.1.100", request_delay=0) as device:
            with pytest.raises(_report_steps.TestStepSkipped, match="fallback"):
                await _report_steps.test_set_device_config(device)

    assert ("POST", _CONFIG_SET_URL) not in m.requests


def test_mvp_script_is_thin_wrapper() -> None:
    """The CLI must not carry a second copy of the report core."""
    source = Path(mvp_test.__file__).read_text(encoding="utf-8")

    for duplicate in (
        "class DiagnosticReport",
        "def _run_write_tests",
        "def _redact_json_values",
        "def test_add_user",
    ):
        assert duplicate not in source


async def test_run_step_records_success() -> None:
    """Run a successful step and record its label."""
    results = mvp_test.TestResults()

    value = await mvp_test.run_step(results, "SUCCESS", _successful_step())

    assert value == "ok"
    assert results.passed == ["SUCCESS"]
    assert results.failed == []
    assert results.skipped == []


async def test_run_step_records_non_fatal_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Record device errors as failures without raising."""
    results = mvp_test.TestResults()

    await mvp_test.run_step(results, "LIST USERS", _device_error_step())

    assert results.failed == [("LIST USERS", "No handlers for this request")]
    assert "✗ LIST USERS: No handlers for this request" in capsys.readouterr().out


async def test_run_step_records_skip(capsys: pytest.CaptureFixture[str]) -> None:
    """Record expected skips separately from failures."""
    results = mvp_test.TestResults()

    await mvp_test.run_step(results, "SET DEVICE CONFIG", _skipped_step())

    assert results.skipped == [("SET DEVICE CONFIG", "missing prerequisite")]
    output = capsys.readouterr().out
    assert "⊘ SET DEVICE CONFIG skipped: missing prerequisite" in output


async def test_run_step_reraises_connection_errors() -> None:
    """Abort on connection failures."""
    results = mvp_test.TestResults()

    with pytest.raises(AkuvoxConnectionError):
        await mvp_test.run_step(results, "FATAL", _connection_error_step())

    assert results.total == 0


async def test_run_step_reraises_authentication_errors() -> None:
    """Abort on authentication failures."""
    results = mvp_test.TestResults()

    with pytest.raises(AkuvoxAuthenticationError):
        await mvp_test.run_step(results, "FATAL", _authentication_error_step())

    assert results.total == 0


def test_skip_step_records_dependency_skip(capsys: pytest.CaptureFixture[str]) -> None:
    """Record dependent steps skipped by the write-test chain."""
    results = mvp_test.TestResults()

    mvp_test.skip_step(results, "DELETE USER", "requires internal ID from ADD USER")

    assert results.skipped == [
        ("DELETE USER", "requires internal ID from ADD USER"),
    ]
    assert (
        "⊘ DELETE USER skipped: requires internal ID from ADD USER"
        in capsys.readouterr().out
    )


def test_summary_lists_all_result_buckets(capsys: pytest.CaptureFixture[str]) -> None:
    """Print counts and labels for passed, failed, and skipped steps."""
    results = mvp_test.TestResults()
    results.mark_passed("GET DEVICE INFO")
    results.mark_failed("LIST USERS", "No handlers for this request")
    results.mark_skipped("DELETE USER", "requires ADD USER")

    results.print_summary()

    output = capsys.readouterr().out
    assert "Total:      3" in output
    assert "✓ Passed:   1" in output
    assert "✗ Failed:   1" in output
    assert "⊘ Skipped:  1" in output
    assert "- GET DEVICE INFO" in output
    assert "- LIST USERS: No handlers for this request" in output
    assert "- DELETE USER: requires ADD USER" in output


def test_summary_prints_capability_matrix_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Print matrix-friendly status and observed read fields."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)
    diagnostics.begin_test("LIST USERS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/user/get",
        data=None,
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text='{"retcode":0,"message":"OK","data":{"item":[{"ID":"1",'
        '"Name":"Alice","Schedule":"1-1"}]}}',
        body=None,
        retcode=0,
        retmsg="OK",
        data={"item": [{"ID": "1", "Name": "Alice", "Schedule": "1-1"}]},
    )
    diagnostics.finish_test("passed")
    results.mark_passed("LIST USERS")

    results.print_summary()

    output = capsys.readouterr().out
    assert "Capability matrix data:" in output
    assert "capability=list_users status=supported endpoint=/api/user/get" in output
    assert "observed_fields=ID,Name,Schedule" in output
    action_not_supported = "".join(("unsup", "port action"))
    diagnostics.begin_test("ADD CONTACT")
    diagnostics.begin_http_event(
        method="POST",
        endpoint="/api/contact/set",
        data={"data": {"item": [{"Name": "Test", "Phone": "555"}]}},
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text=f'{{"retcode":-1,"retmsg":"{action_not_supported}"}}',
        body={"retcode": -1, "retmsg": action_not_supported},
        retcode=-1,
        retmsg=action_not_supported,
        data={},
    )
    diagnostics.finish_test("failed", action_not_supported)

    results.print_summary()

    output = capsys.readouterr().out
    assert (
        "capability=add_contact status=unsupported endpoint=/api/contact/set" in output
    )
    assert (
        f'failure_shape=http=200 retcode=-1 retmsg="{action_not_supported}"' in output
    )


async def test_open_door_helper_redacts_password(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the MVP OpenDoor helper without printing the password."""
    device = _FakeOpenDoorDevice()

    await mvp_test.test_open_door(
        cast("Any", device),
        user="relay-user",
        password="relay-secret",
    )

    assert device.calls == [("relay-user", "relay-secret", 1)]
    output = capsys.readouterr().out
    assert "relay-user" in output
    assert mvp_test._REDACTED_VALUE in output
    assert "relay-secret" not in output


async def test_write_tests_skip_open_door_without_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Write tests report OpenDoor as skipped unless explicitly enabled."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        redact_stdout=False,
    )

    assert device.calls == []
    assert any(label == "open_door_http" for label, _reason in results.skipped)


async def test_write_tests_attempt_open_door_once_with_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Write tests fire OpenDoor exactly once when opt-in credentials exist."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=True,
        open_door_user="relay-user",
        open_door_password="relay-secret",
        redact_stdout=False,
    )

    assert device.calls == [("relay-user", "relay-secret", 1)]
    assert "open_door_http" in results.passed
    output = capsys.readouterr().out
    assert mvp_test._REDACTED_VALUE in output
    assert "relay-secret" not in output


async def test_write_tests_retry_user_cleanup_after_delete_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry user cleanup silently when the recorded delete step fails."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)

    async def fail_delete(*_args: object, **_kwargs: object) -> None:
        """Pretend the diagnostic delete step failed."""
        raise mvp_test.TestStepFailed("delete failed")

    monkeypatch.setattr(_report_steps, "test_delete_user", fail_delete)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        redact_stdout=False,
    )

    assert ("user", "user-id") in device.cleanup_calls
    assert ("delete_user", "delete failed") in results.failed


async def test_write_tests_retry_user_cleanup_after_verify_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry user cleanup when delete passes but verification fails."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)

    async def fail_verify(*_args: object, **_kwargs: object) -> None:
        """Pretend the deleted user still appears in list results."""
        raise mvp_test.TestStepFailed("User still present after delete")

    monkeypatch.setattr(_report_steps, "test_verify_user_deletion", fail_verify)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        redact_stdout=False,
    )

    assert ("user", "user-id") in device.cleanup_calls
    assert (
        "verify_user_deletion",
        "User still present after delete",
    ) in results.failed


@pytest.mark.parametrize(
    ("step_name", "result_name", "entity", "entity_id"),
    [
        ("test_add_user", "add_user", "user", "user-id"),
        ("test_add_schedule", "add_schedule", "schedule", "schedule-id"),
        ("test_add_group", "add_group", "group", "group-id"),
        ("test_add_contact", "add_contact", "contact", "contact-id"),
    ],
)
async def test_write_tests_retry_cleanup_after_unlisted_add_failure(
    monkeypatch: pytest.MonkeyPatch,
    step_name: str,
    result_name: str,
    entity: str,
    entity_id: str,
) -> None:
    """Retry cleanup when an add step creates a record but cannot find its ID."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)

    async def fail_add(*_args: object, **_kwargs: object) -> str:
        """Pretend an add step failed after creating a record."""
        raise mvp_test.TestStepFailed("created record not listed")

    monkeypatch.setattr(_report_steps, step_name, fail_add)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        redact_stdout=False,
    )

    assert (entity, entity_id) in device.cleanup_calls
    assert (result_name, "created record not listed") in results.failed


async def test_best_effort_delete_suppresses_cleanup_error() -> None:
    """Ignore best-effort cleanup failures."""

    async def fail_cleanup() -> None:
        """Raise a cleanup failure that should not escape."""
        raise AkuvoxDeviceError("cleanup failed")

    await _report_steps._best_effort_delete(fail_cleanup)


async def test_best_effort_delete_preserves_cancellation() -> None:
    """Propagate task cancellation through best-effort cleanup."""

    async def cancel_cleanup() -> None:
        """Raise cancellation from cleanup."""
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _report_steps._best_effort_delete(cancel_cleanup)


@pytest.mark.parametrize(
    ("cleanup_name", "identifier"),
    [
        ("_cleanup_user_by_user_id", "9999"),
        ("_cleanup_schedule_by_name", "pylocal-test-sched"),
        ("_cleanup_group_by_name", "__test_group__"),
        ("_cleanup_contact_by_name", "__test_contact__"),
    ],
)
async def test_silent_cleanup_skips_when_add_failure_has_no_match(
    cleanup_name: str,
    identifier: str,
) -> None:
    """Skip silent cleanup when the failed add step left no discoverable record."""
    device = _FakeOpenDoorDevice()
    device.discoverable_cleanup = False
    cleanup = getattr(_report_steps, cleanup_name)

    await cleanup(device, identifier)

    assert device.cleanup_calls == []


@pytest.mark.parametrize(
    ("step_name", "result_name", "entity", "entity_id"),
    [
        ("test_delete_schedule", "delete_schedule", "schedule", "schedule-id"),
        ("test_delete_group", "delete_group", "group", "group-id"),
        ("test_delete_contact", "delete_contact", "contact", "contact-id"),
    ],
)
async def test_write_tests_retry_other_cleanup_after_delete_failure(
    monkeypatch: pytest.MonkeyPatch,
    step_name: str,
    result_name: str,
    entity: str,
    entity_id: str,
) -> None:
    """Retry non-user cleanup silently when a recorded delete step fails."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)

    async def fail_delete(*_args: object, **_kwargs: object) -> None:
        """Pretend the diagnostic delete step failed."""
        raise mvp_test.TestStepFailed("delete failed")

    monkeypatch.setattr(_report_steps, step_name, fail_delete)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        redact_stdout=False,
    )

    assert (entity, entity_id) in device.cleanup_calls
    assert (result_name, "delete failed") in results.failed


@pytest.mark.parametrize(
    ("step_name", "result_name", "entity", "entity_id"),
    [
        (
            "test_verify_schedule_deletion",
            "verify_schedule_deletion",
            "schedule",
            "schedule-id",
        ),
        ("test_verify_group_deletion", "verify_group_deletion", "group", "group-id"),
        (
            "test_verify_contact_deletion",
            "verify_contact_deletion",
            "contact",
            "contact-id",
        ),
    ],
)
async def test_write_tests_retry_other_cleanup_after_verify_failure(
    monkeypatch: pytest.MonkeyPatch,
    step_name: str,
    result_name: str,
    entity: str,
    entity_id: str,
) -> None:
    """Retry non-user cleanup when delete passes but verification fails."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)

    async def fail_verify(*_args: object, **_kwargs: object) -> None:
        """Pretend the deleted record still appears in list results."""
        raise mvp_test.TestStepFailed("Record still present after delete")

    monkeypatch.setattr(_report_steps, step_name, fail_verify)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    await mvp_test._run_write_tests(
        {},
        results,
        capabilities=_all_supported_capabilities(),
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        redact_stdout=False,
    )

    assert (entity, entity_id) in device.cleanup_calls
    assert (result_name, "Record still present after delete") in results.failed


async def test_write_tests_cleanup_user_before_fatal_reraise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry user cleanup before propagating fatal mid-chain errors."""
    device = _FakeOpenDoorDevice()
    _patch_fast_write_steps(monkeypatch, device)

    async def fail_modify(*_args: object, **_kwargs: object) -> None:
        """Pretend the diagnostic modify step hit a fatal connection error."""
        raise AkuvoxConnectionError("connection lost")

    monkeypatch.setattr(_report_steps, "test_modify_user", fail_modify)
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    with pytest.raises(AkuvoxConnectionError):
        await mvp_test._run_write_tests(
            {},
            results,
            capabilities=_all_supported_capabilities(),
            open_door=False,
            open_door_user=None,
            open_door_password=None,
            redact_stdout=False,
        )

    assert device.cleanup_calls == [("user", "user-id")]


async def test_report_attempt_unknown_allows_unknown_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Honor the caller device's UNKNOWN-capability opt-in in report runs."""
    passed_capabilities: dict[str, DeviceCapabilities] = {}
    profile = DeviceCapabilities(
        device_class="Test",
        firmware_version="1",
        capabilities={
            Capability.USER_LIST: CapabilityStatus.UNKNOWN,
            Capability.CONTACT_LIST: CapabilityStatus.UNSUPPORTED,
        },
        field_aliases={},
        schema_shapes={},
    )

    async def skip_validation() -> None:
        """Avoid the live validation probe in this orchestration test."""
        return None

    async def return_profile(*_args: object, **_kwargs: object) -> DeviceCapabilities:
        """Return a profile containing UNKNOWN and UNSUPPORTED evidence."""
        return profile

    async def capture_read_capabilities(
        _device: object,
        _results: object,
        *,
        capabilities: DeviceCapabilities,
        redact_stdout: bool,
    ) -> None:
        """Capture the capability profile passed to read tests."""
        assert redact_stdout is False
        passed_capabilities["read"] = capabilities

    monkeypatch.setattr(_capability_report, "test_validation", skip_validation)
    monkeypatch.setattr(
        _capability_report, "_probe_device_capabilities", return_profile
    )
    monkeypatch.setattr(
        _capability_report, "_run_read_tests", capture_read_capabilities
    )
    monkeypatch.setattr(
        _capability_report,
        "create_device",
        lambda _kwargs, _diagnostics: _FakeDeviceContext(_FakeOpenDoorDevice()),
    )

    await _capability_report._run_capability_report(
        cast("Any", _FakeReportTemplate(attempt_unknown_capability=True)),
        write=False,
        open_door=False,
        open_door_user=None,
        open_door_password=None,
        timeout=None,
        redact_stdout=False,
    )

    assert passed_capabilities["read"].status_of(Capability.USER_LIST) is (
        CapabilityStatus.SUPPORTED
    )
    assert passed_capabilities["read"].status_of(Capability.CONTACT_LIST) is (
        CapabilityStatus.UNSUPPORTED
    )


async def test_report_open_door_read_only_skip_names_write_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explain that read-only OpenDoor opt-ins need write mode."""
    profile = _all_supported_capabilities()

    async def skip_validation() -> None:
        """Avoid the live validation probe in this orchestration test."""
        return None

    async def return_profile(*_args: object, **_kwargs: object) -> DeviceCapabilities:
        """Return a profile that lets the read pass continue."""
        return profile

    async def skip_read_tests(
        _device: object,
        _results: object,
        *,
        capabilities: DeviceCapabilities,
        redact_stdout: bool,
    ) -> None:
        """Avoid unrelated read steps in this orchestration test."""
        assert capabilities is profile
        assert redact_stdout is False

    monkeypatch.setattr(_capability_report, "test_validation", skip_validation)
    monkeypatch.setattr(
        _capability_report, "_probe_device_capabilities", return_profile
    )
    monkeypatch.setattr(_capability_report, "_run_read_tests", skip_read_tests)
    monkeypatch.setattr(
        _capability_report,
        "create_device",
        lambda _kwargs, _diagnostics: _FakeDeviceContext(_FakeOpenDoorDevice()),
    )

    report = await _capability_report._run_capability_report(
        cast("Any", _FakeReportTemplate(attempt_unknown_capability=False)),
        write=False,
        open_door=True,
        open_door_user="relay-user",
        open_door_password="relay-secret",
        timeout=None,
        redact_stdout=False,
    )

    tests = cast("list[dict[str, object]]", report["tests"])
    open_door_test = next(test for test in tests if test["name"] == "open_door_http")
    assert open_door_test["reason"] == "requires write=True to run OpenDoor HTTP"


def test_report_write_alias_fallback_preserves_statuses() -> None:
    """Diagnostic write alias fallback must not fabricate support."""
    profile = DeviceCapabilities(
        device_class="Synthetic",
        firmware_version="1",
        capabilities={Capability.USER_DELETE: CapabilityStatus.UNSUPPORTED},
        field_aliases={
            "schedule_relay": FieldAliases(read=("Schedule",), write=()),
        },
        schema_shapes={},
    )

    normalized = _capability_report._with_report_write_alias_fallback(profile)

    assert normalized.status_of(Capability.USER_ADD) is CapabilityStatus.UNKNOWN
    assert normalized.status_of(Capability.USER_MODIFY) is CapabilityStatus.UNKNOWN
    assert normalized.status_of(Capability.USER_DELETE) is CapabilityStatus.UNSUPPORTED
    aliases = normalized.field_aliases["schedule_relay"]
    assert aliases.read == ("Schedule",)
    assert aliases.write == DEFAULT_USER_FIELD_ALIASES.write


def test_report_write_alias_fallback_leaves_curated_aliases() -> None:
    """Recognized matrix write aliases must stay unchanged."""
    curated = FieldAliases(read=("Schedule",), write=("CuratedSchedule",))
    profile = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={Capability.USER_ADD: CapabilityStatus.SUPPORTED},
        field_aliases={"schedule_relay": curated},
        schema_shapes={},
    )

    normalized = _capability_report._with_report_write_alias_fallback(profile)

    assert normalized is profile
    assert normalized.field_aliases["schedule_relay"] is curated


def test_report_write_alias_fallback_leaves_missing_aliases() -> None:
    """Missing schedule aliases still use the device wrapper default path."""
    profile = DeviceCapabilities(
        device_class="Unknown",
        firmware_version="1",
        capabilities={},
        field_aliases={},
        schema_shapes={},
    )

    assert _capability_report._with_report_write_alias_fallback(profile) is profile


async def test_write_report_backfills_user_write_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unrecognized write reports attempt add/modify with default write aliases."""
    base_url = "http://192.0.2.10"
    profile = DeviceCapabilities(
        device_class="Synthetic",
        firmware_version="1",
        capabilities={},
        field_aliases={
            "schedule_relay": FieldAliases(read=("Schedule",), write=()),
        },
        schema_shapes={},
    )

    async def skip_validation() -> None:
        """Avoid the live validation probe in this orchestration test."""
        return None

    async def return_profile(*_args: object, **_kwargs: object) -> DeviceCapabilities:
        """Return an unrecognized probe profile with read-only aliases."""
        return profile

    async def skip_read_tests(
        _device: object,
        _results: object,
        *,
        capabilities: DeviceCapabilities,
        redact_stdout: bool,
    ) -> None:
        """Avoid unrelated read steps in this write-path regression test."""
        assert capabilities is not profile
        assert redact_stdout is False

    _patch_non_user_write_steps(monkeypatch)
    monkeypatch.setattr(_capability_report, "test_validation", skip_validation)
    monkeypatch.setattr(
        _capability_report, "_probe_device_capabilities", return_profile
    )
    monkeypatch.setattr(_capability_report, "_run_read_tests", skip_read_tests)

    unknown_info = {
        "retcode": 0,
        "action": "info",
        "message": "",
        "data": {
            "Status": {
                "Model": "Synthetic",
                "MAC": "AA:BB:CC:DD:EE:FF",
                "FirmwareVersion": "1",
                "HardwareVersion": "1.0",
            }
        },
    }
    created_user = {
        "ID": "user-id",
        "Name": "pylocal-test",
        "UserID": "9999",
        "WebRelay": "0",
        "Schedule": "1001-1",
        "LiftFloorNum": "0",
        "PrivatePIN": "1234",
        "CardCode": "",
    }
    created_users = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {"item": [created_user]},
    }
    no_users = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {"item": []},
    }

    with aioresponses() as responses:
        responses.get(f"{base_url}/api/system/info", payload=unknown_info, repeat=True)
        responses.post(
            f"{base_url}/api/user/set",
            payload={"retcode": 0, "message": "ok"},
            repeat=True,
        )
        responses.get(f"{base_url}/api/user/get", payload=created_users)
        responses.get(f"{base_url}/api/user/get?page=1", payload=created_users)
        responses.get(f"{base_url}/api/user/get", payload=no_users)

        report = await _capability_report._run_capability_report(
            cast("Any", _FakeReportTemplate(attempt_unknown_capability=True)),
            write=True,
            open_door=False,
            open_door_user=None,
            open_door_password=None,
            timeout=None,
            redact_stdout=False,
        )

    post_key = ("POST", aiohttp.client.URL(f"{base_url}/api/user/set"))
    post_calls = responses.requests[post_key]
    add_item = post_calls[0].kwargs["json"]["data"]["item"][0]
    modify_item = post_calls[1].kwargs["json"]["data"]["item"][0]

    for alias in DEFAULT_USER_FIELD_ALIASES.write:
        assert add_item[alias] == "1001-1"
        assert modify_item[alias] == "1001-1"
    assert "Schedule" not in add_item
    assert "Schedule" not in modify_item

    tests = cast("list[dict[str, object]]", report["tests"])
    outcomes = {test["name"]: test["status"] for test in tests}
    assert outcomes["add_user"] == "passed"
    assert outcomes["modify_user"] == "passed"


def test_main_parses_open_door_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI parses explicit OpenDoor relay credentials."""
    captured: dict[str, Any] = {}

    async def fake_run_all(args: Any) -> None:
        """Capture parsed CLI args without running online tests."""
        captured["args"] = args

    monkeypatch.setattr(mvp_test, "run_all", fake_run_all)
    monkeypatch.setattr(
        cast("Any", mvp_test).asyncio,
        "run",
        _run_parser_coroutine_without_loop,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mvp_test.py",
            "192.0.2.10",
            "--write",
            "--open-door",
            "--open-door-user",
            "relay-user",
            "--open-door-pass",
            "relay-secret",
        ],
    )

    mvp_test.main()

    args = captured["args"]
    assert args.open_door is True
    assert args.open_door_user == "relay-user"
    assert args.open_door_password == "relay-secret"


def test_main_reads_open_door_password_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI accepts the OpenDoor relay password from the environment."""
    captured: dict[str, Any] = {}

    async def fake_run_all(args: Any) -> None:
        """Capture parsed CLI args without running online tests."""
        captured["args"] = args

    monkeypatch.setenv("AKUVOX_OPEN_DOOR_PASSWORD", "env-secret")
    monkeypatch.setattr(mvp_test, "run_all", fake_run_all)
    monkeypatch.setattr(
        cast("Any", mvp_test).asyncio,
        "run",
        _run_parser_coroutine_without_loop,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mvp_test.py",
            "192.0.2.10",
            "--write",
            "--open-door",
            "--open-door-user",
            "relay-user",
        ],
    )

    mvp_test.main()

    assert captured["args"].open_door_password == "env-secret"


@pytest.mark.parametrize(
    "argv",
    [
        ["mvp_test.py", "192.0.2.10", "--open-door"],
        ["mvp_test.py", "192.0.2.10", "--write", "--open-door"],
        [
            "mvp_test.py",
            "192.0.2.10",
            "--write",
            "--open-door",
            "--open-door-user",
            "relay-user",
        ],
    ],
)
def test_main_rejects_incomplete_open_door_args(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> None:
    """CLI rejects unsafe OpenDoor opt-ins that lack prerequisites."""
    monkeypatch.delenv("AKUVOX_OPEN_DOOR_PASSWORD", raising=False)
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        mvp_test.main()


def test_failure_signature_quotes_single_line_tokens() -> None:
    """Keep failure-shape summary tokens escaped and single-line."""
    event = mvp_test.DiagnosticHttpEvent(
        method="GET",
        endpoint="/api/user/get",
        http_status=200,
        retcode=-1,
        retmsg='bad "field"\nsecond line',
        exception_class="AkuvoxDeviceError",
        exception_message='bad "field" \\ path',
    )

    signature = event.failure_signature()

    assert 'retmsg="bad \\"field\\""' in signature
    assert 'exception="AkuvoxDeviceError: bad \\"field\\" \\\\ path"' in signature
    assert "\n" not in signature


async def test_diagnostic_handler_omits_successful_response_values() -> None:
    """Capture successful read schemas without serializing private values."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("LIST USERS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/user/get",
        data=None,
        params=None,
    )
    body = {
        "retcode": 0,
        "message": "OK",
        "data": {
            "item": [
                {
                    "ID": "42",
                    "Name": "Alice Resident",
                    "PrivatePIN": "123456",
                    "Phone": "555-0100",
                    "CardCode": "RFID-SECRET",
                    "Schedule": "1001-1",
                }
            ]
        },
    }
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_success_handler),
    )

    await handler(cast("Any", _FakeResponse(200, json.dumps(body))))
    diagnostics.finish_test("passed")

    report_text = json.dumps(diagnostics.to_json())
    assert "body_snippet" not in report_text
    for private_value in (
        "42",
        "Alice Resident",
        "123456",
        "555-0100",
        "RFID-SECRET",
        "1001-1",
    ):
        assert private_value not in report_text
    for key in ("ID", "Name", "PrivatePIN", "Phone", "CardCode", "Schedule"):
        assert key in report_text


async def test_redact_stdout_hides_printed_private_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Redact sample PII values from the script's stdout print paths."""
    device = cast("Any", _FakePrintDevice())

    await mvp_test.test_get_info(device, redact_stdout=True)
    await mvp_test.test_list_users(device, redact_stdout=True)
    await mvp_test.test_list_contacts(device, redact_stdout=True)
    await mvp_test.test_get_door_logs(device, redact_stdout=True)
    await mvp_test.test_get_call_logs(device, redact_stdout=True)

    output = capsys.readouterr().out
    assert mvp_test._REDACTED_VALUE in output
    for private_value in (
        "00:11:22:33:44:55",
        "Alice Resident",
        "user-1234",
        "123456",
        "Bob Visitor",
        "555-0100",
        "Carol Door",
        "Dave Caller",
    ):
        assert private_value not in output
    for label in ("MAC:", "Name=", "UserID=", "PIN=", "Phone="):
        assert label in output


async def test_stdout_redaction_is_default_off(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep interactive stdout values visible unless redaction is requested."""
    device = cast("Any", _FakePrintDevice())

    await mvp_test.test_get_info(device)
    await mvp_test.test_list_users(device)
    await mvp_test.test_list_contacts(device)
    await mvp_test.test_get_door_logs(device)
    await mvp_test.test_get_call_logs(device)

    output = capsys.readouterr().out
    for private_value in (
        "00:11:22:33:44:55",
        "Alice Resident",
        "user-1234",
        "123456",
        "Bob Visitor",
        "555-0100",
        "Carol Door",
        "Dave Caller",
    ):
        assert private_value in output


def test_redaction_helper_default_off_keeps_nested_values() -> None:
    """Keep nested values visible when redaction is disabled."""
    value = {"item": [{"Name": "Alice Resident", "PrivatePIN": "123456"}]}

    displayed = mvp_test._display_value("payload", value, redact_stdout=False)

    assert "Alice Resident" in displayed
    assert "123456" in displayed


async def test_diagnostic_handler_redacts_failed_response_values() -> None:
    """Redact sensitive values from failed response body snippets."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("ADD USER")
    diagnostics.begin_http_event(
        method="POST",
        endpoint="/api/user/set",
        data={"data": {"item": [{"Name": "Alice Resident"}]}},
        params=None,
    )
    body = {
        "retcode": -1,
        "retmsg": "bad field",
        "data": {
            "item": [
                {
                    "Name": "Alice Resident",
                    "MAC": "00:11:22:33:44:55",
                    "PrivatePIN": "123456",
                    "Phone": "555-0100",
                    "CardCode": "RFID-SECRET",
                }
            ]
        },
    }
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_device_error_handler),
    )

    with pytest.raises(AkuvoxDeviceError):
        await handler(cast("Any", _FakeResponse(200, json.dumps(body))))

    report_text = json.dumps(diagnostics.to_json())
    assert mvp_test._REDACTED_VALUE in report_text
    for private_value in (
        "Alice Resident",
        "00:11:22:33:44:55",
        "123456",
        "555-0100",
        "RFID-SECRET",
    ):
        assert private_value not in report_text


async def test_missing_envelope_error_omits_response_values() -> None:
    """Avoid leaking response values in parse-error diagnostics."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("LIST USERS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/user/get",
        data=None,
        params=None,
    )
    body = {
        "Name": "Alice Resident",
        "Phone": "555-0100",
        "PrivatePIN": "123456",
    }
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_success_handler),
    )

    with pytest.raises(AkuvoxParseError) as exc_info:
        await handler(cast("Any", _FakeResponse(200, json.dumps(body))))
    diagnostics.record_exception(exc_info.value)
    diagnostics.finish_test("failed", str(exc_info.value))

    report_text = json.dumps(diagnostics.to_json())
    assert "Name" in report_text
    assert "Phone" in report_text
    assert "PrivatePIN" in report_text
    for private_value in ("Alice Resident", "555-0100", "123456"):
        assert private_value not in report_text


def test_failure_body_excerpt_is_clipped() -> None:
    """Clip long failed response snippets to the configured limit."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )
    long_value = "x" * 10_000

    diagnostics.record_http_response(
        status=200,
        body_text=json.dumps({"retcode": -1, "retmsg": "boom", "data": long_value}),
        body={"retcode": -1, "retmsg": "boom", "data": long_value},
        retcode=-1,
        retmsg="boom",
        data={},
    )

    tests = cast("list[dict[str, Any]]", diagnostics.to_json()["tests"])
    failure_shape = cast("dict[str, Any]", tests[0]["failure_shape"])
    body_snippet = cast("str", failure_shape["body_snippet"])
    assert len(body_snippet) <= mvp_test._BODY_SNIPPET_CHARS


def test_scalar_failure_body_excerpt_omits_value() -> None:
    """Omit scalar JSON failure values because they have no redactable keys."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=500,
        body_text='"Alice Resident"',
        body="Alice Resident",
        retcode=None,
        retmsg=None,
        data={},
    )

    report_text = json.dumps(diagnostics.to_json())
    assert "Alice Resident" not in report_text
    assert mvp_test._SCALAR_JSON_BODY_OMITTED in report_text


def test_unknown_success_status_body_omits_excerpt() -> None:
    """Omit body snippets for HTTP 200 responses with no retcode."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=200,
        body_text="not-json Alice Resident",
        body=None,
        retcode=None,
        retmsg=None,
        data={},
    )

    report_text = json.dumps(diagnostics.to_json())
    assert "Alice Resident" not in report_text
    assert "body_snippet" not in report_text


def test_scalar_list_failure_body_excerpt_redacts_values() -> None:
    """Redact scalar values nested inside failed JSON response lists."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET CONFIG")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/config/get",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=500,
        body_text='{"data":["Alice Resident"],"retmsg":"boom"}',
        body={"data": ["Alice Resident"], "retmsg": "boom"},
        retcode=None,
        retmsg="boom",
        data={},
    )

    report_text = json.dumps(diagnostics.to_json())
    assert "Alice Resident" not in report_text
    assert mvp_test._REDACTED_VALUE in report_text


def test_positive_retcode_omits_body_excerpt() -> None:
    """Treat non-negative retcodes as success for body snippet capture."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET STATUS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/system/status",
        data=None,
        params=None,
    )

    diagnostics.record_http_response(
        status=200,
        body_text='{"retcode":1,"message":"OK","data":{"Name":"Alice"}}',
        body={"retcode": 1, "message": "OK", "data": {"Name": "Alice"}},
        retcode=1,
        retmsg="OK",
        data={"Name": "Alice"},
    )
    diagnostics.finish_test("passed")

    report_text = json.dumps(diagnostics.to_json())
    assert "body_snippet" not in report_text
    assert "Alice" not in report_text


async def test_unsupported_message_delegates_to_original_handler() -> None:
    """Let the library classify unsupported messages even with retcode >= 0."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("GET RELAY STATUS")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/relay/status",
        data=None,
        params=None,
    )
    handler = mvp_test._build_diagnostic_response_handler(
        diagnostics,
        cast("Any", _fake_original_unsupported_handler),
    )
    body = {"retcode": 0, "message": "Api unsupported", "data": {}}

    with pytest.raises(AkuvoxDeviceError):
        await handler(cast("Any", _FakeResponse(200, json.dumps(body))))


def test_observed_fields_excludes_failure_events() -> None:
    """Report observed fields only from successful response events."""
    record = mvp_test.DiagnosticTestRecord(label="LIST USERS")
    record.events.append(
        mvp_test.DiagnosticHttpEvent(
            method="GET",
            endpoint="/api/user/get",
            http_status=200,
            retcode=-1,
            observed_fields=["Name"],
        )
    )

    assert record.observed_fields == []


def test_observed_fields_include_nested_response_keys() -> None:
    """Expose nested object keys for schema comparison."""
    fields = mvp_test._extract_observed_fields(
        {
            "Status": {
                "Model": "X916",
                "MAC": "00:11:22:33:44:55",
                "FirmwareVersion": "916.30.10.114",
            }
        }
    )

    assert fields == ["FirmwareVersion", "MAC", "Model", "Status"]


async def test_exception_capture_uses_first_line_only() -> None:
    """Store only the first line of multi-line exception messages."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    results = mvp_test.TestResults(diagnostics)

    async def fail_with_multiline() -> None:
        """Raise a multi-line exception for diagnostic capture."""
        raise ValueError("first line\nsecond line")

    await mvp_test.run_step(results, "MULTILINE", fail_with_multiline())

    tests = cast("list[dict[str, Any]]", diagnostics.to_json()["tests"])
    failure_shape = cast("dict[str, Any]", tests[0]["failure_shape"])
    assert failure_shape["exception_message"] == "first line"
    assert "second line" not in json.dumps(diagnostics.to_json())


def test_write_json_round_trip(tmp_path: Any) -> None:
    """Write a JSON report and load the same structure back."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )
    diagnostics.begin_test("LIST USERS")
    diagnostics.finish_test("passed")
    report_path = tmp_path / "mvp-diagnostic-report.json"
    diagnostics.write_json(report_path)
    loaded = json.loads(report_path.read_text(encoding="utf-8"))

    assert loaded == diagnostics.to_json()


def test_json_report_redacts_device_host() -> None:
    """Avoid leaking private device hostnames or IPs in shareable reports."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )

    report = diagnostics.to_json()
    device = cast("dict[str, Any]", report["device"])

    assert device["host"] == mvp_test._REDACTED_VALUE
    assert "192.0.2.10" not in json.dumps(report)


def test_diagnostic_report_handles_empty_and_identity_paths() -> None:
    """Cover report no-op and device-identity update branches."""
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="none",
        use_ssl=False,
        verify_ssl=True,
    )

    diagnostics.finish_test("passed")
    diagnostics.begin_test("EXCEPTION ONLY")
    diagnostics.record_exception(ValueError("first line\nsecond line"))
    diagnostics.finish_test("failed", "boom")
    diagnostics.begin_test("BAD STATUS SHAPE")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/system/info",
        data=None,
        params=None,
    )
    diagnostics.record_exception(RuntimeError("active event failed"))
    event = diagnostics.tests[-1].events[-1]
    setattr(diagnostics, "_current_test", None)
    diagnostics.record_exception(RuntimeError("active event without test"))
    assert event.exception_message == "active event without test"
    setattr(diagnostics, "_current_test", diagnostics.tests[-1])
    diagnostics.record_http_response(
        status=200,
        body_text='{"retcode":0}',
        body={"data": {"Status": "bad"}},
        retcode=0,
        retmsg=None,
        data={},
    )
    diagnostics.finish_test("passed")
    diagnostics.begin_test("GET DEVICE INFO")
    diagnostics.begin_http_event(
        method="GET",
        endpoint="/api/system/info",
        data=None,
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text='{"retcode":0}',
        body={"data": {"Status": {"Model": "X916", "FirmwareVersion": "1.2.3"}}},
        retcode=0,
        retmsg=None,
        data={},
    )

    report = diagnostics.to_json()
    device = cast("dict[str, Any]", report["device"])
    exception_record = diagnostics.tests[0]
    assert exception_record.exception_message == "first line"
    assert device["model"] == "X916"
    assert device["firmware"] == "1.2.3"


def test_json_report_includes_failure_shape() -> None:
    """Export structured failure shape and request field names."""
    action_not_supported = "".join(("unsup", "port action"))
    diagnostics = mvp_test.DiagnosticReport(
        host="192.0.2.10",
        auth_method="digest",
        use_ssl=True,
        verify_ssl=False,
    )
    diagnostics.begin_test("ADD CONTACT")
    diagnostics.begin_http_event(
        method="POST",
        endpoint="/api/contact/set",
        data={
            "target": "contact",
            "action": "add",
            "data": {"item": [{"Name": "Test", "Phone": "555", "Group": "Default"}]},
        },
        params=None,
    )
    diagnostics.record_http_response(
        status=200,
        body_text=f'{{"retcode":-1,"retmsg":"{action_not_supported}","data":{{}}}}',
        body=None,
        retcode=-1,
        retmsg=action_not_supported,
        data={},
    )
    diagnostics.record_exception(AkuvoxDeviceError(action_not_supported))
    diagnostics.finish_test("failed", action_not_supported)

    report = diagnostics.to_json()

    tests = cast("list[dict[str, Any]]", report["tests"])
    test = tests[0]
    failure_shape = cast("dict[str, Any]", test["failure_shape"])
    assert test["name"] == "add_contact"
    assert test["capability_status"] == "unsupported"
    assert test["endpoint"] == "/api/contact/set"
    assert failure_shape["retcode"] == -1
    assert failure_shape["retmsg"] == action_not_supported
    assert test["request_fields"] == [
        "Group",
        "Name",
        "Phone",
        "action",
        "data",
        "item",
        "target",
    ]
