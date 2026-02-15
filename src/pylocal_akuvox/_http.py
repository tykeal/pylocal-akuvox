# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Internal HTTP client wrapper for Akuvox device communication."""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import TYPE_CHECKING, Any

import aiohttp

from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pylocal_akuvox.auth import AuthConfig

    type _Middleware = Any

_UNSUPPORTED_MSG = "Api unsupported"


class AkuvoxHttpClient:
    """Low-level HTTP client for Akuvox device API calls."""

    def __init__(
        self,
        host: str,
        timeout: int = 10,
        auth: AuthConfig | None = None,
        *,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the HTTP client."""
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._auth = auth
        self._verify_ssl = verify_ssl
        self._use_ssl = use_ssl
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> AkuvoxHttpClient:
        """Open the HTTP session."""
        if self._session is not None and not self._session.closed:
            msg = "Session already open; nested context usage is not supported"
            raise AkuvoxConnectionError(msg)
        aiohttp_auth, middlewares = self._resolve_auth()
        ssl_context: ssl.SSLContext | bool | None = None
        if self._use_ssl and not self._verify_ssl:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(
            force_close=True,
            ssl=ssl_context,
        )
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
            auth=aiohttp_auth,
            middlewares=middlewares,
            connector=connector,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a GET request and return parsed envelope data."""
        async with self._lock:
            return await self._request("GET", path, params=params)

    async def post(
        self, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a POST request with JSON payload."""
        async with self._lock:
            return await self._request("POST", path, data=data)

    async def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request and parse the response envelope."""
        if self._session is None or self._session.closed:
            msg = "Session not open; use async context manager"
            raise AkuvoxConnectionError(msg)

        if not path.startswith("/"):
            path = f"/{path}"

        url = f"{self._base_url}{path}"
        kwargs: dict[str, Any] = {}
        if data is not None:
            kwargs["json"] = data
        if params is not None:
            kwargs["params"] = params

        try:
            async with self._session.request(method, url, **kwargs) as resp:
                return await self._handle_response(resp)
        except (aiohttp.ClientError, TimeoutError) as err:
            msg = f"Connection to {self._base_url} failed: {err}"
            raise AkuvoxConnectionError(msg) from err

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> dict[str, Any]:
        """Parse response and map errors to exceptions."""
        if resp.status == 401:
            msg = "Authentication required"
            raise AkuvoxAuthenticationError(msg)
        if resp.status == 400:
            msg = f"Bad request: {resp.status}"
            raise AkuvoxRequestError(msg)
        if 400 < resp.status < 500:
            msg = f"HTTP client error: {resp.status}"
            raise AkuvoxRequestError(msg)
        if resp.status >= 500:
            msg = f"Device error: HTTP {resp.status}"
            raise AkuvoxDeviceError(msg)

        try:
            body = await resp.json(content_type=None)
        except (json.JSONDecodeError, aiohttp.ContentTypeError) as err:
            msg = "Invalid JSON response"
            raise AkuvoxParseError(msg) from err

        if not isinstance(body, dict) or "retcode" not in body:
            msg = f"Missing envelope fields: {body!r}"
            raise AkuvoxParseError(msg)

        retcode = body["retcode"]
        message = body.get("message", "")

        if _UNSUPPORTED_MSG in message:
            raise AkuvoxUnsupportedError(message)

        if retcode < 0:
            raise AkuvoxDeviceError(message)

        data = body.get("data", {})
        result: dict[str, Any] = data if isinstance(data, dict) else {}
        return result

    def _resolve_auth(
        self,
    ) -> tuple[aiohttp.BasicAuth | None, Sequence[_Middleware]]:
        """Map AuthConfig to aiohttp auth and middlewares."""
        if self._auth is None:
            return None, ()

        from pylocal_akuvox.auth import AuthMethod

        if self._auth.method in (AuthMethod.NONE, AuthMethod.ALLOWLIST):
            return None, ()
        if self._auth.method == AuthMethod.BASIC:
            return aiohttp.BasicAuth(
                self._auth.username or "",
                self._auth.password or "",
            ), ()
        # DIGEST: aiohttp 3.13+ uses DigestAuthMiddleware via middlewares param.
        # There is no aiohttp.DigestAuth; digest auth requires middleware.
        return None, (
            aiohttp.DigestAuthMiddleware(
                self._auth.username or "",
                self._auth.password or "",
            ),
        )
