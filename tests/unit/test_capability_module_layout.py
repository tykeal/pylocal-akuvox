# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Layout assertions for specs 009-capabilities-module-split + 010-probe-split.

These tests pin the post-refactor module shape so the changes cannot be
silently undone:

* The legacy ``pylocal_akuvox.capabilities`` and
  ``pylocal_akuvox.capability_probe`` subpaths must be gone
  (``ModuleNotFoundError`` on both bare-import and from-import forms).
* The four new capability-side underscore-prefixed sibling modules
  (spec 009) and the four new probe-side underscore-prefixed sibling
  modules (spec 010) must be importable via
  :func:`importlib.import_module` (proves the splits are real and
  not behaviour-equivalent shims).
* The five public symbols re-exported from the top-level package must
  resolve via identity to the corresponding members of the new
  underscore modules (proves the top-level re-export traces through
  the new modules, not through some accidental fallback).
* The five public symbol names must be present in
  :data:`pylocal_akuvox.__all__` (belt-and-suspenders against an
  accidental ``__all__`` edit).
* ``AkuvoxDevice.probe_capabilities`` remains the public consumer-
  facing handle for the capability probe (presence pin only — the
  behaviour suite lives in ``test_capability_probe.py``).
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

import pylocal_akuvox
import pylocal_akuvox._capability_profile as _profile
import pylocal_akuvox._capability_types as _types


def test_capabilities_subpath_is_gone() -> None:
    """``import pylocal_akuvox.capabilities`` must raise ``ModuleNotFoundError``."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pylocal_akuvox.capabilities")


def test_capabilities_subpath_from_import_is_gone() -> None:
    """``from pylocal_akuvox.capabilities import Capability`` must raise.

    Uses ``exec()`` because a static ``from`` import at module top level
    would be evaluated at pytest-collection time, outside the
    ``pytest.raises`` context, and would itself raise
    ``ModuleNotFoundError`` post-split, preventing the test module from
    loading. ``ModuleNotFoundError`` is required specifically (not the
    wider ``ImportError`` superclass) so a hypothetical partial-shim
    regression — e.g. a re-resurrected ``pylocal_akuvox.capabilities``
    module that loads but no longer exports ``Capability`` — would
    raise the bare ``ImportError`` and fail this test loudly rather
    than slip through.
    """
    with pytest.raises(ModuleNotFoundError):
        exec("from pylocal_akuvox.capabilities import Capability")  # noqa: S102


def test_underscore_modules_importable() -> None:
    """Each of the four new underscore modules must import cleanly."""
    for name in (
        "pylocal_akuvox._capability_types",
        "pylocal_akuvox._capability_profile",
        "pylocal_akuvox._capability_matching",
        "pylocal_akuvox._capability_defaults",
    ):
        importlib.import_module(name)


def test_public_symbols_roundtrip_via_top_level() -> None:
    """The 5 public symbols must trace to their source underscore modules."""
    assert pylocal_akuvox.Capability is _types.Capability
    assert pylocal_akuvox.CapabilityStatus is _types.CapabilityStatus
    assert pylocal_akuvox.SchemaShape is _types.SchemaShape
    assert pylocal_akuvox.DeviceCapabilities is _profile.DeviceCapabilities
    assert pylocal_akuvox.FieldAliases is _profile.FieldAliases


def test_capability_symbols_in_top_level_all() -> None:
    """The 5 public capability names must be present in ``__all__``."""
    for name in (
        "Capability",
        "CapabilityStatus",
        "SchemaShape",
        "DeviceCapabilities",
        "FieldAliases",
    ):
        assert name in pylocal_akuvox.__all__, (
            f"{name!r} missing from pylocal_akuvox.__all__"
        )


def test_capability_probe_subpath_is_gone() -> None:
    """``import pylocal_akuvox.capability_probe`` must raise ``ModuleNotFoundError``.

    Per spec 010-capability-probe-split FR-002: the
    ``pylocal_akuvox.capability_probe`` module path is removed entirely
    post-split. No shim, no package — just a clean
    ``ModuleNotFoundError``. The migration path lives in
    ``docs/changelog.rst`` Unreleased "Breaking changes" subsection:
    consumers continue to call ``AkuvoxDevice.probe_capabilities()``.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pylocal_akuvox.capability_probe")


