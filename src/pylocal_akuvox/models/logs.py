# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Event-log data models (door-open and call records)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylocal_akuvox.exceptions import AkuvoxParseError


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
