# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report write-test orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pylocal_akuvox._capability_types import Capability
from pylocal_akuvox._report_config_probe import test_set_device_config
from pylocal_akuvox._report_instrumentation import (
    _install_probed_capabilities,
    create_device,
)
from pylocal_akuvox._report_steps import (
    TestResults,
    _default_emit,
    run_step,
    skip_step,
    step,
)
from pylocal_akuvox._report_write_chains import (
    _run_contact_write_tests,
    _run_group_write_tests,
    _run_schedule_write_tests,
    _run_user_write_tests,
)
from pylocal_akuvox._report_write_steps import (
    _MUTATION_SETTLE_SECS,
    test_open_door,
    test_trigger_relay,
)

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox.device import AkuvoxDevice

_OPEN_DOOR_PASSWORD_ENV = "AKUVOX_OPEN_DOOR_PASSWORD"


@dataclass(frozen=True, kw_only=True)
class _WriteOptions:
    """Opt-in OpenDoor credentials and stdout redaction for write tests."""

    open_door: bool
    open_door_user: str | None
    open_door_password: str | None = field(repr=False)
    redact_stdout: bool


async def _run_write_tests(  # pragma: no cover
    device_kwargs: dict[str, Any],
    results: TestResults,
    *,
    capabilities: DeviceCapabilities,
    options: _WriteOptions,
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
        await _run_user_write_tests(
            device, results, capabilities, redact_stdout=options.redact_stdout
        )

    # Device needs cooldown between request groups
    await _settle_device()

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Schedule add + delete
        await _run_schedule_write_tests(device, results, capabilities)
        await _run_relay_and_config_write_tests(device, results, capabilities, options)

    # Cooldown before group tests
    await _settle_device()

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Group add + delete
        await _run_group_write_tests(device, results, capabilities)

    # Cooldown before contact tests
    await _settle_device()

    async with create_device(device_kwargs, results.diagnostics) as device:
        _install_probed_capabilities(device, capabilities)
        # Contact add + modify + delete
        await _run_contact_write_tests(device, results, capabilities)

    # Cooldown before read tests
    await _settle_device()


async def _settle_device() -> None:
    """Wait for the device to settle between write-test request groups."""
    _default_emit("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)


async def _run_relay_and_config_write_tests(
    device: AkuvoxDevice,
    results: TestResults,
    capabilities: DeviceCapabilities,
    options: _WriteOptions,
) -> None:
    """Run the relay trigger, opt-in OpenDoor, and config set steps."""
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
    await _run_open_door_write_step(device, results, options=options)

    # Config set + read-back verification
    await step(
        results=results,
        name="set_device_config",
        capability=Capability.DEVICE_CONFIG_SET,
        capabilities=capabilities,
        coro_factory=lambda: test_set_device_config(device),
    )


async def _run_open_door_write_step(  # pragma: no cover
    device: AkuvoxDevice,
    results: TestResults,
    *,
    options: _WriteOptions,
) -> None:
    """Run or skip the opt-in OpenDoor HTTP write-test step."""
    if (
        not options.open_door
        or options.open_door_user is None
        or options.open_door_password is None
    ):
        skip_step(results, "open_door_http", _open_door_skip_reason())
        return
    await run_step(
        results,
        "open_door_http",
        test_open_door(
            device,
            user=options.open_door_user,
            password=options.open_door_password,
            redact_stdout=options.redact_stdout,
        ),
    )


def _open_door_skip_reason() -> str:  # pragma: no cover
    """Return the user-facing reason for skipping the OpenDoor write step."""
    return (
        "requires --open-door with --open-door-user and "
        f"--open-door-pass or {_OPEN_DOOR_PASSWORD_ENV}"
    )
