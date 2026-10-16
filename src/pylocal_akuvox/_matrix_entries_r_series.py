# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability-matrix entries for R20-family door phones.

Holds the R20K, R20A, and R20BX3
:class:`~pylocal_akuvox._capability_profile.DeviceCapabilities`
entries. Registration order lives in
:data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`.
"""

from __future__ import annotations

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_profile import DeviceCapabilities, Provenance
from pylocal_akuvox._capability_types import Capability, CapabilityStatus, SchemaShape
from pylocal_akuvox._matrix_provenance import LIB_VERSION, OBSERVED_AT

# Issue #229: R20K door phone community write report.
R20K_CURRENT = DeviceCapabilities(
    device_class="R20K",
    firmware_version="320.30.3.122",
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
        # Issue #237: R20-family vouch promotes set support.
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    provenance=Provenance(
        test_bench_device_id="community-reporter (issue #229)",
        firmware_version="320.30.3.122",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


# Issue #234: R20A shares the R20-family door-phone shape, but this
# firmware returns "please use new interface" for legacy FCGI OpenDoor.
R20A_CURRENT = DeviceCapabilities(
    device_class="R20A",
    firmware_version="320.30.11.63",
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
        Capability.RELAY_TRIGGER_FCGI: CapabilityStatus.UNSUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_GET: CapabilityStatus.SUPPORTED,
        # Issue #237: webhook config writes confirm set support.
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    provenance=Provenance(
        test_bench_device_id="community reporter (issue #234)",
        firmware_version="320.30.11.63",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


# Issue #298: R20BX3 door phone community write report. Group modify and
# the FCGI OpenDoor path were not exercised, so they stay UNKNOWN.
R20BX3_CURRENT = DeviceCapabilities(
    device_class="R20BX3",
    firmware_version="320.30.10.153",
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
        test_bench_device_id="community reporter (issue #298)",
        firmware_version="320.30.10.153",
        library_version=LIB_VERSION,
        # Date the write-mode report was attached to the issue.
        observed_at="2026-10-16",
    ),
)


__all__ = ["R20K_CURRENT", "R20A_CURRENT", "R20BX3_CURRENT"]
