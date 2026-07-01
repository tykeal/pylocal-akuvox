<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Feature Specification: Capability Report API

**Feature Branch**: `014-capability-report-api`
**Created**: 2026-07-01
**Status**: Draft
**Input**: Issue #208 — Extract the report-generating core of
`examples/mvp_test.py` (~2360 lines) into an importable, tested,
documented library API (`run_capability_report`) that becomes the single
source of truth shared by the CLI and external consumers. The immediate
downstream consumer is the Home Assistant integration
[`tykeal/homeassistant-local-akuvox`](https://github.com/tykeal/homeassistant-local-akuvox),
which wants to offer an opt-in, write-enabled full capability report as a
Home Assistant service so device owners can generate exactly the evidence
the [`new_device` issue template](/.github/ISSUE_TEMPLATE/new_device.yml)
asks for.

## Overview

Today the rich, redacted capability report lives **only** inside the
standalone CLI script `examples/mvp_test.py`. The package exports no
report/diagnostics producer beyond the read-only
`probe_capabilities()`; the JSON report schema, the step/test framework,
the write-mode CRUD suite, the opt-in OpenDoor relay test, and all
redaction logic are private to the script. Any external consumer that
wants the same evidence — most importantly the HA integration's planned
opt-in "generate capability report" service — would have to reimplement
~2000 lines and keep them byte-for-byte in sync with the CLI's schema and
redaction policy.

This feature **extracts** the report-generating core of `mvp_test.py`
into a public, importable, tested library function —
`run_capability_report()` — exported from `pylocal_akuvox` and documented
under `docs/api/`. The CLI is then rewritten as a **thin wrapper** over
this API so the two cannot drift.

**This is an extraction, not a greenfield addition.** The observable
behaviour of the CLI and the exact JSON contract and redaction policy of
the report it produces MUST be preserved. The function is the new single
source of truth; the CLI consumes it.

The read-only half of the report already has a public analogue in
`AkuvoxDevice.probe_capabilities()` (which the HA integration's read-only
diagnostics download already uses). What is missing — and what this
feature delivers — is a reusable, **write-capable** report producer that
captures the `add`/`modify`/`delete` → `supported` evidence that is the
most valuable signal for capability-matrix authoring, plus the opt-in
credentialed OpenDoor relay test.

## Background and Evidence

### What lives in `examples/mvp_test.py` today (extraction targets)

The following constructs are the extraction targets. The spec references
them so planning reconciles against the live code rather than inventing
APIs.

| Construct | Location (`examples/mvp_test.py`) | Role |
|---|---|---|
| `DiagnosticReport` class | ~line 270 | Accumulates `device`, `auth`, `observed_schemas`, `tests`; exposes `to_json()` / `write_json()` |
| `DiagnosticTestRecord` / `DiagnosticHttpEvent` | ~line 130–265 | Per-test and per-HTTP-exchange records with `to_json()` |
| Redaction helpers | ~line 94–657 | `_REDACTED_VALUE = "<redacted>"`, `_redact_json_values`, `_redact_sensitive_value`, `_failure_body_snippet`, `_SENSITIVE_FIELD_MARKERS` |
| Step framework | ~line 437–780 | `TestResults`, `step()`, `skip_step()`, `_record_capability_skip`, `_effective_status`, `TestStepFailed` / `TestStepSkipped` |
| Device instrumentation | ~line 898–970 | `create_device()` / `_instrument_device()` wrap the HTTP client so every exchange is captured into the report |
| Capability threading | ~line 879–896, 2176 | `_probe_device_capabilities()` probes **once**; `_install_probed_capabilities()` reuses the profile on every subsequent connection |
| Write suite | ~line 1822–2075 | `_run_write_tests()` — user / schedule / group / contact CRUD + relay trigger + config set, each capability-gated, with dependency skips |
| OpenDoor opt-in | ~line 2077–2126, 1359–1378 | `_run_open_door_write_step()`, `test_open_door()`, `_validate_open_door_args()`, `AKUVOX_OPEN_DOOR_PASSWORD` env |
| Orchestration | ~line 2129–2244 | `run_all()` — probe once, run write tests (if `--write`), run read tests, emit summary + optional JSON report |
| CLI plumbing | ~line 2247–2360 | `main()` — argparse, auth prompt, `asyncio.run(run_all(args))` |

### The exact JSON report contract (must be preserved)

`DiagnosticReport.to_json()` returns a top-level object with **four**
keys:

- **`device`** — `{"class", "model", "firmware", "host"}` where `host`
  is always the literal `"<redacted>"`.
- **`auth`** — `{"method", "ssl", "verify_ssl"}`.
- **`observed_schemas`** — a mapping of endpoint → sorted list of field
  names observed in successful responses.
- **`tests`** — a list of per-test records. **Each test record carries
  its own `http_events` list** (`DiagnosticTestRecord.to_json()` emits
  `name`, `label`, `status`, `capability_status`, `reason`, `endpoint`,
  `request_fields`, `observed_fields`, `failure_shape`, and
  `http_events`).

> **Reconciliation note (important):** Issue #208 lists the schema as
> `device`, `auth`, `observed_schemas`, `tests`, `http_events` — implying
> `http_events` is a **top-level** key. In the live code it is **not**:
> `http_events` is nested **inside each `tests[]` record**, and each HTTP
> event carries `method`, `endpoint`, `http`, `retcode`, `retmsg`,
> `observed_fields`, `request_fields`, optional `exception_*`, and a
> redacted `body_snippet` (present only for HTTP or Akuvox-retcode
> failures). The extraction MUST preserve the **actual** nested shape
> exactly; it MUST NOT invent a new top-level `http_events` key. Every
> claim in this spec about the schema reflects the live `to_json()`
> methods, not the issue's shorthand.

### The redaction policy (must be preserved)

- Body excerpts in the returned structure are **always** redacted:
  `_redact_json_values()` replaces every JSON leaf value with
  `"<redacted>"`, and `body_snippet` is only recorded at all for HTTP or
  retcode **failures** (successful bodies are omitted, not redacted).
- Non-JSON and scalar bodies are replaced with fixed privacy sentinels
  (`<non-json response body omitted for privacy>` /
  `<scalar JSON response body omitted for privacy>`).
- `host` is always `"<redacted>"` in the report.
- The report structure never contains credentials, PINs, MACs, names,
  phone numbers, or the OpenDoor password.
- The CLI's separate `--redact-stdout` behaviour (redacting **terminal**
  output) is orthogonal to the returned structure — the JSON/return-value
  redaction is unconditional and independent of it.

