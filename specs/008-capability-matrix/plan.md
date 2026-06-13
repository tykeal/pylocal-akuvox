<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Device Capability Probe, Capabilities Matrix, and Capability-Aware API Surfacing

**Branch**: `008-capability-matrix` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-capability-matrix/spec.md`

## Summary

Issue #123 calls for a structural change so the library stops treating every
Akuvox device as a single capability surface. The work is split into four
independently shippable phases mapped 1:1 to spec User Stories 1–4:

1. **Phase 1 — Capability model and probe.** Introduce a cross-cutting
   `pylocal_akuvox/capabilities.py` module exporting the `Capability` enum,
   the `CapabilityStatus` enum (three-valued: `SUPPORTED` / `UNSUPPORTED` /
   `UNKNOWN`), the `DeviceCapabilities` dataclass that wraps a
   `Mapping[Capability, CapabilityStatus]`, and the `DeviceClassPattern`
   matcher.
   Add `await device.probe_capabilities()` — a strictly read-only inspection
   that issues only `GET` / list calls and classifies the four well-known
   failure shapes (`"No handlers for this request"`, the typo
   `"No hanlders for this request"`, `"unsupported action"`, HTTP 500) into <!-- codespell:ignore hanlders -->
   documented categories. The probe **never infers write capability** from
   read endpoints: **all write capabilities** (every `*_ADD` / `*_MODIFY`
   / `*_DELETE` capability across users/contacts/schedules/groups, plus
   `DEVICE_CONFIG_SET` and `RELAY_TRIGGER_*`) **remain `UNKNOWN` after the
   probe**. Only a curated matrix entry (Phase 2) can promote a write
   capability to `SUPPORTED` or demote it to `UNSUPPORTED`. Cross-reference
   `spec.md` FR-003 and `contracts/probe-api.md` Edge case 7 (the 9-cell
   probe-vs-matrix merge table).
   No public-call behavior changes; the probe is opt-in.
2. **Phase 2 — Matrix, dispatch, and structured `AkuvoxUnsupportedError`.**
   Ship a curated `CAPABILITY_MATRIX` covering X916, X915S (current FW),
   E18C (current FW), and IT83. On connect, populate the device's effective
   capability profile from the matrix. Evolve the existing
   `AkuvoxUnsupportedError` (already a sibling of `AkuvoxError`) to carry
   structured `capability`, `device_class`, and `reason` fields while
   remaining backward compatible with its single-arg message constructor.
   Every public `AkuvoxDevice.*` method consults the profile and raises
   `AkuvoxUnsupportedError` *before* any HTTP request when the underlying
   capability is missing. For relay-trigger, dispatch via an adapter
   registry — `/api/relay/trig` for X916/E18C/X915S, `/fcgi/do?action=OpenDoor`
   for IT83 — with a caller override hook.
3. **Phase 3 — Refactor existing aliasing onto the matrix.** Move the read
   alias chain (`ScheduleRelay` / `Schedule-Relay` / `Schedule`) currently
   hardcoded in `models/users.py` and the dual-write
   (`ScheduleRelay` + `Schedule-Relay`) currently hardcoded in
   `users.py:add_user`/`modify_user` onto capability-record-driven field-name
   lists. Move contact-schema-shape selection for **read paths only**
   (door-phone vs apartment-book parsing) onto a capability flag.
   **Apartment-book contact WRITE payloads are out of scope** (see
   `spec.md` Out-of-Scope §"Apartment-book contact writes" — current
   public `add_contact`/`modify_contact` signature has no source for
   `APTName`/`APTNum`/`Building`/`Landline` and no hardware-bench write
   evidence exists; the `schema_shape=SchemaShape.APARTMENT_BOOK`
   write path raises `NotImplementedError` with a deferral message).
   Externally a no-op for the supported door-phone path: every #99/#101
   and #118/#120 regression test stays green with no test logic
   changes.
4. **Phase 4 — Documentation and MVP example.** Publish a "Device support
   matrix" page under `docs/` driven by autodoc on the `Capability` enum
   plus a tabular render of the matrix; a doc-vs-matrix consistency check
   in CI guards against drift. `examples/mvp_test.py` probes once at
   startup and skips-with-reason any step whose capability is absent.

Each phase ships as its own implementation PR. The spec PR (this branch's
plan + spec rubber-duck artifacts) lands first.

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also exercises
3.14 forward.
**Primary Dependencies**: `aiohttp>=3.14.0` (runtime, sole runtime dep);
`pytest`, `pytest-asyncio`, `aioresponses` (test); `ruff`, `mypy`,
`interrogate`, `sphinx` (tooling). **No new runtime dependencies are added
by this feature.**
**Storage**: N/A — library only; the device is the system of record. The
capability matrix is in-process Python data (compile-time literal), not a
persisted store.
**Testing**: pytest + pytest-asyncio; HTTP stubbed with `aioresponses`.
Existing `tests/unit/` is the regression net; new tests live in
`tests/unit/test_capabilities.py` (Phase 1), `tests/unit/test_matrix.py` and
`tests/unit/test_dispatch.py` (Phase 2), and `tests/unit/test_<domain>_*` get
new cases covering capability-driven aliasing (Phase 3). A new
`tests/unit/test_docs_matrix_consistency.py` enforces the doc-vs-matrix
check (Phase 4).
**Target Platform**: Library consumed by async Python applications on
Linux/macOS/Windows. The reference downstream is the Home Assistant custom
component `tykeal/homeassistant-local-akuvox` plus `examples/mvp_test.py`.
**Project Type**: Single Python package (`src/pylocal_akuvox/`).
**Performance Goals**:

- Probe completes in ≤ `2 × probe_timeout` seconds **typical-case** against a
  healthy device that responds promptly to every probe step (non-timeout
  responses on a healthy LAN; sub-second per call). **Worst-case** bound is
  `9 × probe_timeout` (every step times out independently — the deterministic
  9-step sequence per `contracts/probe-api.md` §"Probe step sequence" and
  `research.md` Decision 1). `probe_timeout` is bounded per-call (default 5 s,
  configurable). Probe issues at most one read per capability class — no
  exponential fan-out — and short-circuits only when **step 1** returns
  HTTP 401/403 (raises `AkuvoxAuthenticationError` after exactly 1 call)
  or when step 1's body fails to parse to `DeviceInfo` (raises
  `AkuvoxParseError`). Later-step 401/403 records the affected
  capability as `UNKNOWN` with a `notes` entry and the probe continues
  to all 9 calls — see `contracts/probe-api.md` §"Probe step sequence"
  Call-count invariant and Step-1 failure modes.
- Capability check on the call-time path is an O(1) `dict.get()`
  against an immutable `Mapping[Capability, CapabilityStatus]` (the
  three-valued status model — see `research.md` Decision 2 and the
  spec-side note about FR-002 wording in this plan's Phase Rollout)
  plus an O(k) field-alias lookup against
  a `tuple[str, ...]` of length ≤ 3. No measurable per-call overhead.
- Matrix lookup at connect time is O(N) over a small N (currently 4 device
  classes; expected to stay < 50). Patterns are pre-compiled at import time.

**Constraints**:

- **No event-loop blocking** (constitution §IV). The probe is fully
  `async`/`await`; pattern compilation happens at module import time, not on
  the hot path.
- **Backward compatible at every phase boundary** (constitution §VI, §III).
  Phase 2's `AkuvoxUnsupportedError` evolution preserves the single-arg
  message constructor used by `_http.py:201` and the existing test in
  `tests/unit/test_http.py::test_unsupported_api_raises_unsupported_error` (line ~223). Phase 3 preserves all externally observable
  payload and parse shapes for X916, X915S, and E18C (FR-016, SC-008).
- **Conservative on unknown devices** (FR-013). The library does not
  silently auto-probe on first call; integrators must opt in via
  `probe_capabilities()`.
- **No runtime mutation of the shipped matrix** (out-of-scope item 3 in
  spec). The matrix is a curated `Mapping[DeviceClassPattern, DeviceCapabilities]`
  built at import time and is treated as read-only thereafter; probe results
  populate a *separate* per-connection profile.

**Scale/Scope**:

- New module `src/pylocal_akuvox/capabilities.py` (~250–350 LOC: `Capability`
  enum, `CapabilityStatus` enum, `DeviceCapabilities` dataclass with
  `status_of()` / `require()` / `supported_set`,
  `DeviceClassPattern` matcher, `AkuvoxUnsupportedError` evolution
  re-export). The frozen-dataclass invariant + `__post_init__`
  `MappingProxyType` wrapping (per `data-model.md` §"`DeviceCapabilities`"
  class docstring) is sufficient — no public builder method is exposed
  — `dataclasses.replace(dc, capabilities=new_mapping)` covers the
  composition case if a future consumer needs it, and the 9-cell
  probe-vs-matrix merge happens inside `capability_probe.probe_capabilities`
  (tasks.md T051) without exposing a public merge helper.
- New module `src/pylocal_akuvox/capability_matrix.py` (~150–250 LOC: the
  four matrix entries plus their provenance metadata).
- New module `src/pylocal_akuvox/capability_probe.py` (~200–300 LOC: the
  `probe_capabilities()` implementation and response classifier).
- New module `src/pylocal_akuvox/capability_adapters.py` (~100–200 LOC:
  relay-trigger adapter registry; one entry per supported variant).
- Touches across phases (cumulative): `device.py` (the **only** capability-gating layer — every public `AkuvoxDevice.*` service method gains `self._capabilities.require(...)` before delegating; service-module free functions stay capability-unaware since they have no `self`), `users.py` (alias-list-driven field emission via new optional `field_aliases=` kwarg, Phase 3),
  `models/users.py` (alias-list-driven read parsing, Phase 3),
  `models/contacts.py` (apartment-book schema selector, Phase 3),
  `contacts.py` (mirroring; new optional `schema_shape=` kwarg, Phase 3), `relay.py` (kept for backward-compat re-exports; the relay-trigger adapter implementations move into `capability_adapters.py` and dispatch lives on `AkuvoxDevice.trigger_relay`, Phase 2),
  `_http.py` (Phase 1: (i) extend `get`/`post`/`_request` with optional per-call `timeout=` kwarg used by the probe — backward compatible default to session timeout, (ii) add a new private sibling helper `_request_raw(method, path, *, params=None, data=None, timeout=None) -> tuple[int, str]` that bypasses `_handle_response`'s HTTP/envelope translation so the probe can drive `_classify_response` on raw `(status, body)` tuples — see `contracts/probe-api.md` §"Raw HTTP helper"; existing public surface unchanged; otherwise no behavior change — existing `Api unsupported`-message branch still produces a structured `AkuvoxUnsupportedError` after Phase 2),
  `__init__.py` (re-exports), `examples/mvp_test.py` (Phase 4),
  `docs/api/capabilities.rst` (Phase 4).
- Single repository, single branch per phase PR (`008-capability-matrix-phase-{1..4}`
  branched off this spec branch's merge), all on main after each phase
  merges.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2. Re-checked
after Phase 1 design — see "Post-Design Re-Check" below.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | New modules use the project's standard SPDX header pair. Every new public class, function, and method gets a docstring covering purpose, parameters, return values, and raised exceptions (interrogate already enforces this). Type annotations are mandatory on every new public signature (mypy strict). The capability gate in `AkuvoxDevice` methods is a one-line `self._effective_caps.require(Capability.X)` call — does not push any method past C901's complexity-of-10 limit. Adapter dispatch uses a flat registry (one dict lookup) rather than nested conditionals; pattern matching is delegated to a `DeviceClassPattern.matches()` method whose body is a straight-line two-glob comparison. ruff, mypy, interrogate stay green. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | Each phase follows red-green-refactor at the unit level. Phase 1: failing tests for `Capability` enum membership, `DeviceCapabilities` defaults, response-shape classification (one test per failure-shape edge case), and probe idempotence land first. Phase 2: failing tests for matrix lookup (one per supported device class), pre-flight `AkuvoxUnsupportedError` raise (request-log assertion that no HTTP call was made), adapter dispatch (request-log assertion of selected URL per device). Phase 3: each #99/#101 and #118/#120 regression test stays green; new tests assert the field-alias list is consulted from the capability record. Phase 4: doc-vs-matrix consistency test asserts both directions. Higher-level integration tests against the real-device evidence corpus (mocked) land in Phase 4. **Phase-level test planning per constitution §II is incremental** — Phase 4's integration tests are not pre-written in Phase 1. |
| **III. User Experience Consistency** | PASS | `AkuvoxUnsupportedError` evolves additively: existing single-arg `AkuvoxUnsupportedError(message)` construction continues to work (the existing call site at `_http.py:201` and existing test `tests/unit/test_http.py::test_unsupported_api_raises_unsupported_error` at line ~223 are untouched). New structured fields (`capability`, `device_class`, `reason`) default to `None`; no kwargs become required. Error messages are actionable: when the device is unrecognized, the message names the detected device class string and directs the caller to `probe_capabilities()` (FR-013). Public function signatures gain no new required arguments; `device.connect()` semantics are unchanged from the caller's perspective — what changes is what the device's *effective profile* becomes. The new public surface is `await device.probe_capabilities()` and `device.capabilities` (a read-only property returning the effective `DeviceCapabilities`). |
| **IV. Performance Requirements** | PASS | Probe is bounded by `probe_timeout` per-call and short-circuits on auth failure (FR-004). Matrix lookup is N=4 today, pre-compiled. Per-call gating is an O(1) `dict.get()` against the per-capability status mapping (three-valued model; see `research.md` Decision 2). No blocking I/O on the event loop — the probe is fully async, the matrix is in-memory. Adapter dispatch is one dict lookup. **Performance benchmarks are not warranted at this scope** (constitution §IV requires benchmarks "for performance-sensitive paths"; capability gating is not on a hot path — it precedes a network round-trip and is constant-time relative to that round-trip). |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | Each phase lands as its own implementation PR with multiple commits, each one logical change (e.g. "Feat(capabilities): Add Capability enum and DeviceCapabilities", "Feat(capabilities): Add probe_capabilities() with response classifier", "Feat(capabilities): Add curated matrix for four supported devices", "Feat(capabilities): Add AkuvoxUnsupportedError structured fields", "Refactor(users): Drive schedule-relay aliasing from capability record"). All new files carry SPDX headers verbatim. Pre-commit hooks (ruff, mypy, interrogate, REUSE, pytest) run on every commit; `--no-verify` is prohibited. Conventional Commits with capitalized types per `AGENTS.md`. |
| **VI. Phased Development** | PASS | Four phases mirror the four user stories one-to-one. Each phase is independently shippable and ends at a CI-green checkpoint: Phase 1 introduces opt-in surface (no behavior change); Phase 2 introduces fail-fast surfacing (visible behavior change, but regressions limited to the cases the matrix declares unsupported); Phase 3 is observably a no-op (every existing test stays green); Phase 4 is doc + example only. Phase boundaries are documented here in `plan.md`; per-phase `tasks.md` files will be generated by `/speckit.tasks` against the merged plan. |

**Result**: All gates pass. **Complexity Tracking** section below is empty —
no justified violations.

## Project Structure

### Documentation (this feature)

```text
specs/008-capability-matrix/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec (input)
├── research.md          # Phase 0 output — design decisions for 11 topics
├── data-model.md        # Phase 1 output — type/home map for new entities
├── quickstart.md        # Phase 1 output — phase-by-phase verification recipe
├── tasks.md             # Phase task breakdown for PR 0 and implementation PRs
├── contracts/
│   ├── probe-api.md     # Public probe API contract
│   ├── matrix-lookup.md # Matrix lookup + DeviceClassPattern semantics
│   ├── unsupported-error.md  # AkuvoxUnsupportedError structured form
│   └── adapter-dispatch.md   # Adapter registry contract for relay variants
└── checklists/          # Pre-existing review checklists
```

`tasks.md` is included in this spec PR as the phase task breakdown
produced after planning by `/speckit.tasks`.

### Source Code (repository root)

Pre-feature (current state, abbreviated to the affected area):

```text
src/pylocal_akuvox/
├── __init__.py              # Re-exports public surface
├── _http.py                 # AkuvoxHttpClient; line 201 raises AkuvoxUnsupportedError(msg)
├── auth.py
├── config.py                # Service module
├── contacts.py              # Service module — door-phone-shape contact ops
├── device.py                # AkuvoxDevice public surface (8 service-call methods)
├── exceptions.py            # AkuvoxUnsupportedError (currently message-only sibling)
├── groups.py                # Service module
├── logs.py                  # Service module
├── models/
│   ├── __init__.py          # Re-export shim
│   ├── config.py
│   ├── contacts.py          # Contact dataclass — single-shape parser
│   ├── device.py
│   ├── groups.py
│   ├── logs.py
│   ├── schedules.py
│   └── users.py             # User.from_api_response — hardcoded ScheduleRelay/Schedule-Relay/Schedule chain
├── py.typed
├── relay.py                 # trigger_relay → /api/relay/trig (single path)
├── schedules.py             # Service module
└── users.py                 # add_user/modify_user — hardcoded ScheduleRelay+Schedule-Relay dual-write

