<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: OpenDoor HTTP Relay Unlock

**Input**: Design documents from `/specs/012-open-door-http/`
**Prerequisites**: spec.md, plan.md, research.md,
contracts/open-door-http.md, quickstart.md (all merged to `main`).
**Branch**: `012-open-door-http` hosts the future implementation PR. The
spec PR, plan PR, and this tasks artifact each ship as separate
documentation PRs. This tasks PR leaves every checkbox **unchecked**;
checkbox flips ride on the later implementation PR (per AGENTS.md §"Task
List Updates Are Separate Commits").

**Tests are MANDATORY** per constitution §II (TDD). Each phase leads with a
failing (red) test before the production change (green). No production code
is written before a failing test pins the behaviour.

**Atomic commits** per AGENTS.md §"Atomic Commits": the implementation PR
keeps the helper, dispatch correction, docs, changelog, and mvp_test opt-in
as logically separate commits. Only the implementation PR carries the
`Closes #122` keyword — this tasks PR references #122 without closing it.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no
  incomplete dependencies between them).
- **[Story]**: Maps the task to a spec user story (US1–US4) where one
  applies. Cross-cutting setup, dispatch-reconciliation, and final-sweep
  tasks carry no story label.
- Every task names exact file path(s), a goal, files touched, and
  acceptance criteria.

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, `tests/unit/`, `examples/`,
`docs/`. Spec artifacts in `specs/012-open-door-http/`.

## User-story → phase map

| Story | Priority | Phases |
|---|---|---|
| US1 — Unlock where the JSON relay API fails | P1 | Phase 2 (helper), Phase 4 (device passthrough) |
| US2 — Credentials encoded, never leaked to logs | P1 | Phase 3 |
| US3 — Choose the correct mechanism with guidance | P2 | Phase 6 |
| US4 — Optionally exercise OpenDoor from the MVP script | P3 | Phase 7 |
| (cross-cutting) reconcile the FCGI dispatch path | — | Phase 5 (FR-014/FR-015) |

## Live-source validation cheat sheet

Validated against `main` at tasks-authoring time (worktree base
`c15a6c2`). Re-run these checks before implementation; **live source is
canonical** if anything drifts.

- `src/pylocal_akuvox/relay.py`: module imports `from __future__ import
  annotations`; `from typing import TYPE_CHECKING, Any`; `from
  pylocal_akuvox.exceptions import AkuvoxValidationError`. Contains
  `_MAX_DELAY`, `_validate_relay_trigger_args(*, num, mode, level, delay)`
  (the `isinstance(x, bool) or num < 1` pattern reused for `door_num`),
  `trigger_relay(http, *, num, mode=0, level=0, delay=0)`,
  `get_relay_status(http)`. **No** `logging` import today.
- `src/pylocal_akuvox/_http.py`: `_request_raw(self, method, path, *,
  params=None, data=None, timeout=None) -> tuple[int, str]` acquires
  `self._lock`, honours `_post_request_delay`, wraps transport errors as
  `AkuvoxConnectionError`, and forwards `params` to aiohttp (`kwargs
  ["params"] = params`). This is the raw, non-JSON path required by FR-004.
- `src/pylocal_akuvox/capability_adapters.py`: `_fcgi_relay_trigger(http,
  args)` (lines ~81-124) currently issues `await http._request_raw("GET",
  f"/fcgi/do?action=OpenDoor&relay={args.num}")` with **no credentials**,
  rejects non-zero `mode`/`level`/`delay`, and maps 2xx/401/4xx/5xx. The
  `# noqa: SLF001` on the `_request_raw` call is to be removed with the
  call. Registries `RELAY_TRIGGER_ADAPTERS`
  (`(Capability.RELAY_TRIGGER_FCGI, "fcgi"): _fcgi_relay_trigger`),
  `RELAY_TRIGGER_PREFERENCE`, `CAPABILITY_TO_VARIANT`, and the frozen
  `RelayTriggerArgs` dataclass are retained.
- `src/pylocal_akuvox/device.py`: `AkuvoxDevice.trigger_relay(*, num,
  mode=0, level=0, delay=0, adapter=None)` delegates to
  `_device_relays.trigger_relay(self._context(), ...)`. `self._http` is the
  `AkuvoxHttpClient`; `get_info`/`get_status` already pass `self._http`
  directly (the non-gated pattern `open_door_http` follows — **not**
  `self._context()`). `_device_relays` is imported at module top.
- `src/pylocal_akuvox/capability_matrix.py`: `_IT83_83_30_10_4` (line ~69)
  sets `RELAY_TRIGGER_API = UNSUPPORTED`, `RELAY_TRIGGER_FCGI = SUPPORTED`,
  with a `# Issue #122: IT83 supports relay only via FCGI OpenDoor.`
  comment (line ~73) to be updated to reference `open_door_http`.
