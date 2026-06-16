<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Probe Parsers Module

**Owning module**: `src/pylocal_akuvox/_probe_parsers.py`
**Owning tests**: `tests/unit/test_capability_probe.py` (parser /
recorder tests covering `_step_1_payload`, `_extract_items`, and the
three `_record_*` helpers at lines ~674–1188 post-rewrite),
`tests/unit/test_capability_module_layout.py` (import assertions per
FR-011)

## Internal-Consumer Surface

This module exports the step-1 payload extractor, the generic item
extractor used by all schema-recording helpers, and the three
schema/alias recorders that mutate accumulator dicts in-place.

```python
__all__ = [
    "_step_1_payload",
    "_extract_items",
    "_record_user_aliases",
    "_record_user_schema_keys",
    "_record_contact_shape",
]
```

All five names retain their leading underscore. They are reachable
from `_capability_probe.py` and from white-box tests via
`from pylocal_akuvox._probe_parsers import …`.

### `_step_1_payload(body: str) -> dict[str, Any]`

Decodes and validates the `/api/system/info` envelope. Returns
the inner `data` dict on success. Raises `AkuvoxParseError` on
every failure mode (invalid JSON → chained `__cause__`; missing /
non-int retcode; bool retcode). Behavior preserved verbatim from
lines 212–242 of the pre-split source.

The `bool`-retcode exclusion is preserved (same load-bearing reason
as in `_summarise_system_status` — see
`contracts/probe-classifiers.md`).

### `_extract_items(body: str) -> list[Any] | None`

Returns the list of records under `data.Item` or `data.item`, or
`None` if the body is not parseable / not a JSON object / has
neither key holding a list. Real Akuvox responses use both
PascalCase and lowercase forms across firmware bands; the helper
accepts either to keep the recorders firmware-agnostic. Behavior
preserved verbatim from lines 245–270.

### `_record_user_aliases(field_aliases: dict[str, FieldAliases], body: str) -> None`

Updates `field_aliases["schedule_relay"]` from a user-list body.
Inspects items for any of the three observed schedule-field
aliases (`ScheduleRelay`, `Schedule-Relay`, `Schedule`) and
records them in observed order. Tolerates malformed bodies — never
raises. Behavior preserved verbatim from lines 273–299.

### `_record_user_schema_keys(notes: dict[str, str], body: str) -> None`

Records observed schema-variant keys (`Building`, `Room`,
`EffectiveType`) from a user-list body under
`notes["user_schema_observed_keys"]` (comma-joined sorted list).
Sorting is load-bearing for the byte-equal idempotence guarantee
(SC-002 in `specs/008-capability-matrix/contracts/probe-api.md`,
distinct from this spec's SC-002 about aislop size) — two
probes against an unchanged device must produce identical
`notes` dicts regardless of dict-iteration order at scan time.
Behavior preserved verbatim from lines 302–329.

### `_record_contact_shape(schema_shapes: dict[str, SchemaShape], body: str) -> None`

Updates `schema_shapes["contact"]` based on whether the first
contact item carries an apartment-book-distinctive key (`APTName`
or `APTNum` → `SchemaShape.APARTMENT_BOOK`) or not (→
`SchemaShape.DOOR_PHONE`). Behavior preserved verbatim from
lines 332–354. The single-item probe basis (only `items[0]` is
inspected) is preserved — widening to "any item with apartment
keys" would be a behavior change, which is out of scope.

## Top-Level Re-Export

This module exports nothing at the package top level.

## What This Module Does NOT Export

- The `_ProbeOutcome` enum and marker constants — they live in
  `_probe_outcomes`
- The classifier helpers — they live in `_probe_classifiers`
- The orchestration entry — lives in `_capability_probe`

## Dependencies

- `pylocal_akuvox._capability_profile` — imports `FieldAliases`
  (constructed inside `_record_user_aliases`)
- `pylocal_akuvox._capability_types` — imports `SchemaShape`
  (used inside `_record_contact_shape`)
- `pylocal_akuvox.exceptions` — imports `AkuvoxParseError` (raised
  by `_step_1_payload`)
- stdlib: `json`, `typing.Any`

This module does NOT depend on `_probe_classifiers`. The two are
siblings at the same dependency level under `_capability_probe.py`
(see `research.md` Decision 8).

## Backward-Compatibility Note

The following old import paths would have resolved to names now in
this module:

| Old path | Symbol |
|---|---|
| `from pylocal_akuvox.capability_probe import _step_1_payload` | `_step_1_payload` |
| `from pylocal_akuvox.capability_probe import _extract_items` | `_extract_items` |
| `from pylocal_akuvox.capability_probe import _record_user_aliases` | `_record_user_aliases` |
| `from pylocal_akuvox.capability_probe import _record_user_schema_keys` | `_record_user_schema_keys` |
| `from pylocal_akuvox.capability_probe import _record_contact_shape` | `_record_contact_shape` |

Post-split, all five old paths raise `ModuleNotFoundError`.
White-box tests must use
`from pylocal_akuvox._probe_parsers import …`.

## Behavior-Preservation Guarantee

Post-split, every recorder MUST mutate its accumulator dict
identically to today for the same body input — same observed-order
preservation in `_record_user_aliases`, same sorted-comma-join in
`_record_user_schema_keys`, same first-item inspection in
`_record_contact_shape`. The byte-equal idempotence guarantee
(SC-002 in `specs/008-capability-matrix/contracts/probe-api.md`,
distinct from this spec's SC-002 about aislop size) depends on
all three. Any deviation from cut-paste requires explicit
justification.
