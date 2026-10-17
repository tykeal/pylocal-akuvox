# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report device instrumentation and capability probe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pylocal_akuvox._diagnostic_redaction import _decode_json_body
from pylocal_akuvox._report_steps import (
    _default_emit,
    print_header,
)
from pylocal_akuvox.device import AkuvoxDevice
from pylocal_akuvox.exceptions import AkuvoxParseError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import aiohttp

    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._diagnostic_report import DiagnosticReport


def _install_probed_capabilities(  # pragma: no cover
    device: AkuvoxDevice, profile: DeviceCapabilities
) -> None:
    """Override ``device._capabilities`` with the supplied probe-merged profile.

    The :meth:`AkuvoxDevice.__aenter__` boundary populates
    ``_capabilities`` from the static matrix only. After
    :func:`_probe_device_capabilities` has captured a probe-merged
    profile for the whole script run (Decision 9), this helper
    installs the same profile onto every subsequent connection so
    the wrapper-level per-method capability gate and :func:`step`'s
    gating use the same source of truth — otherwise a
    probe-discovered ``SUPPORTED`` capability could pass
    :func:`step` and then be rejected by the wrapper layer's
    matrix-derived gate (or vice versa for ``UNSUPPORTED``).
    """
    device._capabilities = profile  # noqa: SLF001 - probe-vs-matrix layer parity


def create_device(  # pragma: no cover
    device_kwargs: dict[str, Any],
    diagnostics: DiagnosticReport,
) -> AkuvoxDevice:
    """Create an AkuvoxDevice instrumented for diagnostic capture."""
    device = AkuvoxDevice(**device_kwargs)
    _instrument_device(device, diagnostics)
    return device


