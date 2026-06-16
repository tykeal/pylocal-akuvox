<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: Refactor device.py Under Aislop Size Limit

**Feature Branch**: `011-device-internal-split`
**Created**: 2026-06-16
**Status**: Draft
**Input**: Issue #142 — `aislop scan` flags
`src/pylocal_akuvox/device.py` (952 lines on the issue baseline/current
display, with 951 source lines counted by `splitlines()`) with
`complexity/file-too-large` against the project's 400-line threshold.
This specification describes a non-breaking internal split that keeps
the public `AkuvoxDevice` class and `pylocal_akuvox.device` import path
intact.

## Overview

`src/pylocal_akuvox/device.py` is the high-level async facade for the
library. It currently owns connection lifecycle, capability-profile
initialisation, capability gating, probe/matrix merge, relay adapter
dispatch, and every domain wrapper (users, contacts, groups,
schedules, relays, logs, config). That aggregation pushes the file far
past the 400-line aislop threshold even though most method bodies are
thin capability-gated delegations to already-focused service modules.

This refactor is **NON-BREAKING**. Unlike specs 009 and 010, the
`pylocal_akuvox.device` subpath is preserved. The public class
`AkuvoxDevice` remains defined in `src/pylocal_akuvox/device.py`, and
top-level `from pylocal_akuvox import AkuvoxDevice` continues to resolve
through `src/pylocal_akuvox/__init__.py` exactly as it does today.
Only internal helpers, constants, internal protocols/type aliases, and
possibly internal mixins (if needed as a last resort) move to sibling
underscore-prefixed `_device_*.py` modules.

The implementation should prefer keeping `AkuvoxDevice` as one class in
`device.py` with public method signatures as thin wrappers that call
free functions in the new helper modules. Internal mixins are allowed
only if the free-function approach cannot keep all affected modules
under 400 lines without contorting the code, and only if the mixin
boundaries preserve `self` invariants cleanly.

## Background and Evidence

Current `src/pylocal_akuvox/device.py` concerns, inventoried from live
`main` before authoring this spec:

1. **Module setup and fallback profile** — imports,
   `_DEVICE_NOT_IN_MATRIX_NOTE`, `_conservative_empty_profile` (~70
   lines).
2. **Facade state and lifecycle** — `AkuvoxDevice.__init__`,
   `capabilities`, `_require_capabilities`, `__aenter__`, `__aexit__`,
   `get_info`, `get_status` (~240 lines including docstrings).
3. **Probe bridge and merge** — `probe_capabilities`,
   `_merge_probe_with_matrix` (~110 lines).
4. **User wrappers** — `add_user`, `list_users`, `modify_user`,
   `delete_user` (~100 lines).
5. **Relay wrappers and adapter dispatch** — `trigger_relay`,
   `_resolve_override_adapter`, `_resolve_default_adapter`,
   `get_relay_status` (~180 lines).
6. **Configuration wrappers** — `get_device_config`,
   `set_device_config` (~20 lines).
7. **Schedule wrappers** — `add_schedule`, `list_schedules`,
   `modify_schedule`, `delete_schedule` (~110 lines).
8. **Group wrappers** — `list_groups`, `add_group`, `modify_group`,
   `delete_group` (~50 lines).
9. **Contact wrappers** — `list_contacts`, `add_contact`,
   `modify_contact`, `delete_contact` (~85 lines).
10. **Log wrappers** — `get_door_logs`, `get_call_logs` (~20 lines).

Splitting helpers along these natural cohesion boundaries lets each
module stay below the 400-line threshold while preserving the public
facade in `device.py`.

## User Scenarios & Testing

### User Story 1 — Public imports remain stable (Priority: P1)

A library consumer importing `AkuvoxDevice` from either the top-level
package or the `pylocal_akuvox.device` subpath sees no import change and
no runtime behavior change.

**Why this priority**: This is the explicit difference from specs 009
and 010. The selected approach is `keep_class_intact`; any deleted
`device.py` file or removed `pylocal_akuvox.device` import path would be
a regression.

**Independent Test**: Extend
`tests/unit/test_capability_module_layout.py` with device-specific
assertions that import `pylocal_akuvox.device`, assert it has
`AkuvoxDevice`, and assert identity with `pylocal_akuvox.AkuvoxDevice`.

**Acceptance Scenarios**:

1. **Given** `from pylocal_akuvox import AkuvoxDevice`, **When** the
   import executes post-refactor, **Then** it succeeds and returns the
   same class object as today.
