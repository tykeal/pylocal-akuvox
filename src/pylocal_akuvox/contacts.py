# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contact management operations for Akuvox devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import Contact

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient


def _mutation_body(action: str, item: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap a contact payload in the device mutation envelope.

    The ``target`` field is required by E18 firmware to route the
    request to the correct CGI handler.
    """
    return {
        "target": "contact",
        "action": action,
        "data": {"item": item},
    }


async def list_contacts(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
) -> list[Contact]:
    """List contacts from the device, optionally paginated."""
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page

    data = await http.get("/api/contact/get", params=params or None)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [Contact.from_api_response(item) for item in items if isinstance(item, dict)]


async def add_contact(
    http: AkuvoxHttpClient,
    *,
    name: str,
    phone: str | None = None,
    group: str | None = None,
) -> None:
    """Add a contact to the device address book."""
    if not name:
        msg = "name is required for add_contact"
        raise AkuvoxValidationError(msg)

    payload: dict[str, Any] = {"Name": name}
    if phone is not None:
        payload["Phone"] = phone
    if group is not None:
        payload["Group"] = group

    await http.post("/api/contact/set", data=_mutation_body("add", [payload]))


async def _get_contact_by_id(
    http: AkuvoxHttpClient,
    contact_id: str,
) -> dict[str, Any]:
    """Fetch a single contact's raw data by internal ID.

    Iterates through all pages (device returns 10 per page).
    """
    from pylocal_akuvox.exceptions import AkuvoxDeviceError

    page = 1
    while True:
        data = await http.get("/api/contact/get", params={"page": page})
        items = data.get("item", [])
        if not isinstance(items, list) or len(items) == 0:
            break
        for item in items:
            if isinstance(item, dict) and item.get("ID") == contact_id:
                return item
        page += 1
    msg = f"Contact ID {contact_id} not found"
    raise AkuvoxDeviceError(msg)


async def modify_contact(
    http: AkuvoxHttpClient,
    *,
    id: str,
    name: str | None = None,
    phone: str | None = None,
    group: str | None = None,
) -> None:
    """Modify an existing contact on the device.

    The device requires a full contact record for set operations,
    so this fetches the current record and merges changes.
    """
    if name is None and phone is None and group is None:
        msg = "at least one of name, phone, or group is required for modify_contact"
        raise AkuvoxValidationError(msg)
    current = await _get_contact_by_id(http, id)
    if name is not None:
        current["Name"] = name
    if phone is not None:
        current["Phone"] = phone
    if group is not None:
        current["Group"] = group

    await http.post("/api/contact/set", data=_mutation_body("set", [current]))


async def delete_contact(
    http: AkuvoxHttpClient,
    *,
    id: str | list[str],
) -> None:
    """Delete one or more contacts from the device."""
    if isinstance(id, str):
        ids = [id]
    else:
        ids = id
    items = [{"ID": cid} for cid in ids]
    await http.post("/api/contact/set", data=_mutation_body("del", items))
