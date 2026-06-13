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
        request_delay: float = 0.25,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            host: Device host name or IP address.
            timeout: Total request timeout in seconds.
            auth: Optional authentication configuration.
            use_ssl: Whether to use HTTPS for requests.
            verify_ssl: Whether to verify TLS certificates.
            request_delay: Delay in seconds after each successful request.

        Raises:
            ValueError: If request_delay is negative.

        """
        if request_delay < 0:
            msg = "request_delay must be non-negative"
            raise ValueError(msg)

        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._auth = auth
        self._verify_ssl = verify_ssl
        self._use_ssl = use_ssl
        self._request_delay = request_delay
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> AkuvoxHttpClient:
        """Open the HTTP session."""
        if self._session is not None and not self._session.closed:
            msg = "Session already open; nested context usage is not supported"
            raise AkuvoxConnectionError(msg)
        aiohttp_auth, middlewares = self._resolve_auth()
        ssl_context = self._build_ssl_context()
        connector_kwargs: dict[str, object] = {"force_close": True}
        if ssl_context is not None:
            connector_kwargs["ssl"] = ssl_context
        connector = aiohttp.TCPConnector(**connector_kwargs)
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
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a GET request and return parsed envelope data.

        Args:
            path: Request path (joined with the base URL).
            params: Optional query-string parameters.
            timeout: Optional per-call total timeout in seconds. When
                ``None`` (the default) the session-level timeout
                configured at construction time applies.

        """
        async with self._lock:
            result = await self._request("GET", path, params=params, timeout=timeout)
            await self._post_request_delay()
            return result

    async def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a POST request with JSON payload.

        Args:
            path: Request path (joined with the base URL).
            data: Optional JSON body.
            timeout: Optional per-call total timeout in seconds. When
                ``None`` (the default) the session-level timeout
                configured at construction time applies.

        """
        async with self._lock:
            result = await self._request("POST", path, data=data, timeout=timeout)
            await self._post_request_delay()
            return result

    async def _post_request_delay(self) -> None:
        """Pause after a successful request to avoid overwhelming the device."""
        if self._request_delay > 0:
            await asyncio.sleep(self._request_delay)

    async def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
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
        if timeout is not None:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        try:
            async with self._session.request(method, url, **kwargs) as resp:
                return await self._handle_response(resp)
        except (aiohttp.ClientError, TimeoutError) as err:
            msg = f"Connection to {self._base_url} failed: {err}"
            raise AkuvoxConnectionError(msg) from err

    async def _request_raw(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str]:
        """Issue a request and return ``(status, raw_body_text)`` unchanged.

        Bypasses :meth:`_handle_response` translation: returns the raw
        HTTP status and the unparsed body text for every non-transport
        outcome, including HTTP 4xx / 5xx and any JSON envelope whose
        ``retcode`` is negative or whose ``message`` carries an
        ``Api unsupported`` / ``unsupported action`` marker (see the
        constants in this module for the exact strings).
        Authentication classification (status 401 / 403) is the
        caller's responsibility.

        Raises :class:`AkuvoxConnectionError` only for transport-level
        failures (connection refused, DNS failure, asyncio
        ``TimeoutError``) — same wrapper as the existing public
        methods. The capability probe is the sole intended consumer.
        """
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
        if timeout is not None:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        try:
            async with self._session.request(method, url, **kwargs) as resp:
                body = await resp.text()
                return resp.status, body
        except (aiohttp.ClientError, TimeoutError) as err:
            msg = f"Connection to {self._base_url} failed: {err}"
            raise AkuvoxConnectionError(msg) from err

    @staticmethod
    def _parse_envelope(body: object) -> tuple[int, str, dict[str, Any]]:
        """Extract and validate retcode, message, data from response body."""
        if not isinstance(body, dict) or "retcode" not in body:
            msg = f"Missing envelope fields: {body!r}"
            raise AkuvoxParseError(msg)

        retcode = body["retcode"]
        if not isinstance(retcode, int):
            msg = f"Expected retcode to be int, got {type(retcode).__name__}"
            raise AkuvoxParseError(msg)

        message = body.get("message", "")
        if not isinstance(message, str):
            message = str(message) if message is not None else ""

        data = body.get("data", {})
        result: dict[str, Any] = data if isinstance(data, dict) else {}
        return retcode, message, result

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

        retcode, message, data = self._parse_envelope(body)

        if _UNSUPPORTED_MSG in message:
            raise AkuvoxUnsupportedError(message)

        if retcode < 0:
            raise AkuvoxDeviceError(message)

        return data

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        """Build SSL context for the connector.

        Returns a permissive SSLContext when SSL is enabled with
        verification disabled, or None for default behavior.
        """
        if not self._use_ssl or self._verify_ssl:
            return None
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # Some Akuvox devices (e.g. S562 indoor monitor) ship
        # 1024-bit DH parameters, which OpenSSL's default
        # SECLEVEL=2 rejects with "dh key too small". Lower the
        # security level to allow legacy primes/ciphers. Only in
        # effect when the caller has already disabled verification.
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=0")
        except ssl.SSLError:
            # TLS backends without OpenSSL's @SECLEVEL syntax (e.g.
            # some LibreSSL builds) reject this string. Fall back to
            # backend defaults rather than failing session creation.
            pass
        return ctx

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
