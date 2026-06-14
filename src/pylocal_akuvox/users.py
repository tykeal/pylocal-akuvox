# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""User management operations for Akuvox devices."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pylocal_akuvox.capabilities import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import User

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import DeviceCapabilities, FieldAliases

_PIN_PATTERN = re.compile(r"^[0-9]{4,8}$")
_SCHEDULE_RELAY_PATTERN = re.compile(r"^[0-9]+-[0-9]+(,[0-9]+-[0-9]+)*,?$")


def _mutation_body(action: str, item: dict[str, Any]) -> dict[str, Any]:
    """Wrap a user payload in the device mutation envelope.

    The ``target`` field is required by E18 firmware to route the
    request to the correct CGI handler.
    """
    return {"target": "user", "action": action, "data": {"item": [item]}}


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
    """Validate schedule_relay matches comma-separated pairs.

    Expected format: ``<ScheduleID>-<RelayID>`` with multiple
    entries separated by commas.  A single trailing comma is
    tolerated.  None and empty string are allowed.
    """
    if schedule_relay is None or schedule_relay == "":
        return
    if not _SCHEDULE_RELAY_PATTERN.match(schedule_relay):
        msg = (
            "schedule_relay must be comma-separated "
            "'<ScheduleID>-<RelayID>' pairs "
            "(e.g. '1001-1,1002-2'), optional trailing comma"
        )
        raise AkuvoxValidationError(msg)


async def add_user(
    http: AkuvoxHttpClient,
    *,
    name: str,
    user_id: str,
    web_relay: str | None = None,
    schedule_relay: str,
    lift_floor_num: str,
    private_pin: str | None = None,
    card_code: str | None = None,
    field_aliases: FieldAliases | None = None,
) -> None:
    """Add a local user to the device.

    The primary relay schedule is emitted once per name in
    ``field_aliases.write`` (defaulting to
    :data:`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES`
    when ``field_aliases`` is ``None`` or omitted). The default write
    list is ``("ScheduleRelay", "Schedule-Relay")``, byte-identical
    to the pre-refactor hardcoded dual-write — so direct callers that
    do not supply ``field_aliases`` see no observable change (FR-016).

    Service-module functions stay capability-unaware: this function
    does **not** consult any global capability matrix or
    ``self._capabilities`` (it has no ``self``). The
    :meth:`AkuvoxDevice.add_user` wrapper performs the capability
    gate and extracts the appropriate ``FieldAliases`` from
    ``self._capabilities`` before delegating here.
    """
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

    write_aliases = (
        field_aliases.write
        if field_aliases is not None
        else DEFAULT_USER_FIELD_ALIASES.write
    )

    payload: dict[str, Any] = {
        "Name": name,
        "UserID": user_id,
    }
    # Schedule fields preserved in their pre-refactor position so the
    # serialized payload key order is unchanged when ``field_aliases``
    # is omitted (FR-016 byte-identity for default callers).
    for alias in write_aliases:
        payload[alias] = schedule_relay
    payload["LiftFloorNum"] = lift_floor_num
    if web_relay is not None:
        payload["WebRelay"] = web_relay
    if private_pin:
        payload["PrivatePIN"] = private_pin
    if card_code:
        payload["CardCode"] = card_code

    await http.post("/api/user/set", data=_mutation_body("add", payload))


async def list_users(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
    capabilities: DeviceCapabilities | None = None,
) -> list[User]:
    """List users from the device, optionally paginated.

    ``capabilities`` is threaded to each
    :meth:`User.from_api_response` call so the parser can consult
    per-device-class field aliases (FR-014). The default ``None``
    falls through to the parser's
    :data:`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES`
    chain, preserving byte-identical behaviour for direct callers
    (FR-016 / SC-008).
    """
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page

    data = await http.get("/api/user/get", params=params or None)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [
        User.from_api_response(item, capabilities=capabilities)
        for item in items
        if isinstance(item, dict)
    ]


async def _get_user_by_id(http: AkuvoxHttpClient, internal_id: str) -> dict[str, Any]:
    """Fetch a single user's raw data by internal ID.

    Iterates through all pages (device returns 10 per page).
    """
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    page = 1
    while True:
        data = await http.get("/api/user/get", params={"page": page})
        items = data.get("item", [])
        if not isinstance(items, list) or len(items) == 0:
            break
        for item in items:
            if isinstance(item, dict) and item.get("ID") == internal_id:
                return item
        page += 1
    msg = f"User ID {internal_id} not found"
    raise AkuvoxDeviceError(msg)


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
    field_aliases: FieldAliases | None = None,
) -> None:
    """Modify an existing user on the device.

    The device generally requires a full user record for set
    operations, so this fetches the current record and merges
    changes. Primary schedule fields are the compatibility exception:
    when supplied, the schedule is emitted under each name in
    ``field_aliases.write`` (defaulting to
    :data:`pylocal_akuvox.capabilities.DEFAULT_USER_FIELD_ALIASES`,
    which mirrors today's hardcoded
    ``("ScheduleRelay", "Schedule-Relay")`` dual-write). When unset,
    every name in the same write list is removed from the merged
    record to avoid conflicting values across firmwares.

    Service-module functions stay capability-unaware: this function
    does **not** consult any global capability matrix or
    ``self._capabilities`` (it has no ``self``). The
    :meth:`AkuvoxDevice.modify_user` wrapper performs the capability
    gate and extracts the appropriate ``FieldAliases`` from
    ``self._capabilities`` before delegating here.
    """
    # Normalize empty strings to None for optional update handling.
    private_pin = private_pin or None
    schedule_relay = schedule_relay or None

    validate_pin(private_pin)
    validate_schedule_relay(schedule_relay)

    write_aliases = (
        field_aliases.write
        if field_aliases is not None
        else DEFAULT_USER_FIELD_ALIASES.write
    )

    current = await _get_user_by_id(http, id)
    if name is not None:
        current["Name"] = name
    if user_id is not None:
        current["UserID"] = user_id
    if private_pin is not None:
        current["PrivatePIN"] = private_pin
    if card_code is not None:
        current["CardCode"] = card_code
    if web_relay is not None:
        current["WebRelay"] = web_relay
    if schedule_relay is not None:
        for alias in write_aliases:
            current[alias] = schedule_relay
    else:
        for alias in write_aliases:
            current.pop(alias, None)
    if lift_floor_num is not None:
        current["LiftFloorNum"] = lift_floor_num

    await http.post("/api/user/set", data=_mutation_body("set", current))


async def delete_user(
    http: AkuvoxHttpClient,
    *,
    id: str,
) -> None:
    """Delete a user from the device."""
    await http.post("/api/user/set", data=_mutation_body("del", {"ID": id}))
