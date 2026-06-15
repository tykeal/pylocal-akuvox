# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Layout assertions for spec ``009-capabilities-module-split``.

These tests pin the post-refactor module shape so the change cannot be
silently undone:

* The legacy ``pylocal_akuvox.capabilities`` subpath must be gone
  (``ModuleNotFoundError`` on both bare-import and from-import forms).
* The four new underscore-prefixed sibling modules must be importable
  via :func:`importlib.import_module` (proves the split is real and
  not a behaviour-equivalent shim).
* The five public symbols re-exported from the top-level package must
  resolve via identity to the corresponding members of the new
  underscore modules (proves the top-level re-export traces through
  the new modules, not through some accidental fallback).
* The five public symbol names must be present in
  :data:`pylocal_akuvox.__all__` (belt-and-suspenders against an
  accidental ``__all__`` edit).
"""

from __future__ import annotations

import importlib

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
