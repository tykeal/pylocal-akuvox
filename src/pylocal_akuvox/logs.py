# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Log retrieval operations for Akuvox devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox.models import CallLogEntry, DoorLogEntry

if TYPE_CHECKING:
    from pylocal_akuvox._http import AkuvoxHttpClient


async def get_door_logs(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
) -> list[DoorLogEntry]:
    """Retrieve door access logs from the device."""
    body: dict[str, Any] = {}
    if page is not None:
        body["page"] = page

    data = await http.post("/api/doorlog/get", data=body or None)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [
        DoorLogEntry.from_api_response(item) for item in items if isinstance(item, dict)
    ]


async def get_call_logs(
    http: AkuvoxHttpClient,
    *,
    page: int | None = None,
) -> list[CallLogEntry]:
    """Retrieve call logs from the device."""
    body: dict[str, Any] = {}
    if page is not None:
        body["page"] = page

    data = await http.post("/api/calllog/get", data=body or None)
    items = data.get("item", [])
    if not isinstance(items, list):
        return []
    return [
        CallLogEntry.from_api_response(item) for item in items if isinstance(item, dict)
    ]
