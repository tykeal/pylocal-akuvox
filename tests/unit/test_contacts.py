# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for contact management operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxDeviceError,
    AkuvoxValidationError,
)
from tests.unit._helpers import register_default_info

if TYPE_CHECKING:
    from pylocal_akuvox.capabilities import Capability, CapabilityStatus

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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
        m.get(f"{BASE_URL}/api/contact/get", payload=bad_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxParseError, match="Missing required field"):
                await device.list_contacts()


# -- add_contact tests --


@pytest.mark.asyncio
async def test_add_contact_sends_correct_payload() -> None:
    """Verify add_contact sends correct envelope to /api/contact/set."""
    with aioresponses() as m:
        register_default_info(m)
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
        register_default_info(m)
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
    with aioresponses() as m:
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
async def test_modify_contact_non_list_items_raises() -> None:
    """Verify modify_contact raises when item is not a list."""
    non_list_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": "not-a-list"},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=non_list_response,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(
                AkuvoxDeviceError,
                match="Contact ID 1 not found",
            ):
                await device.modify_contact(id="1", name="Ghost")


@pytest.mark.asyncio
async def test_modify_contact_non_dict_entries_raises() -> None:
    """Verify modify_contact raises when items contain non-dicts."""
    non_dict_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 2, "item": ["string-entry", 42]},
    }
    empty_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": []},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=non_dict_response,
        )
        m.get(
            f"{BASE_URL}/api/contact/get?page=2",
            payload=empty_response,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(
                AkuvoxDeviceError,
                match="Contact ID 1 not found",
            ):
                await device.modify_contact(id="1", name="Ghost")


@pytest.mark.asyncio
async def test_modify_contact_no_fields_raises() -> None:
    """Verify modify_contact raises when no fields are provided."""
    with aioresponses() as m:
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
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
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_DEL_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_contact(id="1")


# ============================================================================
# Phase 3 tests: schema-shape plumbing (T060, T066, T066a)
# ============================================================================


# -- T060: Contact.from_api_response capabilities= kwarg --


def test_contact_from_api_response_door_phone_default() -> None:
    """T060: ``capabilities=None`` keeps door-phone byte-identity.

    Direct callers that omit ``capabilities`` (or pass ``None``) see
    byte-identical behaviour to the pre-refactor parser: ``Name`` is
    required; missing ``Name`` raises :class:`AkuvoxParseError`;
    optional ``ID``/``Phone``/``Group`` pass through. Pins FR-016.
    """
    from pylocal_akuvox.exceptions import AkuvoxParseError
    from pylocal_akuvox.models import Contact

    data = {"ID": "1", "Name": "Alice", "Phone": "555-1", "Group": "Default"}
    c1 = Contact.from_api_response(data)
    c2 = Contact.from_api_response(data, capabilities=None)
    assert c1 == c2
    assert c1.name == "Alice"
    assert c1.id == "1"
    assert c1.phone == "555-1"
    assert c1.group == "Default"

    # Missing Name still raises.
    with pytest.raises(AkuvoxParseError, match="Missing required field"):
        Contact.from_api_response({"ID": "1"})


def test_contact_from_api_response_apartment_book_no_id() -> None:
    """T060: APARTMENT_BOOK shape parses without ``ID``.

    Issue #121: X915S apartment-book responses omit ``ID`` entirely.
    The door-phone parser doesn't actually require ``ID`` (it's
    ``data.get("ID")``), but the apartment-book branch also accepts
    the extra ``APTName``/``APTNum``/``Building``/``Landline`` keys
    without raising. Asserts the apartment-book branch is reached
    and returns a usable :class:`Contact`.
    """
    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        SchemaShape,
    )
    from pylocal_akuvox.models import Contact

    caps = DeviceCapabilities(
        device_class="X915S",
        firmware_version="2915.30.10.114",
        capabilities={},
        field_aliases={},
        schema_shapes={"contact": SchemaShape.APARTMENT_BOOK},
    )
    data = {
        "Name": "Apt 101 Resident",
        "APTName": "Building A",
        "APTNum": "101",
        "Building": "A",
        "Landline": "5550100",
        # NO "ID" field — apartment-book payloads may omit it.
    }
    c = Contact.from_api_response(data, capabilities=caps)
    assert c.name == "Apt 101 Resident"
    assert c.id is None
    # Apartment-book fields are accepted but not surfaced on the
    # public model yet — only the parser tolerates them.


def test_contact_from_api_response_door_phone_explicit_shape() -> None:
    """T060: explicit DOOR_PHONE shape == default behaviour.

    Passing a capability record whose ``schema_shapes["contact"]`` is
    explicitly ``DOOR_PHONE`` produces the same ``Contact`` instance
    as the no-capabilities default — locks FR-016.
    """
    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        SchemaShape,
    )
    from pylocal_akuvox.models import Contact

    caps = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities={},
        field_aliases={},
        schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    )
    data = {"ID": "1", "Name": "Alice", "Phone": "555-1", "Group": "Default"}
    a = Contact.from_api_response(data)
    b = Contact.from_api_response(data, capabilities=caps)
    assert a == b


