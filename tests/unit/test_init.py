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
    with patch.object(
        importlib.metadata,
        "version",
        return_value="1.2.3",
    ):
        import importlib as imp

        mod = imp.reload(pylocal_akuvox)
        assert mod.__version__ == "1.2.3"


def test_version_fallback() -> None:
    """Verify fallback version when package metadata is missing."""
    with patch.object(
        importlib.metadata,
        "version",
        side_effect=importlib.metadata.PackageNotFoundError,
    ):
        import importlib as imp

        mod = imp.reload(pylocal_akuvox)
        assert mod.__version__ == "0.0.0"