- `src/pylocal_akuvox/_capability_types.py`: `Capability.RELAY_TRIGGER_API`
  / `RELAY_TRIGGER_FCGI` members — both retained.
- `src/pylocal_akuvox/exceptions.py`: `AkuvoxError`,
  `AkuvoxConnectionError`, `AkuvoxAuthenticationError`,
  `AkuvoxRequestError`, `AkuvoxDeviceError`, `AkuvoxParseError`,
  `AkuvoxUnsupportedError` (the guard exception), `AkuvoxValidationError`.
- `tests/unit/test_relay.py`: imports `AkuvoxConnectionError`,
  `AkuvoxDeviceError`, `AkuvoxValidationError`, `register_default_info`,
  `BASE_URL = "http://192.168.1.100"`; OpenDoor tests are added here.
- `tests/unit/test_dispatch.py`: module docstring (lines ~9-16) describes
  IT83 → `/fcgi/do?action=OpenDoor&relay=<num>`. These tests pin the
  current credential-less behaviour and **must** be rewritten in Phase 5:
  `test_it83_routes_to_fcgi_do` (~137),
  `test_x916_with_fcgi_adapter_and_attempt_unknown_dispatches` (~193),
  `test_fcgi_adapter_rejects_nonzero_extras` (~218),
  `test_fcgi_adapter_accepts_non_json_success_body` (~293),
  `test_fcgi_adapter_raises_device_error_on_http_500` (~307),
  `test_fcgi_adapter_raises_auth_error_on_http_401` (~324),
  `test_fcgi_adapter_raises_request_error_on_http_403` (~350). The
  `test_it83_with_api_adapter_*` (capability_missing) and
  `test_x916_with_fcgi_adapter_default_raises_capability_unknown` tests are
  **unaffected** (they assert dispatch-gating, not the request payload).
- `examples/mvp_test.py`: `_REDACTED_VALUE = "<redacted>"` (line ~89);
  `argparse` block builds flags in `main()` (~2108-2183, `parser.error`
  validation at ~2190); `_run_write_tests(...)` (~1750) wires steps via
  `step(...)`/`skip_step(...)`; `test_trigger_relay(device)` (~1295) calls
  `device.trigger_relay(num=1)`; the relay-trigger `step(...)` is gated on
  `(RELAY_TRIGGER_API, RELAY_TRIGGER_FCGI)` (~1877).
- `tests/unit/test_mvp_test.py`: existing unit coverage for the MVP script;
  new OpenDoor opt-in/skip coverage is added here.
- `docs/changelog.rst`: `Unreleased` block already has `Changed` (~52) and
  `Added` (~62) subsections under the `^^^` underline convention.
  `docs/quickstart.rst` (relay usage near line ~123) and `README.md` gain
  the two-mechanism note.

---

## Phase 1: Setup & baseline

**Purpose**: Confirm the working tree and capture the current green state
before any TDD red step.

- [ ] T001 Capture the pre-change baseline on `main`.

  - **Goal**: Record that the suite is green and the FCGI dispatch tests
    currently pin the credential-less `relay=1` request, so later red/green
    transitions are unambiguous.
  - **Files touched**: none (read-only).
  - **Steps**:
    1. `uv run pytest tests/unit/test_relay.py tests/unit/test_dispatch.py tests/unit/test_mvp_test.py -q` — confirm green.
    2. `uv run pytest -q` then `uv run ruff check`, `uv run mypy src tests`,
       `uv run interrogate -c pyproject.toml`, and the project `aislop`
       gate — confirm all clean and coverage at the required 100% branch
       level.
    3. Re-grep the cheat-sheet symbols above and reconcile any drift before
       proceeding.
  - **Acceptance criteria**: full suite green; lint/type/docstring/aislop
    gates clean; cheat-sheet symbols confirmed present at the stated
    locations.

---

## Phase 2 (plan Phase 1): `open_door_http` helper + validation (TDD) — US1

**Goal**: The credentialed free function in `relay.py` — the **sole**
OpenDoor request path — plus `door_num` validation. Covers FR-001, FR-004,
FR-005, FR-006 (a free function is inherently non-gated), FR-008, FR-013.

