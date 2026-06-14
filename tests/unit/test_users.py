# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for user operations: PIN validation and CRUD."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxValidationError,
)
from pylocal_akuvox.users import validate_pin, validate_schedule_relay
from tests.unit._helpers import register_default_info

if TYPE_CHECKING:
    from pylocal_akuvox.capabilities import Capability, CapabilityStatus

BASE_URL = "http://192.168.1.100"

# Mock response for user-get used by modify_user read-modify-write
_USER_GET_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {
        "num": 1,
        "item": [
            {
                "ID": "1",
                "Name": "Alice",
                "UserID": "2001",
                "WebRelay": "0",
                "ScheduleRelay": "1001-1",
                "LiftFloorNum": "0",
                "PrivatePIN": "",
                "CardCode": "",
            },
        ],
    },
}

_SET_OK_RESPONSE: dict[str, object] = {
    "retcode": 1,
    "action": "set",
    "message": "OK",
    "data": {},
}

_EMPTY_PAGE_RESPONSE: dict[str, object] = {
    "retcode": 0,
    "action": "get",
    "message": "OK",
    "data": {"num": 1, "item": []},
}

# -- T026: PIN validation tests --


def test_validate_pin_4_digits() -> None:
    """Verify 4-digit PIN is accepted."""
    validate_pin("1234")


def test_validate_pin_8_digits() -> None:
    """Verify 8-digit PIN is accepted."""
    validate_pin("12345678")


def test_validate_pin_0000_valid() -> None:
    """Verify '0000' is a valid PIN."""
    validate_pin("0000")


def test_validate_pin_none_allowed() -> None:
    """Verify None PIN is allowed (optional field)."""
    validate_pin(None)


def test_validate_pin_empty_allowed() -> None:
    """Verify empty string PIN is allowed (optional field)."""
    validate_pin("")


def test_validate_pin_too_short_rejected() -> None:
    """Verify <4 digit PIN is rejected."""
    with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
        validate_pin("123")


def test_validate_pin_too_long_rejected() -> None:
    """Verify >8 digit PIN is rejected."""
    with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
        validate_pin("123456789")


def test_validate_pin_non_digit_rejected() -> None:
    """Verify non-digit characters in PIN are rejected."""
    with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
        validate_pin("12ab")


def test_validate_pin_5_digits() -> None:
    """Verify 5-digit PIN is accepted."""
    validate_pin("12345")


def test_validate_pin_6_digits() -> None:
    """Verify 6-digit PIN is accepted."""
    validate_pin("123456")


def test_validate_pin_7_digits() -> None:
    """Verify 7-digit PIN is accepted."""
    validate_pin("1234567")


# -- T026: schedule_relay validation --


def test_validate_schedule_relay_valid_single() -> None:
    """Verify single schedule-relay pair is accepted."""
    validate_schedule_relay("1001-1")


def test_validate_schedule_relay_valid_multiple() -> None:
    """Verify multiple schedule-relay pairs are accepted."""
    validate_schedule_relay("1001-1,1002-2")


def test_validate_schedule_relay_trailing_comma() -> None:
    """Verify trailing comma is tolerated."""
    validate_schedule_relay("1001-1,1002-2,")


def test_validate_schedule_relay_none_allowed() -> None:
    """Verify None schedule_relay is allowed."""
    validate_schedule_relay(None)


def test_validate_schedule_relay_empty_allowed() -> None:
    """Verify empty string schedule_relay is allowed in validator.

    The validator allows empty for optional contexts (modify_user).
    add_user enforces non-empty separately.
    """
    validate_schedule_relay("")


def test_validate_schedule_relay_semicolon_rejected() -> None:
    """Verify semicolon separator is rejected (comma is correct)."""
    with pytest.raises(AkuvoxValidationError, match="schedule_relay"):
        validate_schedule_relay("1001-1;1002-2;")


def test_validate_schedule_relay_invalid_format() -> None:
    """Verify non-numeric format is rejected."""
    with pytest.raises(AkuvoxValidationError, match="schedule_relay"):
        validate_schedule_relay("abc-xyz")