def test_capability_probe_subpath_from_import_is_gone() -> None:
    """``from pylocal_akuvox.capability_probe import probe_capabilities`` must raise.

    Uses ``exec()`` for the same reason as
    :func:`test_capabilities_subpath_from_import_is_gone`: a static
    ``from`` import at module top level would be evaluated at
    pytest-collection time, outside the ``pytest.raises`` context, and
    would itself raise ``ModuleNotFoundError`` post-split, preventing
    the test module from loading. ``ModuleNotFoundError`` is required
    specifically (not the wider ``ImportError`` superclass) so a
    hypothetical partial-shim regression — e.g. a re-resurrected
    ``pylocal_akuvox.capability_probe`` module that loads but no
    longer exports ``probe_capabilities`` — would raise the bare
    ``ImportError`` and fail this test loudly rather than slip through.
    Covers spec 010 FR-003.
    """
    with pytest.raises(ModuleNotFoundError):
        exec("from pylocal_akuvox.capability_probe import probe_capabilities")  # noqa: S102


def test_probe_underscore_modules_importable() -> None:
    """Each of the four new probe-side underscore modules must import cleanly."""
    for name in (
        "pylocal_akuvox._probe_outcomes",
        "pylocal_akuvox._probe_classifiers",
        "pylocal_akuvox._probe_parsers",
        "pylocal_akuvox._capability_probe",
    ):
        importlib.import_module(name)


def test_probe_capabilities_reachable_via_device() -> None:
    """``AkuvoxDevice.probe_capabilities`` remains the public consumer handle.

    Presence pin only — the behaviour suite lives in
    ``test_capability_probe.py``. Covers spec 010 FR-001 + User
    Story 1 acceptance scenario.
    """
    assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities)


def test_device_subpath_remains_importable() -> None:
    """``pylocal_akuvox.device`` remains a public import path."""
    module = importlib.import_module("pylocal_akuvox.device")

    assert getattr(module, "AkuvoxDevice") is pylocal_akuvox.AkuvoxDevice
    assert module.__file__ is not None
    module_path = Path(module.__file__)
    assert module_path.name == "device.py" or (
        module_path.suffix == ".pyc" and module_path.name.startswith("device.")
    )


def test_device_public_symbol_in_top_level_all() -> None:
    """``AkuvoxDevice`` remains part of the top-level public exports."""
    assert "AkuvoxDevice" in pylocal_akuvox.__all__


def test_device_underscore_modules_importable() -> None:
    """Each focused device helper module must import cleanly."""
    for name in (
        "pylocal_akuvox._device_profiles",
        "pylocal_akuvox._device_runtime",
        "pylocal_akuvox._device_users",
        "pylocal_akuvox._device_relays",
        "pylocal_akuvox._device_access",
        "pylocal_akuvox._device_contacts",
        "pylocal_akuvox._device_config_logs",
    ):
        importlib.import_module(name)


def _module_line_count(module_name: str) -> int:
    """Return the source line count for an importable module."""
    module = importlib.import_module(module_name)
    assert module.__file__ is not None
    path = Path(module.__file__)
    if path.suffix == ".pyc":
        source_path = Path(importlib.util.source_from_cache(str(path)))
        if not source_path.exists():
            pytest.skip(f"source file not available for {module_name}")
        path = source_path
    return len(path.read_text(encoding="utf-8").splitlines())


def test_device_modules_under_aislop_limit() -> None:
    """The retained facade and helper modules must stay below 400 lines."""
    for name in (
        "pylocal_akuvox.device",
        "pylocal_akuvox._device_profiles",
        "pylocal_akuvox._device_runtime",
        "pylocal_akuvox._device_users",
        "pylocal_akuvox._device_relays",
        "pylocal_akuvox._device_access",
        "pylocal_akuvox._device_contacts",
        "pylocal_akuvox._device_config_logs",
    ):
        assert _module_line_count(name) < 400