tests/unit/
└── …

examples/
└── mvp_test.py              # Runs every operation, catches errors
```

Post-feature (only the changed area is shown; everything else is unchanged
unless noted):

```text
src/pylocal_akuvox/
├── __init__.py              # Adds: Capability, DeviceCapabilities, AkuvoxUnsupportedError (already exported), probe_capabilities export note
├── _http.py                 # Phase 1 — (i) extends `get`/`post`/`_request` with optional per-call `timeout=` kwarg (backward compatible; default falls back to session timeout, used by probe); (ii) adds new private `_request_raw(method, path, *, params=None, data=None, timeout=None) -> tuple[int, str]` that bypasses `_handle_response`'s HTTP/envelope translation (the probe needs raw status + body to classify per `contracts/probe-api.md` §"Raw HTTP helper"). Phase 2 may enrich the message-only `AkuvoxUnsupportedError` raise at line 201 with `capability=None` to remain backward compatible.
├── auth.py                  # UNCHANGED
├── capabilities.py          # NEW (Phase 1) — Capability enum, CapabilityStatus enum, DeviceCapabilities dataclass, DeviceClassPattern, FieldAliases, SchemaShape; cross-cutting per spec 007 §R9
├── capability_matrix.py     # NEW (Phase 2) — CAPABILITY_MATRIX: tuple[tuple[DeviceClassPattern, DeviceCapabilities], ...]
├── capability_probe.py      # NEW (Phase 1) — probe_capabilities() + response classifier; consumed by AkuvoxDevice
├── capability_adapters.py   # NEW (Phase 2) — RELAY_TRIGGER_ADAPTERS registry; adapter callables
├── config.py                # Phase 2 — UNCHANGED (capability gate lives on the AkuvoxDevice wrapper, not here)
├── contacts.py              # Phase 3 — accepts optional `schema_shape=` kwarg (default DOOR_PHONE) so AkuvoxDevice can pass the matrix-derived shape; service-module remains capability-unaware
├── device.py                # Phase 1 adds probe_capabilities() + capabilities property; Phase 2 adds connect-time matrix population + per-method capability gate on every AkuvoxDevice service method (the only gating layer)
├── exceptions.py            # Phase 2 evolves AkuvoxUnsupportedError additively (capability/device_class/reason fields, all default-None)
├── groups.py                # Phase 2 — UNCHANGED (gate lives on AkuvoxDevice wrapper)
├── logs.py                  # Phase 2 — UNCHANGED (gate lives on AkuvoxDevice wrapper)
├── models/
│   ├── __init__.py          # UNCHANGED — shim continues to re-export ten model classes
│   ├── config.py            # UNCHANGED
│   ├── contacts.py          # Phase 3 — apartment-book vs door-phone shape selected from capability record
│   ├── device.py            # UNCHANGED
│   ├── groups.py            # UNCHANGED
│   ├── logs.py              # UNCHANGED
│   ├── schedules.py         # UNCHANGED
│   └── users.py             # Phase 3 — read alias chain from capability record's field-aliases for ScheduleRelay
├── py.typed                 # UNCHANGED
├── relay.py                 # Phase 2 — kept for legacy import paths; adapter implementations move into capability_adapters.py and AkuvoxDevice.trigger_relay does the dispatch via RELAY_TRIGGER_ADAPTERS
├── schedules.py             # Phase 2 — UNCHANGED (gate lives on AkuvoxDevice wrapper)
└── users.py                 # Phase 3 — `add_user`/`modify_user` accept optional `field_aliases=` kwarg (default `DEFAULT_USER_FIELD_ALIASES`); AkuvoxDevice wrapper passes the matrix-derived FieldAliases. Today's hardcoded dual-write becomes the default fallback — byte-identical for legacy callers