### The read-only probe (align, do not duplicate)

`src/pylocal_akuvox/_capability_probe.py::probe_capabilities()` runs a
deterministic 9-call **read-only** sequence and returns a frozen
`DeviceCapabilities` profile (byte-equal across consecutive runs, no
wall-clock timestamp). `AkuvoxDevice.probe_capabilities()` is the public
handle; `mvp_test.py` already calls it exactly once
(`_probe_device_capabilities`) and threads the profile into every
subsequent connection. The new API's read-only mode MUST reuse this probe
for capability discovery rather than reimplementing it.

### Capability gating (must be honored)

`AkuvoxDevice.attempt_unknown_capability` (default `False`) controls
whether `UNKNOWN` capabilities are attempted. `mvp_test.py`'s `step()`
consults the shared `DeviceCapabilities` profile and prints
`SKIP: <name>: ...` for `UNSUPPORTED` / `UNKNOWN` steps instead of
attempting-and-failing; `_install_probed_capabilities()` keeps the
`step()`-level gate and the device's per-method wrapper gate in sync. The
extracted API MUST preserve this gating behaviour and honor
`attempt_unknown_capability`.

### The device's connection-per-CRUD-group workaround (constraint)

`run_all()` does **not** run the whole suite on one connection. Because
Akuvox firmware (observed on E18 `18.30.10.72`) corrupts internal CGI
state under rapid successive requests, `mvp_test.py` opens a **fresh
short-lived connection per CRUD group** with a settle pause between
groups (`_MUTATION_SETTLE_SECS`). This is material to the extracted API's
signature: the issue's sketch passes an *already-entered*
`AkuvoxDevice`, but the current write flow creates and closes multiple
connections internally from `device_kwargs`. Reconciling "takes an entered
device" against "opens/closes several connections" is an open design
question (see Outstanding Clarifications).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate a read-only capability report from code (Priority: P1)