- [ ] T002 [US1] Red — author construction, default, classification, and
  validation tests for `open_door_http` in `tests/unit/test_relay.py`.

  - **Goal**: Pin the observable request and the status→exception mapping
    before any production code exists.
  - **Files touched**: `tests/unit/test_relay.py` only.
  - **Assertions** (use `aioresponses`, mirroring existing relay tests):
    1. A success call issues exactly **one** `GET` to `/fcgi/do` whose
       query carries `action=OpenDoor`, `UserName=<user>`,
       `Password=<password>`, and `DoorNum=<n>`; `open_door_http(...)`
       returns `None` (FR-001, US1 scenario 1).
    2. Omitting `door_num` defaults `DoorNum=1` (FR-001, US1 scenario 2).
    3. Status classification (Resolved Clarification 1 /
       contracts/open-door-http.md): `2xx` → returns `None`; `401` →
       `AkuvoxAuthenticationError`; `403` and another `4xx` (e.g. `404`) →
       `AkuvoxRequestError`; `500` and another non-2xx (e.g. `302`/`418` per
       chosen rule) → `AkuvoxDeviceError` (FR-008; SC-005).
    4. A non-JSON failure body (HTML/plain text) raises the mapped
       `Akuvox*` error and **never** `AkuvoxParseError`; assert at least one
       success shape uses a non-JSON body too (FR-004; SC-005).
    5. Transport failure surfaces `AkuvoxConnectionError` (raised inside
       `_request_raw`) — e.g. via `aioresponses` exception injection.
    6. `door_num` validation issues **zero** requests and raises
       `AkuvoxValidationError` for: `0`/negative, a non-int (e.g. `"1"`,
       `1.0`), and `bool` (`True`/`False`) — mirroring
       `_validate_relay_trigger_args` (FR-005; SC-004). Assert zero requests
       were registered/awaited.
  - **Acceptance criteria**: `uv run python -m py_compile tests/unit/test_relay.py` passes; the new tests **fail** (red) because
    `open_door_http`/`_validate_door_num` do not yet exist.

- [ ] T003 [US1] Green — implement `open_door_http` and `_validate_door_num`
  in `src/pylocal_akuvox/relay.py`.

  - **Goal**: Make T002 pass with the helper, validation, and HTTP-status
    classification.
  - **Files touched**: `src/pylocal_akuvox/relay.py` only.
  - **Implementation**:
    1. Add `_validate_door_num(door_num: int) -> None` raising
       `AkuvoxValidationError` for `isinstance(door_num, bool)` or
       non-`int` or `door_num < 1`, mirroring `_validate_relay_trigger_args`
       (a positive-integer message). Raise **before** any request (FR-005).
    2. Add `async def open_door_http(http, *, user, password, door_num=1)
       -> None`. Keyword-only credentials/`door_num` (FR-001/FR-007).
    3. Call `_validate_door_num(door_num)` first, then issue the request via
       the raw path: `status, body = await http._request_raw("GET",
       "/fcgi/do", params={...})` with an **ordered** mapping
       `{"action": "OpenDoor", "UserName": user, "Password": password,
       "DoorNum": door_num}`. Add `# noqa: SLF001` on the `_request_raw`
       call, consistent with the existing adapter call site. Never
       string-interpolate credentials into the path (FR-002/FR-004).
    4. Classify on HTTP status, reusing the `_fcgi_relay_trigger` mapping:
       `2xx` → `return`; `401` → `AkuvoxAuthenticationError`; other `4xx`
       (incl. `403`) → `AkuvoxRequestError`; else → `AkuvoxDeviceError`.
       Failure messages carry status + a truncated **body** excerpt
       (`body[:200]!r`), never the URL/credentials (FR-008). Isolate the
       classification so a future body-marker rule can be tightened in one
       place (research Decision 1).
    5. Import the needed exceptions
       (`AkuvoxAuthenticationError`, `AkuvoxDeviceError`,
       `AkuvoxRequestError`) alongside the existing `AkuvoxValidationError`.
    6. Add a **complete** docstring now (purpose, args, returns, raises)
       per constitution §I, so `interrogate` is green at this phase. The
       FR-009 clear-text/prerequisite security wording is layered onto this
       complete docstring in Phase 6 (T010) — Phase 6 refines the existing
       docstring, it does not first-author it.
    7. Do **not** add `open_door_http` to `pylocal_akuvox.__all__`
       (consistent with `trigger_relay`; research Decision 6). Keep the
       function under C901 ≤10 by delegating validation/classification to
       helpers as needed.
  - **Acceptance criteria**: T002 tests pass; `uv run pytest tests/unit/test_relay.py -q` green; `uv run ruff check`, `uv run mypy src tests`, `uv run interrogate -c pyproject.toml`, and `aislop` clean;
    100% branch coverage on the new lines.

**Checkpoint**: `open_door_http` constructs and classifies correctly and
validates `door_num`; the credentialed request path exists.

---

## Phase 3 (plan Phase 2): Encoding + redaction (TDD) — US2

