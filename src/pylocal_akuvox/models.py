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
        except (ValueError, TypeError) as exc:
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
        except (ValueError, TypeError) as exc:
            msg = f"Invalid type for relay 'number': got {raw_number!r}"
            raise AkuvoxParseError(msg) from exc

        return cls(
            number=number,
            state=data.get("state"),
        )
