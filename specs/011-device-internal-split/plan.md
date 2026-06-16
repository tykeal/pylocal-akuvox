<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Refactor device.py Under Aislop Size Limit

**Branch**: `011-device-internal-split` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-device-internal-split/spec.md`

## Summary

Issue #142 calls for a **non-breaking** internal split of
`src/pylocal_akuvox/device.py` (952 displayed lines / 951 lines counted by
`splitlines()` on the current `main` baseline, flagged by `aislop scan` for
`complexity/file-too-large` against the 400-line threshold). Unlike specs 009
and 010, the public subpath stays: `pylocal_akuvox.device` remains importable,
`AkuvoxDevice` remains defined in `device.py`, and both
`from pylocal_akuvox import AkuvoxDevice` and
`from pylocal_akuvox.device import AkuvoxDevice` continue to return the same
class object.

The implementation splits cohesive internal logic into seven sibling
underscore-prefixed helper modules while leaving `AkuvoxDevice` as a slim facade
of public method signatures and thin delegations:

- `src/pylocal_akuvox/_device_profiles.py`
- `src/pylocal_akuvox/_device_runtime.py`
- `src/pylocal_akuvox/_device_users.py`
- `src/pylocal_akuvox/_device_relays.py`
- `src/pylocal_akuvox/_device_access.py`
- `src/pylocal_akuvox/_device_contacts.py`
- `src/pylocal_akuvox/_device_config_logs.py`
- `src/pylocal_akuvox/device.py` retained with `AkuvoxDevice` and kept below
  400 lines

This is a pure layout refactor. Public method names, signatures, async nature,
return types, exception semantics, capability-gating behaviour, network call
ordering, and cached-info lifecycle behaviour remain unchanged. The
implementation commit is routine (`Refactor(device): …`), contains no `!`, and
adds only a single `Changed` changelog bullet for issue #142. There is no
"Breaking changes" subsection for this spec.

This `plan.md` PR is documentation only and **does not close #142**. The
implementation PR/commit carries the closing keyword.

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also exercises
Python 3.14 forward.
**Primary Dependencies**: No new runtime or test dependencies. Tooling
(`ruff`, `mypy`, `interrogate`, `aislop`, `sphinx`, `pytest`,
`pytest-asyncio`, `aioresponses`) is unchanged.
**Storage**: N/A — async Python library only; this is a structural refactor.
**Testing**: pytest + pytest-asyncio. Existing behavioural suites remain the
regression net. `tests/unit/test_capability_module_layout.py` is extended with
device-specific import-preservation and line-count assertions.
**Target Platform**: Async Python applications on Linux/macOS/Windows. No
platform-specific change.
**Project Type**: Single Python package under `src/pylocal_akuvox/`.
**Performance Goals**: Runtime behaviour is unchanged. The helpers add module
imports at package import time, but no new I/O, no new async boundary, and no
algorithmic work. The cost is one-time Python module parsing and then cached in
`sys.modules`.

**Constraints**:

- `src/pylocal_akuvox/device.py` stays present and contains the
  `class AkuvoxDevice` definition. It must not become an import-only shim.
- `pylocal_akuvox.device` stays importable. Tests must assert successful import
  with `importlib.import_module`, not `pytest.raises(ModuleNotFoundError)`.
- Top-level `pylocal_akuvox.__all__` keeps `"AkuvoxDevice"`.
- Helper modules are internal only; no `_device_*` symbol is added to top-level
  `__all__`.
- Every affected source module must be below 400 lines after the split.
- The implementation commit subject must not contain `!`; no breaking-change
  changelog entry is added for issue #142.
- `src/` is not touched by this plan PR. Source changes belong to the later
  implementation PR.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2. Re-checked
after the file-by-file phase plan below — see "Post-Design Re-Check".*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | Each new source module gets SPDX headers, a focused module docstring, full type annotations, and no public API expansion. The split reduces the oversized facade while keeping each helper below the 400-line threshold. Existing docstrings may move to helpers if needed; public wrapper docstrings remain accurate. ruff, mypy, interrogate, and aislop must pass. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | Device-layout assertions are authored first locally in `tests/unit/test_capability_module_layout.py`. Against `main`, the import-preservation assertions pass but the `_device_*` module and line-count assertions fail (red). Each extraction phase then makes the relevant assertions green. Existing device/user/relay/access/contact/config/log/probe tests keep behaviour pinned. |
| **III. User Experience Consistency** | PASS | The documented public surface is unchanged: `AkuvoxDevice` remains available from both top-level and `pylocal_akuvox.device`; method signatures and error contracts are preserved. This is explicitly non-breaking and does not require a migration path for public consumers. |
| **IV. Performance Requirements** | PASS | The refactor adds internal function calls and module imports only. No event-loop blocking, network call reordering, extra probe/request calls, or cache invalidation change is introduced. Helper functions receive the same `AkuvoxHttpClient` instance and cached `DeviceCapabilities` state as the current methods use. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | The implementation should land as one atomic refactor commit plus a separate changelog commit only if the implementer chooses to keep docs distinct. Implementation commits must follow `AGENTS.md` co-author guidance and identify the AI model actually used. This plan PR itself lands as one `Docs(spec)` commit with DCO sign-off and a single Claude co-author trailer, per the plan-authoring instructions. New implementation source files later must carry SPDX headers. |
| **VI. Phased Development** | PASS | The implementation is decomposed into ten phases below. Each helper extraction phase has a green checkpoint (compile, targeted tests, ruff, mypy) before the next phase. The order is most-leaf-first so later helpers can depend on earlier runtime/profile contracts without cycles. |

**Result**: All gates pass. **Complexity Tracking** remains empty.

## Phases

### Phase 1 — Extend device layout tests first

**Goal**: Add failing structural assertions before source extraction. This is
the TDD red phase for the module split and the regression pin for the
non-breaking import-path requirement.

**Files created/modified**:

- Modified: `tests/unit/test_capability_module_layout.py`

**Planned assertions**:

- `importlib.import_module("pylocal_akuvox.device")` succeeds.
- `getattr(device_module, "AkuvoxDevice") is pylocal_akuvox.AkuvoxDevice`.
- `"AkuvoxDevice" in pylocal_akuvox.__all__`.
- Each `_device_*.py` helper module imports cleanly via
  `importlib.import_module`.
- `device.py` and all `_device_*.py` helpers are below 400 lines using a
  line-count helper based on `Path(module.__file__).read_text().splitlines()`.
- The test must **not** use `pytest.raises(ModuleNotFoundError)` for
  `pylocal_akuvox.device`.

**Estimated line count for new module(s)**: N/A.

**Acceptance criteria**:

- `uv run python -m py_compile tests/unit/test_capability_module_layout.py`
  passes.
- `uv run pytest tests/unit/test_capability_module_layout.py -q` fails only on
  expected red assertions before source extraction; after the implementation it
  passes.
- `uv run ruff check tests/unit/test_capability_module_layout.py` is clean.
- `uv run mypy tests/unit/test_capability_module_layout.py` is clean, or the
  project-wide mypy gate including tests is clean if that is the configured
  target.

### Phase 2 — Extract `_device_profiles.py`

**Goal**: Move capability-profile shaping into the first leaf helper module.
This phase owns the unrecognised-device fallback and the probe/matrix merge.
Runtime lifecycle can then import this module without depending on `device.py`.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_profiles.py`
- Modified: `src/pylocal_akuvox/device.py`
- Modified as needed: `tests/unit/test_capability_probe.py` private helper
  imports if tests import `_merge_probe_with_matrix` or
  `_DEVICE_NOT_IN_MATRIX_NOTE` from `pylocal_akuvox.device` on the live source
  during implementation.

