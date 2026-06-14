# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Curated capability matrix for known Akuvox device classes.

This module owns the ``CAPABILITY_MATRIX`` constant — the curated
list of ``(DeviceClassPattern, DeviceCapabilities)`` entries that
:func:`pylocal_akuvox.capabilities.lookup_capabilities` consults
at connect time. ``lookup_capabilities`` itself lives in
``capabilities.py`` and lazy-imports this module to avoid an import
cycle with :mod:`pylocal_akuvox.capability_adapters` (which itself
imports from :mod:`pylocal_akuvox.capabilities`).

The module also defines a small ``_library_version`` helper plus
the ``_LIB_VERSION`` and ``_OBSERVED_AT`` sentinels that every
:class:`Provenance` instance threads through; these are private and
exist solely to keep every matrix entry's provenance consistent
across the process (sampled once at import time).

The matrix is curated **most-specific-first**: the first
``DeviceClassPattern`` that matches an observed device wins. Adding a
more-permissive entry is a one-line append at the end; adding a
narrower entry is a one-line insert above broader entries.

See ``specs/008-capability-matrix/contracts/matrix-lookup.md`` and
``specs/008-capability-matrix/data-model.md`` §"`CAPABILITY_MATRIX`
initial entries" for the contract that drives the shape and ordering
of the entries below.
"""

from __future__ import annotations

import importlib.metadata

from pylocal_akuvox.capabilities import (
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
    DeviceClassPattern,
    Provenance,
    SchemaShape,
)


def _library_version() -> str:
    """Return the installed library version, or a placeholder if unbuilt.

    Sampled at import time so every matrix entry's :class:`Provenance`
    records the same version string for the duration of the process.
    """
    try:
        return importlib.metadata.version("pylocal-akuvox")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


_LIB_VERSION = _library_version()
_OBSERVED_AT = "2026-06-13"


# --- IT83 indoor monitor (community-reporter, issue #122 / #130) ----------
#
# IT83 supports relay trigger ONLY via /fcgi/do?action=OpenDoor; the
# /api/relay/* endpoints return "No handlers for this request"
# (UNSUPPORTED). All other capabilities are UNKNOWN — the community
# reporter did not exercise user/contact/schedule/group writes.
_IT83_83_30_10_4 = DeviceCapabilities(
    device_class="IT83",
    firmware_version="83.30.10.4",
    capabilities={
        Capability.RELAY_TRIGGER_API: CapabilityStatus.UNSUPPORTED,
        Capability.RELAY_TRIGGER_FCGI: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.UNSUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    field_aliases={},
    schema_shapes={},
    provenance=Provenance(
        test_bench_device_id="community-reporter (issue #130 / #122)",
        firmware_version="83.30.10.4",
        library_version=_LIB_VERSION,
        observed_at=_OBSERVED_AT,
    ),
)

# --- X915S current firmware (door-phone, issue #121 evidence) -------------
#
# Door-phone shape, but `add_contact` is confirmed-UNSUPPORTED on this
# variant per issue #121's "unsupported action" envelope observation;
# `modify_contact` / `delete_contact` were not specifically exercised
# and remain UNKNOWN per FR-003. ``schema_shapes["contact"]`` records
# APARTMENT_BOOK so the contact parser uses the apartment-book shape.
_X915S_CURRENT = DeviceCapabilities(
    device_class="X915S",
    firmware_version="2915.30.10.114",
    capabilities={
        Capability.USER_LIST: CapabilityStatus.SUPPORTED,
        Capability.USER_ADD: CapabilityStatus.SUPPORTED,
        Capability.USER_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.USER_DELETE: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_LIST: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_ADD: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_DELETE: CapabilityStatus.SUPPORTED,
        Capability.GROUP_LIST: CapabilityStatus.SUPPORTED,
        Capability.GROUP_ADD: CapabilityStatus.SUPPORTED,
        Capability.GROUP_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.GROUP_DELETE: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_LIST: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_ADD: CapabilityStatus.UNSUPPORTED,
        Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_GET: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    field_aliases={},
    schema_shapes={"contact": SchemaShape.APARTMENT_BOOK},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="2915.30.10.114",
        library_version=_LIB_VERSION,
        observed_at=_OBSERVED_AT,
    ),
)

# --- E18C current firmware (door-phone) -----------------------------------
_E18C_CURRENT = DeviceCapabilities(
    device_class="E18C",
    firmware_version="18.30.11.21",
    capabilities={
        Capability.USER_LIST: CapabilityStatus.SUPPORTED,
        Capability.USER_ADD: CapabilityStatus.SUPPORTED,
        Capability.USER_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.USER_DELETE: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_LIST: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_ADD: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_DELETE: CapabilityStatus.SUPPORTED,
        Capability.GROUP_LIST: CapabilityStatus.SUPPORTED,
        Capability.GROUP_ADD: CapabilityStatus.SUPPORTED,
        Capability.GROUP_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.GROUP_DELETE: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_LIST: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_ADD: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_DELETE: CapabilityStatus.SUPPORTED,
        Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_GET: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    field_aliases={},
    schema_shapes={},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="18.30.11.21",
        library_version=_LIB_VERSION,
        observed_at=_OBSERVED_AT,
    ),
)

# --- X916 baseline (door-phone) -------------------------------------------
_X916_BASELINE = DeviceCapabilities(
    device_class="X916",
    firmware_version="916.30.10.114",
    capabilities={
        Capability.USER_LIST: CapabilityStatus.SUPPORTED,
        Capability.USER_ADD: CapabilityStatus.SUPPORTED,
        Capability.USER_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.USER_DELETE: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_LIST: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_ADD: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_DELETE: CapabilityStatus.SUPPORTED,
        Capability.GROUP_LIST: CapabilityStatus.SUPPORTED,
        Capability.GROUP_ADD: CapabilityStatus.SUPPORTED,
        Capability.GROUP_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.GROUP_DELETE: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_LIST: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_ADD: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_DELETE: CapabilityStatus.SUPPORTED,
        Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_GET: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    field_aliases={},
    schema_shapes={},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="916.30.10.114",
        library_version=_LIB_VERSION,
        observed_at=_OBSERVED_AT,
    ),
)


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
    # X916 baseline — glob match (last because most permissive).
    (
        DeviceClassPattern(model_prefix="X916", firmware_band="916.30.10.*"),
        _X916_BASELINE,
    ),
)


__all__ = ["CAPABILITY_MATRIX"]