# -- T027: User CRUD operation tests --


async def test_add_user_posts_to_correct_endpoint() -> None:
    """Verify add_user POSTs to /api/user/set with required fields."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "add",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "user"
        assert body["action"] == "add"
        item = body["data"]["item"][0]
        assert item["Name"] == "Alice"
        assert item["UserID"] == "2001"
        assert item["WebRelay"] == "0"
        assert item["ScheduleRelay"] == "1001-1"
        assert item["LiftFloorNum"] == "0"


async def test_add_user_emits_dual_primary_relay_schedule_keys() -> None:
    """Verify add_user emits both primary schedule field names."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "add",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert item["ScheduleRelay"] == "1001-1"
        assert item["Schedule-Relay"] == "1001-1"


async def test_add_user_does_not_introduce_secondary_relay_keys() -> None:
    """Verify add_user does not emit secondary schedule fields."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "add",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert "ScheduleSRelay" not in item
        assert "Schedule-SRelay" not in item


async def test_add_user_with_pin() -> None:
    """Verify add_user includes optional PIN in payload."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "add",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                private_pin="1234",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )


async def test_add_user_invalid_pin_raises_validation_error() -> None:
    """Verify add_user with invalid PIN raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    private_pin="12ab",
                    web_relay="0",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )


async def test_add_user_invalid_schedule_relay_raises() -> None:
    """Verify add_user with invalid schedule_relay raises."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="schedule_relay"):
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    web_relay="0",
                    schedule_relay="bad-format",
                    lift_floor_num="0",
                )


async def test_add_user_empty_schedule_relay_raises() -> None:
    """Verify add_user rejects empty schedule_relay (required field)."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="schedule_relay"):
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    web_relay="0",
                    schedule_relay="",
                    lift_floor_num="0",
                )


async def test_modify_user_empty_pin_omitted() -> None:
    """Verify modify_user normalizes empty string PIN to None (omit)."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(id="1", private_pin="", name="Updated")

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "user"
        assert body["action"] == "set"
        item = body["data"]["item"][0]
        # Empty PIN normalized to None - field not updated, original value preserved
        assert item["ID"] == "1"
        assert item["Name"] == "Updated"
        assert item["PrivatePIN"] == ""


async def test_list_users_posts_to_correct_endpoint() -> None:
    """Verify list_users GETs from /api/user/get and returns User list."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/user/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "",
                "data": {
                    "num": 2,
                    "curPageNum": 2,
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
                            "Type": "ordinary",
                            "Source": "web",
                            "SourceType": "Local",
                        },
                        {
                            "ID": "2",
                            "Name": "Bob",
                            "UserID": "2002",
                            "WebRelay": "0",
                            "ScheduleRelay": "1001-1",
                        },
                    ],
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            users = await device.list_users()

    assert len(users) == 2
    assert users[0].name == "Alice"
    assert users[0].private_pin == "1234"
    assert users[1].name == "Bob"


async def test_list_users_paginated() -> None:
    """Verify list_users with page parameter sends page as query param."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/user/get?page=1",
            payload={
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
                            "WebRelay": "0",
                            "ScheduleRelay": "1001-1",
                        },
                    ],
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            users = await device.list_users(page=1)

        url_key = ("GET", aiohttp.client.URL(f"{BASE_URL}/api/user/get?page=1"))
        assert url_key in m.requests

    assert len(users) == 1


async def test_list_users_empty_returns_empty_list() -> None:
    """Verify list_users with no users returns empty list."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/user/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "",
                "data": {
                    "num": 0,
                    "curPageNum": 0,
                    "item": [],
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            users = await device.list_users()

    assert users == []


async def test_modify_user_posts_to_correct_endpoint() -> None:
    """Verify modify_user fetches user then POSTs to /api/user/set."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(id="1", private_pin="5678")


