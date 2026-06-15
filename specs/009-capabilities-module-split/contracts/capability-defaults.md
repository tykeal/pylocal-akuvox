<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Capability Defaults Module

**Owning module**: `src/pylocal_akuvox/_capability_defaults.py`
**Owning tests**: `tests/unit/test_capabilities.py` (constant value),
`tests/unit/test_users.py` (usage in user model),
`tests/unit/test_capability_module_layout.py` (import assertions)

## Public Surface

This module exports a single constant — the default field-alias mapping
used when no device-specific profile overrides it:

```python
__all__ = ["DEFAULT_USER_FIELD_ALIASES"]
```

### `DEFAULT_USER_FIELD_ALIASES` (constant)

Type: `FieldAliases`

The fallback field-alias configuration for user schedule fields. Used by
the user model's payload builder when no device-specific capability
profile provides an override.

## Top-Level Re-Export

This symbol is NOT re-exported at the package top level.

- `DEFAULT_USER_FIELD_ALIASES` — **no** (internal)

## What This Module Does NOT Export

- `Capability`, `CapabilityStatus`, `SchemaShape` — from
  `_capability_types`
- `FieldAliases`, `Provenance`, `DeviceCapabilities` — from
  `_capability_profile`
- `DeviceClassPattern`, `lookup_capabilities` — from
  `_capability_matching`

## Dependencies

- `pylocal_akuvox._capability_profile` — for `FieldAliases` (the type
  of the constant value)

## Backward-Compatibility Note

The following old import path would have resolved to the name now in
this module:

| Old path | Symbol | Still public? |
|---|---|---|
| `from pylocal_akuvox.capabilities import DEFAULT_USER_FIELD_ALIASES` | `DEFAULT_USER_FIELD_ALIASES` | **no** (internal) |

Post-split, the old path raises `ModuleNotFoundError`. Internal code
and white-box tests import directly from
`pylocal_akuvox._capability_defaults`.