**Goal**: FR-002 (single-encoder, injection-safe) and FR-003 (password
redaction). Covers SC-002, SC-003.

- [ ] T004 [US2] Red — author special-character encoding and log-redaction
  tests in `tests/unit/test_relay.py`.

  - **Goal**: Pin that arbitrary credentials are encoded exactly once and
    that the literal password never reaches a log record.
  - **Files touched**: `tests/unit/test_relay.py` only.
  - **Assertions**:
    1. With `user="a b"` and `password="p@ss &word=1"` (and at least one
       non-ASCII case), the issued request preserves the intended four
       parameters with the special characters percent-encoded and **no**
       extra/overridden query parameters — a `&`/`=` in the password does
       not split the query (FR-002; SC-002; US2 scenario 1). Inspect the
       recorded request URL/query via `aioresponses`.
    2. Using `caplog` at DEBUG, a successful OpenDoor call emits a record in
       which the literal password text is **absent** while `action`,
       `UserName`, and `DoorNum` remain visible (FR-003; SC-003; US2
       scenarios 2-3).
    3. The literal password is absent from **all** log output across at
       least one success and one failure path, and from any raised
       exception message (SC-003).
  - **Acceptance criteria**: `py_compile` passes; the encoding assertion may
    already pass if `params=` was used in T003, but the redaction/log
    assertions **fail** (red) because no logger/redaction helper exists yet.

- [ ] T005 [US2] Green — add the module logger and
  `_redacted_open_door_query` redaction helper in
  `src/pylocal_akuvox/relay.py`.

  - **Goal**: Make T004 pass with a redacted DEBUG record and a confirmed
    single-encoding pass.
  - **Files touched**: `src/pylocal_akuvox/relay.py` only.
  - **Implementation**:
    1. Add `import logging` and a module-level `_LOGGER =
       logging.getLogger(__name__)`.
    2. Add `_redacted_open_door_query(*, user, door_num) -> <mapping/str>`
       that renders the query with `Password` replaced by the
       `<redacted>` placeholder (matching `examples/mvp_test.py`'s
       `_REDACTED_VALUE`) while keeping `action`, `UserName`, and `DoorNum`
       visible. The raw password is **never** passed to it.
    3. In `open_door_http`, emit at most a single `_LOGGER.debug(...)`
       built from the redaction helper. Redaction is **unconditional** (not
       gated on log level). The raw password must not be interpolated into
       any log call or any exception message (FR-003; Security
       Considerations).
    4. Confirm credentials flow through the single `params=` encoder only
       (no manual `urlencode`, no f-string path interpolation) so encoding
       happens exactly once (FR-002; research Decision 3).
  - **Acceptance criteria**: T002+T004 tests pass; full `test_relay.py`
    green; ruff/mypy/interrogate/aislop clean; 100% branch coverage on new
    lines; `open_door_http` remains ≤ C901 10.

**Checkpoint**: Credentials are injection-safe and the password is redacted
from logs and exceptions on every path.

---

## Phase 4 (plan Phase 3): `AkuvoxDevice.open_door_http` passthrough (TDD) — US1

**Goal**: The facade surface (FR-001) that is **not** capability-gated
(FR-006) and uses per-call credentials independent of `AuthConfig`
(FR-007). Covers SC-001.

- [ ] T006 [US1] Red — author the passthrough delegation/non-gated test.

  - **Goal**: Pin that `AkuvoxDevice.open_door_http` delegates to
    `relay.open_door_http(self._http, ...)` and succeeds **without** a prior
    `probe_capabilities()` call.
  - **Files touched**: `tests/unit/test_relay.py` (or a focused device test
    module — keep it beside the existing relay tests for locality).
  - **Assertions**:
    1. Constructing `AkuvoxDevice` and calling `await
       device.open_door_http(user=..., password=..., door_num=...)` issues
       the same `GET /fcgi/do?...` request as the free function and returns
       `None` — **without** calling `probe_capabilities()` first (FR-006;
       US1 scenario 3; SC-001).
    2. `door_num` defaults to `1` through the passthrough (FR-001).
    3. (Optional) assert the call does not touch `self._capabilities` /
       `_context()` (e.g. patch `relay.open_door_http` and assert it
       receives `device._http`).
  - **Acceptance criteria**: `py_compile` passes; the test **fails** (red)
    because `AkuvoxDevice.open_door_http` does not yet exist.