An integrator (the HA integration, or any consumer) has an entered
`AkuvoxDevice` and calls `run_capability_report(device)` with defaults.
They receive the same redacted JSON-serializable structure the CLI's
`--json-report` produces in read-only mode, without shelling out to the
CLI or reimplementing the harness.

**Why this priority**: This is the core of the extraction — a public,
importable producer of the report structure. It unblocks the downstream
HA service and removes the ~2000-line duplication risk.

**Independent Test**: Call `run_capability_report(device)` (defaults,
`write=False`) against a stub/fake device and assert the returned dict
has exactly the top-level keys `device`, `auth`, `observed_schemas`,
`tests`, with per-test `http_events` nested, and that it equals what the
CLI produces for the same device.

**Acceptance Scenarios**:

1. **Given** an entered `AkuvoxDevice`, **When** `run_capability_report(device)`
   is awaited with defaults, **Then** it returns a JSON-serializable
   `dict` whose top-level keys are exactly `device`, `auth`,
   `observed_schemas`, `tests`.
2. **Given** the same device, **When** the report is produced via the API
   and via the CLI's `--json-report` path in read-only mode, **Then** the
   two structures are equal (the CLI derives its report from the API).
3. **Given** a device whose read probe fails at step 1 (auth/connection),
   **When** `run_capability_report(device)` is awaited, **Then** the same
   error type the CLI surfaces is raised (no silent partial report).

---

### User Story 2 — Write-mode report captures CRUD evidence and cleans up (Priority: P1)

The integrator calls `run_capability_report(device, write=True)`. The API
exercises the full create/modify/delete suite against **throwaway** test
entities (users, schedules, groups, contacts), records each outcome as
`supported` / `unsupported` / `unknown` evidence, and cleans up the
throwaway entities — exactly as `mvp_test.py --write` does today.

**Why this priority**: The write-mode `supported` evidence is the single
most valuable signal for capability-matrix authoring and is the reason
the HA integration needs this API at all (read-only is already covered by
`probe_capabilities()`).

**Independent Test**: Call `run_capability_report(device, write=True)`
against a fake device that accepts CRUD, and assert the created throwaway
entities are subsequently deleted and that each CRUD step appears in
`tests` with a `capability_status`.

**Acceptance Scenarios**:

1. **Given** a write-capable device, **When** `run_capability_report(device, write=True)`
   is awaited, **Then** the report's `tests` include add/modify/delete
   records for user, schedule, group, and contact, and the throwaway
   entities created during the run are deleted before the call returns.
2. **Given** `write=False` (default), **When** the report is produced,
   **Then** no create/modify/delete request is issued — the run is
   equivalent to today's read-only probe.
3. **Given** an `add_*` step that fails or is skipped, **When** the
   suite continues, **Then** the dependent `modify_*` / `delete_*` /
   `verify_*_deletion` steps are recorded as skipped (dependency skip),
   matching the CLI's behaviour today.
4. **Given** a mid-suite failure after a throwaway entity was created,
   **When** the run unwinds, **Then** cleanup of already-created
   throwaway entities behaves the same way it does in the CLI today
   [NEEDS CLARIFICATION: the CLI's cleanup is per-step delete rather than
   a guaranteed teardown-on-failure; the exact partial-failure
   cleanup/idempotency contract to guarantee at the API boundary is a
   planning decision].

---

### User Story 3 — Opt in to the credentialed OpenDoor relay test (Priority: P2)

The integrator explicitly opts in to the physical OpenDoor relay test by
passing `open_door=True` plus the required credentials. Without the
credentials, the OpenDoor step is skipped (never silently actuated). The
relay is physically triggered only on a deliberate, credentialed opt-in.

**Why this priority**: OpenDoor physically actuates a relay/opens a door,
so it must remain a separate, explicit, credentialed opt-in distinct from
the general write suite. It is lower priority than the core extraction
but must be preserved from the CLI.

**Independent Test**: Call `run_capability_report(device, write=True, open_door=True, ...)`
with and without credentials against a fake device; assert the OpenDoor
step runs only when credentials are supplied and is skipped (with the
same skip reason shape) otherwise.

