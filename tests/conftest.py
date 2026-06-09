# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures for pylocal-akuvox tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

import aiohttp
import aioresponses.core
import pytest

if TYPE_CHECKING:
    import asyncio

    from aiohttp.abc import AbstractStreamWriter
    from aiohttp.client_reqrep import RequestInfo
    from aiohttp.helpers import BaseTimerContext
    from aiohttp.tracing import Trace


class _Aiohttp314ClientResponse(aiohttp.ClientResponse):  # type: ignore[misc]
    """Client response compatible with aioresponses and aiohttp 3.14."""

    def __init__(
        self,
        method: str,
        url: object,
        *,
        writer: asyncio.Task[None] | None,
        continue100: asyncio.Future[bool] | None,
        timer: BaseTimerContext,
        request_info: RequestInfo,
        traces: list[Trace],
        loop: asyncio.AbstractEventLoop,
        session: aiohttp.ClientSession | None,
        stream_writer: AbstractStreamWriter | None = None,
    ) -> None:
        """Initialize the response with aiohttp 3.14 stream writer support."""
        if stream_writer is None:
            stream_writer = cast("AbstractStreamWriter", Mock())
        super().__init__(
            method,
            url,
            writer=writer,
            continue100=continue100,
            timer=timer,
            request_info=request_info,
            traces=traces,
            loop=loop,
            session=cast("aiohttp.ClientSession", session),
            stream_writer=stream_writer,
        )


@pytest.fixture(autouse=True)
def _patch_aioresponses_client_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch aioresponses for aiohttp 3.14's ClientResponse signature."""
    monkeypatch.setattr(aioresponses.core, "ClientResponse", _Aiohttp314ClientResponse)