- [ ] T007 [US1] Green — add `AkuvoxDevice.open_door_http` in
  `src/pylocal_akuvox/device.py`.

  - **Goal**: Make T006 pass with a thin, non-gated passthrough.
  - **Files touched**: `src/pylocal_akuvox/device.py` only.
  - **Implementation**:
    1. Add `async def open_door_http(self, *, user: str, password: str,
       door_num: int = 1) -> None` beside `trigger_relay`.
    2. Body delegates **directly**: `await relay.open_door_http(self._http,
       user=user, password=password, door_num=door_num)` — using
       `self._http` (the `get_info`/`get_status` pattern), **not**
       `self._context()` and with **no** `require_capabilities`/probe call
       (FR-006/FR-007). Ensure `relay` is importable here (add the import if
       `device.py` does not already reference `relay`).
    3. Add a **complete** docstring now (purpose, args, returns, raises)
       per constitution §I, so `interrogate` is green at this phase. The
       FR-009 clear-text/prerequisite security wording is refined onto this
       complete docstring in Phase 6 (T010).
  - **Acceptance criteria**: T006 passes; `uv run pytest tests/unit/test_relay.py -q` green; ruff/mypy/interrogate/aislop clean;
    `device.py` stays under its aislop size limit; 100% branch coverage.

**Checkpoint**: An operator can unlock via `device.open_door_http(...)` with
no capability probe (SC-001 satisfied at the unit level).

---

## Phase 5 (plan Phase 4): Dispatch correction (TDD) — FR-014/FR-015

**Goal**: No shipped path issues a credential-less `action=OpenDoor`
request. Convert `_fcgi_relay_trigger` to an actionable guard; retain the
registries, the `RELAY_TRIGGER_FCGI` member, and the IT83 matrix entry
(research Decision 2, option (a)). Covers FR-014, FR-015.

- [ ] T008 Red — rewrite the FCGI dispatch tests in
  `tests/unit/test_dispatch.py` to pin the guard behaviour.

  - **Goal**: Replace every assertion that the dispatch path issues
    `/fcgi/do?action=OpenDoor&relay=1` with assertions that it raises an
    actionable error and issues **zero** `/fcgi/do` requests.
  - **Files touched**: `tests/unit/test_dispatch.py` only.
  - **Changes** (against the cheat-sheet line numbers):
    1. Update the module docstring (lines ~9-16) to describe IT83 dispatch
       as "raises an actionable error directing callers to
       `open_door_http`" rather than issuing a credential-less request.
    2. Rewrite `test_it83_routes_to_fcgi_do` → assert
       `device.trigger_relay(num=1)` on an IT83 raises
       `AkuvoxUnsupportedError` (the guard exception) **and** that no
       `/fcgi/do` request was registered/issued (FR-015). Assert the error
       message names `open_door_http` (US1/US3 actionability).
    3. Rewrite `test_x916_with_fcgi_adapter_and_attempt_unknown_dispatches`
       → with `attempt_unknown_capability=True` and
       `adapter=Capability.RELAY_TRIGGER_FCGI`, assert the same guard raise
       and zero `/fcgi/do` requests (the adapter no longer dispatches).
    4. Remove or repurpose `test_fcgi_adapter_rejects_nonzero_extras`,
       `test_fcgi_adapter_accepts_non_json_success_body`,
       `test_fcgi_adapter_raises_device_error_on_http_500`,
       `test_fcgi_adapter_raises_auth_error_on_http_401`, and
       `test_fcgi_adapter_raises_request_error_on_http_403`: the guard
       issues no request, so the HTTP-status and mode/level/delay assertions
       move to the guard contract (it raises regardless of args, before any
       network call). Keep one test asserting the guard raises even for the
       previously-"valid" `num=1, mode=0, level=0, delay=0` shape.
    5. Leave the dispatch-gating tests untouched
       (`test_it83_with_api_adapter_*` capability_missing,
       `test_x916_with_fcgi_adapter_default_raises_capability_unknown`) —
       they assert gating, not the request payload.
  - **Acceptance criteria**: `py_compile` passes; the rewritten tests
    **fail** (red) against the still-credential-less adapter; the untouched
    gating tests still pass.

- [ ] T009 Green — convert `_fcgi_relay_trigger` to an actionable guard and
  update the matrix comment.

  - **Goal**: Make T008 pass; guarantee FR-015 by issuing no request.
  - **Files touched**: `src/pylocal_akuvox/capability_adapters.py` and
    `src/pylocal_akuvox/capability_matrix.py`.
  - **Implementation**:
    1. In `capability_adapters.py`, replace the body of
       `_fcgi_relay_trigger(http, args)` with a `raise
       AkuvoxUnsupportedError(...)` whose message directs callers to
       `AkuvoxDevice.open_door_http(...)` with the device's
       Open-Relay-Via-HTTP credentials. Remove the `_request_raw` call and
       its `# noqa: SLF001`, the `relay=` path string, the mode/level/delay
       pre-check, and the now-unused 401/4xx/5xx mapping. Import
       `AkuvoxUnsupportedError`; drop imports that become unused. Update the
       function docstring to describe the guard (FR-014 is moot for a path
       that issues nothing; the `DoorNum` correction lives in the helper).
    2. **Retain** `RelayTriggerArgs`, `RELAY_TRIGGER_ADAPTERS`,
       `RELAY_TRIGGER_PREFERENCE`, `CAPABILITY_TO_VARIANT`, `__all__`, and
       the `(Capability.RELAY_TRIGGER_FCGI, "fcgi")` registry entry as-is
       (spec Out-of-Scope retention note).
    3. In `capability_matrix.py`, keep the `_IT83_83_30_10_4` entry
       (`RELAY_TRIGGER_API = UNSUPPORTED`, `RELAY_TRIGGER_FCGI = SUPPORTED`)
       and update the `# Issue #122: ...` comment (line ~73) to note that
       IT83 relay is reached via `open_door_http` (the FCGI dispatch path is
       now an informational guard).
  - **Acceptance criteria**: T008 passes; `uv run pytest tests/unit/test_dispatch.py -q` green; a repo-wide grep confirms **no**
    code path issues `action=OpenDoor` without `UserName`/`Password`
    (`grep -rn "action=OpenDoor" src/` shows only the credentialed
    `params=` mapping in `relay.py`); ruff/mypy/interrogate/aislop clean;
    100% branch coverage.

**Checkpoint**: FR-015 holds — the only `action=OpenDoor` request in the
codebase is the credentialed `relay.open_door_http`; the dispatch path
raises an actionable guard.

---

## Phase 6 (plan Phase 5): Documentation (FR-009/FR-010) — US3

**Goal**: Docstring security/prerequisite note and user-facing
two-mechanism guidance, plus changelog. Covers SC-006.

- [ ] T010 [US3] Finalize the FR-009 docstrings on `open_door_http` (free
  function and passthrough).

  - **Goal**: Refine the complete docstrings authored in T003/T007 to add
    the clear-text-URL trade-off and the device-side prerequisite (FR-009).
  - **Files touched**: `src/pylocal_akuvox/relay.py` and
    `src/pylocal_akuvox/device.py`.
  - **Content**: Each docstring states (a) the password is sent **clear
    text in the URL** (visible in proxy / device access logs, by vendor
    design) and (b) the device must have **Phone → Relay → Open Relay Via
    HTTP** enabled with a configured username/password (FR-009; US3
    scenario 2). Document params/returns/raises.
  - **Acceptance criteria**: `interrogate` clean; aislop clean; no
    behavioural test change required (docstring-only); existing tests stay
    green.

- [ ] T011 [P] [US3] Add the two-mechanism guidance to `docs/quickstart.rst`
  and `README.md`.

  - **Goal**: Tell integrators when to use `/fcgi/do?action=OpenDoor` vs
    `/api/relay/trig`, with the prerequisite and the security trade-off.
  - **Files touched**: `docs/quickstart.rst`, `README.md`.
  - **Content**: A relay section contrasting `device.trigger_relay(...)`
    (`/api/relay/trig`, door phones, `AuthConfig`) with
    `device.open_door_http(...)` (`/fcgi/do?action=OpenDoor`, IT83-class,
    Open-Relay-Via-HTTP credentials), the clear-text-URL trade-off, and the
    IT83 note that `trigger_relay()` now raises an actionable error pointing
    at `open_door_http()` (mirrors quickstart.md) (FR-010; US3 scenario 1;
    SC-006).
  - **Acceptance criteria**: the canonical warnings-as-errors docs build
    `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`
    (AGENTS.md §Documentation) succeeds; markdownlint/RST hygiene clean;
    aislop clean.

- [ ] T012 [P] [US3] Add changelog entries in `docs/changelog.rst`.

  - **Goal**: Record the new method and the IT83 dispatch behaviour change.
  - **Files touched**: `docs/changelog.rst`.
  - **Content** (under `Unreleased`): an **Added** bullet for
    `open_door_http` / `AkuvoxDevice.open_door_http` (the credentialed
    `/fcgi/do?action=OpenDoor` unlock), referencing #122; a **Changed**
    bullet that `trigger_relay()` on an IT83 now raises an actionable error
    directing callers to `open_door_http()` instead of issuing a broken,
    credential-less request (research Decision 2 consequence). Reference
    #122 without a closing keyword.
  - **Acceptance criteria**: the canonical warnings-as-errors docs build
    `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`
    succeeds; RST hygiene clean; aislop clean.

**Checkpoint**: A reader can pick the correct mechanism and understands the
trade-off (SC-006).

---

## Phase 7 (plan Phase 6): MVP script opt-in (FR-012) — US4