**Owns**:

- `_DEVICE_NOT_IN_MATRIX_NOTE`
- `_conservative_empty_profile(info: DeviceInfo) -> DeviceCapabilities`
- `_merge_probe_with_matrix(matrix: DeviceCapabilities | None, probe: DeviceCapabilities) -> DeviceCapabilities`

The helper may keep leading-underscore function names if live white-box tests
expect them, but the owning module is `_device_profiles.py`. Revalidate the
exact import list against live source before editing tests or `__all__`.

**Estimated line count for new module(s)**:

- `_device_profiles.py`: ~140-180 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_profiles.py` passes.
- `uv run pytest tests/unit/test_capability_probe.py tests/unit/test_device.py -q` passes.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_profiles.py tests/unit/test_capability_probe.py` is clean.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_profiles.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py'` reports no `complexity/file-too-large` for `_device_profiles.py` and records current `device.py` progress.

### Phase 3 — Extract `_device_runtime.py` and `_DeviceContext`

**Goal**: Isolate runtime/lifecycle concerns and establish the shared helper
signature contract for later domain modules. This phase introduces the small
internal `_DeviceContext` dataclass used by user/relay/access/contact/config/log
helpers.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_runtime.py`
- Modified: `src/pylocal_akuvox/device.py`

**Owns**:

- `_DeviceContext` dataclass (internal helper argument bundle):
  `client: AkuvoxHttpClient`, `capabilities: DeviceCapabilities`,
  `allow_unknown: bool`.
- `require_capabilities(capabilities: DeviceCapabilities | None) -> DeviceCapabilities`.
- `make_context(client: AkuvoxHttpClient, capabilities: DeviceCapabilities | None, *, allow_unknown: bool) -> _DeviceContext`.
- `enter_device(device: _DeviceRuntime) -> None` or an equivalent helper using
  an internal protocol for `_http`, `_info`, `_capabilities`, and `get_info()`.
- `exit_device(device: _DeviceRuntime, exc_type, exc_val, exc_tb) -> None`.
- `get_info(client: AkuvoxHttpClient, cached_info: DeviceInfo | None) -> DeviceInfo`.
- `get_status(client: AkuvoxHttpClient) -> DeviceStatus`.

**Signature decision**: Use `_DeviceContext` for all domain helpers after this
phase. It avoids repeated `(client, capabilities, allow_unknown)` parameter
triples, keeps capability gates consistent, and prevents helpers from touching
`AkuvoxDevice` or optional `_capabilities` directly. Lifecycle helpers still use
an internal protocol or explicit state arguments because they must mutate
`_info` and `_capabilities`; domain helpers receive the frozen context and
cannot mutate facade state.

**Estimated line count for new module(s)**:

- `_device_runtime.py`: ~170-220 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_runtime.py` passes.
- `uv run pytest tests/unit/test_device.py tests/unit/test_capability_module_layout.py -q` passes for runtime-related assertions once this phase is complete.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_runtime.py tests/unit/test_capability_module_layout.py` is clean.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_runtime.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py'` reports no file-too-large finding for the two helper modules.

