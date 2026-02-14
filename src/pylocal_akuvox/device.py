# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""High-level async interface for Akuvox device operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.models import DeviceInfo, DeviceStatus

if TYPE_CHECKING:
    from pylocal_akuvox.auth import AuthConfig
    from pylocal_akuvox.models import User


class AkuvoxDevice:
    """Async context manager for communicating with an Akuvox device."""

    def __init__(
        self,
        host: str,
        auth: AuthConfig | None = None,
        timeout: int = 10,
    ) -> None:
        """Initialize the device connection parameters."""
        self._http = AkuvoxHttpClient(host=host, auth=auth, timeout=timeout)

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
        web_relay: str,
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
