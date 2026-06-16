<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Probe Classifiers Module

**Owning module**: `src/pylocal_akuvox/_probe_classifiers.py`
**Owning tests**: `tests/unit/test_capability_probe.py` (classifier
tests covering all five `_ProbeOutcome` discriminations and the
`_summarise_system_status` token vocabulary at lines ~739–1048
post-rewrite), `tests/unit/test_capability_module_layout.py` (import
assertions per FR-011)

## Internal-Consumer Surface

This module exports four pure response-classification helpers that
operate on raw `(status, body)` tuples and return primitive values
or enum members. None mutate any input. None perform I/O.

```python
__all__ = [
    "_extract_message",
    "_summarise_system_status",
    "_classify_response",
    "_outcome_to_status",
]
```

All four names retain their leading underscore. They are reachable
from internal-consumer code (`_capability_probe.py`) and from
white-box tests via `from pylocal_akuvox._probe_classifiers import …`.

### `_extract_message(body: str) -> str`

Returns the lowercased `message` field from `body`, or `""` for
non-JSON / non-dict / non-string-message bodies. Never raises.
Behavior is byte-for-byte identical to today's
`capability_probe._extract_message`.

### `_summarise_system_status(status: int, body: str) -> str`

Collapses a `/api/system/status` response to a stable summary
token from the vocabulary `{"ok", "retcode_<n>", "unparsable",
"http_<status>"}`. The exact decision tree is preserved verbatim
from the live source (lines 126–161 of pre-split
`capability_probe.py`):

- HTTP non-2xx → `f"http_{status}"`
- HTTP 2xx + non-JSON / non-dict / non-int retcode / bool retcode
  → `"unparsable"`
- HTTP 2xx + retcode 0 → `"ok"`
- HTTP 2xx + non-zero int retcode → `f"retcode_{retcode}"`

The `bool` check (`isinstance(retcode, bool)` exclusion) is
load-bearing: Python `bool` is a subclass of `int`, so without
the exclusion `{"retcode": true}` would pass as a retcode of `1`.
This guard is preserved post-split.

### `_classify_response(status: int, body: str) -> _ProbeOutcome`

Classifies a probe-step response into one of the five
`_ProbeOutcome` values per
`specs/008-capability-matrix/contracts/probe-api.md`. Decision tree preserved verbatim
(lines 164–199 of pre-split source). Calls `_extract_message` for
the marker scan and falls through to a `retcode == 0` check for
the SUPPORTED-vs-INDETERMINATE discrimination.

Step 1 (`/api/system/info`) handles its own auth / parse gates and
does NOT call this helper. Step 2 (`/api/system/status`) uses
`_summarise_system_status` instead. **Steps 3–9** call
`_classify_response`. (The live source's pre-split docstring says
"Steps 2-9 do" — that phrasing is technically imprecise; this
contract corrects it.)

### `_outcome_to_status(outcome: _ProbeOutcome) -> CapabilityStatus`

Maps a `_ProbeOutcome` to the recorded `CapabilityStatus`:

- `SUPPORTED` → `CapabilityStatus.SUPPORTED`
- `INDETERMINATE` → `CapabilityStatus.UNKNOWN`
- All three `UNSUPPORTED_*` → `CapabilityStatus.UNSUPPORTED`

This collapses the 5-valued probe vocabulary to the 3-valued
public capability vocabulary at the boundary between probe internals
and the recorded `DeviceCapabilities` profile.

## Top-Level Re-Export

This module exports nothing at the package top level.

## What This Module Does NOT Export

- The `_ProbeOutcome` enum or marker constants — they live in
  `_probe_outcomes`
- The parser / recorder helpers — they live in `_probe_parsers`
- The orchestration entry — lives in `_capability_probe`

## Dependencies

- `pylocal_akuvox._probe_outcomes` — imports `_ProbeOutcome`,
  `_NO_HANDLER_MARKERS`, `_API_UNSUPPORTED_MARKER`,
  `_ACTION_UNSUPPORTED_MARKERS`
- `pylocal_akuvox._capability_types` — imports `CapabilityStatus`
  (return type of `_outcome_to_status`)
- stdlib: `json`

This module does NOT depend on `_probe_parsers`. The two are
siblings at the same dependency level under `_capability_probe.py`
(see `research.md` Decision 8).

## Backward-Compatibility Note

The following old import paths would have resolved to names now in
this module:

| Old path | Symbol |
|---|---|
| `from pylocal_akuvox.capability_probe import _classify_response` | `_classify_response` |
| `from pylocal_akuvox.capability_probe import _summarise_system_status` | `_summarise_system_status` |
| `from pylocal_akuvox.capability_probe import _extract_message` | `_extract_message` |
| `from pylocal_akuvox.capability_probe import _outcome_to_status` | `_outcome_to_status` |

Post-split, all four old paths raise `ModuleNotFoundError`.
White-box tests must use
`from pylocal_akuvox._probe_classifiers import …`.

## Behavior-Preservation Guarantee

Post-split, every call site that today computes a value via these
four helpers MUST receive a byte-equal result for the same input.
No string vocabulary changes, no decision-tree reordering, no
short-circuit changes. The cut-paste-and-rewrite-imports
implementation strategy is the simplest way to achieve this; any
deviation from it requires explicit justification in the
implementation PR.
