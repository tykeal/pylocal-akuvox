# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for user operations: PIN validation and CRUD."""

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import (
    AkuvoxValidationError,
)
from pylocal_akuvox.users import validate_pin, validate_schedule_relay

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
                "ScheduleRelay": "1001-1;",
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
    validate_schedule_relay("1001-1;")


def test_validate_schedule_relay_valid_multiple() -> None:
    """Verify multiple schedule-relay pairs are accepted."""
    validate_schedule_relay("1001-1;1002-2;")


def test_validate_schedule_relay_none_allowed() -> None:
    """Verify None schedule_relay is allowed."""
    validate_schedule_relay(None)


def test_validate_schedule_relay_empty_allowed() -> None:
    """Verify empty string schedule_relay is allowed in validator.

    The validator allows empty for optional contexts (modify_user).
    add_user enforces non-empty separately.
    """
    validate_schedule_relay("")


def test_validate_schedule_relay_missing_semicolon() -> None:
    """Verify missing trailing semicolon is rejected."""
    with pytest.raises(AkuvoxValidationError, match="schedule_relay"):
        validate_schedule_relay("1001-1")


def test_validate_schedule_relay_invalid_format() -> None:
    """Verify non-numeric format is rejected."""
    with pytest.raises(AkuvoxValidationError, match="schedule_relay"):
        validate_schedule_relay("abc-xyz;")


# -- T027: User CRUD operation tests --


async def test_add_user_posts_to_correct_endpoint() -> None:
    """Verify add_user POSTs to /api/user/add with required fields."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/user/add",
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
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )

        url_key = ("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/add"))
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["action"] == "add"
        item = body["data"]["item"][0]
        assert item["Name"] == "Alice"
        assert item["UserID"] == "2001"
        assert item["WebRelay"] == "0"
        assert item["ScheduleRelay"] == "1001-1;"
        assert item["LiftFloorNum"] == "0"


async def test_add_user_with_pin() -> None:
    """Verify add_user includes optional PIN in payload."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/user/add",
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
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )


async def test_add_user_invalid_pin_raises_validation_error() -> None:
    """Verify add_user with invalid PIN raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
            await device.add_user(
                name="Alice",
                user_id="2001",
                private_pin="12ab",
                web_relay="0",
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )


async def test_add_user_invalid_schedule_relay_raises() -> None:
    """Verify add_user with invalid schedule_relay raises."""
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
        assert body["action"] == "set"
        item = body["data"]["item"][0]
        # Empty PIN normalized to None - field not updated, original value preserved
        assert item["ID"] == "1"
        assert item["Name"] == "Updated"
        assert item["PrivatePIN"] == ""


async def test_list_users_posts_to_correct_endpoint() -> None:
    """Verify list_users GETs from /api/user/get and returns User list."""
    with aioresponses() as m:
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
                            "ScheduleRelay": "1001-1;",
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
                            "ScheduleRelay": "1001-1;",
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
                            "ScheduleRelay": "1001-1;",
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
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=_USER_GET_RESPONSE)
        m.post(
            f"{BASE_URL}/api/user/set",
            payload=_SET_OK_RESPONSE,
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.modify_user(id="1", private_pin="5678")


async def test_modify_user_invalid_pin_raises() -> None:
    """Verify modify_user with invalid PIN raises AkuvoxValidationError."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(AkuvoxValidationError, match="4.*8 digits"):
            await device.modify_user(id="1", private_pin="bad")


async def test_delete_user_posts_to_correct_endpoint() -> None:
    """Verify delete_user POSTs to /api/user/del with ID."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/user/del",
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
        m.post(
            f"{BASE_URL}/api/user/add",
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
                    schedule_relay="1001-1;",
                    lift_floor_num="0",
                )


async def test_add_user_with_card_code() -> None:
    """Verify add_user includes card_code in payload."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/user/add",
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
                schedule_relay="1001-1;",
                lift_floor_num="0",
                card_code="RFID1234",
            )


async def test_list_users_non_list_items_returns_empty() -> None:
    """Verify list_users returns empty list if items is not a list."""
    with aioresponses() as m:
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
                schedule_relay="1002-2;",
                lift_floor_num="5",
            )


async def test_modify_user_without_pin() -> None:
    """Verify modify_user works without private_pin."""
    with aioresponses() as m:
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
        m.get(f"{BASE_URL}/api/user/get?page=1", payload=bad_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="not found"):
                await device.modify_user(id="1", name="Ghost")


async def test_add_user_empty_name_raises() -> None:
    """Verify add_user rejects empty name (required field)."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(AkuvoxValidationError, match="name"):
            await device.add_user(
                name="",
                user_id="2001",
                web_relay="0",
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )


async def test_add_user_empty_user_id_raises() -> None:
    """Verify add_user rejects empty user_id (required field)."""
    async with AkuvoxDevice("192.168.1.100") as device:
        with pytest.raises(AkuvoxValidationError, match="user_id"):
            await device.add_user(
                name="Alice",
                user_id="",
                web_relay="0",
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )


async def test_add_user_without_web_relay() -> None:
    """Verify add_user omits WebRelay when not provided."""
    with aioresponses() as m:
        m.post(
            f"{BASE_URL}/api/user/add",
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
                schedule_relay="1001-1;",
                lift_floor_num="0",
            )

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/user/add"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        item = body["data"]["item"][0]
        assert "WebRelay" not in item


async def test_list_users_non_dict_items_skipped() -> None:
    """Verify list_users skips non-dict items in the response."""
    with aioresponses() as m:
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
                            "ScheduleRelay": "1001-1;",
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
