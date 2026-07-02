# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for package metadata reads on async device entry."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from typing import TYPE_CHECKING

from aioresponses import aioresponses

from tests.unit._helpers import drop_capability_matrix, register_default_info

if TYPE_CHECKING:
    import pytest


async def test_device_entry_does_not_read_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entering a device context must not call importlib metadata APIs."""
    import pylocal_akuvox
    from pylocal_akuvox.device import AkuvoxDevice

    drop_capability_matrix(pylocal_akuvox)
    calls: list[str] = []

    def fail_metadata_version(distribution_name: str) -> str:
        """Fail if package metadata is read after package import."""
        calls.append(distribution_name)
        raise AssertionError("metadata version read during async device entry")

    monkeypatch.setattr(importlib.metadata, "version", fail_metadata_version)

    with aioresponses() as mocked:
        register_default_info(mocked)
        async with AkuvoxDevice("192.168.1.100") as device:
            assert device.capabilities is not None
            assert device.capabilities.device_class == "X916"

    assert calls == []


def test_matrix_version_matches_package_version() -> None:
    """Matrix provenance uses the package version sampled at import time."""
    import pylocal_akuvox
    import pylocal_akuvox.capability_matrix as capability_matrix

    assert getattr(capability_matrix, "_LIB_VERSION") == pylocal_akuvox.__version__
    for _pattern, capabilities in capability_matrix.CAPABILITY_MATRIX:
        assert capabilities.provenance is not None
        assert capabilities.provenance.library_version == pylocal_akuvox.__version__


def _fresh_imports(*module_names: str) -> None:
    """Import modules after temporarily clearing pylocal_akuvox from sys.modules."""
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "pylocal_akuvox" or name.startswith("pylocal_akuvox.")
    }
    for name in saved:
        sys.modules.pop(name, None)
    try:
        for module_name in module_names:
            assert importlib.import_module(module_name) is not None
    finally:
        for name in list(sys.modules):
            if name == "pylocal_akuvox" or name.startswith("pylocal_akuvox."):
                sys.modules.pop(name, None)
        sys.modules.update(saved)


def test_fresh_package_import_succeeds() -> None:
    """Fresh package import must not regress into a circular import."""
    _fresh_imports("pylocal_akuvox")


def test_fresh_matrix_then_matching_import_succeeds() -> None:
    """Importing matrix before matching must not regress into a cycle."""
    _fresh_imports(
        "pylocal_akuvox.capability_matrix",
        "pylocal_akuvox._capability_matching",
    )


def test_fresh_matching_then_matrix_import_succeeds() -> None:
    """Importing matching before matrix must not regress into a cycle."""
    _fresh_imports(
        "pylocal_akuvox._capability_matching",
        "pylocal_akuvox.capability_matrix",
    )