tests/unit/
├── test_capabilities.py     # NEW (Phase 1) — Capability enum, CapabilityStatus enum, DeviceCapabilities (status_of, require, supported_set), DeviceClassPattern.matches
├── test_capability_probe.py # NEW (Phase 1) — probe idempotence, four failure-shape classifications, no-write assertion via aioresponses request log
├── test_matrix.py           # NEW (Phase 2) — one test per supported device class confirming matrix entry shape and provenance
├── test_pattern.py          # NEW (Phase 2) — DeviceClassPattern matching truth table (extends Phase 1's T013 with the four production patterns)
├── test_dispatch.py         # NEW (Phase 2) — relay adapter dispatch picks correct URL per device
├── test_unsupported_error.py # NEW (Phase 2) — backward-compat single-arg construction + structured-fields construction
├── test_users.py            # Phase 3 — new cases asserting the alias list is read from capability record (existing #99/#101 cases stay green)
├── test_models.py           # Phase 3 — new cases asserting User.from_api_response consults capability record's field-aliases (existing #118/#120 cases stay green)
├── test_contacts.py         # Phase 3 — apartment-book schema parses without ID when capability flag is set
├── test_docs_matrix_consistency.py  # NEW (Phase 4) — every device class in matrix appears in docs and vice versa
└── …                         # other module tests unchanged

