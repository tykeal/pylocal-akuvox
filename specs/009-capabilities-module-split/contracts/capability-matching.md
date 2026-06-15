<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Capability Matching Module

**Owning module**: `src/pylocal_akuvox/_capability_matching.py`
**Owning tests**: `tests/unit/test_pattern.py` (DeviceClassPattern),
`tests/unit/test_dispatch.py` (lookup_capabilities),
`tests/unit/test_capability_module_layout.py` (import assertions)

## Public Surface

This module exports the pattern-matching and lookup machinery used to
resolve a device's identity to its capability profile from the matrix:

```python
__all__ = ["DeviceClassPattern", "lookup_capabilities"]
```

### `DeviceClassPattern` (frozen dataclass, kw_only)

Matrix key that matches a device class + firmware band. Attributes:

- `model_prefix: str` — device model prefix (e.g., `"916"`, `"2915"`)
- `firmware_band: str` — firmware version pattern (glob, floor, or exact)

Methods:

- `matches(device_info: DeviceInfo) -> bool` — returns whether this
  pattern matches the given device info

Construction validates the firmware-band form.

### `_parse_firmware_segments` (private function)

```python
def _parse_firmware_segments(firmware: str) -> tuple[int, ...] | None: ...
```

Parses a firmware version string into numeric segments for comparison.
Private (single underscore prefix) — not part of any public contract but
importable for white-box testing.

### `lookup_capabilities` (function)

```python
def lookup_capabilities(device_info: DeviceInfo) -> DeviceCapabilities | None: ...
```

Searches the capability matrix for the first matching pattern and
returns the associated `DeviceCapabilities`, or `None` if no match.

Uses a lazy import of `pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX`
inside the function body to preserve the existing circular-dependency
break.

## Top-Level Re-Export

None of this module's symbols are re-exported at the package top level.

- `DeviceClassPattern` — **no** (internal)
- `lookup_capabilities` — **no** (internal)
- `_parse_firmware_segments` — **no** (private)

## What This Module Does NOT Export

- `Capability`, `CapabilityStatus`, `SchemaShape` — from
  `_capability_types`
- `FieldAliases`, `Provenance`, `DeviceCapabilities` — from
  `_capability_profile`
- `DEFAULT_USER_FIELD_ALIASES` — from `_capability_defaults`

## Dependencies

- `pylocal_akuvox._capability_profile` — for `DeviceCapabilities`
  (return type of `lookup_capabilities`)
- `TYPE_CHECKING`-only: `pylocal_akuvox.models` — for `DeviceInfo`
  (type annotation in `matches()` and `lookup_capabilities()`)
- Lazy import (runtime, inside function body):
  `pylocal_akuvox.capability_matrix` — for `CAPABILITY_MATRIX`
  (preserves existing circular-dependency break from current
  `capabilities.py` lines 446–449)
- stdlib: `dataclasses`, `typing`

## Backward-Compatibility Note

The following old import paths would have resolved to names now in this
module:

| Old path | Symbol | Still public? |
|---|---|---|
| `from pylocal_akuvox.capabilities import DeviceClassPattern` | `DeviceClassPattern` | **no** (internal) |
| `from pylocal_akuvox.capabilities import lookup_capabilities` | `lookup_capabilities` | **no** (internal) |

Post-split, the old paths raise `ModuleNotFoundError`. Internal code
and white-box tests import directly from
`pylocal_akuvox._capability_matching`.
