<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: OpenDoor HTTP Relay Unlock

**Branch**: `012-open-door-http` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-open-door-http/spec.md`

## Summary

Issue #122 asks for first-class support for Akuvox's vendor-documented
`GET /fcgi/do?action=OpenDoor` door-unlock command — a **credentialed,
clear-text-URL** relay trigger that is the only working programmatic unlock
path on some device classes (notably the IT83 indoor monitor, where every
`/api/relay/*` call returns `No hanlders for this request`). <!-- codespell:ignore hanlders -->

This is **not a greenfield addition**. `main` already ships a partial FCGI
relay variant — `Capability.RELAY_TRIGGER_FCGI`, the `_fcgi_relay_trigger`
adapter, the `RELAY_TRIGGER_ADAPTERS` / `RELAY_TRIGGER_PREFERENCE` /
`CAPABILITY_TO_VARIANT` dispatch registries, the IT83 capability-matrix
entry, and pinning tests in `tests/unit/test_dispatch.py`. That adapter
issues `GET /fcgi/do?action=OpenDoor&relay=<num>` via the raw request path
**with no credentials** and using the wrong query parameter name
(`relay=` instead of the vendor-documented `DoorNum=`). A correctly
configured device rejects it, and shipping it violates FR-015 (no
credential-less OpenDoor request may ship).

The plan therefore delivers a **corrective + additive** change:

1. **Add** a non-capability-gated, credentialed helper
   `open_door_http(http, *, user, password, door_num=1)` in `relay.py` plus
   a thin `AkuvoxDevice.open_door_http(...)` passthrough — the **sole** code
   path that issues the OpenDoor request, with mandatory URL-encoding
   (FR-002), password redaction (FR-003), raw/non-JSON response handling on
   HTTP status (FR-004/FR-008), and `door_num` validation (FR-005).
2. **Retire the credential-less request** from the capability-dispatch path
   (recommended option **(a)**, see "Resolved Clarification 2"): the
   `_fcgi_relay_trigger` adapter no longer issues a credential-less
   OpenDoor request. The `RELAY_TRIGGER_FCGI` capability member and the
   IT83 matrix entry are **retained as-is** (per the spec's Out-of-Scope
   note); the dispatch adapter is converted to an actionable guard that
   directs callers to `open_door_http`.
3. **Document** the two-mechanism choice and the clear-text trade-off
   (FR-009/FR-010), and **opt-in** OpenDoor exercise in
   `examples/mvp_test.py --write` (FR-012).

This `plan.md` PR is **documentation only**. It does **not** modify `src/`,
`tests/`, `examples/`, or `docs/`, and it does **not** close #122 — the
later implementation PR carries the closing keyword. Both deliberate
[NEEDS CLARIFICATION] markers from the spec are resolved here (see "Resolved
Clarifications").

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also
exercises forward versions.
**Primary Dependencies**: No new runtime or test dependencies. Runtime:
`aiohttp` (already present). Encoding uses the standard library
(`urllib.parse`) and/or the existing aiohttp/yarl query encoder; redaction
logging uses the standard-library `logging` module. Tooling (`ruff`,
`mypy`, `interrogate`, `aislop`, `sphinx`, `pytest`, `pytest-asyncio`,
`aioresponses`) is unchanged.
**Storage**: N/A — async Python library; no persistence. Per FR / Security
Considerations, relay credentials are **never** stored or cached.
**Testing**: pytest + pytest-asyncio + `aioresponses`. New unit tests in
`tests/unit/test_relay.py` (OpenDoor construction, encoding, redaction,
success/failure shapes, validation) and updates to
`tests/unit/test_dispatch.py` (the FCGI dispatch behaviour change).
100% branch coverage is required and enforced.
**Target Platform**: Async Python applications on Linux/macOS/Windows. No
platform-specific behaviour.
**Project Type**: Single Python package under `src/pylocal_akuvox/`.
**Performance Goals**: One additional `GET` request per unlock; no new
async boundary, retry, or throttling behaviour. Reuses the existing
`_request_raw` lock + post-request delay so OpenDoor traffic obeys the same
device-throttling guarantee as every other call. No performance-sensitive
path is introduced, so no benchmark is required (Constitution IV).

**Constraints**:

- **FR-015 is non-negotiable**: after this feature lands, **no** shipped
  code path may issue `action=OpenDoor` without `UserName`/`Password`.
- **FR-002**: credentials MUST be URL-encoded, never raw-interpolated into
  the URL string. The encoder MUST treat `&`, `=`, `@`, space, and
  non-ASCII safely so a credential cannot alter the query structure.
- **FR-003**: the literal `Password` value MUST NOT appear in any log
  record; `UserName`, `DoorNum`, and `action` MAY remain visible.
- **FR-004/FR-008**: the OpenDoor path MUST use the raw, non-JSON
  `_request_raw` path and classify success/failure on HTTP status; a
  non-JSON failure body MUST NOT surface as `AkuvoxParseError`.
- **FR-006**: `open_door_http` MUST be callable without a successful
  capability probe (not capability-gated).
- **FR-007**: relay credentials are per-call and independent of the
  device's general `AuthConfig`.
- **FR-013**: only `action=OpenDoor` on `/fcgi/do` is added; no other
  `/fcgi/` command and no runtime mechanism auto-detection.
- `src/`, `tests/`, `examples/`, and `docs/` are **not** touched by this
  plan PR; all code changes belong to the later implementation PR.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2.
Re-checked after the phase plan — see "Post-Design Re-Check".*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | New code lives in `relay.py` (helper + validation) and a thin `AkuvoxDevice` passthrough. SPDX headers already present on all touched files; any new test file gets one. Every new function gets a docstring (purpose, params, returns, raises) and full type annotations. The helper is kept under the C901 ≤10 cyclomatic limit by splitting validation (`_validate_door_num`), redaction (`_redacted_open_door_query`), and status classification into small helpers (mirroring `_validate_relay_trigger_args`). ruff/mypy/interrogate/aislop must pass. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | Unit tests are authored first (red) for each behaviour: URL/param construction, special-character encoding, password redaction, `door_num` default and validation, ≥1 success shape, and ≥1 failure shape per status class (401/403/4xx/5xx). The FCGI dispatch behaviour change is pinned by updating `test_dispatch.py` first. No production code is written before a failing test. |
| **III. User Experience Consistency** | PASS | `open_door_http` mirrors `trigger_relay`'s conventions: keyword-only args, returns `None` on success, raises a named `Akuvox*` exception on failure, validates with `AkuvoxValidationError`. Error messages are actionable and never leak the password. The behaviour change to `trigger_relay` on IT83 (now an actionable raise instead of a broken credential-less request) is documented in the changelog and points callers to `open_door_http`. |
| **IV. Performance Requirements** | PASS | No performance-sensitive path; one GET per unlock, no new async boundary, reuses the existing `_request_raw` lock + post-request delay. No benchmark required. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | Implementation lands as small atomic commits (helper+tests, dispatch correction+tests, docs, mvp_test opt-in) per `AGENTS.md` Conventional Commits with capitalized types and DCO sign-off; AI co-authorship is attributed in `Co-Authored-By` only. This plan PR is a single `Docs(plan)` commit. New files carry SPDX headers. |
| **VI. Phased Development** | PASS | Decomposed into ordered phases below, each with a green checkpoint (targeted tests + ruff + mypy + coverage) before the next. Phase boundaries are documented here and will be carried into `tasks.md` at the next stage. |

**Result**: All gates pass. **Complexity Tracking** remains empty.

## Resolved Clarifications

The spec deliberately retained two [NEEDS CLARIFICATION] markers. Both are
resolved here for design purposes; full rationale and alternatives live in
[research.md](./research.md).

### Resolved Clarification 1 — Success/failure classification

**Decision**: Classify on **HTTP status** via `_request_raw`, exactly
mirroring the existing `_fcgi_relay_trigger` mapping so integrators catch a
single error family regardless of which path fired:

- `2xx` → success (`open_door_http` returns `None`).
- `401` → `AkuvoxAuthenticationError`.
- `403` and any other `4xx` → `AkuvoxRequestError`.
- `5xx` and any other non-`2xx` → `AkuvoxDeviceError`.
- Transport failures (refused/DNS/timeout) propagate as the existing
  `AkuvoxConnectionError` (raised inside `_request_raw`).

**Assumption (documented)**: the OpenDoor response body shape on real IT83
hardware has **not** been probed, so success is assumed to be signalled by
`2xx` alone (spec Assumptions). The classification is deliberately isolated
in a single helper so that, if a real IT83 returns `HTTP 200` with an
error marker in an HTML/plain-text body, the rule can be **tightened** to
inspect that body marker without touching the request-construction or
redaction code. The failure-shape unit tests (FR-011) pin whichever rule is
adopted; implementation against real hardware MAY tighten it before merge.
A non-JSON body is never routed through the envelope parser, so it can
never surface as `AkuvoxParseError` (FR-004).

### Resolved Clarification 2 — Existing adapter relationship (RECOMMEND a)

The spec offered three options. **Recommendation: option (a)** — *retire
the credential-less request from the capability-dispatch path and route all
real OpenDoor unlocks exclusively through the new credentialed,
non-gated `open_door_http`.*

**Why (a) over (b)/(c)** (verified against live source):

- **(b) thread credentials through `trigger_relay`'s dispatch** would
  overload `trigger_relay`'s capability-gated signature with FCGI-only,
  per-call relay credentials and still leave the call **capability-gated**,
  directly contradicting FR-006 (the method must be callable without a
  probe) and muddying FR-007 (credentials independent of `AuthConfig`).
- **(c) keep both, credential-less adapter for "legacy" devices** is
  forbidden outright: a credential-less OpenDoor request cannot ship
  (FR-015). The current adapter never worked against a correctly
  configured device, so there is no working behaviour to preserve.
- **(a)** is the only option that simultaneously satisfies FR-006
  (non-gated), FR-007 (per-call credentials), and FR-015 (no
  credential-less ship), keeps `trigger_relay` a clean `/api/relay/trig`
  capability dispatcher, and matches the spec's stated entry point
  (`open_door_http`).

**Implementation of (a) — minimal, preserves the matrix "as-is"**: rather
than ripping out the `RELAY_TRIGGER_FCGI` capability member, the dispatch
registries, and the IT83 matrix entry (which the spec's Out-of-Scope
section says to **retain**), the `_fcgi_relay_trigger` adapter is converted
from "issue a credential-less `relay=` request" into an **actionable
guard** that raises `AkuvoxUnsupportedError` (or `AkuvoxValidationError`)
instructing the caller to use `AkuvoxDevice.open_door_http(...)` with the
device's Open-Relay-Via-HTTP credentials. Consequences:

- FR-015 holds: the dispatch path issues **no** request at all, so it can
  never send a credential-less OpenDoor.
- FR-014 is moot for the dispatch path (it issues nothing); the new helper
  uses the correct `DoorNum` parameter.
- `Capability.RELAY_TRIGGER_FCGI` and the IT83 matrix entry are retained
  as **informational** ("this class needs the OpenDoor path"), satisfying
  the Out-of-Scope retention note without extending the probe/matrix
  surface.
- `trigger_relay(num=1)` on an IT83 changes from "issue a broken,
  credential-less request" to "raise an actionable error pointing at
  `open_door_http`". This is a **behaviour change** to a path that never
  functioned correctly, recorded as a `Changed` changelog entry (not a
  public-signature break).

The alternative — fully deleting the FCGI registry entries and removing the
capability from `RELAY_TRIGGER_PREFERENCE`/`CAPABILITY_TO_VARIANT` — is also
FR-compliant and is captured in research.md as the rejected alternative
(more churn; conflicts with the "retain matrix as-is" note).

## Design Overview

### Public/observable contract (fixed by FR-001)

`open_door_http(http, *, user, password, door_num=1) -> None`, with the
`AkuvoxDevice.open_door_http(*, user, password, door_num=1) -> None`
passthrough. The observable request is:

```text
GET /fcgi/do?action=OpenDoor&UserName=<enc>&Password=<enc>&DoorNum=<n>
```

See [contracts/open-door-http.md](./contracts/open-door-http.md) for the
full request/response/error contract and
[quickstart.md](./quickstart.md) for usage.

### Encoding (FR-002)

Credentials are passed as **raw** values into a single URL-encoding step —
never string-interpolated into the path. The implementation builds an
ordered parameter mapping (`action`, `UserName`, `Password`, `DoorNum`) and
hands it to the encoder exactly once. The recommended mechanism is the
`params=` argument already supported by
`AkuvoxHttpClient._request_raw` (aiohttp/yarl encodes each value once),
which avoids the double-encoding hazard of putting a pre-built query string
into the path (the existing adapter's inline
`/fcgi/do?action=OpenDoor&relay={num}` style would re-encode `%` in a
credential). research.md records the `urllib.parse.urlencode` alternative
and why a single-encoder rule matters.

### Redaction & logging (FR-003)

`src/pylocal_akuvox/` currently emits **no** logs, so there is no existing
request-logging leak. The helper adds a module-level
`logging.getLogger(__name__)` and emits at most a **DEBUG** record built
from a dedicated `_redacted_open_door_query(...)` helper that renders the
query with the `Password` value replaced by a redaction placeholder
(`<redacted>`, matching the `examples/mvp_test.py` `_REDACTED_VALUE`
convention) while leaving `action`, `UserName`, and `DoorNum` visible.
Redaction does **not** depend on log level being low — the raw password is
never passed to any log call or embedded in any exception message
(failure messages carry status + a truncated *body* excerpt, never the
request URL/credentials).

### Validation (FR-005)

A `_validate_door_num(door_num)` helper (mirroring
`_validate_relay_trigger_args`) raises `AkuvoxValidationError` for a
non-positive value, a non-integer, or a `bool` (which is an `int`
subclass), **before** any network request is issued.

### Dispatch correction (FR-014/FR-015)

`_fcgi_relay_trigger` is converted to an actionable guard (see Resolved
Clarification 2). `RELAY_TRIGGER_ADAPTERS`, `RELAY_TRIGGER_PREFERENCE`,
`CAPABILITY_TO_VARIANT`, the `RELAY_TRIGGER_FCGI` enum member, and the IT83
matrix entry are retained. Existing `tests/unit/test_dispatch.py`
assertions that pin `relay=1` and a successful credential-less dispatch are
updated to assert the new guard behaviour.

## Project Structure

### Documentation (this feature)

```text
specs/012-open-door-http/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 — design decisions & alternatives
├── contracts/
│   └── open-door-http.md  # Observable request/response/error contract
├── quickstart.md        # Usage example & mechanism-choice guidance
├── checklists/
│   └── requirements.md  # (from the spec stage)
├── spec.md              # (merged spec stage)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

A standalone `data-model.md` is intentionally **omitted**: this feature
adds no domain entity or persistence. The three "Key Entities" in the spec
(OpenDoor request, HTTP-relay credential pair, OpenDoor outcome) are fully
described by the contract in `contracts/open-door-http.md`; a separate data
model would be redundant.

### Source Code (repository root) — touched by the LATER implementation PR

```text
src/pylocal_akuvox/
├── relay.py                 # + open_door_http(), _validate_door_num(),
│                            #   _redacted_open_door_query(), module logger
├── device.py                # + AkuvoxDevice.open_door_http() passthrough
│                            #   (non-capability-gated)
├── capability_adapters.py   # _fcgi_relay_trigger -> actionable guard
│                            #   (no credential-less request)
├── capability_matrix.py     # IT83 entry retained; comment updated to
│                            #   reference open_door_http
└── _capability_types.py     # RELAY_TRIGGER_FCGI retained (informational)

tests/unit/
├── test_relay.py            # + OpenDoor construction/encoding/redaction/
│                            #   validation/success+failure-shape tests
└── test_dispatch.py         # FCGI dispatch behaviour-change updates

examples/mvp_test.py         # + --open-door opt-in flag & relay creds
docs/quickstart.rst, README.md, docs/changelog.rst
                             # + two-mechanism guidance, trade-off, changelog
```

**Structure Decision**: Single Python package; the feature is a small
credentialed HTTP helper plus a dispatch correction. No new module is
required — `open_door_http` belongs beside `trigger_relay` in `relay.py`,
and the facade passthrough beside `AkuvoxDevice.trigger_relay` in
`device.py`.

### Agent context

`update-agent-context.sh` is **not** run for this feature: it introduces no
new technology (no new runtime/test dependency, same Python, same tooling),
and recent specs (009–011) likewise did not regenerate
`.github/agents/copilot-instructions.md`. Re-running it would add only a
churn-only "Recent Changes" bullet, so it is intentionally skipped per the
workflow rule "Add only new technology from current plan".

## Phases

Phases are ordered so each lands as an atomic, independently testable
commit with a green checkpoint (targeted tests + ruff + mypy + 100% branch
coverage) before the next begins.

### Phase 1 — `open_door_http` helper + validation (TDD)

**Goal**: the credentialed helper in `relay.py`, the sole OpenDoor request
path.

- Red: tests in `tests/unit/test_relay.py` for request construction
  (`action=OpenDoor`, `UserName`, `Password`, `DoorNum`), `door_num`
  default `1`, and `door_num` validation (non-positive / non-int / `bool`
  → `AkuvoxValidationError`, **zero** requests issued).
- Green: add `open_door_http(http, *, user, password, door_num=1)` and
  `_validate_door_num()`; issue the request via `_request_raw` with the
  `params=` mapping; classify on HTTP status per Resolved Clarification 1.
- Covers FR-001, FR-004, FR-005, FR-006 (free function is inherently
  non-gated), FR-008.

### Phase 2 — Encoding + redaction (TDD)

**Goal**: FR-002 and FR-003.

- Red: tests asserting special-character credentials (`p@ss &word=1`,
  `a b`, non-ASCII) are percent-encoded and never alter the query
  structure (SC-002); a `caplog`-based test asserting the literal password
  is **absent** from log output while `action`/`UserName`/`DoorNum` remain
  visible (SC-003).
- Green: route all values through the single encoder; add the module
  logger and `_redacted_open_door_query()`; ensure no exception message
  embeds credentials.
- Covers FR-002, FR-003; SC-002, SC-003.

### Phase 3 — `AkuvoxDevice.open_door_http` passthrough (TDD)

**Goal**: FR-001 facade surface; FR-006 non-gated.

- Red: test that the passthrough delegates to `relay.open_door_http` with
  the supplied args and succeeds **without** a prior `probe_capabilities`
  call (not capability-gated).
- Green: add the thin `AkuvoxDevice.open_door_http(*, user, password,
  door_num=1)` that calls `relay.open_door_http(self._http, ...)` directly
  (no `_context()` / capability `require`).
- Covers FR-001, FR-006, FR-007; SC-001.

### Phase 4 — Dispatch correction (TDD)

**Goal**: FR-014/FR-015 against the existing FCGI path.

- Red: update `tests/unit/test_dispatch.py` so the IT83 (and
  `attempt_unknown` X916) FCGI dispatch asserts the new **actionable
  raise** instead of a credential-less `relay=1` request; assert no
  `/fcgi/do` request is issued by the dispatch path.
- Green: convert `_fcgi_relay_trigger` to the guard; retain the registries,
  `RELAY_TRIGGER_FCGI`, and the IT83 matrix entry; update the matrix
  comment to reference `open_door_http`.
- Covers FR-014, FR-015.

### Phase 5 — Documentation (FR-009/FR-010)

**Goal**: docstring + user docs.

- `open_door_http` docstring states (a) the clear-text-URL trade-off
  (password visible in proxy/device access logs, by vendor design) and
  (b) the **Phone → Relay → Open Relay Via HTTP** prerequisite (FR-009).
- `docs/quickstart.rst` / `README.md` gain a relay section contrasting
  `/fcgi/do?action=OpenDoor` with `/api/relay/trig` (prerequisite +
  security trade-off) (FR-010); `docs/changelog.rst` gets an `Added`
  bullet for `open_door_http` and a `Changed` bullet for the IT83
  `trigger_relay` dispatch behaviour, referencing #122.
- Covers FR-009, FR-010; SC-006.

### Phase 6 — MVP script opt-in (FR-012)

**Goal**: optional real-hardware exercise.

- Add an `--open-door` opt-in flag plus relay credentials
  (`--open-door-user` / `--open-door-pass`, password also accepted via an
  env var). In `--write` mode, fire OpenDoor **exactly once** when the flag
  and credentials are present; otherwise **skip and report** (never fail).
  Add unit coverage in `tests/unit/test_mvp_test.py`.
- Covers FR-012; SC tied to US4.

### Phase boundary checkpoints

Each phase ends green: targeted pytest subset, `ruff check`, `mypy`,
`interrogate`, and `aislop ci` clean, with **100% branch coverage** on new
/ changed lines. CI must pass before any manual hardware validation
(Constitution II/VI).

## Post-Design Re-Check (Constitution)

Re-evaluated after the phase plan:

- **I. Code Quality** — still PASS. Helper complexity stays ≤ C901 10 via
  the validation/redaction/classification split; docstrings and type
  annotations on every new symbol; SPDX headers intact.
- **II. TDD** — still PASS. Every phase leads with a failing test; the
  dispatch behaviour change is pinned before the source edit.
- **III. UX Consistency** — still PASS. `open_door_http` matches
  `trigger_relay` conventions; the IT83 dispatch change is actionable and
  changelog-documented.
- **IV. Performance** — still PASS. No new benchmarked path.
- **V. Atomic Commits** — still PASS. Six focused phases map to atomic,
  signed, conventionally-typed commits.
- **VI. Phased Development** — still PASS. Ordered phases, each with a green
  checkpoint; boundaries documented here and carried into `tasks.md`.

**Result**: All gates still pass. **Complexity Tracking** remains empty.

## Complexity Tracking

> No Constitution violations — this table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Artifacts Generated

- `plan.md` (this file)
- `research.md` — design decisions, both clarifications resolved,
  adapter-relationship recommendation with rejected alternatives
- `contracts/open-door-http.md` — observable request/response/error
  contract
- `quickstart.md` — usage example + mechanism-choice guidance

`tasks.md` is **not** produced by this stage (`/speckit.tasks` follows).

## Remaining [NEEDS CLARIFICATION]

Both spec markers are resolved at the design level (see "Resolved
Clarifications"). One **soft** item remains for the implementation stage,
explicitly bounded so it does not block planning:

- The exact OpenDoor success/failure **body** behaviour on real IT83
  hardware is still unprobed. The plan adopts the HTTP-status default and
  isolates classification in one helper so the rule can be tightened
  against a live device during implementation without reworking
  request construction or redaction. The failure-shape tests pin whichever
  rule ships.
