<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Refactor device.py Under Aislop Size Limit

**Input**: Design documents from `/specs/011-device-internal-split/`
**Prerequisites**: spec.md, plan.md. There is no `contracts/` directory on
`main` for spec 011 at task-authoring time.
**Branch**: `011-device-internal-split` (or another non-protected implementation
branch) hosts the future implementation PR. The spec PR (#153), plan PR (#154),
and this tasks artifact each ship as separate documentation PRs.

**Tests are MANDATORY** per constitution §II (TDD). The public
`pylocal_akuvox.device` preservation assertions in
`tests/unit/test_capability_module_layout.py` are authored first and already
pass on `main`. The `_device_*` importability and line-count assertions are
added incrementally in the phases that create those helpers; the final
`device.py` line-count assertion is added when the facade is slimmed below 400
lines.

**Non-breaking invariant**: `src/pylocal_akuvox/device.py` stays present,
`class AkuvoxDevice` stays defined in that file, `pylocal_akuvox.device` stays
importable, and both `from pylocal_akuvox import AkuvoxDevice` and
`from pylocal_akuvox.device import AkuvoxDevice` keep returning the same class
object. Do **not** write `pytest.raises(ModuleNotFoundError)` for
`pylocal_akuvox.device`.

**Atomic commits** per AGENTS.md §"Atomic Commits" + §"Task List Updates Are
Separate Commits": the implementation PR should keep code, changelog, and any
future task-list checkbox flips logically separate. This tasks PR leaves every
checkbox unchecked; checkbox flips ride on the later implementation PR.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no
  incomplete dependencies between them).
- Every task names exact file path(s), a goal, files touched, and acceptance
  criteria.
- Any task saying "extract only these helpers" or "make no other changes" means
  no behavioral changes, modulo automatic ruff/isort import-block reordering and
  ruff format whitespace normalization.

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, `tests/unit/`, `docs/`. Spec
artifacts in `specs/011-device-internal-split/`.

## Live-source validation cheat sheet

Validated against `src/pylocal_akuvox/device.py` on `main` at plan merge
`aa05aee` before authoring this task list. Re-run these checks before the later
implementation, because live source is canonical if line numbers drift.

- Top-level internal symbols currently in `device.py`:
  `_DEVICE_NOT_IN_MATRIX_NOTE` (lines 43-48),
  `_conservative_empty_profile(info)` (51-69), and
  `_merge_probe_with_matrix(matrix, probe)` (875-951).
- `AkuvoxDevice` currently spans lines 72-872 and contains these public methods:
  `capabilities`, `probe_capabilities`, `__aenter__`, `__aexit__`, `get_info`,
  `get_status`, `add_user`, `list_users`, `modify_user`, `delete_user`,
  `trigger_relay`, `get_relay_status`, `get_device_config`,
  `set_device_config`, `add_schedule`, `list_schedules`, `modify_schedule`,
  `delete_schedule`, `list_groups`, `add_group`, `modify_group`,
  `delete_group`, `list_contacts`, `add_contact`, `modify_contact`,
  `delete_contact`, `get_door_logs`, and `get_call_logs`.
- Private methods currently on `AkuvoxDevice`: `_require_capabilities`,
  `_resolve_override_adapter`, `_resolve_default_adapter`.
- `tests/unit/test_capability_probe.py` imports private helpers from
  `pylocal_akuvox.device` at two sites: `_merge_probe_with_matrix` and
  `_DEVICE_NOT_IN_MATRIX_NOTE`. To keep the final `from pylocal_akuvox.device`
  grep count stable, preserve redundant-alias compatibility exports in
  `device.py`, e.g. `from pylocal_akuvox._device_profiles import
  _DEVICE_NOT_IN_MATRIX_NOTE as _DEVICE_NOT_IN_MATRIX_NOTE`.
- Baseline `grep -rn "from pylocal_akuvox.device" src/ tests/ docs/` count is
  12 on `main` at task-authoring time. Final sweep expects the same count unless
  a later live-source change updates the baseline before implementation starts.

---

## Phase 1: Tests first — extend device layout assertions

**Purpose**: Pin the non-breaking public import path before extracting source
code; helper-module layout assertions are added incrementally as helpers land.

