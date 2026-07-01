<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Capability Report API

**Branch**: `014-capability-report-api` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-capability-report-api/spec.md`

## Summary

Issue #208 asks us to extract the report-generating core of the standalone
CLI script `examples/mvp_test.py` (~2360 lines) into a public, importable,
tested, documented library function — `run_capability_report()` — exported
from `pylocal_akuvox`. That function becomes the **single source of truth**
for the redacted capability report; the CLI is rewritten as a **thin
wrapper** over it so the two cannot drift. The immediate downstream consumer
is the Home Assistant integration
(`tykeal/homeassistant-local-akuvox#149`), which will offer an opt-in,
write-enabled "generate capability report" service producing exactly the
evidence the `new_device` issue template asks for.

**This is an extraction, not a greenfield addition.** The CLI's observable
behaviour, the exact JSON report contract (top-level `device` / `auth` /
`observed_schemas` / `tests`, with `http_events` nested **per-test**), and
the redaction policy MUST all be preserved byte-for-byte. Read-only mode
reuses the existing `AkuvoxDevice.probe_capabilities()` /
`_capability_probe.py` probe rather than reimplementing the 9-call sequence;
write mode runs the full add/modify/delete suite against throwaway entities
and cleans them up; OpenDoor stays a separate, explicit, credentialed opt-in
that physically actuates the relay only on deliberate opt-in.

