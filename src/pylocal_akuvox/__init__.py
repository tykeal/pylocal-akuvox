# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Async Python library for the Akuvox local HTTP API."""

import importlib.metadata

_DIST_NAME = "pylocal-akuvox"

try:
    __version__ = importlib.metadata.version(_DIST_NAME)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

# Public API re-exports will be added as modules are implemented.
__all__: list[str] = []