def test_contact_from_api_response_capabilities_without_shape_key_falls_back() -> None:
    """T060: capability record without ``"contact"`` shape falls back to DOOR_PHONE.

    The fallback branch of T065 — covered explicitly so the
    apartment-book branch can never be reached when the matrix entry
    forgot to populate ``schema_shapes["contact"]``.
    """
    from pylocal_akuvox.capabilities import DeviceCapabilities
    from pylocal_akuvox.models import Contact

    caps = DeviceCapabilities(
        device_class="Synth",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={},
        schema_shapes={},  # no "contact" key
    )
    data = {"ID": "9", "Name": "Bob"}
    c = Contact.from_api_response(data, capabilities=caps)
    assert c.name == "Bob"
    assert c.id == "9"


# -- T066: contacts.add_contact / modify_contact schema_shape= kwarg --


async def test_add_contact_service_function_default_shape_byte_identical() -> None:
    """T066: ``add_contact`` with no kwarg == ``schema_shape=DOOR_PHONE``.

    Direct service-function callers that omit the new kwarg see
    byte-identical payloads to calls that explicitly pass
    ``SchemaShape.DOOR_PHONE`` — pins FR-016 for the door-phone
    write path.
    """
    import json

    from pylocal_akuvox import contacts as contacts_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import SchemaShape

    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/contact/set",
            payload=_MUTATION_OK_RESPONSE,
            repeat=True,
        )
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await contacts_svc.add_contact(http, name="x", phone="555")
            await contacts_svc.add_contact(
                http, name="x", phone="555", schema_shape=SchemaShape.DOOR_PHONE
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))
        calls = m.requests[url_key]
        assert len(calls) == 2
        a = json.dumps(calls[0].kwargs.get("json"), sort_keys=False)
        b = json.dumps(calls[1].kwargs.get("json"), sort_keys=False)
        assert a == b


async def test_add_contact_service_function_apartment_book_raises() -> None:
    """T066: ``schema_shape=APARTMENT_BOOK`` raises ``NotImplementedError``.

    Apartment-book writes are explicitly deferred — the message names
    the missing source for ``APTName``/``APTNum``/``Building``/
    ``Landline`` so an integrator can pivot.
    """
    from pylocal_akuvox import contacts as contacts_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import SchemaShape

    with aioresponses() as m:
        # No HTTP mock needed — service function raises before the
        # request leaves the process.
        async with AkuvoxHttpClient("192.168.1.100") as http:
            with pytest.raises(NotImplementedError, match="apartment-book"):
                await contacts_svc.add_contact(
                    http, name="x", schema_shape=SchemaShape.APARTMENT_BOOK
                )
        # No request should have been issued.
        assert m.requests == {}


async def test_modify_contact_service_function_apartment_book_raises() -> None:
    """T066: ``modify_contact`` apartment-book path raises ``NotImplementedError``.

    Mirror of the add-side deferral: same deferral message, same
    no-request guarantee.
    """
    from pylocal_akuvox import contacts as contacts_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import SchemaShape

    with aioresponses() as m:
        async with AkuvoxHttpClient("192.168.1.100") as http:
            with pytest.raises(NotImplementedError, match="apartment-book"):
                await contacts_svc.modify_contact(
                    http, id="1", name="x", schema_shape=SchemaShape.APARTMENT_BOOK
                )
        assert m.requests == {}


async def test_modify_contact_service_function_door_phone_byte_identical() -> None:
    """T066: ``modify_contact`` with no kwarg == ``schema_shape=DOOR_PHONE``.

    Direct callers that omit the kwarg see byte-identical merge-and-set
    payloads to the explicit DOOR_PHONE path.
    """
    import json

    from pylocal_akuvox import contacts as contacts_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import SchemaShape

    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/contact/get?page=1",
            payload=_CONTACT_GET_RESPONSE,
            repeat=True,
        )
        m.post(f"{BASE_URL}/api/contact/set", payload=_SET_OK_RESPONSE, repeat=True)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await contacts_svc.modify_contact(http, id="1", name="Alice2")
            await contacts_svc.modify_contact(
                http, id="1", name="Alice2", schema_shape=SchemaShape.DOOR_PHONE
            )
        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))
        calls = m.requests[url_key]
        assert len(calls) == 2
        a = json.dumps(calls[0].kwargs.get("json"), sort_keys=False)
        b = json.dumps(calls[1].kwargs.get("json"), sort_keys=False)
        assert a == b


