# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Curated capability matrix for known Akuvox device classes.

This module owns the ``CAPABILITY_MATRIX`` constant — the curated
list of ``(DeviceClassPattern, DeviceCapabilities)`` entries that
:func:`pylocal_akuvox._capability_matching.lookup_capabilities` consults
at connect time. ``lookup_capabilities`` itself lives in
:mod:`pylocal_akuvox._capability_matching` and lazy-imports this
module's ``CAPABILITY_MATRIX`` constant inside its function body to
break the import cycle that would otherwise form between the two
modules: this module imports ``DeviceClassPattern`` from
``_capability_matching`` at module load, so a corresponding top-level
import of ``CAPABILITY_MATRIX`` from ``_capability_matching``'s
direction would close the loop.

The per-device ``DeviceCapabilities`` entries live in private
device-family modules (``_matrix_entries_e_series``,
``_matrix_entries_r_series``, ``_matrix_entries_x_series``, and
``_matrix_entries_indoor_access``); this module only registers them.
The shared ``LIB_VERSION`` and ``OBSERVED_AT`` provenance sentinels
live in :mod:`pylocal_akuvox._matrix_provenance` so every entry's
provenance stays consistent across the process (sampled once when
that module loads). Names that were importable from this module
before the split are kept importable via redundant-alias re-exports.

The matrix is curated **most-specific-first**: the first
``DeviceClassPattern`` that matches an observed device wins. Adding a
more-permissive entry is an append at the end; adding a narrower
entry is an insert above broader entries.

See ``specs/008-capability-matrix/contracts/matrix-lookup.md`` and
``specs/008-capability-matrix/data-model.md`` §"`CAPABILITY_MATRIX`
initial entries" for the contract that drives the shape and ordering
of the entries below.
"""

from __future__ import annotations

from pylocal_akuvox import _capability_profile
from pylocal_akuvox._capability_defaults import (
    DEFAULT_USER_FIELD_ALIASES as DEFAULT_USER_FIELD_ALIASES,
)
from pylocal_akuvox._capability_matching import DeviceClassPattern
from pylocal_akuvox._capability_profile import (
    FieldAliases as FieldAliases,
)
from pylocal_akuvox._capability_profile import (
    Provenance as Provenance,
)
from pylocal_akuvox._capability_types import (
    Capability as Capability,
)
from pylocal_akuvox._capability_types import (
    CapabilityStatus as CapabilityStatus,
)
from pylocal_akuvox._capability_types import (
    SchemaShape as SchemaShape,
)
from pylocal_akuvox._matrix_entries_e_series import (
    E12W_CURRENT as _E12W_CURRENT,
)
from pylocal_akuvox._matrix_entries_e_series import (
    E18_CURRENT as _E18_CURRENT,
)
from pylocal_akuvox._matrix_entries_e_series import (
    E18C_CURRENT as _E18C_CURRENT,
)
from pylocal_akuvox._matrix_entries_indoor_access import (
    A08S_CURRENT as _A08S_CURRENT,
)
from pylocal_akuvox._matrix_entries_indoor_access import (
    IT83_83_30_10_4 as _IT83_83_30_10_4,
)
from pylocal_akuvox._matrix_entries_r_series import R20A_CURRENT as _R20A_CURRENT
from pylocal_akuvox._matrix_entries_r_series import R20K_CURRENT as _R20K_CURRENT
from pylocal_akuvox._matrix_entries_x_series import X915S_CURRENT as _X915S_CURRENT
from pylocal_akuvox._matrix_entries_x_series import X916_BASELINE as _X916_BASELINE

# Runtime binding (not a type-only import) so ``DeviceCapabilities`` stays
# importable from this module alongside the re-exports above.
DeviceCapabilities = _capability_profile.DeviceCapabilities

CAPABILITY_MATRIX: tuple[tuple[DeviceClassPattern, DeviceCapabilities], ...] = (
    # IT83 indoor monitor — exact firmware match (most specific).
    (
        DeviceClassPattern(model_prefix="IT83", firmware_band="83.30.10.4"),
        _IT83_83_30_10_4,
    ),
    # X915S current firmware — floor band (excludes historical 113).
    (
        DeviceClassPattern(model_prefix="X915S", firmware_band="2915.30.10.114+"),
        _X915S_CURRENT,
    ),
    # E18C current firmware — glob match.
    (
        DeviceClassPattern(model_prefix="E18C", firmware_band="18.30.11.*"),
        _E18C_CURRENT,
    ),
    # E18 current firmware — floor band, after E18C to avoid shadowing.
    (
        DeviceClassPattern(model_prefix="E18", firmware_band="18.30.10.118+"),
        _E18_CURRENT,
    ),
    # A08S access unit — floor band.
    (
        DeviceClassPattern(model_prefix="A08S", firmware_band="108.30.10.144+"),
        _A08S_CURRENT,
    ),
    # R20K door phone — floor band from community write report.
    (
        DeviceClassPattern(model_prefix="R20K", firmware_band="320.30.3.122+"),
        _R20K_CURRENT,
    ),
    # R20A door phone — floor band from community write report.
    (
        DeviceClassPattern(model_prefix="R20A", firmware_band="320.30.11.63+"),
        _R20A_CURRENT,
    ),
    # E12W door phone — floor band from community write report.
    (
        DeviceClassPattern(model_prefix="E12W", firmware_band="312.30.11.15+"),
        _E12W_CURRENT,
    ),
    # X916 baseline — glob match (last because most permissive).
    (
        DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*"),
        _X916_BASELINE,
    ),
)


__all__ = ["CAPABILITY_MATRIX"]
