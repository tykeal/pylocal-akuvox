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
    from collections.abc import Coroutine

from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
)
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxError,
    AkuvoxUnsupportedError,
    AkuvoxValidationError,
)

SEPARATOR = "-" * 60
# Akuvox devices need time to persist mutations before the next
# API call; two seconds is sufficient based on testing.
_MUTATION_SETTLE_SECS = 2


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
    try:
        status = await device.get_relay_status()
        print(f"  Raw status: {status}")
        print("  ✓ get_relay_status() OK")
    except AkuvoxUnsupportedError as exc:
        print(f"  ⚠ Relay status not supported: {exc}")
    except AkuvoxDeviceError as exc:
        print(f"  ⚠ Relay status rejected: {exc}")


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


async def test_get_door_logs(device: AkuvoxDevice) -> None:
    """Test: Retrieve door access logs."""
    print_header("GET DOOR LOGS (/api/doorlog/get)")
    try:
        entries = await device.get_door_logs()
    except AkuvoxUnsupportedError as exc:
        print(f"  ⚠ Door logs not supported: {exc}")
        return
    except AkuvoxDeviceError as exc:
        print(f"  ⚠ Door logs rejected: {exc}")
        return
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
    try:
        entries = await device.get_call_logs()
    except AkuvoxUnsupportedError as exc:
        print(f"  ⚠ Call logs not supported: {exc}")
        return
    except AkuvoxDeviceError as exc:
        print(f"  ⚠ Call logs rejected: {exc}")
        return
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


async def test_add_user(device: AkuvoxDevice) -> str | None:
    """Test: Add a test user. Returns the user's internal ID if found."""
    print_header("ADD USER (/api/user/set action:add)")
    test_name = "pylocal-test"
    test_user_id = "9999"

    try:
        await device.add_user(
            name=test_name,
            user_id=test_user_id,
            private_pin="1234",
            web_relay="0",
            schedule_relay="1001-1;",
            lift_floor_num="0",
        )
        print(f"  Added user: {test_name} (UserID={test_user_id}, PIN=1234)")
        print("  ✓ add_user() OK")
    except AkuvoxDeviceError as exc:
        print(f"  ✗ Device rejected add_user: {exc}")
        print("    (User may already exist or schedule 1001 may not exist)")
        return None

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    # Search for the newly added user (page 1 has all items)
    users = await device.list_users()
    for user in users:
        if user.user_id == test_user_id:
            print(f"  → Assigned internal ID: {user.id}")
            return user.id

    print("  ⚠ User added but not found in list")
    return None


# Not called in the current test flow — modify operations are
# reserved for future testing once firmware behavior is fully
# characterized.  Kept as a ready-to-use helper.
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
    try:
        await device.trigger_relay(num=1, delay=1)
        print("  Triggered relay 1 (auto-close, delay=1s)")
        print("  ✓ trigger_relay() OK")
    except AkuvoxUnsupportedError as exc:
        print(f"  ⚠ Relay trigger not supported: {exc}")
    except AkuvoxDeviceError as exc:
        print(f"  ⚠ Relay trigger rejected by device: {exc}")
        print("  (Some models do not support relay trigger)")


async def test_add_schedule(device: AkuvoxDevice) -> str | None:
    """Test: Add a test schedule. Returns schedule ID if found."""
    print_header("ADD SCHEDULE (/api/schedule/set action:add)")
    test_name = "pylocal-test-sched"

    try:
        await device.add_schedule(
            schedule_type="1",
            name=test_name,
            week="12345",
            time_start="08:00",
            time_end="18:00",
        )
        print(f"  Added schedule: {test_name} (Weekly, Mon-Fri 08-18)")
        print("  ✓ add_schedule() OK")
    except AkuvoxDeviceError as exc:
        print(f"  ✗ Device rejected add_schedule: {exc}")
        return None

    # Device needs time to persist the new record
    await asyncio.sleep(_MUTATION_SETTLE_SECS)

    schedules = await device.list_schedules()
    for sched in schedules:
        if sched.name == test_name:
            print(f"  → Assigned internal ID: {sched.id}")
            return sched.id

    print("  ⚠ Schedule added but not found in list")
    return None


# Not called in the current test flow — modify operations are
# reserved for future testing once firmware behavior is fully
# characterized.  Kept as a ready-to-use helper.
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
            schedule_relay="1001-1;",
            lift_floor_num="0",
        ),
    )
    await _check_validation(
        "Empty name rejected",
        device.add_user(
            name="",
            user_id="0001",
            web_relay="0",
            schedule_relay="1001-1;",
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

    print("  ✓ All validation checks passed")


async def _run_read_tests(device: AkuvoxDevice) -> None:
    """Run all read-only tests against a connected device."""
    await test_get_info(device)
    await test_get_status(device)
    await test_list_users(device)
    await test_get_relay_status(device)
    await test_list_schedules(device)
    await test_get_door_logs(device)
    await test_get_call_logs(device)


async def _run_write_tests(device_kwargs: dict[str, Any]) -> None:
    """Run write tests (user/schedule CRUD, relay trigger)."""
    async with AkuvoxDevice(**device_kwargs) as device:
        # User add + delete FIRST — before any other
        # requests to avoid CGI state corruption.
        internal_id = await test_add_user(device)
        if internal_id:
            await test_delete_user(device, internal_id)
            print_header("VERIFY USER DELETION")
            users = await device.list_users()
            found = any(u.id == internal_id for u in users)
            if not found:
                print("  ✓ User successfully removed")
            else:
                print("  ✗ User still present after delete!")

    # Device needs cooldown between request groups
    print("\n  ⏳ Waiting for device to settle…")
    await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)

    async with AkuvoxDevice(**device_kwargs) as device:
        # Schedule add + delete
        sched_id = await test_add_schedule(device)
        if sched_id:
            await test_delete_schedule(device, sched_id)
            print_header("VERIFY SCHEDULE DELETION")
            scheds = await device.list_schedules()
            found = any(s.id == sched_id for s in scheds)
            if not found:
                print("  ✓ Schedule successfully removed")
            else:
                print("  ✗ Schedule still present after delete!")

        # Relay trigger (safe: auto-close after 1s)
        await test_trigger_relay(device)

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
            await _run_write_tests(device_kwargs)

        async with AkuvoxDevice(**device_kwargs) as device:
            await _run_read_tests(device)

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
