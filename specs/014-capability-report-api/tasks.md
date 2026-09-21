<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Capability Report API

**Input**: Design documents from `/specs/014-capability-report-api/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md,
contracts/run-capability-report.md, contracts/report-json-schema.md,
quickstart.md (all merged to `main`).
**Branch**: `014-capability-report-api` hosts the future implementation PR.
The spec PR, plan PR, and this tasks artifact each ship as separate
documentation PRs. **This tasks PR leaves every checkbox unchecked**;
checkbox flips ride on the later implementation PR as a **separate atomic
commit** (per AGENTS.md §"Task List Updates Are Separate Commits").

**This is an EXTRACTION/REFACTOR, not a greenfield addition.** The central
invariant is **byte-identical CLI output**: for the same device
interactions the CLI's stdout flow, summary, exit codes, and `--json-report`
output MUST be unchanged after the extraction (FR-011/FR-012, SC-002, US5).
Every task is sequenced to make the extraction **safe**: the library modules,
the public API, and their owned tests are built and proven green FIRST
(against mocked HTTP), THEN `examples/mvp_test.py` is refactored into a thin
wrapper, THEN CLI stdout + `--json-report` byte-parity is asserted against a
golden oracle captured **before** any source moves.

**Tests are MANDATORY** per constitution §II (TDD). Each phase leads with a
failing (red) test before the production change (green). No production code
is written before a failing test pins the behaviour.

**Atomic commits** per AGENTS.md §"Atomic Commits" / constitution §V: the
implementation PR keeps each phase's move as a logically separate commit
(report dataclasses + redaction; step framework + gating + read steps + emit
seam; write suite + cleanup; OpenDoor; orchestrator + public export;
CLI thin-wrapper refactor; docs). Only the implementation PR carries the
`Closes #208` keyword — this tasks PR references #208 **without** closing it.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no
  incomplete dependencies between them).
- **[Story]**: Maps the task to a spec user story (US1–US5) where one
  applies. Cross-cutting setup, full-gate, and final-sweep tasks carry no
  story label.
- Every task names exact file path(s), a goal, files touched, and
  acceptance criteria.

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, the CLI in `examples/`,
`tests/unit/` + `tests/integration/`, docs in `docs/`, `README.md`. Spec
artifacts in `specs/014-capability-report-api/`.

## User-story → phase map

| Story | Priority | Phases |
|---|---|---|
| US1 — Generate a read-only capability report from code | P1 | Phase 3 (step framework + read steps), Phase 6 (orchestrator + export) |
| US2 — Write-mode report captures CRUD evidence and cleans up | P1 | Phase 4 (write suite + cleanup), Phase 6 (orchestrator) |
| US3 — Opt in to the credentialed OpenDoor relay test | P2 | Phase 5 (OpenDoor opt-in) |
| US4 — Secrets never leak into the returned report | P1 | Phase 2 (report dataclasses + redaction), Phase 3 (gating) |
| US5 — The CLI keeps working, byte-for-byte | P1 | Phase 1 (golden oracle), Phase 6 (single source of truth), Phase 7 (thin-wrapper + parity) |

## Plan-phase → tasks-phase map

| plan.md phase | tasks.md phase | Modules touched |
|---|---|---|
| (pre-work) | Phase 1 — Setup & baseline | — (baseline + golden oracle fixture) |
| Phase 1 — Report dataclasses + redaction | Phase 2 | `_diagnostic_report.py` |
| Phase 2 — Step framework + gating + read steps | Phase 3 | `_report_steps.py` (+ emit seam) |
| Phase 3 — Write suite + best-effort cleanup | Phase 4 | `_report_steps.py` |
| Phase 4 — OpenDoor opt-in | Phase 5 | `_report_steps.py` |
| Phase 5 — Orchestrator + public export | Phase 6 | `_capability_report.py`, `device.py`, `__init__.py` |
| Phase 6 — CLI thin-wrapper refactor | Phase 7 | `examples/mvp_test.py` |
| Phase 7 — Documentation | Phase 8 | `docs/api/report.rst`, `docs/api/index.rst`, `docs/api/capabilities.rst`, `docs/changelog.rst` |
| (green sweep) | Phase 9 — Polish & pre-PR sweep | full-repo gates |

## Live-source validation cheat sheet

Validated against `main` at tasks-authoring time (worktree base
`f55af2e`). **Re-run these checks before implementation; live source is
canonical** if anything drifts. All line numbers are approximate.

- `examples/mvp_test.py` is ~2360 lines. The **report core** to extract:
  - **Redaction constants (mvp_test.py:89-118)**: `_MUTATION_SETTLE_SECS = 2`,
    `_BODY_SNIPPET_CHARS = 400`,
    `_NON_JSON_BODY_OMITTED = "<non-json response body omitted for privacy>"`,
    `_SCALAR_JSON_BODY_OMITTED = "<scalar JSON response body omitted for privacy>"`,
    `_REDACTED_VALUE = "<redacted>"`,
    `_OPEN_DOOR_PASSWORD_ENV = "AKUVOX_OPEN_DOOR_PASSWORD"`,
    `_SENSITIVE_FIELD_MARKERS = (...)`, `_UNSUPPORTED_SIGNATURES = (...)`.
  - **Report dataclasses**: `class DiagnosticHttpEvent` (:129) with
    `to_json()` (:143); `class DiagnosticTestRecord` (:178) with
    `failure_event` (:204), `capability_status()` (:236) and `to_json()`
    (:252); `class DiagnosticReport` (:270) with `record_exception` (:308),
    `begin_http_event` (:319), `record_http_response` (:339), `to_json()`
    (:369) and `write_json()` (:390).
  - **Redaction / helper functions**: `_event_failed` (:523),
    `_event_succeeded` (:532), `_failure_body_snippet() -> str | None`
    (:600), `_redact_json_values` (:620), `_redact_sensitive_value` (:637),
    `_display_value(field, value, *, redact_stdout)` (:652),
    `_drop_none` (:499), `_clip` (:509), `_decode_json_body` (:1053).
  - **Step framework**: `class TestResults` (:437, `was_passed` :464,
    `print_summary` :468), `class TestStepFailed` (:120) /
    `TestStepSkipped` (:124), `skip_step` (:660), `_effective_status` (:669),
    `_record_capability_skip` (:695), `step[T](...)` (:704),
    `_begin_diagnostic_step` (:847), `_finish_diagnostic_step` (:853).
  - **Device instrumentation**: `_install_probed_capabilities` (:879),
    `create_device(device_kwargs, diagnostics)` (:898),
    `_instrument_device` (:908), `_build_diagnostic_response_handler` (:988),
    `_parse_diagnostic_envelope` (:1065), `print_header` (:1102).
  - **Read steps**: `test_get_info`/`test_list_users`/`test_get_relay_status`/
    `test_list_schedules`/`test_list_groups`/`test_list_contacts`/
    `test_get_door_logs`/`test_get_call_logs` (~:1109-1275),
    `test_validation()` (offline, :1521), `_run_read_tests` (:1641).
  - **Write suite**: `_run_write_tests(device_kwargs, results, *, capabilities,
    open_door, open_door_user, open_door_password, redact_stdout)` (:1822) —
    **four** `async with create_device(device_kwargs, results.diagnostics)`
    connection groups (user :1845; schedule + relay + OpenDoor + config :1897;
    group :1984; contact :2025) with `asyncio.sleep(_MUTATION_SETTLE_SECS * 3)`
    settle pauses between groups; write `test_*` bodies + `test_*_deletion`
    (~:1283-1819).
  - **OpenDoor**: `test_open_door(...)` (:1359), `_run_open_door_write_step`
    (:2077), `_open_door_skip_reason()` (:2102).
  - **CLI plumbing (STAYS in the wrapper)**: `_validate_open_door_args`
    (:2110, reads `_OPEN_DOOR_PASSWORD_ENV`), `run_all(args)` (:2129),
    `_probe_device_capabilities(device_kwargs, diagnostics)` (:2225),
    `main()` (:2247), argparse builder (:2255-2340, flags `--write`,
    `--open-door`, `--open-door-user`, `--open-door-pass`, `--json-report`,
    `--redact-stdout`, auth/SSL/timeout), `build_auth`.