- [ ] T001 Extend `tests/unit/test_capability_module_layout.py` with the
  device-layout TDD assertions.

  - **Goal**: Add structural tests for spec 011 before any source extraction.
  - **Files touched**: `tests/unit/test_capability_module_layout.py` only.
  - **Specific assertions** (may be combined into fewer test functions for
    readability):
    1. Import `pylocal_akuvox.device` with `importlib.import_module` and assert
       the module has `AkuvoxDevice`.
    2. Assert `getattr(module, "AkuvoxDevice") is
       pylocal_akuvox.AkuvoxDevice`.
    3. Import `Path` with `from pathlib import Path`, assert
       `module.__file__ is not None`, derive `module_path` from
       `Path(module.__file__)`, and assert the name is `device.py` (or
       `device.*.pyc` when running from bytecode).
    4. Assert `"AkuvoxDevice" in pylocal_akuvox.__all__`.
  - **Incremental layout-test ownership after T001**:
    - Each helper-module extraction phase adds that helper's importability and
      line-count coverage in `tests/unit/test_capability_module_layout.py`. The
      owning task must list that test file under **Files touched** and include a
      layout-test acceptance criterion for the assertions present at that phase.
    - The facade-slimming phase adds `pylocal_akuvox.device` to the line-count
      coverage after the retained facade is below 400 lines. That owning task
      must likewise list `tests/unit/test_capability_module_layout.py` under
      **Files touched** and include the full layout-test acceptance criterion.
  - **Acceptance criteria**:
    - `uv run python -m py_compile tests/unit/test_capability_module_layout.py`
      passes.
    - `uv run pytest tests/unit/test_capability_module_layout.py -q` passes on
      `main` for the initial public import-preservation assertions.
    - No assertion uses `pytest.raises(ModuleNotFoundError)` for
      `pylocal_akuvox.device`.

- [ ] T002 Capture implementation baselines on `main` before the source split.

  - **Goal**: Record comparison numbers for the implementation PR body.
  - **Files touched**: none.
  - **Commands / data to record**:
    - `uv run pytest tests/ --collect-only -q | tail -1` for test count
      (must be at least the current 680-test baseline).
    - `uv run pytest tests/` and the generated `coverage.xml` branch-rate
      (must remain 100%).
    - `wc -l src/pylocal_akuvox/device.py` (record the live output; minor
      drift from spec/plan line-count prose is acceptable).
    - `grep -rn "from pylocal_akuvox.device" src/ tests/ docs/ | wc -l`
      (currently 12).
    - `uv run aislop scan` showing `device.py` as the issue #142
      `complexity/file-too-large` target.
  - **Acceptance criteria**: Baseline values are copied into the implementation
    PR description; no repository file is changed.

---

## Phase 2: Extract `_device_profiles.py`

**Purpose**: Move profile shaping and probe/matrix merge logic into a leaf
helper module while preserving compatibility imports from `device.py`.

- [ ] T003 Create `src/pylocal_akuvox/_device_profiles.py`.

  - **Goal**: Establish the profile helper module with the exact live-source
    profile helpers.
  - **Files touched**: create `src/pylocal_akuvox/_device_profiles.py`.
  - **Specific items extracted from live `device.py`**:
    - `_DEVICE_NOT_IN_MATRIX_NOTE`
    - `_conservative_empty_profile(info: DeviceInfo) -> DeviceCapabilities`
    - `_merge_probe_with_matrix(matrix: DeviceCapabilities | None, probe: DeviceCapabilities) -> DeviceCapabilities`
  - **Imports to add to `_device_profiles.py`**:
    - `from __future__ import annotations`
    - `from pylocal_akuvox._capability_profile import DeviceCapabilities`
    - `from pylocal_akuvox._capability_types import Capability, CapabilityStatus`
    - `from pylocal_akuvox.models import DeviceInfo`
  - **Acceptance criteria**:
    - Bodies are copied without behavioral changes from live `device.py`, modulo
      automatic ruff/isort import-block reordering and ruff format whitespace
      normalization.
    - `__all__` is either omitted or contains only the three owned internal
      names; do not add anything to top-level `pylocal_akuvox.__all__`.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_profiles.py`
      passes.

- [ ] T004 Wire `device.py` to `_device_profiles.py` and remove duplicate
  profile bodies.

  - **Goal**: Make `device.py` call the extracted profile helpers while keeping
    private compatibility exports for live white-box tests.
  - **Files touched**: `src/pylocal_akuvox/device.py` only.
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox._device_profiles import (_DEVICE_NOT_IN_MATRIX_NOTE as _DEVICE_NOT_IN_MATRIX_NOTE, _conservative_empty_profile, _merge_probe_with_matrix)`
  - **Items to remove from `device.py`**:
    - The local `_DEVICE_NOT_IN_MATRIX_NOTE` assignment.
    - The local `_conservative_empty_profile` function body.
    - The local `_merge_probe_with_matrix` function body.
  - **Items to keep working from `pylocal_akuvox.device`**:
    - `_DEVICE_NOT_IN_MATRIX_NOTE`
    - `_merge_probe_with_matrix`
  - **Acceptance criteria**:
    - `tests/unit/test_capability_probe.py` imports do not need to change.
    - `uv run pytest tests/unit/test_capability_probe.py tests/unit/test_device.py -q`
      passes.
    - `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_profiles.py`
      is clean; no F401 from the compatibility import.

---

## Phase 3: Extract `_device_runtime.py` and `_DeviceContext`

**Purpose**: Isolate lifecycle, cached info/status, capability-requirement, and
shared domain-helper context logic.

