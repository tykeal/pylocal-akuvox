# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Schedule and group helpers for :mod:`pylocal_akuvox.device`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox import groups, schedules
from pylocal_akuvox._capability_types import Capability

if TYPE_CHECKING:
    from pylocal_akuvox._device_runtime import _DeviceContext
    from pylocal_akuvox.models import AccessSchedule, Group


async def add_schedule(
    ctx: _DeviceContext,
    *,
    schedule_type: str,
    name: str | None = None,
    week: str | None = None,
    daily: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
    sun: str | None = None,
    mon: str | None = None,
    tue: str | None = None,
    wed: str | None = None,
    thur: str | None = None,
    fri: str | None = None,
    sat: str | None = None,
) -> None:
    """Add an access schedule to the device."""
    ctx.capabilities.require(Capability.SCHEDULE_ADD, allow_unknown=ctx.allow_unknown)
    await schedules.add_schedule(
        ctx.client,
        schedule_type=schedule_type,
        name=name,
        week=week,
        daily=daily,
        date_start=date_start,
        date_end=date_end,
        time_start=time_start,
        time_end=time_end,
        sun=sun,
        mon=mon,
        tue=tue,
        wed=wed,
        thur=thur,
        fri=fri,
        sat=sat,
    )


async def list_schedules(
    ctx: _DeviceContext,
    *,
    page: int | None = None,
) -> list[AccessSchedule]:
    """List schedules from the device."""
    ctx.capabilities.require(Capability.SCHEDULE_LIST, allow_unknown=ctx.allow_unknown)
    return await schedules.list_schedules(ctx.client, page=page)


async def modify_schedule(
    ctx: _DeviceContext,
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
    sun: str | None = None,
    mon: str | None = None,
    tue: str | None = None,
    wed: str | None = None,
    thur: str | None = None,
    fri: str | None = None,
    sat: str | None = None,
) -> None:
    """Modify an existing schedule on the device."""
    ctx.capabilities.require(
        Capability.SCHEDULE_MODIFY,
        allow_unknown=ctx.allow_unknown,
    )
    await schedules.modify_schedule(
        ctx.client,
        id=id,
        name=name,
        schedule_type=schedule_type,
        week=week,
        daily=daily,
        date_start=date_start,
        date_end=date_end,
        time_start=time_start,
        time_end=time_end,
        sun=sun,
        mon=mon,
        tue=tue,
        wed=wed,
        thur=thur,
        fri=fri,
        sat=sat,
    )


async def delete_schedule(ctx: _DeviceContext, *, id: str) -> None:
    """Delete a schedule from the device."""
    ctx.capabilities.require(
        Capability.SCHEDULE_DELETE,
        allow_unknown=ctx.allow_unknown,
    )
    await schedules.delete_schedule(ctx.client, id=id)


async def list_groups(
    ctx: _DeviceContext,
    *,
    page: int | None = None,
) -> list[Group]:
    """List groups from the device."""
    ctx.capabilities.require(Capability.GROUP_LIST, allow_unknown=ctx.allow_unknown)
    return await groups.list_groups(ctx.client, page=page)


async def add_group(ctx: _DeviceContext, *, name: str) -> None:
    """Add a group to the device."""
    ctx.capabilities.require(Capability.GROUP_ADD, allow_unknown=ctx.allow_unknown)
    await groups.add_group(ctx.client, name=name)


async def modify_group(ctx: _DeviceContext, *, id: str, name: str) -> None:
    """Modify an existing group on the device."""
    ctx.capabilities.require(Capability.GROUP_MODIFY, allow_unknown=ctx.allow_unknown)
    await groups.modify_group(ctx.client, id=id, name=name)


async def delete_group(ctx: _DeviceContext, *, id: str) -> None:
    """Delete a group from the device."""
    ctx.capabilities.require(Capability.GROUP_DELETE, allow_unknown=ctx.allow_unknown)
    await groups.delete_group(ctx.client, id=id)
