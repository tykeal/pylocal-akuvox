# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for HTTP client wrapper and response envelope parsing."""

import asyncio
import json
from typing import Any

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


@pytest.fixture
def client() -> AkuvoxHttpClient:
    """Create test HTTP client."""
    return AkuvoxHttpClient(host="192.168.1.100", timeout=5)


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
        m.post(f"{BASE_URL}/api/user/add", payload=response)
        async with client:
            result = await client.post("/api/user/add", data={})
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


async def test_post_sends_text_plain(client: AkuvoxHttpClient) -> None:
    """Verify POST sends JSON encoded as text/plain content type."""
    response = {
        "retcode": 0,
        "action": "addUser",
        "message": "Success",
        "data": {},
    }
    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/user/add", payload=response)
        async with client:
            await client.post("/api/user/add", data={"Name": "Test"})

        call = m.requests[("POST", aiohttp.client.URL(f"{BASE_URL}/api/user/add"))][0]
        body = call.kwargs.get("data", "")
        parsed = json.loads(body)
        assert parsed == {"Name": "Test"}


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