- [ ] T005 Create `src/pylocal_akuvox/_device_runtime.py`.

  - **Goal**: Provide the internal runtime helpers and common domain context.
  - **Files touched**: create `src/pylocal_akuvox/_device_runtime.py`.
  - **Specific items to create**:
    - `_DeviceContext` frozen, slotted dataclass with
      `client: AkuvoxHttpClient`, `capabilities: DeviceCapabilities`, and
      `allow_unknown: bool`.
    - `_DeviceRuntime` protocol or equivalent explicit state contract for
      helpers that mutate `_http`, `_info`, and `_capabilities`.
    - `require_capabilities(capabilities: DeviceCapabilities | None) -> DeviceCapabilities`.
    - `make_context(client: AkuvoxHttpClient, capabilities: DeviceCapabilities | None, *, allow_unknown: bool) -> _DeviceContext`.
    - `enter_device(device: _DeviceRuntime) -> None`.
    - `exit_device(device: _DeviceRuntime, exc_type, exc_val, exc_tb) -> None`.
    - `get_info(client: AkuvoxHttpClient, cached_info: DeviceInfo | None) -> DeviceInfo`.
    - `get_status(client: AkuvoxHttpClient) -> DeviceStatus`.
  - **Imports to add to `_device_runtime.py`**:
    - `from __future__ import annotations`
    - `import asyncio`, `import contextlib`
    - `from dataclasses import dataclass`
    - `from typing import Protocol` and any needed `TYPE_CHECKING`
    - `from pylocal_akuvox._capability_matching import lookup_capabilities`
    - `from pylocal_akuvox._capability_profile import DeviceCapabilities`
    - `from pylocal_akuvox._device_profiles import _conservative_empty_profile`
    - `from pylocal_akuvox._http import AkuvoxHttpClient`
    - `from pylocal_akuvox.exceptions import AkuvoxConnectionError`
    - `from pylocal_akuvox.models import DeviceInfo, DeviceStatus`
  - **Acceptance criteria**:
    - Lifecycle cleanup preserves the live-source `asyncio.shield` plus
      `contextlib.suppress(BaseException)` semantics.
    - The `AkuvoxConnectionError` message from `_require_capabilities` is
      preserved exactly.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_runtime.py`
      passes.

- [ ] T006 Update runtime methods in `device.py` to delegate to
  `_device_runtime.py`.

  - **Goal**: Replace lifecycle and runtime method bodies with thin wrappers.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Methods to update from live `AkuvoxDevice`**:
    - `_require_capabilities`
    - `__aenter__`
    - `__aexit__`
    - `get_info`
    - `get_status`
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox._device_runtime import (enter_device, exit_device, get_info as _runtime_get_info, get_status as _runtime_get_status, make_context, require_capabilities)`
  - **Imports expected to become removable from `device.py` in this phase**:
    - `import asyncio`
    - `import contextlib`
    - `from pylocal_akuvox._capability_matching import lookup_capabilities`
    - `from pylocal_akuvox.exceptions import AkuvoxConnectionError` if no longer
      referenced by annotations or compatibility code.
  - **Acceptance criteria**:
    - `AkuvoxDevice.__aenter__` still returns `self`.
    - `AkuvoxDevice.__aexit__` still resets `_info` and `_capabilities` in a
      `finally` path.
    - `uv run pytest tests/unit/test_device.py tests/unit/test_capability_module_layout.py -q`
      passes with layout assertions added through the runtime helper phase;
      assertions for later helper modules are not added yet.
    - No behavioral changes beyond extraction, modulo automatic ruff/isort
      import-block reordering and ruff format whitespace normalization.

---

## Phase 4: Extract `_device_users.py`

**Purpose**: Move user CRUD wrappers behind `_DeviceContext` while preserving
capability gates and field-alias fallback behavior.

