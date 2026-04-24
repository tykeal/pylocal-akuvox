# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for contact management operations."""

from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxDeviceError,
    AkuvoxValidationError,
)

BASE_URL = "http://192.168.1.100"

_CONTACT_GET_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 2,
        "item": [
            {"ID": "1", "Name": "Alice", "Phone": "5551234", "Group": "Default"},
            {"ID": "2", "Name": "Bob", "Phone": "", "Group": "Staff"},
        ],
    },
}

_CONTACT_EMPTY_RESPONSE: dict[str, object] = {
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
        "item": [{"ID": "3", "Name": "Charlie", "Ret": 0}],
    },
}

_SET_OK_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "set",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [{"ID": "1", "Name": "Alice", "Ret": 0}],
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

_EMPTY_PAGE_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {"num": 0, "item": []},
}


# -- list_contacts tests --


@pytest.mark.asyncio
async def test_list_contacts_returns_contacts() -> None:
    """Verify list_contacts returns Contact objects."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get",
            payload=_CONTACT_GET_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            contacts = await device.list_contacts()
            assert len(contacts) == 2
            assert contacts[0].name == "Alice"
            assert contacts[0].id == "1"
            assert contacts[0].phone == "5551234"
            assert contacts[0].group == "Default"
            assert contacts[1].name == "Bob"
            assert contacts[1].id == "2"
            assert contacts[1].phone is None  # empty string → None
            assert contacts[1].group == "Staff"


@pytest.mark.asyncio
async def test_list_contacts_paginated() -> None:
    """Verify page parameter is passed to request."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get?page=2",
            payload=_CONTACT_EMPTY_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            contacts = await device.list_contacts(page=2)
            assert contacts == []


@pytest.mark.asyncio
async def test_list_contacts_empty() -> None:
    """Verify empty item list returns empty collection."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get",
            payload=_CONTACT_EMPTY_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            contacts = await device.list_contacts()
            assert contacts == []


@pytest.mark.asyncio
async def test_list_contacts_no_item_key() -> None:
    """Verify missing 'item' key returns empty list."""
    no_item: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/contact/get", payload=no_item)
        async with AkuvoxDevice("192.168.1.100") as device:
            contacts = await device.list_contacts()
            assert contacts == []


@pytest.mark.asyncio
async def test_list_contacts_non_list_items() -> None:
    """Verify non-list item field returns empty list."""
    bad_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": "not-a-list"},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/contact/get", payload=bad_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            contacts = await device.list_contacts()
            assert contacts == []


@pytest.mark.asyncio
async def test_list_contacts_skips_non_dict() -> None:
    """Verify non-dict entries are filtered out."""
    mixed_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 2,
            "item": [
                {"ID": "1", "Name": "Alice", "Phone": "5551234", "Group": "Default"},
                "not-a-dict",
                42,
            ],
        },
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/contact/get", payload=mixed_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            contacts = await device.list_contacts()
            assert len(contacts) == 1
            assert contacts[0].name == "Alice"


@pytest.mark.asyncio
async def test_list_contacts_missing_name_raises() -> None:
    """Verify list_contacts raises AkuvoxParseError for missing Name."""
    from pylocal_akuvox.exceptions import AkuvoxParseError

    bad_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {"ID": "1", "Phone": "5551234", "Group": "Default"},
            ],
        },
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/contact/get", payload=bad_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="Missing required field"):
                await device.list_contacts()


# -- add_contact tests --


@pytest.mark.asyncio
async def test_add_contact_sends_correct_payload() -> None:
    """Verify add_contact sends correct envelope to /api/contact/set."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_MUTATION_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_contact(name="Charlie")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))][0]
        body = req.kwargs["json"]
        assert body["target"] == "contact"
        assert body["action"] == "add"
        assert body["data"]["item"] == [{"Name": "Charlie"}]


@pytest.mark.asyncio
async def test_add_contact_with_group_and_phone() -> None:
    """Verify add_contact includes phone and group when provided."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_MUTATION_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_contact(
                name="Charlie",
                phone="5559999",
                group="Residents",
            )
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))][0]
        body = req.kwargs["json"]
        assert body["data"]["item"] == [
            {"Name": "Charlie", "Phone": "5559999", "Group": "Residents"}
        ]


@pytest.mark.asyncio
async def test_add_contact_empty_name_raises() -> None:
    """Verify empty name raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(
            AkuvoxValidationError,
            match="name is required",
        ):
            await device.add_contact(name="")


# -- modify_contact tests --


@pytest.mark.asyncio
async def test_modify_contact_fetches_and_merges() -> None:
    """Verify modify_contact does fetch-merge-write."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=_CONTACT_GET_RESPONSE,
        )
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_contact(id="1", name="Alice Updated", phone="5550000")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))][0]
        body = req.kwargs["json"]
        assert body["target"] == "contact"
        assert body["action"] == "set"
        item = body["data"]["item"][0]
        assert item["Name"] == "Alice Updated"
        assert item["Phone"] == "5550000"
        assert item["ID"] == "1"


@pytest.mark.asyncio
async def test_modify_contact_changes_group() -> None:
    """Verify modify_contact can change group membership."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=_CONTACT_GET_RESPONSE,
        )
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_contact(id="1", group="VIP")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))][0]
        body = req.kwargs["json"]
        item = body["data"]["item"][0]
        assert item["Group"] == "VIP"
        # Name should remain unchanged
        assert item["Name"] == "Alice"


@pytest.mark.asyncio
async def test_modify_contact_not_found_raises() -> None:
    """Verify modify_contact raises when ID not found."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=_CONTACT_GET_RESPONSE,
        )
        m.get(
            f"{BASE_URL}/api/contact/get?page=2",
            payload=_EMPTY_PAGE_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="Contact ID 999 not found"):
                await device.modify_contact(id="999", name="Ghost")


@pytest.mark.asyncio
async def test_modify_contact_no_fields_raises() -> None:
    """Verify modify_contact raises when no fields are provided."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(
            AkuvoxValidationError,
            match="at least one of name, phone, or group",
        ):
            await device.modify_contact(id="1")


# -- delete_contact tests --


@pytest.mark.asyncio
async def test_delete_contact_single() -> None:
    """Verify delete_contact sends single ID."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_DEL_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_contact(id="1")
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))][0]
        body = req.kwargs["json"]
        assert body["target"] == "contact"
        assert body["action"] == "del"
        assert body["data"]["item"] == [{"ID": "1"}]


@pytest.mark.asyncio
async def test_delete_contact_batch() -> None:
    """Verify delete_contact sends multiple IDs."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_DEL_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_contact(id=["2", "3"])
        req = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))][0]
        body = req.kwargs["json"]
        assert body["data"]["item"] == [{"ID": "2"}, {"ID": "3"}]


# -- Facade delegation tests --


@pytest.mark.asyncio
async def test_device_list_contacts_delegates() -> None:
    """Verify device.list_contacts delegates to contacts module."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get",
            payload=_CONTACT_EMPTY_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            result = await device.list_contacts()
            assert isinstance(result, list)


@pytest.mark.asyncio
async def test_device_add_contact_delegates() -> None:
    """Verify device.add_contact delegates to contacts module."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_MUTATION_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_contact(name="Test")


@pytest.mark.asyncio
async def test_device_modify_contact_delegates() -> None:
    """Verify device.modify_contact delegates to contacts module."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=_CONTACT_GET_RESPONSE,
        )
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_contact(id="1", name="Updated")


@pytest.mark.asyncio
async def test_device_delete_contact_delegates() -> None:
    """Verify device.delete_contact delegates to contacts module."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_DEL_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_contact(id="1")