### Phase 4 — Extract `_device_users.py`

**Goal**: Move user CRUD wrapper logic behind `_DeviceContext` while preserving
capability gates, `DEFAULT_USER_FIELD_ALIASES` fallback, and all public method
signatures.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_users.py`
- Modified: `src/pylocal_akuvox/device.py`

**Owns**:

- `add_user(ctx: _DeviceContext, *, name, user_id, web_relay, schedule_relay, lift_floor_num, private_pin, card_code) -> None`
- `list_users(ctx: _DeviceContext, *, page: int | None = None) -> list[User]`
- `modify_user(ctx: _DeviceContext, *, id, name, user_id, private_pin, card_code, web_relay, schedule_relay, lift_floor_num) -> None`
- `delete_user(ctx: _DeviceContext, *, id: str) -> None`

Each helper performs the same `ctx.capabilities.require(Capability.USER_*,
allow_unknown=ctx.allow_unknown)` gate before delegating to `users.py`.

**Estimated line count for new module(s)**:

- `_device_users.py`: ~100-140 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_users.py` passes.
- `uv run pytest tests/unit/test_users.py tests/unit/test_device.py -q` passes.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_users.py tests/unit/test_users.py tests/unit/test_device.py` is clean.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_users.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_users.py'` reports no file-too-large finding for `_device_users.py`.

### Phase 5 — Extract `_device_relays.py`

**Goal**: Move relay validation, adapter selection, adapter-missing errors, and
relay status delegation together. This is the riskiest domain extraction because
`trigger_relay` is adapter-gated rather than a simple
`DeviceCapabilities.require(...)` wrapper.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_relays.py`
- Modified: `src/pylocal_akuvox/device.py`
- Modified as needed: relay white-box tests if they call private adapter
  resolution helpers on `AkuvoxDevice` in the live source.

**Owns**:

- `trigger_relay(ctx: _DeviceContext, *, num: int, mode: int = 0, level: int = 0, delay: int = 0, adapter: Capability | None = None) -> None`
- `resolve_override_adapter(capabilities: DeviceCapabilities, adapter: Capability, *, allow_unknown: bool) -> Capability`
- `resolve_default_adapter(capabilities: DeviceCapabilities) -> Capability`
- `get_relay_status(ctx: _DeviceContext) -> dict[str, Any]`

`device.py` may retain thin private compatibility methods
`_resolve_override_adapter()` and `_resolve_default_adapter()` if live tests or
internal users call them on the class; those methods should delegate directly to
`_device_relays` and not duplicate logic.

**Estimated line count for new module(s)**:

- `_device_relays.py`: ~170-230 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_relays.py` passes.
- `uv run pytest tests/unit/test_device.py tests/unit/test_dispatch.py -q` passes.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_relays.py tests/unit/test_device.py tests/unit/test_dispatch.py` is clean.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_relays.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_relays.py'` reports no file-too-large finding for `_device_relays.py`.

### Phase 6 — Extract `_device_access.py`

**Goal**: Move access-management collection wrappers: schedules and groups.
These are simple gate-then-delegate helpers with long public signatures that are
best removed from the slim facade in one cohesive phase.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_access.py`
- Modified: `src/pylocal_akuvox/device.py`

**Owns**:

- `add_schedule(ctx: _DeviceContext, *, schedule_type, name, week, daily, date_start, date_end, time_start, time_end, sun, mon, tue, wed, thur, fri, sat) -> None`
- `list_schedules(ctx: _DeviceContext, *, page: int | None = None) -> list[AccessSchedule]`
- `modify_schedule(ctx: _DeviceContext, *, id, name, schedule_type, week, daily, date_start, date_end, time_start, time_end, sun, mon, tue, wed, thur, fri, sat) -> None`
- `delete_schedule(ctx: _DeviceContext, *, id: str) -> None`
- `list_groups(ctx: _DeviceContext, *, page: int | None = None) -> list[Group]`
- `add_group(ctx: _DeviceContext, *, name: str) -> None`
- `modify_group(ctx: _DeviceContext, *, id: str, name: str) -> None`
- `delete_group(ctx: _DeviceContext, *, id: str) -> None`

**Estimated line count for new module(s)**:

- `_device_access.py`: ~190-260 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_access.py` passes.
- `uv run pytest tests/unit/test_device.py -q` plus any dedicated schedule/group tests present in `tests/unit/` pass.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_access.py tests/unit/` is clean for touched files.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_access.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_access.py'` reports no file-too-large finding for `_device_access.py`.

