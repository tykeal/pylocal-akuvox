# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Shared provenance sentinels for the curated capability matrix.

``LIB_VERSION`` and ``OBSERVED_AT`` are threaded through every
:class:`~pylocal_akuvox._capability_profile.Provenance` instance built
by the ``_matrix_entries_*`` device-family modules. They live in their
own module so every family module shares the same values, sampled once
when this module loads, keeping matrix provenance consistent across
the process.
``LIB_VERSION`` reuses the package ``__version__`` so building the
matrix never triggers package-metadata I/O.
"""

from __future__ import annotations

from pylocal_akuvox import __version__ as LIB_VERSION

OBSERVED_AT = "2026-06-13"

__all__ = ["LIB_VERSION", "OBSERVED_AT"]