**Acceptance Scenarios**:

1. **Given** `open_door=True` with valid OpenDoor credentials, **When**
   the write suite runs, **Then** the OpenDoor HTTP relay step executes
   and its outcome is recorded in `tests`.
2. **Given** `open_door=True` **without** the required credentials,
   **When** the suite runs, **Then** the OpenDoor step is skipped with a
   reason indicating the missing credentials (matching the CLI's skip
   reason), and no relay is actuated.
3. **Given** `open_door=False` (default), **When** the report is
   produced, **Then** the OpenDoor step is skipped and the relay is never
   actuated.
4. **Given** `open_door=True` but `write=False`, **When** the call is
   made, **Then** the same guard the CLI enforces (`--open-door requires
   --write`) applies [NEEDS CLARIFICATION: whether the API rejects this
   combination with an error, or simply skips OpenDoor, is a planning
   decision].

---

### User Story 4 — Secrets never leak into the returned report (Priority: P1)

Any consumer that pastes the returned report into a public issue (the
`new_device` template) must be safe: the structure never contains
credentials, PINs, MACs, names, phone numbers, the host, or the OpenDoor
password. Body excerpts are always redacted.

**Why this priority**: The report is designed to be pasted into public
GitHub issues. A redaction regression is a security/privacy incident, so
this is P1 and must be preserved exactly from the CLI.

**Independent Test**: Produce a report from a fake device whose responses
contain sensitive fields; assert every leaf of any recorded body excerpt
is `"<redacted>"`, `host` is `"<redacted>"`, and no credential/PIN/MAC
value appears anywhere in the serialized structure.

**Acceptance Scenarios**:

1. **Given** a device response containing sensitive fields, **When** the
   report is produced, **Then** every recorded `body_snippet` has all
   leaf values replaced with `"<redacted>"`.
2. **Given** any report, **When** it is serialized, **Then** `device.host`
   is `"<redacted>"` and no credential, PIN, MAC, name, phone, or
   OpenDoor password appears anywhere in the structure.
3. **Given** a successful (non-failure) HTTP exchange, **When** the event
   is recorded, **Then** no response `body_snippet` is included at all
   (successful bodies are omitted, not merely redacted), matching the CLI.

---

### User Story 5 — The CLI keeps working, byte-for-byte (Priority: P1)

An existing CLI user runs `uv run examples/mvp_test.py <ip> [--write]
[--json-report ...] [--open-door ...]` after the extraction and sees no
behaviour change: the same stdout flow, the same summary, and a
byte-identical JSON report for the same device interactions.

**Why this priority**: The extraction's central guarantee is "no drift".
If the CLI's observable behaviour or JSON output changes, the extraction
has failed its core purpose.

**Independent Test**: Run the CLI against a recorded/fake device before
and after the extraction and diff the produced JSON report and stdout;
they must match.

**Acceptance Scenarios**:

1. **Given** the same device interactions, **When** the CLI writes a
   `--json-report`, **Then** the produced JSON is byte-identical to what
   the pre-extraction CLI produced.
2. **Given** any CLI invocation (`--write`, `--open-door`,
   `--redact-stdout`, auth flags, SSL flags), **When** it runs, **Then**
   its observable behaviour is unchanged from today.
3. **Given** the extraction is complete, **When** the code is inspected,
   **Then** the CLI derives its report from `run_capability_report()`
   (there is no second copy of the report/redaction/step logic to drift).

---

### Edge Cases

- What happens when the read probe aborts at step 1 (401/403/5xx/parse
  error)? → The API surfaces the same error the probe raises today; it
  does not return a half-built report.
- What happens when a throwaway entity is created but a later step in its
  chain fails before delete? → See User Story 2 scenario 4 / Outstanding
  Clarifications (partial-failure cleanup contract).
- What happens when `open_door=True` but the device class marks OpenDoor
  `UNKNOWN` and `attempt_unknown_capability` is `False`? → The step is
  capability-gated and skipped exactly as any other gated step.
- What happens when the caller passes an un-entered device (no HTTP
  session open)? → Behaviour depends on the entered-device vs
  opens-its-own-connections decision (Outstanding Clarifications).
