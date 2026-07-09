# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0
# aislop-ignore-file complexity/file-too-large -- extracted CLI parity steps

"""Capability report diagnostic step helpers."""

from __future__ import annotations

import asyncio
import sys
import traceback
from typing import TYPE_CHECKING, Any

from pylocal_akuvox._capability_profile import DeviceCapabilities
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
from pylocal_akuvox._diagnostic_report import (
    DiagnosticReport,
    _decode_json_body,
    _display_value,
    _first_line,
)
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxError,
    AkuvoxParseError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
    AkuvoxValidationError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Iterator

    import aiohttp

    from pylocal_akuvox.models import DeviceConfig

SEPARATOR = "-" * 60
_MUTATION_SETTLE_SECS = 2
_OPEN_DOOR_PASSWORD_ENV = "AKUVOX_OPEN_DOOR_PASSWORD"
_TEST_USER_NAME = "pylocal-test"
_TEST_USER_ID = "9999"
_TEST_USER_PIN = "1234"
_TEST_SCHEDULE_NAME = "pylocal-test-sched"
_TEST_GROUP_NAME = "__test_group__"
_TEST_CONTACT_NAME = "__test_contact__"
_CONFIG_SET_TOGGLE_KEY = "Config.DoorSetting.RELAY.HoldDelayA"
_CONFIG_SET_NOOP_KEYS = (
    # Lead with common SNTP / general settings that were live-validated as
    # writable by same-value no-op on an E18 (fw 18.30.10.118) and are also
    # present in the R20A schema. No single key is universal, so keep the
    # try-until-accepted loop and retain R20A DeviceName plus proven relay-A
    # fallbacks for models where the broader settings are absent or read-only.
    "Config.Settings.SNTP.NTPServer1",
    "Config.Settings.SNTP.TimeZone",
    "Config.Settings.GENERAL.WebTitle",
    "Config.Settings.GENERAL.HttpUserAgent",
    "Config.Settings.SNTP.Name",
    "Config.DoorSetting.GENERAL.DeviceName",
    "Config.TR069.DeviceInfo.DeviceName",
    "Config.DoorSetting.RELAY.TriggerDelayA",
    "Config.DoorSetting.RELAY.TrigDelayA",
    "Config.DoorSetting.RELAY.NameA",
    "Config.DoorSetting.RELAY.RelayNameA",
)
_CONFIG_SET_NOOP_REJECTION_ERRORS = (
    AkuvoxUnsupportedError,
    AkuvoxRequestError,
    AkuvoxDeviceError,
)


def _default_emit(message: str) -> None:  # pragma: no cover
    """Emit one diagnostic line to stdout."""
    sys.stdout.write(f"{message}\n")


class TestStepFailed(Exception):  # pragma: no cover
    """Expected diagnostic step failure that does not need a traceback."""


class TestStepSkipped(Exception):  # pragma: no cover
    """Diagnostic step skip with a reason for the summary."""


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
        _default_emit(f"\n{'=' * 60}")
        _default_emit("  SUMMARY")
        _default_emit("=" * 60)
        _default_emit(f"  Total:    {self.total:3}")
        _default_emit(f"  ✓ Passed: {len(self.passed):3}")
        _default_emit(f"  ✗ Failed: {len(self.failed):3}")
        _default_emit(f"  ⊘ Skipped:{len(self.skipped):3}")

        _print_summary_section("Passed", [(label, "") for label in self.passed])
        _print_summary_section("Failures", self.failed)
        _print_summary_section("Skipped", self.skipped)
        if self.diagnostics is not None:
            self.diagnostics.print_capability_matrix_data()


def _print_summary_section(  # pragma: no cover
    title: str,
    entries: list[tuple[str, str]],
) -> None:
    """Print one section of the diagnostic summary."""
    if not entries:
        return

    _default_emit(f"\n  {title}:")
    for label, reason in entries:
        suffix = f": {reason}" if reason else ""
        _default_emit(f"    - {label}{suffix}")


def skip_step(
    results: TestResults, label: str, reason: str
) -> None:  # pragma: no cover  # noqa: E501
    """Record and print a skipped diagnostic step."""
    results.mark_skipped(label, reason)
    if results.diagnostics is not None:
        results.diagnostics.begin_test(label)
        results.diagnostics.finish_test("skipped", reason)
    _default_emit(f"  ⊘ {label} skipped: {reason}")