- [ ] T007 Create `src/pylocal_akuvox/_device_users.py`.

  - **Goal**: Own user CRUD helper functions.
  - **Files touched**: create `src/pylocal_akuvox/_device_users.py`.
  - **Specific helper functions**:
    - `add_user(ctx: _DeviceContext, *, name: str, user_id: str, web_relay: str | None = None, schedule_relay: str, lift_floor_num: str, private_pin: str | None = None, card_code: str | None = None) -> None`
    - `list_users(ctx: _DeviceContext, *, page: int | None = None) -> list[User]`
    - `modify_user(ctx: _DeviceContext, *, id: str, name: str | None = None, user_id: str | None = None, private_pin: str | None = None, card_code: str | None = None, web_relay: str | None = None, schedule_relay: str | None = None, lift_floor_num: str | None = None) -> None`
    - `delete_user(ctx: _DeviceContext, *, id: str) -> None`
  - **Imports to add to `_device_users.py`**:
    - `from __future__ import annotations`
    - `from typing import TYPE_CHECKING`
    - `from pylocal_akuvox import users`
    - `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`
    - `from pylocal_akuvox._capability_types import Capability`
    - `from pylocal_akuvox._device_runtime import _DeviceContext`
    - Under `TYPE_CHECKING`: `from pylocal_akuvox.models import User`
  - **Acceptance criteria**:
    - Each helper performs the same `Capability.USER_*` gate as the live method,
      using `allow_unknown=ctx.allow_unknown`.
    - Add/modify preserve the `schedule_relay` alias lookup with
      `DEFAULT_USER_FIELD_ALIASES` fallback.
    - `list_users` delegates with `capabilities=ctx.capabilities`, matching live
      `device.py` so field-alias parsing remains capability-aware.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_users.py` passes.

- [ ] T008 Update user wrappers in `device.py`.

  - **Goal**: Make public user methods thin wrappers around `_device_users`.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Methods to update**: `add_user`, `list_users`, `modify_user`,
    `delete_user`.
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox import _device_users`
  - **Deferred imports to remove from these methods**:
    - `from pylocal_akuvox import users`
    - `from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES`
  - **Acceptance criteria**:
    - Public signatures and return types are unchanged.
    - Wrappers construct `make_context(self._http, self._capabilities,
      allow_unknown=self.attempt_unknown_capability)` or equivalent once and pass
      it to helpers.
    - `uv run pytest tests/unit/test_users.py tests/unit/test_device.py -q`
      passes.
    - No other behavior changes, modulo automatic ruff/isort import-block
      reordering and ruff format whitespace normalization.

---

## Phase 5: Extract `_device_relays.py`

**Purpose**: Move relay validation, adapter dispatch, resolver errors, and
relay-status delegation together.

- [ ] T009 Create `src/pylocal_akuvox/_device_relays.py`.

  - **Goal**: Own relay trigger adapter selection and relay status helpers.
  - **Files touched**: create `src/pylocal_akuvox/_device_relays.py`.
  - **Specific helper functions**:
    - `trigger_relay(ctx: _DeviceContext, *, num: int, mode: int = 0, level: int = 0, delay: int = 0, adapter: Capability | None = None) -> None`
    - `resolve_override_adapter(capabilities: DeviceCapabilities, adapter: Capability, *, allow_unknown: bool) -> Capability`
    - `resolve_default_adapter(capabilities: DeviceCapabilities) -> Capability`
    - `get_relay_status(ctx: _DeviceContext) -> dict[str, Any]`
  - **Imports to add to `_device_relays.py`**:
    - `from __future__ import annotations`
    - `from typing import Any`
    - `from pylocal_akuvox import relay`
    - `from pylocal_akuvox._capability_profile import DeviceCapabilities`
    - `from pylocal_akuvox._capability_types import Capability, CapabilityStatus`
    - `from pylocal_akuvox._device_runtime import _DeviceContext`
    - `from pylocal_akuvox.capability_adapters import CAPABILITY_TO_VARIANT, RELAY_TRIGGER_ADAPTERS, RELAY_TRIGGER_PREFERENCE, RelayTriggerArgs`
    - `from pylocal_akuvox.exceptions import AkuvoxUnsupportedError, AkuvoxValidationError`
    - `from pylocal_akuvox.relay import _validate_relay_trigger_args`
  - **Acceptance criteria**:
    - Relay validation still runs before adapter dispatch.
    - Override adapter validation still rejects non-relay capabilities with
      `AkuvoxValidationError`.
    - `capability_missing`, `capability_unknown`, and `adapter_missing` reasons
      remain unchanged.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_relays.py` passes.

- [ ] T010 Update relay wrappers and private compatibility methods in
  `device.py`.

  - **Goal**: Delegate relay logic while keeping private resolver methods
    available on `AkuvoxDevice`.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Methods to update**: `trigger_relay`, `_resolve_override_adapter`,
    `_resolve_default_adapter`, `get_relay_status`.
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox import _device_relays`
  - **Imports expected to become removable from `device.py`**:
    - `from pylocal_akuvox.capability_adapters import CAPABILITY_TO_VARIANT, RELAY_TRIGGER_ADAPTERS, RELAY_TRIGGER_PREFERENCE, RelayTriggerArgs`
    - `from pylocal_akuvox.exceptions import AkuvoxUnsupportedError, AkuvoxValidationError`
    - `CapabilityStatus` from `pylocal_akuvox._capability_types` if no longer
      referenced elsewhere in `device.py`.
  - **Acceptance criteria**:
    - `_resolve_override_adapter()` and `_resolve_default_adapter()` remain
      callable methods if white-box tests or downstream internals use them, but
      they delegate directly to `_device_relays`.
    - `uv run pytest tests/unit/test_device.py tests/unit/test_dispatch.py -q`
      passes.
    - No other behavior changes, modulo automatic ruff/isort import-block
      reordering and ruff format whitespace normalization.

---

