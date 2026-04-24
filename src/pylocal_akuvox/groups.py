# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Group management operations for Akuvox devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import Group

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient


def _mutation_body(action: str, item: dict[str, Any]) -> dict[str, Any]:
    """Wrap a group payload in the device mutation envelope."""
    return {
        "target": "group",
        "action": action,
        "data": {"item": [item]},
    }


async def list_groups(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
) -> list[Group]:
    """List groups from the device, optionally paginated."""
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page

    data = await http.get(
        "/api/group/get",
        params=params or None,
    )
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [Group.from_api_response(item) for item in items if isinstance(item, dict)]


async def add_group(
    http: AkuvoxHttpClient,
    *,
    name: str,
) -> None:
    """Add a group to the device."""
    if not name:
        msg = "name is required for add_group"
        raise AkuvoxValidationError(msg)

    await http.post(
        "/api/group/add",
        data=_mutation_body("add", {"Name": name}),
    )


async def modify_group(
    http: AkuvoxHttpClient,
    *,
    id: str,
    name: str,
) -> None:
    """Modify an existing group on the device."""
    if not name:
        msg = "name is required for modify_group"
        raise AkuvoxValidationError(msg)

    payload = {"ID": id, "Name": name}
    await http.post(
        "/api/group/set",
        data=_mutation_body("set", payload),
    )


async def delete_group(
    http: AkuvoxHttpClient,
    *,
    id: str,
) -> None:
    """Delete a group from the device."""
    await http.post(
        "/api/group/del",
        data=_mutation_body("del", {"ID": id}),
    )