def _effective_status(  # pragma: no cover
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


def _record_capability_skip(
    results: TestResults, name: str, reason: str
) -> None:  # pragma: no cover  # noqa: E501
    """Record + print a capability-gate skip in the ``SKIP: <name>:`` style."""
    if results.diagnostics is not None:
        results.diagnostics.begin_test(name)
        results.diagnostics.finish_test("skipped", reason)
    results.mark_skipped(name, reason)
    _default_emit(f"  SKIP: {name}: {reason}")


async def _best_effort_delete(delete_coro: Callable[[], Awaitable[None]]) -> None:
    """Run a silent teardown operation and suppress cleanup failures."""
    try:
        await delete_coro()
    except asyncio.CancelledError:
        raise
    except Exception:
        return


def _step_failed(results: TestResults, label: str) -> bool:
    """Return whether a diagnostic step recorded a failure."""
    return any(failed_label == label for failed_label, _ in results.failed)


async def _cleanup_user_by_user_id(device: AkuvoxDevice, user_id: str) -> None:
    """Delete any silent-cleanup user matching a known user ID."""
    users = await device.list_users()
    for user in users:
        if user.user_id == user_id and user.id is not None:
            await device.delete_user(id=user.id)


async def _cleanup_schedule_by_name(device: AkuvoxDevice, name: str) -> None:
    """Delete any silent-cleanup schedule matching a known name."""
    schedules = await device.list_schedules()
    for sched in schedules:
        if sched.name == name and sched.id is not None:
            await device.delete_schedule(id=sched.id)


async def _cleanup_group_by_name(device: AkuvoxDevice, name: str) -> None:
    """Delete any silent-cleanup group matching a known name."""
    groups = await device.list_groups()
    for group in groups:
        if group.name == name and group.id is not None:
            await device.delete_group(id=group.id)


async def _cleanup_contact_by_name(device: AkuvoxDevice, name: str) -> None:
    """Delete any silent-cleanup contact matching a known name."""
    contacts = await device.list_contacts()
    for contact in contacts:
        if contact.name == name and contact.id is not None:
            await device.delete_contact(id=contact.id)


async def step[T](  # pragma: no cover
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
        _default_emit(f"  SKIP: {name}: {reason}")
        return None
    except TestStepSkipped as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "skipped", message, exc)
        results.mark_skipped(name, message)
        _default_emit(f"  SKIP: {name}: {message}")
        return None
    except (TestStepFailed, AkuvoxError) as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(name, message)
        _default_emit(f"  ✗ {name}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {_first_line(str(exc))}"
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(name, message)
        _default_emit(f"  ✗ {name}: {message}")
        traceback.print_exc()
        return None

    _finish_diagnostic_step(results, "passed")
    results.mark_passed(name)
    _default_emit(f"  OK:   {name}")
    return result


async def run_step[T](  # pragma: no cover
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
        _default_emit(f"  ⊘ {label} skipped: {message}")
        return None
    except TestStepFailed as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        _default_emit(f"  ✗ {label}: {message}")
        return None
    except AkuvoxError as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        _default_emit(f"  ✗ {label}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {_first_line(str(exc))}"
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        _default_emit(f"  ✗ {label}: {message}")
        traceback.print_exc()
        return None

    _finish_diagnostic_step(results, "passed")
    results.mark_passed(label)
    return result


def _begin_diagnostic_step(
    results: TestResults, label: str
) -> None:  # pragma: no cover  # noqa: E501
    """Begin diagnostics for a test step when enabled."""
    if results.diagnostics is not None:
        results.diagnostics.begin_test(label)


def _finish_diagnostic_step(  # pragma: no cover
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


def _install_probed_capabilities(  # pragma: no cover
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


def create_device(  # pragma: no cover
    device_kwargs: dict[str, Any],
    diagnostics: DiagnosticReport,
) -> AkuvoxDevice:
    """Create an AkuvoxDevice instrumented for diagnostic capture."""
    device = AkuvoxDevice(**device_kwargs)
    _instrument_device(device, diagnostics)
    return device


def _instrument_device(
    device: AkuvoxDevice, diagnostics: DiagnosticReport
) -> None:  # pragma: no cover  # noqa: E501
    """Attach diagnostic HTTP capture hooks to a device instance."""
    http = device._http  # noqa: SLF001 - example diagnostics need raw exchanges.
    original_request = http._request  # noqa: SLF001
    original_request_raw = http._request_raw  # noqa: SLF001
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

    async def diagnostic_request_raw(
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
        allow_redirects: bool = True,
    ) -> tuple[int, str]:
        """Capture raw request metadata before delegating to the HTTP client."""
        endpoint = path if path.startswith("/") else f"/{path}"
        diagnostics.begin_http_event(
            method=method,
            endpoint=endpoint,
            data=data,
            params=params,
        )
        try:
            status, body_text = await original_request_raw(
                method,
                path,
                params=params,
                data=data,
                timeout=timeout,
                allow_redirects=allow_redirects,
            )
        except Exception as exc:
            diagnostics.record_exception(exc)
            raise
        body, _json_error = _decode_json_body(body_text)
        diagnostics.record_http_response(
            status=status,
            body_text=body_text,
            body=body,
            retcode=None,
            retmsg=None,
            data={},
        )
        return status, body_text

    http._request_raw = diagnostic_request_raw  # type: ignore[method-assign]  # noqa: SLF001
    http._handle_response = _build_diagnostic_response_handler(  # type: ignore[assignment,method-assign]  # noqa: SLF001
        diagnostics,
        original_handle_response,
    )


def _build_diagnostic_response_handler(  # pragma: no cover
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


def _parse_response_shape(  # pragma: no cover
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


def _parse_diagnostic_envelope(  # pragma: no cover
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


def _missing_envelope_message(body: object) -> str:  # pragma: no cover
    """Return a parse error message that exposes schema keys, not values."""
    if isinstance(body, dict):
        keys = sorted(str(key) for key in body)
        return f"Missing envelope field 'retcode'; keys={keys}"
    return f"Missing envelope fields in {type(body).__name__} response"


def _extract_retmsg(body: dict[str, Any]) -> str:  # pragma: no cover
    """Return the device message field, preserving firmware spelling."""
    message = body.get("retmsg", body.get("message", ""))
    if isinstance(message, str):
        return message
    return str(message) if message is not None else ""


def print_header(title: str) -> None:  # pragma: no cover
    """Print a section header."""
    _default_emit(f"\n{SEPARATOR}")
    _default_emit(f"  {title}")
    _default_emit(SEPARATOR)


async def test_get_info(
    device: AkuvoxDevice, *, redact_stdout: bool = False
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Retrieve device info."""
    print_header("GET DEVICE INFO (/api/system/info)")
    info = await device.get_info()
    _default_emit(f"  Model:            {info.model}")
    mac = _display_value("MAC", info.mac_address, redact_stdout=redact_stdout)
    _default_emit(f"  MAC:              {mac}")
    _default_emit(f"  Firmware:         {info.firmware_version}")
    _default_emit(f"  Hardware:         {info.hardware_version}")
    _default_emit(f"  Uptime:           {info.uptime}")
    _default_emit(f"  Web Language:     {info.web_language}")
    _default_emit("  ✓ get_info() OK")


async def test_get_status(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Retrieve device status."""
    print_header("GET DEVICE STATUS (/api/system/status)")
    status = await device.get_status()
    _default_emit(f"  Unix Time:        {status.unix_time}")
    _default_emit(f"  Uptime:           {status.uptime}")
    _default_emit("  ✓ get_status() OK")


async def test_list_users(
    device: AkuvoxDevice, *, redact_stdout: bool = False
) -> None:  # pragma: no cover  # noqa: E501
    """Test: List all users."""
    print_header("LIST USERS (/api/user/get)")
    users = await device.list_users()
    _default_emit(f"  Found {len(users)} user(s)")
    for user in users:
        name = _display_value("Name", user.name, redact_stdout=redact_stdout)
        user_id = _display_value("UserID", user.user_id, redact_stdout=redact_stdout)
        pin_display = _display_value(
            "PrivatePIN",
            user.private_pin,
            redact_stdout=redact_stdout,
        )
        _default_emit(
            f"    ID={user.id}  Name={name}  "
            f"UserID={user_id}  PIN={pin_display}  "
            f"ScheduleRelay={user.schedule_relay}"
        )
    _default_emit("  ✓ list_users() OK")


async def test_get_relay_status(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Get relay status."""
    print_header("GET RELAY STATUS (/api/relay/status)")
    status = await device.get_relay_status()
    _default_emit(f"  Raw status: {status}")
    _default_emit("  ✓ get_relay_status() OK")


async def test_get_device_config(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Get full device configuration."""
    print_header("GET DEVICE CONFIG (/api/config/get)")
    cfg = await device.get_device_config()
    _default_emit(f"  Total keys:       {len(cfg)}")
    # Show sample keys by category
    categories: dict[str, int] = {}
    for key in cfg.keys():
        parts = key.split(".")
        cat = ".".join(parts[:2]) if len(parts) >= 2 else key
        categories[cat] = categories.get(cat, 0) + 1
    _default_emit(f"  Categories:       {len(categories)}")
    for cat, count in sorted(categories.items())[:10]:
        _default_emit(f"    {cat}: {count} keys")
    if len(categories) > 10:
        _default_emit(f"    ... and {len(categories) - 10} more categories")
    _default_emit("  ✓ get_device_config() OK")


async def test_list_schedules(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: List all schedules."""
    print_header("LIST SCHEDULES (/api/schedule/get)")
    schedules = await device.list_schedules()
    _default_emit(f"  Found {len(schedules)} schedule(s)")
    for sched in schedules:
        name = _display_value("Name", sched.name, redact_stdout=redact_stdout)
        _default_emit(
            f"    ID={sched.id}  Name={name}  "
            f"Type={sched.schedule_type}  "
            f"Time={sched.time_start}-{sched.time_end}  "
            f"Week={sched.week}"
        )
    _default_emit("  ✓ list_schedules() OK")


async def test_list_groups(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: List all groups."""
    print_header("LIST GROUPS (/api/group/get)")
    groups = await device.list_groups()
    _default_emit(f"  Found {len(groups)} group(s)")
    for grp in groups:
        name = _display_value("Name", grp.name, redact_stdout=redact_stdout)
        _default_emit(f"    ID={grp.id}  Name={name}")
    _default_emit("  ✓ list_groups() OK")


async def test_list_contacts(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: List all contacts."""
    print_header("LIST CONTACTS (/api/contact/get)")
    contacts = await device.list_contacts()
    _default_emit(f"  Found {len(contacts)} contact(s)")
    for c in contacts:
        name = _display_value("Name", c.name, redact_stdout=redact_stdout)
        phone = _display_value("Phone", c.phone, redact_stdout=redact_stdout)
        _default_emit(f"    ID={c.id}  Name={name}  Phone={phone}  Group={c.group}")
    _default_emit("  ✓ list_contacts() OK")


async def test_get_door_logs(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: Retrieve door access logs."""
    print_header("GET DOOR LOGS (/api/doorlog/get)")
    entries = await device.get_door_logs()
    _default_emit(f"  Found {len(entries)} door log entry(ies)")
    for entry in entries[:5]:
        name = _display_value("Name", entry.name, redact_stdout=redact_stdout)
        _default_emit(
            f"    ID={entry.id}  {entry.date} {entry.time}  "
            f"Name={name}  Type={entry.door_type}  "
            f"Status={entry.status}"
        )
    if len(entries) > 5:
        _default_emit(f"    ... and {len(entries) - 5} more")
    _default_emit("  ✓ get_door_logs() OK")

    # Test pagination — page 1 should return the same or subset
    page1 = await device.get_door_logs(page=1)
    _default_emit(f"  Page 1: {len(page1)} entry(ies)")
    _default_emit("  ✓ get_door_logs(page=1) OK")


async def test_get_call_logs(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    redact_stdout: bool = False,
) -> None:
    """Test: Retrieve call logs."""
    print_header("GET CALL LOGS (/api/calllog/get)")
    entries = await device.get_call_logs()
    _default_emit(f"  Found {len(entries)} call log entry(ies)")
    for entry in entries[:5]:
        name = _display_value("Name", entry.name, redact_stdout=redact_stdout)
        _default_emit(
            f"    ID={entry.id}  {entry.date} {entry.time}  "
            f"Name={name}  Type={entry.call_type}  "
            f"Count={entry.count}"
        )
    if len(entries) > 5:
        _default_emit(f"    ... and {len(entries) - 5} more")
    _default_emit("  ✓ get_call_logs() OK")

    # Test pagination — page 1 should return the same or subset
    page1 = await device.get_call_logs(page=1)
    _default_emit(f"  Page 1: {len(page1)} entry(ies)")
    _default_emit("  ✓ get_call_logs(page=1) OK")


async def test_add_user(
    device: AkuvoxDevice, *, redact_stdout: bool = False
) -> str:  # pragma: no cover  # noqa: E501
    """Test: Add a test user and return its internal ID."""
    print_header("ADD USER (/api/user/set action:add)")
    test_name = _TEST_USER_NAME
    test_user_id = _TEST_USER_ID
    test_pin = _TEST_USER_PIN

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
    _default_emit(f"  Added user: {name} (UserID={user_id}, PIN={pin})")
    _default_emit("  ✓ add_user() OK")

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    # Search for the newly added user (page 1 has all items)
    users = await device.list_users()
    for user in users:
        if user.user_id == test_user_id and user.id is not None:
            _default_emit(f"  → Assigned internal ID: {user.id}")
            return user.id

    msg = "User added but internal ID not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_modify_user(  # pragma: no cover
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
    _default_emit(f"  Modified user ID={internal_id}: PIN changed to {pin}")
    _default_emit("  ✓ modify_user() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_delete_user(
    device: AkuvoxDevice, internal_id: str
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Delete the test user."""
    print_header("DELETE USER (/api/user/set action:del)")
    await device.delete_user(id=internal_id)
    _default_emit(f"  Deleted user ID={internal_id}")
    _default_emit("  ✓ delete_user() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_trigger_relay(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Trigger relay 1.

    Uses ``delay=0``. Door-phone classes route through
    ``/api/relay/trig``. IT83-class FCGI dispatch now raises an
    actionable guard because real OpenDoor unlocks require
    relay-specific credentials; use ``--open-door`` to exercise that
    credentialed path.
    """
    print_header("TRIGGER RELAY (/api/relay/trig | /fcgi/do?action=OpenDoor)")
    await device.trigger_relay(num=1)
    _default_emit("  Triggered relay 1")
    _default_emit("  ✓ trigger_relay() OK")


async def test_open_door(  # pragma: no cover
    device: AkuvoxDevice,
    *,
    user: str,
    password: str,
    redact_stdout: bool = False,
) -> None:
    """Test: Trigger OpenDoor HTTP relay 1 with relay-specific credentials."""
    print_header("OPEN DOOR HTTP (/fcgi/do?action=OpenDoor)")
    display_user = _display_value("UserName", user, redact_stdout=redact_stdout)
    display_password = _display_value(
        "Password",
        password,
        redact_stdout=True,
    )
    _default_emit(f"  UserName: {display_user}")
    _default_emit(f"  Password: {display_password}")
    await device.open_door_http(user=user, password=password)
    _default_emit("  Triggered OpenDoor HTTP door 1")
    _default_emit("  ✓ open_door_http() OK")


async def test_add_schedule(device: AkuvoxDevice) -> str:  # pragma: no cover
    """Test: Add a test schedule and return its internal ID."""
    print_header("ADD SCHEDULE (/api/schedule/set action:add)")
    test_name = _TEST_SCHEDULE_NAME

    await device.add_schedule(
        schedule_type="1",
        name=test_name,
        week="12345",
        time_start="08:00",
        time_end="18:00",
    )
    _default_emit(f"  Added schedule: {test_name} (Weekly, Mon-Fri 08-18)")
    _default_emit("  ✓ add_schedule() OK")

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    schedules = await device.list_schedules()
    for sched in schedules:
        if sched.name == test_name and sched.id is not None:
            _default_emit(f"  → Assigned internal ID: {sched.id}")
            return sched.id

    msg = "Schedule added but internal ID not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_modify_schedule(
    device: AkuvoxDevice, internal_id: str
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Modify the test schedule."""
    print_header("MODIFY SCHEDULE (/api/schedule/set)")
    await device.modify_schedule(
        id=internal_id,
        name="pylocal-test-modified",
        time_start="09:00",
        time_end="17:00",
    )
    _default_emit(f"  Modified schedule ID={internal_id}: name + times changed")
    _default_emit("  ✓ modify_schedule() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_delete_schedule(
    device: AkuvoxDevice, internal_id: str
) -> None:  # pragma: no cover  # noqa: E501
    """Test: Delete the test schedule."""
    print_header("DELETE SCHEDULE (/api/schedule/set action:del)")
    await device.delete_schedule(id=internal_id)
    _default_emit(f"  Deleted schedule ID={internal_id}")
    _default_emit("  ✓ delete_schedule() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_add_group(device: AkuvoxDevice) -> str:  # pragma: no cover
    """Test: Add a group and return its internal ID."""
    print_header("ADD GROUP (/api/group/add)")
    await device.add_group(name=_TEST_GROUP_NAME)
    _default_emit("  Sent add_group(name='__test_group__')")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    groups = await device.list_groups()
    for grp in groups:
        if grp.name == _TEST_GROUP_NAME and grp.id is not None:
            _default_emit(f"  ✓ add_group() OK — ID={grp.id}")
            return grp.id
    msg = "Group created but not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_delete_group(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Delete the test group."""
    print_header("DELETE GROUP (/api/group/del)")
    await device.delete_group(id=internal_id)
    _default_emit(f"  Deleted group ID={internal_id}")
    _default_emit("  ✓ delete_group() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_add_contact(device: AkuvoxDevice) -> str:  # pragma: no cover
    """Test: Add a contact and return its internal ID."""
    print_header("ADD CONTACT (/api/contact/set action:add)")
    await device.add_contact(
        name=_TEST_CONTACT_NAME,
        phone="5550000",
        group="Default",
    )
    _default_emit("  Sent add_contact(name='__test_contact__')")
    _default_emit("  ✓ add_contact() OK")

    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    contacts = await device.list_contacts()
    for c in contacts:
        if c.name == _TEST_CONTACT_NAME and c.id is not None:
            _default_emit(f"  → Assigned internal ID: {c.id}")
            return c.id
    msg = "Contact created but not found in list"
    _default_emit(f"  ⚠ {msg}")
    raise TestStepFailed(msg)


async def test_delete_contact(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Delete the test contact."""
    print_header("DELETE CONTACT (/api/contact/set action:del)")
    await device.delete_contact(id=internal_id)
    _default_emit(f"  Deleted contact ID={internal_id}")
    _default_emit("  ✓ delete_contact() OK")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)


async def test_modify_contact(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Modify a contact's group membership."""
    print_header("MODIFY CONTACT (/api/contact/set action:set)")
    await device.modify_contact(id=internal_id, group="Default")
    _default_emit(f"  Modified contact ID={internal_id} group→Default")
    await asyncio.sleep(_MUTATION_SETTLE_SECS)
    contacts = await device.list_contacts()
    for c in contacts:
        if c.id == internal_id:
            _default_emit(f"  → Group is now: {c.group}")
            break
    _default_emit("  ✓ modify_contact() OK")


async def _check_validation(
    label: str, coro: Coroutine[object, object, None]
) -> None:  # pragma: no cover  # noqa: E501
    """Run a single validation check and print the result."""
    try:
        await coro
        _default_emit(f"  ✗ Should have raised for {label}")
    except AkuvoxValidationError as exc:
        _default_emit(f"  ✓ {label}: {exc}")


async def test_validation() -> None:  # pragma: no cover
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

    _default_emit("  ✓ All validation checks passed")


async def test_discover_config_keys(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Discover all configuration key categories."""
    print_header("DISCOVER CONFIG KEYS")
    cfg = await device.get_device_config()
    categories: dict[str, int] = {}
    for key in cfg.keys():
        parts = key.split(".")
        cat = ".".join(parts[:2]) if len(parts) >= 2 else key
        categories[cat] = categories.get(cat, 0) + 1
    _default_emit(f"  Total keys:       {len(cfg)}")
    _default_emit(f"  Categories:       {len(categories)}")
    for cat, count in sorted(categories.items()):
        _default_emit(f"    {cat}: {count} keys")
    _default_emit("  ✓ Key discovery OK")


async def _run_read_tests(  # pragma: no cover
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


async def test_set_device_config(device: AkuvoxDevice) -> None:  # pragma: no cover
    """Test: Set and verify a device configuration value."""
    print_header("SET DEVICE CONFIG (/api/config/set)")
    cfg = await device.get_device_config()
    original = cfg.get(_CONFIG_SET_TOGGLE_KEY)
    if original is None:
        await _probe_config_set_noop(device, cfg)
        return
    await _probe_config_set_toggle_with_restore(device, original)


async def _probe_config_set_noop(device: AkuvoxDevice, cfg: DeviceConfig) -> None:
    """Exercise config.set with the first accepted same-value fallback."""
    rejections: list[tuple[str, BaseException]] = []
    saw_candidate = False

    for key, current in _iter_config_set_noop_candidates(cfg):
        saw_candidate = True
        _default_emit(
            f"  {_CONFIG_SET_TOGGLE_KEY} not present; probing {key} "
            "with unchanged value"
        )
        try:
            await device.set_device_config({key: current})
        except _CONFIG_SET_NOOP_REJECTION_ERRORS as exc:
            rejections.append((key, exc))
            _default_emit(f"  ⚠ {key} rejected: {_first_line(str(exc))}")
            continue

        _default_emit(f"  Set {key} to its current value")
        _default_emit("  ✓ No restore needed; value was unchanged")
        _default_emit("  ✓ set_device_config() OK")
        return

    if not saw_candidate:
        msg = (
            f"Config key {_CONFIG_SET_TOGGLE_KEY!r} not present and no safe "
            "fallback key available"
        )
        _default_emit(f"  ⚠ {msg}; skipping")
        raise TestStepSkipped(msg)

    msg = _format_config_set_noop_rejections(rejections)
    raise TestStepFailed(msg) from rejections[-1][1]


def _iter_config_set_noop_candidates(cfg: DeviceConfig) -> Iterator[tuple[str, str]]:
    """Yield present same-value config.set fallback candidates in probe order."""
    for key in _CONFIG_SET_NOOP_KEYS:
        current = cfg.get(key)
        if current is not None:
            yield key, current


def _format_config_set_noop_rejections(
    rejections: list[tuple[str, BaseException]],
) -> str:
    """Summarize rejected same-value config.set fallback attempts."""
    details = "; ".join(f"{key}: {_first_line(str(exc))}" for key, exc in rejections)
    return f"All safe config.set fallback candidates were rejected ({details})"


async def _probe_config_set_toggle_with_restore(
    device: AkuvoxDevice,
    original: str,
) -> None:
    """Toggle the legacy probe key and restore it afterward."""
    key = _CONFIG_SET_TOGGLE_KEY
    primary_error = False
    try:
        new_val = "7" if original != "7" else "6"
        await device.set_device_config({key: new_val})
        _default_emit(f"  Set {key} = {new_val}")
        cfg2 = await device.get_device_config()
        readback = cfg2.get(key)
        if readback == new_val:
            _default_emit(f"  ✓ Read-back confirmed: {readback}")
            _default_emit("  ✓ set_device_config() OK")
        else:
            msg = f"Read-back mismatch: {readback!r}"
            raise TestStepFailed(msg)
    except Exception:
        primary_error = True
        raise
    finally:
        try:
            await device.set_device_config({key: original})
            _default_emit(f"  Restored {key} = {original}")
        except Exception as exc:
            if not primary_error:
                raise
            _default_emit(f"  ⚠ Restore failed after earlier failure: {exc}")


async def test_verify_user_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test user was deleted."""
    print_header("VERIFY USER DELETION")
    users = await device.list_users()
    found = any(u.id == internal_id for u in users)
    if found:
        raise TestStepFailed("User still present after delete")
    _default_emit("  ✓ User successfully removed")


async def test_verify_schedule_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test schedule was deleted."""
    print_header("VERIFY SCHEDULE DELETION")
    scheds = await device.list_schedules()
    found = any(s.id == internal_id for s in scheds)
    if found:
        raise TestStepFailed("Schedule still present after delete")
    _default_emit("  ✓ Schedule successfully removed")


async def test_verify_group_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test group was deleted."""
    print_header("VERIFY GROUP DELETION")
    grps = await device.list_groups()
    found = any(g.id == internal_id for g in grps)
    if found:
        raise TestStepFailed("Group still present after delete")
    _default_emit("  ✓ Group successfully removed")


async def test_verify_contact_deletion(  # pragma: no cover
    device: AkuvoxDevice,
    internal_id: str,
) -> None:
    """Test: Verify the test contact was deleted."""
    print_header("VERIFY CONTACT DELETION")
    contacts = await device.list_contacts()
    found = any(c.id == internal_id for c in contacts)
    if found:
        raise TestStepFailed("Contact still present after delete")
    _default_emit("  ✓ Contact successfully removed")


# aislop-ignore-next-line complexity/function-too-long complexity/too-many-params
async def _run_write_tests(  # pragma: no cover  # noqa: C901
    device_kwargs: dict[str, Any],
    results: TestResults,
    *,
    capabilities: DeviceCapabilities,
    open_door: bool,
    open_door_user: str | None,
    open_door_password: str | None,
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
        internal_id: str | None = None
        user_deleted = False
        try:
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
                        coro_factory=lambda: test_verify_user_deletion(
                            device, internal_id
                        ),
                    )
                    user_deleted = results.was_passed("verify_user_deletion")
                else:
                    skip_step(
                        results,
                        "verify_user_deletion",
                        "requires delete_user to pass",
                    )
        finally:
            if internal_id is not None and not user_deleted:
                await _best_effort_delete(lambda: device.delete_user(id=internal_id))
            elif internal_id is None and _step_failed(results, "add_user"):
                await _best_effort_delete(
                    lambda: _cleanup_user_by_user_id(device, _TEST_USER_ID)
                )

    # Device needs cooldown between request groups
    _default_emit("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Schedule add + delete
        sched_id: str | None = None
        schedule_deleted = False
        try:
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
                    schedule_deleted = results.was_passed("verify_schedule_deletion")
                else:
                    skip_step(
                        results,
                        "verify_schedule_deletion",
                        "requires delete_schedule to pass",
                    )
        finally:
            if sched_id is not None and not schedule_deleted:
                await _best_effort_delete(lambda: device.delete_schedule(id=sched_id))
            elif sched_id is None and _step_failed(results, "add_schedule"):
                await _best_effort_delete(
                    lambda: _cleanup_schedule_by_name(device, _TEST_SCHEDULE_NAME)
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
        await _run_open_door_write_step(
            device,
            results,
            open_door=open_door,
            open_door_user=open_door_user,
            open_door_password=open_door_password,
            redact_stdout=redact_stdout,
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
    _default_emit("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Group add + delete
        group_id: str | None = None
        group_deleted = False
        try:
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
                        coro_factory=lambda: test_verify_group_deletion(
                            device, group_id
                        ),
                    )
                    group_deleted = results.was_passed("verify_group_deletion")
                else:
                    skip_step(
                        results,
                        "verify_group_deletion",
                        "requires delete_group to pass",
                    )
        finally:
            if group_id is not None and not group_deleted:
                await _best_effort_delete(lambda: device.delete_group(id=group_id))
            elif group_id is None and _step_failed(results, "add_group"):
                await _best_effort_delete(
                    lambda: _cleanup_group_by_name(device, _TEST_GROUP_NAME)
                )

    # Cooldown before contact tests
    _default_emit("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Contact add + modify + delete
        contact_id: str | None = None
        contact_deleted = False
        try:
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
                    contact_deleted = results.was_passed("verify_contact_deletion")
                else:
                    skip_step(
                        results,
                        "verify_contact_deletion",
                        "requires delete_contact to pass",
                    )
        finally:
            if contact_id is not None and not contact_deleted:
                await _best_effort_delete(lambda: device.delete_contact(id=contact_id))
            elif contact_id is None and _step_failed(results, "add_contact"):
                await _best_effort_delete(
                    lambda: _cleanup_contact_by_name(device, _TEST_CONTACT_NAME)
                )

    # Cooldown before read tests
    _default_emit("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)


async def _run_open_door_write_step(  # pragma: no cover
    device: AkuvoxDevice,
    results: TestResults,
    *,
    open_door: bool,
    open_door_user: str | None,
    open_door_password: str | None,
    redact_stdout: bool,
) -> None:
    """Run or skip the opt-in OpenDoor HTTP write-test step."""
    if not open_door or open_door_user is None or open_door_password is None:
        skip_step(results, "open_door_http", _open_door_skip_reason())
        return
    await run_step(
        results,
        "open_door_http",
        test_open_door(
            device,
            user=open_door_user,
            password=open_door_password,
            redact_stdout=redact_stdout,
        ),
    )


def _open_door_skip_reason() -> str:  # pragma: no cover
    """Return the user-facing reason for skipping the OpenDoor write step."""
    return (
        "requires --open-door with --open-door-user and "
        f"--open-door-pass or {_OPEN_DOOR_PASSWORD_ENV}"
    )


async def _probe_device_capabilities(  # pragma: no cover
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
    _default_emit(
        f"  Device class: {capabilities.device_class} "
        f"(firmware {capabilities.firmware_version})"
    )
    _default_emit(f"  Supported capabilities: {supported}")
    return capabilities
