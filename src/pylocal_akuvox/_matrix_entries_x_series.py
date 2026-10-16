# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability-matrix entries for X-series door phones.

Holds the X915S and X916
:class:`~pylocal_akuvox._capability_profile.DeviceCapabilities`
entries. Registration order lives in
:data:`pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`.
"""

from __future__ import annotations

from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES
from pylocal_akuvox._capability_profile import (
    DeviceCapabilities,
    FieldAliases,
    Provenance,
)
from pylocal_akuvox._capability_types import Capability, CapabilityStatus, SchemaShape
from pylocal_akuvox._matrix_provenance import LIB_VERSION, OBSERVED_AT

X915S_CURRENT = DeviceCapabilities(
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
        # Issue #121: apartment-book contact writes are unsupported over HTTP.
        Capability.CONTACT_ADD: CapabilityStatus.UNSUPPORTED,
        Capability.CONTACT_MODIFY: CapabilityStatus.UNSUPPORTED,
        Capability.CONTACT_DELETE: CapabilityStatus.UNSUPPORTED,
        Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED,
        Capability.RELAY_STATUS: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_GET: CapabilityStatus.SUPPORTED,
        Capability.DEVICE_CONFIG_SET: CapabilityStatus.SUPPORTED,
        Capability.LOG_DOOR: CapabilityStatus.SUPPORTED,
        Capability.LOG_CALL: CapabilityStatus.SUPPORTED,
        Capability.KEY_DISCOVERY: CapabilityStatus.SUPPORTED,
    },
    # X915S current FW returns the bare ``Schedule`` key on user
    # reads (issue #118 / PR #120). Order matters: the parser walks
    # ``read`` in declared order and uses the first match, so
    # ``Schedule`` comes first to win against any future payload
    # that happens to also carry ``ScheduleRelay``. Write list keeps
    # parity with X916 (``ScheduleRelay`` + ``Schedule-Relay`` —
    # dual-write satisfies both firmware bands and preserves the
    # E18C compatibility contract).
    field_aliases={
        "schedule_relay": FieldAliases(
            read=("Schedule", "ScheduleRelay", "Schedule-Relay"),
            write=("ScheduleRelay", "Schedule-Relay"),
        ),
    },
    schema_shapes={"contact": SchemaShape.APARTMENT_BOOK},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="2915.30.10.114",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


X916_BASELINE = DeviceCapabilities(
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
    # X916 baseline aliasing — matches today's hardcoded default chain
    # byte-for-byte. Door-phone contact schema (no apartment-book
    # keys observed on this class).
    field_aliases={"schedule_relay": DEFAULT_USER_FIELD_ALIASES},
    schema_shapes={"contact": SchemaShape.DOOR_PHONE},
    provenance=Provenance(
        test_bench_device_id="maintainer's bench unit",
        firmware_version="916.30.10.114",
        library_version=LIB_VERSION,
        observed_at=OBSERVED_AT,
    ),
)


__all__ = ["X915S_CURRENT", "X916_BASELINE"]
