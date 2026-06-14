# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for :class:`AkuvoxUnsupportedError`.

Covers the five tests required by
``specs/008-capability-matrix/contracts/unsupported-error.md``
§"Test coverage required":

* :func:`test_default_constructor_message_only` — message-only construction
  preserves the legacy single-arg surface (FR-010 backward-compat half).
* :func:`test_structured_constructor_capability_missing` — structured
  kwargs round-trip cleanly.
* :func:`test_structured_constructor_capability_unknown` — three-valued
  status reason round-trips identically.
* :func:`test_reason_taxonomy_closed` — production raises in ``src/`` only
  use values inside the documented closed set.
* :func:`test_isinstance_akuvox_error` — class hierarchy preserved.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pylocal_akuvox.capabilities import Capability
from pylocal_akuvox.exceptions import AkuvoxError, AkuvoxUnsupportedError


def test_default_constructor_message_only() -> None:
    """Single-arg construction preserves the legacy surface (FR-010)."""
    exc = AkuvoxUnsupportedError("x")
    assert exc.args == ("x",)
    assert str(exc) == "x"
    assert exc.capability is None
    assert exc.device_class is None
    assert exc.reason is None


def test_structured_constructor_capability_missing() -> None:
    """Structured kwargs round-trip on a ``capability_missing`` raise."""
    exc = AkuvoxUnsupportedError(
        "Device class IT83 does not support relay.trigger.api",
        capability=Capability.RELAY_TRIGGER_API,
        device_class="IT83",
        reason="capability_missing",
    )
    assert exc.capability is Capability.RELAY_TRIGGER_API
    assert exc.device_class == "IT83"
    assert exc.reason == "capability_missing"
    assert "IT83" in str(exc)
    # Class hierarchy preserved.
    assert isinstance(exc, AkuvoxError)


def test_structured_constructor_capability_unknown() -> None:
    """``capability_unknown`` reason round-trips identically."""
    exc = AkuvoxUnsupportedError(
        "Capability user.add has unknown status on IT83",
        capability=Capability.USER_ADD,
        device_class="IT83",
        reason="capability_unknown",
    )
    assert exc.capability is Capability.USER_ADD
    assert exc.device_class == "IT83"
    assert exc.reason == "capability_unknown"


def test_reason_taxonomy_closed() -> None:
    """Production raises only use values in the documented closed set.

    Greps every ``raise AkuvoxUnsupportedError(...)`` call site in
    ``src/`` and asserts the literal string passed to ``reason=`` is
    one of the allowed values. Catches accidental reason-string drift
    that would corrupt the closed-set discriminator (e.g.
    ``reason="unknown_capability"`` vs ``reason="capability_unknown"``).
    """
    allowed = {
        "capability_missing",
        "capability_unknown",
        "device_unrecognized",
        "adapter_missing",
        "envelope_unsupported",
    }
    src = Path(__file__).resolve().parents[2] / "src" / "pylocal_akuvox"
    pattern = re.compile(r"reason\s*=\s*['\"]([a-z_]+)['\"]")
    found: set[str] = set()
    for path in src.rglob("*.py"):
        text = path.read_text()
        for match in pattern.finditer(text):
            found.add(match.group(1))
    # Every observed reason string is in the allowed closed set.
    assert found, "expected at least one reason= literal in src/"
    assert found <= allowed, f"unexpected reasons: {sorted(found - allowed)}"


def test_isinstance_akuvox_error() -> None:
    """``AkuvoxUnsupportedError`` is still an :class:`AkuvoxError`."""
    exc = AkuvoxUnsupportedError("x")
    assert isinstance(exc, AkuvoxError)
    assert isinstance(exc, Exception)
    # Round-trip through ``raise``/``except`` to exercise the hierarchy.
    with pytest.raises(AkuvoxError):
        raise AkuvoxUnsupportedError("y")