### Phase 7 — Extract `_device_contacts.py`

**Goal**: Move contact wrapper logic and schema-shape selection while preserving
the `SchemaShape.DOOR_PHONE` fallback for add/modify and the shape-agnostic
delete behaviour.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_contacts.py`
- Modified: `src/pylocal_akuvox/device.py`

**Owns**:

- `list_contacts(ctx: _DeviceContext, *, page: int | None = None) -> list[Contact]`
- `add_contact(ctx: _DeviceContext, *, name: str, phone: str | None = None, group: str | None = None) -> None`
- `modify_contact(ctx: _DeviceContext, *, id: str, name: str | None = None, phone: str | None = None, group: str | None = None) -> None`
- `delete_contact(ctx: _DeviceContext, *, id: str | list[str]) -> None`

**Estimated line count for new module(s)**:

- `_device_contacts.py`: ~100-140 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_contacts.py` passes.
- `uv run pytest tests/unit/test_contacts.py tests/unit/test_device.py -q` passes.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_contacts.py tests/unit/test_contacts.py tests/unit/test_device.py` is clean.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_contacts.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_contacts.py'` reports no file-too-large finding for `_device_contacts.py`.

### Phase 8 — Extract `_device_config_logs.py`

**Goal**: Move the small operational wrappers for device configuration and logs
into one focused helper module.

**Files created/modified**:

- Created: `src/pylocal_akuvox/_device_config_logs.py`
- Modified: `src/pylocal_akuvox/device.py`

**Owns**:

- `get_device_config(ctx: _DeviceContext) -> DeviceConfig`
- `set_device_config(ctx: _DeviceContext, settings: dict[str, str]) -> None`
- `get_door_logs(ctx: _DeviceContext, *, page: int | None = None) -> list[DoorLogEntry]`
- `get_call_logs(ctx: _DeviceContext, *, page: int | None = None) -> list[CallLogEntry]`

**Estimated line count for new module(s)**:

- `_device_config_logs.py`: ~80-120 lines.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_config_logs.py` passes.
- `uv run pytest tests/unit/test_device.py -q` plus any dedicated config/log tests present in `tests/unit/` pass.
- `uv run ruff check src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_config_logs.py tests/unit/` is clean for touched files.
- `uv run mypy src/pylocal_akuvox/device.py src/pylocal_akuvox/_device_config_logs.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_config_logs.py'` reports no file-too-large finding for `_device_config_logs.py`.

### Phase 9 — Final `device.py` slimming and compatibility pass

**Goal**: Ensure `device.py` remains the public class home but drops below the
400-line limit. The facade should contain imports, `AkuvoxDevice.__init__`, the
`capabilities` property, public method signatures, thin wrappers that construct
`_DeviceContext` and delegate, and any necessary private compatibility methods.

**Files created/modified**:

- Modified: `src/pylocal_akuvox/device.py`
- Modified as needed: `tests/unit/test_device.py` for private white-box import
  rewrites only; assertion semantics must not change.

**Expected facade shape**:

- `class AkuvoxDevice` remains in `device.py`.
- `pylocal_akuvox.__init__` continues importing `AkuvoxDevice` from
  `pylocal_akuvox.device` unchanged.
- Public wrappers preserve exact signatures and return types.
- Wrappers call `make_context(self._http, self._capabilities, allow_unknown=self.attempt_unknown_capability)` or equivalent once and pass the context into helpers.
- `_require_capabilities()` may remain as a thin method delegating to
  `_device_runtime.require_capabilities` for compatibility and readability.
- Private relay resolver methods may remain as thin delegates if live tests
  require them.

**Estimated line count for new module(s)**: N/A. Target `device.py`: ~330-390
lines, with a hard cap below 400.

**Acceptance criteria**:

- `uv run python -m py_compile src/pylocal_akuvox/device.py` passes.
- `uv run python -c "from pylocal_akuvox import AkuvoxDevice; from pylocal_akuvox.device import AkuvoxDevice as D; assert AkuvoxDevice is D; print('ok')"` prints `ok`.
- `uv run pytest tests/unit/test_device.py tests/unit/test_capability_module_layout.py -q` passes.
- `uv run ruff check src/pylocal_akuvox/device.py tests/unit/test_device.py tests/unit/test_capability_module_layout.py` is clean.
- `uv run mypy src/pylocal_akuvox/device.py` is clean.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'` reports no `complexity/file-too-large` findings.

### Phase 10 — Changelog, pre-PR sweeps, and full validation