## Phase 6: Extract `_device_access.py`

**Purpose**: Move schedule and group access-management wrappers.

- [ ] T011 Create `src/pylocal_akuvox/_device_access.py`.

  - **Goal**: Own schedule and group delegation helpers.
  - **Files touched**: create `src/pylocal_akuvox/_device_access.py`.
  - **Specific helper functions**:
    - `add_schedule(ctx: _DeviceContext, *, schedule_type: str, name: str | None = None, week: str | None = None, daily: str | None = None, date_start: str | None = None, date_end: str | None = None, time_start: str | None = None, time_end: str | None = None, sun: str | None = None, mon: str | None = None, tue: str | None = None, wed: str | None = None, thur: str | None = None, fri: str | None = None, sat: str | None = None) -> None`
    - `list_schedules(ctx: _DeviceContext, *, page: int | None = None) -> list[AccessSchedule]`
    - `modify_schedule(ctx: _DeviceContext, *, id: str, name: str | None = None, schedule_type: str | None = None, week: str | None = None, daily: str | None = None, date_start: str | None = None, date_end: str | None = None, time_start: str | None = None, time_end: str | None = None, sun: str | None = None, mon: str | None = None, tue: str | None = None, wed: str | None = None, thur: str | None = None, fri: str | None = None, sat: str | None = None) -> None`
    - `delete_schedule(ctx: _DeviceContext, *, id: str) -> None`
    - `list_groups(ctx: _DeviceContext, *, page: int | None = None) -> list[Group]`
    - `add_group(ctx: _DeviceContext, *, name: str) -> None`
    - `modify_group(ctx: _DeviceContext, *, id: str, name: str) -> None`
    - `delete_group(ctx: _DeviceContext, *, id: str) -> None`
  - **Imports to add to `_device_access.py`**:
    - `from __future__ import annotations`
    - `from typing import TYPE_CHECKING`
    - `from pylocal_akuvox import groups, schedules`
    - `from pylocal_akuvox._capability_types import Capability`
    - `from pylocal_akuvox._device_runtime import _DeviceContext`
    - Under `TYPE_CHECKING`: `from pylocal_akuvox.models import AccessSchedule, Group`
  - **Acceptance criteria**:
    - Each helper preserves the live `Capability.SCHEDULE_*` or
      `Capability.GROUP_*` gate and passes `allow_unknown=ctx.allow_unknown`.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_access.py`
      passes.

- [ ] T012 Update schedule/group wrappers in `device.py`.

  - **Goal**: Delegate access-management public methods to `_device_access`.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Methods to update**: `add_schedule`, `list_schedules`,
    `modify_schedule`, `delete_schedule`, `list_groups`, `add_group`,
    `modify_group`, `delete_group`.
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox import _device_access`
  - **Deferred imports to remove from these methods**:
    - `from pylocal_akuvox import schedules`
    - `from pylocal_akuvox import groups`
  - **Acceptance criteria**:
    - Public signatures remain byte-for-byte compatible except for permissible
      formatting normalization.
    - `uv run pytest tests/unit/test_schedules.py tests/unit/test_groups.py tests/unit/test_device.py -q`
      passes.
    - No other behavior changes, modulo automatic ruff/isort import-block
      reordering and ruff format whitespace normalization.

---

## Phase 7: Extract `_device_contacts.py`

**Purpose**: Move contact wrappers and contact schema-shape selection.

- [ ] T013 Create `src/pylocal_akuvox/_device_contacts.py`.

  - **Goal**: Own contact list/add/modify/delete helpers.
  - **Files touched**: create `src/pylocal_akuvox/_device_contacts.py`.
  - **Specific helper functions**:
    - `list_contacts(ctx: _DeviceContext, *, page: int | None = None) -> list[Contact]`
    - `add_contact(ctx: _DeviceContext, *, name: str, phone: str | None = None, group: str | None = None) -> None`
    - `modify_contact(ctx: _DeviceContext, *, id: str, name: str | None = None, phone: str | None = None, group: str | None = None) -> None`
    - `delete_contact(ctx: _DeviceContext, *, id: str | list[str]) -> None`
  - **Imports to add to `_device_contacts.py`**:
    - `from __future__ import annotations`
    - `from typing import TYPE_CHECKING`
    - `from pylocal_akuvox import contacts`
    - `from pylocal_akuvox._capability_types import Capability, SchemaShape`
    - `from pylocal_akuvox._device_runtime import _DeviceContext`
    - Under `TYPE_CHECKING`: `from pylocal_akuvox.models import Contact`
  - **Acceptance criteria**:
    - Each helper preserves the matching `Capability.CONTACT_*` gate and passes
      `allow_unknown=ctx.allow_unknown`.
    - `add_contact` and `modify_contact` preserve the
      `SchemaShape.DOOR_PHONE` fallback.
    - `list_contacts` delegates with `capabilities=ctx.capabilities`, matching
      live `device.py` so contact schema parsing remains capability-aware.
    - `delete_contact` remains shape-agnostic and gate-only.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_contacts.py`
      passes.

- [ ] T014 Update contact wrappers in `device.py`.

  - **Goal**: Delegate contact public methods to `_device_contacts`.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Methods to update**: `list_contacts`, `add_contact`, `modify_contact`,
    `delete_contact`.
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox import _device_contacts`
  - **Deferred imports to remove from these methods**:
    - `from pylocal_akuvox import contacts`
    - `from pylocal_akuvox._capability_types import SchemaShape`
  - **Acceptance criteria**:
    - `uv run pytest tests/unit/test_contacts.py tests/unit/test_device.py -q`
      passes.
    - No public import paths change.
    - No other behavior changes, modulo automatic ruff/isort import-block
      reordering and ruff format whitespace normalization.