- **`capability_status()` (mvp_test.py:236-250)** returns exactly
  `"supported"` / `"unsupported"` / `"inconclusive"` — **never `"unknown"`**.
  `passed → supported`; `skipped → inconclusive`; failure with HTTP status in
  `{404, 405, 501}` or a `_UNSUPPORTED_SIGNATURES` retmsg → `unsupported`;
  otherwise `inconclusive`.
- **`DiagnosticReport.to_json()` (mvp_test.py:369-388)** emits four top-level
  keys `device` / `auth` / `observed_schemas` / `tests`. `device.host` is
  hard-coded `_REDACTED_VALUE`. **`device.class` / `device.model` /
  `device.firmware` are emitted WITHOUT `_drop_none`** (:376-378) and so
  serialize as `null` when identity is not inferred. `class == model`.
  There is **no top-level `http_events` key** — it is nested per-test.
- **`DiagnosticTestRecord.to_json()` (:252-268)** passes its dict through
  `_drop_none` (:267), so `reason` / `endpoint` / `failure_shape` are
  **omitted** when `None`, never `null`. `http_events` is nested here.
- **`DiagnosticHttpEvent.to_json()` (:143-176)** passes through `_drop_none`,
  so `http` / `retcode` / `retmsg` / `exception_class` / `exception_message` /
  `body_snippet` are **omitted** when `None`. `body_snippet` is a **clipped
  redacted JSON string** (`_failure_body_snippet() -> str | None`,
  :600-617) present **only** for HTTP or Akuvox-retcode failures; success
  events (`http < 400` and `retcode >= 0`) carry no `body_snippet`.
- **`auth.method`** ∈ `"none"` / `"basic"` / `"digest"`; allowlist/no-auth is
  represented as the string `"none"` (verified `run_all`: `auth_desc =
  args.auth if args.auth != "none" else ...`; the report stores `args.auth`).
- **Redaction helpers**: `_redact_json_values` replaces **every** JSON leaf
  with `_REDACTED_VALUE`; `_failure_body_snippet` redacts then `json.dumps`
  then `_clip(..., _BODY_SNIPPET_CHARS)`; non-JSON → `_NON_JSON_BODY_OMITTED`;
  scalar JSON → `_SCALAR_JSON_BODY_OMITTED`. `_redact_sensitive_value` /
  `_SENSITIVE_FIELD_MARKERS` back `_display_value` (terminal-only display).
- **`redact_stdout` is TERMINAL-display only** (mvp_test.py:652-657 →
  `_display_value` → `_redact_sensitive_value(field, value, redact=...)`),
  threaded through **every** read/write `test_*` and `_run_read_tests` /
  `_run_write_tests`. It is **field-aware value redaction inside printed
  strings**, orthogonal to the (always-on) report redaction. See
  **Anomalies §1** for how byte-identity forces this through the emit seam.
- **Connection ownership**: `run_all` builds `device_kwargs = {"host",
  "auth", "timeout", "use_ssl", "verify_ssl"}` (:2151-2157) and opens
  ~6 short-lived `create_device(device_kwargs, ...)` connections (probe :2236;
  four write groups; one read pass). There is **no** single persistent
  entered device. Connection params live on private
  `AkuvoxDevice._http` (`_base_url`, `_timeout` as `aiohttp.ClientTimeout`,
  `_auth`, `_use_ssl`, `_verify_ssl`, `_request_delay`); `AkuvoxDevice`
  itself has no public connection-spec accessor today
  (`AkuvoxDevice.__init__` :54-76). See **Anomalies §2**.
- **`AkuvoxDevice.probe_capabilities()`** (device.py:95) and
  `_capability_probe.py` are **UNCHANGED** and reused for read-only discovery
  (FR-004/FR-014). `AkuvoxDevice.attempt_unknown_capability` (device.py:76,
  default `False`) is the gating toggle.
- **`__init__.py` `__all__`** (:49-76) currently exports 27 symbols; it does
  **not** contain `run_capability_report`. No `pylocal_akuvox.capability_report`
  or `_capability_report` / `_diagnostic_report` / `_report_steps` module
  exists yet.
- **Existing tests to re-point**: `tests/unit/test_mvp_test.py` (imports
  `examples.mvp_test as mvp_test`, monkeypatches `mvp_test.test_add_user`
  etc.), `tests/integration/test_mvp_smoke.py` (drives `mvp_test.run_all`
  against mocked devices, asserts `SKIP:` / `OK:` wording), and
  `tests/unit/test_capability_module_layout.py` (pins module layout +
  `__all__` membership + public re-export identity).
- **Docs**: `docs/api/index.rst` toctree (device, models, groups, contacts,
  config, auth, capabilities, exceptions — **no** `report` yet);
  `docs/api/capabilities.rst`; `docs/changelog.rst` `Unreleased`.
- **REUSE / SPDX**: every new `.py` / `.rst` file MUST carry an SPDX header
  (`# SPDX-FileCopyrightText`/`# SPDX-License-Identifier` for `.py`, the
  `..` comment form for `.rst`) per `REUSE.toml` / constitution §V.

---

## Phase 1: Setup & baseline

**Purpose**: Confirm the green starting state and capture the **byte-identity
oracle** before any source moves — this is what makes the extraction safe.

- [x] T001 Capture the pre-change baseline on `main`.

  - **Goal**: Record that the full suite is green and that the cheat-sheet
    symbols are present at the stated locations, so later red→green
    transitions are unambiguous.
  - **Files touched**: none (read-only).
  - **Steps**:
    1. `uv run pytest -q` — confirm green at 100% branch coverage.
    2. `uv run ruff check`; `uv run ruff format --check`;
       `uv run mypy src tests examples`;
       `uv run interrogate -c pyproject.toml`; the project `aislop` gate;
       `codespell`; and the warnings-as-errors docs build
       `uv run --extra docs sphinx-build -W -b html docs docs/_build/html` —
       all clean.
    3. Re-grep the cheat-sheet symbols and reconcile any drift before
       proceeding (**live source wins**).
  - **Acceptance criteria**: full suite + all gates green; cheat-sheet
    symbols confirmed.