async def test_modify_user_emits_dual_primary_relay_schedule_keys() -> None:
    """Verify modify_user emits both primary schedule field names."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(id="1", schedule_relay="1002-2")

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert item["ScheduleRelay"] == "1002-2"
        assert item["Schedule-Relay"] == "1002-2"


async def test_modify_user_omits_primary_schedule_keys_when_unset() -> None:
    """Verify modify_user omits primary schedule fields when unset."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(id="1", name="Updated")

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert "ScheduleRelay" not in item
        assert "Schedule-Relay" not in item


async def test_modify_user_keeps_secondary_relay_single_key() -> None:
    """Verify ScheduleSRelay keeps no hyphenated companion."""
    response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {
                    "ID": "1",
                    "Name": "Alice",
                    "UserID": "2001",
                    "WebRelay": "0",
                    "ScheduleRelay": "1001-1",
                    "ScheduleSRelay": "1001-2",
                    "LiftFloorNum": "0",
                    "PrivatePIN": "",
                    "CardCode": "",
                },
            ],
        },
    }

    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=response)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(id="1", schedule_relay="1002-2")

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert item["ScheduleSRelay"] == "1001-2"
        assert "Schedule-SRelay" not in item


async def test_modify_user_invalid_pin_raises() -> None:
    """Verify modify_user with invalid PIN raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
                await device.modify_user(id="1", private_pin="bad")


async def test_delete_user_posts_to_correct_endpoint() -> None:
    """Verify delete_user POSTs to /api/user/set with ID."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "del",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.delete_user(id="1")


async def test_add_user_duplicate_returns_device_error() -> None:
    """Verify duplicate user add returns non-zero retcode as error."""
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": -1,
                "action": "add",
                "message": "User already exists",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError):
                await device.add_user(
                    name="Alice",
                    user_id="2001",
                    web_relay="0",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )


async def test_add_user_with_card_code() -> None:
    """Verify add_user includes card_code in payload."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "add",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                web_relay="0",
                schedule_relay="1001-1",
                lift_floor_num="0",
                card_code="RFID1234",
            )


async def test_list_users_non_list_items_returns_empty() -> None:
    """Verify list_users returns empty list if items is not a list."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/user/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "",
                "data": {"num": 0, "curPageNum": 0, "item": "not-a-list"},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            users = await device.list_users()

    assert users == []


async def test_modify_user_all_fields() -> None:
    """Verify modify_user sends all optional fields when provided."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(
                id="1",
                name="Updated",
                user_id="3001",
                private_pin="9999",
                card_code="NEW_CARD",
                web_relay="1",
                schedule_relay="1002-2",
                lift_floor_num="5",
            )


async def test_modify_user_without_pin() -> None:
    """Verify modify_user works without private_pin."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(
                id="1",
                name="Updated",
                card_code="CARD123",
            )


async def test_modify_user_not_found_raises() -> None:
    """Verify modify_user raises when user ID not found."""
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.get(f"{BASE_URL}/api/user/get?page=2", payload=_EMPTY_PAGE_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="not found"):
                await device.modify_user(id="999", name="Ghost")


async def test_modify_user_malformed_item_raises() -> None:
    """Verify modify_user raises when item list is not a list."""
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    bad_response: dict[str, object] = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {"num": 0, "item": "not-a-list"},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=bad_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="not found"):
                await device.modify_user(id="1", name="Ghost")


async def test_add_user_empty_name_raises() -> None:
    """Verify add_user rejects empty name (required field)."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="name"):
                await device.add_user(
                    name="",
                    user_id="2001",
                    web_relay="0",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )


async def test_add_user_empty_user_id_raises() -> None:
    """Verify add_user rejects empty user_id (required field)."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="user_id"):
                await device.add_user(
                    name="Alice",
                    user_id="",
                    web_relay="0",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                )


