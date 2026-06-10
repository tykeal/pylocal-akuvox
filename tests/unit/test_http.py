# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for HTTP client wrapper and response envelope parsing."""

import asyncio
import ssl
from typing import Any
from unittest.mock import AsyncMock, call, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
)

BASE_URL = "http://192.168.1.100"
SUCCESS_RESPONSE = {
    "retcode": 0,
    "action": "getSystemInfo",
    "message": "Success",
    "data": {"Status": {"Model": "E16C"}},
}


@pytest.fixture
def client() -> AkuvoxHttpClient:
    """Create test HTTP client with no delay for existing tests."""
    return AkuvoxHttpClient(host="192.168.1.100", timeout=5, request_delay=0.0)


async def test_successful_get(client: AkuvoxHttpClient) -> None:
    """Verify successful GET returns envelope data."""
    response = {
        "retcode": 0,
        "action": "getSystemInfo",
        "message": "Success",
        "data": {"Status": {"Model": "E16C"}},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=response)
        async with client:
            result = await client.get("/api/system/info")
    assert result == {"Status": {"Model": "E16C"}}


async def test_null_data_returns_empty_dict(client: AkuvoxHttpClient) -> None:
    """Verify null data field returns empty dict."""
    response = {
        "retcode": 0,
        "action": "trigRelay",
        "message": "Success",
        "data": None,
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=response)
        async with client:
            result = await client.get("/api/system/info")
    assert result == {}


async def test_non_dict_data_returns_empty_dict(client: AkuvoxHttpClient) -> None:
    """Verify non-dict data field returns empty dict."""
    response = {
        "retcode": 0,
        "action": "listUsers",
        "message": "Success",
        "data": ["unexpected", "list"],
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=response)
        async with client:
            result = await client.get("/api/system/info")
    assert result == {}


async def test_successful_post(client: AkuvoxHttpClient) -> None:
    """Verify successful POST sends JSON as application/json."""
    response = {
        "retcode": 0,
        "action": "trigRelay",
        "message": "Success",
        "data": {},
    }
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/relay/trig", payload=response)
        async with client:
            result = await client.post("/api/relay/trig", data={"num": 1})

        call = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"))][0]
        # json= kwarg tells aiohttp to send application/json
        assert call.kwargs.get("json") == {"num": 1}
    assert result == {}


async def test_retcode_positive_nonzero_succeeds(
    client: AkuvoxHttpClient,
) -> None:
    """Verify positive retcode (e.g. 1) is treated as success."""
    response = {
        "retcode": 1,
        "action": "add",
        "message": "OK",
    }
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/user/set", payload=response)
        async with client:
            result = await client.post("/api/user/set", data={})
    assert result == {}


async def test_retcode_negative_raises_device_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify negative retcode raises AkuvoxDeviceError."""
    response = {
        "retcode": -1,
        "action": "trigRelay",
        "message": "Error occurred",
    }
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/relay/trig", payload=response)
        async with client:
            with pytest.raises(AkuvoxDeviceError, match="Error occurred"):
                await client.post("/api/relay/trig", data={"num": 1})


async def test_non_json_raises_parse_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify non-JSON response raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            body="<html>Not Found</html>",
            content_type="text/html",
        )
        async with client:
            with pytest.raises(AkuvoxParseError):
                await client.get("/api/system/info")


async def test_http_401_raises_auth_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify HTTP 401 raises AkuvoxAuthenticationError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=401)
        async with client:
            with pytest.raises(AkuvoxAuthenticationError):
                await client.get("/api/system/info")


async def test_http_400_raises_request_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify HTTP 400 raises AkuvoxRequestError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=400)
        async with client:
            with pytest.raises(AkuvoxRequestError):
                await client.get("/api/system/info")


async def test_http_403_raises_request_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify HTTP 403 raises AkuvoxRequestError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=403)
        async with client:
            with pytest.raises(AkuvoxRequestError, match="HTTP client error"):
                await client.get("/api/system/info")


async def test_http_404_raises_request_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify HTTP 404 raises AkuvoxRequestError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=404)
        async with client:
            with pytest.raises(AkuvoxRequestError, match="HTTP client error"):
                await client.get("/api/system/info")


async def test_connection_timeout_raises_connection_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify connection timeout raises AkuvoxConnectionError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=TimeoutError(),
        )
        async with client:
            with pytest.raises(AkuvoxConnectionError):
                await client.get("/api/system/info")


async def test_connection_refused_raises_connection_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify connection refused raises AkuvoxConnectionError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=aiohttp.ClientError("Connection refused"),
        )
        async with client:
            with pytest.raises(AkuvoxConnectionError):
                await client.get("/api/system/info")


async def test_unsupported_api_raises_unsupported_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify 'Api unsupported' retcode raises AkuvoxUnsupportedError."""
    response = {
        "retcode": 200,
        "action": "unknown",
        "message": "Api unsupported",
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=response)
        async with client:
            with pytest.raises(AkuvoxUnsupportedError):
                await client.get("/api/system/info")


