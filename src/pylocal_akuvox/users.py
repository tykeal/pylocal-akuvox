# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""User management operations for Akuvox devices."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import User

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases
    from pylocal_akuvox._http import AkuvoxHttpClient

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
    ``field_aliases.write``, defaulting to the canonical
    ``schedule_relay`` fallback chain when ``field_aliases`` is
    ``None`` or omitted::

        FieldAliases(
            read=("ScheduleRelay", "Schedule-Relay", "Schedule"),
            write=("ScheduleRelay", "Schedule-Relay"),
        )

    The default write list is ``("ScheduleRelay", "Schedule-Relay")``,
    byte-identical to the pre-refactor hardcoded dual-write — so direct
    callers that do not supply ``field_aliases`` see no observable
    change (FR-016).

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
    # Defensive: a capability record with an empty ``write`` tuple
    # would silently drop the schedule key entirely, producing a
    # malformed ``add`` payload the device will reject. Validate
    # eagerly so the caller gets a clear ``AkuvoxValidationError``
    # at the service boundary instead of an opaque device-side
    # rejection (Copilot review round 1).
    if not write_aliases:
        msg = (
            "field_aliases.write is empty; add_user cannot emit a "
            "schedule-relay key without at least one write alias"
        )
        raise AkuvoxValidationError(msg)

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
    falls through to the parser's canonical ``schedule_relay``
    fallback chain::

        FieldAliases(
            read=("ScheduleRelay", "Schedule-Relay", "Schedule"),
            write=("ScheduleRelay", "Schedule-Relay"),
        )

    preserving byte-identical behaviour for direct callers
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


def _resolve_alias_lists(
    field_aliases: FieldAliases | None,
) -> tuple[tuple[str, ...], tuple[str, ...], list[str]]:
    """Resolve write/read alias tuples plus their ordered union.

    Returns ``(write_aliases, read_aliases, all_aliases)`` derived
    from ``field_aliases`` when supplied, or from
    :data:`DEFAULT_USER_FIELD_ALIASES` when ``None``. ``all_aliases``
    is the read-first, write-second ordered union (deduplicated)
    used to strip stale alias keys from a fetched record.
    """
    write_aliases = (
        field_aliases.write
        if field_aliases is not None
        else DEFAULT_USER_FIELD_ALIASES.write
    )
    read_aliases = (
        field_aliases.read
        if field_aliases is not None
        else DEFAULT_USER_FIELD_ALIASES.read
    )
    # Mirror ``User.from_api_response``'s empty-``read`` fallback
    # (Copilot round 1 in ``models/users.py``; round 2 caught the
    # corresponding gap here): a capability record whose ``read``
    # tuple is empty would otherwise leave ``all_aliases`` without
    # the legacy ``Schedule`` key — and ``modify_user(...,
    # schedule_relay=None)`` would silently fail to strip the
    # stale read-only alias returned by X915S current FW. Fall
    # back to the default read chain so degenerate matrix data
    # still produces the documented "omit schedule keys when
    # unset" behaviour. ``write`` is intentionally NOT
    # back-filled — an empty ``write`` already triggers an
    # eager ``AkuvoxValidationError`` in ``modify_user`` whenever
    # ``schedule_relay`` is supplied, and a pure no-op merge
    # (``schedule_relay=None``) genuinely wants no writes.
    if not read_aliases:
        read_aliases = DEFAULT_USER_FIELD_ALIASES.read
    all_aliases = list(read_aliases) + [
        alias for alias in write_aliases if alias not in read_aliases
    ]
    return write_aliases, read_aliases, all_aliases


def _apply_schedule_to_record(
    current: dict[str, Any],
    schedule_relay: str | None,
    *,
    write_aliases: tuple[str, ...],
    all_aliases: list[str],
) -> None:
    """Mutate ``current`` to set or strip schedule-relay aliases.

    When ``schedule_relay`` is supplied, every known alias is first
    popped (covers stale read-only aliases such as ``Schedule`` on
    X915S current FW; see Copilot review round 1 — issue #118) and
    then the value is written under each name in ``write_aliases``.
    When ``schedule_relay`` is ``None``, every known alias is
    stripped.
    """
    if schedule_relay is not None:
        for alias in all_aliases:
            current.pop(alias, None)
        for alias in write_aliases:
            current[alias] = schedule_relay
    else:
        for alias in all_aliases:
            current.pop(alias, None)


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
    ``field_aliases.write``, defaulting to the canonical
    ``schedule_relay`` fallback chain::

        FieldAliases(
            read=("ScheduleRelay", "Schedule-Relay", "Schedule"),
            write=("ScheduleRelay", "Schedule-Relay"),
        )

    which mirrors today's hardcoded
    ``("ScheduleRelay", "Schedule-Relay")`` dual-write. On both
    the set and the unset paths, every name in the **read+write
    union** is first stripped from the merged record (so a stale
    read-only alias such as ``Schedule`` returned by X915S current
    FW cannot survive the round-trip and re-emerge on the next
    read); on the set path, the write aliases are then re-populated
    with the new value. The unset path therefore removes every
    known alias (read and write) — not just the write list — to
    avoid conflicting values across firmwares.

    An empty ``write`` tuple combined with a supplied
    ``schedule_relay`` raises ``AkuvoxValidationError`` (the loop
    would otherwise silently drop the schedule key). An empty
    ``read`` tuple falls back to
    :data:`DEFAULT_USER_FIELD_ALIASES.read` for the strip union so
    degenerate matrix data still strips the legacy ``Schedule``
    key.

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

    write_aliases, _read_aliases, all_aliases = _resolve_alias_lists(field_aliases)
    # Defensive: same rationale as ``add_user`` — an empty write
    # list would silently drop the schedule key when ``schedule_relay``
    # is supplied, producing a malformed ``set`` payload (Copilot
    # review round 1). Only enforced when a schedule update is
    # actually requested; pure no-op merges with ``schedule_relay``
    # left as ``None`` are still allowed even on an empty write list.
    if schedule_relay is not None and not write_aliases:
        msg = (
            "field_aliases.write is empty; modify_user cannot emit a "
            "schedule-relay key without at least one write alias"
        )
        raise AkuvoxValidationError(msg)

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
    _apply_schedule_to_record(
        current,
        schedule_relay,
        write_aliases=write_aliases,
        all_aliases=all_aliases,
    )
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