async def test_add_user_without_web_relay() -> None:
    """Verify add_user omits WebRelay when not provided."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload={
                "retcode": 0,
                "action": "add",
                "message": "",
                "data": {},
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="2001",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/user/set"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert "WebRelay" not in item


async def test_list_users_non_dict_items_skipped() -> None:
    """Verify list_users skips non-dict items in the response."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(
            f"{BASE_URL}/api/user/get",
            payload={
                "retcode": 0,
                "action": "get",
                "message": "",
                "data": {
                    "num": 2,
                    "curPageNum": 2,
                    "item": [
                        {
                            "ID": "1",
                            "Name": "Alice",
                            "UserID": "2001",
                            "WebRelay": "0",
                            "ScheduleRelay": "1001-1",
                        },
                        "not-a-dict",
                        42,
                    ],
                },
            },
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            users = await device.list_users()

    assert len(users) == 1
    assert users[0].name == "Alice"


# ============================================================================
# Phase 3 tests: field-aliases plumbing (T058, T059, T064a, T066b)
# ============================================================================
#
# These tests cover the capability-aware refactor of ``users.add_user`` /
# ``users.modify_user`` / ``users.list_users`` (service-module layer) and
# the ``AkuvoxDevice`` wrappers that extract field aliases from
# ``self._capabilities`` and pass them as the keyword-only ``field_aliases=``
# / ``capabilities=`` kwargs. See tasks T058 (parser unit test), T059
# (write-path service + wrapper tests), and T064a (read-path end-to-end
# plumbing).


# -- T058: User.from_api_response capabilities= kwarg --


def test_user_from_api_response_consults_capability_field_aliases() -> None:
    """T058: synthetic capability custom read alias is honoured.

    When the caller supplies a :class:`DeviceCapabilities` whose
    ``field_aliases["schedule_relay"].read`` is ``("CustomFieldName",)``,
    the parser picks up the value at ``"CustomFieldName"`` and ignores
    every name in the default chain (``"ScheduleRelay"``,
    ``"Schedule-Relay"``, ``"Schedule"``). This proves the parser
    consults the supplied record, not a hardcoded fallback.
    """
    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        FieldAliases,
    )
    from pylocal_akuvox.models import User

    caps = DeviceCapabilities(
        device_class="Synth",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={
            "schedule_relay": FieldAliases(read=("CustomFieldName",), write=()),
        },
        schema_shapes={},
    )
    # Payload also carries the default chain — synthetic alias must win.
    data = {
        "Name": "Alice",
        "UserID": "1",
        "CustomFieldName": "custom-value",
        "ScheduleRelay": "default-ignored",
        "Schedule-Relay": "default-ignored",
        "Schedule": "default-ignored",
    }
    user = User.from_api_response(data, capabilities=caps)
    assert user.schedule_relay == "custom-value"


def test_user_from_api_response_capabilities_none_uses_default_chain() -> None:
    """T058: ``capabilities=None`` keeps the legacy default chain.

    The default fallback list is ``DEFAULT_USER_FIELD_ALIASES.read`` ==
    ``("ScheduleRelay", "Schedule-Relay", "Schedule")``. Direct callers
    that omit ``capabilities`` (or pass ``None``) see byte-identical
    behaviour to the pre-refactor parser (FR-016).
    """
    from pylocal_akuvox.models import User

    data = {"Name": "Alice", "UserID": "1", "Schedule": "x"}
    # Both forms parse identically.
    a = User.from_api_response(data)
    b = User.from_api_response(data, capabilities=None)
    assert a.schedule_relay == "x"
    assert b.schedule_relay == "x"


def test_user_from_api_response_capabilities_without_alias_key_falls_back() -> None:
    """T058: capability record without ``"schedule_relay"`` falls back to default.

    A ``DeviceCapabilities`` whose ``field_aliases`` mapping has no
    ``"schedule_relay"`` entry resolves via the parser's
    :data:`DEFAULT_USER_FIELD_ALIASES` fallback — same chain as the
    no-capabilities path. Covers the fallback branch of T063.
    """
    from pylocal_akuvox.capabilities import DeviceCapabilities
    from pylocal_akuvox.models import User

    caps = DeviceCapabilities(
        device_class="Synth",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={},  # no schedule_relay key
        schema_shapes={},
    )
    data = {"Name": "Bob", "UserID": "2", "Schedule-Relay": "y"}
    user = User.from_api_response(data, capabilities=caps)
    assert user.schedule_relay == "y"


