# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for relay operations: trigger and status retrieval."""

from __future__ import annotations

import logging
import re
from unittest.mock import patch
from urllib.parse import unquote

import aiohttp
import pytest
from aioresponses import aioresponses

from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox._http import AkuvoxHttpClient
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxRequestError,
    AkuvoxValidationError,
)
from pylocal_akuvox.relay import open_door_http
from tests.unit._helpers import register_default_info

BASE_URL = "http://192.168.1.100"
_OPEN_DOOR_URL_RE = re.compile(rf"{re.escape(BASE_URL)}/fcgi/do.*")

_TRIG_OK_RESPONSE = {
    "retcode": 1,
    "action": "trigRelay",
    "message": "OK",
    "data": {},
}

_STATUS_RESPONSE = {
    "retcode": 0,
    "action": "get",
    "message": "",
    "data": {
        "RelayA": "open",
        "RelayB": "closed",
    },
}


async def test_trigger_relay_posts_to_correct_endpoint() -> None:
    """Verify trigger_relay POSTs to /api/relay/trig."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "relay"
        assert body["action"] == "trig"
        assert body["data"]["num"] == 1


async def test_trigger_relay_with_all_params() -> None:
    """Verify trigger_relay sends num, mode, level, delay."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=2, mode=1, level=1, delay=5)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["target"] == "relay"
        assert body["action"] == "trig"
        assert body["data"] == {"num": 2, "mode": 1, "level": 1, "delay": 5}


async def test_trigger_relay_defaults() -> None:
    """Verify trigger_relay defaults: mode=0, level=0, delay=0."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["data"] == {"num": 1, "mode": 0, "level": 0, "delay": 0}


async def test_trigger_relay_invalid_num_zero() -> None:
    """Verify relay num 0 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Relay number must be"):
                await device.trigger_relay(num=0)


async def test_trigger_relay_invalid_num_negative() -> None:
    """Verify negative relay num raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Relay number must be"):
                await device.trigger_relay(num=-1)


async def test_trigger_relay_invalid_delay_negative() -> None:
    """Verify negative delay raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Delay must be"):
                await device.trigger_relay(num=1, delay=-1)


async def test_trigger_relay_invalid_delay_too_large() -> None:
    """Verify delay > 65535 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Delay must be"):
                await device.trigger_relay(num=1, delay=65536)


async def test_trigger_relay_invalid_mode() -> None:
    """Verify mode not 0 or 1 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Mode must be"):
                await device.trigger_relay(num=1, mode=2)


async def test_trigger_relay_invalid_mode_negative() -> None:
    """Verify negative mode raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Mode must be"):
                await device.trigger_relay(num=1, mode=-1)


async def test_trigger_relay_invalid_level() -> None:
    """Verify level not 0 or 1 raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Level must be"):
                await device.trigger_relay(num=1, level=2)


async def test_trigger_relay_invalid_level_negative() -> None:
    """Verify negative level raises AkuvoxValidationError."""
    with aioresponses() as m:
        register_default_info(m)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxValidationError, match="Level must be"):
                await device.trigger_relay(num=1, level=-1)


async def test_trigger_relay_max_delay_valid() -> None:
    """Verify delay=65535 (max) is accepted."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.trigger_relay(num=1, delay=65535)

        url_key = (
            "POST",
            aiohttp.client.URL(f"{BASE_URL}/api/relay/trig"),
        )
        call = m.requests[url_key][0]
        body = call.kwargs.get("json")
        assert body["data"]["delay"] == 65535


async def test_trigger_relay_device_error() -> None:
    """Verify device error (retcode < 0) raises AkuvoxDeviceError."""
    error_response = {
        "retcode": -1,
        "action": "trigRelay",
        "message": "Failed",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.post(f"{BASE_URL}/api/relay/trig", payload=error_response)
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxDeviceError, match="Failed"):
                await device.trigger_relay(num=1)


async def test_trigger_relay_connection_error() -> None:
    """Verify connection failure raises AkuvoxConnectionError."""
    with aioresponses() as m:
        register_default_info(m)
        m.post(
            f"{BASE_URL}/api/relay/trig",
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxDevice("192.168.1.100") as device:
            with pytest.raises(AkuvoxConnectionError):
                await device.trigger_relay(num=1)


async def test_get_relay_status_gets_correct_endpoint() -> None:
    """Verify get_relay_status GETs /api/relay/status."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/relay/status", payload=_STATUS_RESPONSE)
        async with AkuvoxDevice("192.168.1.100") as device:
            result = await device.get_relay_status()

    assert result == {"RelayA": "open", "RelayB": "closed"}