**Goal**: `examples/mvp_test.py --write` optionally fires OpenDoor exactly
once, gated behind an explicit opt-in flag and relay credentials; otherwise
skip-and-report.

- [ ] T013 [US4] Red — author MVP opt-in/skip unit tests in
  `tests/unit/test_mvp_test.py`.

  - **Goal**: Pin that OpenDoor is skipped (reported, not failed) without
    the opt-in, and fired exactly once with it.
  - **Files touched**: `tests/unit/test_mvp_test.py` only.
  - **Assertions**:
    1. `--write` **without** `--open-door` (or without relay credentials) →
       OpenDoor is **skipped and reported**, not counted as a failure (US4
       scenario 1).
    2. `--write --open-door --open-door-user ... --open-door-pass ...` →
       the OpenDoor call is attempted **exactly once** (US4 scenario 2;
       FR-012).
    3. Argparse parses the new flags and the password is also accepted via
       the documented env var; the password is redacted in any printed
       diagnostics (reuse `_REDACTED_VALUE`).
  - **Acceptance criteria**: `py_compile` passes; tests **fail** (red)
    because the flags/step do not exist yet.

- [ ] T014 [US4] Green — add the `--open-door` opt-in, credentials, and the
  gated step in `examples/mvp_test.py`.

  - **Goal**: Make T013 pass with a single opt-in OpenDoor exercise.
  - **Files touched**: `examples/mvp_test.py`.
  - **Implementation**:
    1. Add argparse flags `--open-door` (opt-in), `--open-door-user`, and
       `--open-door-pass` (password also accepted via an env var), with
       `parser.error(...)` validation requiring credentials when
       `--open-door` is set.
    2. Add a `test_open_door(device, *, user, password, redact_stdout)`
       coroutine that calls `device.open_door_http(...)` exactly once and
       prints a redacted summary (no clear-text password).
    3. In `_run_write_tests`, add an OpenDoor `step(...)` that runs only
       when `--open-door` and credentials are present; otherwise
       `skip_step(...)` with a reported reason (never a failure). Keep the
       relay credentials **out** of the standard `AuthConfig` path
       (FR-007).
    4. Note: with the Phase 5 guard, the existing `trigger_relay` smoke step
       now **raises** on an IT83. Adjust that step's handling so the IT83
       guard raise is reported (and points to `--open-door`) rather than
       surfacing as an unexpected hard failure (see Anomalies). `--open-door`
       is the replacement real-hardware unlock path for IT83-class devices.
  - **Acceptance criteria**: T013 passes; `uv run pytest tests/unit/test_mvp_test.py -q` green; ruff/mypy/interrogate/aislop
    clean; `examples/mvp_test.py` stays under its aislop size limit; 100%
    branch coverage on new lines.

**Checkpoint**: The MVP script can opt into a single OpenDoor exercise and
safely skips otherwise.

---

## Phase 8: Polish, full validation & pre-PR sweep

**Purpose**: Whole-suite green, coverage gate, and conventions compliance
before the implementation PR.

- [ ] T015 Run the full quality gate.

  - **Goal**: Confirm every gate is green across the whole change.
  - **Files touched**: none (read-only), modulo auto-formatting fixes.
  - **Steps**: `uv run pytest -q` (100% branch coverage enforced);
    `uv run ruff check`; `uv run mypy src tests`;
    `uv run interrogate -c pyproject.toml`; the project `aislop` gate over
    the affected modules (`relay.py`, `device.py`, `capability_adapters.py`,
    `capability_matrix.py`, `examples/mvp_test.py`, and the touched tests);
    the canonical warnings-as-errors docs build
    `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`.
  - **Acceptance criteria**: all gates green; 100% branch coverage.

- [ ] T016 Pre-PR conventions & REUSE/SPDX sweep.

  - **Goal**: Ensure new/changed files carry SPDX headers, no credential
    leaks, and Conventional-Commit-ready diffs.
  - **Files touched**: none new (verification); fix headers if any new file
    was added.
  - **Steps**: confirm SPDX headers on any new file;
    `grep -rn "action=OpenDoor" src/` shows only the credentialed
    `params=` mapping; `grep -rni "password" docs/ README.md` shows no
    literal secret; run full `pre-commit` after staging the implementation
    files (fix-and-restage on failure, never `--no-verify`).
  - **Acceptance criteria**: `pre-commit` clean; REUSE compliant; no
    credential or `relay=` OpenDoor request remains in `src/`.

---

## Dependencies

- **T001** → everything (baseline first).
- **T002 → T003** (red before green: helper + validation).
- **T003 → T004 → T005** (encoding/redaction builds on the helper; the
  redaction green depends on its red test).