2. **Given** `from pylocal_akuvox.device import AkuvoxDevice`, **When**
   the import executes post-refactor, **Then** it succeeds and returns
   the same class object as the top-level export.
3. **Given** `importlib.import_module("pylocal_akuvox.device")`, **When**
   the import executes post-refactor, **Then** it succeeds; no
   `pytest.raises(ModuleNotFoundError)` is used for this module.

---

### User Story 2 — Device behavior is unchanged (Priority: P1)

A consumer using any existing `AkuvoxDevice` public method observes the
same signature, return type, exception contract, capability-gating
behavior, network call ordering, cached-info behavior, and relay adapter
selection behavior as before the split.

**Why this priority**: The refactor is motivated only by source layout
and maintainability. It must not alter device semantics.

**Independent Test**: Run the full test suite (`uv run pytest tests/`)
and targeted device/probe/layout tests. The implementation may rewrite
private imports in white-box tests if helpers move, but assertion logic
and expected behavior do not change.

**Acceptance Scenarios**:

1. **Given** a test that previously passed for `add_user`, `list_users`,
   `trigger_relay`, `probe_capabilities`, lifecycle cleanup, or cached
   `get_info`, **When** the same test runs post-refactor, **Then** it
   still passes without expected-value changes.
2. **Given** a capability is `UNSUPPORTED` or `UNKNOWN`, **When** a
   gated public method is called post-refactor, **Then** the same
   `AkuvoxUnsupportedError` reason and capability metadata are produced
   as today.
3. **Given** `examples/mvp_test.py`, **When** its existing smoke tests
   run post-refactor, **Then** the MVP script remains importable and its
   mocked smoke behavior still passes.

---

### User Story 3 — Maintainers find focused helper modules (Priority: P2)

A maintainer editing relay dispatch, schedule wrappers, or lifecycle
cleanup opens a small `_device_*.py` helper module with one cohesive
responsibility rather than navigating the 952-line facade file.

**Why this priority**: Developer experience and aislop compliance are
the reason for the change, but public behavior preservation is higher
priority.

**Independent Test**:
`uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'`
reports zero `complexity/file-too-large` findings.

**Acceptance Scenarios**:

1. **Given** any affected module in the `--include` list, **When** aislop
   scans it, **Then** no module exceeds 400 lines.
2. **Given** a maintainer writing a white-box test for relay adapter
   resolution, **When** they import from `_device_relays.py`, **Then**
   the internal helper is available without importing from a public
   facade shim.
3. **Given** automatic import sorting by ruff/isort, **When** imports are
   rewritten for helper extraction, **Then** import-block reordering is
   permitted and is not treated as an unrelated change.

## Functional Requirements

### FR-001: `AkuvoxDevice` remains in `device.py`

The public `AkuvoxDevice` class remains defined in
`src/pylocal_akuvox/device.py`. The implementation must not delete
`device.py`, replace it with an import-only shim, or move the class
definition to another module.

### FR-002: `pylocal_akuvox.device` remains importable

`import pylocal_akuvox.device` must succeed post-refactor. The module
must expose `AkuvoxDevice` as an attribute.

### FR-003: Top-level and subpath imports both resolve

Both supported import forms continue to resolve to the same class object:

```python
from pylocal_akuvox import AkuvoxDevice
from pylocal_akuvox.device import AkuvoxDevice as DeviceFromSubpath
assert AkuvoxDevice is DeviceFromSubpath
```

`src/pylocal_akuvox/__init__.py` already re-exports
`AkuvoxDevice` from `pylocal_akuvox.device`; that public surface remains
unchanged.

### FR-004: Public method contracts are preserved

Every existing public `AkuvoxDevice` method retains the same signature,
return type, async/sync nature, exception contract, capability-gating
behavior, and observable network behavior. This includes:

- `capabilities`
- `probe_capabilities`
- `get_info`
- `get_status`
- `add_user`, `list_users`, `modify_user`, `delete_user`
- `trigger_relay`, `get_relay_status`
- `get_device_config`, `set_device_config`
- `add_schedule`, `list_schedules`, `modify_schedule`,
  `delete_schedule`
- `list_groups`, `add_group`, `modify_group`, `delete_group`
- `list_contacts`, `add_contact`, `modify_contact`, `delete_contact`
- `get_door_logs`, `get_call_logs`

Private helper placement may change, but public method behavior must not.

### FR-005: Internal helpers move to `_device_*.py` siblings

