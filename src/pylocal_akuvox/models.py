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


@dataclass(frozen=True)
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