- [x] T002 [US5] Capture the golden CLI byte-identity oracle.

  - **Goal**: Freeze the **pre-extraction** CLI output (stdout + the
    `--json-report` bytes) for a deterministic set of mocked-device runs, so
    Phase 7 can assert the refactored CLI reproduces them **byte-for-byte**
    (FR-012/SC-002). Capturing this **before** any source moves is the
    load-bearing safety net for the whole extraction.
  - **Files touched**: NEW fixture(s) under `tests/fixtures/` (e.g.
    `tests/fixtures/mvp_oracle/<case>.stdout.txt` and `<case>.report.json`),
    plus a capture harness in `tests/integration/` (may be a helper the
    parity test reuses); no `src/` change.
  - **Steps**:
    1. Using the `tests/integration/test_mvp_smoke.py` pattern
       (`argparse.Namespace` + `aioresponses` + monkeypatched
       `mvp_test.asyncio.sleep` to a no-op for determinism), drive the
       **current** `examples.mvp_test.run_all` for representative cases:
       a fully-supported door-phone class (e.g. X916) read-only **and**
       `--write`; an indoor-monitor class with `UNKNOWN` writes (e.g. IT83);
       and a `--write --open-door` case both **with** and **without** relay
       credentials (asserting the relay is/ isn't actuated). Include a
       `--redact-stdout` variant to pin terminal value-redaction.
    2. Capture `capsys` stdout verbatim and the exact bytes
       `DiagnosticReport.write_json` produces
       (`json.dumps(..., indent=2, sort_keys=True) + "\n"`) into the golden
       fixtures. Redact nothing by hand — the fixtures ARE the contract.
    3. Add SPDX headers / `REUSE.toml` entries as required for any new
       non-`.py` fixture files that cannot carry an inline header.
  - **Acceptance criteria**: golden fixtures generated deterministically
    (re-running the capture yields identical bytes); fixtures committed with
    REUSE compliance; the capture harness is importable by the Phase 7
    parity test.

**Checkpoint**: baseline green; the pre-extraction stdout + `--json-report`
oracle is frozen for the same mocked interactions the parity test will
replay.

---

## Phase 2 (plan Phase 1): `_diagnostic_report.py` — report dataclasses + redaction (TDD) — US4

**Goal**: Move the report dataclasses and **all** redaction logic into a new
underscore module with a byte-identical `to_json()` contract. Covers FR-002,
FR-003, FR-014, FR-016; SC-003; US4; US1 scenario 1 (schema).

- [x] T003 [P] [US4] Red — author `tests/unit/test_diagnostic_report.py`.

  - **Goal**: Pin the frozen JSON contract and the unconditional redaction
    policy against the **new** module path before the module exists.
  - **Files touched**: `tests/unit/test_diagnostic_report.py` (NEW) only.
  - **Assertions** (import from `pylocal_akuvox._diagnostic_report`):
    1. `DiagnosticReport.to_json()` yields **exactly** the four top-level
       keys `{"device", "auth", "observed_schemas", "tests"}` and **no**
       top-level `http_events` key (FR-002; report-json-schema.md).
    2. `device.host` is always `"<redacted>"`; when device identity is not
       inferred, `device.class` / `device.model` / `device.firmware`
       serialize as **`null`** (present, not omitted); when inferred,
       `class == model` (FR-003; schema "device.* nullability").
    3. `auth.method` round-trips `"none"` / `"basic"` / `"digest"` (a
       `"none"`/allowlist connection yields `"none"`), and `ssl` /
       `verify_ssl` reflect the toggles.
    4. `DiagnosticTestRecord.to_json()` omits `reason` / `endpoint` /
       `failure_shape` when `None` (via `_drop_none`), never emitting `null`;
       `http_events` is nested inside the record; `capability_status()`
       returns `"supported"` (passed), `"inconclusive"` (skipped / non-
       classifiable failure), `"unsupported"` (HTTP `404/405/501` or a
       `_UNSUPPORTED_SIGNATURES` retmsg) and **never** `"unknown"`
       (FR-002; schema note).
    5. `DiagnosticHttpEvent.to_json()`: a **success** event (`http < 400`,
       `retcode >= 0`) has **no** `body_snippet` and no `exception_*` keys;
       a **failure** event records `body_snippet` as a **clipped JSON
       string** whose parsed content has **every leaf `"<redacted>"`**
       (`_redact_json_values` → `json.dumps` → clip to `_BODY_SNIPPET_CHARS`);
       a **non-JSON** failure body → `"<non-json response body omitted for
       privacy>"`; a **scalar JSON** failure body → `"<scalar JSON response
       body omitted for privacy>"` (FR-003; US4 scenarios 1-3; SC-003).
    6. (No-secret-leak) Feed responses containing name / PIN / MAC / phone
       and assert **none** of those raw values appears anywhere in
       `json.dumps(report.to_json())`; every recorded `body_snippet` leaf is
       `"<redacted>"` (SC-003; Security Considerations).
    7. `write_json(path)` writes `json.dumps(..., indent=2, sort_keys=True)`
       **plus a trailing newline** (byte-for-byte the CLI serialization;
       schema.md §Serialization).
  - **Acceptance criteria**: `uv run python -m py_compile
    tests/unit/test_diagnostic_report.py` passes; the suite **fails** (red)
    with `ModuleNotFoundError: pylocal_akuvox._diagnostic_report`.

- [x] T004 [US4] Green — create `src/pylocal_akuvox/_diagnostic_report.py`.

  - **Goal**: Make T003 pass by moving the report dataclasses + redaction
    helpers **verbatim** (behaviour-preserving) into the new module.
  - **Files touched**: `src/pylocal_akuvox/_diagnostic_report.py` (NEW);
    (temporarily) `examples/mvp_test.py` may import the moved symbols to keep
    the CLI importable until Phase 7 — but do **not** duplicate logic.
  - **Implementation**:
    1. Create the module with an SPDX header and a module docstring. Move
       `DiagnosticHttpEvent`, `DiagnosticTestRecord`, `DiagnosticReport` and
       the helper/constant set: `_REDACTED_VALUE`, `_NON_JSON_BODY_OMITTED`,
       `_SCALAR_JSON_BODY_OMITTED`, `_BODY_SNIPPET_CHARS`,
       `_SENSITIVE_FIELD_MARKERS`, `_UNSUPPORTED_SIGNATURES`, `_event_failed`,
       `_event_succeeded`, `_failure_body_snippet`, `_redact_json_values`,
       `_redact_sensitive_value`, `_drop_none`, `_clip`, `_decode_json_body`.
       Keep every docstring / type annotation; keep each function under the
       C901 ≤10 cyclomatic limit (no logic change, so parity is preserved).
    2. Keep `to_json()` byte-identical: **do not** add `_drop_none` to the
       `device.*` keys (they must still be able to serialize as `null`), and
       keep `host = _REDACTED_VALUE` hard-coded.
    3. Re-point `examples/mvp_test.py` (and, where trivially disjoint,
       `tests/unit/test_mvp_test.py`) to import the moved names from
       `pylocal_akuvox._diagnostic_report` so the CLI + existing tests stay
       importable. (The full CLI refactor is Phase 7; this step only keeps
       the tree green.)
  - **Acceptance criteria**: T003 passes; existing `test_mvp_test.py` report
    tests still green; ruff / ruff format / mypy / interrogate / aislop
    clean; 100% branch coverage on the new module; new file carries an SPDX
    header.

**Checkpoint**: The report/redaction core lives in `_diagnostic_report.py`
with a byte-identical `to_json()`; secrets are provably redacted.

---

## Phase 3 (plan Phase 2): `_report_steps.py` — step framework + gating + read steps + emit seam (TDD) — US1, US4

**Goal**: Move the step framework, device instrumentation, and read `test_*`
bodies into a new module, threading the **`emit` console seam** so the
library is silent by default while the CLI reproduces byte-identical stdout.
Covers FR-004 (partial), FR-008, FR-016; US1; US4 (gating). Introduces the
`emit`/`redact_stdout` seam (Anomalies §1).

- [x] T005 [P] [US1] [US4] Red — author `tests/unit/test_report_steps.py`.

  - **Goal**: Pin capability gating, read-step outcomes, the silent-by-
    default emitter, and the emit/`redact_stdout` seam before the module
    exists.
  - **Files touched**: `tests/unit/test_report_steps.py` (NEW) only.
  - **Assertions** (import from `pylocal_akuvox._report_steps`; use
    `aioresponses` + a fake/entered `AkuvoxDevice`):
    1. **Gating**: with a `DeviceCapabilities` profile marking a capability
       `UNSUPPORTED`, `step(...)` records `status="skipped"` →
       `capability_status="inconclusive"` and issues **zero** HTTP requests;
       the emitted line matches the CLI's `SKIP: <name>: ...` wording
       (FR-008; US4 gating).
    2. **`UNKNOWN` gating honours `attempt_unknown_capability`**: an
       `UNKNOWN` capability is **skipped** when
       `device.attempt_unknown_capability is False` and **attempted** when
       `True` (FR-008; spec §Capability gating).
    3. **Dependency skip primitive**: `skip_step(results, label, reason)`
       records a skipped record with the given reason and a matrix-parity
       `capability_status="inconclusive"` (FR-009 primitive).
    4. **Silent by default**: running a read step with the default silent
       emitter prints **nothing** to stdout (`capsys` empty), while the
       report is still populated; passing a capturing emitter receives the
       exact same text the CLI prints (emit seam).
    5. **`redact_stdout` display seam**: a read step over a response with a
       sensitive field emits the field's value **verbatim** when
       `redact_stdout=False` and `"<redacted>"` when `redact_stdout=True`,
       while the **returned report** is redacted in **both** cases
       (Anomalies §1; FR-003 vs terminal display orthogonality).
    6. **Instrumentation capture**: a `create_device`-wrapped device records
       each HTTP exchange into the `DiagnosticReport` (`observed_schemas`
       accumulates sorted fields; per-test `http_events` populated).
  - **Acceptance criteria**: `py_compile` passes; suite **fails** (red) with
    `ModuleNotFoundError: pylocal_akuvox._report_steps`.

- [x] T006 [US1] [US4] Green — create `src/pylocal_akuvox/_report_steps.py`
  with the emit seam.

  - **Goal**: Make T005 pass by moving the step framework + instrumentation +
    read steps and threading a single injected `emit: Callable[[str], None]`.
  - **Files touched**: `src/pylocal_akuvox/_report_steps.py` (NEW);
    re-point `examples/mvp_test.py` + affected tests to the new paths.
  - **Implementation**:
    1. SPDX header + module docstring. Move `TestStepFailed`,
       `TestStepSkipped`, `TestResults` (incl. `was_passed`,
       `print_summary`), `skip_step`, `_effective_status`,
       `_record_capability_skip`, `step`, `_begin_diagnostic_step`,
       `_finish_diagnostic_step`, `_install_probed_capabilities`,
       `create_device`, `_instrument_device`,
       `_build_diagnostic_response_handler`, `_parse_diagnostic_envelope`,
       `print_header`, `_display_value`, the read `test_*` bodies
       (`test_get_info`, `test_list_users`, `test_get_relay_status`,
       `test_list_schedules`, `test_list_groups`, `test_list_contacts`,
       `test_get_door_logs`, `test_get_call_logs`), `test_validation`,
       `_run_read_tests`, and `_MUTATION_SETTLE_SECS`. Import report/redaction
       symbols from `_diagnostic_report`.
    2. **Thread the `emit` seam**: replace every `print(...)` /
       `print_header(...)` in the moved code with a call routed through an
       injected `emit` carried on `TestResults` (e.g.
       `TestResults(diagnostics, *, emit)`), defaulting to a **silent sink**
       (`lambda _msg: None`). `print_header` and `print_summary` emit through
       the same seam. The **byte content** of each emitted line MUST be
       identical to today's `print(...)` output (T002 oracle guards this in
       Phase 7).
    3. **Keep `redact_stdout` threaded** through `_run_read_tests` and every
       `test_*` exactly as today (it feeds `_display_value`); default
       `False`. It affects only the **emitted** strings, never the report
       (Anomalies §1).
    4. Preserve gating semantics exactly: `step()` consults the shared
       `DeviceCapabilities`; `_install_probed_capabilities` keeps the
       `step()`-level gate and the device per-method gate in sync;
       `attempt_unknown_capability` is honoured.
  - **Acceptance criteria**: T005 passes; existing smoke/unit tests
    re-pointed and green; ruff / ruff format / mypy / interrogate / aislop
    clean; 100% branch coverage on the new module; each moved function stays
    under C901 ≤10.

**Checkpoint**: The step framework + read steps run silently as a library and
reproduce identical text through an injected emitter; gating +
`attempt_unknown_capability` are preserved.

---

## Phase 4 (plan Phase 3): Write suite + best-effort cleanup (TDD) — US2

**Goal**: Move the full CRUD write suite (per-group short-lived connections +
settle pauses + dependency skips + throwaway-entity fixtures) into
`_report_steps.py` and add the byte-neutral best-effort teardown guard.
Covers FR-005, FR-009, FR-016; SC-004; US2.

- [x] T007 [US2] Red — author the write-suite tests in
  `tests/unit/test_capability_report.py`.

  - **Goal**: Pin CRUD evidence, cleanup, dependency skips, and the
    happy-path no-op teardown guard before the suite moves.
  - **Files touched**: `tests/unit/test_capability_report.py` (NEW; shared by
    Phases 4-6) only.
  - **Assertions** (drive `_run_write_tests` — or the Phase-6 orchestrator in
    write mode — against an `aioresponses`-mocked write-capable device;
    monkeypatch `asyncio.sleep` to a no-op):
    1. `tests` include add/modify/delete records for **user, schedule,
       group, and contact**, each with a `capability_status` (US2 scenario 1;
       FR-005).
    2. Every throwaway entity whose `add_*` succeeded is **deleted before the
       run returns** (assert the `delete_*` request was issued and
       `verify_*_deletion` records removal); **no** throwaway entity remains
       (SC-004; US2 scenario 1).
    3. **Dependency skip**: when an `add_*` fails or is skipped, the
       dependent `modify_*` / `delete_*` / `verify_*_deletion` records are
       **skipped** with the CLI's reason strings (FR-009; US2 scenario 3).
    4. **Best-effort teardown guard (happy path = no-op)**: on a clean run
       the guard issues **no** extra delete (the report is **byte-identical**
       to the un-guarded flow) — assert request counts match the un-guarded
       baseline (plan Clarification 3).
    5. **Best-effort teardown guard (abnormal path)**: when a connection/auth
       error escapes a CRUD group **after** an entity was created but
       **before** its normal `delete_*`, the guard issues **one** final
       best-effort delete for the tracked ID on group teardown (plan
       Clarification 3; SC-004 best-effort "no orphaned entities").
    6. Throwaway entities keep their fixed recognizable identifiers
       (`pylocal-test`, UserID `9999`, PIN `1234`→`5678`, and the analogous
       schedule/group/contact fixtures) so any residue is identifiable
       (data-model.md §Throwaway test entity).
  - **Acceptance criteria**: `py_compile` passes; the suite **fails** (red)
    because the write suite / teardown guard are not yet in
    `_report_steps.py`.

- [x] T008 [US2] Green — move `_run_write_tests` + write `test_*` + teardown
  guard into `src/pylocal_akuvox/_report_steps.py`.

  - **Goal**: Make T007 pass, preserving the connection-per-CRUD-group +
    settle-pause choreography and adding the byte-neutral guard.
  - **Files touched**: `src/pylocal_akuvox/_report_steps.py`;
    re-point `examples/mvp_test.py` + affected tests.
  - **Implementation**:
    1. Move `_run_write_tests` and the write `test_*` bodies (`test_add_user`,
       `test_modify_user`, `test_delete_user`, `test_verify_user_deletion`,
       and the schedule/group/contact analogues) verbatim, routing prints
       through `emit` and keeping `redact_stdout` threaded. Preserve the
       **four** `async with create_device(device_kwargs, ...)` groups and the
       `asyncio.sleep(_MUTATION_SETTLE_SECS * 3)` pauses **exactly** (the E18
       CGI-state workaround — do not collapse to one connection).
    2. Wrap **each** CRUD group in a `try`/`finally` **best-effort teardown
       guard** that tracks created IDs and, **only if** the normal `delete_*`
       step did not confirm removal, issues **one** final best-effort delete
       on group-connection teardown. On the happy path the guard is a
       **no-op** (byte-identical report). Swallow guard-path errors (teardown
       must not mask the original abort) and do **not** emit output on the
       happy path.
    3. Keep the dependency-skip chains (`skip_step` for
       `modify_*`/`delete_*`/`verify_*_deletion` when the parent `add_*`
       fails/skips) unchanged.
  - **Acceptance criteria**: T007 passes; ruff / ruff format / mypy /
    interrogate / aislop clean; 100% branch coverage (both guard branches —
    no-op and fired — exercised); each moved function stays under C901 ≤10.

**Checkpoint**: Write mode records CRUD evidence and leaves zero throwaway
entities on success; the teardown guard is provably a happy-path no-op and
fires only on abnormal abort.

---

## Phase 5 (plan Phase 4): OpenDoor opt-in (TDD) — US3

**Goal**: Move the credentialed OpenDoor relay step with the two-credential
signature; the relay actuates **only** on a deliberate, credentialed opt-in.
Covers FR-006, FR-007, FR-016; SC-005; US3. Resolves the US3-scenario-4
inline marker (library skips when `write=False`; CLI keeps its stricter
`parser.error`).

- [x] T009 [US3] Red — author the OpenDoor tests in
  `tests/unit/test_capability_report.py`.

  - **Goal**: Pin actuate-iff-opted-in-with-creds, the skip reasons, the
    `write=False` skip-not-raise behaviour, and password non-leakage.
  - **Files touched**: `tests/unit/test_capability_report.py` (extend) only.
  - **Assertions**:
    1. With `open_door=True`, `write=True`, and **both** credentials
       supplied, the OpenDoor `/fcgi/do?action=OpenDoor` relay step
       **executes** and its outcome is recorded in `tests` (US3 scenario 1;
       FR-006). Assert exactly one relay request is issued.
    2. With `open_door=True` but **missing** credentials, the OpenDoor step
       is **skipped** with the CLI's exact `_open_door_skip_reason()` string
       and **no** relay request is issued (US3 scenario 2; FR-007; SC-005).
    3. With `open_door=False` (default) the step is skipped and **no** relay
       request is issued (US3 scenario 3; SC-005).
    4. With `open_door=True` but `write=False`, the **library** skips
       OpenDoor (no raise, no actuation) — resolving US3 scenario 4 at the
       library boundary (contract §3; plan §OpenDoor opt-in).
    5. **Password non-leakage**: the `open_door_password` value appears
       **nowhere** in `json.dumps(report)` and in no emitted line
       (Security Considerations; SC-003).
  - **Acceptance criteria**: `py_compile` passes; suite **fails** (red)
    because the OpenDoor step is not yet in `_report_steps.py`.

- [x] T010 [US3] Green — move `test_open_door` / `_run_open_door_write_step` /
  `_open_door_skip_reason` into `src/pylocal_akuvox/_report_steps.py`.

  - **Goal**: Make T009 pass with the two explicit credential parameters
    (`open_door_user` / `open_door_password`); the library **never** reads
    `os.environ`.
  - **Files touched**: `src/pylocal_akuvox/_report_steps.py`;
    re-point `examples/mvp_test.py` + affected tests.
  - **Implementation**:
    1. Move `test_open_door`, `_run_open_door_write_step`, and
       `_open_door_skip_reason` verbatim (route prints through `emit`),
       taking `open_door_user: str | None` + `open_door_password: str | None`
       and calling `AkuvoxDevice.open_door_http(user=..., password=...)`. The
       relay actuates **only** when `open_door=True` **and** both credentials
       are non-`None`; otherwise emit + record the skip with the exact CLI
       reason.
    2. Ensure the OpenDoor step runs inside the existing schedule/relay/config
       CRUD group connection (matching `_run_write_tests` today). When
       `write=False` the step is simply not reached (library-skips-not-
       raises); the CLI's `parser.error("--open-door requires --write")`
       stays in the wrapper (Phase 7).
    3. Confirm the password is never passed to any recorded body excerpt (it
       is not a request field the instrumentation records; add an assertion-
       backed comment if needed).
  - **Acceptance criteria**: T009 passes; ruff / ruff format / mypy /
    interrogate / aislop clean; 100% branch coverage on both the actuate and
    skip branches.

**Checkpoint**: The relay actuates in exactly and only the credentialed
opt-in case; every other configuration skips without actuation; the OpenDoor
password never appears in the report or emitted output.

---

## Phase 6 (plan Phase 5): Orchestrator + public export + connection ownership (TDD) — US1, US2, US5

**Goal**: Assemble the public `run_capability_report`, own the connection
lifecycle (accept an entered device; open the API's own short-lived
instrumented connections), re-export from `__init__` / `__all__`, and
preserve error propagation. Covers FR-001, FR-004, FR-010, FR-014, FR-015,
FR-016; SC-001, SC-004, SC-007; US1, US2.

- [x] T011 [US1] [US2] Red — author orchestrator + connection-spec + module-
  layout + probe-regression tests.

  - **Goal**: Pin the public surface, read/write end-to-end behaviour, error
    propagation, connection ownership, the module layout, and the untouched
    `probe_capabilities()` contract before the orchestrator exists.
  - **Files touched**: `tests/unit/test_capability_report.py` (extend);
    `tests/unit/test_capability_module_layout.py` (extend).
  - **Assertions**:
    1. **Public surface**: `from pylocal_akuvox import run_capability_report`
       resolves; it is `async`; `"run_capability_report" in
       pylocal_akuvox.__all__`; and the top-level symbol is **identity-equal**
       to `pylocal_akuvox._capability_report.run_capability_report` (extend
       `test_capability_module_layout.py`, matching its existing re-export-
       identity pattern) (FR-001; SC-007).
    2. **New underscore modules importable** via `importlib.import_module`:
       `pylocal_akuvox._diagnostic_report`, `pylocal_akuvox._report_steps`,
       `pylocal_akuvox._capability_report` (proves the split is real).
    3. **Read-only default** (`write=False`): returns a dict whose top-level
       keys are exactly `{"device", "auth", "observed_schemas", "tests"}`
       with per-test `http_events` nested; issues **zero**
       create/modify/delete requests; reuses `probe_capabilities()` for
       discovery (assert the probe's 9-call read sequence occurred and no
       write endpoint was hit) (FR-004; US1 scenarios 1-2; SC-004).
    4. **Return parity**: the same mocked device produces an **equal**
       structure via `run_capability_report(device)` and via the CLI's
       `--json-report` path in read-only mode (US1 scenario 2) — asserted
       fully in Phase 7, referenced here for the read-only return shape;
       the function **never** returns a `DeviceCapabilities` (Clarification 5).
    5. **Write mode** end-to-end (`write=True`): CRUD evidence recorded +
       cleanup (delegates to the Phase-4 suite) (FR-005; SC-004).
    6. **Connection ownership**: the orchestrator opens its **own**
       short-lived instrumented connections derived from the entered device
       (probe + one per write CRUD group + read pass), preserving the
       settle-pause choreography — assert a fresh connection per group
       (Clarification 2). Exercise the new private connection-spec accessor on
       `AkuvoxDevice` (e.g. `device._connection_spec()` returning the
       `create_device` kwargs `{host, auth, timeout, use_ssl, verify_ssl}`).
    7. **Error propagation** (FR-015): a device whose probe aborts at step 1
       (auth/connection/parse) raises the **same** error type the CLI
       surfaces; **no** half-built report is returned (US1 scenario 3; edge
       case).
    8. **`probe_capabilities()` regression** (FR-014): a direct
       `await device.probe_capabilities()` still returns a frozen
       `DeviceCapabilities` with its unchanged contract/shape (the extraction
       does not alter it).
  - **Acceptance criteria**: `py_compile` passes; suite **fails** (red) with
    `ImportError` / `ModuleNotFoundError` for `run_capability_report` /
    `_capability_report` and `AttributeError` for the connection-spec
    accessor.

- [x] T012 [US1] [US2] Green — create `src/pylocal_akuvox/_capability_report.py`,
  add the connection-spec accessor, and re-export the public symbol.

  - **Goal**: Make T011 pass — the orchestrator ties probe + optional write
    suite + read pass together and returns `DiagnosticReport.to_json()`.
  - **Files touched**: `src/pylocal_akuvox/_capability_report.py` (NEW);
    `src/pylocal_akuvox/device.py` (private accessor only);
    `src/pylocal_akuvox/__init__.py` (import + `__all__`).
  - **Implementation**:
    1. Add a **private** connection-spec accessor to `AkuvoxDevice` (e.g.
       `_connection_spec() -> dict[str, Any]`) that returns the
       `create_device`-shaped kwargs `{host, auth, timeout, use_ssl,
       verify_ssl}` reconstructed from `self._http` (`_base_url` → host,
       `_timeout.total` → timeout, `_auth`, `_use_ssl`, `_verify_ssl`).
       **Public contract of `AkuvoxDevice` is otherwise unchanged** (FR-014).
       Docstring + typing; keep under C901 ≤10.
    2. Create `_capability_report.py` with an SPDX header + module docstring.
       Implement:

       ```python
       async def run_capability_report(
           device: AkuvoxDevice,
           *,
           write: bool = False,
           open_door: bool = False,
           open_door_user: str | None = None,
           open_door_password: str | None = None,
           timeout: float | None = None,
           redact_stdout: bool = False,  # display-only seam — see Anomalies §1
           emit: Callable[[str], None] | None = None,
       ) -> dict[str, object]: ...
       ```

       Port `run_all`'s **online** flow (probe once via the API's own
       instrumented connection reusing `device.probe_capabilities()`; if
       `write`, run the write suite; run the read pass) plus `test_validation`
       ordering, but **without** any argparse / env / `getpass` / `sys.exit` /
       `write_json`. Build `device_kwargs` from `device._connection_spec()`
       (override `timeout` when supplied). Default `emit` to a silent sink;
       thread `emit` + `redact_stdout` into `TestResults` and the suites.
       Construct the `DiagnosticReport` (host/auth/ssl/verify from the spec),
       return `report.to_json()`. **Always** the fuller four-key dict, in both
       modes (Clarification 5). Let probe auth/connection/parse errors
       **propagate** (FR-015) — do not map to `sys.exit` here (that stays in
       the CLI).
    3. Re-export in `__init__.py`: import `run_capability_report` from
       `._capability_report` and add `"run_capability_report"` to `__all__`
       (keep `__all__` sorted).
  - **Acceptance criteria**: T011 passes; ruff / ruff format / mypy /
    interrogate / aislop clean; 100% branch coverage on the new module + the
    accessor; the orchestrator is decomposed (per-group helpers) to stay
    under C901 ≤10; new file carries an SPDX header.

**Checkpoint**: `run_capability_report` is importable from the package root,
returns the fuller redacted report dict in both modes, owns its connections,
propagates the CLI's errors, and leaves `probe_capabilities()` untouched.

---

## Phase 7 (plan Phase 6): CLI thin-wrapper refactor + byte-parity (TDD) — US5

**Goal**: Rewrite `examples/mvp_test.py` so its report derives **solely** from
`run_capability_report()`, with byte-identical stdout + `--json-report`.
Covers FR-011, FR-012, FR-015; SC-002; US5.

- [x] T013 [US5] Red — author the CLI byte-parity regression test.

  - **Goal**: Assert the refactored CLI reproduces the T002 golden oracle
    byte-for-byte before the wrapper is rewritten.
  - **Files touched**: `tests/integration/test_mvp_smoke.py` (extend) or a
    NEW `tests/integration/test_mvp_parity.py`.
  - **Assertions** (replay the exact T002 cases: same mocked device, same
    `argparse.Namespace`, `asyncio.sleep` no-op):
    1. Captured stdout equals the golden `<case>.stdout.txt` **byte-for-byte**
       for each read-only / `--write` / `--open-door` (with + without creds) /
       `--redact-stdout` case (FR-011; SC-002; US5 scenario 2).
    2. The bytes written by `--json-report` equal the golden
       `<case>.report.json` **byte-for-byte** (FR-012; SC-002; US5
       scenario 1).
    3. **Single source of truth**: assert `examples/mvp_test.py` no longer
       defines `DiagnosticReport` / `_run_write_tests` / `_redact_json_values`
       / the `test_*` bodies (they moved to the package) — e.g. grep the
       module source / assert the names resolve to `pylocal_akuvox` modules
       (US5 scenario 3; FR-011).
  - **Acceptance criteria**: `py_compile` passes; the parity assertions
    **fail** (red) until the wrapper is refactored (or pass trivially only
    for the still-unchanged CLI — sequence so the "single source of truth"
    grep assertion is red pre-refactor).