Extracted code moves only to sibling underscore-prefixed modules under
`src/pylocal_akuvox/` (for example `_device_profiles.py` or
`_device_relays.py`). No extracted helper is added to top-level
`pylocal_akuvox.__all__`. New helpers remain internal and may be
free functions, internal protocols/type aliases, or internal mixins if
strictly justified.

### FR-006: Affected modules stay under 400 lines

Every affected module, including the retained `device.py`, must be under
the 400-line aislop `complexity/file-too-large` threshold after the
implementation. Estimated post-refactor sizes:

| Module | Estimated lines | Cohesion rationale |
|---|---:|---|
| `device.py` | ~360-390 | Public `AkuvoxDevice` class, constructor, properties, public method signatures, and thin delegation only |
| `_device_profiles.py` | ~130-170 | Conservative fallback profile and matrix/probe merge helpers |
| `_device_runtime.py` | ~150-190 | Internal device protocol, lifecycle enter/exit, cached info/status helpers, capability requirement helper |
| `_device_users.py` | ~100-140 | User CRUD delegation and field-alias selection |
| `_device_relays.py` | ~160-220 | Relay validation, adapter dispatch, override/default adapter resolution, relay status |
| `_device_access.py` | ~180-260 | Schedule and group access-management delegation |
| `_device_contacts.py` | ~100-140 | Contact list/add/modify/delete delegation and schema-shape selection |
| `_device_config_logs.py` | ~80-120 | Device config get/set plus door/call log delegation |

The implementer may adjust helper module names or combine/split modules
if live line counts show a better natural boundary, but all final files
must remain below 400 lines.

### FR-007: Aislop scan is clean with comma-separated include

The implementation must validate affected file sizes with the
comma-separated `--include` form, never positional filenames:

```bash
uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'
```

The command must report zero `complexity/file-too-large` findings for
the affected modules. If module names change, update only the comma-
separated include list accordingly.

### FR-008: Tests and coverage do not regress

The full suite must remain at or above the current collected test count
(680 tests on the issue baseline) and preserve the current 100% branch
coverage requirement. Test assertion semantics must not be weakened.

### FR-009: Layout assertions are extended in the existing file

Extend the existing `tests/unit/test_capability_module_layout.py` rather
than creating a parallel layout test file. Required additions:

1. `test_device_subpath_remains_importable` —
   `importlib.import_module("pylocal_akuvox.device")` succeeds.
2. `test_device_subpath_exports_akuvox_device` —
   `getattr(module, "AkuvoxDevice") is pylocal_akuvox.AkuvoxDevice`.
3. `test_device_public_symbol_in_top_level_all` — `"AkuvoxDevice"` is
   still present in `pylocal_akuvox.__all__`.

This is intentionally the inverse of specs 009/010: do **not** use
`pytest.raises(ModuleNotFoundError)` for `pylocal_akuvox.device`.

### FR-010: Pre-PR import and stale-phrase sweep

Before opening the implementation PR, run and document the result of:

```bash
grep -rn "from pylocal_akuvox.device" src/ tests/ docs/
```

Because the path is preserved, consuming-code changes are not expected;
the sweep documents that public `AkuvoxDevice` imports remain valid.
The live source currently also has white-box test imports of private
helpers from `pylocal_akuvox.device` (notably
`_DEVICE_NOT_IN_MATRIX_NOTE` and `_merge_probe_with_matrix` in
`tests/unit/test_capability_probe.py`). The implementation must either
rewrite those private white-box imports to the new owning helper module
or leave explicit compatibility aliases in `device.py`; do not assume
all grep hits are public imports. Also sweep for stale phrases such as
"monolithic", "all in one file", and "single device module" in modified
source, tests, and docs, and update any phrasing that becomes inaccurate
after the split.

### FR-011: RST literal and changelog hygiene

Any modified RST/docstring multi-line literals must use indented `::`
literal blocks rather than multi-line inline `` ``...`` `` spans. If the
implementation adds a changelog section header, it must use the sibling
level `^^^^^^^^^^^^^^^^` underline depth. For this non-breaking refactor,
a single bullet under an Unreleased `Changed` section is sufficient; if
`Changed` is absent, create it at sibling depth with the same
`^^^^^^^^^^^^^^^^` underline style. No "Breaking changes" subsection is
added for issue #142.

### FR-012: Bare `ModuleNotFoundError` rule is carried forward

