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

    # Digest auth with write tests
    AKUVOX_PASSWORD=secret uv run examples/mvp_test.py 192.168.1.100 \
        --auth digest --user admin --write

"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
import traceback
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Coroutine

from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
)
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
    AkuvoxValidationError,
)

SEPARATOR = "-" * 60
# Akuvox devices need time to persist mutations before the next
# API call; two seconds is sufficient based on testing.
_MUTATION_SETTLE_SECS = 2


class TestStepFailed(Exception):
    """Expected diagnostic step failure that does not need a traceback."""


class TestStepSkipped(Exception):
    """Diagnostic step skip with a reason for the summary."""


class TestResults:
    """Collect diagnostic test outcomes for the final summary."""

    def __init__(self) -> None:
        """Initialize empty result buckets."""
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.skipped: list[tuple[str, str]] = []

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


def skip_step(results: TestResults, label: str, reason: str) -> None:
    """Record and print a skipped diagnostic step."""
    results.mark_skipped(label, reason)
    print(f"  ⊘ {label} skipped: {reason}")


async def run_step[T](
    results: TestResults,
    label: str,
    coro: Awaitable[T],
) -> T | None:
    """Run one diagnostic coroutine and continue after non-fatal errors."""
    try:
        result = await coro
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except (AkuvoxConnectionError, AkuvoxAuthenticationError):
        raise
    except TestStepSkipped as exc:
        message = str(exc)
        results.mark_skipped(label, message)
        print(f"  ⊘ {label} skipped: {message}")
        return None
    except TestStepFailed as exc:
        message = str(exc)
        results.mark_failed(label, message)
        print(f"  ✗ {label}: {message}")
        return None
    except AkuvoxError as exc:
        message = str(exc)
        results.mark_failed(label, message)
        print(f"  ✗ {label}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {exc}"
        results.mark_failed(label, message)
        print(f"  ✗ {label}: {message}")
        traceback.print_exc()
        return None

    results.mark_passed(label)
    return result


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


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


async def test_get_info(device: AkuvoxDevice) -> None:
    """Test: Retrieve device info."""
    print_header("GET DEVICE INFO (/api/system/info)")
    info = await device.get_info()
    print(f"  Model:            {info.model}")
    print(f"  MAC:              {info.mac_address}")
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


async def test_list_users(device: AkuvoxDevice) -> None:
    """Test: List all users."""
    print_header("LIST USERS (/api/user/get)")
    users = await device.list_users()
    print(f"  Found {len(users)} user(s)")
    for user in users:
        pin_display = user.private_pin or "(none)"
        print(
            f"    ID={user.id}  Name={user.name}  "
            f"UserID={user.user_id}  PIN={pin_display}  "
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


async def test_list_schedules(device: AkuvoxDevice) -> None:
    """Test: List all schedules."""
    print_header("LIST SCHEDULES (/api/schedule/get)")
    schedules = await device.list_schedules()
    print(f"  Found {len(schedules)} schedule(s)")
    for sched in schedules:
        print(
            f"    ID={sched.id}  Name={sched.name}  "
            f"Type={sched.schedule_type}  "
            f"Time={sched.time_start}-{sched.time_end}  "
            f"Week={sched.week}"
        )
    print("  ✓ list_schedules() OK")


async def test_list_groups(device: AkuvoxDevice) -> None:
    """Test: List all groups."""
    print_header("LIST GROUPS (/api/group/get)")
    groups = await device.list_groups()
    print(f"  Found {len(groups)} group(s)")
    for grp in groups:
        print(f"    ID={grp.id}  Name={grp.name}")
    print("  ✓ list_groups() OK")


async def test_list_contacts(device: AkuvoxDevice) -> None:
    """Test: List all contacts."""
    print_header("LIST CONTACTS (/api/contact/get)")
    contacts = await device.list_contacts()
    print(f"  Found {len(contacts)} contact(s)")
    for c in contacts:
        print(f"    ID={c.id}  Name={c.name}  Phone={c.phone}  Group={c.group}")
    print("  ✓ list_contacts() OK")


async def test_get_door_logs(device: AkuvoxDevice) -> None:
    """Test: Retrieve door access logs."""
    print_header("GET DOOR LOGS (/api/doorlog/get)")
    entries = await device.get_door_logs()
    print(f"  Found {len(entries)} door log entry(ies)")
    for entry in entries[:5]:
        print(
            f"    ID={entry.id}  {entry.date} {entry.time}  "
            f"Name={entry.name}  Type={entry.door_type}  "
            f"Status={entry.status}"
        )
    if len(entries) > 5:
        print(f"    ... and {len(entries) - 5} more")
    print("  ✓ get_door_logs() OK")

    # Test pagination — page 1 should return the same or subset
    page1 = await device.get_door_logs(page=1)
    print(f"  Page 1: {len(page1)} entry(ies)")
    print("  ✓ get_door_logs(page=1) OK")


async def test_get_call_logs(device: AkuvoxDevice) -> None:
    """Test: Retrieve call logs."""
    print_header("GET CALL LOGS (/api/calllog/get)")
    entries = await device.get_call_logs()
    print(f"  Found {len(entries)} call log entry(ies)")
    for entry in entries[:5]:
        print(
            f"    ID={entry.id}  {entry.date} {entry.time}  "
            f"Name={entry.name}  Type={entry.call_type}  "
            f"Count={entry.count}"
        )
    if len(entries) > 5:
        print(f"    ... and {len(entries) - 5} more")
    print("  ✓ get_call_logs() OK")

    # Test pagination — page 1 should return the same or subset
    page1 = await device.get_call_logs(page=1)
    print(f"  Page 1: {len(page1)} entry(ies)")
    print("  ✓ get_call_logs(page=1) OK")


async def test_add_user(device: AkuvoxDevice) -> str:
    """Test: Add a test user and return its internal ID."""
    print_header("ADD USER (/api/user/set action:add)")
    test_name = "pylocal-test"
    test_user_id = "9999"

    await device.add_user(
        name=test_name,
        user_id=test_user_id,
        private_pin="1234",
        web_relay="0",
        schedule_relay="1001-1",
        lift_floor_num="0",
    )
    print(f"  Added user: {test_name} (UserID={test_user_id}, PIN=1234)")
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


async def test_modify_user(device: AkuvoxDevice, internal_id: str) -> None:
    """Test: Modify the test user's PIN."""
    print_header("MODIFY USER (/api/user/set)")
    await device.modify_user(id=internal_id, private_pin="5678")
    print(f"  Modified user ID={internal_id}: PIN changed to 5678")
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
    """Test: Trigger relay 1 with auto-close."""
    print_header("TRIGGER RELAY (/api/relay/trig)")
    await device.trigger_relay(num=1, delay=1)
    print("  Triggered relay 1 (auto-close, delay=1s)")
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
    """Test: Client-side validation (no device needed)."""
    print_header("CLIENT-SIDE VALIDATION (no network)")

    device = AkuvoxDevice("0.0.0.0")

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


async def _run_read_tests(device: AkuvoxDevice, results: TestResults) -> None:
    """Run all read-only tests against a connected device."""
    await run_step(results, "GET DEVICE INFO", test_get_info(device))
    await run_step(results, "GET DEVICE STATUS", test_get_status(device))
    await run_step(results, "LIST USERS", test_list_users(device))
    await run_step(results, "GET RELAY STATUS", test_get_relay_status(device))
    await run_step(results, "GET DEVICE CONFIG", test_get_device_config(device))
    await run_step(results, "DISCOVER CONFIG KEYS", test_discover_config_keys(device))
    await run_step(results, "LIST SCHEDULES", test_list_schedules(device))
    await run_step(results, "LIST GROUPS", test_list_groups(device))
    await run_step(results, "LIST CONTACTS", test_list_contacts(device))
    await run_step(results, "GET DOOR LOGS", test_get_door_logs(device))
    await run_step(results, "GET CALL LOGS", test_get_call_logs(device))


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
) -> None:
    """Run write tests (user/schedule CRUD, relay trigger)."""
    async with AkuvoxDevice(**device_kwargs) as device:
        # User add + delete FIRST — before any other
        # requests to avoid CGI state corruption.
        internal_id = await run_step(results, "ADD USER", test_add_user(device))
        if internal_id is None:
            reason = "requires internal ID from ADD USER"
            skip_step(results, "MODIFY USER", reason)
            skip_step(results, "DELETE USER", reason)
            skip_step(results, "VERIFY USER DELETION", reason)
        else:
            await run_step(
                results,
                "MODIFY USER",
                test_modify_user(device, internal_id),
            )
            await run_step(
                results,
                "DELETE USER",
                test_delete_user(device, internal_id),
            )
            if results.was_passed("DELETE USER"):
                await run_step(
                    results,
                    "VERIFY USER DELETION",
                    test_verify_user_deletion(device, internal_id),
                )
            else:
                skip_step(
                    results,
                    "VERIFY USER DELETION",
                    "requires DELETE USER to pass",
                )

    # Device needs cooldown between request groups
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with AkuvoxDevice(**device_kwargs) as device:
        # Schedule add + delete
        sched_id = await run_step(results, "ADD SCHEDULE", test_add_schedule(device))
        if sched_id is None:
            reason = "requires internal ID from ADD SCHEDULE"
            skip_step(results, "MODIFY SCHEDULE", reason)
            skip_step(results, "DELETE SCHEDULE", reason)
            skip_step(results, "VERIFY SCHEDULE DELETION", reason)
        else:
            await run_step(
                results,
                "MODIFY SCHEDULE",
                test_modify_schedule(device, sched_id),
            )
            await run_step(
                results,
                "DELETE SCHEDULE",
                test_delete_schedule(device, sched_id),
            )
            if results.was_passed("DELETE SCHEDULE"):
                await run_step(
                    results,
                    "VERIFY SCHEDULE DELETION",
                    test_verify_schedule_deletion(device, sched_id),
                )
            else:
                skip_step(
                    results,
                    "VERIFY SCHEDULE DELETION",
                    "requires DELETE SCHEDULE to pass",
                )

        # Relay trigger (safe: auto-close after 1s)
        await run_step(results, "TRIGGER RELAY", test_trigger_relay(device))

        # Config set + read-back verification
        await run_step(results, "SET DEVICE CONFIG", test_set_device_config(device))

    # Cooldown before group tests
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with AkuvoxDevice(**device_kwargs) as device:
        # Group add + delete
        group_id = await run_step(results, "ADD GROUP", test_add_group(device))
        if group_id is None:
            reason = "requires internal ID from ADD GROUP"
            skip_step(results, "DELETE GROUP", reason)
            skip_step(results, "VERIFY GROUP DELETION", reason)
        else:
            await run_step(
                results,
                "DELETE GROUP",
                test_delete_group(device, group_id),
            )
            if results.was_passed("DELETE GROUP"):
                await run_step(
                    results,
                    "VERIFY GROUP DELETION",
                    test_verify_group_deletion(device, group_id),
                )
            else:
                skip_step(
                    results,
                    "VERIFY GROUP DELETION",
                    "requires DELETE GROUP to pass",
                )

    # Cooldown before contact tests
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with AkuvoxDevice(**device_kwargs) as device:
        # Contact add + modify + delete
        contact_id = await run_step(results, "ADD CONTACT", test_add_contact(device))
        if contact_id is None:
            reason = "requires internal ID from ADD CONTACT"
            skip_step(results, "MODIFY CONTACT", reason)
            skip_step(results, "DELETE CONTACT", reason)
            skip_step(results, "VERIFY CONTACT DELETION", reason)
        else:
            await run_step(
                results,
                "MODIFY CONTACT",
                test_modify_contact(device, contact_id),
            )
            await run_step(
                results,
                "DELETE CONTACT",
                test_delete_contact(device, contact_id),
            )
            if results.was_passed("DELETE CONTACT"):
                await run_step(
                    results,
                    "VERIFY CONTACT DELETION",
                    test_verify_contact_deletion(device, contact_id),
                )
            else:
                skip_step(
                    results,
                    "VERIFY CONTACT DELETION",
                    "requires DELETE CONTACT to pass",
                )

    # Cooldown before read tests
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)


async def run_all(args: argparse.Namespace) -> None:
    """Run all MVP tests against the device."""
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
    results = TestResults()

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
        if args.write:
            await _run_write_tests(device_kwargs, results)

        async with AkuvoxDevice(**device_kwargs) as device:
            await _run_read_tests(device, results)

            if not args.write:
                print_header("SKIPPING WRITE TESTS")
                print("  Use --write to test:")
                print("    - add/modify/delete user")
                print("    - add/modify/delete schedule")
                print("    - trigger relay (auto-close, 1s)")
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
  %(prog)s 192.168.1.100 --auth basic --user admin --pass secret
  %(prog)s 192.168.1.100 --auth digest --user admin --pass secret --write
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
