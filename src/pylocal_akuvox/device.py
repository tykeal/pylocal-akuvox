# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""High-level async interface for Akuvox device operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.models import DeviceInfo

if TYPE_CHECKING:
    from pylocal_akuvox.auth import AuthConfig


class AkuvoxDevice:
    """Async context manager for communicating with an Akuvox device."""

    def __init__(
        self,
        host: str,
        auth: AuthConfig | None = None,
        timeout: int = 10,
    ) -> None:
        """Initialize the device connection parameters."""
        self._http = AkuvoxHttpClient(host=host, auth=auth, timeout=timeout)

    async def __aenter__(self) -> AkuvoxDevice:
        """Open the underlying HTTP session."""
        await self._http.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the underlying HTTP session."""
        await self._http.__aexit__(exc_type, exc_val, exc_tb)

    async def get_info(self) -> DeviceInfo:
        """Retrieve device identification data."""
        data = await self._http.get("/api/system/info")
        return DeviceInfo.from_api_response(data)