Specs 009/010 require bare `pytest.raises(ModuleNotFoundError)` for
removed subpaths, never `(ModuleNotFoundError, ImportError)`. For this
spec, that rule is still carried forward for any removed internal
subpath test the implementer might add, but it does **not** apply to
`pylocal_akuvox.device` because that module remains importable and must
be asserted via successful `importlib.import_module`.

### FR-013: Contract import lists are revalidated against live source

Before creating helper modules or rewriting imports, revalidate every
planned helper import list against the live source. Do not blindly copy
symbol lists from this spec into module `__all__` blocks or tests. The
retro from issue #141 applies: a stale tasks entry listed `_extract_items`
where the contract correctly excluded it, which would have caused ruff
F401. Live-source validation is mandatory before module creation.

### FR-014: Automatic import-block reordering is permitted

Any "no other change" or "behavior unchanged" implementation guidance
must carve out automatic import-block reordering by ruff/isort. Import
sorting may reorder imports after extraction and is not considered an
unrelated behavioral change.

### FR-015: Implementation commit is non-breaking

The implementation commit subject must not contain `!`, and the
changelog must not add a "Breaking changes" entry for this issue. A
routine subject such as `Refactor(device): Split internal helpers` is
appropriate, provided it stays within repository commit-length rules.

## Inventory and Proposed Module Assignment

The following inventory covers every current top-level helper, constant,
class method, and type-alias/protocol category in `device.py` and assigns
each item to its intended post-refactor home.

