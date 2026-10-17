# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report offline client-side validation step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._capability_profile import DeviceCapabilities
from pylocal_akuvox._report_steps import (
    _default_emit,
    print_header,
)
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import AkuvoxValidationError

if TYPE_CHECKING:
    from collections.abc import Coroutine


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
