# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report read-only diagnostic steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._capability_types import Capability
from pylocal_akuvox._diagnostic_redaction import _display_value
from pylocal_akuvox._report_instrumentation import _install_probed_capabilities
from pylocal_akuvox._report_steps import (
    TestResults,
    _default_emit,
    print_header,
    run_step,
    step,
)

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox.device import AkuvoxDevice


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
