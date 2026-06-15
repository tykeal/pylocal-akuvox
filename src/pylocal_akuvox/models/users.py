# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""User-domain data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox.exceptions import AkuvoxParseError

if TYPE_CHECKING:
    from pylocal_akuvox._capability_profile import DeviceCapabilities


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
    def from_api_response(
        cls,
        data: dict[str, Any],
        *,
        capabilities: DeviceCapabilities | None = None,
    ) -> User:
        """Create User from API response data.

        ``capabilities`` is an optional :class:`DeviceCapabilities`
        record. When supplied, the parser consults
        ``capabilities.field_aliases.get("schedule_relay")`` to find
        the schedule-relay field, walking each name in
        ``FieldAliases.read`` in declared order and using the first
        match. When omitted (or when the record has no
        ``"schedule_relay"`` entry), the parser falls back to the
        canonical ``schedule_relay`` chain::

            FieldAliases(
                read=("ScheduleRelay", "Schedule-Relay", "Schedule"),
                write=("ScheduleRelay", "Schedule-Relay"),
            )

        byte-identical to the pre-refactor hardcoded chain —
        preserving FR-016 (no externally observable change for
        default callers).
        """
        aliases = DEFAULT_USER_FIELD_ALIASES
        if capabilities is not None:
            aliases = capabilities.field_aliases.get(
                "schedule_relay", DEFAULT_USER_FIELD_ALIASES
            )
        # Defensive: a capability record with an empty ``read`` tuple
        # for the schedule-relay field (incomplete matrix entry, or
        # an unexpected probe output) would otherwise make every
        # parse raise ``AkuvoxParseError`` even for payloads that
        # carry the legacy keys. Fall back to the default chain so
        # incomplete capability data degrades gracefully rather than
        # bricking the read path (Copilot review round 1).
        if not aliases.read:
            aliases = DEFAULT_USER_FIELD_ALIASES

        missing = object()
        schedule_relay: Any = missing
        for key in aliases.read:
            if key in data:
                schedule_relay = data[key]
                break
        if schedule_relay is missing:
            # Reuse the pre-refactor message verbatim so the existing
            # regression assertions in test_models.py (which probe the
            # exact substring set) keep passing under the default
            # fallback path (FR-016 / SC-008).
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