async def test_concurrent_requests_serialize(
    client: AkuvoxHttpClient,
) -> None:
    """Verify concurrent requests are serialized via Lock."""
    events: list[str] = []
    response = {
        "retcode": 0,
        "action": "getSystemInfo",
        "message": "Success",
        "data": {},
    }

    original_request = client._request

    async def instrumented_request(
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record entry/exit to verify non-overlap."""
        idx = len([e for e in events if e.startswith("enter")])
        events.append(f"enter-{idx}")
        result = await original_request(method, path, data, params)
        events.append(f"exit-{idx}")
        return result

    client._request = instrumented_request  # type: ignore[method-assign]

    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=response, repeat=True)

        async with client:
            await asyncio.gather(
                client.get("/api/system/info"),
                client.get("/api/system/info"),
                client.get("/api/system/info"),
            )

    # With serialization, events must alternate enter/exit (no overlap)
    assert len(events) == 6
    for i in range(0, 6, 2):
        assert events[i].startswith("enter")
        assert events[i + 1].startswith("exit")
        # Each exit matches its enter
        assert events[i].split("-")[1] == events[i + 1].split("-")[1]


async def test_post_sends_json(client: AkuvoxHttpClient) -> None:
    """Verify POST sends JSON with application/json content type."""
    response = {
        "retcode": 0,
        "action": "addUser",
        "message": "Success",
        "data": {},
    }
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/user/set", payload=response)
        async with client:
            await client.post("/api/user/set", data={"Name": "Test"})

        call = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/set"))][0]
        assert call.kwargs.get("json") == {"Name": "Test"}


async def test_context_manager_lifecycle(
    client: AkuvoxHttpClient,
) -> None:
    """Verify async context manager creates and closes session."""
    assert client._session is None
    async with client:
        assert client._session is not None
        assert not client._session.closed
    assert client._session is None or client._session.closed


async def test_http_500_raises_device_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify HTTP 500 raises AkuvoxDeviceError."""
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", status=500)
        async with client:
            with pytest.raises(AkuvoxDeviceError):
                await client.get("/api/system/info")


async def test_request_without_session_raises() -> None:
    """Verify request without open session raises AkuvoxConnectionError."""
    client = AkuvoxHttpClient(host="192.168.1.100")
    with pytest.raises(AkuvoxConnectionError, match="Session not open"):
        await client.get("/api/system/info")


async def test_missing_envelope_raises_parse_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify response without retcode raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"unexpected": "response"},
        )
        async with client:
            with pytest.raises(AkuvoxParseError, match="Missing envelope"):
                await client.get("/api/system/info")


async def test_retcode_not_int_raises_parse_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify non-integer retcode raises AkuvoxParseError."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"retcode": "0", "message": "ok", "data": {}},
        )
        async with client:
            with pytest.raises(AkuvoxParseError, match="Expected retcode"):
                await client.get("/api/system/info")