async def test_get_relay_status_empty_data() -> None:
    """Verify get_relay_status returns empty dict when no data."""
    response = {
        "retcode": 0,
        "action": "get",
        "message": "",
        "data": {},
    }
    with aioresponses() as m:
        register_default_info(m)
        m.get(f"{BASE_URL}/api/relay/status", payload=response)
        async with AkuvoxDevice("192.168.1.100") as device:
            result = await device.get_relay_status()

    assert result == {}


# --- Free-function coverage (relay.trigger_relay) ----------------------------
#
# Service-module free functions remain capability-unaware (Phase 2 contract).
# AkuvoxDevice.trigger_relay routes through the adapter registry, but the
# legacy free function is kept as a public entry point for advanced users
# who want a capability-unaware call. The tests below exercise it directly.


async def test_free_function_trigger_relay_posts_correctly() -> None:
    """Direct call to relay.trigger_relay free function."""
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.relay import trigger_relay

    with aioresponses() as m:
        m.post(f"{BASE_URL}/api/relay/trig", payload=_TRIG_OK_RESPONSE)
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await trigger_relay(http, num=3, mode=1, level=1, delay=10)

        # Verify the request was made to /api/relay/trig
        post_calls = [(k, v) for k, v in m.requests.items() if k[0] == "POST"]
        assert len(post_calls) == 1
        key, calls = post_calls[0]
        assert str(key[1]).endswith("/api/relay/trig")
        body = calls[0].kwargs["json"]
        assert body["target"] == "relay"
        assert body["action"] == "trig"
        assert body["data"] == {"num": 3, "mode": 1, "level": 1, "delay": 10}


async def test_free_function_trigger_relay_validates_args() -> None:
    """Free-function trigger_relay shares validation with adapter path."""
    from pylocal_akuvox._http import AkuvoxHttpClient
    from pylocal_akuvox.relay import trigger_relay

    async with AkuvoxHttpClient(host="192.168.1.100") as http:
        with pytest.raises(AkuvoxValidationError):
            await trigger_relay(http, num=0)
        with pytest.raises(AkuvoxValidationError):
            await trigger_relay(http, num=True)  # bool subclass rejected


def _only_open_door_request_url(
    mocked: aioresponses,
) -> aiohttp.client.URL:
    """Return the single recorded OpenDoor request URL."""
    get_requests = [key for key in mocked.requests if key[0] == "GET"]
    assert len(get_requests) == 1
    return get_requests[0][1]


async def test_open_door_http_issues_credentialed_fcgi_request() -> None:
    """OpenDoor HTTP success uses the credentialed raw FCGI endpoint."""
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body="OK")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(
                http,
                user="relay-user",
                password="relay-pass",
                door_num=2,
            )

        url = _only_open_door_request_url(m)
        assert url.path == "/fcgi/do"
        assert url.query["action"] == "OpenDoor"
        assert url.query["UserName"] == "relay-user"
        assert url.query["Password"] == "relay-pass"
        assert url.query["DoorNum"] == "2"
        assert "relay" not in url.query


async def test_open_door_http_defaults_to_door_one() -> None:
    """Omitting ``door_num`` defaults the OpenDoor request to door one."""
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=204, body="")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(http, user="relay-user", password="relay-pass")

        url = _only_open_door_request_url(m)
        assert url.query["DoorNum"] == "1"