| Current symbol | Lines | Kind | Proposed post-refactor owner | Notes |
|---|---:|---|---|---|
| `_DEVICE_NOT_IN_MATRIX_NOTE` | 43-48 | constant | `_device_profiles.py` | Used only to build the fallback `DeviceCapabilities` note |
| `_conservative_empty_profile(info)` | 51-69 | helper | `_device_profiles.py` | Preserve exact fallback profile semantics and note key |
| `AkuvoxDevice` | 72-872 | public class | `device.py` | Class definition remains in `device.py`; no public move |
| `AkuvoxDevice.__init__` | 75-120 | public constructor | `device.py` | Owns `_http`, `_capabilities`, `_info`, `attempt_unknown_capability` initialisation |
| `AkuvoxDevice.capabilities` | 123-138 | public property | `device.py` | Returns cached profile; may keep concise docstring |
| `AkuvoxDevice._require_capabilities` | 140-169 | private method | thin method in `device.py` delegating to `_device_runtime.require_capabilities` | Keep lifecycle error type/message semantics |
| `AkuvoxDevice.probe_capabilities` | 171-205 | public async method | `device.py` wrapper + `_device_profiles.merge_probe_with_matrix` | Public method stays; helper performs merge |
| `AkuvoxDevice.__aenter__` | 207-253 | public async context method | `device.py` wrapper + `_device_runtime.enter_device` | Preserve close-on-failed-discovery shield/suppress semantics |
| `AkuvoxDevice.__aexit__` | 255-280 | public async context method | `device.py` wrapper + `_device_runtime.exit_device` | Preserve cached state reset in `finally` |
| `AkuvoxDevice.get_info` | 282-302 | public async method | `device.py` wrapper + `_device_runtime.get_info` | Preserve cached info after successful enter |
| `AkuvoxDevice.get_status` | 304-311 | public async method | `device.py` wrapper + `_device_runtime.get_status` | Not capability-gated |
| `AkuvoxDevice.add_user` | 313-350 | public async method | `device.py` wrapper + `_device_users.add_user` | Preserve default alias fallback and kwargs |
| `AkuvoxDevice.list_users` | 352-362 | public async method | `device.py` wrapper + `_device_users.list_users` | Pass current capabilities to service |
| `AkuvoxDevice.modify_user` | 364-399 | public async method | `device.py` wrapper + `_device_users.modify_user` | Preserve optional field semantics and alias fallback |
| `AkuvoxDevice.delete_user` | 401-409 | public async method | `device.py` wrapper + `_device_users.delete_user` | Gate then delegate |
| `AkuvoxDevice.trigger_relay` | 411-474 | public async method | `device.py` wrapper + `_device_relays.trigger_relay` | Preserve validation before dispatch and adapter override behavior |
| `AkuvoxDevice._resolve_override_adapter` | 476-525 | private method | `_device_relays.resolve_override_adapter` | May remain as thin private compatibility method if tests import/call it |
| `AkuvoxDevice._resolve_default_adapter` | 527-577 | private method | `_device_relays.resolve_default_adapter` | May remain as thin private compatibility method if tests import/call it |
| `AkuvoxDevice.get_relay_status` | 579-587 | public async method | `device.py` wrapper + `_device_relays.get_relay_status` | Gate then delegate |
| `AkuvoxDevice.get_device_config` | 589-597 | public async method | `device.py` wrapper + `_device_config_logs.get_device_config` | Gate then delegate |
| `AkuvoxDevice.set_device_config` | 599-607 | public async method | `device.py` wrapper + `_device_config_logs.set_device_config` | Preserve settings dict contract |
| `AkuvoxDevice.add_schedule` | 609-652 | public async method | `device.py` wrapper + `_device_access.add_schedule` | Preserve all keyword-only schedule fields |
| `AkuvoxDevice.list_schedules` | 654-662 | public async method | `device.py` wrapper + `_device_access.list_schedules` | Gate then delegate |
| `AkuvoxDevice.modify_schedule` | 664-709 | public async method | `device.py` wrapper + `_device_access.modify_schedule` | Preserve optional field semantics |
| `AkuvoxDevice.delete_schedule` | 711-719 | public async method | `device.py` wrapper + `_device_access.delete_schedule` | Gate then delegate |
| `AkuvoxDevice.list_groups` | 721-733 | public async method | `device.py` wrapper + `_device_access.list_groups` | Group methods share access-management module with schedules |
| `AkuvoxDevice.add_group` | 735-743 | public async method | `device.py` wrapper + `_device_access.add_group` | Gate then delegate |
| `AkuvoxDevice.modify_group` | 745-758 | public async method | `device.py` wrapper + `_device_access.modify_group` | Gate then delegate |
| `AkuvoxDevice.delete_group` | 760-768 | public async method | `device.py` wrapper + `_device_access.delete_group` | Gate then delegate |
| `AkuvoxDevice.list_contacts` | 770-784 | public async method | `device.py` wrapper + `_device_contacts.list_contacts` | Pass current capabilities to service |
| `AkuvoxDevice.add_contact` | 786-809 | public async method | `device.py` wrapper + `_device_contacts.add_contact` | Preserve `SchemaShape.DOOR_PHONE` fallback |
| `AkuvoxDevice.modify_contact` | 811-836 | public async method | `device.py` wrapper + `_device_contacts.modify_contact` | Preserve `SchemaShape.DOOR_PHONE` fallback |
| `AkuvoxDevice.delete_contact` | 838-852 | public async method | `device.py` wrapper + `_device_contacts.delete_contact` | Shape-agnostic delete remains gate-only |
| `AkuvoxDevice.get_door_logs` | 854-862 | public async method | `device.py` wrapper + `_device_config_logs.get_door_logs` | Gate then delegate |
| `AkuvoxDevice.get_call_logs` | 864-872 | public async method | `device.py` wrapper + `_device_config_logs.get_call_logs` | Gate then delegate |
| `_merge_probe_with_matrix(matrix, probe)` | 875-951 | helper | `_device_profiles.py` | Preserve 9-cell merge, metadata merge, and note stripping |
| Current type aliases | n/a | none | n/a | No type aliases currently exist in `device.py` |
| Future internal protocol/type alias | n/a | optional internal type support | `_device_runtime.py` or `_device_types.py` | Use only to type helper functions without importing `AkuvoxDevice` back into helpers |

## Proposed Module Breakdown

### `src/pylocal_akuvox/device.py`

Retains the public `AkuvoxDevice` class. The file should contain the
constructor, public property, public method signatures, thin capability
checks/delegation, and any private compatibility methods that must remain
callable on the class. It must not become an import-only shim.

### `src/pylocal_akuvox/_device_profiles.py`

Owns profile-shaping helpers: `_DEVICE_NOT_IN_MATRIX_NOTE`,
`_conservative_empty_profile`, and `_merge_probe_with_matrix` (or public
within-internal-module names without leading underscores if preferred).
This keeps fallback-profile construction and probe/matrix merge rules in
one focused module.

### `src/pylocal_akuvox/_device_runtime.py`

Owns runtime/lifecycle helpers: an optional `_DeviceRuntime` protocol,
`require_capabilities`, `enter_device`, `exit_device`, `get_info`, and
`get_status`. This module isolates cached state handling and the
`__aenter__` failure cleanup contract.

### `src/pylocal_akuvox/_device_users.py`

Owns user CRUD helper functions and user field-alias selection. It
continues delegating to `pylocal_akuvox.users` and preserves the
`DEFAULT_USER_FIELD_ALIASES` fallback.

