# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""High-level async interface for Akuvox device operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox import (
    _device_access,
    _device_config_logs,
    _device_contacts,
    _device_relays,
    _device_users,
)
from pylocal_akuvox._capability_probe import probe_capabilities as _probe_capabilities
from pylocal_akuvox._device_profiles import (
    _DEVICE_NOT_IN_MATRIX_NOTE,
    _merge_probe_with_matrix,
)
from pylocal_akuvox._device_runtime import (
    enter_device,
    exit_device,
    make_context,
    require_capabilities,
)
from pylocal_akuvox._device_runtime import (
    get_info as _runtime_get_info,
)
from pylocal_akuvox._device_runtime import (
    get_status as _runtime_get_status,
)
from pylocal_akuvox._http import AkuvoxHttpClient

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._capability_types import Capability
    from pylocal_akuvox._device_runtime import _DeviceContext
    from pylocal_akuvox.auth import AuthConfig
    from pylocal_akuvox.models import (
        AccessSchedule,
        CallLogEntry,
        Contact,
        DeviceConfig,
        DeviceInfo,
        DeviceStatus,
        DoorLogEntry,
        Group,
        User,
    )


__all__ = [
    "AkuvoxDevice",
    "_DEVICE_NOT_IN_MATRIX_NOTE",
    "_merge_probe_with_matrix",
]


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
        request_delay: float = 0.25,
    ) -> None:
        """Initialize the device connection parameters."""
        self._http = AkuvoxHttpClient(
            host=host,
            auth=auth,
            timeout=timeout,
            use_ssl=use_ssl,
            verify_ssl=verify_ssl,
            request_delay=request_delay,
        )
        self._capabilities: DeviceCapabilities | None = None
        self._info: DeviceInfo | None = None
        self.attempt_unknown_capability: bool = False

    @property
    def capabilities(self) -> DeviceCapabilities | None:
        """Return the effective capability profile for this connection."""
        return self._capabilities

    def _context(self) -> _DeviceContext:
        """Build the helper context from current facade state."""
        return make_context(
            self._http,
            self._capabilities,
            allow_unknown=self.attempt_unknown_capability,
        )

    def _require_capabilities(self) -> DeviceCapabilities:
        """Return established capabilities or raise the legacy lifecycle error."""
        return require_capabilities(self._capabilities)

    async def probe_capabilities(
        self,
        *,
        timeout: float | None = None,
    ) -> DeviceCapabilities:
        """Run a non-destructive capability probe against the connected device."""
        resolved_timeout = 5.0 if timeout is None else timeout
        probe_result = await _probe_capabilities(self._http, timeout=resolved_timeout)
        merged = _merge_probe_with_matrix(self._capabilities, probe_result)
        self._capabilities = merged
        return merged

    async def __aenter__(self) -> AkuvoxDevice:
        """Open the underlying HTTP session and populate capabilities."""
        await enter_device(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the underlying HTTP session and clear cached state."""
        await exit_device(self, exc_type, exc_val, exc_tb)

    async def get_info(self) -> DeviceInfo:
        """Retrieve device identification data."""
        return await _runtime_get_info(self._http, self._info)

    async def get_status(self) -> DeviceStatus:
        """Retrieve device operational status."""
        return await _runtime_get_status(self._http)

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
        await _device_users.add_user(
            self._context(),
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
        return await _device_users.list_users(self._context(), page=page)

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
        await _device_users.modify_user(
            self._context(),
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
        await _device_users.delete_user(self._context(), id=id)

    async def trigger_relay(
        self,
        *,
        num: int,
        mode: int = 0,
        level: int = 0,
        delay: int = 0,
        adapter: Capability | None = None,
    ) -> None:
        """Trigger a relay to unlock a door or gate."""
        await _device_relays.trigger_relay(
            self._context(),
            num=num,
            mode=mode,
            level=level,
            delay=delay,
            adapter=adapter,
        )

    def _resolve_override_adapter(
        self,
        caps: DeviceCapabilities,
        adapter: Capability,
    ) -> Capability:
        """Resolve a caller-supplied ``adapter=`` override."""
        return _device_relays.resolve_override_adapter(
            caps,
            adapter,
            allow_unknown=self.attempt_unknown_capability,
        )

    def _resolve_default_adapter(self, caps: DeviceCapabilities) -> Capability:
        """Walk the preference list and pick the first supported variant."""
        return _device_relays.resolve_default_adapter(caps)

    async def get_relay_status(self) -> dict[str, Any]:
        """Retrieve current relay states from the device."""
        return await _device_relays.get_relay_status(self._context())

    async def get_device_config(self) -> DeviceConfig:
        """Retrieve full device configuration."""
        return await _device_config_logs.get_device_config(self._context())

    async def set_device_config(self, settings: dict[str, str]) -> None:
        """Update device configuration settings."""
        await _device_config_logs.set_device_config(self._context(), settings)

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
        await _device_access.add_schedule(
            self._context(),
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
        return await _device_access.list_schedules(self._context(), page=page)

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
        await _device_access.modify_schedule(
            self._context(),
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
        await _device_access.delete_schedule(self._context(), id=id)

    async def list_groups(self, *, page: int | None = None) -> list[Group]:
        """List groups from the device."""
        return await _device_access.list_groups(self._context(), page=page)

    async def add_group(self, *, name: str) -> None:
        """Add a group to the device."""
        await _device_access.add_group(self._context(), name=name)

    async def modify_group(self, *, id: str, name: str) -> None:
        """Modify an existing group on the device."""
        await _device_access.modify_group(self._context(), id=id, name=name)

    async def delete_group(self, *, id: str) -> None:
        """Delete a group from the device."""
        await _device_access.delete_group(self._context(), id=id)

    async def list_contacts(self, *, page: int | None = None) -> list[Contact]:
        """List contacts from the device."""
        return await _device_contacts.list_contacts(self._context(), page=page)

    async def add_contact(
        self,
        *,
        name: str,
        phone: str | None = None,
        group: str | None = None,
    ) -> None:
        """Add a contact to the device address book."""
        await _device_contacts.add_contact(
            self._context(),
            name=name,
            phone=phone,
            group=group,
        )

    async def modify_contact(
        self,
        *,
        id: str,
        name: str | None = None,
        phone: str | None = None,
        group: str | None = None,
    ) -> None:
        """Modify an existing contact on the device."""
        await _device_contacts.modify_contact(
            self._context(),
            id=id,
            name=name,
            phone=phone,
            group=group,
        )

    async def delete_contact(self, *, id: str | list[str]) -> None:
        """Delete one or more contacts from the device."""
        await _device_contacts.delete_contact(self._context(), id=id)

    async def get_door_logs(self, *, page: int | None = None) -> list[DoorLogEntry]:
        """Retrieve door access logs from the device."""
        return await _device_config_logs.get_door_logs(self._context(), page=page)

    async def get_call_logs(self, *, page: int | None = None) -> list[CallLogEntry]:
        """Retrieve call logs from the device."""
        return await _device_config_logs.get_call_logs(self._context(), page=page)
