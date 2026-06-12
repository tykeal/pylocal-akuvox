# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""User-domain data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylocal_akuvox.exceptions import AkuvoxParseError


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
        missing = object()
        schedule_relay: Any = missing
        for key in ("ScheduleRelay", "Schedule-Relay", "Schedule"):
            if key in data:
                schedule_relay = data[key]
                break
        if schedule_relay is missing:
            msg = (
                "Missing required field 'ScheduleRelay' (or 'Schedule-Relay'/"
                "'Schedule' on some firmwares) in user data"
            )
            raise AkuvoxParseError(msg)

        try:
            return cls(
                name=data["Name"],
                user_id=data["UserID"],
                schedule_relay=schedule_relay,
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
