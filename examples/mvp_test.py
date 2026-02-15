#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Interactive CLI script to test pylocal-akuvox against a real device.

Usage:
    uv run examples/mvp_test.py <device-ip>
    uv run examples/mvp_test.py <device-ip> --write
    uv run examples/mvp_test.py <device-ip> --auth basic --user admin --pass secret

Examples:
    # AllowList / no auth (default) — read-only tests
    uv run examples/mvp_test.py 192.168.1.100

    # Include write tests (creates and deletes a test user)
    uv run examples/mvp_test.py 192.168.1.100 --write

    # Basic auth
    uv run examples/mvp_test.py 192.168.1.100 --auth basic --user admin --pass secret

    # Digest auth with write tests
    uv run examples/mvp_test.py 192.168.1.100 \
        --auth digest --user admin --pass secret --write

"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback

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
    AkuvoxValidationError,
)

SEPARATOR = "-" * 60


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


async def test_add_user(device: AkuvoxDevice) -> str | None:
    """Test: Add a test user. Returns the user's internal ID if found."""
    print_header("ADD USER (/api/user/add)")
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

    # Find the user's internal ID for later operations
    users = await device.list_users()
    for user in users:
        if user.user_id == test_user_id:
            print(f"  → Assigned internal ID: {user.id}")
            return user.id

    print("  ⚠ User added but not found in list (pagination?)")
    return None


async def test_modify_user(device: AkuvoxDevice, internal_id: str) -> None:
    """Test: Modify the test user's PIN."""
    print_header("MODIFY USER (/api/user/set)")
    await device.modify_user(id=internal_id, private_pin="5678")
    print(f"  Modified user ID={internal_id}: PIN changed to 5678")
    print("  ✓ modify_user() OK")


async def test_delete_user(device: AkuvoxDevice, internal_id: str) -> None:
    """Test: Delete the test user."""
    print_header("DELETE USER (/api/user/del)")
    await device.delete_user(id=internal_id)
    print(f"  Deleted user ID={internal_id}")
    print("  ✓ delete_user() OK")


async def test_validation() -> None:
    """Test: Client-side validation (no device needed)."""
    print_header("CLIENT-SIDE VALIDATION (no network)")

    # Invalid PIN
    try:
        async with AkuvoxDevice("0.0.0.0") as device:
            await device.add_user(
                name="Bad",
                user_id="0001",
                private_pin="12ab",
                web_relay="0",
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )
        print("  ✗ Should have raised for invalid PIN")
    except AkuvoxValidationError as exc:
        print(f"  ✓ Invalid PIN rejected: {exc}")

    # Empty name
    try:
        async with AkuvoxDevice("0.0.0.0") as device:
            await device.add_user(
                name="",
                user_id="0001",
                web_relay="0",
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )
        print("  ✗ Should have raised for empty name")
    except AkuvoxValidationError as exc:
        print(f"  ✓ Empty name rejected: {exc}")

    # Empty schedule_relay
    try:
        async with AkuvoxDevice("0.0.0.0") as device:
            await device.add_user(
                name="Bad",
                user_id="0001",
                web_relay="0",
                schedule_relay="",
                lift_floor_num="0",
            )
        print("  ✗ Should have raised for empty schedule_relay")
    except AkuvoxValidationError as exc:
        print(f"  ✓ Empty schedule_relay rejected: {exc}")

    print("  ✓ All validation checks passed")


async def run_all(args: argparse.Namespace) -> None:
    """Run all MVP tests against the device."""
    auth = build_auth(args)
    auth_desc = args.auth if args.auth != "none" else "allowlist (no auth)"

    print(f"\n🔌 Connecting to {args.host} ({auth_desc})")
    print(f"   Timeout: {args.timeout}s\n")

    # 1. Validation tests (offline)
    await test_validation()

    # 2. Device tests (online)
    try:
        async with AkuvoxDevice(args.host, auth=auth, timeout=args.timeout) as device:
            await test_get_info(device)
            await test_get_status(device)
            await test_list_users(device)

            if args.write:
                internal_id = await test_add_user(device)
                if internal_id:
                    await test_modify_user(device, internal_id)
                    await test_delete_user(device, internal_id)
                    # Verify deletion
                    print_header("VERIFY DELETION")
                    users = await device.list_users()
                    found = any(u.id == internal_id for u in users)
                    if not found:
                        print("  ✓ User successfully removed")
                    else:
                        print("  ✗ User still present after delete!")
            else:
                print_header("SKIPPING WRITE TESTS")
                print("  Use --write to test add/modify/delete user")
                print("  ⚠ This WILL create and delete a test user on the device")

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
    parser.add_argument("--pass", dest="password", default=None, help="Auth password")
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

    args = parser.parse_args()

    if args.auth in ("basic", "digest") and (not args.user or not args.password):
        parser.error(f"--auth {args.auth} requires --user and --pass")

    asyncio.run(run_all(args))


if __name__ == "__main__":
    main()
