# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability-matrix entries for E-series door phones.

Holds the E18C, E18, and E12W
:class:`~pylocal_akuvox._capability_profile.DeviceCapabilities`
entries. Registration order lives in
:data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`.
"""

from __future__ import annotations

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_profile import DeviceCapabilities, Provenance
from pylocal_akuvox._capability_types import Capability, CapabilityStatus, SchemaShape
from pylocal_akuvox._matrix_provenance import LIB_VERSION, OBSERVED_AT

E18C_CURRENT = DeviceCapabilities(
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
    # E18C aliasing matches X916 — accepts both ``ScheduleRelay`` and
    # ``Schedule-Relay`` on read; emits both on write (the spec-line-119
    # collision rule observed in issues #99/#101).
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="18.30.11.21",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


# Issue #207: E18 shares the E18C/X916 door-phone capability set.
E18_CURRENT = DeviceCapabilities(
    device_class="E18",
    firmware_version="18.30.10.118",
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
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="18.30.10.118",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


# Issue #299: E12W door phone community write report. Group modify and
# the FCGI OpenDoor path were not exercised, so they stay UNKNOWN.
E12W_CURRENT = DeviceCapabilities(
    device_class="E12W",
    firmware_version="312.30.11.15",
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
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    provenance=Provenance(
        test_bench_device_id="community reporter (issue #299)",
        firmware_version="312.30.11.15",
        library_version=LIB_VERSION,
        # Date the write-mode report was attached to the issue.
        observed_at="2026-10-15",
    ),
)


__all__ = ["E18C_CURRENT", "E18_CURRENT", "E12W_CURRENT"]
