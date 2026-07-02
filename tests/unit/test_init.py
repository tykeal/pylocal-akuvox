# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for package initialization."""

import importlib.metadata
from unittest.mock import patch

import pylocal_akuvox


def test_version_is_string() -> None:
    """Verify __version__ is a string."""
    assert isinstance(pylocal_akuvox.__version__, str)


def test_version_not_empty() -> None:
    """Verify __version__ is not empty."""
    assert len(pylocal_akuvox.__version__) > 0


def test_all_is_list() -> None:
    """Verify __all__ is a list."""
    assert isinstance(pylocal_akuvox.__all__, list)


def test_version_from_metadata() -> None:
    """Verify version is read from package metadata."""
    import importlib as imp

    try:
        with patch.object(
            importlib.metadata,
            "version",
            return_value="1.2.3",
        ):
            mod = imp.reload(pylocal_akuvox)
            assert mod.__version__ == "1.2.3"
    finally:
        imp.reload(pylocal_akuvox)


def test_version_fallback() -> None:
    """Verify fallback version when package metadata is missing."""
    import importlib as imp

    try:
        with patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("pylocal-akuvox"),
        ):
            mod = imp.reload(pylocal_akuvox)
            assert mod.__version__ == "0.0.0"
    finally:
        imp.reload(pylocal_akuvox)


def test_group_in_all() -> None:
    """Verify Group is exported in __all__."""
    assert "Group" in pylocal_akuvox.__all__


def test_group_importable() -> None:
    """Verify Group is importable from pylocal_akuvox."""
    from pylocal_akuvox import Group

    assert Group is not None


def test_contact_in_all() -> None:
    """Verify Contact is exported in __all__."""
    assert "Contact" in pylocal_akuvox.__all__


def test_contact_importable() -> None:
    """Verify Contact is importable from pylocal_akuvox."""
    from pylocal_akuvox import Contact

    assert Contact is not None