---

## Phase 8: Extract `_device_config_logs.py`

**Purpose**: Move device configuration and log wrappers into one focused helper.

- [ ] T015 Create `src/pylocal_akuvox/_device_config_logs.py`.

  - **Goal**: Own config get/set and door/call log delegation helpers.
  - **Files touched**: create `src/pylocal_akuvox/_device_config_logs.py`.
  - **Specific helper functions**:
    - `get_device_config(ctx: _DeviceContext) -> DeviceConfig`
    - `set_device_config(ctx: _DeviceContext, settings: dict[str, str]) -> None`
    - `get_door_logs(ctx: _DeviceContext, *, page: int | None = None) -> list[DoorLogEntry]`
    - `get_call_logs(ctx: _DeviceContext, *, page: int | None = None) -> list[CallLogEntry]`
  - **Imports to add to `_device_config_logs.py`**:
    - `from __future__ import annotations`
    - `from typing import TYPE_CHECKING`
    - `from pylocal_akuvox import config, logs`
    - `from pylocal_akuvox._capability_types import Capability`
    - `from pylocal_akuvox._device_runtime import _DeviceContext`
    - Under `TYPE_CHECKING`: `from pylocal_akuvox.models import CallLogEntry, DeviceConfig, DoorLogEntry`
  - **Acceptance criteria**:
    - Each helper preserves the live `Capability.DEVICE_CONFIG_*` or
      `Capability.LOG_*` gate and passes `allow_unknown=ctx.allow_unknown`.
    - `uv run python -m py_compile src/pylocal_akuvox/_device_config_logs.py`
      passes.

- [ ] T016 Update config/log wrappers in `device.py`.

  - **Goal**: Delegate config and log public methods to `_device_config_logs`.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Methods to update**: `get_device_config`, `set_device_config`,
    `get_door_logs`, `get_call_logs`.
  - **Imports to add to `device.py`**:
    - `from pylocal_akuvox import _device_config_logs`
  - **Deferred imports to remove from these methods**:
    - `from pylocal_akuvox import config`
    - `from pylocal_akuvox import logs`
  - **Acceptance criteria**:
    - `uv run pytest tests/unit/test_config.py tests/unit/test_logs.py tests/unit/test_device.py -q`
      passes.
    - No other behavior changes, modulo automatic ruff/isort import-block
      reordering and ruff format whitespace normalization.

---

## Phase 9: Slim retained `device.py` facade

**Purpose**: Ensure the public class remains in `device.py` while the file drops
under the 400-line aislop limit.

- [ ] T017 Trim `device.py` to the retained facade shape.

  - **Goal**: Remove duplicate extraction residue and keep only public wrappers,
    constructor/property state, and deliberate compatibility aliases.
  - **Files touched**: `src/pylocal_akuvox/device.py`.
  - **Required retained items**:
    - `class AkuvoxDevice` remains defined in `device.py`.
    - `AkuvoxDevice.__init__` keeps the same public signature and initializes
      `_http`, `_capabilities`, `_info`, and `attempt_unknown_capability`.
    - All public method signatures listed in the live-source validation cheat
      sheet remain available and async/sync nature is unchanged.
    - `_require_capabilities`, `_resolve_override_adapter`, and
      `_resolve_default_adapter` may remain as thin compatibility methods.
    - `_DEVICE_NOT_IN_MATRIX_NOTE` and `_merge_probe_with_matrix` remain
      importable from `pylocal_akuvox.device` via redundant-alias compatibility
      imports if needed to keep existing private white-box tests unchanged.
  - **Imports expected to keep or add in final `device.py`**:
    - `from pylocal_akuvox._capability_probe import probe_capabilities as _probe_capabilities`
    - `from pylocal_akuvox._capability_profile import DeviceCapabilities`
    - `from pylocal_akuvox._capability_types import Capability`
    - `from pylocal_akuvox._device_profiles import ...`
    - `from pylocal_akuvox._device_runtime import ...`
    - `from pylocal_akuvox import _device_access, _device_config_logs, _device_contacts, _device_relays, _device_users`
    - `from pylocal_akuvox._http import AkuvoxHttpClient`
    - `TYPE_CHECKING` imports for `AuthConfig` and return model types as needed.
  - **Imports expected to be removed from final `device.py` if ruff reports
    unused**:
    - `asyncio`, `contextlib`, `Any`, `lookup_capabilities`,
      `CapabilityStatus`, `CAPABILITY_TO_VARIANT`, `RELAY_TRIGGER_ADAPTERS`,
      `RELAY_TRIGGER_PREFERENCE`, `RelayTriggerArgs`, `AkuvoxConnectionError`,
      `AkuvoxUnsupportedError`, `AkuvoxValidationError`, direct `DeviceInfo`,
      and direct `DeviceStatus` imports, unless still required by annotations or
      compatibility wrappers.
  - **Acceptance criteria**:
    - `wc -l src/pylocal_akuvox/device.py` reports `< 400`.
    - `uv run python -c "from pylocal_akuvox import AkuvoxDevice; from pylocal_akuvox.device import AkuvoxDevice as D; assert AkuvoxDevice is D; print('ok')"`
      prints `ok`.
    - No public behavior changes, modulo automatic ruff/isort import-block
      reordering and ruff format whitespace normalization.