def _instrument_device(
    device: AkuvoxDevice, diagnostics: DiagnosticReport
) -> None:  # pragma: no cover  # noqa: E501
    """Attach diagnostic HTTP capture hooks to a device instance."""
    http = device._http  # noqa: SLF001 - example diagnostics need raw exchanges.
    original_request = http._request  # noqa: SLF001
    original_request_raw = http._request_raw  # noqa: SLF001
    original_handle_response = http._handle_response  # noqa: SLF001

    async def diagnostic_request(
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Capture request metadata before delegating to the HTTP client."""
        endpoint = path if path.startswith("/") else f"/{path}"
        diagnostics.begin_http_event(
            method=method,
            endpoint=endpoint,
            data=data,
            params=params,
        )
        try:
            return await original_request(
                method, path, data=data, params=params, timeout=timeout
            )
        except Exception as exc:
            diagnostics.record_exception(exc)
            raise

    http._request = diagnostic_request  # type: ignore[method-assign]  # noqa: SLF001

    async def diagnostic_request_raw(
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float | None = None,
        allow_redirects: bool = True,
    ) -> tuple[int, str]:
        """Capture raw request metadata before delegating to the HTTP client."""
        endpoint = path if path.startswith("/") else f"/{path}"
        diagnostics.begin_http_event(
            method=method,
            endpoint=endpoint,
            data=data,
            params=params,
        )
        try:
            status, body_text = await original_request_raw(
                method,
                path,
                params=params,
                data=data,
                timeout=timeout,
                allow_redirects=allow_redirects,
            )
        except Exception as exc:
            diagnostics.record_exception(exc)
            raise
        body, _json_error = _decode_json_body(body_text)
        diagnostics.record_http_response(
            status=status,
            body_text=body_text,
            body=body,
            retcode=None,
            retmsg=None,
            data={},
        )
        return status, body_text

    http._request_raw = diagnostic_request_raw  # type: ignore[method-assign]  # noqa: SLF001
    http._handle_response = _build_diagnostic_response_handler(  # type: ignore[assignment,method-assign]  # noqa: SLF001
        diagnostics,
        original_handle_response,
    )


def _build_diagnostic_response_handler(  # pragma: no cover
    diagnostics: DiagnosticReport,
    original_handle_response: Callable[
        [aiohttp.ClientResponse],
        Awaitable[dict[str, Any]],
    ],
) -> Callable[[aiohttp.ClientResponse], Awaitable[dict[str, Any]]]:
    """Build a response parser that records the raw failure shape."""

    async def diagnostic_handle_response(
        resp: aiohttp.ClientResponse,
    ) -> dict[str, Any]:
        """Capture response shape before applying library error mapping."""
        body_text = await resp.text()
        body, json_error = _decode_json_body(body_text)
        retcode: int | None = None
        retmsg: str | None = None
        data: dict[str, Any] = {}
        parse_error: AkuvoxParseError | None = None
        if json_error is None:
            try:
                retcode, retmsg, data = _parse_response_shape(
                    body,
                    tolerate_missing_envelope=resp.status >= 400,
                )
            except AkuvoxParseError as exc:
                parse_error = exc
        diagnostics.record_http_response(
            status=resp.status,
            body_text=body_text,
            body=body,
            retcode=retcode,
            retmsg=retmsg,
            data=data,
        )
        if json_error is not None and resp.status < 400:
            msg = "Invalid JSON response"
            raise AkuvoxParseError(msg) from json_error
        if parse_error is not None:
            raise parse_error
        if (
            resp.status < 400
            and retcode is not None
            and retcode >= 0
            and (retmsg is None or "api unsupported" not in retmsg.casefold())
        ):
            return data
        return await original_handle_response(resp)

    return diagnostic_handle_response


def _parse_response_shape(  # pragma: no cover
    body: object | None,
    *,
    tolerate_missing_envelope: bool,
) -> tuple[int | None, str | None, dict[str, Any]]:
    """Parse response envelope or tolerate HTTP error bodies."""
    if tolerate_missing_envelope and (
        not isinstance(body, dict) or "retcode" not in body
    ):
        return None, None, {}
    return _parse_diagnostic_envelope(body)


def _parse_diagnostic_envelope(  # pragma: no cover
    body: object | None,
) -> tuple[int | None, str | None, dict[str, Any]]:
    """Parse an Akuvox response envelope for diagnostics."""
    if body is None:
        return None, None, {}
    if not isinstance(body, dict) or "retcode" not in body:
        msg = _missing_envelope_message(body)
        raise AkuvoxParseError(msg)

    retcode = body["retcode"]
    if not isinstance(retcode, int):
        msg = f"Expected retcode to be int, got {type(retcode).__name__}"
        raise AkuvoxParseError(msg)

    retmsg = _extract_retmsg(body)
    data = body.get("data", {})
    result: dict[str, Any] = data if isinstance(data, dict) else {}
    return retcode, retmsg, result


def _missing_envelope_message(body: object) -> str:  # pragma: no cover
    """Return a parse error message that exposes schema keys, not values."""
    if isinstance(body, dict):
        keys = sorted(str(key) for key in body)
        return f"Missing envelope field 'retcode'; keys={keys}"
    return f"Missing envelope fields in {type(body).__name__} response"


def _extract_retmsg(body: dict[str, Any]) -> str:  # pragma: no cover
    """Return the device message field, preserving firmware spelling."""
    message = body.get("retmsg", body.get("message", ""))
    if isinstance(message, str):
        return message
    return str(message) if message is not None else ""


async def _probe_device_capabilities(  # pragma: no cover
    device_kwargs: dict[str, Any], diagnostics: DiagnosticReport
) -> DeviceCapabilities:
    """Open a short-lived connection, probe once, and return the profile.

    The probe is the **only** capability discovery the script performs
    (FR-019 / Decision 9). Subsequent connections opened by
    :func:`_run_write_tests` and :func:`_run_read_tests` reuse the
    profile captured here rather than re-probing on every context entry.
    """
    print_header("CAPABILITY PROBE")
    async with create_device(device_kwargs, diagnostics) as device:
        capabilities = await device.probe_capabilities()
    supported = len(capabilities.supported_set)
    _default_emit(
        f"  Device class: {capabilities.device_class} "
        f"(firmware {capabilities.firmware_version})"
    )
    _default_emit(f"  Supported capabilities: {supported}")
    return capabilities