async def test_non_string_message_coerced(
    client: AkuvoxHttpClient,
) -> None:
    """Verify non-string message is coerced to str without error."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"retcode": 0, "message": 12345, "data": {"ok": True}},
        )
        async with client:
            result = await client.get("/api/system/info")
    assert result == {"ok": True}


async def test_none_message_coerced_to_empty(
    client: AkuvoxHttpClient,
) -> None:
    """Verify None message becomes empty string."""
    with aioresponses() as m:
        m.get(
            f"{BASE_URL}/api/system/info",
            payload={"retcode": 0, "message": None, "data": {"ok": True}},
        )
        async with client:
            result = await client.get("/api/system/info")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_resolve_auth_basic() -> None:
    """Verify BASIC auth resolves to aiohttp.BasicAuth."""
    from pylocal_akuvox.auth import AuthConfig, AuthMethod

    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="pass")
    client = AkuvoxHttpClient(host="192.168.1.100", auth=auth)
    resolved_auth, middlewares = client._resolve_auth()
    assert isinstance(resolved_auth, aiohttp.BasicAuth)
    assert resolved_auth.login == "admin"
    assert resolved_auth.password == "pass"
    assert middlewares == ()


async def test_resolve_auth_digest() -> None:
    """Verify DIGEST auth resolves to DigestAuthMiddleware."""
    from pylocal_akuvox.auth import AuthConfig, AuthMethod

    auth = AuthConfig(method=AuthMethod.DIGEST, username="admin", password="pass")
    client = AkuvoxHttpClient(host="192.168.1.100", auth=auth)
    resolved_auth, middlewares = client._resolve_auth()
    assert resolved_auth is None
    assert len(middlewares) == 1
    assert isinstance(middlewares[0], aiohttp.DigestAuthMiddleware)


async def test_resolve_auth_none() -> None:
    """Verify NONE auth resolves to None."""
    from pylocal_akuvox.auth import AuthConfig, AuthMethod

    auth = AuthConfig(method=AuthMethod.NONE)
    client = AkuvoxHttpClient(host="192.168.1.100", auth=auth)
    resolved_auth, middlewares = client._resolve_auth()
    assert resolved_auth is None
    assert middlewares == ()


async def test_aexit_idempotent(client: AkuvoxHttpClient) -> None:
    """Verify __aexit__ is safe when session is already None."""
    await client.__aexit__(None, None, None)
    assert client._session is None


async def test_request_on_closed_session_raises(client: AkuvoxHttpClient) -> None:
    """Verify request on externally closed session raises AkuvoxConnectionError."""
    async with client:
        assert client._session is not None
        await client._session.close()
        with pytest.raises(AkuvoxConnectionError, match="Session not open"):
            await client.get("/api/system/info")


async def test_reenter_raises_connection_error(
    client: AkuvoxHttpClient,
) -> None:
    """Verify re-entering open session raises AkuvoxConnectionError."""
    async with client:
        with pytest.raises(AkuvoxConnectionError, match="Session already open"):
            await client.__aenter__()


async def test_path_without_leading_slash(client: AkuvoxHttpClient) -> None:
    """Verify path without leading slash is normalized."""
    response = {
        "retcode": 0,
        "action": "getSystemInfo",
        "message": "Success",
        "data": {"Status": {"Model": "E16C"}},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/system/info", payload=response)
        async with client:
            result = await client.get("api/system/info")
    assert result == {"Status": {"Model": "E16C"}}


async def test_get_with_params(client: AkuvoxHttpClient) -> None:
    """Verify get() passes query params to the request."""
    response = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {"num": 0, "item": []},
    }
    with aioresponses() as m:
        m.get(f"{BASE_URL}/api/user/get?page=2", payload=response)
        async with client:
            result = await client.get("/api/user/get", params={"page": 2})
    assert result == {"num": 0, "item": []}


# -- SSL configuration tests --


def test_default_uses_http() -> None:
    """Verify default client uses http scheme."""
    c = AkuvoxHttpClient(host="192.168.1.100")
    assert c._base_url == "http://192.168.1.100"


def test_use_ssl_uses_https() -> None:
    """Verify use_ssl=True switches to https scheme."""
    c = AkuvoxHttpClient(host="192.168.1.100", use_ssl=True)
    assert c._base_url == "https://192.168.1.100"


def test_ssl_no_verify_creates_permissive_context() -> None:
    """Verify ssl+no verify creates SSLContext with CERT_NONE."""
    c = AkuvoxHttpClient(host="192.168.1.100", use_ssl=True, verify_ssl=False)
    ctx = c._build_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False


def test_ssl_no_verify_lowers_seclevel_for_legacy_dh() -> None:
    """Verify ssl+no verify lowers OpenSSL SECLEVEL for legacy DH.

    Some Akuvox devices (e.g. S562) ship 1024-bit DH parameters that
    OpenSSL's default SECLEVEL=2 rejects. The no-verify path lowers
    SECLEVEL to 0 so the handshake succeeds.
    """
    c = AkuvoxHttpClient(host="192.168.1.100", use_ssl=True, verify_ssl=False)
    ctx = c._build_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)

    # Build a reference context at SECLEVEL=0 for comparison.
    ref = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ref.set_ciphers("DEFAULT@SECLEVEL=0")
    ref_names = {cipher["name"] for cipher in ref.get_ciphers()}

    # A default context (no set_ciphers) represents the unchanged
    # OpenSSL default the verified path would use.
    default = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    default_names = {cipher["name"] for cipher in default.get_ciphers()}

    ctx_names = {cipher["name"] for cipher in ctx.get_ciphers()}

    # The lowered context must match the SECLEVEL=0 cipher list,
    # proving set_ciphers("DEFAULT@SECLEVEL=0") was applied, and must
    # differ from the untouched default cipher list.
    assert ctx_names == ref_names
    assert ctx_names != default_names


def test_ssl_verify_default_returns_none() -> None:
    """Verify ssl+verify_ssl=True returns None (default validation)."""
    c = AkuvoxHttpClient(host="192.168.1.100", use_ssl=True, verify_ssl=True)
    assert c._build_ssl_context() is None


def test_no_ssl_ignores_verify_flag() -> None:
    """Verify plain http returns None regardless of verify_ssl."""
    c = AkuvoxHttpClient(host="192.168.1.100", use_ssl=False, verify_ssl=False)
    assert c._build_ssl_context() is None


async def test_ssl_no_verify_connector_receives_context() -> None:
    """Verify __aenter__ passes SSLContext to connector."""
    c = AkuvoxHttpClient(host="192.168.1.100", use_ssl=True, verify_ssl=False)
    async with c:
        assert c._session is not None


async def test_negative_request_delay_raises_value_error() -> None:
    """Verify negative request_delay is rejected."""
    with pytest.raises(ValueError, match="request_delay must be non-negative"):
        AkuvoxHttpClient(host="192.168.1.100", request_delay=-1.0)


async def test_post_request_delay_calls_sleep() -> None:
    """Verify successful requests await the configured post-request delay."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5, request_delay=0.3)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE)
        async with client:
            await client.get("/api/system/info")
    mock_sleep.assert_awaited_once_with(0.3)


