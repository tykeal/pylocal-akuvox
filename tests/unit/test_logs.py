# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for log retrieval operations."""

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import AkuvoxDeviceError

BASE_URL = "http://192.168.1.100"

_DOOR_LOG_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 2,
        "curPageNum": 2,
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
            },
            {
                "ID": "43",
                "Date": "2026-01-15",
                "Time": "10:00:00",
                "Name": "Bob",
                "Code": "5678",
                "Type": "Card",
                "Relay": "2",
                "Status": "Failed",
                "AccessMode": "1",
            },
        ],
    },
}

_CALL_LOG_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 2,
        "curPageNum": 2,
        "item": [
            {
                "ID": "100",
                "Date": "2026-01-15",
                "Time": "14:30:00",
                "Name": "Front Door",
                "Type": "Received",
                "LocalIdentity": "sip:100@192.168.1.1",
                "Num": "3",
            },
            {
                "ID": "101",
                "Date": "2026-01-15",
                "Time": "15:00:00",
                "Name": "Back Door",
                "Type": "Missed",
                "LocalIdentity": "sip:200@192.168.1.1",
                "Num": "1",
                "PicUrl": "http://device/pics/101.jpg",
            },
        ],
    },
}

_EMPTY_LOG_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 0,
        "curPageNum": 0,
        "item": [],
    },
}

_ERROR_RESPONSE: dict[str, object] = {
    "retcode": -1,
    "action": "get",
    "message": "Failed",
}


# -- T043: get_door_logs tests --


@pytest.mark.asyncio
async def test_get_door_logs_posts_correct_endpoint() -> None:
    """Verify get_door_logs GETs /api/doorlog/get."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/doorlog/get", payload=_DOOR_LOG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_door_logs()
    assert len(logs) == 2
    assert logs[0].id == "42"
    assert logs[0].name == "Alice"
    assert logs[0].door_type == "PIN"
    assert logs[0].status == "Succ"
    assert logs[1].id == "43"
    assert logs[1].access_mode == "1"


@pytest.mark.asyncio
async def test_get_door_logs_with_pagination() -> None:
    """Verify get_door_logs sends page query parameter."""
    with aioresponses() as m:
        url = f"{BASE_URL}/api/doorlog/get?page=1"
        m.get(url, payload=_DOOR_LOG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_door_logs(page=1)
    assert len(logs) == 2
    url_key = (
        "GET",
        aiohttp.client.URL(url),
    )
    assert url_key in m.requests


@pytest.mark.asyncio
async def test_get_door_logs_empty_returns_empty_list() -> None:
    """Verify empty device returns empty list not error."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/doorlog/get", payload=_EMPTY_LOG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_door_logs()
    assert logs == []


@pytest.mark.asyncio
async def test_get_door_logs_no_item_key_returns_empty() -> None:
    """Verify missing item key returns empty list."""
    response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/doorlog/get", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_door_logs()
    assert logs == []


@pytest.mark.asyncio
async def test_get_door_logs_error_raises_device_error() -> None:
    """Verify device error raises AkuvoxDeviceError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/doorlog/get", payload=_ERROR_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError):
                await device.get_door_logs()


# -- T043: get_call_logs tests --


@pytest.mark.asyncio
async def test_get_call_logs_posts_correct_endpoint() -> None:
    """Verify get_call_logs GETs /api/calllog/get."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/calllog/get", payload=_CALL_LOG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_call_logs()
    assert len(logs) == 2
    assert logs[0].id == "100"
    assert logs[0].name == "Front Door"
    assert logs[0].call_type == "Received"
    assert logs[0].count == "3"
    assert logs[0].pic_url is None
    assert logs[1].id == "101"
    assert logs[1].pic_url == "http://device/pics/101.jpg"


@pytest.mark.asyncio
async def test_get_call_logs_with_pagination() -> None:
    """Verify get_call_logs sends page query parameter."""
    with aioresponses() as m:
        url = f"{BASE_URL}/api/calllog/get?page=2"
        m.get(url, payload=_CALL_LOG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_call_logs(page=2)
    assert len(logs) == 2
    url_key = (
        "GET",
        aiohttp.client.URL(url),
    )
    assert url_key in m.requests


@pytest.mark.asyncio
async def test_get_call_logs_empty_returns_empty_list() -> None:
    """Verify empty device returns empty list not error."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/calllog/get", payload=_EMPTY_LOG_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_call_logs()
    assert logs == []


@pytest.mark.asyncio
async def test_get_call_logs_no_item_key_returns_empty() -> None:
    """Verify missing item key returns empty list."""
    response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/calllog/get", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_call_logs()
    assert logs == []


@pytest.mark.asyncio
async def test_get_call_logs_error_raises_device_error() -> None:
    """Verify device error raises AkuvoxDeviceError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/calllog/get", payload=_ERROR_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError):
                await device.get_call_logs()


@pytest.mark.asyncio
async def test_get_door_logs_non_list_item_returns_empty() -> None:
    """Verify non-list item value returns empty list."""
    response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": "not-a-list"},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/doorlog/get", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_door_logs()
    assert logs == []


@pytest.mark.asyncio
async def test_get_call_logs_non_list_item_returns_empty() -> None:
    """Verify non-list item value returns empty list."""
    response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": "not-a-list"},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/calllog/get", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            logs = await device.get_call_logs()
    assert logs == []
