# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contact / address-book data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylocal_akuvox.exceptions import AkuvoxParseError


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