def test_user_from_api_response_alias_order_is_honoured() -> None:
    """T058: parser walks ``read`` aliases in declared order, not default.

    With aliases reversed from the default chain
    (``("Schedule", "ScheduleRelay", "Schedule-Relay")``) and a payload
    carrying both ``"ScheduleRelay"`` and ``"Schedule"`` keys, the
    parser must return the ``"Schedule"`` value because it appears
    first in the declared read list — proving the parser consults the
    supplied order, not the hardcoded default which checks
    ``"ScheduleRelay"`` first.
    """
    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        FieldAliases,
    )
    from pylocal_akuvox.models import User

    caps = DeviceCapabilities(
        device_class="Synth",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={
            "schedule_relay": FieldAliases(
                read=("Schedule", "ScheduleRelay", "Schedule-Relay"), write=()
            ),
        },
        schema_shapes={},
    )
    data = {
        "Name": "Alice",
        "UserID": "1",
        "ScheduleRelay": "default-first",
        "Schedule": "synthetic-first",
    }
    user = User.from_api_response(data, capabilities=caps)
    assert user.schedule_relay == "synthetic-first"


# -- T059: users.add_user / users.modify_user field_aliases= kwarg --


async def test_add_user_service_function_field_aliases_kwarg() -> None:
    """T059: ``users.add_user(field_aliases=...)`` emits each write alias.

    A custom ``FieldAliases(write=("Custom", "Custom-Alt"))`` causes
    the service function to emit BOTH names in the JSON payload, each
    carrying the schedule-relay value. Default ``ScheduleRelay`` /
    ``Schedule-Relay`` keys must be absent (the custom write list
    fully replaces them).
    """
    from pylocal_akuvox import users as users_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import FieldAliases

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await users_svc.add_user(
                http,
                name="Alice",
                user_id="1",
                schedule_relay="1001-1",
                lift_floor_num="0",
                field_aliases=FieldAliases(read=(), write=("Custom", "Custom-Alt")),
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        body = m.requests[url_key][0].kwargs.get("json")
        item = body["data"]["item"][0]
        assert item["Custom"] == "1001-1"
        assert item["Custom-Alt"] == "1001-1"
        # Default keys must NOT appear when a custom write list is supplied.
        assert "ScheduleRelay" not in item
        assert "Schedule-Relay" not in item


async def test_add_user_service_function_no_kwarg_byte_identical() -> None:
    """T059: omitting ``field_aliases=`` emits today's dual-write payload.

    Pins FR-016 — direct callers of the service function that do not
    pass the new kwarg see byte-identical payloads to the pre-refactor
    behaviour. Compared against a parallel call that explicitly passes
    ``DEFAULT_USER_FIELD_ALIASES`` — both must produce identical
    JSON bodies (same keys, same values, same order).
    """
    import json

    from pylocal_akuvox import users as users_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import DEFAULT_USER_FIELD_ALIASES

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE, repeat=True)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await users_svc.add_user(
                http,
                name="Alice",
                user_id="1",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )
            await users_svc.add_user(
                http,
                name="Alice",
                user_id="1",
                schedule_relay="1001-1",
                lift_floor_num="0",
                field_aliases=DEFAULT_USER_FIELD_ALIASES,
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        calls = m.requests[url_key]
        assert len(calls) == 2
        body_a = json.dumps(calls[0].kwargs.get("json"), sort_keys=False)
        body_b = json.dumps(calls[1].kwargs.get("json"), sort_keys=False)
        assert body_a == body_b


async def test_modify_user_service_function_field_aliases_kwarg() -> None:
    """T059: ``users.modify_user`` honours custom write aliases on set.

    Emits each name in ``field_aliases.write`` with the new value;
    the service function stays capability-unaware so any extra keys
    inherited from the fetched record pass through unchanged
    (capability extraction lives on the wrapper layer per T064).
    """
    from pylocal_akuvox import users as users_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import FieldAliases

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await users_svc.modify_user(
                http,
                id="1",
                schedule_relay="2002-2",
                field_aliases=FieldAliases(read=(), write=("Custom", "Custom-Alt")),
            )
        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        item = m.requests[url_key][0].kwargs.get("json")["data"]["item"][0]
        assert item["Custom"] == "2002-2"
        assert item["Custom-Alt"] == "2002-2"


# -- T059 (wrapper-layer): AkuvoxDevice.add_user / modify_user extract aliases --


async def test_wrapper_add_user_passes_default_field_aliases_for_x916() -> None:
    """T059 wrapper: X916 wrapper passes ``DEFAULT_USER_FIELD_ALIASES``.

    Verified end-to-end via the on-the-wire payload: an X916 device
    (matrix entry pins ``field_aliases["schedule_relay"] =
    DEFAULT_USER_FIELD_ALIASES``) emits both ``ScheduleRelay`` and
    ``Schedule-Relay`` keys in the add payload, matching the
    pre-refactor dual-write byte-for-byte.
    """
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.add_user(
                name="Alice",
                user_id="1",
                schedule_relay="1001-1",
                lift_floor_num="0",
            )
        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        item = m.requests[url_key][0].kwargs.get("json")["data"]["item"][0]
        assert item["ScheduleRelay"] == "1001-1"
        assert item["Schedule-Relay"] == "1001-1"


# -- T064a: read-path plumbing (list_users threading capabilities=) --


async def test_list_users_threads_synthetic_alias_through_wrapper() -> None:
    """T064a: ``AkuvoxDevice.list_users`` passes capabilities to parser.

    Wires a synthetic capability matrix entry so the X916-prefixed
    device used by ``register_default_info`` carries a custom alias
    list (``read=("CustomScheduleField",)``). Mocks ``/api/user/get``
    to return items keyed only with ``"CustomScheduleField"`` (no
    default chain key). The default parser would raise
    :class:`AkuvoxParseError` on missing ``"ScheduleRelay"`` /
    ``"Schedule-Relay"`` / ``"Schedule"``; the test passes only if
    the wrapper threads its capability record all the way through to
    ``User.from_api_response``.
    """
    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        FieldAliases,
    )

    custom_caps = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities=dict(_X916_ALL_SUPPORTED_CAPABILITIES()),
        field_aliases={
            "schedule_relay": FieldAliases(
                read=("CustomScheduleField",), write=("CustomScheduleField",)
            ),
        },
        schema_shapes={},
    )

    list_payload = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {
                    "ID": "1",
                    "Name": "Alice",
                    "UserID": "1",
                    "CustomScheduleField": "1001-1",
                    "WebRelay": "0",
                    "LiftFloorNum": "0",
                },
            ],
        },
    }

    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get", payload=list_payload)
        async with AkuvoxDevice("192.168.1.100") as device:
            # Inject synthetic capabilities AFTER connect so the matrix
            # lookup runs as usual; the test exercises the wrapper's
            # extraction-from-self._capabilities path.
            device._capabilities = custom_caps  # noqa: SLF001
            users = await device.list_users()

    assert len(users) == 1
    assert users[0].schedule_relay == "1001-1"


