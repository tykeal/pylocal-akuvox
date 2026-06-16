<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Data Model: Capability Probe Module Split

**Feature**: 010-capability-probe-split
**Date**: 2026-06-16

## Scope

This is a pure refactor — no new data model is introduced. The
underlying capability data model is fully specified in
`specs/008-capability-matrix/data-model.md`, and the probe behavior
contract lives in `specs/008-capability-matrix/contracts/probe-api.md` (008 / pre-009). This
document describes the **module layout** (which symbol lives where
post-split) and the **affected-file list** for downstream import
rewrites.

## Module Layout Table

| Symbol | Kind | Today (`capability_probe.py`) | Post-split | Public re-export |
|---|---|---|---|---|
| `_ProbeOutcome` | enum | yes | `_probe_outcomes.py` | **no** (internal) |
| `_NO_HANDLER_MARKERS` | constant (tuple) | yes | `_probe_outcomes.py` | **no** (internal) |
| `_API_UNSUPPORTED_MARKER` | constant (str) | yes | `_probe_outcomes.py` | **no** (internal) |
| `_ACTION_UNSUPPORTED_MARKERS` | constant (tuple) | yes | `_probe_outcomes.py` | **no** (internal) |
| `_extract_message` | function | yes | `_probe_classifiers.py` | **no** (internal) |
| `_summarise_system_status` | function | yes | `_probe_classifiers.py` | **no** (internal) |
| `_classify_response` | function | yes | `_probe_classifiers.py` | **no** (internal) |
| `_outcome_to_status` | function | yes | `_probe_classifiers.py` | **no** (internal) |
| `_step_1_payload` | function | yes | `_probe_parsers.py` | **no** (internal) |
| `_extract_items` | function | yes | `_probe_parsers.py` | **no** (internal) |
| `_record_user_aliases` | function | yes | `_probe_parsers.py` | **no** (internal) |
| `_record_user_schema_keys` | function | yes | `_probe_parsers.py` | **no** (internal) |
| `_record_contact_shape` | function | yes | `_probe_parsers.py` | **no** (internal) |
| `_PROBE_STEP_3_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_PROBE_STEP_4_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_PROBE_STEP_5_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_PROBE_STEP_6_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_PROBE_STEP_7_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_PROBE_STEP_8_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_PROBE_STEP_9_PATH` | constant (str) | yes | `_capability_probe.py` | **no** (internal) |
| `_LATER_STEPS` | constant (tuple) | yes | `_capability_probe.py` | **no** (internal) |
| `probe_capabilities` | async function | yes | `_capability_probe.py` | **no** (no module-level re-export from `pylocal_akuvox.__init__`; the **public consumer-facing handle** is the `AkuvoxDevice.probe_capabilities()` method. Sibling modules — `device.py` and white-box test files — may still `from pylocal_akuvox._capability_probe import probe_capabilities`; see quickstart Step 6) |

**Symbol count**: 22 symbols across 4 modules. None are added to
top-level `pylocal_akuvox.__all__`.

The consumer-facing handle is the `AkuvoxDevice.probe_capabilities`
**method** (not a top-level function), which `device.py` defines and
which delegates to `_capability_probe.probe_capabilities()`. The
`AkuvoxDevice` class itself is already in
`pylocal_akuvox.__all__` (added by spec 002 / device-config), so
the public consumer surface is unchanged.

## Cross-Module Dependencies

Each new module's import dependencies on its siblings and the rest
of the package. Import graph is acyclic (verified in `research.md`
Decision 8).

### `_probe_outcomes.py`

- **Depends on**: stdlib only (`enum`)
- **No sibling imports**
- This is the leaf of the probe-side dependency graph — both
  `_probe_classifiers` and `_capability_probe` depend on it without
  risk of cycles.

### `_probe_classifiers.py`

- **Depends on**:
  - `pylocal_akuvox._probe_outcomes` — for `_ProbeOutcome` and the
    three message-marker constants
  - `pylocal_akuvox._capability_types` — for `CapabilityStatus`
    (used as the return type of `_outcome_to_status`)
  - stdlib: `json`
- **Does NOT import from** `_probe_parsers` (verified in
  `research.md` Decision 8).

### `_probe_parsers.py`

- **Depends on**:
  - `pylocal_akuvox._capability_profile` — for `FieldAliases`
    (constructed inside `_record_user_aliases`)
  - `pylocal_akuvox._capability_types` — for `SchemaShape` (used
    inside `_record_contact_shape`)
  - `pylocal_akuvox.exceptions` — for `AkuvoxParseError` (raised
    by `_step_1_payload`)
  - stdlib: `json`, `typing.Any`
- **Does NOT import from** `_probe_classifiers` (verified in
  `research.md` Decision 8).

### `_capability_probe.py`