async def test_post_request_delay_skipped_when_zero() -> None:
    """Verify zero request_delay skips the post-request pause."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5, request_delay=0.0)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE)
        async with client:
            await client.get("/api/system/info")
    mock_sleep.assert_not_awaited()


async def test_default_delay_between_sequential_requests() -> None:
    """Verify the default request delay is applied to each successful request."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE, repeat=True)
        async with client:
            await client.get("/api/system/info")
            await client.get("/api/system/info")
    assert mock_sleep.await_args_list == [call(0.25), call(0.25)]


async def test_single_request_no_pre_request_delay() -> None:
    """Verify the delay occurs only after the request completes."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5)
    events: list[str] = []
    original_request = client._request

    async def instrumented_request(
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record request execution order around the wrapped call."""
        events.append("request-start")
        result = await original_request(method, path, data, params)
        events.append("request-end")
        return result

    def record_sleep(_: float) -> None:
        """Record the mocked post-request delay."""
        events.append("sleep")

    client._request = instrumented_request  # type: ignore[method-assign]

    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep",
            new=AsyncMock(side_effect=record_sleep),
        ),
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE)
        async with client:
            await client.get("/api/system/info")

    assert events == ["request-start", "request-end", "sleep"]


async def test_five_sequential_requests_each_delayed() -> None:
    """Verify each successful request in a batch applies the configured delay."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE, repeat=True)
        async with client:
            for _ in range(5):
                await client.get("/api/system/info")
    assert mock_sleep.await_count == 5


async def test_custom_delay_0_5_produces_matching_pause() -> None:
    """Verify custom request_delay values are awaited exactly."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5, request_delay=0.5)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE)
        async with client:
            await client.get("/api/system/info")
    mock_sleep.assert_awaited_once_with(0.5)


async def test_zero_delay_no_pause_backward_compatible() -> None:
    """Verify request_delay=0 preserves the previous no-delay behavior."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5, request_delay=0.0)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE)
        async with client:
            await client.get("/api/system/info")
    mock_sleep.assert_not_awaited()


async def test_no_delay_on_connection_error() -> None:
    """Verify failed requests do not await the post-request delay."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(
            f"{BASE_URL}/api/system/info",
            exception=aiohttp.ClientError("Connection refused"),
        )
        async with client:
            with pytest.raises(AkuvoxConnectionError):
                await client.get("/api/system/info")
    mock_sleep.assert_not_awaited()


async def test_delay_after_error_then_success() -> None:
    """Verify only successful requests apply the post-request delay."""
    client = AkuvoxHttpClient(host="192.168.1.100", timeout=5)
    with (
        aioresponses() as m,
        patch(
            "pylocal_akuvox._http.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        m.get(
            f"{BASE_URL}/api/system/error",
            exception=aiohttp.ClientError("Connection refused"),
        )
        m.get(f"{BASE_URL}/api/system/info", payload=SUCCESS_RESPONSE)
        async with client:
            with pytest.raises(AkuvoxConnectionError):
                await client.get("/api/system/error")
            await client.get("/api/system/info")
    mock_sleep.assert_awaited_once_with(0.25)