**Goal**: Add the non-breaking changelog bullet, run the carry-forward sweeps,
and validate the whole tree before PR review.

**Files created/modified**:

- Modified: `docs/changelog.rst`
- No task-list update in this phase unless `/speckit.tasks` later creates a
  tasks artifact; task-list updates are separate commits by repository policy.

**Changelog strategy**:

- Add a single bullet under Unreleased `Changed` for issue #142.
- If `Changed` does not exist, create it at sibling subsection depth with
  `^^^^^^^^^^^^^^^^` underline style.
- Do **not** add a `Breaking changes` entry for issue #142.

**Estimated line count for new module(s)**: N/A.

**Acceptance criteria**:

- `grep -rn "from pylocal_akuvox.device" src/ tests/ docs/` output reviewed.
  Because the path is preserved, public import rewrites are not expected;
  private helper imports are either already absent or intentionally rewritten to
  owning `_device_*` modules.
- Stale-phrase sweep for `monolithic`, `all in one file`, and similar language
  in modified `src/`, `tests/`, and `docs/` has no inaccurate hits.
- `uv run pytest tests/ -x -q` passes.
- `uv run ruff check src/ tests/` is clean.
- `uv run mypy src/` is clean.
- `git add -A && pre-commit run --all-files` passes without bypass flags.
- `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'` reports no affected file-too-large findings.
- `uv run python -c "import importlib, pylocal_akuvox; m = importlib.import_module('pylocal_akuvox.device'); assert getattr(m, 'AkuvoxDevice') is pylocal_akuvox.AkuvoxDevice; print('ok')"` prints `ok`.

## Migration Order / Extraction Order

The extraction order is most-leaf-first and avoids helper modules importing
`AkuvoxDevice`:

```text
_device_profiles.py                    (leaf: fallback + probe/matrix merge)
        ▲
        │
_device_runtime.py                     (_DeviceContext + lifecycle helpers)
        ▲
        │
        ├── _device_users.py           (uses _DeviceContext)
        ├── _device_relays.py          (uses _DeviceContext + adapter tables)
        ├── _device_access.py          (uses _DeviceContext)
        ├── _device_contacts.py        (uses _DeviceContext)
        └── _device_config_logs.py     (uses _DeviceContext)
        ▲
        │
device.py                              (public facade; class remains here)
```

Detailed ordering rationale:

1. **Tests first**: layout tests pin the non-breaking import contract and the
   final file-size target before any source move.
2. **Profiles before runtime**: `enter_device()` needs the conservative-empty
   fallback, and `probe_capabilities()` needs probe/matrix merge.
3. **Runtime before domain modules**: `_DeviceContext` and
   `make_context()` define the stable helper signature so the rest of the
   extraction does not invent incompatible argument shapes.
4. **Users before relays/access/contacts/config**: user CRUD is the simplest
   context-using module with one additional alias lookup; it proves the pattern.
5. **Relays early**: relay adapter dispatch is the highest-risk domain; moving
   it before the remaining simple wrappers leaves time for focused review.
6. **Access, contacts, config/logs**: these are progressively simpler
   gate-and-delegate extractions once the context pattern is established.
7. **Final device.py pass last**: only after every helper owns its logic should
   docstrings/imports/private compatibility methods be trimmed to get the
   retained class file under 400 lines.

## Helper Signature Contract

All domain helper modules use a common context object rather than receiving
three repeated arguments:

```python
@dataclass(frozen=True, slots=True)
class _DeviceContext:
    """Runtime dependencies for device helper functions."""

    client: AkuvoxHttpClient
    capabilities: DeviceCapabilities
    allow_unknown: bool
```

`device.py` constructs the context from facade state:

```python
ctx = make_context(
    self._http,
    self._capabilities,
    allow_unknown=self.attempt_unknown_capability,
)
```

Helper functions then gate with:

```python
ctx.capabilities.require(Capability.USER_ADD, allow_unknown=ctx.allow_unknown)
```

and delegate with `ctx.client`.

Benefits:

- Keeps helper signatures short and uniform.
- Prevents domain helpers from accepting optional capabilities.
- Avoids importing `AkuvoxDevice` into helper modules and therefore avoids a
  `device.py` ↔ helper cycle.
- Makes the `attempt_unknown_capability` policy explicit and testable as
  `ctx.allow_unknown`.

Trade-off:

- Adds one internal dataclass and one wrapper construction per public method.
  This is negligible and clearer than repeatedly passing
  `(client, capabilities, attempt_unknown_capability)` or a mutable facade
  object.

Lifecycle helpers are the exception: they mutate `_info` and `_capabilities`, so
they use either an internal `_DeviceRuntime` protocol or explicit state-return
contracts rather than `_DeviceContext`.

## Test Strategy

Extend `tests/unit/test_capability_module_layout.py`; do not create a parallel
layout test file. The file already pins specs 009/010 and imports
`importlib`, `pytest`, `pylocal_akuvox`, and capability helper modules. Add a
new device section that is the inverse of the 009/010 subpath-removal tests.