- What happens on a read-only device class where every write endpoint is
  `UNSUPPORTED`? → All write steps are recorded as skipped with the
  matrix-derived reason; the report still contains valid read evidence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The package MUST export a public asynchronous function
  `run_capability_report(...)` from `pylocal_akuvox` (added to
  `src/pylocal_akuvox/__init__.py` and `__all__`).
- **FR-002**: `run_capability_report` MUST return a JSON-serializable
  `dict` with the **same** structure the CLI's `--json-report` produces:
  top-level keys `device`, `auth`, `observed_schemas`, `tests`, with each
  `tests[]` record carrying its own nested `http_events` (the shape MUST
  match the live `DiagnosticReport.to_json()` /
  `DiagnosticTestRecord.to_json()` / `DiagnosticHttpEvent.to_json()`
  output exactly — see "The exact JSON report contract").
- **FR-003**: The returned structure MUST have the existing redaction
  policy applied unconditionally: body excerpts fully redacted
  (`"<redacted>"` leaves), `host` = `"<redacted>"`, successful bodies
  omitted, non-JSON/scalar bodies replaced with the fixed privacy
  sentinels, and no credential/PIN/MAC/name/phone/OpenDoor-password
  anywhere in the structure.
- **FR-004**: With `write=False` (the default), `run_capability_report`
  MUST be read-only — issuing no create/modify/delete requests — and MUST
  use the existing read-only capability probe for capability discovery
  (it MUST NOT reimplement the 9-call probe).
- **FR-005**: With `write=True`, `run_capability_report` MUST run the
  full create/modify/delete suite against **throwaway** test entities
  (users, schedules, groups, contacts) and clean them up, recording each
  step's outcome as `supported` / `unsupported` / `unknown` evidence,
  matching `mvp_test.py --write` today.
- **FR-006**: `run_capability_report` MUST keep OpenDoor a **separate,
  explicit opt-in** (`open_door=False` by default) that physically
  actuates the relay only when explicitly enabled **and** the required
  credentials are supplied; otherwise the OpenDoor step MUST be skipped
  without actuating the relay.
- **FR-007**: When OpenDoor is opted-in without the required credentials,
  the OpenDoor step MUST be recorded as skipped with a reason matching
  the CLI's skip reason; the relay MUST NOT be actuated.
- **FR-008**: `run_capability_report` MUST honor capability gating —
  consulting the shared `DeviceCapabilities` profile and skipping
  `UNSUPPORTED` / `UNKNOWN` steps — and MUST honor
  `attempt_unknown_capability` exactly as the CLI does today.
- **FR-009**: Write-mode dependent steps (`modify_*` / `delete_*` /
  `verify_*_deletion`) MUST be skipped when their parent `add_*` step
  fails or is skipped, matching the CLI's dependency-skip behaviour.
- **FR-010**: `run_capability_report` MUST support a caller-supplied
  `timeout` and the read-only-vs-write toggle via keyword arguments; the
  exact final signature (including how OpenDoor credentials are passed —
  see Outstanding Clarifications) is a planning decision, but MUST cover
  at least `write`, `open_door`, and `timeout`.
- **FR-011**: `examples/mvp_test.py` MUST become a **thin CLI wrapper**
  that derives its report from `run_capability_report()`, with **no
  observable behaviour change** for CLI users (stdout flow, summary,
  exit codes, and JSON report output preserved).
- **FR-012**: The CLI's produced `--json-report` output MUST be
  byte-identical, for the same device interactions, before and after the
  extraction.
- **FR-013**: `run_capability_report` MUST be documented under
  `docs/api/` — either by extending `docs/api/capabilities.rst`
  ("Contributing a new device class") or adding a new page — including
  its parameters, the returned schema, the redaction guarantees, and the
  OpenDoor opt-in safety note.
- **FR-014**: The feature MUST NOT change `probe_capabilities()`'s
  behaviour, the report's JSON schema, or the redaction policy — it
  preserves all three.
- **FR-015**: The extraction MUST preserve the errors the CLI surfaces
  today (e.g. the probe's auth/connection/parse errors propagate rather
  than being swallowed into a partial report).
