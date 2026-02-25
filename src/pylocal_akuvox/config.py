# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Device configuration operations for Akuvox devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox.exceptions import AkuvoxValidationError

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.models import DeviceConfig


async def get_device_config(http: AkuvoxHttpClient) -> DeviceConfig:
    """Retrieve full device configuration.

    Args:
        http: The HTTP client for device communication.

    Returns:
        A DeviceConfig object with all configuration key-value pairs.

    """
    from pylocal_akuvox.models import DeviceConfig as _DeviceConfig

    data = await http.get("/api/config/get")
    return _DeviceConfig.from_api_response(data)


async def set_device_config(http: AkuvoxHttpClient, settings: dict[str, str]) -> None:
    """Update device configuration settings.

    Args:
        http: The HTTP client for device communication.
        settings: Dict of autop-format keys to new string values.

    Raises:
        AkuvoxValidationError: If settings is empty.

    """
    if not settings:
        msg = "settings must contain at least one key-value pair"
        raise AkuvoxValidationError(msg)

    body = {"target": "config", "action": "set", "data": dict(settings)}
    await http.post("/api/config/set", data=body)
