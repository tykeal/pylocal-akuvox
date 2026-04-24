# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Data models for Akuvox API responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylocal_akuvox.exceptions import AkuvoxParseError


@dataclass(frozen=True)
class DeviceInfo:
    """Read-only device identification data."""

    model: str
    mac_address: str
    firmware_version: str
    hardware_version: str
    uptime: str | None = None
    web_language: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> DeviceInfo:
        """Create DeviceInfo from API response data."""
        status = data.get("Status", {})
        if not isinstance(status, dict):
            msg = "Expected 'Status' to be a dict in device info"
            raise AkuvoxParseError(msg)
        web_lang = status.get("WebLang")
        try:
            web_language = int(web_lang) if web_lang is not None else None
        except ValueError:
            # Separate handlers due to ruff 0.15.0 format bug
            # that strips parens from `except (ValueError, TypeError):`
            web_language = None
        except TypeError:
            web_language = None
        try:
            return cls(
                model=status["Model"],
                mac_address=status["MAC"],
                firmware_version=status["FirmwareVersion"],
                hardware_version=status["HardwareVersion"],
                uptime=status.get("Uptime"),
                web_language=web_language,
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in device info"
            raise AkuvoxParseError(msg) from exc


@dataclass(frozen=True)
class DeviceStatus:
    """Point-in-time device operational status."""

    unix_time: int
    uptime: int

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> DeviceStatus:
        """Create DeviceStatus from API response data."""
        try:
            raw_time = data["SystemTime"]
            raw_uptime = data["UpTime"]
        except KeyError as exc:
            msg = f"Missing required field {exc} in device status"
            raise AkuvoxParseError(msg) from exc

        try:
            return cls(
                unix_time=int(raw_time),
                uptime=int(raw_uptime),
            )
        except ValueError as exc:
            # Separate handlers due to ruff 0.15.0 format bug
            # that strips parens from `except (ValueError, TypeError):`
            msg = "Invalid type for 'SystemTime' or 'UpTime' in device status"
            raise AkuvoxParseError(msg) from exc
        except TypeError as exc:
            msg = "Invalid type for 'SystemTime' or 'UpTime' in device status"
            raise AkuvoxParseError(msg) from exc


@dataclass(frozen=True)
class Relay:
    """Controllable relay on the device."""

    number: int
    state: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Relay:
        """Create Relay from API response data."""
        try:
            raw_number = data["number"]
        except KeyError as exc:
            msg = f"Missing required field {exc} in relay data"
            raise AkuvoxParseError(msg) from exc

        try:
            number = int(raw_number)
        except ValueError as exc:
            # Separate handlers due to ruff 0.15.0 format bug
            # that strips parens from `except (ValueError, TypeError):`
            msg = f"Invalid type for relay 'number': got {raw_number!r}"
            raise AkuvoxParseError(msg) from exc
        except TypeError as exc:
            msg = f"Invalid type for relay 'number': got {raw_number!r}"
            raise AkuvoxParseError(msg) from exc

        return cls(
            number=number,
            state=data.get("state"),
        )


@dataclass(frozen=True, kw_only=True)
class User:
    """Local user account stored on the device."""

    name: str
    user_id: str
    schedule_relay: str
    id: str | None = None
    web_relay: str | None = None
    private_pin: str | None = None
    card_code: str | None = None
    lift_floor_num: str | None = None
    user_type: str | None = None
    source: str | None = None
    source_type: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> User:
        """Create User from API response data."""
        try:
            return cls(
                name=data["Name"],
                user_id=data["UserID"],
                schedule_relay=data["ScheduleRelay"],
                id=data.get("ID"),
                web_relay=data.get("WebRelay"),
                private_pin=data.get("PrivatePIN") or None,
                card_code=data.get("CardCode") or None,
                lift_floor_num=data.get("LiftFloorNum"),
                user_type=data.get("Type"),
                source=data.get("Source"),
                source_type=data.get("SourceType"),
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in user data"
            raise AkuvoxParseError(msg) from exc

    def to_api_payload(self) -> dict[str, str]:
        """Convert to PascalCase dict for add/set API calls."""
        payload: dict[str, str] = {
            "Name": self.name,
            "UserID": self.user_id,
            "ScheduleRelay": self.schedule_relay,
        }
        if self.id is not None:
            payload["ID"] = self.id
        if self.web_relay is not None:
            payload["WebRelay"] = self.web_relay
        if self.private_pin is not None:
            payload["PrivatePIN"] = self.private_pin
        if self.card_code is not None:
            payload["CardCode"] = self.card_code
        if self.lift_floor_num is not None:
            payload["LiftFloorNum"] = self.lift_floor_num
        if self.user_type is not None:
            payload["Type"] = self.user_type
        return payload


@dataclass(frozen=True, kw_only=True)
class AccessSchedule:
    """Time-based access schedule stored on the device."""

    schedule_type: str
    id: str | None = None
    name: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    week: str | None = None
    daily: str | None = None
    display_id: str | None = None
    source_type: str | None = None
    mode: str | None = None
    sun: str | None = None
    mon: str | None = None
    tue: str | None = None
    wed: str | None = None
    thur: str | None = None
    fri: str | None = None
    sat: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> AccessSchedule:
        """Create AccessSchedule from API response data."""
        try:
            return cls(
                schedule_type=data["Type"],
                id=data.get("ID"),
                name=data.get("Name"),
                date_start=data.get("DateStart"),
                date_end=data.get("DateEnd"),
                time_start=data.get("TimeStart"),
                time_end=data.get("TimeEnd"),
                week=data.get("Week"),
                daily=data.get("Daily"),
                display_id=data.get("DisplayID"),
                source_type=data.get("SourceType"),
                mode=data.get("Mode"),
                sun=data.get("Sun"),
                mon=data.get("Mon"),
                tue=data.get("Tue"),
                wed=data.get("Wed"),
                thur=data.get("Thur"),
                fri=data.get("Fri"),
                sat=data.get("Sat"),
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in schedule data"
            raise AkuvoxParseError(msg) from exc

    def to_api_payload(self) -> dict[str, str]:
        """Convert to PascalCase dict for add/set API calls."""
        payload: dict[str, str] = {
            "Type": self.schedule_type,
        }
        _optional: list[tuple[str | None, str]] = [
            (self.id, "ID"),
            (self.name, "Name"),
            (self.date_start, "DateStart"),
            (self.date_end, "DateEnd"),
            (self.time_start, "TimeStart"),
            (self.time_end, "TimeEnd"),
            (self.week, "Week"),
            (self.daily, "Daily"),
            (self.display_id, "DisplayID"),
            (self.source_type, "SourceType"),
            (self.mode, "Mode"),
            (self.sun, "Sun"),
            (self.mon, "Mon"),
            (self.tue, "Tue"),
            (self.wed, "Wed"),
            (self.thur, "Thur"),
            (self.fri, "Fri"),
            (self.sat, "Sat"),
        ]
        for value, key in _optional:
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True, kw_only=True)
class DoorLogEntry:
    """Read-only record from the device door access log."""

    id: str
    date: str
    time: str
    name: str
    code: str
    door_type: str
    status: str
    relay: str | None = None
    access_mode: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> DoorLogEntry:
        """Create DoorLogEntry from API response data."""
        try:
            return cls(
                id=data["ID"],
                date=data["Date"],
                time=data["Time"],
                name=data["Name"],
                code=data["Code"],
                door_type=data["Type"],
                status=data["Status"],
                relay=data.get("Relay"),
                access_mode=data.get("AccessMode"),
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in door log"
            raise AkuvoxParseError(msg) from exc


@dataclass(frozen=True, kw_only=True)
class CallLogEntry:
    """Read-only record from the device call log."""

    id: str
    date: str
    time: str
    name: str
    call_type: str
    local_identity: str
    count: str
    pic_url: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> CallLogEntry:
        """Create CallLogEntry from API response data."""
        try:
            return cls(
                id=data["ID"],
                date=data["Date"],
                time=data["Time"],
                name=data["Name"],
                call_type=data["Type"],
                local_identity=data["LocalIdentity"],
                count=data["Num"],
                pic_url=data.get("PicUrl"),
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in call log"
            raise AkuvoxParseError(msg) from exc


@dataclass(frozen=True, kw_only=True)
class DeviceConfig:
    """Full device configuration from /api/config/get.

    Wraps all autop-format key-value pairs returned by the device.
    Provides dict-like read access to any configuration key.
    """

    data: dict[str, str]

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> DeviceConfig:
        """Create DeviceConfig from API response data."""
        return cls(data={k: str(v) for k, v in data.items()})

    def to_api_payload(self) -> dict[str, str]:
        """Return the full data dict for set API calls."""
        return dict(self.data)

    def keys(self) -> list[str]:
        """Return all autop-format key names in this config.

        Returns:
            List of dotted key strings (e.g.,
            ``Config.DoorSetting.RELAY.HoldDelayA``).

        """
        return list(self.data.keys())

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a config value by autop-format key."""
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> str:
        """Bracket access by autop-format key."""
        return self.data[key]

    def __contains__(self, key: object) -> bool:
        """Check if an autop-format key exists."""
        return key in self.data

    def __len__(self) -> int:
        """Return the number of configuration keys."""
        return len(self.data)


@dataclass(frozen=True, kw_only=True)
class Group:
    """Organizational group stored on the device."""

    name: str
    id: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Group:
        """Create Group from API response data."""
        try:
            return cls(
                name=data["Name"],
                id=data.get("ID"),
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in group data"
            raise AkuvoxParseError(msg) from exc

    def to_api_payload(self) -> dict[str, str]:
        """Convert to PascalCase dict for add/set API calls."""
        payload: dict[str, str] = {"Name": self.name}
        if self.id is not None:
            payload["ID"] = self.id
        return payload


@dataclass(frozen=True, kw_only=True)
class Contact:
    """Contact entry in the device address book."""

    name: str
    id: str | None = None
    phone: str | None = None
    group: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> Contact:
        """Create Contact from API response data."""
        try:
            return cls(
                name=data["Name"],
                id=data.get("ID"),
                phone=data.get("Phone") or None,
                group=data.get("Group") or None,
            )
        except KeyError as exc:
            msg = f"Missing required field {exc} in contact data"
            raise AkuvoxParseError(msg) from exc

    def to_api_payload(self) -> dict[str, str]:
        """Convert to PascalCase dict for add/set API calls."""
        payload: dict[str, str] = {"Name": self.name}
        if self.id is not None:
            payload["ID"] = self.id
        if self.phone is not None:
            payload["Phone"] = self.phone
        if self.group is not None:
            payload["Group"] = self.group
        return payload