- [ ] T018 Run targeted facade and layout validation after slimming.

  - **Goal**: Prove the retained public import path and line-count assertions are
    green.
  - **Files touched**: none.
  - **Commands**:
    - `uv run pytest tests/unit/test_capability_module_layout.py -q`
    - `uv run pytest tests/unit/test_device.py tests/unit/test_capability_probe.py -q`
    - `uv run python -c "import importlib, pylocal_akuvox; m = importlib.import_module('pylocal_akuvox.device'); assert getattr(m, 'AkuvoxDevice') is pylocal_akuvox.AkuvoxDevice; print('ok')"`
  - **Acceptance criteria**: All commands exit 0; `pylocal_akuvox.device` is a
    successful import, not a removed subpath.

---

## Phase 10: Validation, changelog, and pre-PR sweep

**Purpose**: Run the whole-tree gates, document the non-breaking changelog, and
prepare the implementation PR for review.

- [ ] T019 Run the targeted domain regression matrix.

  - **Goal**: Exercise every extracted domain helper through existing behavior
    tests before full-suite validation.
  - **Files touched**: none.
  - **Command**:
    - `uv run pytest tests/unit/test_users.py tests/unit/test_contacts.py tests/unit/test_schedules.py tests/unit/test_groups.py tests/unit/test_config.py tests/unit/test_logs.py tests/unit/test_dispatch.py tests/unit/test_device.py tests/unit/test_capability_probe.py -q`
  - **Acceptance criteria**: Exit 0; test assertions are not weakened to fit the
    extraction.

- [ ] T020 Run MVP smoke regression tests.

  - **Goal**: Confirm examples and smoke coverage remain importable after the
    internal split.
  - **Files touched**: none.
  - **Command**: `uv run pytest tests/unit/test_mvp_test.py tests/integration/test_mvp_smoke.py -q`
  - **Acceptance criteria**: Exit 0.

- [ ] T021 Run full tests and branch coverage gate.

  - **Goal**: Preserve the current suite size and 100% branch coverage.
  - **Files touched**: none.
  - **Commands**:
    - `uv run pytest tests/ -x -q`
    - `uv run pytest --cov=pylocal_akuvox --cov-branch --cov-report=term-missing tests/`
  - **Acceptance criteria**: Full suite passes, at least 680 tests are collected,
    and branch coverage remains 100%.

- [ ] T022 Run lint and type-check gates.

  - **Goal**: Catch stale imports from the extraction and strict typing issues.
  - **Files touched**: none.
  - **Commands**:
    - `uv run ruff check src/ tests/`
    - `uv run mypy src/`
  - **Acceptance criteria**: Both commands exit 0; no F401 stale imports from
    copied task lists or redundant compatibility exports.

- [ ] T023 Run full pre-commit after staging the implementation files.

  - **Goal**: Let the repository hooks enforce REUSE, ruff, mypy, interrogate,
    aislop, and pytest coverage before commit.
  - **Files touched**: none directly; hooks may auto-format staged files.
  - **Command**: `git add -A && pre-commit run --all-files`
  - **Acceptance criteria**: Exit 0 without `--no-verify`; if hooks modify files,
    stage the modifications and re-run. Do not use `git reset` after hook
    failures.

- [ ] T024 Run explicit affected-module aislop scan with comma-separated
  `--include`.

  - **Goal**: Prove the retained facade and every new helper module are under
    the size threshold using the required include syntax.
  - **Files touched**: none.
  - **Command**:
    - `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'`
  - **Acceptance criteria**: No `complexity/file-too-large` findings appear
    for any listed module in the scan; command exit 0 alone is not sufficient
    because scan output must be reviewed. The comma-separated `--include` form is
    mandatory; do not pass affected files as positional arguments.

