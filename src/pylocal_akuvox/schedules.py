# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Schedule management operations for Akuvox devices."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import AccessSchedule

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient

_VALID_TYPES = {"0", "1", "2"}
_TIME_PATTERN = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
_DATE_PATTERN = re.compile(r"^[0-9]{8}$")
_WEEK_PATTERN = re.compile(r"^[0-6]+$")
_DAILY_PATTERN = re.compile(
    r"^([01][0-9]|2[0-3]):[0-5][0-9]-([01][0-9]|2[0-3]):[0-5][0-9]$"
)


def _mutation_body(action: str, item: dict[str, Any]) -> dict[str, Any]:
    """Wrap a schedule payload in the device mutation envelope."""
    return {"action": action, "data": {"item": [item]}}


def validate_schedule_type(schedule_type: str) -> None:
    """Validate schedule type is 0, 1, or 2."""
    if schedule_type not in _VALID_TYPES:
        msg = "schedule_type must be '0', '1', or '2'"
        raise AkuvoxValidationError(msg)


def validate_time(value: str | None, field: str) -> None:
    """Validate time is HH:MM format."""
    if value is None or value == "":
        return
    if not _TIME_PATTERN.match(value):
        msg = f"{field} must be HH:MM format"
        raise AkuvoxValidationError(msg)


def validate_date(value: str | None, field: str) -> None:
    """Validate date is YYYYMMDD format."""
    if value is None or value == "":
        return
    if not _DATE_PATTERN.match(value):
        msg = f"{field} must be YYYYMMDD format"
        raise AkuvoxValidationError(msg)


def validate_week(week: str | None) -> None:
    """Validate week codes are digits 0-6."""
    if week is None or week == "":
        return
    if not _WEEK_PATTERN.match(week):
        msg = "week must contain only digits 0-6"
        raise AkuvoxValidationError(msg)


def validate_daily(daily: str | None) -> None:
    """Validate daily is HH:MM-HH:MM format."""
    if daily is None or daily == "":
        return
    if not _DAILY_PATTERN.match(daily):
        msg = "daily must be HH:MM-HH:MM format"
        raise AkuvoxValidationError(msg)


async def add_schedule(
    http: AkuvoxHttpClient,
    *,
    schedule_type: str,
    name: str | None = None,
    week: str | None = None,
    daily: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
) -> None:
    """Add an access schedule to the device."""
    validate_schedule_type(schedule_type)
    validate_week(week)
    validate_daily(daily)
    validate_date(date_start, "date_start")
    validate_date(date_end, "date_end")
    validate_time(time_start, "time_start")
    validate_time(time_end, "time_end")

    payload: dict[str, Any] = {"Type": schedule_type}
    if name is not None:
        payload["Name"] = name
    if week is not None:
        payload["Week"] = week
    if daily is not None:
        payload["Daily"] = daily
    if date_start is not None:
        payload["DateStart"] = date_start
    if date_end is not None:
        payload["DateEnd"] = date_end
    if time_start is not None:
        payload["TimeStart"] = time_start
    if time_end is not None:
        payload["TimeEnd"] = time_end

    await http.post("/api/schedule/set", data=_mutation_body("add", payload))


async def list_schedules(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
) -> list[AccessSchedule]:
    """List schedules from the device, optionally paginated."""
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page

    data = await http.get("/api/schedule/get", params=params or None)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [
        AccessSchedule.from_api_response(item)
        for item in items
        if isinstance(item, dict)
    ]


async def _get_schedule_by_id(
    http: AkuvoxHttpClient, internal_id: str
) -> dict[str, Any]:
    """Fetch a single schedule's raw data by internal ID.

    Iterates through all pages until the schedule is found.
    """
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    page = 1
    while True:
        data = await http.get("/api/schedule/get", params={"page": page})
        items = data.get("item", [])
        if not isinstance(items, list) or len(items) == 0:
            break
        for item in items:
            if isinstance(item, dict) and item.get("ID") == internal_id:
                return item
        page += 1
    msg = f"Schedule ID {internal_id} not found"
    raise AkuvoxDeviceError(msg)


async def modify_schedule(
    http: AkuvoxHttpClient,
    *,
    id: str,
    name: str | None = None,
    schedule_type: str | None = None,
    week: str | None = None,
    daily: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
) -> None:
    """Modify an existing schedule on the device.

    Fetches the current record and merges changes, since the
    device requires a full record for set operations.
    """
    if schedule_type is not None:
        validate_schedule_type(schedule_type)
    validate_week(week)
    validate_daily(daily)
    validate_date(date_start, "date_start")
    validate_date(date_end, "date_end")
    validate_time(time_start, "time_start")
    validate_time(time_end, "time_end")

    current = await _get_schedule_by_id(http, id)
    if name is not None:
        current["Name"] = name
    if schedule_type is not None:
        current["Type"] = schedule_type
    if week is not None:
        current["Week"] = week
    if daily is not None:
        current["Daily"] = daily
    if date_start is not None:
        current["DateStart"] = date_start
    if date_end is not None:
        current["DateEnd"] = date_end
    if time_start is not None:
        current["TimeStart"] = time_start
    if time_end is not None:
        current["TimeEnd"] = time_end

    await http.post("/api/schedule/set", data=_mutation_body("set", current))


async def delete_schedule(
    http: AkuvoxHttpClient,
    *,
    id: str,
) -> None:
    """Delete a schedule from the device."""
    await http.post(
        "/api/schedule/set",
        data=_mutation_body("del", {"ID": id}),
    )
