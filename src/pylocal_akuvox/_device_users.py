# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""User CRUD helpers for :class:`pylocal_akuvox.device.AkuvoxDevice`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox import users
from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_types import Capability

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import FieldAliases
    from pylocal_akuvox._device_runtime import _DeviceContext
    from pylocal_akuvox.models import User


def _schedule_relay_aliases(ctx: _DeviceContext) -> FieldAliases:
    """Return schedule relay aliases with the project default fallback."""
    return ctx.capabilities.field_aliases.get(
        "schedule_relay", DEFAULT_USER_FIELD_ALIASES
    )


async def add_user(
    ctx: _DeviceContext,
    *,
    name: str,
    user_id: str,
    web_relay: str | None = None,
    schedule_relay: str,
    lift_floor_num: str,
    private_pin: str | None = None,
    card_code: str | None = None,
) -> None:
    """Add a local user to the device."""
    ctx.capabilities.require(Capability.USER_ADD, allow_unknown=ctx.allow_unknown)
    await users.add_user(
        ctx.client,
        name=name,
        user_id=user_id,
        web_relay=web_relay,
        schedule_relay=schedule_relay,
        lift_floor_num=lift_floor_num,
        private_pin=private_pin,
        card_code=card_code,
        field_aliases=_schedule_relay_aliases(ctx),
    )


async def list_users(ctx: _DeviceContext, *, page: int | None = None) -> list[User]:
    """List users from the device."""
    ctx.capabilities.require(Capability.USER_LIST, allow_unknown=ctx.allow_unknown)
    return await users.list_users(
        ctx.client,
        page=page,
        capabilities=ctx.capabilities,
    )


async def modify_user(
    ctx: _DeviceContext,
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
    ctx.capabilities.require(Capability.USER_MODIFY, allow_unknown=ctx.allow_unknown)
    await users.modify_user(
        ctx.client,
        id=id,
        name=name,
        user_id=user_id,
        private_pin=private_pin,
        card_code=card_code,
        web_relay=web_relay,
        schedule_relay=schedule_relay,
        lift_floor_num=lift_floor_num,
        field_aliases=_schedule_relay_aliases(ctx),
    )


async def delete_user(ctx: _DeviceContext, *, id: str) -> None:
    """Delete a user from the device."""
    ctx.capabilities.require(Capability.USER_DELETE, allow_unknown=ctx.allow_unknown)
    await users.delete_user(ctx.client, id=id)
