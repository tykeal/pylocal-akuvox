<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Capability Profile Module

**Owning module**: `src/pylocal_akuvox/_capability_profile.py`
**Owning tests**: `tests/unit/test_capabilities.py` (dataclass surface),
`tests/unit/test_device.py` (DeviceCapabilities integration),
`tests/unit/test_capability_module_layout.py` (import assertions)

## Public Surface

This module exports three dataclasses that represent a device's
capability profile:

```python
__all__ = ["DeviceCapabilities", "FieldAliases", "Provenance"]
```

### `FieldAliases` (frozen dataclass, kw_only)

Field-name aliasing for a single logical field. Attributes:

- `read: tuple[str, ...]` — names the device uses in read responses
- `write: tuple[str, ...]` — names the device accepts in write payloads

### `Provenance` (frozen dataclass, kw_only)

Matrix-entry metadata. Attributes:

- `test_bench_device_id: str`
- `firmware_version: str`
- `library_version: str`
- `observed_at: str` (ISO-8601 date)

### `DeviceCapabilities` (frozen dataclass, kw_only)

The effective capability profile carried by an `AkuvoxDevice`. Contains
per-capability status mappings, field aliases, schema shapes, notes, and
provenance. Exposes helper methods:

- `status_of(capability: Capability) -> CapabilityStatus`
- `require(capability: Capability) -> None` (raises
  `AkuvoxUnsupportedError` if not supported)

## Top-Level Re-Export

From this module, `DeviceCapabilities` and `FieldAliases` are
re-exported at the package top level. (`SchemaShape` is also a
top-level export but comes from `_capability_types`, not this module.)

- `pylocal_akuvox.DeviceCapabilities` — **yes** (public)
- `pylocal_akuvox.FieldAliases` — **yes** (public)
- `Provenance` — **no** (internal only)

## What This Module Does NOT Export

- `Capability`, `CapabilityStatus`, `SchemaShape` — live in
  `_capability_types`
- `DeviceClassPattern`, `lookup_capabilities` — live in
  `_capability_matching`
- `DEFAULT_USER_FIELD_ALIASES` — lives in `_capability_defaults`

## Dependencies

- `pylocal_akuvox._capability_types` — for `Capability`,
  `CapabilityStatus`, `SchemaShape` (used in type annotations and `status_of` logic)
- `pylocal_akuvox.exceptions` — for `AkuvoxUnsupportedError` (raised by
  `DeviceCapabilities.require()`)
- stdlib: `dataclasses`, `types.MappingProxyType`

## Backward-Compatibility Note

The following old import paths would have resolved to names now in this
module:

| Old path | Symbol | Still public? |
|---|---|---|
| `from pylocal_akuvox.capabilities import FieldAliases` | `FieldAliases` | yes (via top-level) |
| `from pylocal_akuvox.capabilities import Provenance` | `Provenance` | **no** (internal) |
| `from pylocal_akuvox.capabilities import DeviceCapabilities` | `DeviceCapabilities` | yes (via top-level) |

Post-split, the old paths raise `ModuleNotFoundError`. Public consumers
use `from pylocal_akuvox import DeviceCapabilities, FieldAliases`.
Internal code and white-box tests import `Provenance` directly from
`pylocal_akuvox._capability_profile`.