examples/
└── mvp_test.py              # Phase 4 — calls probe_capabilities() at startup; skips-with-reason any step whose capability is absent

docs/api/
├── capabilities.rst         # NEW (Phase 4) — autodoc on Capability enum + DeviceCapabilities + matrix table render
└── …                         # existing pages unchanged

docs/_ext/
└── capability_matrix.py     # NEW (Phase 4) — custom sphinx directive that renders CAPABILITY_MATRIX as a reST grid table (or inline in docs/conf.py — see research.md Decision 11)
```

**Structure Decision**: Single Python package (`src/pylocal_akuvox/`) with
**capability concerns split into four sibling modules** under the package
root rather than one fat module:

- `capabilities.py` — types only (enum, dataclasses, pattern). Stable, low
  churn, easy to autodoc.
- `capability_matrix.py` — data only (the curated entries). High churn as
  new firmware bands land; isolating it keeps PRs that add a device class
  to a single-file diff (FR-017, SC-007).
- `capability_probe.py` — runtime probe logic. Touches HTTP; depends on
  `capabilities.py`.
- `capability_adapters.py` — adapter registry for capabilities with
  multiple implementations (relay trigger today; future: any operation
  with a `/api/*` vs `/fcgi/*` variant). Touches HTTP; depends on
  `capabilities.py`.

This four-way split honours the spec-007 cross-cutting note (the *types*
live at the package root, sibling to service modules and outside the
`models/` package) while preventing one mega-module that would violate the
project's preference for narrow, single-purpose files (the same rationale
that drove spec 007). Discussion of the tradeoffs and the alternatives
considered (single `capabilities.py`; subpackage `capabilities/…`) is in
`research.md` §5.

### Post-Design Re-Check (after Phase 1 artifacts)

After authoring `data-model.md`, `contracts/`, and `quickstart.md`:

| Principle | Status | Re-check Notes |
|-----------|--------|---------------|
| **I. Code Quality** | PASS | Designed types stay narrow: every public method on `DeviceCapabilities` is a one-liner (`dict.get()` for `status_of`, an `if`-chain raise for `require()`, alias-tuple lookup elsewhere). No method exceeds C901's complexity-of-10. |
| **II. TDD** | PASS | Contracts are concrete enough to write failing tests against in Phase 1's red phase before any production code lands. The contract docs name the test files that own each behavior. |
| **III. UX** | PASS | `AkuvoxUnsupportedError` contract preserves single-arg construction and adds optional structured fields — confirmed in `contracts/unsupported-error.md`. No documented public name is removed at any phase. The Phase 3 refactor's externally observable surface is byte-identical for currently-supported devices (FR-016). |
| **IV. Performance** | PASS | Contracts confirm the per-call gate is an O(1) `dict.get()` against `Mapping[Capability, CapabilityStatus]`; no design choice introduces hidden quadratic behavior. |
| **V. Atomic Commits** | PASS | Each contract maps to a small commit set. The data-model identifies each new file's owner and SPDX headers will be added at file creation time. |
| **VI. Phased Development** | PASS | The four contracts partition cleanly across the four phases — no contract requires Phase 2 + Phase 3 to land atomically. |

## Phase Rollout Plan

Each phase below is an **independently mergeable PR** branched off the
post-merge tip of the spec branch (i.e. branched off `main` once this spec
PR lands). The spec/plan PR (this branch) lands first.

### PR 0 — Spec & plan (this branch)

- Files: `specs/008-capability-matrix/{spec,plan,research,data-model,quickstart}.md`
  and `specs/008-capability-matrix/contracts/*.md`.
- No source-code changes.
- Constitution: §VI (phased development) — this is the planning checkpoint.

### PR 1 — Phase 1: Capability model and probe (User Story 1)

- Adds: `src/pylocal_akuvox/capabilities.py`,
  `src/pylocal_akuvox/capability_probe.py`,
  `tests/unit/test_capabilities.py`,
  `tests/unit/test_capability_probe.py`.
- Modifies: `src/pylocal_akuvox/device.py` (adds `probe_capabilities()` and
  the `capabilities` read-only property; effective profile is set via the
  property setter when the probe completes — no other public method changes
  behavior in this PR), `src/pylocal_akuvox/__init__.py` (re-exports new
  public names).
- Independent value: integrators can probe an unfamiliar device safely.
- CI gate: Phase 1 acceptance scenarios 1–5 in spec User Story 1; SC-001,
  SC-002, SC-003.

### PR 2 — Phase 2: Matrix, dispatch, and `AkuvoxUnsupportedError` evolution (User Story 2)

- Adds: `src/pylocal_akuvox/capability_matrix.py`,
  `src/pylocal_akuvox/capability_adapters.py`,
  `tests/unit/test_matrix.py`, `tests/unit/test_dispatch.py`,
  `tests/unit/test_unsupported_error.py`.
- Modifies: `src/pylocal_akuvox/exceptions.py` (additive evolution of
  `AkuvoxUnsupportedError`), `src/pylocal_akuvox/device.py` (matrix lookup
  on connect; **per-method capability gate added to every public
  `AkuvoxDevice.*` service method — this is the only gating layer**),
  `src/pylocal_akuvox/relay.py` (legacy import path; the relay adapter
  implementations live in `capability_adapters.py` and dispatch lives on
  `AkuvoxDevice.trigger_relay`), `src/pylocal_akuvox/__init__.py`. **Service
  modules (`config.py`, `contacts.py`, `groups.py`, `logs.py`,
  `schedules.py`, `users.py`) are NOT modified in Phase 2** — they are
  module-level free functions with no `self`, so capability gating cannot
  live there. Phase 3 will add optional kwargs (`field_aliases=`,
  `schema_shape=`) to a subset for the aliasing refactor.
- Independent value: visible fail-fast errors and adapter-correct relay
  trigger on the four supported device classes.
- CI gate: Phase 2 acceptance scenarios 1–6 in spec User Story 2; SC-004,
  SC-005, SC-006.

### PR 3 — Phase 3: Refactor aliasing onto matrix (User Story 3)

- Modifies: `src/pylocal_akuvox/users.py` (write-aliases driven from
  capability record + read-side `list_users` plumbing for T064a),
  `src/pylocal_akuvox/models/users.py` (read-aliases
  driven from capability record), `src/pylocal_akuvox/models/contacts.py`
  (apartment-book schema flag), `src/pylocal_akuvox/contacts.py`
  (mutation `schema_shape=` for T066 + read-side `list_contacts`
  `capabilities=` plumbing for T066a),
  `src/pylocal_akuvox/device.py` (`AkuvoxDevice.list_users` /
  `list_contacts` / `list_schedules` / `list_groups` wrapper updates
  to thread `capabilities=self._capabilities` per T064a/T066a/T066b),
  `src/pylocal_akuvox/capability_matrix.py` (existing X916/E18C/X915S
  entries gain explicit field-alias lists; matrix is the new source of
  truth for what was previously hardcoded), updates to existing
  `tests/unit/test_users.py`, `tests/unit/test_models.py`,
  `tests/unit/test_contacts.py`, plus NEW tests in
  `tests/unit/test_users.py` (T064a end-to-end alias plumbing —
  non-default + conflict resolution), `tests/unit/test_contacts.py`
  (T066a end-to-end schema-shape plumbing — apartment-book +
  door-phone baseline), `tests/unit/test_schedules.py` (T066b
  baseline), `tests/unit/test_groups.py` (T066b baseline), and
  `tests/unit/test_matrix.py` (T061 synthetic-matrix-entry test).
- Independent value: the structural payoff. Adding a new firmware band
  becomes a one-entry matrix change. Externally observable behavior is
  unchanged for X916, X915S, E18C (FR-016, SC-008).
- CI gate: every existing #99/#101 and #118/#120 test passes with no logic
  changes (only changes where a test was specifically asserting "this
  conditional lives in this file"); new tests assert that the alias list
  comes from the capability record.

### PR 4 — Phase 4: Documentation and MVP example (User Story 4)

- Adds: `docs/api/capabilities.rst`,
  `tests/unit/test_docs_matrix_consistency.py`.
- Modifies: `docs/api/index.rst` (add new page), `docs/index.rst` (add to
  toctree if needed), `examples/mvp_test.py` (probe-then-skip-supported).
- Independent value: a discoverable device support matrix and an MVP
  example that does not crash on IT83.
- CI gate: SC-009 (doc-vs-matrix consistency), SC-010 (mvp_test snapshot
  reports skipped-with-reason on IT83).

## Complexity Tracking

> No constitutional violations to justify — left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | (none)     | (none)                              |

## Spec consistency flags (carry into next rubber-duck round)

The three rubber-duck flags raised during the cascade have all been
resolved by spec edits applied alongside this plan revision (the spec
PR will commit spec.md and these plan artifacts together). The
flags are recorded here for traceability into the next rubber-duck
round:

1. **FR-002 / Key Entities wording — RESOLVED.**  Spec FR-002 now reads
   "a per-capability status profile (each known `Capability` mapped to
   `supported`, `unsupported`, or `unknown`)". The Key Entities entry
   for `DeviceCapabilities` carries the same wording and explicitly
   notes the `supported_set` convenience view for callers that do not
   need the three-valued distinction. The `Capability` and a new
   `CapabilityStatus` Key-Entities entries were added. User Story 1
   acceptance scenario #1 was reworded from "set of capabilities" to
   "per-capability status profile". Edge case 3 (HTTP 500) now
   explicitly maps the response to `unknown` status and references the
   three-valued model.

2. **`AkuvoxDevice.attempt_unknown_capability` opt-in — RESOLVED.**
   Added as **FR-021** in a new spec subsection "Integrator opt-in for
   unknown-status capabilities (Phase 2)". User Story 2 gained
   acceptance scenario #7 covering both states of the override; the
   Independent-Test paragraph for US2 lists the override as test
   condition (e). FR-011 was reworded to reference FR-021 as the
   default-fail-fast-on-UNKNOWN escape hatch. SC-011 added to the
   Success Criteria, asserting request-log behaviour for both states
   of the override. Phasing entry for Phase 2 mentions FR-021.

3. **`device_unrecognized` ↔ `capability_unknown` foldability —
   RESOLVED.**  Added as a fourth bullet in the Out of Scope section
   stating that the implementation MAY collapse the two reasons since
   both surface identical caller-facing UX. This locks in the
   contracts/unsupported-error.md flexibility without forcing a
   particular implementation choice.

All three resolutions are traceable: each spec section either names
the new FR-021 / SC-011 / status-profile wording, or — for
implementer-flexibility — explicitly defers the choice to Phase 2
implementation. No further spec edits are queued for the next
rubber-duck round on this axis.
