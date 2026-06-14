# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contact management operations for Akuvox devices.

.. note::

   This module uses the ``/api/contact/*`` HTTP endpoints which manage a
   **separate data store** from the Akuvox device web UI.  Contacts
   created via these endpoints will **not** appear in the web UI, and
   vice-versa.  The web UI uses session-authenticated ``/web/`` endpoints
   that are not supported by this library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox.capabilities import SchemaShape
from pylocal_akuvox.exceptions import AkuvoxValidationError
from pylocal_akuvox.models import Contact

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.capabilities import DeviceCapabilities


_APARTMENT_BOOK_WRITE_DEFERRAL_MSG = (
    "apartment-book contact writes are not yet supported; "
    "the current public add_contact/modify_contact signature has no "
    "source for APTName/APTNum/Building/Landline and no hardware-bench "
    "write evidence exists for the apartment-book payload shape"
)


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
    capabilities: DeviceCapabilities | None = None,
) -> list[Contact]:
    """List contacts from the device, optionally paginated.

    ``capabilities`` is threaded to each
    :meth:`Contact.from_api_response` call so the parser can choose
    between door-phone and apartment-book parse paths via
    ``capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)``
    (FR-015). The default ``None`` falls through to the door-phone
    branch, preserving byte-identical behaviour for direct callers
    (FR-016 / SC-008).
    """
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page

    data = await http.get("/api/contact/get", params=params or None)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [
        Contact.from_api_response(item, capabilities=capabilities)
        for item in items
        if isinstance(item, dict)
    ]


async def add_contact(
    http: AkuvoxHttpClient,
    *,
    name: str,
    phone: str | None = None,
    group: str | None = None,
    schema_shape: SchemaShape | None = None,
) -> None:
    """Add a contact to the device address book.

    ``schema_shape`` defaults to :attr:`SchemaShape.DOOR_PHONE` when
    ``None`` (preserves FR-016 byte-identity for direct callers). The
    :attr:`SchemaShape.APARTMENT_BOOK` branch raises
    :class:`NotImplementedError` with a deferral message — the
    current public signature has no source for the required
    ``APTName``/``APTNum``/``Building``/``Landline`` fields and no
    hardware-bench write evidence exists for that payload shape (see
    issue #121 / Phase 3 §"Apartment-book contact writes" deferral).

    Service-module functions stay capability-unaware: this function
    does **not** consult any global capability matrix or
    ``self._capabilities``. The :meth:`AkuvoxDevice.add_contact`
    wrapper performs the capability gate and extracts the schema
    shape from ``self._capabilities`` before delegating here.
    """
    if not name:
        msg = "name is required for add_contact"
        raise AkuvoxValidationError(msg)

    shape = schema_shape if schema_shape is not None else SchemaShape.DOOR_PHONE
    if shape is SchemaShape.APARTMENT_BOOK:
        raise NotImplementedError(_APARTMENT_BOOK_WRITE_DEFERRAL_MSG)

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
    schema_shape: SchemaShape | None = None,
) -> None:
    """Modify an existing contact on the device.

    The device requires a full contact record for set operations,
    so this fetches the current record and merges changes.

    ``schema_shape`` defaults to :attr:`SchemaShape.DOOR_PHONE` when
    ``None`` (preserves FR-016 byte-identity for direct callers). The
    :attr:`SchemaShape.APARTMENT_BOOK` branch raises
    :class:`NotImplementedError` with a deferral message — see
    :func:`add_contact` for the rationale.

    Service-module functions stay capability-unaware: see
    :func:`add_contact` for the wrapper-extraction contract.
    """
    if name is None and phone is None and group is None:
        msg = "at least one of name, phone, or group is required for modify_contact"
        raise AkuvoxValidationError(msg)

    shape = schema_shape if schema_shape is not None else SchemaShape.DOOR_PHONE
    if shape is SchemaShape.APARTMENT_BOOK:
        raise NotImplementedError(_APARTMENT_BOOK_WRITE_DEFERRAL_MSG)

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
    """Delete one or more contacts from the device.

    ``delete_contact`` is shape-agnostic: Akuvox firmware only accepts
    a delete-by-id payload on either schema, so no ``schema_shape=``
    kwarg is offered. The :meth:`AkuvoxDevice.delete_contact`
    wrapper performs the capability gate via
    ``self._capabilities.require(Capability.CONTACT_DELETE, ...)``
    and then delegates here without further dispatch.
    """
    if isinstance(id, str):
        ids = [id]
    else:
        ids = id
    items = [{"ID": cid} for cid in ids]
    await http.post("/api/contact/set", data=_mutation_body("del", items))