- [ ] T025 Add the non-breaking changelog bullet and run the closing pre-PR
  sweep.

  - **Goal**: Document issue #142 as a routine internal refactor and complete the
    final no-stale-import validation before opening the implementation PR.
  - **Files touched**: `docs/changelog.rst`.
  - **Changelog requirements**:
    - Add one bullet under Unreleased `Changed`; if `Changed` is absent, create
      it at sibling depth with `^^^^^^^^^^^^^^^^` underline style.
    - The bullet says the `AkuvoxDevice` implementation was split into focused
      internal `_device_*` helpers while preserving `pylocal_akuvox.device` and
      both public import forms.
    - Include `Refs #142`.
    - Do **not** add a `Breaking changes` subsection for issue #142.
  - **Closing sweep commands**:
    - `grep -rn "from pylocal_akuvox.device" src/ tests/ docs/` — expect the
      same count as the T002 baseline (12 at task-authoring time) because the
      public path is preserved and no consumers should change.
    - `grep -RniE "monolithic|all in one file|single device module" docs/ src/ specs/` — review any spec-artifact hits; there must be 0 inaccurate hits in
      non-spec source or docs modified by the implementation.
    - `grep -RniE "monolithic|all in one file|single device module" src/ tests/ docs/` — additional implementation-tree sweep; zero inaccurate hits in
      modified source, tests, or docs.
    - `pytest tests/ -x` and `uv run pytest tests/ -x` — at least 680 tests
      and 100% branch coverage.
    - `ruff check . && mypy src/` and `uv run ruff check . && uv run mypy src/`
      — clean.
    - `git add -A && pre-commit run --all-files` — rerun after the changelog
      edit so the final staged tree is hook-clean.
    - `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'` — final explicit size scan with comma-separated `--include`; do not use positional file paths.
  - **Acceptance criteria**: Changelog is non-breaking, all closing sweep commands
    pass or are manually reviewed as described, the final staged tree is
    pre-commit clean, and the implementation branch is ready for PR review.

---

## Dependencies

- **T001 → T002**: tests-first, then baseline capture.
- **T003 → T004**: profile module must exist before `device.py` imports it.
- **T005 → T006**: runtime module must exist before runtime wrappers delegate.
- **T007 → T008**: user helper module must exist before user wrappers delegate.
- **T009 → T010**: relay helper module must exist before relay wrappers delegate.
- **T011 → T012**: access helper module must exist before schedule/group wrappers
  delegate.
- **T013 → T014**: contacts helper module must exist before contact wrappers
  delegate.
- **T015 → T016**: config/log helper module must exist before wrappers delegate.
- **T017** depends on T004, T006, T008, T010, T012, T014, and T016 so all helper
  ownership has already moved.
- **T018–T025** depend on T017.

## Parallel-execution opportunities

- Module creation tasks **T007, T009, T011, T013, and T015** can be prepared in
  parallel after T005/T006 establishes `_DeviceContext`, because they touch
  different helper files. Their corresponding `device.py` wiring tasks remain
  sequential to keep facade diffs reviewable.
- Read-only validation tasks **T019–T022** can run in parallel once T018 is
  green, but serial execution is preferred when preserving readable output.

## Coverage Map: FR / SC → Tasks

| Requirement / criterion | Implementing tasks | Verifying tasks |
|---|---|---|
| FR-001 `AkuvoxDevice` remains in `device.py` | T017 | T001, T018, T025 |
| FR-002 `pylocal_akuvox.device` importable | T001, T017 | T018, T025 |
| FR-003 top-level and subpath identity | T001, T017 | T018, T025 |
| FR-004 public method contracts preserved | T004, T006, T008, T010, T012, T014, T016, T017 | T019, T021 |
| FR-005 helpers move to `_device_*.py` siblings | T003, T005, T007, T009, T011, T013, T015 | T001, T018, T024 |
| FR-006 affected modules under 400 lines | T017 | T001, T024 |
| FR-007 comma-separated aislop include | T024 | T025 |
| FR-008 tests and coverage do not regress | T001, T019 | T021 |
| FR-009 layout assertions extended | T001 | T018 |
| FR-010 import and stale-phrase sweep | T002, T025 | T025 |
| FR-011 RST/changelog hygiene | T025 | T025 |
| FR-012 bare `ModuleNotFoundError` rule carried forward | T001 | T018 |
| FR-013 live-source import-list validation | cheat sheet, T003-T017 | T022, T025 |
| FR-014 import-block reordering carve-out | T003-T017 | T022 |
| FR-015 non-breaking implementation commit/changelog | T025 | implementation PR review |

## Anomalies / open questions

None at task-generation time. All helper names, method names, and private
compatibility imports above were validated against the live `device.py` source;
re-run the live-source validation pass before implementation if `main` changes.
