# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Sphinx extension that renders ``CAPABILITY_MATRIX`` as a grid table.

Registered in ``docs/conf.py`` and invoked from
``docs/api/capabilities.rst`` via the ``.. capability-matrix::``
directive. Per ``specs/008-capability-matrix/research.md`` Decision
11, the directive imports
:data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX` at
documentation build time and emits a reST grid table with one row per
entry. This avoids hand-maintained tables that go stale (the failure
mode SC-009 was written to prevent).

The directive is sphinx-only — it is not imported from the library
package itself. The pytest plain-text consistency check in
``tests/unit/test_docs_matrix_consistency.py`` runs *without* sphinx
so the production test surface stays decoupled from the docs
toolchain (Decision 11 §"Rationale").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import StringList

from pylocal_akuvox._capability_types import Capability, CapabilityStatus
from pylocal_akuvox.capability_matrix import CAPABILITY_MATRIX

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sphinx.application import Sphinx  # type: ignore[import-not-found]


_HEADERS: tuple[str, ...] = (
    "Model prefix",
    "Firmware band",
    "Supported",
    "Unsupported",
    "Unknown",
    "Provenance",
)


def _count_status(
    capabilities: Mapping[Capability, CapabilityStatus] | None,
    status: CapabilityStatus,
) -> int:
    """Count entries with ``status`` in the supplied capabilities mapping."""
    if capabilities is None:
        return 0
    return sum(1 for value in capabilities.values() if value is status)


def _build_rows() -> list[tuple[str, str, str, str, str, str]]:
    """Render each ``CAPABILITY_MATRIX`` entry as one row of strings.

    Counts are derived from the entry's ``capabilities`` mapping:

    * ``Supported`` and ``Unsupported`` count entries explicitly set
      to that status.
    * ``Unknown`` is computed as ``len(Capability) - supported -
      unsupported`` so it includes both entries explicitly set to
      ``CapabilityStatus.UNKNOWN`` **and** every capability that is
      *absent* from the mapping. Absence is semantically ``UNKNOWN``
      per :meth:`DeviceCapabilities.status_of` and
      ``contracts/matrix-lookup.md``; without this, the rendered
      column would significantly under-report unknowns and mislead
      readers into thinking most capabilities are classified.
    """
    rows: list[tuple[str, str, str, str, str, str]] = []
    total_caps = len(Capability)
    for pattern, capabilities in CAPABILITY_MATRIX:
        # ``DeviceCapabilities.capabilities`` is a read-only mapping;
        # casting is safe because we only read.
        caps_map = dict(capabilities.capabilities)
        supported = _count_status(caps_map, CapabilityStatus.SUPPORTED)
        unsupported = _count_status(caps_map, CapabilityStatus.UNSUPPORTED)
        # ``Unknown`` includes both explicit ``CapabilityStatus.UNKNOWN``
        # entries AND every Capability member that is *absent* from
        # the mapping (absence == UNKNOWN per
        # ``DeviceCapabilities.status_of`` and
        # ``contracts/matrix-lookup.md``). Computing as
        # ``len(Capability) - SUPPORTED - UNSUPPORTED`` keeps the
        # rendered "Unknown" column consistent with what
        # :meth:`AkuvoxDevice` actually enforces at call time.
        unknown = total_caps - supported - unsupported

        prov = capabilities.provenance
        if prov is not None:
            provenance_text = (
                f"{prov.test_bench_device_id} "
                f"@ lib {prov.library_version}, observed {prov.observed_at}"
            )
        else:
            provenance_text = "—"

        rows.append(
            (
                pattern.model_prefix,
                pattern.firmware_band,
                str(supported),
                str(unsupported),
                str(unknown),
                provenance_text,
            )
        )
    return rows


def _render_grid_table(
    headers: tuple[str, ...],
    rows: Sequence[tuple[str, ...]],
) -> str:
    """Render ``(headers, rows)`` as a docutils grid table source block.

    The widths are computed per-column from the longest cell so the
    output passes docutils' grid-table parser without alignment
    warnings.
    """
    columns = list(zip(headers, *rows, strict=True))
    widths = [max(len(str(cell)) for cell in column) for column in columns]

    def _separator(char: str) -> str:
        """Return a horizontal grid-table separator line built from ``char``."""
        segments = [char * (width + 2) for width in widths]
        return "+" + "+".join(segments) + "+"

    def _row(values: tuple[str, ...]) -> str:
        """Return one grid-table row, left-padded to each column's width."""
        cells = [
            f" {value:<{width}} " for value, width in zip(values, widths, strict=True)
        ]
        return "|" + "|".join(cells) + "|"

    lines = [_separator("-"), _row(headers), _separator("=")]
    for row in rows:
        lines.append(_row(row))
        lines.append(_separator("-"))
    return "\n".join(lines)


class CapabilityMatrixDirective(Directive):
    """Render :data:`CAPABILITY_MATRIX` as a reST grid table at build time."""

    has_content = False
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[nodes.Node]:
        """Return the parsed grid-table nodes ready to slot into the doc tree."""
        rows = _build_rows()
        table_text = _render_grid_table(_HEADERS, rows)
        input_lines = self.state_machine.input_lines
        source: str | None = None
        if input_lines is not None:
            source = input_lines.source(
                self.lineno - self.state_machine.input_offset - 1,
            )
        view = StringList(table_text.splitlines(), source=source or "")
        container = nodes.Element()
        self.state.nested_parse(view, self.content_offset, container)
        return list(container.children)


def setup(app: Sphinx) -> dict[str, object]:
    """Register the ``capability-matrix`` directive with sphinx."""
    app.add_directive("capability-matrix", CapabilityMatrixDirective)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}


__all__ = ["CapabilityMatrixDirective", "setup"]
