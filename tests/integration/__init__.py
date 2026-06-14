# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Integration test suite for pylocal-akuvox.

Integration tests exercise the library end-to-end against mocked
devices using :mod:`aioresponses`. They are slower than unit tests
and are deliberately separated under ``tests/integration/`` so the
unit-test fast feedback loop stays sub-second per file.
"""
