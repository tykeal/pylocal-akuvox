# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Capability profile helpers for :mod:`pylocal_akuvox.device`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylocal_akuvox._capability_profile import DeviceCapabilities, FieldAliases
from pylocal_akuvox._capability_types import Capability, CapabilityStatus

if TYPE_CHECKING:
    from pylocal_akuvox.models import DeviceInfo

_DEVICE_NOT_IN_MATRIX_NOTE = (
    "Device not in capability matrix. Call "
    "device.probe_capabilities() to enumerate, or set "
    "device.attempt_unknown_capability=True to opt in to "
    "unknown-status operations."
)


def _conservative_empty_profile(info: DeviceInfo) -> DeviceCapabilities:
    """Build the FR-013 fallback profile for an unrecognised device."""
    return DeviceCapabilities(
        device_class=info.model,
        firmware_version=info.firmware_version,
        capabilities={},
        field_aliases={},
        schema_shapes={},
        notes={"device_not_in_matrix": _DEVICE_NOT_IN_MATRIX_NOTE},
    )


def _merge_probe_with_matrix(
    matrix: DeviceCapabilities | None,
    probe: DeviceCapabilities,
) -> DeviceCapabilities:
    """Merge a probe-derived profile on top of a matrix-derived profile."""
    if matrix is None:
        return probe

    merged: dict[Capability, CapabilityStatus] = dict(matrix.capabilities)
    for capability, probe_status in probe.capabilities.items():
        if probe_status is CapabilityStatus.UNKNOWN:
            continue
        merged[capability] = probe_status

    field_aliases = dict(matrix.field_aliases)
    for field, probe_aliases in probe.field_aliases.items():
        matrix_aliases = field_aliases.get(field)
        if matrix_aliases is None:
            field_aliases[field] = probe_aliases
            continue
        field_aliases[field] = FieldAliases(
            read=probe_aliases.read,
            write=probe_aliases.write or matrix_aliases.write,
        )
    schema_shapes = dict(matrix.schema_shapes)
    schema_shapes.update(probe.schema_shapes)
    notes = dict(matrix.notes)
    notes.update(probe.notes)
    notes.pop("device_not_in_matrix", None)

    return DeviceCapabilities(
        device_class=probe.device_class,
        firmware_version=probe.firmware_version,
        capabilities=merged,
        field_aliases=field_aliases,
        schema_shapes=schema_shapes,
        notes=notes,
        provenance=matrix.provenance,
    )
