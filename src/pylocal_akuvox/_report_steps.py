# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability report diagnostic step framework."""

from __future__ import annotations

import asyncio
import sys
import traceback
from typing import TYPE_CHECKING

from pylocal_akuvox._capability_types import Capability, CapabilityStatus
from pylocal_akuvox._diagnostic_redaction import _first_line
from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
    AkuvoxUnsupportedError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pylocal_akuvox._capability_profile import DeviceCapabilities
    from pylocal_akuvox._diagnostic_report import DiagnosticReport

SEPARATOR = "-" * 60


def _default_emit(message: str) -> None:  # pragma: no cover
    """Emit one diagnostic line to stdout."""
    sys.stdout.write(f"{message}\n")


class TestStepFailed(Exception):  # pragma: no cover
    """Expected diagnostic step failure that does not need a traceback."""


class TestStepSkipped(Exception):  # pragma: no cover
    """Diagnostic step skip with a reason for the summary."""


class TestResults:
    """Collect diagnostic test outcomes for the final summary."""

    def __init__(self, diagnostics: DiagnosticReport | None = None) -> None:
        """Initialize empty result buckets."""
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.skipped: list[tuple[str, str]] = []
        self.diagnostics = diagnostics

    @property
    def total(self) -> int:
        """Return the total number of recorded test steps."""
        return len(self.passed) + len(self.failed) + len(self.skipped)

    def mark_passed(self, label: str) -> None:
        """Record a passed test step."""
        self.passed.append(label)

    def mark_failed(self, label: str, reason: str) -> None:
        """Record a failed test step with its reason."""
        self.failed.append((label, reason))

    def mark_skipped(self, label: str, reason: str) -> None:
        """Record a skipped test step with its reason."""
        self.skipped.append((label, reason))

    def was_passed(self, label: str) -> bool:
        """Return whether a test step passed."""
        return label in self.passed

    def print_summary(self) -> None:
        """Print a summary of all recorded diagnostic test steps."""
        _default_emit(f"\n{'=' * 60}")
        _default_emit("  SUMMARY")
        _default_emit("=" * 60)
        _default_emit(f"  Total:    {self.total:3}")
        _default_emit(f"  ✓ Passed: {len(self.passed):3}")
        _default_emit(f"  ✗ Failed: {len(self.failed):3}")
        _default_emit(f"  ⊘ Skipped:{len(self.skipped):3}")

        _print_summary_section("Passed", [(label, "") for label in self.passed])
        _print_summary_section("Failures", self.failed)
        _print_summary_section("Skipped", self.skipped)
        if self.diagnostics is not None:
            self.diagnostics.print_capability_matrix_data()


def _print_summary_section(  # pragma: no cover
    title: str,
    entries: list[tuple[str, str]],
) -> None:
    """Print one section of the diagnostic summary."""
    if not entries:
        return

    _default_emit(f"\n  {title}:")
    for label, reason in entries:
        suffix = f": {reason}" if reason else ""
        _default_emit(f"    - {label}{suffix}")


def skip_step(
    results: TestResults, label: str, reason: str
) -> None:  # pragma: no cover  # noqa: E501
    """Record and print a skipped diagnostic step."""
    results.mark_skipped(label, reason)
    if results.diagnostics is not None:
        results.diagnostics.begin_test(label)
        results.diagnostics.finish_test("skipped", reason)
    _default_emit(f"  ⊘ {label} skipped: {reason}")


def _effective_status(  # pragma: no cover
    capabilities: DeviceCapabilities,
    *caps: Capability,
) -> CapabilityStatus:
    """Return the best-of-N capability status across ``*caps``.

    Used by :func:`step` to gate operations whose backend has multiple
    transport variants (today only relay trigger has both
    ``RELAY_TRIGGER_API`` and ``RELAY_TRIGGER_FCGI``). The rule is:

    * Any ``SUPPORTED`` wins — at least one variant works on this
      device class, so :meth:`AkuvoxDevice.trigger_relay` will dispatch
      successfully.
    * All ``UNSUPPORTED`` → ``UNSUPPORTED`` — every variant has been
      confirmed-negative; the gate fails fast.
    * Otherwise → ``UNKNOWN`` — at least one variant has been observed
      ``UNKNOWN``; the gate suggests the integrator opt in.
    """
    statuses = [capabilities.status_of(cap) for cap in caps]
    if any(status is CapabilityStatus.SUPPORTED for status in statuses):
        return CapabilityStatus.SUPPORTED
    if all(status is CapabilityStatus.UNSUPPORTED for status in statuses):
        return CapabilityStatus.UNSUPPORTED
    return CapabilityStatus.UNKNOWN


def _record_capability_skip(
    results: TestResults, name: str, reason: str
) -> None:  # pragma: no cover  # noqa: E501
    """Record + print a capability-gate skip in the ``SKIP: <name>:`` style."""
    if results.diagnostics is not None:
        results.diagnostics.begin_test(name)
        results.diagnostics.finish_test("skipped", reason)
    results.mark_skipped(name, reason)
    _default_emit(f"  SKIP: {name}: {reason}")


