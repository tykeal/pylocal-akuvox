# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Access-schedule (time-window) data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylocal_akuvox.exceptions import AkuvoxParseError


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
