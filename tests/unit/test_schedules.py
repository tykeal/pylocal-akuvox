# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for schedule validation and CRUD operations."""

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxDeviceError,
    AkuvoxValidationError,
)
from pylocal_akuvox.schedules import (
    validate_daily,
    validate_date,
    validate_schedule_type,
    validate_time,
    validate_week,
)

BASE_URL = "http://192.168.1.100"

_SCHEDULE_GET_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [
            {
                "ID": "1001",
                "Name": "Weekday",
                "Type": "1",
                "DateStart": "20260101",
                "DateEnd": "20261231",
                "TimeStart": "08:00",
                "TimeEnd": "18:00",
                "Week": "12345",
            },
        ],
    },
}

_ADD_OK_RESPONSE: dict[str, object] = {
    "retcode": 1,
    "action": "add",
    "message": "OK",
    "data": {},
}

_SET_OK_RESPONSE: dict[str, object] = {
    "retcode": 1,
    "action": "set",
    "message": "OK",
    "data": {},
}

_DEL_OK_RESPONSE: dict[str, object] = {
    "retcode": 1,
    "action": "del",
    "message": "OK",
    "data": {},
}

_EMPTY_PAGE_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {"num": 0, "item": []},
}


# -- T037: Schedule type validation --


def test_validate_schedule_type_0() -> None:
    """Verify type '0' (Normal) is accepted."""
    validate_schedule_type("0")


def test_validate_schedule_type_1() -> None:
    """Verify type '1' (Weekly) is accepted."""
    validate_schedule_type("1")


def test_validate_schedule_type_2() -> None:
    """Verify type '2' (Daily) is accepted."""
    validate_schedule_type("2")


def test_validate_schedule_type_invalid() -> None:
    """Verify invalid type raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="schedule_type"):
        validate_schedule_type("3")


def test_validate_schedule_type_empty() -> None:
    """Verify empty string raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="schedule_type"):
        validate_schedule_type("")


# -- T037: Time validation --


def test_validate_time_valid() -> None:
    """Verify valid HH:MM time is accepted."""
    validate_time("08:30", "time_start")


def test_validate_time_none() -> None:
    """Verify None time is allowed (optional)."""
    validate_time(None, "time_start")


def test_validate_time_midnight() -> None:
    """Verify midnight 00:00 is accepted."""
    validate_time("00:00", "time_start")


def test_validate_time_invalid_format() -> None:
    """Verify non-HH:MM format raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM"):
        validate_time("8:30", "time_start")


def test_validate_time_invalid_chars() -> None:
    """Verify non-numeric time raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM"):
        validate_time("ab:cd", "time_start")


def test_validate_time_invalid_minutes() -> None:
    """Verify minutes >59 raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM"):
        validate_time("08:60", "time_start")


def test_validate_time_hour_24_rejected() -> None:
    """Verify hour 24 is rejected."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM"):
        validate_time("24:00", "time_start")


def test_validate_time_hour_29_rejected() -> None:
    """Verify hour 29 is rejected."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM"):
        validate_time("29:00", "time_start")


def test_validate_time_empty_allowed() -> None:
    """Verify empty string time is allowed (optional)."""
    validate_time("", "time_start")


# -- T037: Date validation --


def test_validate_date_valid() -> None:
    """Verify valid YYYYMMDD date is accepted."""
    validate_date("20260115", "date_start")


def test_validate_date_none() -> None:
    """Verify None date is allowed (optional)."""
    validate_date(None, "date_start")


def test_validate_date_too_short() -> None:
    """Verify short date raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="YYYYMMDD"):
        validate_date("202601", "date_start")


def test_validate_date_invalid_chars() -> None:
    """Verify non-numeric date raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="YYYYMMDD"):
        validate_date("2026-01-15", "date_start")


def test_validate_date_empty_allowed() -> None:
    """Verify empty string date is allowed (optional)."""
    validate_date("", "date_start")


# -- T037: Week validation --


def test_validate_week_valid() -> None:
    """Verify valid week codes are accepted."""
    validate_week("12345")


def test_validate_week_none() -> None:
    """Verify None week is allowed (optional)."""
    validate_week(None)


def test_validate_week_single_day() -> None:
    """Verify single day code is accepted."""
    validate_week("0")


def test_validate_week_all_days() -> None:
    """Verify all days 0-6 are accepted."""
    validate_week("0123456")


def test_validate_week_invalid_digit() -> None:
    """Verify digit > 6 raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="digits 0-6"):
        validate_week("7")


