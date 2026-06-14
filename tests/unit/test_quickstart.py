# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Validate quickstart.md code examples against mocked devices."""

import pytest
from aioresponses import aioresponses

from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
)
from pylocal_akuvox.exceptions import AkuvoxValidationError
from tests.unit._helpers import register_default_info

_BASE = "http://192.168.1.100"

_INFO_PAYLOAD = {
    "retcode": 0,
    "action": "info",
    "message": "",
    "data": {
        "Status": {
            "Model": "E21V",
            "MAC": "AA:BB:CC:DD:EE:FF",
            "FirmwareVersion": "2.0.0.1",
            "HardwareVersion": "1.0",
            "Uptime": "3 days",
            "WebLang": 0,
        }
    },
}


async def test_connect_and_get_info() -> None:
    """SC-001: connect and retrieve device info in ≤5 lines."""
    with aioresponses() as m:
        m.get(f"{_BASE}/api/system/info", payload=_INFO_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100") as device:
            info = await device.get_info()
            assert info.model == "E21V"
            assert info.firmware_version == "2.0.0.1"


async def test_manage_users() -> None:
    """SC-007: user CRUD in ≤10 lines."""
    user_page = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {
            "num": 1,
            "curPageNum": 1,
            "item": [
                {
                    "ID": "1",
                    "Name": "Alice",
                    "UserID": "2001",
                    "PrivatePIN": "1234",
                    "CardCode": "",
                    "WebRelay": "0",
                    "ScheduleRelay": "1001-1",
                    "LiftFloorNum": "0",
                }
            ],
        },
    }
    ok = {"retcode": 1, "action": "add", "message": "OK", "data": {}}

    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{_BASE}/api/user/set", payload=ok)
        # list_users (no page param)
        m.get(f"{_BASE}/api/user/get", payload=user_page)
        # modify_user: _get_user_by_id paginates with ?page=1
        m.get(f"{_BASE}/api/user/get?page=1", payload=user_page)
        m.post(f"{_BASE}/api/user/set", payload=ok)
        # delete_user
        m.post(f"{_BASE}/api/user/set", payload=ok)

        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                private_pin="1234",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )
            users = await device.list_users()
            assert len(users) == 1
            assert users[0].name == "Alice"

            await device.modify_user(id="1", private_pin="5678")
            await device.delete_user(id="1")


async def test_trigger_relay() -> None:
    """SC-009: trigger relay with ≤1s confirmation."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{_BASE}/api/relay/trig",
            payload={
                "retcode": 1,
                "action": "trigRelay",
                "message": "OK",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1, delay=5)


async def test_get_status() -> None:
    """Retrieve device status."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{_BASE}/api/system/status",
            payload={
                "retcode": 0,
                "action": "status",
                "message": "",
                "data": {"SystemTime": 1700000000, "UpTime": 86400},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            status = await device.get_status()
            assert status.uptime == 86400


async def test_manage_schedules() -> None:
    """SC-010: schedule CRUD in ≤10 lines."""
    with aioresponses() as m:
        register_default_info(m)
        # add_schedule
        m.post(
            f"{_BASE}/api/schedule/set",
            payload={"retcode": 1, "action": "add", "message": "OK", "data": {}},
        )
        # list_schedules
        m.get(
            f"{_BASE}/api/schedule/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "OK",
                "data": {
                    "num": 1,
                    "item": [
                        {
                            "ID": "1001",
                            "Name": "Weekday Access",
                            "Type": "1",
                            "DateStart": "",
                            "DateEnd": "",
                            "TimeStart": "",
                            "TimeEnd": "",
                            "Week": "12345",
                        }
                    ],
                },
            },
        )
        # delete_schedule
        m.post(
            f"{_BASE}/api/schedule/set",
            payload={"retcode": 1, "action": "del", "message": "OK", "data": {}},
        )

        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_schedule(
                name="Weekday Access",
                schedule_type="1",
                week="12345",
                daily="08:00-18:00",
            )
            schedules = await device.list_schedules()
            assert len(schedules) == 1

            await device.delete_schedule(id="1001")


async def test_retrieve_logs() -> None:
    """SC-008: structured log retrieval."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{_BASE}/api/doorlog/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "OK",
                "data": {
                    "num": 1,
                    "curPageNum": 1,
                    "item": [
                        {
                            "ID": "42",
                            "Date": "2026-01-15",
                            "Time": "09:30:00",
                            "Name": "Alice",
                            "Code": "1234",
                            "Type": "PIN",
                            "Relay": "1",
                            "Status": "Succ",
                        }
                    ],
                },
            },
        )
        m.get(
            f"{_BASE}/api/calllog/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "OK",
                "data": {
                    "num": 1,
                    "curPageNum": 1,
                    "item": [
                        {
                            "ID": "100",
                            "Date": "2026-01-15",
                            "Time": "14:30:00",
                            "Name": "Front Door",
                            "Type": "Received",
                            "LocalIdentity": "sip:100@192.168.1.1",
                            "Num": "3",
                        }
                    ],
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            door_logs = await device.get_door_logs()
            assert len(door_logs) == 1
            assert door_logs[0].name == "Alice"
            assert door_logs[0].status == "Succ"

            call_logs = await device.get_call_logs()
            assert len(call_logs) == 1
            assert call_logs[0].call_type == "Received"


async def test_auth_modes() -> None:
    """SC-006: all auth modes connect successfully."""
    with aioresponses() as m:
        # AllowList (default)
        m.get(f"{_BASE}/api/system/info", payload=_INFO_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100") as device:
            info = await device.get_info()
            assert info.model == "E21V"

        # Basic auth
        auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="secret")
        m.get(f"{_BASE}/api/system/info", payload=_INFO_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
            info = await device.get_info()
            assert info.model == "E21V"

        # Digest auth
        auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="secret")
        m.get(f"{_BASE}/api/system/info", payload=_INFO_PAYLOAD)
        async with AkuvoxDevice("192.168.1.100", auth=auth) as device:
            info = await device.get_info()
            assert info.model == "E21V"


async def test_error_handling_validation() -> None:
    """SC-002: validation errors raised for invalid input."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
                await device.add_user(
                    name="Bob",
                    user_id="2002",
                    private_pin="12ab",
                    web_relay="0",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )
