# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the example MVP diagnostic runner helpers."""

from __future__ import annotations

import examples.mvp_test as mvp_test
import pytest

from pylocal_akuvox.exceptions import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
)


async def _successful_step() -> str:
    """Return a value from a successful diagnostic step."""
    return "ok"


async def _device_error_step() -> None:
    """Raise a non-fatal device error."""
    raise AkuvoxDeviceError("No handlers for this request")


async def _skipped_step() -> None:
    """Raise an expected diagnostic skip."""
    raise mvp_test.TestStepSkipped("missing prerequisite")


async def _connection_error_step() -> None:
    """Raise a fatal connection error."""
    raise AkuvoxConnectionError("connection refused")


async def _authentication_error_step() -> None:
    """Raise a fatal authentication error."""
    raise AkuvoxAuthenticationError("bad credentials")


async def test_run_step_records_success() -> None:
    """Run a successful step and record its label."""
    results = mvp_test.TestResults()

    value = await mvp_test.run_step(results, "SUCCESS", _successful_step())

    assert value == "ok"
    assert results.passed == ["SUCCESS"]
    assert results.failed == []
    assert results.skipped == []


async def test_run_step_records_non_fatal_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Record device errors as failures without raising."""
    results = mvp_test.TestResults()

    await mvp_test.run_step(results, "LIST USERS", _device_error_step())

    assert results.failed == [("LIST USERS", "No handlers for this request")]
    assert "✗ LIST USERS: No handlers for this request" in capsys.readouterr().out


async def test_run_step_records_skip(capsys: pytest.CaptureFixture[str]) -> None:
    """Record expected skips separately from failures."""
    results = mvp_test.TestResults()

    await mvp_test.run_step(results, "SET DEVICE CONFIG", _skipped_step())

    assert results.skipped == [("SET DEVICE CONFIG", "missing prerequisite")]
    output = capsys.readouterr().out
    assert "⊘ SET DEVICE CONFIG skipped: missing prerequisite" in output


async def test_run_step_reraises_connection_errors() -> None:
    """Abort on connection failures."""
    results = mvp_test.TestResults()

    with pytest.raises(AkuvoxConnectionError):
        await mvp_test.run_step(results, "FATAL", _connection_error_step())

    assert results.total == 0


async def test_run_step_reraises_authentication_errors() -> None:
    """Abort on authentication failures."""
    results = mvp_test.TestResults()

    with pytest.raises(AkuvoxAuthenticationError):
        await mvp_test.run_step(results, "FATAL", _authentication_error_step())

    assert results.total == 0


def test_skip_step_records_dependency_skip(capsys: pytest.CaptureFixture[str]) -> None:
    """Record dependent steps skipped by the write-test chain."""
    results = mvp_test.TestResults()

    mvp_test.skip_step(results, "DELETE USER", "requires internal ID from ADD USER")

    assert results.skipped == [
        ("DELETE USER", "requires internal ID from ADD USER"),
    ]
    assert (
        "⊘ DELETE USER skipped: requires internal ID from ADD USER"
        in capsys.readouterr().out
    )


def test_summary_lists_all_result_buckets(capsys: pytest.CaptureFixture[str]) -> None:
    """Print counts and labels for passed, failed, and skipped steps."""
    results = mvp_test.TestResults()
    results.mark_passed("GET DEVICE INFO")
    results.mark_failed("LIST USERS", "No handlers for this request")
    results.mark_skipped("DELETE USER", "requires ADD USER")

    results.print_summary()

    output = capsys.readouterr().out
    assert "Total:      3" in output
    assert "✓ Passed:   1" in output
    assert "✗ Failed:   1" in output
    assert "⊘ Skipped:  1" in output
    assert "- GET DEVICE INFO" in output
    assert "- LIST USERS: No handlers for this request" in output
    assert "- DELETE USER: requires ADD USER" in output