def test_validate_week_invalid_chars() -> None:
    """Verify non-digit week raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="digits 0-6"):
        validate_week("abc")


def test_validate_week_empty_allowed() -> None:
    """Verify empty string week is allowed (optional)."""
    validate_week("")


# -- T037: Daily validation --


def test_validate_daily_valid() -> None:
    """Verify valid HH:MM-HH:MM daily is accepted."""
    validate_daily("08:00-18:00")


def test_validate_daily_none() -> None:
    """Verify None daily is allowed (optional)."""
    validate_daily(None)


def test_validate_daily_empty_allowed() -> None:
    """Verify empty string daily is allowed (optional)."""
    validate_daily("")


def test_validate_daily_midnight_range() -> None:
    """Verify midnight range is accepted."""
    validate_daily("00:00-23:59")


def test_validate_daily_invalid_format() -> None:
    """Verify non-range format raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM-HH:MM"):
        validate_daily("08:00")


def test_validate_daily_invalid_hour() -> None:
    """Verify invalid hour in daily raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM-HH:MM"):
        validate_daily("25:00-18:00")


def test_validate_daily_invalid_chars() -> None:
    """Verify non-numeric daily raises AkuvoxValidationError."""
    with pytest.raises(AkuvoxValidationError, match="HH:MM-HH:MM"):
        validate_daily("ab:cd-ef:gh")


# -- T037: add_schedule CRUD tests --


async def test_add_schedule_posts_correct_endpoint() -> None:
    """Verify add_schedule POSTs to /api/schedule/set."""
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/schedule/set", payload=_ADD_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_schedule(
                schedule_type="1",
                name="Weekday",
                week="12345",
                time_start="08:00",
                time_end="18:00",
            )

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "schedule"
        assert body["action"] == "add"
        item = body["data"]["item"][0]
        assert item["Type"] == "1"
        assert item["Name"] == "Weekday"
        assert item["Week"] == "12345"
        assert item["TimeStart"] == "08:00"
        assert item["TimeEnd"] == "18:00"


async def test_add_schedule_minimal() -> None:
    """Verify add_schedule with only required fields."""
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/schedule/set", payload=_ADD_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_schedule(schedule_type="0")

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert item["Type"] == "0"
        assert "Name" not in item


async def test_add_schedule_invalid_type_rejected() -> None:
    """Verify add_schedule rejects invalid schedule type."""
    with aioresponses() as m:
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="schedule_type"):
                await device.add_schedule(schedule_type="9")
        assert len(m.requests) == 0


async def test_add_schedule_invalid_time_rejected() -> None:
    """Verify add_schedule rejects invalid time format."""
    with aioresponses() as m:
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="HH:MM"):
                await device.add_schedule(schedule_type="1", time_start="9:00")
        assert len(m.requests) == 0


async def test_add_schedule_invalid_date_rejected() -> None:
    """Verify add_schedule rejects invalid date format."""
    with aioresponses() as m:
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="YYYYMMDD"):
                await device.add_schedule(schedule_type="1", date_start="2026-01")
        assert len(m.requests) == 0


async def test_add_schedule_invalid_week_rejected() -> None:
    """Verify add_schedule rejects invalid week codes."""
    with aioresponses() as m:
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="digits 0-6"):
                await device.add_schedule(schedule_type="1", week="789")
        assert len(m.requests) == 0


async def test_add_schedule_invalid_daily_rejected() -> None:
    """Verify add_schedule rejects invalid daily format."""
    with aioresponses() as m:
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="HH:MM-HH:MM"):
                await device.add_schedule(schedule_type="1", daily="bad")
        assert len(m.requests) == 0


async def test_add_schedule_with_dates() -> None:
    """Verify add_schedule includes date fields in payload."""
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/schedule/set", payload=_ADD_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_schedule(
                schedule_type="0",
                date_start="20260101",
                date_end="20261231",
            )

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        item = call.kwargs.get("json")["data"]["item"][0]
        assert item["DateStart"] == "20260101"
        assert item["DateEnd"] == "20261231"


async def test_add_schedule_with_daily() -> None:
    """Verify add_schedule includes daily field in payload."""
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/schedule/set", payload=_ADD_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_schedule(
                schedule_type="2",
                daily="08:00-18:00",
            )

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        item = call.kwargs.get("json")["data"]["item"][0]
        assert item["Daily"] == "08:00-18:00"


# -- T037: list_schedules CRUD tests --


async def test_list_schedules_returns_items() -> None:
    """Verify list_schedules returns parsed AccessSchedule list."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/schedule/get", payload=_SCHEDULE_GET_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            schedules = await device.list_schedules()

    assert len(schedules) == 1
    assert schedules[0].id == "1001"
    assert schedules[0].name == "Weekday"
    assert schedules[0].schedule_type == "1"
    assert schedules[0].week == "12345"


