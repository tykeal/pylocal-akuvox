# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability-matrix entries for indoor monitors and access units.

Holds the IT83 indoor-monitor and A08S access-unit
:class:`~pylocal_akuvox._capability_profile.DeviceCapabilities`
entries. Registration order lives in
:data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`.
"""

from __future__ import annotations

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_profile import DeviceCapabilities, Provenance
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
from pylocal_akuvox._matrix_provenance import LIB_VERSION, OBSERVED_AT

IT83_83_30_10_4 = DeviceCapabilities(
    device_class="IT83",
    firmware_version="83.30.10.4",
    capabilities={
        # Issue #122: IT83 relay uses open_door_http; FCGI dispatch is a guard.
        Capability.RELAY_TRIGGER_API: CapabilityStatus.UNSUPPORTED,
        Capability.RELAY_TRIGGER_FCGI: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.UNSUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    # Alias / schema-shape mappings left empty — the matrix-marked
    # user/contact CRUD capabilities are all ``UNKNOWN`` for IT83 so
    # the relevant parsers/payload-builders are never reached on this
    # device class. Leaving these empty makes the wrapper fall back to
    # the safe defaults if a caller opts in via
    # ``attempt_unknown_capability=True`` (FR-017).
    field_aliases={},
    schema_shapes={},
    provenance=Provenance(
        test_bench_device_id="community-reporter (issue #130 / #122)",
        firmware_version="83.30.10.4",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


# Issue #222: A08S access unit lacks contacts, groups, and call logs.
A08S_CURRENT = DeviceCapabilities(
    device_class="A08S",
    firmware_version="108.30.10.144",
    capabilities={
        Capability.USER_LIST: CapabilityStatus.SUPPORTED,
        Capability.USER_ADD: CapabilityStatus.SUPPORTED,
        Capability.USER_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.USER_DELETE: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_LIST: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_ADD: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_MODIFY: CapabilityStatus.SUPPORTED,
        Capability.SCHEDULE_DELETE: CapabilityStatus.SUPPORTED,
        Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_GET: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
        Capability.CONTACT_LIST: CapabilityStatus.UNSUPPORTED,
        Capability.CONTACT_ADD: CapabilityStatus.UNSUPPORTED,
        Capability.CONTACT_MODIFY: CapabilityStatus.UNSUPPORTED,
        Capability.CONTACT_DELETE: CapabilityStatus.UNSUPPORTED,
        Capability.GROUP_LIST: CapabilityStatus.UNSUPPORTED,
        Capability.GROUP_ADD: CapabilityStatus.UNSUPPORTED,
        Capability.GROUP_MODIFY: CapabilityStatus.UNSUPPORTED,
        Capability.GROUP_DELETE: CapabilityStatus.UNSUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.UNSUPPORTED,
    },
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="108.30.10.144",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


__all__ = ["IT83_83_30_10_4", "A08S_CURRENT"]
