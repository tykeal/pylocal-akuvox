# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Public capability report API orchestration."""

from __future__ import annotations

import contextlib
import io
import sys
from typing import TYPE_CHECKING, TextIO

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
from pylocal_akuvox._diagnostic_report import DiagnosticReport
from pylocal_akuvox._report_steps import (
    TestResults,
    _default_emit,
    _probe_device_capabilities,
    _run_read_tests,
    _run_write_tests,
    create_device,
    print_header,
    skip_step,
    test_validation,
)
from pylocal_akuvox.auth import AuthMethod

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from pylocal_akuvox.device import AkuvoxDevice


class _EmitWriter(io.TextIOBase):  # pragma: no cover
    """File-like adapter that forwards complete lines to an emitter."""

    def __init__(
        self,
        emit: Callable[[str], None],
        *,
        stdout: TextIO,
        stderr: TextIO,
    ) -> None:
        """Initialize the writer with the target line emitter."""
        self._emit = emit
        self._stdout = stdout
        self._stderr = stderr
        self._pending = ""

    def writable(self) -> bool:
        """Return whether this stream accepts writes."""
        return True

    def write(self, text: str) -> int:
        """Forward written text to the emitter one line at a time."""
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._emit_line(line)
        return len(text)

    def flush(self) -> None:
        """Emit any buffered partial line."""
        if self._pending:
            self._emit_line(self._pending)
            self._pending = ""

    def _emit_line(self, line: str) -> None:
        """Call the emitter without recursing through redirected stdio."""
        stdout = sys.stdout
        stderr = sys.stderr
        try:
            sys.stdout = self._stdout
            sys.stderr = self._stderr
            self._emit(line)
        finally:
            sys.stdout = stdout
            sys.stderr = stderr


class _DiscardWriter(io.TextIOBase):  # pragma: no cover
    """File-like sink that discards all writes without buffering."""

    def writable(self) -> bool:
        """Return whether this stream accepts writes."""
        return True

    def write(self, text: str) -> int:
        """Discard written text."""
        return len(text)


@contextlib.contextmanager
def _stdout_context(  # pragma: no cover
    emit: Callable[[str], None] | None,
) -> Iterator[None]:
    """Route legacy step stdout through the requested report emitter."""
    if emit is print:
        yield
        return
    if emit is None:
        sink = _DiscardWriter()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            yield
        return
    writer = _EmitWriter(emit, stdout=sys.stdout, stderr=sys.stderr)
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        try:
            yield
        finally:
            writer.flush()


async def run_capability_report(
    device: AkuvoxDevice,
    *,
    write: bool = False,
    open_door: bool = False,
    open_door_user: str | None = None,
    open_door_password: str | None = None,
    timeout: float | None = None,
    redact_stdout: bool = False,
    emit: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Run the redacted capability report using a device connection template.

    Custom emitters and silent mode redirect process-wide stdout/stderr while
    the report runs; avoid concurrent stdout/stderr writers during a run.
    """
    with _stdout_context(emit):
        return await _run_capability_report(
            device,
            write=write,
            open_door=open_door,
            open_door_user=open_door_user,
            open_door_password=open_door_password,
            timeout=timeout,
            redact_stdout=redact_stdout,
        )


# aislop-ignore-next-line complexity/too-many-params -- public kwargs mirror CLI flags
async def _run_capability_report(
    device: AkuvoxDevice,
    *,
    write: bool,
    open_door: bool,
    open_door_user: str | None,
    open_door_password: str | None,
    timeout: float | None,
    redact_stdout: bool,
) -> dict[str, object]:
    """Assemble probe, optional writes, read tests, and summary output."""
    device_kwargs = device._connection_spec()  # noqa: SLF001
    if timeout is not None:
        device_kwargs["timeout"] = timeout
    diagnostics = DiagnosticReport(
        host=str(device_kwargs["host"]),
        auth_method=_auth_method(device_kwargs.get("auth")),
        use_ssl=bool(device_kwargs["use_ssl"]),
        verify_ssl=bool(device_kwargs["verify_ssl"]),
    )
    results = TestResults(diagnostics)

    await test_validation()
    capabilities = await _probe_device_capabilities(device_kwargs, diagnostics)
    if device.attempt_unknown_capability:
        capabilities = _allow_unknown_capabilities(capabilities)
    if write:
        write_capabilities = _with_report_write_alias_fallback(capabilities)
        await _run_write_tests(
            device_kwargs,
            results,
            capabilities=write_capabilities,
            open_door=open_door,
            open_door_user=open_door_user,
            open_door_password=open_door_password,
            redact_stdout=redact_stdout,
        )

    async with create_device(device_kwargs, diagnostics) as read_device:
        await _run_read_tests(
            read_device,
            results,
            capabilities=capabilities,
            redact_stdout=redact_stdout,
        )
        if not write:
            if open_door:
                skip_step(
                    results,
                    "open_door_http",
                    "requires write=True to run OpenDoor HTTP",
                )
            print_header("SKIPPING WRITE TESTS")
            _default_emit("  Use --write to test:")
            _default_emit("    - add/modify/delete user")
            _default_emit("    - add/modify/delete schedule")
            _default_emit("    - trigger relay (device-side default close timer)")
            _default_emit("    - open_door_http with --open-door and relay credentials")
            _default_emit("  ⚠ Write tests WILL create and delete test data")

    print_header("ALL TESTS COMPLETE ✓")
    results.print_summary()
    return diagnostics.to_json()


def _with_report_write_alias_fallback(
    capabilities: DeviceCapabilities,
) -> DeviceCapabilities:
    """Backfill diagnostic user-write aliases without changing statuses."""
    aliases = capabilities.field_aliases.get("schedule_relay")
    if aliases is None:
        return capabilities
    if aliases.write:
        return capabilities

    field_aliases = dict(capabilities.field_aliases)
    field_aliases["schedule_relay"] = FieldAliases(
        read=aliases.read,
        write=DEFAULT_USER_FIELD_ALIASES.write,
    )
    return DeviceCapabilities(
        device_class=capabilities.device_class,
        firmware_version=capabilities.firmware_version,
        capabilities=capabilities.capabilities,
        field_aliases=field_aliases,
        schema_shapes=capabilities.schema_shapes,
        notes=capabilities.notes,
        provenance=capabilities.provenance,
    )


def _auth_method(auth: object) -> str:  # pragma: no cover
    """Return the frozen report auth method string for a connection."""
    if auth is None:
        return AuthMethod.NONE.value
    method = getattr(auth, "method", AuthMethod.NONE)
    if method is AuthMethod.ALLOWLIST:
        return AuthMethod.NONE.value
    if isinstance(method, AuthMethod):
        return method.value
    return str(method)


def _allow_unknown_capabilities(  # pragma: no cover
    capabilities: DeviceCapabilities,
) -> DeviceCapabilities:
    """Return a profile where UNKNOWN capabilities are allowed to run."""
    effective = {
        capability: capabilities.status_of(capability) for capability in Capability
    }
    for capability, status in effective.items():
        if status is CapabilityStatus.UNKNOWN:
            effective[capability] = CapabilityStatus.SUPPORTED
    return DeviceCapabilities(
        device_class=capabilities.device_class,
        firmware_version=capabilities.firmware_version,
        capabilities=effective,
        field_aliases=capabilities.field_aliases,
        schema_shapes=capabilities.schema_shapes,
        notes=capabilities.notes,
        provenance=capabilities.provenance,
    )