### Required device-layout assertions

```python
def test_device_subpath_remains_importable() -> None:
    """``pylocal_akuvox.device`` remains a public import path."""
    module = importlib.import_module("pylocal_akuvox.device")

    assert getattr(module, "AkuvoxDevice") is pylocal_akuvox.AkuvoxDevice


def test_device_public_symbol_in_top_level_all() -> None:
    """``AkuvoxDevice`` remains part of the top-level public exports."""
    assert "AkuvoxDevice" in pylocal_akuvox.__all__


def test_device_underscore_modules_importable() -> None:
    """Each focused device helper module must import cleanly."""
    for name in (
        "pylocal_akuvox._device_profiles",
        "pylocal_akuvox._device_runtime",
        "pylocal_akuvox._device_users",
        "pylocal_akuvox._device_relays",
        "pylocal_akuvox._device_access",
        "pylocal_akuvox._device_contacts",
        "pylocal_akuvox._device_config_logs",
    ):
        importlib.import_module(name)
```

The implementation may combine the first two assertions if readability is
better, but both facts must be pinned. The key rule is that `device` import is a
successful import assertion, never:

```python
with pytest.raises(ModuleNotFoundError):
    importlib.import_module("pylocal_akuvox.device")
```

### Line-count assertions

The 009/010 layout tests did not include line-count checks, so spec 011 should
add a small helper for the affected device modules:

```python
def _module_line_count(module_name: str) -> int:
    module = importlib.import_module(module_name)
    path = Path(module.__file__ or "")
    return len(path.read_text(encoding="utf-8").splitlines())


def test_device_modules_under_aislop_limit() -> None:
    """The retained facade and helper modules must stay below 400 lines."""
    for name in (
        "pylocal_akuvox.device",
        "pylocal_akuvox._device_profiles",
        "pylocal_akuvox._device_runtime",
        "pylocal_akuvox._device_users",
        "pylocal_akuvox._device_relays",
        "pylocal_akuvox._device_access",
        "pylocal_akuvox._device_contacts",
        "pylocal_akuvox._device_config_logs",
    ):
        assert _module_line_count(name) < 400
```

Use a line-count assertion rather than `os.path.getsize` because aislop's
`file-too-large` threshold is line-count based and the spec inventory uses
line counts. If the implementer prefers `os.path.getsize` for robustness, keep
the explicit `aislop scan --include 'a,b,c,d'` gate as the authoritative size
check.

### Behaviour regression strategy

- Existing `tests/unit/test_device.py` keeps lifecycle, capability gates, relay
  adapter dispatch, cached info, and unsupported-error semantics pinned.
- Existing `tests/unit/test_users.py` and `tests/unit/test_contacts.py` keep
  alias/schema-shape service behaviour pinned.
- Existing schedule/group/config/log coverage, where present, remains
  unchanged; if a public wrapper lacks direct unit coverage, the layout test is
  not a substitute for adding targeted coverage in the implementation phase.
- Existing `tests/unit/test_capability_probe.py` keeps `_merge_probe_with_matrix`
  behaviour pinned after any private import rewrites.
- `examples/mvp_test.py` smoke coverage remains unchanged and should pass in
  the MVP validation gate already used by prior specs.

## Project Structure

### Documentation (this feature)

```text
specs/011-device-internal-split/
├── plan.md              # This file (/speckit.plan output)
└── spec.md              # Feature spec (input)
```

There is no `contracts/` directory on `main` for spec 011 at plan-authoring
time. If `/speckit.tasks` or a later design step adds contracts, revalidate them
against live source before implementation.

### Source code (repository root)

Pre-feature (current state, abbreviated):

```text
src/pylocal_akuvox/
├── __init__.py                  # imports AkuvoxDevice from pylocal_akuvox.device
├── device.py                    # 952 displayed lines; contains AkuvoxDevice + helpers
├── _capability_probe.py
├── _capability_profile.py
├── _capability_types.py
├── capability_adapters.py
├── users.py
├── contacts.py
├── relay.py
├── schedules.py
├── groups.py
├── config.py
└── logs.py
```

Post-feature (only changed area shown):

```text
src/pylocal_akuvox/
├── __init__.py                  # unchanged public AkuvoxDevice re-export
├── device.py                    # retained; class AkuvoxDevice lives here (<400 lines)
├── _device_profiles.py          # NEW — fallback profile + probe/matrix merge
├── _device_runtime.py           # NEW — lifecycle helpers + _DeviceContext
├── _device_users.py             # NEW — user CRUD wrappers
├── _device_relays.py            # NEW — relay adapter dispatch/status
├── _device_access.py            # NEW — schedule/group wrappers
├── _device_contacts.py          # NEW — contact wrappers/schema shape
└── _device_config_logs.py       # NEW — config + door/call log wrappers
```

## Validation Gates