async def test_list_users_threads_alias_order_through_wrapper() -> None:
    """T064a (conflict-resolution): wrapper honours alias declared order.

    With ``read=("Schedule", "ScheduleRelay")`` (order reversed from
    the default chain) and a payload carrying BOTH keys, the parser
    must return the ``"Schedule"`` value because it is first in the
    declared list. The default parser would return the
    ``"ScheduleRelay"`` value (default chain first-match), so this
    test fails unless the wrapper threads ``capabilities=`` all the
    way through to the parser.
    """
    from pylocal_akuvox.capabilities import (
        DeviceCapabilities,
        FieldAliases,
    )

    custom_caps = DeviceCapabilities(
        device_class="X916",
        firmware_version="916.30.10.114",
        capabilities=dict(_X916_ALL_SUPPORTED_CAPABILITIES()),
        field_aliases={
            "schedule_relay": FieldAliases(
                read=("Schedule", "ScheduleRelay"), write=("ScheduleRelay",)
            ),
        },
        schema_shapes={},
    )

    list_payload = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {
                    "ID": "1",
                    "Name": "Alice",
                    "UserID": "1",
                    "ScheduleRelay": "wrong_value",
                    "Schedule": "right_value",
                    "WebRelay": "0",
                    "LiftFloorNum": "0",
                },
            ],
        },
    }

    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/user/get", payload=list_payload)
        async with AkuvoxDevice("192.168.1.100") as device:
            device._capabilities = custom_caps  # noqa: SLF001
            users = await device.list_users()

    assert len(users) == 1
    assert users[0].schedule_relay == "right_value"