### `src/pylocal_akuvox/_device_relays.py`

Owns relay trigger validation/dispatch, override/default adapter
resolution, adapter-missing errors, and relay status delegation. Relay
logic stays together because trigger adapter selection is the only
non-standard capability gate in `AkuvoxDevice`.

### `src/pylocal_akuvox/_device_access.py`

Owns schedule and group delegation. These operations are the access-
management collection CRUD surface and have similar gate-then-delegate
shape.

### `src/pylocal_akuvox/_device_contacts.py`

Owns contact list/add/modify/delete delegation and contact schema-shape
selection. Keeping contact shape handling separate avoids coupling it to
user aliases or schedule/group CRUD.

### `src/pylocal_akuvox/_device_config_logs.py`

Owns the small config and log wrappers: device config get/set, door logs,
and call logs. These are simple read/write operational endpoints that do
not need dedicated large modules.

## Implementation Strategy Notes

- Prefer free helper functions that accept concrete dependencies
  (`AkuvoxHttpClient`, `DeviceCapabilities`, `allow_unknown`) or an
  internal protocol describing the required `_http`, `_info`, and
  `_capabilities` attributes. Avoid helper modules importing
  `AkuvoxDevice`, which would create import cycles.
- Keep public wrappers in `device.py` readable. If reducing long
  explanatory docstrings is necessary for the line cap, preserve public
  signatures and behavior; move detailed internal rationale to helper
  docstrings where appropriate.
- Preserve lazy/deferred imports only where they are still useful. If a
  moved helper can use a normal top-level import without cycles and ruff
  accepts it, do so.
- If tests currently exercise private class methods such as
  `_resolve_default_adapter`, either leave thin compatibility methods on
  `AkuvoxDevice` or rewrite white-box tests to the new helper module
  without changing assertions. Revalidate this against live source before
  editing.
- Do not touch `src/` in the spec PR. Source changes belong to the later
  implementation PR.

## Success Criteria

| ID | Criterion | Verification command |
|---|---|---|
| SC-001 | Public top-level import works | `uv run python -c "from pylocal_akuvox import AkuvoxDevice; print(AkuvoxDevice.__name__)"` prints `AkuvoxDevice` |
| SC-002 | Public subpath import works | `uv run python -c "from pylocal_akuvox.device import AkuvoxDevice; print(AkuvoxDevice.__name__)"` prints `AkuvoxDevice` |
| SC-003 | Top-level and subpath identity match | `uv run python -c "import pylocal_akuvox, importlib; m = importlib.import_module('pylocal_akuvox.device'); assert m.AkuvoxDevice is pylocal_akuvox.AkuvoxDevice; print('ok')"` prints `ok` |
| SC-004 | Affected modules are below 400 lines | `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'` reports no `complexity/file-too-large` |
| SC-005 | Layout assertions pass | `uv run pytest tests/unit/test_capability_module_layout.py -v` passes with new device import-preservation tests |
| SC-006 | Full suite green and test count not reduced | `uv run pytest tests/` passes with at least 680 collected tests |
| SC-007 | Branch coverage preserved | Existing coverage command/config reports 100% branch coverage, with no threshold regression |
| SC-008 | MVP smoke remains valid | `uv run pytest tests/unit/test_mvp_test.py tests/integration/test_mvp_smoke.py` passes |
| SC-009 | Pre-PR import sweep documented | `grep -rn "from pylocal_akuvox.device" src/ tests/ docs/` output is reviewed; public `AkuvoxDevice` imports stay valid and private white-box helper imports are either rewritten or intentionally aliased |
| SC-010 | Implementation commit is non-breaking | `git log -1 --format=%s` for the implementation commit contains no `!`, and changelog entry is routine `Changed`/`Refactor`, not `Breaking changes` |

## Out of Scope

- Deleting `src/pylocal_akuvox/device.py` or replacing it with an
  import-only shim.
- Moving the public `AkuvoxDevice` class definition out of `device.py`.
- Removing or breaking the `pylocal_akuvox.device` import path.
- Renaming public methods, changing signatures, changing return types,
  changing async/sync nature, or changing exception contracts.
- Changing capability matrix semantics, probe semantics, relay adapter
  preference order, or unknown-capability opt-in behavior.
- Adding new device features, endpoints, options, or public symbols.
- Adding `!` to commit subjects or documenting issue #142 as a breaking
  change.
- Updating task lists; there are no 011 tasks yet at spec phase.
