# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""High-level async interface for Akuvox device operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.models import DeviceInfo, DeviceStatus

if TYPE_CHECKING:
    from pylocal_akuvox.auth import AuthConfig
    from pylocal_akuvox.models import (
        AccessSchedule,
        CallLogEntry,
        DeviceConfig,
        DoorLogEntry,
        Group,
        User,
    )


class AkuvoxDevice:
    """Async context manager for communicating with an Akuvox device."""

    def __init__(
        self,
        host: str,
        auth: AuthConfig | None = None,
        timeout: int = 10,
        *,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the device connection parameters."""
        self._http = AkuvoxHttpClient(
            host=host,
            auth=auth,
            timeout=timeout,
            use_ssl=use_ssl,
            verify_ssl=verify_ssl,
        )

    async def __aenter__(self) -> AkuvoxDevice:
        """Open the underlying HTTP session."""
        await self._http.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the underlying HTTP session."""
        await self._http.__aexit__(exc_type, exc_val, exc_tb)

    async def get_info(self) -> DeviceInfo:
        """Retrieve device identification data."""
        data = await self._http.get("/api/system/info")
        return DeviceInfo.from_api_response(data)

    async def get_status(self) -> DeviceStatus:
        """Retrieve device operational status."""
        data = await self._http.get("/api/system/status")
        return DeviceStatus.from_api_response(data)

    async def add_user(
        self,
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
        from pylocal_akuvox import users

        await users.add_user(
            self._http,
            name=name,
            user_id=user_id,
            web_relay=web_relay,
            schedule_relay=schedule_relay,
            lift_floor_num=lift_floor_num,
            private_pin=private_pin,
            card_code=card_code,
        )

    async def list_users(self, *, page: int | None = None) -> list[User]:
        """List users from the device."""
        from pylocal_akuvox import users

        return await users.list_users(self._http, page=page)

    async def modify_user(
        self,
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
        from pylocal_akuvox import users

        await users.modify_user(
            self._http,
            id=id,
            name=name,
            user_id=user_id,
            private_pin=private_pin,
            card_code=card_code,
            web_relay=web_relay,
            schedule_relay=schedule_relay,
            lift_floor_num=lift_floor_num,
        )

    async def delete_user(self, *, id: str) -> None:
        """Delete a user from the device."""
        from pylocal_akuvox import users

        await users.delete_user(self._http, id=id)

    async def trigger_relay(
        self,
        *,
        num: int,
        mode: int = 0,
        level: int = 0,
        delay: int = 0,
    ) -> None:
        """Trigger a relay to unlock a door or gate."""
        from pylocal_akuvox import relay

        await relay.trigger_relay(
            self._http, num=num, mode=mode, level=level, delay=delay
        )

    async def get_relay_status(self) -> dict[str, Any]:
        """Retrieve current relay states from the device."""
        from pylocal_akuvox import relay

        return await relay.get_relay_status(self._http)

    async def get_device_config(self) -> DeviceConfig:
        """Retrieve full device configuration."""
        from pylocal_akuvox import config

        return await config.get_device_config(self._http)

    async def set_device_config(self, settings: dict[str, str]) -> None:
        """Update device configuration settings."""
        from pylocal_akuvox import config

        await config.set_device_config(self._http, settings)

    async def add_schedule(
        self,
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
        from pylocal_akuvox import schedules

        await schedules.add_schedule(
            self._http,
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

    async def list_schedules(self, *, page: int | None = None) -> list[AccessSchedule]:
        """List schedules from the device."""
        from pylocal_akuvox import schedules

        return await schedules.list_schedules(self._http, page=page)

    async def modify_schedule(
        self,
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
        from pylocal_akuvox import schedules

        await schedules.modify_schedule(
            self._http,
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

    async def delete_schedule(self, *, id: str) -> None:
        """Delete a schedule from the device."""
        from pylocal_akuvox import schedules

        await schedules.delete_schedule(self._http, id=id)

    async def list_groups(
        self,
        *,
        page: int | None = None,
    ) -> list[Group]:
        """List groups from the device."""
        from pylocal_akuvox import groups

        return await groups.list_groups(self._http, page=page)

    async def add_group(self, *, name: str) -> None:
        """Add a group to the device."""
        from pylocal_akuvox import groups

        await groups.add_group(self._http, name=name)

    async def modify_group(
        self,
        *,
        id: str,
        name: str,
    ) -> None:
        """Modify an existing group on the device."""
        from pylocal_akuvox import groups

        await groups.modify_group(self._http, id=id, name=name)

    async def delete_group(self, *, id: str) -> None:
        """Delete a group from the device."""
        from pylocal_akuvox import groups

        await groups.delete_group(self._http, id=id)

    async def get_door_logs(self, *, page: int | None = None) -> list[DoorLogEntry]:
        """Retrieve door access logs from the device."""
        from pylocal_akuvox import logs

        return await logs.get_door_logs(self._http, page=page)

    async def get_call_logs(self, *, page: int | None = None) -> list[CallLogEntry]:
        """Retrieve call logs from the device."""
        from pylocal_akuvox import logs

        return await logs.get_call_logs(self._http, page=page)