async def test_list_schedules_empty() -> None:
    """Verify list_schedules returns empty list when none exist."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/schedule/get", payload=_EMPTY_PAGE_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            schedules = await device.list_schedules()

    assert schedules == []


async def test_list_schedules_with_page() -> None:
    """Verify list_schedules passes page parameter."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get?page=2",
            payload=_SCHEDULE_GET_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.list_schedules(page=2)

        url_key = (
            "GET",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/get?page=2"),
        )
        assert url_key in m.requests


async def test_list_schedules_non_list_items() -> None:
    """Verify list_schedules returns empty on non-list items."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "OK",
                "data": {"item": "not-a-list"},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            schedules = await device.list_schedules()

    assert schedules == []


async def test_list_schedules_device_error() -> None:
    """Verify list_schedules raises on device error."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get",
            payload={
                "retcode": -1,
                "action": "get",
                "message": "Failed",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError):
                await device.list_schedules()


# -- T037: modify_schedule CRUD tests --


async def test_modify_schedule_read_modify_write() -> None:
    """Verify modify_schedule fetches, merges, and sends."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get?page=1",
            payload=_SCHEDULE_GET_RESPONSE,
        )
        m.post(f"{BASE_URL}/api/schedule/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_schedule(id="1001", name="Updated")

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "schedule"
        assert body["action"] == "set"
        item = body["data"]["item"][0]
        assert item["Name"] == "Updated"
        assert item["ID"] == "1001"
        assert item["Type"] == "1"


async def test_modify_schedule_not_found() -> None:
    """Verify modify_schedule raises when schedule ID is not found."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get?page=1",
            payload=_EMPTY_PAGE_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="not found"):
                await device.modify_schedule(id="9999", name="Missing")


async def test_modify_schedule_validates_type() -> None:
    """Verify modify_schedule validates schedule_type before fetch."""
    with aioresponses() as m:
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="schedule_type"):
                await device.modify_schedule(id="1001", schedule_type="9")
        assert len(m.requests) == 0


async def test_modify_schedule_paginates_to_find() -> None:
    """Verify modify_schedule iterates pages to find the schedule."""
    page2_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {
                    "ID": "2002",
                    "Name": "Weekend",
                    "Type": "0",
                },
            ],
        },
    }
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get?page=1",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "OK",
                "data": {
                    "num": 1,
                    "item": [
                        {
                            "ID": "1001",
                            "Name": "Weekday",
                            "Type": "1",
                        },
                    ],
                },
            },
        )
        m.get(
            f"{BASE_URL}/api/schedule/get?page=2",
            payload=page2_response,
        )
        m.post(f"{BASE_URL}/api/schedule/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_schedule(id="2002", name="Sat+Sun")

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        item = call.kwargs.get("json")["data"]["item"][0]
        assert item["Name"] == "Sat+Sun"
        assert item["ID"] == "2002"


# -- T037: modify_schedule CRUD tests (additional) --


async def test_modify_schedule_without_name() -> None:
    """Verify modify_schedule works without name (covers skip)."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get?page=1",
            payload=_SCHEDULE_GET_RESPONSE,
        )
        m.post(f"{BASE_URL}/api/schedule/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_schedule(id="1001", schedule_type="0")

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        item = call.kwargs.get("json")["data"]["item"][0]
        assert item["Type"] == "0"
        assert item["Name"] == "Weekday"


async def test_modify_schedule_all_merge_fields() -> None:
    """Verify modify_schedule merges all optional fields."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/schedule/get?page=1",
            payload=_SCHEDULE_GET_RESPONSE,
        )
        m.post(f"{BASE_URL}/api/schedule/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_schedule(
                id="1001",
                name="Updated",
                schedule_type="2",
                week="06",
                daily="09:00-17:00",
                date_start="20260201",
                date_end="20261130",
                time_start="09:00",
                time_end="17:00",
            )

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        item = call.kwargs.get("json")["data"]["item"][0]
        assert item["Type"] == "2"
        assert item["Name"] == "Updated"
        assert item["Week"] == "06"
        assert item["Daily"] == "09:00-17:00"
        assert item["DateStart"] == "20260201"
        assert item["DateEnd"] == "20261130"
        assert item["TimeStart"] == "09:00"
        assert item["TimeEnd"] == "17:00"


async def test_delete_schedule_posts_correct_endpoint() -> None:
    """Verify delete_schedule POSTs to /api/schedule/set."""
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/schedule/set", payload=_DEL_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_schedule(id="1001")

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/schedule/set"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "schedule"
        assert body["action"] == "del"
        assert body["data"]["item"][0]["ID"] == "1001"


async def test_delete_schedule_device_error() -> None:
    """Verify delete_schedule raises on device error."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/schedule/set",
            payload={
                "retcode": -1,
                "action": "del",
                "message": "Failed",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError):
                await device.delete_schedule(id="1001")
