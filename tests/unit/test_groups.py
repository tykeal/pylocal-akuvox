# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for group management operations."""

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxParseError,
    AkuvoxValidationError,
)

BASE_URL = "http://192.168.1.100"

_GROUP_GET_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 2,
        "item": [
            {"ID": "1", "Name": "Residents"},
            {"ID": "2", "Name": "Staff"},
        ],
    },
}

_GROUP_SINGLE_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [{"ID": "1", "Name": "Residents"}],
    },
}

_GROUP_EMPTY_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {"num": 0, "item": []},
}

_MUTATION_OK_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "add",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [{"ID": "3", "Name": "Visitors", "Ret": 0}],
    },
}

_SET_OK_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "set",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [{"ID": "1", "Name": "Updated", "Ret": 0}],
    },
}

_DEL_OK_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "del",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [{"ID": "1", "Ret": 0}],
    },
}

_DEVICE_ERROR_RESPONSE: dict[str, object] = {
    "retcode": -1,
    "action": "set",
    "message": "Error",
    "data": {
        "num": 1,
        "item": [{"ID": "999", "Ret": -4}],
    },
}

# -- T007: list_groups tests --


@pytest.mark.asyncio
async def test_list_groups_populated() -> None:
    """Verify list_groups returns multiple Group objects."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get",
            payload=_GROUP_GET_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            groups = await device.list_groups()
            assert len(groups) == 2
            assert groups[0].name == "Residents"
            assert groups[0].id == "1"
            assert groups[1].name == "Staff"
            assert groups[1].id == "2"


@pytest.mark.asyncio
async def test_list_groups_empty() -> None:
    """Verify empty item list returns empty collection."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get",
            payload=_GROUP_EMPTY_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            groups = await device.list_groups()
            assert groups == []


@pytest.mark.asyncio
async def test_list_groups_paginated() -> None:
    """Verify page parameter is passed to request."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get?page=2",
            payload=_GROUP_SINGLE_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            groups = await device.list_groups(page=2)
            assert len(groups) == 1


@pytest.mark.asyncio
async def test_list_groups_malformed_missing_name_raises() -> None:
    """Verify malformed item raises AkuvoxParseError."""
    bad_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 1, "item": [{"ID": "1"}]},
    }
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get",
            payload=bad_response,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="Name"):
                await device.list_groups()


@pytest.mark.asyncio
async def test_list_groups_non_list_item_returns_empty() -> None:
    """Verify non-list item field returns empty list."""
    bad_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": "not-a-list"},
    }
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get",
            payload=bad_response,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            groups = await device.list_groups()
            assert groups == []


@pytest.mark.asyncio
async def test_list_groups_single() -> None:
    """Verify single group response parsed correctly."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get",
            payload=_GROUP_SINGLE_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            groups = await device.list_groups()
            assert len(groups) == 1
            assert groups[0].name == "Residents"


# -- T011: add_group tests --


@pytest.mark.asyncio
async def test_add_group_success() -> None:
    """Verify add_group sends correct envelope to /api/group/add."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/add",
            payload=_MUTATION_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_group(name="Visitors")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/group/add"))][0]
        body = req.kwargs["json"]
        assert body["target"] == "group"
        assert body["action"] == "add"
        assert body["data"]["item"] == [{"Name": "Visitors"}]


@pytest.mark.asyncio
async def test_add_group_empty_name_raises() -> None:
    """Verify empty name raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(
            AkuvoxValidationError,
            match="name is required",
        ):
            await device.add_group(name="")


@pytest.mark.asyncio
async def test_add_group_none_name_raises() -> None:
    """Verify None name raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(
            AkuvoxValidationError,
            match="name is required",
        ):
            await device.add_group(name=None)  # type: ignore[arg-type]


# -- T015: modify_group tests --


@pytest.mark.asyncio
async def test_modify_group_success() -> None:
    """Verify modify_group sends ID+Name to /api/group/set."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_group(id="1", name="Updated")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/group/set"))][0]
        body = req.kwargs["json"]
        assert body["target"] == "group"
        assert body["action"] == "set"
        assert body["data"]["item"] == [{"ID": "1", "Name": "Updated"}]


@pytest.mark.asyncio
async def test_modify_group_empty_name_raises() -> None:
    """Verify empty name raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(
            AkuvoxValidationError,
            match="name is required",
        ):
            await device.modify_group(id="1", name="")


@pytest.mark.asyncio
async def test_modify_group_none_name_raises() -> None:
    """Verify None name raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(
            AkuvoxValidationError,
            match="name is required",
        ):
            await device.modify_group(
                id="1",
                name=None,  # type: ignore[arg-type]
            )


# -- T019: delete_group tests --


@pytest.mark.asyncio
async def test_delete_group_success() -> None:
    """Verify delete_group sends ID to /api/group/del."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/del",
            payload=_DEL_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_group(id="1")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/group/del"))][0]
        body = req.kwargs["json"]
        assert body["target"] == "group"
        assert body["action"] == "del"
        assert body["data"]["item"] == [{"ID": "1"}]


@pytest.mark.asyncio
async def test_delete_group_idempotent() -> None:
    """Verify delete of non-existent ID succeeds (idempotent)."""
    idempotent_response: dict[str, object] = {
        "retcode": 0,
        "action": "del",
        "message": "OK",
        "data": {"num": 1, "item": [{"ID": "999", "Ret": 0}]},
    }
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/del",
            payload=idempotent_response,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_group(id="999")


# -- T008, T012, T016, T020: Facade delegation tests --


@pytest.mark.asyncio
async def test_facade_list_groups_delegates() -> None:
    """Verify device.list_groups delegates to groups module."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/group/get",
            payload=_GROUP_EMPTY_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            result = await device.list_groups()
            assert isinstance(result, list)


@pytest.mark.asyncio
async def test_facade_add_group_delegates() -> None:
    """Verify device.add_group delegates to groups module."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/add",
            payload=_MUTATION_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_group(name="Test")


@pytest.mark.asyncio
async def test_facade_modify_group_delegates() -> None:
    """Verify device.modify_group delegates to groups module."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_group(id="1", name="New")


@pytest.mark.asyncio
async def test_facade_delete_group_delegates() -> None:
    """Verify device.delete_group delegates to groups module."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/group/del",
            payload=_DEL_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_group(id="1")