Every gate below must pass before the implementation PR is opened and after any
Copilot review fixes:

| Gate | Command | Pass criterion |
|---|---|---|
| **Layout tests** | `uv run pytest tests/unit/test_capability_module_layout.py -q` | Device import-preservation, `_device_*` importability, top-level `__all__`, and line-count assertions pass. |
| **Targeted device regression** | `uv run pytest tests/unit/test_device.py tests/unit/test_capability_probe.py tests/unit/test_users.py tests/unit/test_contacts.py -q` | Existing behavioural assertions pass unchanged except import-line rewrites. |
| **MVP smoke** | `uv run pytest tests/unit/test_mvp_test.py tests/integration/test_mvp_smoke.py -q` | Existing MVP mocked smoke coverage remains green. |
| **Full tests** | `uv run pytest tests/ -x -q` | Full suite passes; test count does not regress from the current baseline. |
| **Lint** | `uv run ruff check src/ tests/` | exit 0; zero warnings. |
| **Type check** | `uv run mypy src/` | exit 0; zero errors. |
| **Pre-commit** | `git add -A && pre-commit run --all-files` | exit 0; includes ruff, mypy, interrogate, REUSE, aislop, and pytest-cov hooks. No `--no-verify`. |
| **Aislop affected files** | `uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'` | No `complexity/file-too-large` finding for any affected module. Comma-separated `--include` form is required. |
| **Public import smoke** | `uv run python -c "from pylocal_akuvox import AkuvoxDevice; from pylocal_akuvox.device import AkuvoxDevice as D; assert AkuvoxDevice is D; print('ok')"` | prints `ok`. |
| **Subpath module smoke** | `uv run python -c "import importlib, pylocal_akuvox; m = importlib.import_module('pylocal_akuvox.device'); assert getattr(m, 'AkuvoxDevice') is pylocal_akuvox.AkuvoxDevice; print('ok')"` | prints `ok`. |
| **Import sweep** | `grep -rn "from pylocal_akuvox.device" src/ tests/ docs/` | Output reviewed; path is preserved, so no public-import churn is expected. |
| **Stale phrase sweep** | `grep -RniE "monolithic|all in one file|single device module" src/ tests/ docs/` | Any modified-file hits are reviewed and corrected if inaccurate. |
| **Changelog check** | `grep -A 10 "Changed" docs/changelog.rst` | Contains one non-breaking issue #142 bullet under `Changed`, not under `Breaking changes`. |
| **Commit subject check** | `git log -1 --format=%s` on implementation commit | No `!`; subject ≤50 chars and uses capitalized Conventional Commit type. |

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Helpers accidentally depend on `AkuvoxDevice` and create import cycles | Package import can fail, breaking both public import paths | Helper modules must not import `device.py` or `AkuvoxDevice`. Use `_DeviceContext`, explicit args, and an internal runtime protocol instead. |
| Helpers receive the wrong HTTP client dependency | Delegated service calls may fail or use a stale/closed transport | `_DeviceContext.client` must always be the existing `self._http` / `AkuvoxHttpClient` instance constructed in `AkuvoxDevice.__init__`. Do not introduce a nullable `_client` alias or recreate clients in helpers; lifecycle tests verify closed-session errors and cleanup remain unchanged. |
| `_capabilities` is optional on the facade but helpers need established capabilities | Runtime `AttributeError` or weakened lifecycle errors | `make_context()` must call `require_capabilities()` and raise the same `AkuvoxConnectionError` message as current `_require_capabilities()` when unset. Helpers receive non-optional `DeviceCapabilities`. |
| `attempt_unknown_capability` semantics drift | UNKNOWN capability operations may be allowed or blocked incorrectly | Store it as `_DeviceContext.allow_unknown` and pass it to every `DeviceCapabilities.require(..., allow_unknown=ctx.allow_unknown)` call. Relay override resolution receives `allow_unknown` explicitly. |
| Capability gates move out of public wrappers and become inconsistent | Unsupported devices may call service functions or report wrong reasons | Each helper owns the exact gate immediately before delegation. Tests should assert existing `AkuvoxUnsupportedError.reason`, `capability`, and `device_class` values remain unchanged. |
| Relay dispatch is not a normal `require()` gate | Wrong adapter may be selected; `adapter_missing`, `capability_unknown`, and validation errors may change | Keep relay validation and resolver helpers together in `_device_relays.py`; preserve validation before dispatch; leave thin private compatibility methods on `AkuvoxDevice` if tests call them. |
| Lifecycle extraction mutates cached state incorrectly | `get_info()` caching, failed-`__aenter__` cleanup, or `__aexit__` reset can regress | Runtime helper must preserve the current `asyncio.shield` + `contextlib.suppress(BaseException)` cleanup and reset `_info`/`_capabilities` in the same success/failure cases. Target `tests/unit/test_device.py` lifecycle tests after this phase. |
| `_DeviceContext` could hide mutable state needs | Helpers might need to update facade state in the future | Use `_DeviceContext` only for domain wrappers that currently read client/capabilities/allow flag and delegate. Runtime/probe helpers that update cached state use explicit returns or protocol-based state mutation. |
| White-box tests import private helpers from `pylocal_akuvox.device` | Test imports fail after helper movement | Re-run private import grep against live source before module creation. Rewrite private white-box imports to owning `_device_*` modules or leave deliberate thin aliases only when compatibility is justified. |
| `device.py` remains over 400 lines after all logic moves | Aislop remains red | Final slimming phase trims duplicated comments/docstrings in the facade and moves internal rationale to helpers while preserving public signatures and essential user-facing docstrings. Layout test line-count assertion and aislop gate catch this. |
| Automatic import sorting creates broader-looking diffs | Reviewers may see import-block churn as unrelated | Plan and tasks must carve out ruff/isort import-block reordering as permitted. No behavioural code outside the extraction scope changes. |
| Changelog accidentally looks breaking | Miscommunicates non-breaking refactor | Add one bullet under `Changed`; no `Breaking changes` subsection for #142; implementation subject has no `!`. |

