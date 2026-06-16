# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contact helpers for :class:`pylocal_akuvox.device.AkuvoxDevice`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox import contacts
from pylocal_akuvox._capability_types import Capability, SchemaShape

if TYPE_CHECKING:
    from pylocal_akuvox._device_runtime import _DeviceContext
    from pylocal_akuvox.models import Contact


def _contact_shape(ctx: _DeviceContext) -> SchemaShape:
    """Return the contact schema shape with the door-phone fallback."""
    return ctx.capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)


async def list_contacts(
    ctx: _DeviceContext,
    *,
    page: int | None = None,
) -> list[Contact]:
    """List contacts from the device."""
    ctx.capabilities.require(Capability.CONTACT_LIST, allow_unknown=ctx.allow_unknown)
    return await contacts.list_contacts(
        ctx.client,
        page=page,
        capabilities=ctx.capabilities,
    )


async def add_contact(
    ctx: _DeviceContext,
    *,
    name: str,
    phone: str | None = None,
    group: str | None = None,
) -> None:
    """Add a contact to the device address book."""
    ctx.capabilities.require(Capability.CONTACT_ADD, allow_unknown=ctx.allow_unknown)
    await contacts.add_contact(
        ctx.client,
        name=name,
        phone=phone,
        group=group,
        schema_shape=_contact_shape(ctx),
    )


async def modify_contact(
    ctx: _DeviceContext,
    *,
    id: str,
    name: str | None = None,
    phone: str | None = None,
    group: str | None = None,
) -> None:
    """Modify an existing contact on the device."""
    ctx.capabilities.require(
        Capability.CONTACT_MODIFY,
        allow_unknown=ctx.allow_unknown,
    )
    await contacts.modify_contact(
        ctx.client,
        id=id,
        name=name,
        phone=phone,
        group=group,
        schema_shape=_contact_shape(ctx),
    )


async def delete_contact(ctx: _DeviceContext, *, id: str | list[str]) -> None:
    """Delete one or more contacts from the device."""
    ctx.capabilities.require(
        Capability.CONTACT_DELETE,
        allow_unknown=ctx.allow_unknown,
    )
    await contacts.delete_contact(ctx.client, id=id)