- **T003 → T006 → T007** (the passthrough delegates to the free function).
- **T008 → T009** (dispatch red before the guard conversion). Phase 5 is
  independent of Phases 3-4 at the source level but depends on T003 only for
  the conceptual "single credentialed path"; it touches different files
  (`capability_adapters.py`/`capability_matrix.py` vs `relay.py`/
  `device.py`).
- **T010** depends on T003 and T007 (docstrings on existing symbols).
- **T011, T012** depend on T009/T010 (docs describe the final behaviour);
  they touch different files and are mutually **[P]**.
- **T013 → T014** (MVP red before green). T014 depends on T007 (uses
  `device.open_door_http`) and T009 (the IT83 `trigger_relay` guard note).
- **T015, T016** depend on all prior tasks.

## Parallel-execution opportunities

- **Phase 5** (T008/T009) can be developed in parallel with Phases 3-4
  because it edits `capability_adapters.py`/`capability_matrix.py`/
  `test_dispatch.py` — disjoint from `relay.py`/`device.py`/`test_relay.py`.
  Keep separate commits for reviewability.
- **T011 and T012** are `[P]` — different files (`docs/quickstart.rst` +
  `README.md` vs `docs/changelog.rst`).
- Read-only validation in T015/T016 can run together once the source is
  final, though serial output is easier to read.

## Coverage Map: FR / SC / scenario → Tasks

| Requirement / criterion | Implementing tasks | Verifying tasks |
|---|---|---|
| FR-001 expose OpenDoor helper + passthrough | T003, T007 | T002, T006 |
| FR-002 URL-encode credentials (single encoder) | T003, T005 | T004 |
| FR-003 redact password from logs/exceptions | T005 | T004 |
| FR-004 raw/non-JSON path, no `AkuvoxParseError` | T003 | T002 |
| FR-005 validate `door_num` before any request | T003 | T002 |
| FR-006 not capability-gated | T007 | T006 |
| FR-007 credentials independent of `AuthConfig` | T007, T014 | T006, T013 |
| FR-008 failure raised, success silent | T003 | T002 |
| FR-009 docstring security + prerequisite | T010 | T015 (interrogate) |
| FR-010 docs contrast two mechanisms | T011 | T015 (docs build) |
| FR-011 unit coverage (construction/encode/redact/success/failure) | T002, T004 | T015 |
| FR-012 MVP `--write` opt-in | T014 | T013 |
| FR-013 scope: only `action=OpenDoor` | T003 | T002, T016 |
| FR-014 use `DoorNum`, not `relay=` | T003, T009 | T002, T008 |
| FR-015 no credential-less OpenDoor ships | T009 | T008, T016 |
| SC-001 unlock with no prior probe | T007 | T006 |
| SC-002 special-char credentials preserve query | T005 | T004 |
| SC-003 zero password occurrences in logs | T005 | T004 |
| SC-004 invalid `door_num` → zero requests | T003 | T002 |
| SC-005 failure shapes raise (never silent/parse-error) | T003 | T002 |
| SC-006 docs convey mechanism choice | T011, T012 | T015 |
| US1 scenarios 1-3 | T003, T007 | T002, T006 |
| US2 scenarios 1-3 | T005 | T004 |
| US3 scenarios 1-2 | T010, T011 | T015 |
| US4 scenarios 1-2 | T014 | T013 |

## Anomalies / open questions

- **IT83 `trigger_relay` smoke step (mvp_test) now raises.** After the
  Phase 5 guard lands, the existing `trigger_relay` write-test step routes
  to the FCGI guard on an IT83 and raises `AkuvoxUnsupportedError`. T014
  must report this as an expected, actionable outcome (pointing at
  `--open-door`) rather than a hard failure. This is a real behaviour change
  to a path that never worked credential-less; it is captured in the
  changelog (T012) and is the reason `--open-door` is the IT83 unlock path.
- **Soft, non-blocking (carried from plan/spec).** The OpenDoor success
  **body** shape on real IT83 hardware is unprobed; tasks adopt the
  HTTP-status default and isolate classification (T003) so the rule can be
  tightened against live hardware during implementation without reworking
  request construction or redaction. The failure-shape tests (T002) pin
  whichever rule ships.
- **Guard exception choice.** Research/plan name `AkuvoxUnsupportedError`
  as the guard exception (with `AkuvoxValidationError` as the alternative).
  Tasks use `AkuvoxUnsupportedError`; if implementation prefers the
  alternative, update T008's expected type accordingly — both are
  FR-015-compliant.

All symbol and file references above were validated against the live `main`
source at authoring time. Re-run the live-source validation cheat sheet
before implementation if `main` changes.