This `plan.md` PR is **documentation only**. It does **not** modify `src/`,
`tests/`, `examples/`, or `docs/`, and it does **not** close #208 — the later
implementation PR carries the closing keyword. All five deliberate
[NEEDS CLARIFICATION] markers the spec retained are resolved here (see
"Resolved Clarifications"), with full rationale and rejected alternatives in
[research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also
exercises forward versions.
**Primary Dependencies**: No new runtime or test dependencies. Runtime:
`aiohttp` (already present, via `AkuvoxHttpClient`). The extraction moves
existing script logic into the package and uses only current internal
modules (`device.py`, `_capability_probe.py`, `models`, `exceptions`) and
the standard library (`asyncio`, `json`). Tooling (`ruff`, `mypy`,
`interrogate`, `aislop`, `sphinx`, `pytest`, `pytest-asyncio`,
`aioresponses`) is unchanged.
**Storage**: N/A — async Python library; no persistence.
**Testing**: pytest + pytest-asyncio + `aioresponses` (mocked HTTP). New
owned unit tests for the extracted module cover read-only, write-mode CRUD,
OpenDoor opt-in (present/absent credentials), redaction, best-effort
cleanup, capability gating / `attempt_unknown_capability`, and CLI-parity
(the CLI derives its report from the API). The existing
`tests/unit/test_mvp_test.py` / `tests/integration/test_mvp_smoke.py` are
re-pointed at the extracted symbols where they moved. 100% branch coverage
is required and enforced.
**Target Platform**: Async Python applications on Linux/macOS/Windows; no
platform-specific behaviour.
**Project Type**: Single Python package under `src/pylocal_akuvox/`, plus
the `examples/mvp_test.py` CLI wrapper.
**Performance Goals**: No new network round-trips, retries, or throttling
beyond what `mvp_test.py` already issues. The E18 CGI-state workaround
(one short-lived connection per CRUD group + a `_MUTATION_SETTLE_SECS`
settle pause) is preserved exactly; no new blocking calls are introduced on
the event loop (Constitution IV). No performance-sensitive path is added, so
no benchmark is required.

**Constraints**:

- **Byte-identity is non-negotiable (FR-011/FR-012, SC-002, US5)**: for the
  same device interactions, the CLI's `--json-report` output and its stdout
  flow, summary, and exit codes MUST be unchanged after the extraction. The
  CLI derives its report solely from `run_capability_report()`.
- **JSON contract is frozen (FR-002/FR-014)**: the returned structure is
  exactly the live `DiagnosticReport.to_json()` shape — four top-level keys
  (`device`, `auth`, `observed_schemas`, `tests`) with `http_events` nested
  inside each `tests[]` record. The extraction MUST NOT invent a top-level
  `http_events` key (the issue's shorthand is wrong; the live code is
  authoritative).
- **Redaction is a security boundary (FR-003, US4)**: body excerpts always
  redacted to `"<redacted>"` leaves, `host` always `"<redacted>"`,
  successful bodies omitted (not redacted), non-JSON/scalar bodies replaced
  with the fixed privacy sentinels, no credential/PIN/MAC/name/phone/OpenDoor
  password anywhere in the structure.
- **Reuse the probe, do not duplicate (FR-004)**: read-only mode discovers
  capabilities via `AkuvoxDevice.probe_capabilities()` and MUST NOT
  reimplement the 9-call probe. `probe_capabilities()`'s own contract and
  output shape are unchanged (FR-014, Out of Scope).
- **OpenDoor safety (FR-006/FR-007)**: the relay actuates only when
  `open_door=True` **and** both credentials are supplied; otherwise the step
  is skipped with the CLI's skip reason and no actuation.
- **Capability gating honored (FR-008/FR-009)**: steps consult the shared
  probe-merged `DeviceCapabilities` profile; `UNSUPPORTED` / `UNKNOWN` steps
  skip; `attempt_unknown_capability` is honored; dependent steps skip when
  their parent `add_*` fails or is skipped.
- **Library is quiet by default**: console printing, argparse, env
  resolution, `getpass`, and `sys.exit` stay in the CLI wrapper. The
  extracted core routes all human-readable output through an injected
  emitter that defaults to a silent sink (see Design Overview §Console
  emitter seam).
- `src/`, `tests/`, `examples/`, and `docs/` are **not** touched by this
  plan PR; all code changes belong to the later implementation PR.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2.
Re-checked after the phase plan — see "Post-Design Re-Check".*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | The extraction moves existing, already-linting-clean logic into underscore-prefixed sibling modules (`_capability_report.py` + cohesive siblings) and adds one public re-export in `__init__`. Every moved/new function keeps or gains a docstring (purpose/params/returns/raises) and full type annotations; the public `run_capability_report` signature is fully typed. The extraction is an opportunity to keep each moved function under the C901 ≤10 cyclomatic limit — the orchestrator is decomposed into the existing per-group helpers rather than one large function. ruff / mypy / interrogate / aislop (100/100) must pass. New source files carry SPDX headers. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | Each behaviour is authored test-first against mocked HTTP: read-only report shape + probe reuse, write-mode CRUD evidence + cleanup, dependency skips, OpenDoor opt-in with/without credentials, redaction (every body leaf `"<redacted>"`, `host` redacted, no secrets), capability gating + `attempt_unknown_capability`, best-effort teardown on partial failure, and CLI-parity (CLI report == API report). No production change precedes its failing test. |
| **III. User Experience Consistency** | PASS | The public entry point is `run_capability_report`, importable from the package root and named consistently with the existing async facade. Keyword-only design toggles (`write`, `open_door`, `open_door_user`, `open_door_password`, `timeout`) mirror the CLI flags and the existing `open_door_http(user=, password=)` signature. Errors the CLI surfaces (auth/connection/parse) propagate unchanged (FR-015). |
| **IV. Performance Requirements** | PASS | No new I/O, retries, or benchmarked path; the preserved settle-pause/reconnect choreography is unchanged. `asyncio.sleep` remains the only cooldown. No benchmark required. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | Implementation lands as small atomic commits (module skeleton + report dataclasses/redaction; step framework; write suite + cleanup; OpenDoor; orchestrator + public export; CLI thin-wrapper refactor; docs), each per `AGENTS.md` Conventional Commits with capitalized types and DCO sign-off; AI co-authorship in `Co-Authored-By` only. This plan PR is a single `Docs(plan)` commit. New files carry SPDX headers. |
| **VI. Phased Development** | PASS | Decomposed into ordered phases below, each with a green checkpoint (targeted tests + ruff + mypy + 100% branch coverage) before the next. Phase boundaries are documented here and carried into `tasks.md` at the next stage. |

**Result**: All gates pass. **Complexity Tracking** remains empty.

## Resolved Clarifications

The spec deliberately retained five [NEEDS CLARIFICATION] markers
(Outstanding Clarifications 1–5). The user deferred **all five** to planning
for a recommendation. Each is resolved here for design purposes; full
rationale and rejected alternatives live in [research.md](./research.md).

### Resolved Clarification 1 — OpenDoor credential-passing shape (RECOMMEND: two explicit keyword params, no library env read)

**Decision**: `run_capability_report` takes **two explicit keyword
parameters**, `open_door_user: str | None = None` and
`open_door_password: str | None = None`. The **library never reads the
environment**. The CLI wrapper keeps its existing surface
(`--open-door-user`, `--open-door-pass`, and the
`AKUVOX_OPEN_DOOR_PASSWORD` env fallback), resolves both values in
`_validate_open_door_args()` / `main()` exactly as today, and passes the
two resolved strings into the API.

**Why**: The HA service must supply both credentials **programmatically**;
a library that reaches into `os.environ` is wrong for an in-process HA
caller and couples the package to a CLI-only convention. Two scalars mirror
the existing `AkuvoxDevice.open_door_http(user=, password=)` signature and
the CLI's two flags one-to-one, so the wrapper is a trivial pass-through and
byte-identity is trivially preserved.

**Rejected**: a single credentials object/tuple (over-engineered for two
strings; asymmetric with `open_door_http`); reading the password from the
environment inside the library (insufficient for HA, and pushes env policy
into the package — env resolution is a CLI concern per the spec).

### Resolved Clarification 2 — Entered device vs. opens-its-own-connections (RECOMMEND: hybrid — accept an entered device, API owns write-mode reconnects)

**Decision**: **Option (c), hybrid.** `run_capability_report(device, ...)`
accepts an **already-entered `AkuvoxDevice`** (matching the issue sketch and
how the HA integration already holds its device). The API **owns the
connection lifecycle for the run**: it captures a connection spec from the
entered device and internally opens its own short-lived, diagnostic-
instrumented connections for (a) the one-time probe, (b) **each** write CRUD
group, and (c) the read-test pass — reproducing `run_all()`'s current
choreography (one connection per CRUD group with a `_MUTATION_SETTLE_SECS`
settle pause). The caller's entered device is the connection **template**
and the source of `attempt_unknown_capability`; write-mode reconnects are
the API's responsibility.

**Why**: Verified against the live source — `run_all()` does **not** run the
suite on one connection. `_probe_device_capabilities()` opens its own
short-lived connection; `_run_write_tests()` opens **four** separate
`create_device(device_kwargs, …)` connections (user; schedule + relay +
OpenDoor + config; group; contact) with settle pauses; `_run_read_tests()`
runs on a fifth. This per-group reconnect is a **load-bearing workaround**
for the E18 `18.30.10.72` CGI-state-corruption bug — a single persistent
connection makes write-mode silently fail on real hardware. So the API
**must** own its own connections for write mode. Accepting an entered device
(rather than raw params) matches the issue and lets read-only mode reuse the
device's probe naturally.

**Rejected**: (a) entered device + integration owns a single connection
(breaks write-mode on real E18 firmware — the settle-pause/reconnect-per-
group workaround is essential); (b) API takes raw connection parameters
instead of a device (contradicts the issue sketch, forces the HA
integration to decompose the device it already holds, and loses the natural
probe reuse).

### Resolved Clarification 3 — Partial-failure cleanup / idempotency (RECOMMEND: preserve per-step delete parity + a byte-neutral best-effort teardown guard)

**Decision**: Preserve the CLI's **per-step-delete** behaviour as the shared,
byte-identical contract (each throwaway entity's `delete_*` is a recorded
diagnostic step). The dependency design already attempts `delete_*` for
**every** entity whose `add_*` succeeded, regardless of the intervening
`modify_*` outcome (verified in `_run_write_tests`). Additionally wrap each
write CRUD group in a **best-effort teardown guard** (`try`/`finally`) that
tracks created IDs and, **only if** the normal `delete_*` step did not
confirm removal, issues one final best-effort delete on group-connection
teardown. On the happy path this guard is a **no-op** (entity already
deleted) → **byte-identical** report. It fires only in the abnormal path
where a connection/auth error escapes the group — and there the CLI aborts
via `sys.exit(1)` and writes **no** report, so no comparable output changes.

**Why**: Byte-identity (FR-012/SC-002) forbids adding output-visible
teardown to the shared happy path, and the device offers no transactional
primitive. This gives the API boundary an honest **best-effort "no orphaned
throwaway entities"** guarantee (SC-004) without altering the CLI's report.
Throwaway entities keep their recognizable fixed names (`pylocal-test`,
UserID `9999`, etc.) so any residue from a hard mid-group abort is
identifiable and manually removable — identical to today.

**Rejected**: a strong transactional/guaranteed-teardown contract (no device
primitive exists; would add output-visible deletes that break byte-identity);
pure "preserve as-is with no guard" (leaves the API boundary silent about
cleanup, which the HA service needs stated).

### Resolved Clarification 4 — Module / documentation placement (RECOMMEND: underscore-prefixed sibling module(s) + public re-export; new `docs/api/report.rst`)

**Decision**: Put the extracted logic in **underscore-prefixed sibling
module(s)** under `src/pylocal_akuvox/` (per AGENTS.md "Refactor &
Module-Layout Conventions") and re-export **only** the public
`run_capability_report` from `pylocal_akuvox/__init__.py` (`__all__`) so it
is importable from the package root. Given the ~2000-line surface, split
along cohesive seams:

- `_capability_report.py` — public `run_capability_report` + the run
  orchestrator and connection ownership;
- `_diagnostic_report.py` — `DiagnosticReport` / `DiagnosticTestRecord` /
  `DiagnosticHttpEvent` + all redaction helpers;
- `_report_steps.py` — the step framework (`TestResults`, `step`,
  `skip_step`, `run_step`, capability gating) and the extracted `test_*`
  step bodies + write suite.

Exact file boundaries are finalized in `tasks.md`; the invariant is
underscore-prefixed internals + a single public re-export. Docs get a **new
page** `docs/api/report.rst` (parameters, returned schema, redaction
guarantees, OpenDoor opt-in safety note) cross-linked from
`docs/api/capabilities.rst` and added to the `docs/api/` toctree.

**Why**: This mirrors the probe split precedent (`_capability_probe.py`,
`_probe_classifiers.py`, … with the public handle on `AkuvoxDevice`). The
public entry point belongs in `__init__`; internals stay underscore-prefixed
so no stale import path resolves. The report API is a distinct concern
(write-capable, redaction, OpenDoor) from the read-only probe/matrix content
in `capabilities.rst`, so it earns its own page.

**Rejected**: a single **public** `capability_report.py` module (violates
the underscore-prefixed-submodule convention; the public symbol belongs in
`__init__`, not a public submodule path); extending `capabilities.rst` only
(overloads a read-only-probe page with a write-capable concern).

### Resolved Clarification 5 — Read-only return-shape parity (RECOMMEND: confirmed — always the fuller report dict, never `DeviceCapabilities`)

**Decision**: **Confirmed yes.** `run_capability_report` **always** returns
the fuller `DiagnosticReport.to_json()` dict (`device` / `auth` /
`observed_schemas` / `tests` with nested `http_events`) in **both**
read-only and write modes — never the frozen `DeviceCapabilities` profile.
Read-only mode reuses `AkuvoxDevice.probe_capabilities()` **internally** for
capability discovery (threaded into the gated steps), then runs the read
test suite to populate `observed_schemas` and the per-test records.
`probe_capabilities()`'s own contract (returning `DeviceCapabilities` to its
direct callers) is untouched (FR-014).

**Why**: A single return type serves both modes and both consumers; the
report — not the profile — is the artifact pasted into the `new_device`
template. The profile is an internal discovery input, not the return value.
This matches the live CLI, whose `--json-report` in read-only mode already
emits the fuller structure.

**Rejected**: returning `DeviceCapabilities` in read-only mode (diverges the
two modes' return types, breaks the "one artifact consumers paste" goal, and
duplicates what `probe_capabilities()` already offers).

## Design Overview

### Public surface (FR-001/FR-010, Clarifications 1/2/5)

```python
# pylocal_akuvox/__init__.py  →  re-exported from _capability_report.py
async def run_capability_report(
    device: AkuvoxDevice,
    *,
    write: bool = False,
    open_door: bool = False,
    open_door_user: str | None = None,
    open_door_password: str | None = None,
    timeout: float | None = None,
    redact_stdout: bool = False,
    emit: Callable[[str], None] | None = None,
) -> dict[str, object]: ...
```

- `device` — an `AkuvoxDevice` connection template; the API opens diagnostic
  child connections for the probe, write, and read passes (Clarification 2).
- `write` — default `False` → read-only, zero create/modify/delete requests
  (FR-004). `True` → full CRUD suite against throwaway entities + cleanup
  (FR-005).
- `open_door` / `open_door_user` / `open_door_password` — the OpenDoor opt-in
  (FR-006/FR-007, Clarification 1). The relay actuates only with
  `open_door=True` **and** both credentials.
- `timeout` — caller-supplied request timeout (FR-010); defaults to the
  device's existing timeout when `None`.
- `redact_stdout` — display-only field-aware redaction threaded into the
  extracted core for emitted CLI text; it never changes the returned report.
- `emit` — the console-emitter seam (see below); defaults to a silent sink
  so the library is quiet.
- **Returns** the redacted report dict (Clarification 5), always the fuller
  four-key structure.

The exact observable contract lives in
[contracts/run-capability-report.md](./contracts/run-capability-report.md);
the frozen JSON schema in
[contracts/report-json-schema.md](./contracts/report-json-schema.md).

### Console emitter seam (byte-identical stdout without a chatty library)

`mvp_test.py` prints heavily from `run_all`, `_run_*_tests`, the `step`
framework, and every `test_*` body. A library must not spew to stdout, yet
US5 requires the CLI's stdout to be **unchanged**. Resolution: thread a
single injected emitter `emit: Callable[[str], None]` through the extracted
core (carried on `TestResults` and passed to the step/`test_*` helpers).
`run_capability_report` defaults `emit` to a **silent sink**; the CLI passes
an emitter that calls `print(...)` producing **byte-identical** stdout.
The CLI's `--redact-stdout` flag is threaded into this extracted core through
the display-only `redact_stdout` keyword rather than remaining CLI-only.
`write_json`, argparse, `getpass`, env resolution, and `sys.exit` stay in
the CLI. The JSON report and return value are independent of `emit` and
always produced. (This is an internal design decision, not a spec
clarification.)

### Preserved JSON contract + redaction (FR-002/FR-003/FR-014)

The moved `DiagnosticReport.to_json()` / `DiagnosticTestRecord.to_json()` /
`DiagnosticHttpEvent.to_json()` emit the identical shapes; the redaction
helpers (`_REDACTED_VALUE`, `_redact_json_values`, `_redact_sensitive_value`,
`_failure_body_snippet`, `_SENSITIVE_FIELD_MARKERS`, the non-JSON/scalar
sentinels) move verbatim. `body_snippet` is recorded **only** for HTTP or
retcode failures; `host` is always `"<redacted>"`. The report structure is
byte-for-byte what the CLI produces today.

### Read-only path (FR-004, Clarification 5)

The orchestrator probes once via `device.probe_capabilities()` (reusing
`_capability_probe.py`), threads the returned profile into the gated read
steps (`_install_probed_capabilities` parity), runs `_run_read_tests`, and
returns `DiagnosticReport.to_json()`. No create/modify/delete requests are
issued (SC-004).

### Write-mode CRUD + cleanup (FR-005/FR-009, Clarification 3)

`_run_write_tests` moves in wholesale, preserving the per-CRUD-group
short-lived connections, the `_MUTATION_SETTLE_SECS` cooldowns, the
dependency-skip chains, and the throwaway-entity fixtures. Each group gains
a best-effort teardown guard (Clarification 3) that is a no-op on the happy
path and only fires on abnormal aborts (byte-neutral).

### Capability gating (FR-008)

The moved `step()` / `_effective_status` / `_record_capability_skip`
consult the shared probe-merged `DeviceCapabilities`; `UNSUPPORTED` /
`UNKNOWN` steps skip with the exact CLI reasons; `attempt_unknown_capability`
is read from the caller's device and honored.

### OpenDoor opt-in (FR-006/FR-007, Clarification 1)

`_run_open_door_write_step` / `test_open_door` / `_open_door_skip_reason`
move in. The relay actuates only when `open_door=True` and both credentials
are non-`None`; otherwise the step is skipped with the CLI's exact reason
string. When `open_door=True` but `write=False`, the **library** skips
OpenDoor (never actuates) rather than raising, while the **CLI** keeps its
stricter `--open-door requires --write` `parser.error` as a CLI-layer guard
(resolves the US3-scenario-4 inline marker). The OpenDoor password never
appears in the report, logs, or any recorded body excerpt.

### CLI thin-wrapper refactor (FR-011/FR-012)

`examples/mvp_test.py` keeps `main()` (argparse + the full flag surface),
`build_auth`, `_validate_open_door_args`, env/`getpass` resolution,
`--redact-stdout` handling, `--json-report` writing, and `sys.exit` error
mapping. `run_all()` becomes a thin adapter that builds an entered
`AkuvoxDevice`, calls `run_capability_report(...)` with a `print` emitter,
threads `redact_stdout` into the core, and writes/prints the returned report.
There is no second copy of the report/step/redaction logic to drift (US5
scenario 3).

## Project Structure

### Documentation (this feature)

```text
specs/014-capability-report-api/
├── plan.md                          # This file (/speckit.plan output)
├── research.md                      # Phase 0 — the five resolved clarifications + source verification
├── data-model.md                    # Phase 1 — the report JSON structure (entities)
├── quickstart.md                    # Phase 1 — how a consumer calls run_capability_report
├── contracts/
│   ├── run-capability-report.md     # Public API observable contract
│   └── report-json-schema.md        # The frozen returned JSON schema
├── checklists/
│   └── requirements.md              # Spec quality checklist (already present)
└── tasks.md                         # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root) — touched by the LATER implementation PR

```text
src/pylocal_akuvox/
├── __init__.py                      # + run_capability_report re-export in __all__ (FR-001)
├── _capability_report.py            # NEW — public run_capability_report + orchestrator + connection ownership
├── _diagnostic_report.py            # NEW — DiagnosticReport/Record/HttpEvent + redaction helpers
├── _report_steps.py                 # NEW — step framework + test_* step bodies + write suite
├── _capability_probe.py             # UNCHANGED — reused for read-only discovery
└── device.py                        # UNCHANGED public contract (may gain a private connection-spec accessor)

examples/
└── mvp_test.py                      # REWRITTEN as a thin CLI wrapper over run_capability_report

docs/api/
├── report.rst                       # NEW — run_capability_report reference + redaction + OpenDoor safety
├── capabilities.rst                 # + cross-link to report.rst
└── index.rst                        # + report page in the toctree

tests/
├── unit/test_capability_report.py   # NEW — read/write/open-door/redaction/cleanup/gating/CLI-parity
├── unit/test_mvp_test.py            # UPDATED — re-pointed at extracted symbols; CLI-wrapper behaviour
├── unit/test_capability_module_layout.py  # + assert new module layout / preserved import paths
└── integration/test_mvp_smoke.py    # UPDATED — smoke the thin wrapper
```

**Structure Decision**: Single Python package under `src/pylocal_akuvox/`
with the CLI in `examples/`. The extraction adds underscore-prefixed sibling
modules and one public re-export (Clarification 4); exact module boundaries
are finalized in `tasks.md`.

### Agent context

No agent-context refresh is required for this plan (mirrors specs 009–013,
which skipped `update-agent-context.sh`). The extraction introduces no new
language, framework, or tooling — only new internal modules and one public
symbol.

## Phases

Ordered, each closing on a green checkpoint (targeted tests + ruff + mypy +
100% branch coverage) before the next. Detailed tasks are generated in
`tasks.md` at the next stage.

### Phase 1 — Report dataclasses + redaction module (TDD) — US4

Move `DiagnosticReport` / `DiagnosticTestRecord` / `DiagnosticHttpEvent` and
all redaction helpers into `_diagnostic_report.py`. Tests: `to_json()` shape
parity for all three; every body-excerpt leaf redacted; `host` redacted;
successful bodies omitted; non-JSON/scalar sentinels.

### Phase 2 — Step framework + gating + read steps (TDD) — US1/US4

Move the step framework (`TestResults`, `step`, `skip_step`, `run_step`,
`_effective_status`, `_record_capability_skip`) and the read `test_*` bodies
into `_report_steps.py`, threading the `emit` seam. Tests: capability gating
(`UNSUPPORTED`/`UNKNOWN` skips + `attempt_unknown_capability`), read-step
outcomes, silent-by-default emitter.

### Phase 3 — Write suite + best-effort cleanup (TDD) — US2

Move `_run_write_tests` + write `test_*` bodies, preserving per-group
connections + settle pauses; add the best-effort teardown guard
(Clarification 3). Tests: CRUD evidence recorded, throwaway entities deleted
on success (SC-004), dependency skips, guard is a no-op on the happy path
and fires only on abnormal abort.

### Phase 4 — OpenDoor opt-in (TDD) — US3

Move `_run_open_door_write_step` / `test_open_door` / `_open_door_skip_reason`
with the two-credential signature (Clarification 1). Tests: actuates only
with `open_door=True` + both creds; skipped with the exact reason otherwise;
password never in the report.

### Phase 5 — Orchestrator + public export (TDD) — US1/US2/US5

Assemble `run_capability_report` in `_capability_report.py` (probe once,
optional write suite, read pass, return `to_json()`), own the connection
lifecycle (Clarification 2), and re-export from `__init__` /`__all__`
(FR-001). Tests: read-only and write-mode end-to-end against mocked HTTP;
error propagation parity (FR-015); module-layout assertions.

### Phase 6 — CLI thin-wrapper refactor (TDD) — US5

Rewrite `run_all()` to delegate to `run_capability_report()` with a `print`
emitter; keep `main()`/argparse/env/`getpass`/`sys.exit`/`write_json`.
Tests: byte-identical `--json-report` output and stdout for the same
interactions (FR-012/SC-002); all existing CLI tests re-pointed and green.

### Phase 7 — Documentation (FR-013/SC-007) — US1..US5

Add `docs/api/report.rst`; cross-link from `capabilities.rst`; add to the
toctree. Build docs warnings-as-errors. No issue/PR refs in reader-facing
docs (changelog excepted).

### Phase boundary checkpoints

Every phase ends with: targeted new tests green, full suite green, `ruff`
clean, `mypy` clean, `interrogate` clean, `aislop ci` 100/100, and 100%
branch coverage on touched modules.

## Post-Design Re-Check (Constitution)

Re-evaluated after the phase plan — no change:

- **I. Code Quality** — PASS. Underscore-prefixed internals + one public
  re-export; docstrings + full typing on all moved/new symbols; the
  orchestrator stays decomposed under C901 ≤10; SPDX on new files.
- **II. TDD** — PASS. Each phase is test-first with mocked HTTP; redaction,
  gating, cleanup, OpenDoor, and CLI-parity all have owned tests.
- **III. UX Consistency** — PASS. One public async entry point, keyword-only
  toggles mirroring the CLI, unchanged error surface (FR-015).
- **IV. Performance** — PASS. No new I/O or benchmarked path; preserved
  settle-pause choreography.
- **V. Atomic Commits & Compliance** — PASS. Small atomic commits;
  Conventional Commits; DCO; AI co-authorship in trailer only; SPDX on new
  files.
- **VI. Phased Development** — PASS. Seven phases, each green before the
  next; boundaries recorded here and carried into `tasks.md`.

**Result**: All gates still pass post-design. Complexity Tracking empty.

## Complexity Tracking

No constitution violations — this table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Artifacts Generated

- [plan.md](./plan.md) — this plan.
- [research.md](./research.md) — the five resolved clarifications (decision /
  rationale / rejected alternatives) + live-source verification and
  corrections.
- [data-model.md](./data-model.md) — the report return-value entities
  (report, test record, HTTP event, throwaway entity, OpenDoor credentials).
- [contracts/run-capability-report.md](./contracts/run-capability-report.md)
  — the public API observable contract.
- [contracts/report-json-schema.md](./contracts/report-json-schema.md) — the
  frozen returned JSON schema.
- [quickstart.md](./quickstart.md) — consumer usage (read-only, write,
  OpenDoor, redaction guarantee).

## Remaining [NEEDS CLARIFICATION]

None. All five spec clarifications are resolved above and in
[research.md](./research.md). One internal design decision (the console
emitter seam) is documented in Design Overview; it is not a spec
clarification.
