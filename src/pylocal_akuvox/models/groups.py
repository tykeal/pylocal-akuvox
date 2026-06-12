# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Organizational-group data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylocal_akuvox.exceptions import AkuvoxParseError


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