## Carry-Forward Retros

These retros are mandatory implementation checklist items carried forward from
specs 009/010 and the 011 spec:

1. **Pre-PR sweep**:

   ```bash
   grep -rn "from pylocal_akuvox.device" src/ tests/ docs/
   ```

   Because `pylocal_akuvox.device` is preserved, consuming-code changes are not
   expected. Also sweep modified files for stale phrases such as
   "monolithic", "all in one file", and "single device module".

2. **Multi-line RST literals**: any modified RST/docstring multi-line literal
   must use an indented `::` block, not a multi-line inline
   ````...```` span.

3. **Aislop include syntax**: use comma-separated include strings:

   ```bash
   uv run aislop scan --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_profiles.py,src/pylocal_akuvox/_device_runtime.py,src/pylocal_akuvox/_device_users.py,src/pylocal_akuvox/_device_relays.py,src/pylocal_akuvox/_device_access.py,src/pylocal_akuvox/_device_contacts.py,src/pylocal_akuvox/_device_config_logs.py'
   ```

   Do not pass affected files as positional arguments.

4. **Bare `ModuleNotFoundError` rule**: if any removed internal subpath test is
   added, use bare `pytest.raises(ModuleNotFoundError)`, not
   `(ModuleNotFoundError, ImportError)`. **For 011, do not use this pattern for
   `pylocal_akuvox.device` itself**; that module remains importable and must be
   asserted through successful `importlib.import_module`.

5. **Changelog underline depth**: if adding a new changelog subsection, use the
   sibling `^^^^^^^^^^^^^^^^` underline depth. For 011, prefer a single bullet
   under `Changed`; create `Changed` at sibling depth only if absent.

6. **Re-validate every contract/import list against live source** before module
   creation. Do not blindly copy symbol lists from the spec into `__all__` or
   tests. The 010 retro about stale `_extract_items` task entries applies.

7. **Anticipate ruff/isort import-block reordering**: any "no other change" or
   "behaviour unchanged" guidance must explicitly carve out automatic import
   sorting.

8. **NEW for 011 — `_DeviceContext` decision**: use `_DeviceContext` for domain
   helper signatures. Documented contract:
   `(client: AkuvoxHttpClient, capabilities: DeviceCapabilities,
   allow_unknown: bool)`. It is intentionally not used for lifecycle helpers
   that mutate facade state. This trades one small internal dataclass for much
   shorter, safer, uniform helper signatures.

## Post-Design Re-Check

After authoring the phase plan, signature contract, test strategy, and risk
register:

| Principle | Status | Re-check Notes |
|-----------|--------|----------------|
| **I. Code Quality** | PASS | The seven helper modules have focused ownership and projected sizes below 400 lines. `_DeviceContext` centralises repeated dependencies and reduces signature noise without expanding public API. |
| **II. TDD** | PASS | Phase 1 creates red structural assertions first; later phases make them green while existing behaviour suites remain unchanged. |
| **III. UX** | PASS | The public class and import paths are explicitly preserved and tested. No `!`, no breaking changelog section, and no public import rewrites are planned. |
| **IV. Performance** | PASS | No new I/O or event-loop blocking is introduced. Helper calls are in-process delegations using the existing client and cached profile. |
| **V. Atomic Commits** | PASS | The plan PR is one documentation commit. The future implementation can use one refactor commit plus an optional separate changelog commit; task-list updates stay separate if generated later. |
| **VI. Phased Development** | PASS | Ten phases provide independently verifiable checkpoints and a dependency-safe leaf-first extraction order. |

## Complexity Tracking

> No constitutional violations to justify — left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none)    | (none)     | (none)                               |

## No-Closes

This plan PR must use `Refs #142`, not `Closes #142`. The implementation
commit/PR that actually splits `device.py` carries the closing keyword after
source, tests, changelog, aislop, CI, and Copilot review are clean.