- **Depends on**:
  - `pylocal_akuvox._probe_outcomes` — for `_ProbeOutcome` (used
    in step-3 / step-4 side-effect guard:
    `if outcome is _ProbeOutcome.SUPPORTED`)
  - `pylocal_akuvox._probe_classifiers` — for `_classify_response`
    and `_outcome_to_status` and `_summarise_system_status`
  - `pylocal_akuvox._probe_parsers` — for `_step_1_payload`,
    `_record_user_aliases`, `_record_user_schema_keys`,
    `_record_contact_shape`
  - `pylocal_akuvox._capability_profile` — for `DeviceCapabilities`
    (return type) and `FieldAliases` (used in the `field_aliases`
    accumulator)
  - `pylocal_akuvox._capability_types` — for `Capability`,
    `CapabilityStatus`, `SchemaShape`
  - `pylocal_akuvox.exceptions` — for `AkuvoxAuthenticationError`,
    `AkuvoxConnectionError`, `AkuvoxParseError`, `AkuvoxRequestError`
  - `pylocal_akuvox.models` — for `DeviceInfo` (used in
    `DeviceInfo.from_api_response(data)` on step 1)
  - `TYPE_CHECKING`-only:
    `pylocal_akuvox._http.AkuvoxHttpClient` (matching the live
    source today)
  - stdlib: `typing.TYPE_CHECKING`

  After the split, the orchestration module does NOT need direct
  `json` or `typing.Any` imports — both are used only by the
  helpers (`_step_1_payload`, `_extract_items`,
  `_summarise_system_status`, `_extract_message`) which now live
  in `_probe_parsers.py` / `_probe_classifiers.py`. The
  orchestration delegates body-parsing work to those helpers
  rather than calling `json.loads` itself, and uses concrete
  types (no `Any`) in its function signature and accumulator
  annotations.

## Affected-File List for Downstream Import Rewrites

The following files currently import from
`pylocal_akuvox.capability_probe` and must be rewritten to use the
new underscore module paths.

**Source of truth**:

```bash
$ grep -rn -F -e "from pylocal_akuvox.capability_probe" -e "import pylocal_akuvox.capability_probe" src/ tests/ docs/
```

(The `-F` switches grep to fixed-string matching so the literal
dots in `pylocal_akuvox.capability_probe` cannot accidentally match
unrelated characters; the two `-e` patterns cover both `from`-import
and bare-import shapes.)

executed on `main` at SHA `4fc75e8`. Total: **42 import-line hits**
across **2 files** (1 in `device.py`, 41 in
`tests/unit/test_capability_probe.py`).

### Package internals (`src/pylocal_akuvox/`)

| File | Line | Current import | Post-split import |
|---|---|---|---|
| `device.py` | 22 | `from pylocal_akuvox.capability_probe import probe_capabilities as _probe_capabilities` | `from pylocal_akuvox._capability_probe import probe_capabilities as _probe_capabilities` |

This is the **only** package-internal importer. Per FR-001, no other
change to `device.py` is permitted under this spec.

### Test files (`tests/unit/`)

`tests/unit/test_capability_probe.py` is the only test file with
imports of the dropped subpath. **41 import-lines** require
rewriting (1 static top-of-file at line 29 plus 40 in-test deferred
imports). Grouped by target underscore module (see Module Layout
Table above for symbol → module mapping):

**Additionally**: line 4 of the same test file currently reads
`"""Tests for the capability probe in ``pylocal_akuvox.capability_probe``."""`
and MUST be updated post-split to either reference
`pylocal_akuvox._capability_probe` (the new internal module) or to
drop the module path entirely (e.g.,
`"""Tests for the capability probe (capability profile runtime side)."""`).
The implementer SHOULD prefer the latter — the test file's purpose is
behavior coverage, not module-shape pinning, so the module path adds
nothing. Module-shape pinning lives in
`tests/unit/test_capability_module_layout.py`.

#### → `_capability_probe`

| Line | Current import | Post-split import |
|---|---|---|
| 29 | `from pylocal_akuvox.capability_probe import probe_capabilities as _probe_helper` | `from pylocal_akuvox._capability_probe import probe_capabilities as _probe_helper` |

(Top-of-file static import; everything else below is an in-test
deferred import.)

#### → `_probe_classifiers`

| Line | Symbols imported | Post-split source |
|---|---|---|
| 739 | `_classify_response, _ProbeOutcome` | `_classify_response` from `_probe_classifiers`; `_ProbeOutcome` from `_probe_outcomes` (split into two `from` lines) |
| 748 | `_classify_response, _ProbeOutcome` | (same as above) |
| 756 | `_classify_response, _ProbeOutcome` | (same as above) |
| 766 | `_classify_response, _ProbeOutcome` | (same as above) |
| 994 | `_summarise_system_status` | `_probe_classifiers` |
| 1008 | `_summarise_system_status` | `_probe_classifiers` |
| 1016 | `_summarise_system_status` | `_probe_classifiers` |
| 1023 | `_summarise_system_status` | `_probe_classifiers` |
| 1036 | `_summarise_system_status` | `_probe_classifiers` |
| 1048 | `_summarise_system_status` | `_probe_classifiers` |

#### → `_probe_outcomes` (split out from the four
`_classify_response, _ProbeOutcome` rewrites above)

