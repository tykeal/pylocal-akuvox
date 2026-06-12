# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Device-configuration data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