- [x] T014 [US5] Green — rewrite `examples/mvp_test.py` as a thin wrapper.

  - **Goal**: Make T013 pass — `run_all` delegates to
    `run_capability_report()` with a `print` emitter; the CLI keeps its full
    flag surface and I/O concerns.
  - **Files touched**: `examples/mvp_test.py`;
    `tests/unit/test_mvp_test.py` (re-point remaining CLI-wrapper tests);
    `tests/integration/test_mvp_smoke.py` (re-point if needed).
  - **Implementation**:
    1. Keep in the wrapper: `main()`, the argparse builder (all flags),
       `build_auth`, `_validate_open_door_args` (resolving
       `AKUVOX_OPEN_DOOR_PASSWORD` / `--open-door-*` + `getpass`),
       `--redact-stdout` and `--json-report` handling, the `sys.exit(1)`
       error mapping for `AkuvoxConnectionError` / `AkuvoxAuthenticationError`
       / `AkuvoxError`, and the connection banner + "JSON report written"
       lines.
    2. Rewrite `run_all(args)` to: print the connection banner (unchanged
       bytes); build an **entered** `AkuvoxDevice` from the args; call
       `report = await run_capability_report(device, write=args.write,
       open_door=..., open_door_user=..., open_door_password=...,
       timeout=args.timeout, redact_stdout=args.redact_stdout, emit=print)`;
       then, if `--json-report`, serialize the returned dict exactly as
       `DiagnosticReport.write_json` did
       (`json.dumps(..., indent=2, sort_keys=True) + "\n"`) and print the
       "JSON report written" line. Map the propagated errors to `sys.exit(1)`
       around the call. Delete the now-moved report/step/redaction/test_*
       definitions from the script (no second copy — US5 scenario 3).
    3. Preserve the exact stdout interleaving the T002 oracle froze (banner →
       emitted probe/test/summary text → report-written line).
  - **Acceptance criteria**: T013 passes (byte-identical stdout +
    `--json-report`); all re-pointed CLI tests green; ruff / ruff format /
    mypy / interrogate / aislop clean; 100% branch coverage; `mvp_test.py`
    contains no duplicated report/step/redaction logic.

**Checkpoint**: The CLI is a thin wrapper; its stdout and `--json-report`
output are byte-identical to the pre-extraction script; there is one source
of truth.

---

## Phase 8 (plan Phase 7): Documentation — US1..US5

**Goal**: Document `run_capability_report` under `docs/api/` and wire it into
the build. Covers FR-013, FR-016; SC-007.