def _X916_ALL_SUPPORTED_CAPABILITIES() -> dict[Capability, CapabilityStatus]:
    """Build the ``capabilities`` mapping for a synthetic X916-like profile.

    Pulls from the production matrix entry so the synthetic profile
    used by the read-path plumbing tests has the same capability gates
    as ``register_default_info``'s X916 fixture — only the
    ``field_aliases`` / ``schema_shapes`` differ.
    """
    from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX

    for _pattern, caps in CAPABILITY_MATRIX:
        if caps.device_class == "X916":
            return dict(caps.capabilities)
    msg = "X916 baseline entry missing from capability matrix"
    raise AssertionError(msg)


# -- Copilot review round 1: defensive paths --


def test_user_from_api_response_empty_read_aliases_falls_back_to_default() -> None:
    """Empty ``aliases.read`` degrades to ``DEFAULT_USER_FIELD_ALIASES``.

    A capability record whose ``schedule_relay`` field carries an
    empty ``read`` tuple (incomplete matrix entry, malformed probe
    output, etc.) would otherwise make every parse raise
    ``AkuvoxParseError`` even when the payload carries a legacy key.
    The parser must fall back to the default chain so incomplete
    capability data degrades gracefully instead of bricking the read
    path (Copilot review round 1, ``models/users.py``).
    """
    from pylocal_akuvox.capabilities import DeviceCapabilities, FieldAliases
    from pylocal_akuvox.models import User

    caps = DeviceCapabilities(
        device_class="Synth",
        firmware_version="0.0.0",
        capabilities={},
        field_aliases={
            "schedule_relay": FieldAliases(read=(), write=("ScheduleRelay",))
        },
        schema_shapes={},
    )
    data = {
        "Name": "Alice",
        "UserID": "1",
        # Legacy default read key — must still be picked up under the
        # default fallback chain because ``aliases.read`` was empty.
        "ScheduleRelay": "1001-1",
    }
    user = User.from_api_response(data, capabilities=caps)
    assert user.schedule_relay == "1001-1"


async def test_add_user_service_function_empty_write_aliases_raises() -> None:
    """``add_user`` raises ``AkuvoxValidationError`` on empty ``write``.

    An empty ``write`` list would silently drop the schedule key from
    the ``add`` payload, producing a request the device will reject
    with an opaque error. Catching this at the service boundary
    surfaces the misconfiguration with a clear message (Copilot
    review round 1, ``users.add_user``).
    """
    from pylocal_akuvox import users as users_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import FieldAliases

    bad_aliases = FieldAliases(read=("ScheduleRelay",), write=())

    with aioresponses() as m:
        # ``add_user`` should raise before ever issuing the POST,
        # so the mock URL existence is not required — register it
        # defensively so a regression that *does* hit the wire
        # produces a more readable test failure than ConnectionError.
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            with pytest.raises(
                AkuvoxValidationError, match="field_aliases.write is empty"
            ):
                await users_svc.add_user(
                    http,
                    name="Alice",
                    user_id="2001",
                    schedule_relay="1001-1",
                    lift_floor_num="0",
                    field_aliases=bad_aliases,
                )