async def test_open_door_http_accepts_body_result_zero() -> None:
    """HTTP 200 plus body ``hcSingleResult=0`` reports OpenDoor success."""
    body = """
    <form name='hiddenValForm_Div'>
    <input id=hcSingleResult type=hidden value='0'>
    </form>
    """
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body=body, content_type="text/html")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(http, user="relay-user", password="relay-pass")


async def test_open_door_http_classifies_body_auth_failure() -> None:
    """HTTP 200 plus ``hcSingleResult=-1`` is a relay credential failure."""
    body = """
    <form name='hiddenValForm_Div'>
    <input id=hcSingleResult type=hidden value='-1'>
    </form>
    """
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body=body, content_type="text/html")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxAuthenticationError) as exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                )

    message = str(exc_info.value)
    assert "hcSingleResult=-1" in message
    assert "Open Relay Via HTTP username/password" in message


async def test_open_door_http_classifies_body_device_failure() -> None:
    """HTTP 200 plus another non-zero body result is a device failure."""
    body = "<input id=hcSingleResult type=hidden value='-2'>"
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body=body, content_type="text/html")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxDeviceError, match="hcSingleResult=-2"):
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                )


async def test_open_door_http_accepts_missing_body_marker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTTP 200 without the IT83 body marker preserves legacy success."""
    caplog.set_level(logging.DEBUG, logger="pylocal_akuvox.relay")
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body="OK", content_type="text/html")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(http, user="relay-user", password="relay-pass")

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "lacked a recognizable hcSingleResult marker" in messages


@pytest.mark.parametrize(
    "body",
    [
        '<INPUT VALUE="0" TYPE=hidden ID=hcSingleResult>',
        "<input value=' 0 ' type=hidden id=' hcSingleResult '>",
        '<input id = "hcSingleResult" type=hidden value = "0" >',
    ],
)
async def test_open_door_http_parses_body_marker_variations(body: str) -> None:
    """OpenDoor result parsing tolerates case, spacing, quotes, and order."""
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body=body, content_type="text/html")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(http, user="relay-user", password="relay-pass")


async def test_open_door_http_redacts_password_from_body_result_error() -> None:
    """Body-based OpenDoor errors redact echoed passwords."""
    password = "do not/log"
    body = (
        "<input id=hcSingleResult type=hidden value='-1'> "
        f"echoed UserName=relay-user&Password={password} do+not%2Flog"
    )
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body=body, content_type="text/html")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxAuthenticationError) as exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password=password,
                )

    message = str(exc_info.value)
    assert "<redacted>" in message
    assert "relay-user" not in message
    assert password not in message
    assert "do+not%2Flog" not in message


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (401, AkuvoxAuthenticationError),
        (403, AkuvoxRequestError),
        (404, AkuvoxRequestError),
        (500, AkuvoxDeviceError),
        (302, AkuvoxDeviceError),
    ],
)
async def test_open_door_http_classifies_http_status(
    status: int,
    exc_type: type[Exception],
) -> None:
    """OpenDoor HTTP maps raw HTTP statuses without parsing the body as JSON."""
    with aioresponses() as m:
        m.get(
            _OPEN_DOOR_URL_RE,
            status=status,
            body="<html>not json</html>",
            content_type="text/html",
        )
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(exc_type) as exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                )

        assert "<html>not json</html>" in str(exc_info.value)
        assert "relay-pass" not in str(exc_info.value)


async def test_open_door_http_surfaces_transport_error() -> None:
    """OpenDoor HTTP lets transport failures surface as connection errors."""
    with aioresponses() as m:
        m.get(
            _OPEN_DOOR_URL_RE,
            exception=aiohttp.ClientConnectionError("refused"),
        )
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxConnectionError):
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                )


@pytest.mark.parametrize("door_num", [0, -1, "1", 1.0, True, False])
async def test_open_door_http_validates_door_num_before_request(
    door_num: object,
) -> None:
    """Invalid OpenDoor door numbers fail locally without issuing a request."""
    with aioresponses() as m:
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxValidationError, match="Door number"):
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                    door_num=door_num,  # type: ignore[arg-type]
                )

        assert not m.requests


async def test_open_door_http_encodes_credentials_once() -> None:
    """Special characters in OpenDoor credentials cannot split the query."""
    password = "p@ss+ &word=1 é"
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body="OK")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(
                http,
                user="a b",
                password=password,
                door_num=3,
            )

            url = _only_open_door_request_url(m)
            assert url.query["UserName"] == "a b"
            assert unquote(url.query["Password"]) == password
            assert url.query["DoorNum"] == "3"
            assert "word" not in url.query


async def test_open_door_http_disables_redirect_following() -> None:
    """OpenDoor HTTP classifies the original response instead of redirects."""
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body="OK")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            assert http._session is not None
            with patch.object(
                http._session, "request", wraps=http._session.request
            ) as spy:
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                )
            assert spy.call_args.kwargs["allow_redirects"] is False


async def test_open_door_http_redacts_password_from_logs_and_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """OpenDoor HTTP logs never include the clear-text relay password."""
    caplog.set_level(logging.DEBUG, logger="pylocal_akuvox.relay")
    password = "do not/log"
    with aioresponses() as m:
        m.get(_OPEN_DOOR_URL_RE, status=200, body="OK")
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            await open_door_http(
                http,
                user="relay-user",
                password=password,
                door_num=1,
            )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "OpenDoor" in messages
    assert "relay-user" in messages
    assert "DoorNum" in messages
    assert "<redacted>" in messages
    assert password not in messages

    caplog.clear()
    with aioresponses() as m:
        m.get(
            _OPEN_DOOR_URL_RE,
            status=403,
            body=f"forbidden UserName=relay-user&Password={password} do+not%2Flog",
            content_type="text/plain",
        )
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxRequestError) as exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password=password,
                )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert password not in messages
    assert password not in str(exc_info.value)
    assert "relay-user" not in str(exc_info.value)
    assert "do+not%2Flog" not in str(exc_info.value)

    with aioresponses() as m:
        m.get(
            _OPEN_DOOR_URL_RE,
            status=403,
            body="forbidden do+not%2flog",
            content_type="text/plain",
        )
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxRequestError) as lower_exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password=password,
                )

    assert "do+not%2flog" not in str(lower_exc_info.value)


async def test_open_door_http_redacts_before_clipping_error_body() -> None:
    """A password crossing the excerpt boundary is redacted before clipping."""
    password = "zzzzzzzzzz-unique-open-door-secret"
    with aioresponses() as m:
        m.get(
            _OPEN_DOOR_URL_RE,
            status=403,
            body=f"{'x' * 195}{password}",
            content_type="text/plain",
        )
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxRequestError) as exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password=password,
                )

    assert password not in str(exc_info.value)
    assert password[:8] not in str(exc_info.value)


async def test_open_door_http_error_body_excerpt_is_bounded_single_line() -> None:
    """Escaped body excerpts remain bounded and single-line."""
    with aioresponses() as m:
        m.get(
            _OPEN_DOOR_URL_RE,
            status=500,
            body="\\" * 250 + "\ntrailing",
            content_type="text/plain",
        )
        async with AkuvoxHttpClient(host="192.168.1.100") as http:
            with pytest.raises(AkuvoxDeviceError) as exc_info:
                await open_door_http(
                    http,
                    user="relay-user",
                    password="relay-pass",
                )

    body_excerpt = str(exc_info.value).split("body=", maxsplit=1)[1]
    assert len(body_excerpt) == 200
    assert "\n" not in body_excerpt


async def test_device_open_door_http_is_not_capability_gated() -> None:
    """Device OpenDoor passthrough works without a capability probe."""
    with aioresponses() as m:
        register_default_info(m)
        m.get(_OPEN_DOOR_URL_RE, status=200, body="OK")
        async with AkuvoxDevice("192.168.1.100") as device:
            await device.open_door_http(
                user="relay-user",
                password="relay-pass",
            )

        get_urls = [key[1] for key in m.requests if key[0] == "GET"]
        open_door_urls = [url for url in get_urls if url.path == "/fcgi/do"]
        assert len(open_door_urls) == 1
        assert open_door_urls[0].query["DoorNum"] == "1"
