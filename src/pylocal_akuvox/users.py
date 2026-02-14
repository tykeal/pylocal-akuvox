# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""User management operations for Akuvox devices."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import User

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient

_PIN_PATTERN = re.compile(r"^[0-9]{4,8}$")
_SCHEDULE_RELAY_PATTERN = re.compile(r"^([0-9]+-[0-9]+;)+$")


def validate_pin(pin: str | None) -> None:
    """Validate PIN is 4-8 digits only.

    None and empty string are allowed (optional field).
    """
    if pin is None or pin == "":
        return
    if not _PIN_PATTERN.match(pin):
        msg = "PIN must be 4-8 digits only"
        raise AkuvoxValidationError(msg)


def validate_schedule_relay(schedule_relay: str | None) -> None:
    """Validate schedule_relay matches <int>-<int>; pattern.

    None and empty string are allowed.
    """
    if schedule_relay is None or schedule_relay == "":
        return
    if not _SCHEDULE_RELAY_PATTERN.match(schedule_relay):
        msg = "schedule_relay must match '<ScheduleID>-<RelayID>;' pattern"
        raise AkuvoxValidationError(msg)


async def add_user(
    http: AkuvoxHttpClient,
    *,
    name: str,
    user_id: str,
    web_relay: str,
    schedule_relay: str,
    lift_floor_num: str,
    private_pin: str | None = None,
    card_code: str | None = None,
) -> None:
    """Add a local user to the device."""
    if not name:
        msg = "name is required for add_user"
        raise AkuvoxValidationError(msg)
    if not user_id:
        msg = "user_id is required for add_user"
        raise AkuvoxValidationError(msg)
    validate_pin(private_pin)
    if not schedule_relay:
        msg = "schedule_relay is required for add_user"
        raise AkuvoxValidationError(msg)
    validate_schedule_relay(schedule_relay)

    payload: dict[str, Any] = {
        "Name": name,
        "UserID": user_id,
        "WebRelay": web_relay,
        "ScheduleRelay": schedule_relay,
        "LiftFloorNum": lift_floor_num,
    }
    if private_pin:
        payload["PrivatePIN"] = private_pin
    if card_code:
        payload["CardCode"] = card_code

    await http.post("/api/user/add", data=payload)


async def list_users(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
) -> list[User]:
    """List users from the device, optionally paginated."""
    payload: dict[str, Any] = {}
    if page is not None:
        payload["page"] = page

    data = await http.post("/api/user/get", data=payload)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [User.from_api_response(item) for item in items if isinstance(item, dict)]


async def modify_user(
    http: AkuvoxHttpClient,
    *,
    id: str,
    name: str | None = None,
    user_id: str | None = None,
    private_pin: str | None = None,
    card_code: str | None = None,
    web_relay: str | None = None,
    schedule_relay: str | None = None,
    lift_floor_num: str | None = None,
) -> None:
    """Modify an existing user on the device."""
    # Normalize empty strings to None (omit from payload)
    private_pin = private_pin or None
    schedule_relay = schedule_relay or None

    validate_pin(private_pin)
    validate_schedule_relay(schedule_relay)

    payload: dict[str, Any] = {"ID": id}
    if name is not None:
        payload["Name"] = name
    if user_id is not None:
        payload["UserID"] = user_id
    if private_pin is not None:
        payload["PrivatePIN"] = private_pin
    if card_code is not None:
        payload["CardCode"] = card_code
    if web_relay is not None:
        payload["WebRelay"] = web_relay
    if schedule_relay is not None:
        payload["ScheduleRelay"] = schedule_relay
    if lift_floor_num is not None:
        payload["LiftFloorNum"] = lift_floor_num

    await http.post("/api/user/set", data=payload)


async def delete_user(
    http: AkuvoxHttpClient,
    *,
    id: str,
) -> None:
    """Delete a user from the device."""
    await http.post("/api/user/del", data={"ID": id})