async def test_modify_user_strips_stale_read_only_alias_keys() -> None:
    """``modify_user`` strips read-only alias keys returned by the device.

    Scenario mirrors X915S current firmware (issue #118): the
    ``user/get`` response includes the bare ``Schedule`` read alias.
    The default write list is ``("ScheduleRelay", "Schedule-Relay")``,
    so without the read-alias-strip the merged ``set`` payload would
    echo ``Schedule`` back alongside the freshly-written write keys —
    defeating the "omit schedule keys when unset" contract and
    risking a stale value on subsequent reads. Verifies that ``set``
    no longer carries the ``Schedule`` key regardless of whether
    ``schedule_relay`` is supplied or omitted (Copilot review round
    1, ``users.modify_user``).

    Case A: schedule_relay supplied -> set re-writes write aliases
    and strips the stale read-only alias.
    Case B: schedule_relay omitted -> all aliases (incl. read-only) stripped.
    """
    import aiohttp

    from pylocal_akuvox import users as users_svc
    from pylocal_akuvox._http import AkuvoxHttpClient

    # Device returns ``Schedule`` in the get payload — stale read alias.
    get_with_stale_schedule = {
        "retcode": 0,
        "action": "get",
        "message": "OK",
        "data": {
            "num": 1,
            "item": [
                {
                    "ID": "1",
                    "Name": "Alice",
                    "UserID": "2001",
                    "WebRelay": "0",
                    "ScheduleRelay": "1001-1",
                    "Schedule-Relay": "1001-1",
                    "Schedule": "STALE",  # the read-only alias
                    "LiftFloorNum": "0",
                    "PrivatePIN": "",
                    "CardCode": "",
                },
            ],
        },
    }

    # Case A: schedule_relay supplied -> set re-writes write aliases
    # and strips the stale read-only alias.
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=get_with_stale_schedule)
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await users_svc.modify_user(
                http,
                id="1",
                schedule_relay="2002-2",
            )

        # Find the POST request and inspect its payload.
        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))
        post_calls = m.requests.get(url_key, [])
        assert len(post_calls) == 1
        sent = post_calls[0].kwargs.get("json")
        sent_item = sent["data"]["item"][0]
        assert "Schedule" not in sent_item
        assert sent_item["ScheduleRelay"] == "2002-2"
        assert sent_item["Schedule-Relay"] == "2002-2"

    # Case B: schedule_relay omitted -> all aliases (incl. read-only) stripped.
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=get_with_stale_schedule)
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            await users_svc.modify_user(http, id="1", name="Renamed")

        post_calls = m.requests.get(url_key, [])
        assert len(post_calls) == 1
        sent = post_calls[0].kwargs.get("json")
        sent_item = sent["data"]["item"][0]
        assert "Schedule" not in sent_item
        assert "ScheduleRelay" not in sent_item
        assert "Schedule-Relay" not in sent_item
        assert sent_item["Name"] == "Renamed"


async def test_modify_user_service_function_empty_write_aliases_raises() -> None:
    """``modify_user`` raises on empty ``write`` when schedule supplied.

    Pure no-op merges (``schedule_relay`` left as ``None``) are still
    allowed even on an empty write list — only blocks the case where
    a schedule update is actually requested and would silently drop
    (Copilot review round 1, ``users.modify_user``).
    """
    from pylocal_akuvox import users as users_svc
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import FieldAliases

    bad_aliases = FieldAliases(read=("ScheduleRelay",), write=())

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(f"{BASE_URL}/api/user/set", payload=_SET_OK_RESPONSE)
        async with AkuvoxHttpClient("192.168.1.100") as http:
            with pytest.raises(
                AkuvoxValidationError, match="field_aliases.write is empty"
            ):
                await users_svc.modify_user(
                    http,
                    id="1",
                    schedule_relay="2002-2",
                    field_aliases=bad_aliases,
                )