The four rewrite lines (739, 748, 756, 766) split each into two
from-lines: one for the classifier, one for `_ProbeOutcome`.

#### → `_probe_parsers`

| Line | Symbols imported | Post-split source |
|---|---|---|
| 773 | `_record_user_aliases` | `_probe_parsers` |
| 782 | `_record_user_aliases` | `_probe_parsers` |
| 791 | `_record_user_aliases` | `_probe_parsers` |
| 800 | `_record_user_aliases` | `_probe_parsers` |
| 809 | `_record_user_aliases` | `_probe_parsers` |
| 820 | `_record_contact_shape` | `_probe_parsers` |
| 829 | `_record_contact_shape` | `_probe_parsers` |
| 838 | `_record_contact_shape` | `_probe_parsers` |
| 847 | `_record_contact_shape` | `_probe_parsers` |
| 866 | `_extract_items` | `_probe_parsers` |
| 875 | `_extract_items` | `_probe_parsers` |
| 884 | `_extract_items` | `_probe_parsers` |
| 893 | `_extract_items` | `_probe_parsers` |
| 900 | `_extract_items` | `_probe_parsers` |
| 907 | `_extract_items` | `_probe_parsers` |
| 914 | `_extract_items` | `_probe_parsers` |
| 921 | `_extract_items` | `_probe_parsers` |
| 929 | `_record_user_aliases` | `_probe_parsers` |
| 940 | `_record_user_schema_keys` | `_probe_parsers` |
| 950 | `_record_contact_shape` | `_probe_parsers` |
| 965 | `_record_contact_shape` | `_probe_parsers` |
| 977 | `_record_contact_shape` | `_probe_parsers` |
| 1122 | `_record_user_schema_keys` | `_probe_parsers` |
| 1142 | `_record_user_schema_keys` | `_probe_parsers` |
| 1152 | `_record_user_schema_keys` | `_probe_parsers` |
| 1161 | `_record_user_schema_keys` | `_probe_parsers` |
| 1170 | `_record_user_schema_keys` | `_probe_parsers` |
| 1179 | `_record_user_schema_keys` | `_probe_parsers` |
| 1188 | `_record_user_schema_keys` | `_probe_parsers` |
| 674 | `_step_1_payload` | `_probe_parsers` |

**Subtotal**: 30 lines target `_probe_parsers`.

### Documentation extensions

| File | Status |
|---|---|
| `docs/_ext/capability_matrix.py` | **No update needed.** Imports only from `_capability_types` and `capability_matrix`; does not touch `capability_probe`. (Verified at lines 30–31 of the live extension.) |
| `docs/api/*.rst` | **No update needed.** None of the API pages reference `pylocal_akuvox.capability_probe`. The probe is documented via `AkuvoxDevice.probe_capabilities` automethod on `device.rst`, which resolves through the `AkuvoxDevice` class and is unaffected by the split. |

### README, quickstart, examples

| File | Status |
|---|---|
| `README.md` | **No update needed.** The single probe reference (line 64: `await device.probe_capabilities()`) uses the public method. |
| `docs/quickstart.rst` | **No update needed.** All probe references (lines 35, 36, 40, 50, 77) use the public method. |
| `examples/mvp_test.py` | **No update needed.** The single probe reference (line 2098: `await device.probe_capabilities()`) uses the public method. |

### Changelog

| File | Status |
|---|---|
| `docs/changelog.rst` | **MUST be updated** per FR-008. New "Breaking changes" subsection bullet under the Unreleased section naming the dropped `pylocal_akuvox.capability_probe` subpath and the migration (use `AkuvoxDevice.probe_capabilities()`). |

### Layout-assertion test

| File | Status |
|---|---|
| `tests/unit/test_capability_module_layout.py` | **MUST be extended** per FR-011. Four new test functions added; module docstring updated to mention spec 010 alongside spec 009. |

## Summary of Affected Files

| Category | Count | Files |
|---|---|---|
| Source files needing import rewrite | 1 | `src/pylocal_akuvox/device.py` (1 line) |
| Test files needing import rewrite | 1 | `tests/unit/test_capability_probe.py` (41 lines) |
| Test files needing extension | 1 | `tests/unit/test_capability_module_layout.py` (4 new test functions) |
| Test files needing docstring fix | 1 | `tests/unit/test_capability_probe.py:4` (module docstring references the dropped subpath; same file as the import-rewrite row above) |
| Documentation files needing update | 1 | `docs/changelog.rst` (new "Breaking changes" bullet) |
| Source files to be deleted | 1 | `src/pylocal_akuvox/capability_probe.py` (entire 465-line file) |
| Source files to be created | 4 | `src/pylocal_akuvox/_probe_outcomes.py`, `_probe_classifiers.py`, `_probe_parsers.py`, `_capability_probe.py` |
| **Total file touch count** | **9** | (4 modified/extended + 1 deleted + 4 created — `device.py`, `test_capability_probe.py` (imports + docstring), `test_capability_module_layout.py`, `docs/changelog.rst`) |