async def step[T](  # pragma: no cover
    *,
    results: TestResults,
    name: str,
    capability: Capability | tuple[Capability, ...],
    capabilities: DeviceCapabilities,
    coro_factory: Callable[[], Awaitable[T]],
) -> T | None:
    """Capability-gate one diagnostic step (Phase 4, FR-019).

    Per ``specs/008-capability-matrix/research.md`` Decision 9, this
    consults the supplied :class:`DeviceCapabilities` profile and:

    * ``UNSUPPORTED`` → print ``SKIP: <name>: not supported on this
      device class (<device_class>)`` and return ``None``.
    * ``UNKNOWN`` → print ``SKIP: <name>: status unknown on this
      device class (<device_class>); add a matrix entry or set
      device.attempt_unknown_capability=True to opt in`` and return
      ``None``.
    * ``SUPPORTED`` → call ``coro_factory()`` and run the resulting
      coroutine. On success print ``OK:   <name>`` and return the
      result. On a runtime :class:`AkuvoxUnsupportedError` (rare
      matrix-vs-actual mismatch — the device emitted "unsupported
      action" even though the matrix marked the capability
      ``SUPPORTED``) the failure is re-mapped to ``SKIP: <name>:
      <message> (reason=<reason>)``.

    ``capability`` may be a single :class:`Capability` or a tuple of
    them; the tuple form uses :func:`_effective_status` to gate on
    the best-of-N status (used today only by
    :meth:`AkuvoxDevice.trigger_relay` which has both API and FCGI
    variants).

    Connection / authentication errors propagate unchanged (the
    integrator wants the script to abort, not skip past a
    "device unreachable" event). ``TestStepSkipped`` / generic
    failures fall through to the same FAIL handling as
    :func:`run_step` for parity with the legacy code path.
    """
    if isinstance(capability, tuple):
        status = _effective_status(capabilities, *capability)
    else:
        status = capabilities.status_of(capability)

    if status is CapabilityStatus.UNSUPPORTED:
        reason = f"not supported on this device class ({capabilities.device_class})"
        _record_capability_skip(results, name, reason)
        return None
    if status is CapabilityStatus.UNKNOWN:
        reason = (
            f"status unknown on this device class ({capabilities.device_class}); "
            f"add a matrix entry or set "
            f"device.attempt_unknown_capability=True to opt in"
        )
        _record_capability_skip(results, name, reason)
        return None

    # SUPPORTED — execute and report outcome.
    _begin_diagnostic_step(results, name)
    try:
        result = await coro_factory()
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except (AkuvoxConnectionError, AkuvoxAuthenticationError) as exc:
        _finish_diagnostic_step(results, "failed", str(exc), exc)
        raise
    except AkuvoxUnsupportedError as exc:
        reason = f"{exc} (reason={exc.reason})"
        _finish_diagnostic_step(results, "skipped", reason, exc)
        results.mark_skipped(name, reason)
        _default_emit(f"  SKIP: {name}: {reason}")
        return None
    except TestStepSkipped as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "skipped", message, exc)
        results.mark_skipped(name, message)
        _default_emit(f"  SKIP: {name}: {message}")
        return None
    except (TestStepFailed, AkuvoxError) as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(name, message)
        _default_emit(f"  ✗ {name}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {_first_line(str(exc))}"
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(name, message)
        _default_emit(f"  ✗ {name}: {message}")
        traceback.print_exc()
        return None

    _finish_diagnostic_step(results, "passed")
    results.mark_passed(name)
    _default_emit(f"  OK:   {name}")
    return result


async def run_step[T](  # pragma: no cover
    results: TestResults,
    label: str,
    coro: Awaitable[T],
) -> T | None:
    """Run one diagnostic coroutine and continue after non-fatal errors."""
    _begin_diagnostic_step(results, label)
    try:
        result = await coro
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except (AkuvoxConnectionError, AkuvoxAuthenticationError) as exc:
        _finish_diagnostic_step(results, "failed", str(exc), exc)
        raise
    except TestStepSkipped as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "skipped", message, exc)
        results.mark_skipped(label, message)
        _default_emit(f"  ⊘ {label} skipped: {message}")
        return None
    except TestStepFailed as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        _default_emit(f"  ✗ {label}: {message}")
        return None
    except AkuvoxError as exc:
        message = str(exc)
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        _default_emit(f"  ✗ {label}: {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostic script safety net
        message = f"{type(exc).__name__}: {_first_line(str(exc))}"
        _finish_diagnostic_step(results, "failed", message, exc)
        results.mark_failed(label, message)
        _default_emit(f"  ✗ {label}: {message}")
        traceback.print_exc()
        return None

    _finish_diagnostic_step(results, "passed")
    results.mark_passed(label)
    return result


def _begin_diagnostic_step(
    results: TestResults, label: str
) -> None:  # pragma: no cover  # noqa: E501
    """Begin diagnostics for a test step when enabled."""
    if results.diagnostics is not None:
        results.diagnostics.begin_test(label)


def _finish_diagnostic_step(  # pragma: no cover
    results: TestResults,
    status: str,
    reason: str | None = None,
    exc: BaseException | None = None,
) -> None:
    """Finish diagnostics for a test step when enabled."""
    if results.diagnostics is None:
        return
    if exc is not None:
        results.diagnostics.record_exception(exc)
    results.diagnostics.finish_test(status, reason)


def print_header(title: str) -> None:  # pragma: no cover
    """Print a section header."""
    _default_emit(f"\n{SEPARATOR}")
    _default_emit(f"  {title}")
    _default_emit(SEPARATOR)
