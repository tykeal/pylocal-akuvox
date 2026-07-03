# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Doc-vs-matrix consistency check (T076, FR-018, SC-009).

Plain-text scan: the test reads ``docs/api/capabilities.rst`` as a
flat string and asserts a bidirectional match against
:data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`. Sphinx is
not invoked. Per ``specs/008-capability-matrix/research.md``
Decision 11 §"Rationale", this keeps the production test surface
decoupled from the docs toolchain so CI does not need sphinx
installed to enforce the doc-stays-in-sync contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX

# The .rst lives at ``<repo>/docs/api/capabilities.rst``. This test
# file lives at ``<repo>/tests/unit/test_docs_matrix_consistency.py``,
# so ``parents[2]`` is the repo root.
_CAPABILITIES_RST = (
    Path(__file__).resolve().parents[2] / "docs" / "api" / "capabilities.rst"
)

# Underline characters used by reST section / sub-section headings in
# the in-repo .rst files. Any single-line "MODEL" followed by one of
# these underlines counts as a heading mention.
_UNDERLINE_CHARS = "=-~^\"'+#*"


@pytest.fixture(scope="module")
def capabilities_rst_text() -> str:
    """Return the full text of ``docs/api/capabilities.rst``."""
    return _CAPABILITIES_RST.read_text(encoding="utf-8")


def _collect_rst_headings(text: str, allowed: set[str]) -> set[str]:
    """Return ``allowed`` device-class headings actually present in ``text``.

    A heading is "<MODEL>" on one line followed by a line of underline
    characters (``=``, ``-``, ``~``, ...). Only model strings in
    ``allowed`` are matched so unrelated single-word lines (e.g.
    autoclass output, ``Public types``) never produce false positives.
    """
    found: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        stripped = line.strip()
        if stripped not in allowed:
            continue
        underline = lines[index + 1].strip()
        if not underline:
            continue
        if all(char in _UNDERLINE_CHARS for char in underline) and len(
            underline
        ) >= len(stripped):
            found.add(stripped)
    return found


# Heuristic for "looks like a device-class model prefix": a single
# uppercase / digit token of 2-12 chars containing at least one
# digit. This catches concrete examples (``X916``, ``X915S``,
# ``E18C``, ``IT83``, ``X999``) without false-positiving on noun
# headings (``Device classes``, ``Public types``, ``Contributing
# a new device class``).
_MODEL_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")


def _collect_modellike_headings(text: str) -> set[str]:
    """Return every heading whose text matches the model-prefix shape.

    Used by :func:`test_every_doc_heading_maps_to_matrix` to detect a
    rogue heading like ``X999`` that has no corresponding matrix
    entry — without this broader scan, the bidirectional check would
    only ever look at prefixes already in the matrix (false-negative
    for an orphan heading).
    """
    found: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        stripped = line.strip()
        if not _MODEL_HEADING_RE.fullmatch(stripped):
            continue
        if not any(ch.isdigit() for ch in stripped):
            continue
        underline = lines[index + 1].strip()
        if not underline:
            continue
        if all(char in _UNDERLINE_CHARS for char in underline) and len(
            underline
        ) >= len(stripped):
            found.add(stripped)
    return found


def test_every_matrix_prefix_appears_in_docs(capabilities_rst_text: str) -> None:
    """Every matrix entry's ``model_prefix`` must be mentioned in the .rst."""
    missing: list[str] = []
    for pattern, _ in CAPABILITY_MATRIX:
        # Match as a whole token so a future "X91" prefix would not
        # silently piggy-back on an "X916" mention.
        token = re.compile(rf"\b{re.escape(pattern.model_prefix)}\b")
        if not token.search(capabilities_rst_text):
            missing.append(pattern.model_prefix)
    assert not missing, (
        f"docs/api/capabilities.rst is missing matrix-registered model "
        f"prefixes: {sorted(set(missing))}"
    )


def test_every_doc_heading_maps_to_matrix(capabilities_rst_text: str) -> None:
    """Every model-prefix-shaped heading in the .rst must map to the matrix.

    Uses :func:`_collect_modellike_headings` (a width-2-12 uppercase
    token with at least one digit) so an orphan heading like ``X999``
    that has no matching ``CAPABILITY_MATRIX`` entry would surface
    here even though it is not in the matrix-derived candidate pool.
    """
    allowed = {pattern.model_prefix for pattern, _ in CAPABILITY_MATRIX}
    headings = _collect_modellike_headings(capabilities_rst_text)
    orphans = headings - allowed
    assert not orphans, (
        f"docs/api/capabilities.rst has device-class headings without a "
        f"matching CAPABILITY_MATRIX entry: {sorted(orphans)}"
    )


def test_canonical_prefixes_present(capabilities_rst_text: str) -> None:
    """Sanity: the canonical prefixes are each a heading."""
    expected = {"X916", "X915S", "E18C", "E18", "A08S", "IT83"}
    headings = _collect_rst_headings(capabilities_rst_text, expected)
    assert headings == expected, (
        f"Expected all canonical prefixes to be section headings; "
        f"found {sorted(headings)}"
    )