- [x] T015 [P] Add `docs/api/report.rst`, wire the toctree, and cross-link.

  - **Goal**: Publish the public API reference (parameters, returned schema,
    redaction guarantees, OpenDoor opt-in safety note) and make it appear in
    the docs build (SC-007).
  - **Files touched**: `docs/api/report.rst` (NEW); `docs/api/index.rst`
    (toctree); `docs/api/capabilities.rst` (cross-link);
    `docs/changelog.rst` (`Unreleased` → `Added`).
  - **Implementation**:
    1. Create `docs/api/report.rst` with an SPDX header (the `..` comment
       form), an `autofunction`/prose reference for `run_capability_report`,
       the parameter table (`write`, `open_door`, `open_door_user`,
       `open_door_password`, `timeout`, `emit`, and the `redact_stdout`
       display seam — Anomalies §1), the frozen four-key return schema
       (nested per-test `http_events`, `_drop_none` omission, `body_snippet`
       as a clipped redacted JSON string, `capability_status` tri-value,
       `auth.method` values), the **redaction guarantees** ("safe to paste
       into `new_device`"), and the **OpenDoor opt-in safety note**. Do
       **not** reference issue/PR numbers in reader-facing docs (changelog
       excepted).
    2. Add `report` to the `docs/api/index.rst` toctree; add a cross-link from
       `docs/api/capabilities.rst` (read-only probe) to the write-capable
       report page.
    3. Add a `docs/changelog.rst` `Unreleased` → `Added` entry for the public
       `run_capability_report` API.
  - **Acceptance criteria**: `uv run --extra docs sphinx-build -W -b html docs
    docs/_build/html` passes (warnings-as-errors); the report page renders in
    the API toctree; `run_capability_report` resolves in the build (SC-007);
    REUSE/SPDX compliant.

**Checkpoint**: The published docs describe the write-capable report API, its
schema, its redaction guarantees, and the OpenDoor opt-in; the docs build is
green with `-W`.

---

## Phase 9: Polish, full validation & pre-PR sweep

**Purpose**: Whole-suite green, coverage gate, and conventions compliance
before the implementation PR.

- [x] T016 Run the full quality gate.

  - **Goal**: Confirm every gate is green across the whole change.
  - **Files touched**: none (read-only), modulo auto-formatting fixes.
  - **Steps**: `uv run pytest -q` (100% branch coverage enforced);
    `uv run ruff check`; `uv run ruff format --check`;
    `uv run mypy src tests examples`; `uv run interrogate -c pyproject.toml`;
    the project `aislop` gate over the affected modules
    (`_diagnostic_report.py`, `_report_steps.py`, `_capability_report.py`,
    `device.py`, `__init__.py`, `examples/mvp_test.py`, and the new/updated
    tests and docs); `codespell` (the verbatim Akuvox `unsupport action` / `unknow`
    strings are already ignored repo-wide via `.codespellrc`); the
    warnings-as-errors docs build
    `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`.
  - **Acceptance criteria**: all gates green; 100% branch coverage.

- [x] T017 Pre-PR conventions & REUSE/SPDX sweep.

  - **Goal**: Ensure the new source/docs files carry SPDX headers and the
    diffs are Conventional-Commit-ready with no duplicated logic left behind.
  - **Files touched**: none new (verification); fix headers if any file lacks
    one.
  - **Steps**: confirm SPDX headers on `_diagnostic_report.py`,
    `_report_steps.py`, `_capability_report.py`, `docs/api/report.rst`, and
    any new test/fixture files; run `uv run reuse lint` (or the repo's REUSE
    check); confirm the moved definitions are gone from the CLI, e.g.:

    ```console
    grep -nE "class DiagnosticReport|def _run_write_tests|def _redact_json_values|def test_add_user" examples/mvp_test.py
    ```

    returns **nothing** (logic fully moved); confirm `run_capability_report`
    is listed in the package `__all__` (`pylocal_akuvox.__init__`); run the
    full `pre-commit` after staging the implementation files (fix-and-restage
    on failure, **never** `--no-verify`).
  - **Acceptance criteria**: `pre-commit` clean; REUSE compliant; no
    duplicated report/step/redaction/test_* definition remains in
    `examples/mvp_test.py`.

---

## Dependencies

- **T001 → T002 → everything** (baseline first; the golden oracle MUST be
  captured **before** any source moves).
- **T003 → T004** (report module red before green).
- **T005 → T006** (step framework red before green); T006 depends on T004
  (imports report/redaction symbols from `_diagnostic_report`).
- **T007 → T008** (write suite red before green); T008 depends on T006 (write
  suite lives in `_report_steps.py` and uses the step framework + emit seam).
- **T009 → T010** (OpenDoor red before green); T010 depends on T008 (OpenDoor
  runs inside the schedule/relay/config write group).
- **T011 → T012** (orchestrator red before green); T012 depends on T004, T006,
  T008, T010 (the orchestrator assembles all moved pieces) and adds the
  `device.py` accessor + `__init__` export.
- **T013 → T014** (parity red before green); both depend on T012 (the CLI
  delegates to the public API) and on the **T002** oracle.
- **T015** depends on T012 (documents the final public surface).
- **T016, T017** depend on all prior tasks (final sweep).

## Parallel-execution opportunities

- **T003** and **T005** red tests are `[P]` — different NEW test files, no
  shared state (each just needs its target module to be absent).
- **T015** (docs) is `[P]` relative to Phase 9's read-only gates — different
  files — but must land after T012.
- The Phase 2/3/4/5 module moves are **strictly sequential** (each imports the
  previous module's symbols and shares `_report_steps.py`), so they are **not**
  mutually `[P]`.
- Read-only validation in T016/T017 runs once the source is final.

## Coverage Map: FR / SC / scenario → Tasks

| Requirement / criterion | Implementing tasks | Verifying tasks |
|---|---|---|
| FR-001 export `run_capability_report` from package | T012 | T011 |
| FR-002 four-key dict, per-test nested `http_events` | T004, T012 | T003, T011 |
| FR-003 unconditional redaction | T004, T006 | T003, T005 |
| FR-004 read-only reuses probe, zero CRUD | T012 | T011 |
| FR-005 write CRUD evidence + cleanup | T008 | T007 |
| FR-006 OpenDoor separate opt-in, actuate iff creds | T010 | T009 |
| FR-007 OpenDoor skip (no creds) with CLI reason | T010 | T009 |
| FR-008 capability gating + `attempt_unknown_capability` | T006 | T005 |
| FR-009 dependency skips | T008 | T007 |
| FR-010 signature kwargs (write/open_door/timeout/…) | T012 | T011 |
| FR-011 CLI thin wrapper, no behaviour change | T014 | T013 |
| FR-012 byte-identical `--json-report` | T014 | T013 (+ T002 oracle) |
| FR-013 docs under `docs/api/` | T015 | T016 (docs build) |
| FR-014 preserve probe/schema/redaction | T004, T012 | T003, T011 |
| FR-015 error propagation (no partial report) | T012 | T011 |
| FR-016 SPDX headers + docstrings | T004, T006, T008, T010, T012, T015 | T017 |
| SC-001 single-call report, zero reimplemented logic | T012 | T011, T013 |
| SC-002 byte-identical CLI output | T014 | T013 (+ T002) |
| SC-003 zero secrets in the report | T004 | T003, T009 |
| SC-004 zero CRUD (read) / zero leftover entities (write) | T008, T012 | T007, T011 |
| SC-005 OpenDoor actuates iff opted-in with creds | T010 | T009 |
| SC-006 100% branch coverage; CLI tests pass | (all green tasks) | T016 |
| SC-007 exported + appears in docs build | T012, T015 | T011, T016 |
| US1 scenarios 1-3 | T006, T012 | T005, T011 |
| US2 scenarios 1-4 | T008 | T007 |
| US3 scenarios 1-4 | T010 | T009 |
| US4 scenarios 1-3 | T004 | T003 |
| US5 scenarios 1-3 | T014 | T013 (+ T002) |

## Anomalies / open questions

1. **`redact_stdout` must reach the public boundary (plan/contract vs.
   byte-identity).** The contract signature
   (`contracts/run-capability-report.md`) lists `write`, `open_door`,
   `open_door_user`, `open_door_password`, `timeout`, `emit` — **not**
   `redact_stdout`. But `--redact-stdout` performs **field-aware value
   redaction inside printed strings** (`_display_value` →
   `_redact_sensitive_value`, mvp_test.py:652-657), threaded through every
   `test_*`. A line-level emit wrapper **cannot** reproduce it, so byte-
   identity (FR-012/SC-002) forces the toggle through the core. **Resolution
   (tasks T012/T014):** add a `redact_stdout: bool = False` keyword to
   `run_capability_report` as a **display-only** seam that affects only the
   `emit` stream and **never** the returned report (which is always fully
   redacted). This is permitted by FR-010 ("MUST cover **at least** `write`,
   `open_door`, and `timeout`"). **Flag for /speckit.analyze:** update the
   contract signature to document `redact_stdout`, or confirm this addition.
2. **Private connection-spec accessor on `AkuvoxDevice`.** The hybrid
   connection model (Clarification 2) needs the API to rebuild
   `create_device` kwargs from an entered device, but connection params live
   on private `AkuvoxDevice._http` and there is **no** accessor today. Tasks
   T011/T012 add a **private** `_connection_spec()` (plan §Project Structure
   already anticipates "may gain a private connection-spec accessor"). The
   **public** `AkuvoxDevice` contract is otherwise unchanged (FR-014).
   Re-verify `_http` attribute names (`_base_url`, `_timeout.total`, `_auth`,
   `_use_ssl`, `_verify_ssl`) before implementing.
3. **Signature discrepancy in the task brief.** The PM brief's recap sketch
   showed `run_capability_report(device, *, write=False, open_door_user=None,
   open_door_password=None, attempt_unknown_capability=False, emit=None)`.
   The **merged plan.md Design Overview** and
   `contracts/run-capability-report.md` are authoritative and instead specify
   `write`, **`open_door: bool`**, `open_door_user`, `open_door_password`,
   **`timeout`**, `emit` — and **no** `attempt_unknown_capability` parameter
   (`attempt_unknown_capability` is read from the caller's **device**,
   device.py:76, not passed as a kwarg — spec §Capability gating, FR-008).
   Tasks follow the merged plan/contract (plus `redact_stdout` per §1).
4. **`test_validation()` is offline.** `run_all` runs `test_validation()`
   (model-validation, no HTTP) first. The orchestrator preserves this ordering
   so stdout/report parity holds; it moves with the read steps into
   `_report_steps.py` (T006).
5. **`device.class`/`model`/`firmware` serialize as `null`.** Unlike every
   other optional field, these three are emitted **without** `_drop_none`
   (mvp_test.py:376-378) and so appear as `null` when identity is not
   inferred. T003/T004 pin this exception explicitly — do **not** "fix" it to
   an omission, as that would break byte-identity.
6. **`http_events` is nested per-test, not top-level.** Issue #208's
   shorthand lists it top-level; the live `to_json()` nests it inside each
   `tests[]` record (mvp_test.py:252-268). All tasks assert the **nested**
   shape and forbid a top-level `http_events` key.

All symbol and file references above were validated against the live `main`
source at authoring time (worktree base `f55af2e`). **Re-run the live-source
validation cheat sheet before implementation** if `main` changes — the source
is canonical if the planning docs drift.