# -- T066 wrapper dispatch pin --


async def test_wrapper_add_contact_passes_door_phone_for_x916() -> None:
    """T066: wrapper extracts ``schema_shapes["contact"]`` and passes it.

    Verifies dispatch end-to-end: X916 matrix entry pins
    ``schema_shapes["contact"] = DOOR_PHONE`` (after T067), so the
    wrapper extracts DOOR_PHONE and the service function emits today's
    payload byte-identically. Asserted via the on-the-wire payload
    matching the existing default-add test fixture.
    """
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/contact/set", payload=_MUTATION_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_contact(name="Charlie", phone="555")

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/contact/set"))
        body = m.requests[url_key][0].kwargs.get("json")
        item = body["data"]["item"][0]
        assert item["Name"] == "Charlie"
        assert item["Phone"] == "555"
        # Door-phone branch — no apartment-book keys leak through.
        assert "APTName" not in item
        assert "Landline" not in item


# -- T066a: read-path schema-shape plumbing (list_contacts) --


async def test_list_contacts_threads_apartment_book_through_wrapper() -> None:
    """T066a: ``AkuvoxDevice.list_contacts`` threads ``capabilities=`` end-to-end.

    Injects a synthetic capability profile with
    ``schema_shapes["contact"] = APARTMENT_BOOK`` and mocks
    ``/api/contact/get`` to return apartment-book-style items with no
    ``ID`` field. Both parser branches currently treat ``ID`` as
    optional (``data.get("ID")``), so payload structure alone does
    not discriminate — we additionally spy on
    :meth:`Contact.from_api_response` to assert it is invoked with
    ``capabilities=custom_caps``. The spy is what makes this test
    MUST-fail if the wrapper drops the ``capabilities=`` kwarg
    (Copilot review round 1 strengthened-discriminator).
    """
    from unittest.mock import patch

    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        SchemaShape,
    )
    from pylocal_akuvox.models import Contact

    custom_caps = DeviceCapabilities(
        device_class="X916",  # match register_default_info
        firmware_version="916.30.10.114",
        capabilities=_x916_all_supported_capabilities(),
        field_aliases={},
        schema_shapes={"contact": SchemaShape.APARTMENT_BOOK},
    )

    apt_payload = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {
                    "Name": "Apt 101 Resident",
                    "APTName": "Building A",
                    "APTNum": "101",
                    "Building": "A",
                    "Landline": "5550100",
                    # NO "ID"
                },
            ],
        },
    }

    original_from_api = Contact.from_api_response
    seen_capabilities: list[DeviceCapabilities | None] = []

    def _spy(data: object, **kwargs: object) -> Contact:
        """Capture ``capabilities=`` kwarg, then delegate to the real parser."""
        seen_capabilities.append(kwargs.get("capabilities"))  # type: ignore[arg-type]
        return original_from_api(data, **kwargs)  # type: ignore[arg-type]

    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/contact/get", payload=apt_payload)
        async with AkuvoxDevice("192.168.1.100") as device:
            device._capabilities = custom_caps  # noqa: SLF001
            with patch.object(Contact, "from_api_response", side_effect=_spy):
                results = await device.list_contacts()

    assert len(results) == 1
    assert results[0].name == "Apt 101 Resident"
    assert results[0].id is None
    # The strong-discriminator assertion: every parse call received
    # the wrapper-extracted capabilities — proves end-to-end
    # threading from ``AkuvoxDevice.list_contacts`` through
    # ``contacts.list_contacts`` into ``Contact.from_api_response``.
    assert seen_capabilities == [custom_caps]


async def test_list_contacts_default_door_phone_byte_identical() -> None:
    """T066a (baseline): empty ``schema_shapes`` parses as door-phone.

    Pins FR-016: an X916-flavour device with empty ``schema_shapes``
    parses contacts byte-identically to the pre-refactor behaviour —
    door-phone path, ``Name`` required, ``ID`` optional.
    """
    from pylocal_akuvox.capabilities import DeviceCapabilities

    custom_caps = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities=_x916_all_supported_capabilities(),
        field_aliases={},
        schema_shapes={},  # falls through to DOOR_PHONE
    )
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/contact/get", payload=_CONTACT_GET_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            device._capabilities = custom_caps  # noqa: SLF001
            results = await device.list_contacts()
    assert len(results) == 2
    assert results[0].name == "Alice"
    assert results[0].id == "1"


def _x916_all_supported_capabilities() -> dict[Capability, CapabilityStatus]:
    """Build the ``capabilities`` mapping for a synthetic X916-like profile."""
    from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX

    for _pattern, caps in CAPABILITY_MATRIX:
        if caps.device_class == "X916":
            return dict(caps.capabilities)
    msg = "X916 baseline entry missing from capability matrix"
    raise AssertionError(msg)
