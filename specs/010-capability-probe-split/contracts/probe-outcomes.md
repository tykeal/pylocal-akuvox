<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Probe Outcomes Module

**Owning module**: `src/pylocal_akuvox/_probe_outcomes.py`
**Owning tests**: `tests/unit/test_capability_probe.py` (outcome
discrimination tests at lines 739, 748, 756, 766 post-rewrite),
`tests/unit/test_capability_module_layout.py` (import assertions per
FR-011)

## Internal-Consumer Surface

This module exports the leaf-level vocabulary that the rest of the
probe internals reason over: an enum of discrete probe-step
outcomes and the three message-marker constants used by the
classifier to recognise device-side "unsupported" responses.

```python
__all__ = [
    "_ProbeOutcome",
    "_NO_HANDLER_MARKERS",
    "_API_UNSUPPORTED_MARKER",
    "_ACTION_UNSUPPORTED_MARKERS",
]
```

All four names retain their leading underscore — they remain
internal to the package. They are reachable from internal-consumer
code via `from pylocal_akuvox._probe_outcomes import …` and from
white-box tests via the same path.

### `_ProbeOutcome` (enum.Enum, str values)

Discrete classification of a single probe-step response. Five
members, values stable post-split (verbatim copy of today's
`capability_probe._ProbeOutcome`):

- `SUPPORTED = "supported"`
- `UNSUPPORTED_NO_HANDLER = "unsupported_no_handler"`
- `UNSUPPORTED_API = "unsupported_api"`
- `UNSUPPORTED_ACTION = "unsupported_action"`
- `INDETERMINATE = "indeterminate"`

The values are stable strings (not auto-generated) so that any
test or future debug log that compares an outcome to a literal
string keeps working. New members are additive only; this is a
package-internal enum, but the same additive-only discipline as
the public `Capability` enum applies to avoid regressions in
downstream classification code.

### `_NO_HANDLER_MARKERS` (tuple of str)

Two-element tuple of lowercased substrings that the
`_classify_response` helper greps for in the device's `message`
field to detect the "no handlers for this request" response.
Values verbatim post-split:

```python
_NO_HANDLER_MARKERS = (
    "no handlers for this request",
    "no hanlders for this request",  # device typo (codespell:ignore)
)
```

The duplicated typo'd marker is **load-bearing** — it matches what
the device actually emits on certain firmware. Removing it would
silently downgrade a `UNSUPPORTED_NO_HANDLER` outcome to
`INDETERMINATE`. The `# codespell:ignore` directive must travel
with the constant when it moves to the new module.

### `_API_UNSUPPORTED_MARKER` (str)

Single-element string marker for the "api unsupported" response:

```python
_API_UNSUPPORTED_MARKER = "api unsupported"
```

### `_ACTION_UNSUPPORTED_MARKERS` (tuple of str)

Two-element tuple of lowercased markers for the "unsupported
action" response:

```python
_ACTION_UNSUPPORTED_MARKERS = (
    "unsupported action",
    "unsupport action",  # device typo (codespell:ignore)
)
```

Same load-bearing-typo note as `_NO_HANDLER_MARKERS` applies.

## Top-Level Re-Export

This module exports nothing at the package top level. The four
names above remain underscore-prefixed and are not added to
`pylocal_akuvox.__all__`.

## What This Module Does NOT Export

- The classifier functions (`_extract_message`, `_classify_response`,
  `_summarise_system_status`, `_outcome_to_status`) — they live in
  `_probe_classifiers`
- The parser / recorder helpers (`_step_1_payload`, `_extract_items`,
  `_record_user_aliases`, `_record_user_schema_keys`,
  `_record_contact_shape`) — they live in `_probe_parsers`
- The orchestration entry (`probe_capabilities`) — it lives in
  `_capability_probe`

## Dependencies

- stdlib `enum` only. No sibling-module imports. No third-party
  imports. This is the leaf of the probe-side dependency graph.

## Backward-Compatibility Note

The following old import paths would have resolved to names now in
this module:

| Old path | Symbol |
|---|---|
| `from pylocal_akuvox.capability_probe import _ProbeOutcome` | `_ProbeOutcome` |

(The three marker constants were never imported by name in tests
or elsewhere — they are referenced internally by `_classify_response`
only. They are documented here for completeness.)

Post-split, the old path raises `ModuleNotFoundError`. White-box
tests must use `from pylocal_akuvox._probe_outcomes import _ProbeOutcome`.