- **FR-016**: All new/moved source files MUST carry SPDX headers per
  `REUSE.toml`, and every new function/class MUST have a docstring
  (constitution: docstring + license-header requirements).

### Key Entities *(include if feature involves data)*

- **Capability report (return value)**: A JSON-serializable `dict` with
  `device` (class/model/firmware/redacted host), `auth`
  (method/ssl/verify_ssl), `observed_schemas` (endpoint → sorted
  fields), and `tests` (per-step records, each with nested
  `http_events`). The single artifact consumers paste into the
  `new_device` template.
- **Test record**: One diagnostic step — `name`, `label`, `status`,
  `capability_status` (`supported` / `unsupported` / `unknown` /
  `inconclusive`), `reason`, `endpoint`, `request_fields`,
  `observed_fields`, optional `failure_shape`, and `http_events`.
- **HTTP event**: One captured request/response exchange within a test —
  `method`, `endpoint`, `http`, `retcode`, `retmsg`, `observed_fields`,
  `request_fields`, optional `exception_*`, and a redacted `body_snippet`
  present only for failures.
- **Throwaway test entity**: A user / schedule / group / contact created
  solely to exercise write CRUD and deleted before the run completes.
- **OpenDoor credentials**: The dedicated relay username + password
  (distinct from the device's general auth) required to opt into the
  physical relay test.

## Security Considerations *(mandatory)*

- The returned report is designed to be pasted into public GitHub issues.
  Redaction (FR-003) is a **security boundary**, not a nicety: a
  regression that leaks a credential, PIN, MAC, name, phone, host, or the
  OpenDoor password into the returned structure is a privacy incident.
- OpenDoor physically actuates a relay/opens a door. It MUST remain a
  deliberate, credentialed opt-in (FR-006/FR-007); it MUST never be a
  side effect of the default call or of `write=True` alone.
- The OpenDoor password MUST NOT appear in the returned report, in logs,
  or in any recorded body excerpt.
- The write suite mutates the device. It MUST operate only on throwaway
  entities and clean them up; it MUST NOT modify or delete pre-existing
  device data.

## Out of Scope *(mandatory)*

- **The downstream Home Assistant service** that will *consume*
  `run_capability_report()` (the `SupportsResponse` action in
  `tykeal/homeassistant-local-akuvox`). That is downstream work; this
  spec delivers only the upstream API it depends on.
- **Changing the report's JSON schema or redaction policy.** Both are
  preserved exactly; any schema/redaction change is a separate feature.
- **Changing `probe_capabilities()` behaviour or output shape.**
- **Adding new capability tests or endpoints** beyond what
  `mvp_test.py` already exercises. This is a pure extraction of existing
  coverage.
- **Any `/fcgi/` command other than the existing OpenDoor relay test.**

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consumer can produce the full redacted capability report
  with a single `await run_capability_report(device, ...)` call — zero
  lines of report/step/redaction logic reimplemented outside the package
  (down from ~2000 lines that would otherwise be duplicated).
- **SC-002**: For identical device interactions, the CLI's
  `--json-report` output is byte-identical before and after the
  extraction (100% match).
- **SC-003**: The returned report contains zero secrets: across all
  test fixtures, no credential, PIN, MAC, name, phone, host value, or
  OpenDoor password appears in the serialized structure, and every
  recorded body excerpt has all leaves redacted.
- **SC-004**: The default (`write=False`) call issues zero
  create/modify/delete requests; the `write=True` call leaves zero
  throwaway test entities behind on success.
- **SC-005**: OpenDoor actuates the relay in exactly and only the case
  where it is explicitly opted-in with valid credentials; in every other
  configuration the relay is never actuated.
- **SC-006**: The change lands at the repo's 100% branch-coverage
  standard, with the CLI still passing its existing tests.
- **SC-007**: `run_capability_report` is exported from `pylocal_akuvox`
  and appears in the `docs/api/` documentation build.

## Assumptions

- The read-only probe (`probe_capabilities()` /
  `AkuvoxDevice.probe_capabilities()`) is the intended capability-discovery
  mechanism for read-only mode; the API reuses it rather than adding a
  parallel probe.
- The existing `DiagnosticReport` / redaction / step framework is the
  behaviour to preserve; the extraction moves this logic into the package
  (public or private modules as planning decides) without altering its
  output.
- "An entered `AkuvoxDevice`" in the issue sketch means a device whose
  async context has been entered (capabilities populated), consistent
  with how the rest of the public API is consumed.
- The CLI retains its full argparse surface (`--write`, `--open-door`,
  `--open-door-user`, `--open-door-pass`, `AKUVOX_OPEN_DOOR_PASSWORD`,
  `--json-report`, `--redact-stdout`, auth/SSL flags); only its internals
  change to delegate to the API.
- The E18-style "one connection per CRUD group with a settle pause"
  workaround remains necessary and is preserved by whatever the API does
  internally.

## Outstanding Clarifications

1. **OpenDoor credential-passing shape.** The issue sketch shows only
   `open_door_user=None`, but OpenDoor requires **both** a username **and**
   a password (the CLI takes `--open-door-user` + `--open-door-pass` or
   the `AKUVOX_OPEN_DOOR_PASSWORD` env var). [NEEDS CLARIFICATION: should
   `run_capability_report` take `open_door_user` + `open_door_password`
   parameters, a single credentials object/tuple, or read the password
   from the environment? The password MUST be passable programmatically
   so the HA service can supply it without relying on process env.]
2. **Entered device vs. opens-its-own-connections.** The issue passes an
   *already-entered* `AkuvoxDevice`, but the current write flow builds
   `device_kwargs` and opens/closes **multiple** short-lived connections
   (one per CRUD group, with settle pauses) to dodge the E18 CGI-state
   bug. [NEEDS CLARIFICATION: does the API take an entered device and
   internally re-open connections from its parameters, take connection
   parameters instead of an entered device, or take an entered device and
   accept single-connection semantics (dropping the per-group reconnect)?
   This directly affects the signature and the write-mode reliability
   contract.]
3. **Partial-failure cleanup / idempotency for throwaway entities.** The
   CLI deletes each throwaway entity as an explicit per-chain step; there
   is no guaranteed teardown if the run aborts mid-chain. [NEEDS
   CLARIFICATION: what cleanup guarantee should the API boundary make on
   partial failure — best-effort teardown of any already-created
   throwaway entity, or preserve the CLI's per-step-delete behaviour
   as-is?]
4. **Module / documentation placement.** [NEEDS CLARIFICATION: should the
   extracted logic live in a new public module (e.g.
   `pylocal_akuvox/capability_report.py`) with private helpers, and
   should docs extend `docs/api/capabilities.rst` or add a new
   `docs/api/report.rst` page? Planning to decide public-vs-private split
   of the moved helpers.]
5. **Read-only return shape parity.** [NEEDS CLARIFICATION: read-only mode
   returns the fuller `mvp_test` JSON structure (`device`/`auth`/
   `observed_schemas`/`tests`), which is richer than
   `probe_capabilities()`'s `DeviceCapabilities`. Confirm the API always
   returns the fuller report structure (not the `DeviceCapabilities`
   profile) even in read-only mode — this spec assumes yes, so a single
   return type serves both modes.]

## Dependencies

- **Read-only probe**: `src/pylocal_akuvox/_capability_probe.py` /
  `AkuvoxDevice.probe_capabilities()` — reused for capability discovery.
- **Device facade**: `src/pylocal_akuvox/device.py` (`AkuvoxDevice`,
  `attempt_unknown_capability`, CRUD methods, `open_door_http`).
- **Public surface**: `src/pylocal_akuvox/__init__.py` — where
  `run_capability_report` is exported.
- **CLI**: `examples/mvp_test.py` — rewritten as a thin wrapper.
- **Evidence target**: `.github/ISSUE_TEMPLATE/new_device.yml` — the
  report feeds this template's fields.
- **Docs**: `docs/api/capabilities.rst` (and possibly a new page).

## References

- Issue #208 (this feature).
- Downstream consumer / tracking:
  `tykeal/homeassistant-local-akuvox#149` (integration adaptation).
- Related upstream: capability-matrix work (#123), OpenDoor HTTP
  (spec `012-open-door-http`, issue #122), apartment-book contacts
  (spec `013-apartment-book-contacts`), capability-probe split
  (spec `010-capability-probe-split`).
