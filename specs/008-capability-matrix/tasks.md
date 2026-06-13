<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Device Capability Probe, Capabilities Matrix, and Capability-Aware API Surfacing

**Input**: Design documents from `/specs/008-capability-matrix/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/*.md, quickstart.md
**Branch**: `008-capability-matrix` (this is the **spec PR** branch).
Implementation phases land on follow-on branches `008-capability-matrix-phase-{1..4}` per `plan.md` §"Phase Rollout Plan".

**Tests are MANDATORY** per constitution §II (TDD). Each phase opens with failing contract tests (red), then minimum implementation (green), then behaviour completion + edge cases, then a verification gate.

**Atomic commits**: every task either ships as one focused commit or is folded with the immediately-preceding implementation commit; the **per-phase task-list-update commit is a SEPARATE atomic commit in the SAME PR** as the implementation commits (see AGENTS.md §"Task List Updates Are Separate Commits"). This is the lesson from PRs #126 / #131 — task-list updates ride in the same PR but are their own commit.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1 / US2 / US3 / US4); setup, foundational, gate, and cleanup tasks have no story label
- Every task names exact file path(s) and the FR/SC/contract it implements or verifies

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, `tests/unit/`, `tests/integration/`, `examples/`, `docs/api/`.

---

## Phase 0: Spec PR (this branch — PR 0; artifacts only, no source code)

**Purpose**: Land the spec/plan/research/data-model/contracts/quickstart artifacts plus this `tasks.md` so the four implementation PRs have a stable reference point. PR 0 has no source-code changes.

- [ ] T001 Capture pre-feature baseline metrics on `main` at the spec PR head: aggregate test count (`uv run pytest tests/ --collect-only -q | tail -1`), branch coverage from `coverage.xml` (`<coverage line-rate>` and `<coverage branch-rate>` attributes from the existing `coverage.xml` artifact at repo root), and per-test-file count for `tests/unit/test_users.py` and `tests/unit/test_models.py` (the #99/#101 and #118/#120 regression baselines for FR-016 / SC-008). Record these numbers in the PR 0 description so Phase 3 (T068) and the per-phase coverage gates (T026, T053, T081) can compare against them.
- [ ] T002 Stage and commit the spec PR contents in a single atomic commit (`Docs(spec): Add 008-capability-matrix specification`): `specs/008-capability-matrix/spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/probe-api.md`, `contracts/matrix-lookup.md`, `contracts/unsupported-error.md`, `contracts/adapter-dispatch.md`, plus this `specs/008-capability-matrix/tasks.md`, plus the `.github/agents/copilot-instructions.md` update (cascade-rolled-in constraints from the planning round). SPDX headers already in place on every artifact.
- [ ] T003 Open PR 0 against `main`, link to issue #123, paste the T001 baseline numbers into the PR body, request review.
- [ ] T004 [Phase 0 task list update] Mark T001–T003 complete in `specs/008-capability-matrix/tasks.md` as a SEPARATE atomic commit in PR 0 (`Docs(tasks): Mark Phase 0 tasks complete`). PR 0 then ships with two commits: T002's artifacts commit and T004's task-list-update commit. Per AGENTS.md §"Task List Updates Are Separate Commits".

**Phase 0 dependency**: T001 → T002 → T003 → T004. All sequential.

**Phase 0 exit criterion**: PR 0 merged to `main`. Phase 1 (PR 1) branches off the merged spec.

---

## Phase 1: PR 1 — Capability model and probe (User Story 1, Priority P1) 🎯 MVP

**Goal**: Introduce `Capability`, `CapabilityStatus`, `DeviceCapabilities`, `FieldAliases`, `SchemaShape`, `Provenance`, `DeviceClassPattern`, and the non-destructive `await device.probe_capabilities()`. No visible behaviour change for existing callers (probe is opt-in).

**Independent Test (mirrors spec US1 §"Independent Test")**: Point the library at a previously-uncharacterised Akuvox device, call `probe_capabilities()`, and confirm (a) the call completes without raising, (b) the returned report enumerates which read operations succeeded and which failed and how, (c) no users / contacts / schedules / relay events were created or fired during the probe, and (d) running the probe a second time produces the same report.

### Setup (skeleton modules so Phase-1 imports do not ImportError before implementations exist)

- [ ] T005 Create `src/pylocal_akuvox/capabilities.py` as a stub: SPDX header pair, single-line module docstring, `__all__ = []`, no other content yet. This unblocks subsequent test imports and matches plan.md §"Project Structure" post-feature layout.
- [ ] T006 [P] Create `src/pylocal_akuvox/capability_probe.py` as a stub: SPDX header pair, single-line module docstring, `__all__ = []`, no other content yet.
- [ ] T007 [P] Create `tests/unit/test_capabilities.py` as a stub: SPDX header pair, single-line module docstring, `pytest` import.
- [ ] T008 [P] Create `tests/unit/test_capability_probe.py` as a stub: SPDX header pair, single-line module docstring, `pytest` and `aioresponses` imports.
- [ ] T008a [P] [US1] In `tests/unit/test_http.py`, add contract tests for **two new pieces** on `AkuvoxHttpClient`:
  - (i) optional per-call `timeout: float | None = None` kwarg on `.get`, `.post`, and `_request`
  - (ii) a new low-level helper `async def _request_raw(self, method: str, path: str, *, params=None, data=None, timeout=None) -> tuple[int, str]` that returns `(http_status, raw_body_text)` **without raising on non-2xx HTTP status and without parsing the JSON envelope**. The helper is the only way to bypass `_handle_response`'s translation (`_http.py:177-204` translates HTTP 4xx/5xx and negative-retcode envelopes into typed exceptions BEFORE returning); the capability probe needs raw access so `_classify_response(status, body) -> _ProbeOutcome` can see HTTP 500 bodies, `"No handlers for this request"`, `"unsupported action"`, and 401/403 status codes as the wire delivered them. `_request_raw` MUST still raise `AkuvoxConnectionError` on transport-level failures (connection refused, DNS failure, asyncio timeout) — it only bypasses HTTP-status and envelope translation, not transport translation.

  Referenced by `contracts/probe-api.md` §"Public surface" + new §"Raw HTTP helper". Tests assert the **plumbing**, not the error-wrapping semantics (`_http.py:153-155` wraps `TimeoutError` in `AkuvoxConnectionError`, so the user-facing behaviour on actual timeout is `AkuvoxConnectionError`). Note the current public signatures per `src/pylocal_akuvox/_http.py:105-121` are `get(path, params=None)` and `post(path, data=None)`; T008a adds the optional `timeout=None` kwarg while preserving the `data=` parameter name (the `data=` dict is serialised to JSON internally — the parameter name is `data`, not `json`):

  **Timeout-plumbing tests (existing public API):**
  - **(a) default**: calling `get(path)` without `timeout=` passes no per-call timeout to `session.request` (the session-level timeout configured in `__init__` applies); use `unittest.mock.patch.object(client._session, "request")` (or an equivalent aiohttp-level patch) and assert `request` was called WITHOUT a `timeout=` kwarg.
  - **(b) get override**: calling `get(path, timeout=2.0)` passes `timeout=aiohttp.ClientTimeout(total=2.0)` (or whatever shape the implementation uses in `_request`, observable on the mocked call kwargs). The contract is "the value reaches the aiohttp layer with `total=2.0`".
  - **(c) post symmetry**: calling `post(path, data={}, timeout=1.5)` results in the mocked `session.request` being called with both (i) `json={}` (the public `data=` dict is converted to aiohttp's `json=` kwarg internally — confirm this conversion is preserved alongside the new timeout plumbing) AND (ii) `timeout=aiohttp.ClientTimeout(total=1.5)`.
  - **(d) end-to-end error path (optional but recommended)**: with a real `aioresponses` configured to delay longer than the override, `await client.get(path, timeout=0.05)` raises `AkuvoxConnectionError` whose `__cause__` is a `TimeoutError` (or `asyncio.TimeoutError` — the union the `except` clause at `_http.py:153` catches). This locks the documented user-facing behaviour without coupling to the wrapper class identity.

  **Raw-helper tests (new `_request_raw`):**
  - **(e) HTTP 500 returns tuple, does NOT raise**: mock `/some/path` to return HTTP 500 + body `'{"retcode": -1, "message": "boom"}'`. Assert `await client._request_raw("GET", "/some/path")` returns the tuple `(500, '{"retcode": -1, "message": "boom"}')` without raising `AkuvoxDeviceError`. Compare against the existing `await client.get("/some/path")` call against the same mock: it MUST raise `AkuvoxDeviceError` (proving the contrast — `get` translates, `_request_raw` does not).
  - **(f) negative-retcode body returns tuple, does NOT raise**: mock to return HTTP 200 + body `'{"retcode": -1, "message": "unsupported action"}'`. Assert `_request_raw` returns `(200, '{"retcode": -1, "message": "unsupported action"}')`. The existing `get()` raises `AkuvoxUnsupportedError` against the same mock.
  - **(g) HTTP 401 returns tuple, does NOT raise**: mock HTTP 401. Assert `_request_raw` returns `(401, '<body>')`. The probe will read this tuple, detect status==401, and raise `AkuvoxAuthenticationError` itself per `contracts/probe-api.md` §"Probe step sequence" step 1 short-circuit. (This is the only auth-classification step; the helper itself stays uniform.)
  - **(h) transport error still raises `AkuvoxConnectionError`**: mock to raise `aiohttp.ClientConnectionError` (or use a closed connector). Assert `_request_raw` raises `AkuvoxConnectionError` whose `__cause__` is the transport error. Proves the helper bypasses only HTTP/envelope translation, not transport translation.
  - **(i) timeout plumbing on raw helper**: `_request_raw("GET", path, timeout=2.0)` results in the underlying `session.request` being called with `timeout=aiohttp.ClientTimeout(total=2.0)` — same contract as (b) but on the raw helper.

  These tests MUST fail before the implementation in T021 (which calls `http._request_raw("GET", path, timeout=timeout)` for each probe endpoint via the module-level helper, NOT `http.get(...)`). Implementation lands as part of T021 or as its own small commit; either way it is part of Phase 1 PR 1.

### TDD: Contract tests (red)

Tests in this section MUST fail before any implementation work in T017–T024.

- [ ] T009 [P] [US1] In `tests/unit/test_capabilities.py`, write contract tests for the `Capability` enum (FR-001, data-model.md §"`Capability` enum members"): every member listed in the data-model table is present (`USER_LIST` … `KEY_DISCOVERY`); every value is a lowercase `domain.action[.variant]` string; the enum is iteration-stable; adding a new member is a non-breaking addition (verified by checking that the existing public re-exports do not enumerate members).
- [ ] T010 [P] [US1] In `tests/unit/test_capabilities.py`, write contract tests for `CapabilityStatus` (FR-002, research.md §"Decision 2"): three members `SUPPORTED`/`UNSUPPORTED`/`UNKNOWN` with string values `"supported"`/`"unsupported"`/`"unknown"`; values are stable across iteration order.
- [ ] T011 [P] [US1] In `tests/unit/test_capabilities.py`, write contract tests for `FieldAliases`, `SchemaShape`, `Provenance` (data-model.md entities #3, #4, #5): all are `frozen=True, kw_only=True` dataclasses (or enums where applicable); `FieldAliases.read` and `.write` are `tuple[str, ...]`; `Provenance` carries `test_bench_device_id`, `firmware_version`, `library_version`, `observed_at` fields.
- [ ] T012 [US1] In `tests/unit/test_capabilities.py`, write contract tests for `DeviceCapabilities` (FR-002, data-model.md §"`DeviceCapabilities` shape"):
  - `status_of(missing_capability)` returns `CapabilityStatus.UNKNOWN` (default-mapping behaviour, research.md Decision 2).
  - `require(capability)` does not raise when the status is `SUPPORTED`.
  - `require(capability)` raises `AkuvoxUnsupportedError` with a message containing the capability value AND device class when status is `UNSUPPORTED`.
  - `require(capability)` raises `AkuvoxUnsupportedError` (message contains `"unknown status"`) when status is `UNKNOWN` and `allow_unknown=False` (default).
  - `require(capability, allow_unknown=True)` does NOT raise when status is `UNKNOWN`; still raises for `UNSUPPORTED`.
  - `supported_set` returns a `frozenset[Capability]` containing exactly the keys whose value is `SUPPORTED`.
  - **Note**: do not assert on `.reason` field yet — that field arrives in Phase 2 (T041). Phase 1 require() raises message-only `AkuvoxUnsupportedError(message)`; the message text is the discriminator.
- [ ] T013 [P] [US1] In `tests/unit/test_capabilities.py`, write contract tests for `DeviceClassPattern` per `contracts/matrix-lookup.md` §"`DeviceClassPattern` matching semantics":
  - Construction parses glob (`"916.30.10.*"`), floor (`"2915.30.10.114+"`), and exact (`"83.30.10.4"`) firmware-band forms.
  - Malformed bands (e.g. `"916.30.*.10"` — wildcard not in trailing position) raise `ValueError` at construction.
  - `matches(device_info)` truth table for each form against synthetic `DeviceInfo` fixtures, including the X915S floor case where `2915.30.10.113` does NOT match the `"2915.30.10.114+"` pattern (covers spec edge case "Provenance staleness" + research.md Decision 6).
  - Wholly non-numeric firmware string returns `False` (does not raise).
- [ ] T014 [US1] In `tests/unit/test_capability_probe.py`, write the contract test for `probe-api.md` §"Probe step sequence" (FR-003, SC-001, FR-004 auth-failure rules). The owning test function MUST be named `test_probe_is_non_destructive` (so quickstart step 1 `pytest test_capability_probe.py -k non_destructive` selects it). Four sub-cases:
  - **(a) full success path**: mock all nine probe URLs against a synthetic X916 with HTTP 200 + valid envelopes; call `await device.probe_capabilities()`; assert (i) the request log contains exactly the nine GET URLs in declared order, (ii) no URL in the request log matches `/(add|set|del|trig)/` or `/fcgi/do?action=OpenDoor`. SC-001 non-destructive-probe verification.
  - **(b) step-1 auth-fail aborts after 1 call**: mock `/api/system/info` to return HTTP 401; call `await device.probe_capabilities()`; assert it raises `AkuvoxAuthenticationError` AND the request log contains exactly **1** entry (`/api/system/info`) — the probe does NOT continue to steps 2–9. Locks the FR-004 step-1 abort rule.
  - **(c) later-step 401/403 records UNKNOWN and continues**: mock `/api/system/info` HTTP 200 (success), `/api/user/get?page=1` (step 3) HTTP 401, all other probe URLs HTTP 200; call `await device.probe_capabilities()`; assert (i) NO exception is raised, (ii) the request log contains exactly **9** entries (all 9 steps were issued), (iii) `profile.status_of(Capability.USER_LIST) is CapabilityStatus.UNKNOWN`, (iv) `profile.notes["user_get_body"]` contains `"401"`. Locks the "later-step 401/403 → UNKNOWN + continue" rule from probe-api.md §"Probe step sequence" Call-count invariant.
  - **(d) step-1 malformed body raises `AkuvoxParseError` after 1 call** — three asserted sub-cases inside one test (each must raise `AkuvoxParseError` with the request log containing exactly **1** entry and NO `DeviceCapabilities` returned, locking the FR-004 / probe-api.md §"Step-1 failure modes" parse-failure abort rule and preserving SC-002 byte-equal idempotence):
    - **(d1) invalid JSON**: mock `/api/system/info` to return HTTP 200 + non-JSON garbage `'<html>nope</html>'`; assert `AkuvoxParseError` whose `__cause__` is a `json.JSONDecodeError`.
    - **(d2) envelope missing/malformed**: mock to return HTTP 200 + valid JSON that is not the expected envelope shape, e.g. `'[]'` (not a dict) or `'{"foo": "bar"}'` (no `retcode` key) or `'{"retcode": "zero"}'` (`retcode` not int); assert `AkuvoxParseError` whose message references the missing/invalid envelope fields. Mirrors `_http.py:_parse_envelope` rejection semantics so probe accepts exactly what regular API calls accept.
    - **(d3) `DeviceInfo` construction fails**: mock to return HTTP 200 + a valid envelope (`'{"retcode": 0, "data": {}}'`) whose `data` payload is missing required `DeviceInfo` fields (e.g. no `Model` / firmware fields). Assert `AkuvoxParseError` whose message references DeviceInfo construction; its `__cause__` is the `AkuvoxParseError` raised by `DeviceInfo.from_api_response` (which may itself chain a `KeyError` for missing fields).
- [ ] T015 [US1] In `tests/unit/test_capability_probe.py`, write contract tests for `probe-api.md` §"Response classification" (FR-004, SC-003): one parametrised test per row of the response-classification table, asserting:
  - HTTP 2xx + `retcode: 0` → status `SUPPORTED`.
  - HTTP 2xx + body containing `"No handlers for this request"` → status `UNSUPPORTED`.
  - HTTP 2xx + body containing the typo `"No hanlders for this request"` → status `UNSUPPORTED` (case-insensitive on `body.message`; spec edge case "typo"). <!-- codespell:ignore hanlders -->
  - HTTP 2xx + body containing `"unsupported action"` on `/api/contact/get` → `CONTACT_LIST = SUPPORTED`; raw body recorded under `DeviceCapabilities.notes["contact_get_body"]`; **`CONTACT_ADD`, `CONTACT_MODIFY`, and `CONTACT_DELETE` MUST all be ABSENT from `profile.capabilities`** (probe MUST NOT add write counterparts to the mapping per FR-003 and probe-api.md §"Probe step sequence" Write-capabilities paragraph — the canonical representation is "absent → `status_of()` returns UNKNOWN by default"). Add explicit dual-assertions per write capability: `assert Capability.CONTACT_ADD not in profile.capabilities AND profile.status_of(Capability.CONTACT_ADD) is CapabilityStatus.UNKNOWN`; same for `CONTACT_MODIFY` and `CONTACT_DELETE`. Repeat the same dual-assertion pattern for one user-domain case: against `"unsupported action"` on `/api/user/get`, assert `USER_ADD`/`USER_MODIFY`/`USER_DELETE` are all absent AND each `status_of()` returns `UNKNOWN`.
  - HTTP 500 → status `UNKNOWN`, raw body recorded under `notes["<endpoint_slug>_body"]` (spec edge case "HTTP 500"; X915S `2915.30.10.113`).
  - HTTP 401 on step 1 → probe raises `AkuvoxAuthenticationError`, NO partial `DeviceCapabilities` returned.
  - HTTP 4xx (non-401/403) on later step → status `UNKNOWN`, probe continues.
- [ ] T015a [P] [US1] In `tests/unit/test_capability_probe.py`, write contract tests for **probe-side recording of `field_aliases` and `schema_shapes`** per `contracts/probe-api.md` §"Probe step sequence" rows 3 and 4 (FR-002 — observed field-name aliases and observed schema shapes are part of `DeviceCapabilities`). Two test cases:
  - **Field-aliases recording**: given a synthetic `/api/user/get` response whose user item carries the key `"Schedule-Relay"` (E18C-style) — and only that key, not `"ScheduleRelay"` or `"Schedule"` — assert the returned `DeviceCapabilities.field_aliases["schedule_relay"].read` reflects `("Schedule-Relay",)` (or at least lists `"Schedule-Relay"` in observed-key order). Variant: with a response carrying only `"Schedule"` (X915S-style), assert `read` reflects `("Schedule",)`.
  - **Schema-shape recording**: given a synthetic `/api/contact/get` response whose contact item carries apartment-book keys (`APTName`, `APTNum`, `Building`, `Landline`) and no `ID` field, assert `DeviceCapabilities.schema_shapes["contact"]` is `SchemaShape.APARTMENT_BOOK`. Variant: a door-phone-shape response (`Name`, `Phone`, `ID`) yields `SchemaShape.DOOR_PHONE`.
  Covers FR-002 (the `field_aliases` and `schema_shapes` halves, beyond T011's type-shape check) for the probe-derived path. Closes the implementation-side gap that probe-api.md §"Probe step sequence" rows 3–4 declare but no other test exercises.
- [ ] T016 [US1] In `tests/unit/test_capability_probe.py`, write contract tests for FR-005 / SC-002 (probe idempotence) AND for the "no write inference" rule from probe-api.md §"Public surface" / Out-of-scope. The idempotence test MUST be named `test_probe_is_idempotent` (so quickstart step 2 `pytest test_capability_probe.py -k idempotent` selects it):
  - **Idempotence**: two consecutive probes against the same mocked device produce `DeviceCapabilities` instances comparing **exactly** equal (`assert a == b` — no per-field normalisation; per probe-api.md §"Idempotence" the probe writes `provenance=None` and no wall-clock timestamp into `notes`, so byte-equal is the contract).
  - **No write inference**: against a fully-responsive X916 (every read returns `retcode: 0`), the returned profile has every `*_ADD`/`*_MODIFY`/`*_DELETE`/`RELAY_TRIGGER_*`/`DEVICE_CONFIG_SET` capability **absent** from `capabilities` (i.e. `status_of(...)` returns `UNKNOWN`). Also: transport refusal during step 4 raises `AkuvoxConnectionError`; no partial profile is returned (probe-api.md edge case 5).

### Implementation (green)

- [ ] T017 [P] [US1] Implement `Capability`, `CapabilityStatus`, `FieldAliases`, `SchemaShape`, `Provenance` in `src/pylocal_akuvox/capabilities.py` per data-model.md (FR-001, FR-002 partial). Includes the `DeviceCapabilities.__post_init__` body per `data-model.md` §"`DeviceCapabilities`" docstring: wrap each of `capabilities`, `field_aliases`, `schema_shapes`, `notes` in `types.MappingProxyType(dict(getattr(self, name)))` via `object.__setattr__` (defensive copy + read-only view). Makes T009 / T010 / T011 / T028a green.
- [ ] T018 [US1] Implement `DeviceCapabilities` (`status_of`, `require`, `supported_set`) in `src/pylocal_akuvox/capabilities.py` per data-model.md §"`DeviceCapabilities` shape" and research.md Decision 2 (FR-002 complete). The dataclass is `frozen=True, kw_only=True` with the `__post_init__` `MappingProxyType` wrapping per T017; no public builder method (e.g. composition / merge helper) is exposed — the frozen invariant plus stdlib `dataclasses.replace()` covers any composition case for a future consumer, and the 9-cell probe-vs-matrix merge is implemented inside `capability_probe.probe_capabilities()` (T051) without a public merge helper. `require()` raises **message-only** `AkuvoxUnsupportedError` in Phase 1; the message text contains the device class, the capability value, and the discriminator wording per `contracts/unsupported-error.md` §"Raise-site contract". Phase 2 T048 updates the call to pass structured kwargs once T041 evolves the exception class. Makes T012 green.
- [ ] T019 [US1] Implement `DeviceClassPattern.__post_init__` (band-form parsing + `ValueError` on bad input) and `DeviceClassPattern.matches(device_info)` in `src/pylocal_akuvox/capabilities.py` per `contracts/matrix-lookup.md` §"`DeviceClassPattern` matching semantics" and research.md Decision 6. Makes T013 green. (`lookup_capabilities()` helper deferred to Phase 2 T043 since it depends on `CAPABILITY_MATRIX`.)
- [ ] T020 [US1] Implement `_classify_response(status, body) -> _ProbeOutcome` in `src/pylocal_akuvox/capability_probe.py` per `contracts/probe-api.md` §"Response classification". Makes T015 green.
- [ ] T021 [US1] Implement `probe_capabilities(http, *, timeout: float = 5.0) -> DeviceCapabilities` (module-level helper, NOT a method — `capability_probe.py` is a module with free functions, no class, no `self`) in `src/pylocal_akuvox/capability_probe.py` per `contracts/probe-api.md` §"Probe step sequence" + research.md Decision 1. The deterministic 9-step probe is sequential, per-call timeout-bounded by the `timeout=` kwarg (default `5.0`s), with the **call-count invariant** per probe-api.md §"Probe step sequence":
  - **Step 1 — explicit sequence** (per probe-api.md §"Step-1 failure modes"):
    1. `status, body = await http._request_raw("GET", "/api/system/info", timeout=timeout)` (the only call issued before the auth/HTTP/parse gates resolve). `body` is raw response text.
    2. **Auth gate**: if `status in (401, 403)`: raise `AkuvoxAuthenticationError("Authentication required for /api/system/info")`. The probe aborts after exactly 1 call. No `DeviceCapabilities` is returned.
    3. **HTTP-error gate**: if `status >= 400` (any 4xx other than 401/403, or any 5xx): raise `AkuvoxConnectionError(f"step-1 returned HTTP {status}")` (chain `__cause__=None`; body may be included for diagnostics). The probe aborts after 1 call.
    4. **Parse gate** — three sub-stages, each mapping to `AkuvoxParseError` with `__cause__` chained, mirroring `_http.py:_parse_envelope` semantics so the probe accepts exactly what regular API calls accept (envelope field name is **lowercase `"data"`** per `_http.py:173`):
       ```python
       try:
           payload = json.loads(body)
       except json.JSONDecodeError as exc:
           raise AkuvoxParseError("step-1 body is not valid JSON") from exc
       if not isinstance(payload, dict) or "retcode" not in payload or not isinstance(payload["retcode"], int):
           raise AkuvoxParseError(f"step-1 envelope missing fields: {payload!r}")
       data = payload.get("data", {})
       if not isinstance(data, dict):
           data = {}
       try:
           device_info = DeviceInfo.from_api_response(data)
       except (KeyError, TypeError, ValueError) as exc:
           raise AkuvoxParseError("step-1 DeviceInfo construction failed") from exc
       ```
       Note: `DeviceInfo.from_api_response(data: dict[str, Any]) -> DeviceInfo` is the actual classmethod (per `src/pylocal_akuvox/models/device.py:26`); there is no `DeviceInfo.parse(...)`.
    5. **Continue**: only now proceed to steps 2–9.
  - Steps 2–9 each call `await http._request_raw("GET", path, timeout=timeout)`. The classifier `_classify_response(status, body)` (T020) handles every response shape including HTTP 401/403 — it maps later-step 401/403 to `INDETERMINATE` (capability `UNKNOWN`) with `notes["<endpoint_slug>_body"] = f"{status}: {body}"` and the probe CONTINUES to the next step. The probe always completes 9 calls when step 1 succeeds.

  **Probe uses `http._request_raw(...)` for every step — NOT `http.get(...)`** — because `_http.get/post`'s `_handle_response` (`_http.py:177-204`) translates HTTP 4xx/5xx and negative-retcode envelopes into typed exceptions BEFORE returning, which would hide the very signals `_classify_response(status, body) -> _ProbeOutcome` needs (HTTP 500 bodies, `"No handlers for this request"`, `"unsupported action"`, 401/403 status codes). `_request_raw` returns `(http_status, raw_body_text)` without raising on non-2xx/non-zero-retcode; it still raises `AkuvoxConnectionError` on transport failures. Underscore-prefix is acceptable since the probe lives in the same package (sibling module).

  Records `provenance=None` (probe-derived) — **NO wall-clock timestamp is written into `notes`** (per probe-api.md §"Provenance produced by the probe" + §"Idempotence": the absent `provenance` is the sole "this is a probe-derived profile" marker; writing a `"derived from probe at <ISO-8601 timestamp>"` note would break SC-002 byte-equal idempotence). Step 2 (`/api/system/status`) records `notes["system_status"] = "<short summary or raw body>"` only; it does NOT classify any capability. Step 9 (`/api/relay/status`) is the sole `RELAY_STATUS` classifier. **Also records observed field-aliases and schema-shapes per probe-api.md steps 3–4**: populates `DeviceCapabilities.field_aliases["schedule_relay"]` from observed user-list keys (any of `"ScheduleRelay"` / `"Schedule-Relay"` / `"Schedule"` present in the response item, in the order observed) and populates `DeviceCapabilities.schema_shapes["contact"]` from observed contact-list keys (apartment-book keys `APTName`/`APTNum`/`Building`/`Landline` → `SchemaShape.APARTMENT_BOOK`; otherwise `SchemaShape.DOOR_PHONE`). **Per-request timeout plumbing**: extends `AkuvoxHttpClient.get`/`.post`/`._request` AND the new `_request_raw` with an optional `timeout: float | None = None` kwarg (default None falls back to session-level timeout, fully backward compatible). Makes T008a, T014, and T015a green.
- [ ] T022 [US1] Add `async def probe_capabilities(self, *, timeout: float | None = None) -> DeviceCapabilities` method and read-only `capabilities` property on `AkuvoxDevice` in `src/pylocal_akuvox/device.py` per `contracts/probe-api.md` §"Public surface". The wrapper resolves `timeout = timeout if timeout is not None else 5.0` and delegates: `result = await capability_probe.probe_capabilities(self._http, timeout=timeout); self._capabilities = result; return result`. **No matrix lookup yet** — that arrives in Phase 2 T046. Add a small unit test in `tests/unit/test_device.py` that asserts (a) calling `await device.probe_capabilities()` (no kwarg) calls the module helper with `timeout=5.0`, (b) calling `await device.probe_capabilities(timeout=2.5)` calls the module helper with `timeout=2.5` (mock the helper and inspect call kwargs).
- [ ] T023 [US1] Update `src/pylocal_akuvox/__init__.py` to re-export `Capability`, `CapabilityStatus`, `DeviceCapabilities`, `FieldAliases`, `SchemaShape` (data-model.md §"Public re-exports"). `Provenance` and `DeviceClassPattern` remain implementation-internal (not re-exported per data-model line 300–305).

### Behaviour completion + edge cases

- [ ] T024 [US1] Implement the **strict no-write-inference rule** in `capability_probe.py` per FR-003 and probe-api.md §"Probe step sequence" Write-capabilities paragraph: probe **does NOT add any write capability to `DeviceCapabilities.capabilities`** (every `*_ADD`/`*_MODIFY`/`*_DELETE` capability — `USER_ADD`, `USER_MODIFY`, `USER_DELETE`, `CONTACT_ADD`, `CONTACT_MODIFY`, `CONTACT_DELETE`, `SCHEDULE_ADD`, `SCHEDULE_MODIFY`, `SCHEDULE_DELETE`, `GROUP_ADD`, `GROUP_MODIFY`, `GROUP_DELETE` — plus `DEVICE_CONFIG_SET` and `RELAY_TRIGGER_*`) is **absent** from the mapping, **regardless of any read-endpoint signal**. The canonical observation is `status_of(write_capability) == CapabilityStatus.UNKNOWN` via the "absent → UNKNOWN" default contract on `DeviceCapabilities.status_of` (see `data-model.md` §"`DeviceCapabilities`"). A read endpoint returning `"unsupported action"` records the read capability per the classification table and records the body under `notes["<endpoint_slug>_body"]` (e.g. `notes["contact_get_body"]`), but MUST NOT add any write capability in the same domain (contact/user/schedule/group) to `capabilities`. `RELAY_TRIGGER_FCGI` likewise stays absent (`status_of(...) == UNKNOWN`) unless a curated matrix entry promotes it. Add explicit unit assertions: against a mocked device returning `unsupported action` on `/api/contact/get`, post-probe assert BOTH (a) `Capability.CONTACT_ADD not in profile.capabilities` AND `Capability.CONTACT_MODIFY not in profile.capabilities` AND `Capability.CONTACT_DELETE not in profile.capabilities`, AND (b) `profile.status_of(Capability.CONTACT_ADD) is CapabilityStatus.UNKNOWN` (and the same for MODIFY/DELETE). Repeat for the user domain (`/api/user/get` + `USER_ADD`/`USER_MODIFY`/`USER_DELETE`). Makes T016 green and closes the BLOCKER-3 inference gap.
- [ ] T025 [US1] Add probe transport-error and parse-error propagation per `contracts/probe-api.md` §"Edge cases" #4 and #5: 401/403 on step 1 raises `AkuvoxAuthenticationError`; transport refusal anywhere raises `AkuvoxConnectionError`; `system/info` parse failure raises `AkuvoxParseError`. No partial `DeviceCapabilities` returned in any case. Final coverage for T015's auth row + T016's transport row.

### Phase 1 verification gate

- [ ] T026 [Gate] Run `uv run ruff check src/ tests/`, `uv run mypy src/ tests/`, `uv run interrogate src/ tests/`. All clean. (Constitution §I.)
- [ ] T027 [Gate] Run `uv run pytest tests/ -x -q`. All green. Capture new aggregate test count and branch coverage; assert non-regression vs T001 baseline (new tests added, coverage ≥ baseline).
- [ ] T028 [Phase 1 Checkpoint] Walk `quickstart.md` steps 1, 2, 3 manually and confirm each command produces the expected output. This independently verifies SC-001 (probe non-destructive), SC-002 (probe idempotent), SC-003 (failure-shape classification). Confirm spec US1 acceptance scenarios 1–5 are each covered by at least one test in T008a, T009–T016 plus T015a. Cross-check via grep that `probe-api.md` is named in the test file's docstring or comments.
- [ ] T028a [P] [US1] In `tests/unit/test_capabilities.py`, add `test_device_capabilities_is_deeply_immutable` per `data-model.md` §"`DeviceCapabilities`" class docstring + `__post_init__` contract: construct a `DeviceCapabilities` from plain `dict` inputs for each of `capabilities`, `field_aliases`, `schema_shapes`, `notes`. After construction, assert each of the four mapping attributes is a `types.MappingProxyType` instance (`assert isinstance(dc.notes, MappingProxyType)`). Then assert that mutation attempts raise `TypeError`: `with pytest.raises(TypeError): dc.notes["evil"] = "x"`; same for `dc.capabilities[Capability.USER_ADD] = CapabilityStatus.SUPPORTED`, `dc.field_aliases["x"] = ...`, `dc.schema_shapes["x"] = ...`. Also assert the **defensive-copy** invariant: pass a plain `dict d = {"a": "b"}` as `notes=`, mutate `d["c"] = "d"` after construction, and assert `dc.notes == MappingProxyType({"a": "b"})` (i.e. the post-construction mutation of the input did NOT leak into the wrapped view). This locks the immutability invariant that all gating logic depends on. Implementation lands in T017 (the `__post_init__` body) — this test makes that part green.

### Phase 1 task-list update (separate atomic commit in PR 1)

- [ ] T029 [Phase 1 task list update] Mark T005–T028 (including T008a, T015a, and T028a) complete in `specs/008-capability-matrix/tasks.md` as a SEPARATE atomic commit in PR 1 (`Docs(tasks): Mark Phase 1 tasks complete`). This commit is the LAST commit in PR 1 — same PR as the implementation commits, separate atomic commit per AGENTS.md §"Task List Updates Are Separate Commits". DO NOT open this as its own follow-up PR (PRs #126 / #131 retrospective).

**Phase 1 dependencies**: T005–T008 (setup, all parallel) → T008a + T009–T016 plus T015a + T028a (red tests, mostly parallel; T028a parallel with T009–T016 — different test function in same file as T009–T012) → T017–T023 (impl, T017 delivers the `__post_init__` body that makes T028a green; T018 blocks on T017; T019 parallel with T018; T020 blocks on T017; T021 blocks on T020 and now also delivers T008a + T015a; T022 blocks on T021; T023 blocks on T017–T022) → T024–T025 (edge cases, parallel) → T026–T028 (gates, sequential) → T029 (commit).

**Phase 1 PR exit**: PR 1 merged with quickstart steps 1–3 green and existing test suite non-regressed. Phase 2 branches off PR 1's merged tip.

---

## Phase 2: PR 2 — Matrix, dispatch, `AkuvoxUnsupportedError` evolution, `attempt_unknown_capability` opt-in (User Story 2, Priority P1)

**Goal**: Connect populates each device's effective profile from the curated `CAPABILITY_MATRIX`; every public method consults the profile and fails fast for `UNSUPPORTED` (default) and `UNKNOWN` (default; bypassed by `device.attempt_unknown_capability=True`); relay-trigger dispatches via adapter registry; `AkuvoxUnsupportedError` evolves additively to carry structured `capability` / `device_class` / `reason`.

**Independent Test (mirrors spec US2 §"Independent Test")**: Configure the library against each of the four supported device classes (X916, X915S current FW, E18C current FW, IT83) without explicitly probing first; for each, confirm (a) calling a supported operation succeeds, (b) calling an unsupported operation raises `AkuvoxUnsupportedError` with the missing capability and device class populated, (c) the unsupported call did not produce a network request, (d) the relay-trigger operation routes to the correct underlying mechanism per device class, and (e) for any capability whose status is `unknown`, the call fails-fast by default but proceeds when `attempt_unknown_capability` is set.

### Setup

- [ ] T030 Create `src/pylocal_akuvox/capability_matrix.py` as a stub (SPDX, docstring, `CAPABILITY_MATRIX: tuple[...] = ()`).
- [ ] T031 [P] Create `src/pylocal_akuvox/capability_adapters.py` as a stub (SPDX, docstring, `__all__ = []`).
- [ ] T032 [P] Create `tests/unit/test_matrix.py`, `tests/unit/test_pattern.py`, `tests/unit/test_dispatch.py`, `tests/unit/test_unsupported_error.py` as stubs (SPDX + docstring + pytest import each).

### TDD: Contract tests (red)

- [ ] T033 [P] [US2] In `tests/unit/test_unsupported_error.py`, write the five tests required by `contracts/unsupported-error.md` §"Test coverage required":
  - `test_default_constructor_message_only` — `AkuvoxUnsupportedError("x")` yields `.args == ("x",)`, `str(exc) == "x"`, `exc.capability is exc.device_class is exc.reason is None`.
  - `test_structured_constructor_capability_missing` — every kwarg round-trips.
  - `test_structured_constructor_capability_unknown` — three-valued status reason round-trips identically.
  - `test_reason_taxonomy_closed` — production raises (collected by grepping `src/`) only use values in `{capability_missing, capability_unknown, device_unrecognized, adapter_missing, envelope_unsupported, None}`.
  - `test_isinstance_akuvox_error` — class hierarchy preserved.
  Covers FR-010.
- [ ] T034 [P] [US2] In `tests/unit/test_pattern.py`, write contract tests for `DeviceClassPattern.matches()` per `contracts/matrix-lookup.md` §"`DeviceClassPattern` matching semantics" — extended truth-table tests beyond Phase 1's T013, including the worked patterns from `data-model.md` §"`CAPABILITY_MATRIX` initial entries" (X916 glob, X915S floor, E18C glob, IT83 exact). (T013 may be the same test if scoped that way; T034 is the dedicated extension covering all four production patterns.)
- [ ] T035 [P] [US2] In `tests/unit/test_matrix.py`, write contract tests per `contracts/matrix-lookup.md`:
  - `test_every_entry_has_provenance` — every entry in `CAPABILITY_MATRIX` has non-`None` `provenance` whose `test_bench_device_id`, `firmware_version`, `library_version`, `observed_at` are populated; covers all four supported device classes (X916, X915S, E18C, IT83). (FR-006, FR-007, SC-004.)
  - `test_no_overlapping_patterns` — no two patterns in `CAPABILITY_MATRIX` match the same synthetic `DeviceInfo`.
  - `test_lookup_returns_first_match` — `lookup_capabilities()` walks `CAPABILITY_MATRIX` in declaration order and returns the first match; returns `None` for an unrecognised device.
  - One test per supported device class confirming the capability-delta row from `data-model.md` §"Capability deltas across the four entries" (notably IT83's `RELAY_TRIGGER_API=UNSUPPORTED` / `RELAY_TRIGGER_FCGI=SUPPORTED` / `RELAY_STATUS=UNSUPPORTED`; X915S's `CONTACT_ADD=UNSUPPORTED` / `CONTACT_SCHEMA_APARTMENT=SUPPORTED`).
- [ ] T036 [US2] In `tests/unit/test_device.py`, write a parametrised contract test (one row per supported device class) for connect-time matrix population per `contracts/matrix-lookup.md` §"Connect-time integration" (FR-008). The owning test function MUST be named `test_connect_populates_capabilities` (parametrised on device class — so quickstart step 4 `pytest test_device.py -k connect_populates_capabilities` selects it). Mock `/api/system/info` to return X916 / X915S current / E18C current / IT83 model+firmware; after `await device.__aenter__()`, assert `device.capabilities` equals the corresponding `CAPABILITY_MATRIX` entry's `DeviceCapabilities` (provenance non-`None`); assert the `aioresponses` request log contains exactly one GET to `/api/system/info` and ZERO requests to any list endpoint. Covers FR-008 (matrix entry adoption without probing) and one half of US2 acceptance scenario 1.
- [ ] T037 [US2] In `tests/unit/test_device.py`, write contract test for unrecognised-device fallback per `contracts/matrix-lookup.md` §"Connect-time integration" (FR-013): mock `/api/system/info` to return a model the matrix does not cover; after `__aenter__`, `device.capabilities` is the conservative-empty profile (`capabilities={}`, `notes["device_not_in_matrix"]` mentions `probe_capabilities()` and `attempt_unknown_capability`); calling any service operation raises `AkuvoxUnsupportedError(reason="capability_unknown"` OR `"device_unrecognized"` — both accepted per closed-set test) with zero HTTP requests issued; the message directs the integrator to `probe_capabilities()` and to `attempt_unknown_capability=True`.
- [ ] T038 [US2] In `tests/unit/test_device.py`, write contract tests for the per-method capability gate (FR-011, SC-005) covering each of the assertions called out in `contracts/unsupported-error.md` §"Raise-site contract". The owning test (or one of the owning tests in the parametrised group) MUST be named `test_unsupported_raises_before_request` (so quickstart step 5 `pytest test_device.py -k unsupported_raises_before_request` selects it). Cases:
  - **X915S `add_contact`** → `AkuvoxUnsupportedError(reason="capability_missing", capability=Capability.CONTACT_ADD, device_class="X915S")`, ZERO HTTP requests in log.
  - **IT83 `trigger_relay(adapter=Capability.RELAY_TRIGGER_API)`** → `AkuvoxUnsupportedError(reason="capability_missing", capability=RELAY_TRIGGER_API, device_class="IT83")`, ZERO HTTP requests.
  - **IT83 `add_user`** → `AkuvoxUnsupportedError(reason="capability_unknown", capability=USER_ADD, device_class="IT83")`, ZERO HTTP requests (matrix records IT83 writes as UNKNOWN, data-model.md table).
  - **FR-011 audit (introspection lock)**: in the same test file, add `test_every_public_device_method_has_capability_gate` that uses `inspect.getmembers(AkuvoxDevice, predicate=inspect.iscoroutinefunction)` to enumerate every public coroutine method, filters out the **infrastructure-method out-of-scope set** `{"get_info", "get_status", "probe_capabilities"}` (per spec FR-011 and `data-model.md` §"Explicit out-of-scope" — `get_info`/`get_status` precede matrix lookup; `probe_capabilities` creates the profile and cannot gate itself), AND the **adapter-gated set** `{"trigger_relay"}` (per `data-model.md` §"Adapter-gated exception" — its gate lives in the `RELAY_TRIGGER_ADAPTERS` registry lookup, not in a literal `require(...)` call; per `contracts/adapter-dispatch.md` §"Dispatch order"). For each remaining method asserts that `inspect.getsource(method)` contains the literal substring `self._capabilities.require(`. The two exception sets are defined inline at the top of the test as `_INFRA_OUT_OF_SCOPE = {"get_info", "get_status", "probe_capabilities"}` and `_ADAPTER_GATED = {"trigger_relay"}` with comments referencing the respective spec/contract sections so the rationale is visible at the test-failure site. This locks the audit in CI so new methods cannot land without a gate; any new infrastructure method or adapter-gated method must be explicitly added to the appropriate set with a comment, forcing a deliberate spec/contract update.
  Covers SC-005 explicitly (the three named cases) plus FR-011 (audit).
- [ ] T039 [US2] In `tests/unit/test_device.py`, write contract tests for FR-021 / SC-011 (`attempt_unknown_capability` integrator opt-in):
  - `device.attempt_unknown_capability` defaults to `False`.
  - With default: calling an `UNKNOWN`-status operation (e.g. IT83 `add_user`) raises `AkuvoxUnsupportedError(reason="capability_unknown")` and issues ZERO HTTP requests.
  - After `device.attempt_unknown_capability = True`: calling the same `UNKNOWN`-status operation dispatches to the underlying API; mock the API to return a typical device-side error envelope and assert the library surfaces it verbatim (does NOT translate it into a capability error).
  - With `attempt_unknown_capability = True` AND a confirmed-`UNSUPPORTED` capability (X915S `add_contact`): still raises `AkuvoxUnsupportedError(reason="capability_missing")`, ZERO HTTP requests — the override does NOT bypass `UNSUPPORTED` (FR-021 last sentence).
  Covers FR-021 in full and SC-011 (request-log assertion both states).
- [ ] T040 [US2] In `tests/unit/test_dispatch.py`, write contract tests per `contracts/adapter-dispatch.md` §"Per-device-class behaviour" (FR-012, SC-006):
  - X916 / X915S current / E18C current `trigger_relay(num=1)` → POST `/api/relay/trig` with the documented body shape.
  - IT83 `trigger_relay(num=1)` → GET `/fcgi/do?action=OpenDoor&relay=1`.
  - IT83 `trigger_relay(num=1, adapter=Capability.RELAY_TRIGGER_API)` → `AkuvoxUnsupportedError(reason="capability_missing")`, ZERO HTTP requests.
  - X916 `trigger_relay(num=1, adapter=Capability.RELAY_TRIGGER_FCGI)` (FCGI=UNKNOWN on X916) → with `attempt_unknown_capability=False`, `AkuvoxUnsupportedError(reason="capability_unknown")` ZERO HTTP requests; with `attempt_unknown_capability=True`, dispatches to the FCGI URL.
  - FCGI adapter passing non-zero `mode`/`level`/`delay` raises `AkuvoxValidationError` at adapter boundary, ZERO HTTP requests.
  - Unrecognised-device profile + `trigger_relay()` → `AkuvoxUnsupportedError(reason="capability_unknown")`, ZERO HTTP requests.
  - `adapter_missing` reason: simulate a registry with the entry deleted and confirm the gate raises `reason="adapter_missing"` (spec edge case "Adapter dispatch with no matching adapter").
- [ ] T041 [US2] In `tests/unit/test_capability_probe.py`, add the probe-vs-matrix merge contract test (FR-009, `contracts/probe-api.md` edge case 7 "9-cell merge table"). Drive every cell of the 3×3 merge table with concrete fixtures from the matrix and from `contracts/probe-api.md` §"Classification table". Test matrix:
  - **Row dimension** = matrix status of the capability under test, sourced from `data-model.md` §"Capability deltas":
    - Matrix-SUPPORTED row: pin to **X916 `USER_LIST`** (data-model.md row `USER_LIST | S | S | S | ?`).
    - Matrix-UNSUPPORTED row: pin to **IT83 `RELAY_STATUS`** (data-model.md row `RELAY_STATUS | S | S | S | U`). RELAY_STATUS is a READ capability (`GET /api/relay/status`), so probe-UNSUPPORTED classification is allowed (BLOCKER 3 / FR-003 only forbids inferring write-capability UNSUPPORTED from read signals).
    - Matrix-UNKNOWN row: pin to **IT83 `USER_LIST`** (data-model.md row `USER_LIST | S | S | S | ?` — IT83 column is `?` = UNKNOWN).
  - **Column dimension** = probe classification of the same endpoint, sourced from `contracts/probe-api.md` §"Classification table":
    - Probe-SUPPORTED column: mock the endpoint to return `retcode:0` + a typed-keyed payload.
    - Probe-UNSUPPORTED column: mock the endpoint to return `"No handlers for this request"` (or the typo variant `"No hanlders for this request"` — both classify identically per spec edge case). For RELAY_STATUS specifically this is the IT83-observed signal per `data-model.md:235`. <!-- codespell:ignore hanlders -->
    - Probe-UNKNOWN column: mock the endpoint to raise HTTP 500 (transient server error per `contracts/probe-api.md` §"Classification table" row "HTTP 5xx").
  - **Nine assertions** (one per cell — every cell uses a real device-class + real-or-real-shape response fixture; no synthetic CONTACT_LIST=UNSUPPORTED abstractions):

    | Cell | Fixture (matrix, probe response) | Expected merged status |
    |------|----------------------------------|-----------------------|
    | (matrix S, probe S) | X916 USER_LIST + 200 keyed `/api/user/get` | SUPPORTED |
    | (matrix S, probe UNSUPPORTED) | X916 USER_LIST + `"No handlers"` body on `/api/user/get` | UNSUPPORTED (probe wins, newer evidence) |
    | (matrix S, probe UNKNOWN) | X916 USER_LIST + HTTP 500 on `/api/user/get` | SUPPORTED (matrix preserved) |
    | (matrix UNSUPPORTED, probe S) | IT83 RELAY_STATUS + 200 keyed `/api/relay/status` | SUPPORTED (probe wins, newer evidence) |
    | (matrix UNSUPPORTED, probe UNSUPPORTED) | IT83 RELAY_STATUS + `"No handlers"` body on `/api/relay/status` | UNSUPPORTED (both agree) |
    | (matrix UNSUPPORTED, probe UNKNOWN) | IT83 RELAY_STATUS + HTTP 500 on `/api/relay/status` | UNSUPPORTED (matrix preserved) |
    | (matrix UNKNOWN, probe S) | IT83 USER_LIST + 200 keyed `/api/user/get` | SUPPORTED |
    | (matrix UNKNOWN, probe UNSUPPORTED) | IT83 USER_LIST + `"No handlers"` body on `/api/user/get` | UNSUPPORTED |
    | (matrix UNKNOWN, probe UNKNOWN) | IT83 USER_LIST + HTTP 500 on `/api/user/get` | UNKNOWN |

  - **Plus one write-capability non-regression assertion** (cross-checks FR-003 strict no-write-inference / BLOCKER 3 from round 2): take X916 with matrix `USER_ADD = SUPPORTED`; mock the user-list READ endpoint to return `"No handlers"` body (probe classifies `USER_LIST` as UNSUPPORTED per row 2 above); assert post-probe `USER_ADD is SUPPORTED` — the read-endpoint UNSUPPORTED signal MUST NOT propagate to the corresponding write capability.
- [ ] T042 [US2] In `tests/unit/test_http.py`, confirm the existing test at `test_unsupported_api_raises_unsupported_error` (line ~223) is unmodified and stays green after T044's exception evolution; add a new positive assertion that the legacy single-arg construction still works (`AkuvoxUnsupportedError("x")` produces the same instance type with `.reason is None`). Covers `contracts/unsupported-error.md` §"Backward-compatibility guarantees".

### Implementation (green)

- [ ] T043 [US2] Implement `lookup_capabilities(device_info)` helper in `src/pylocal_akuvox/capabilities.py` per `contracts/matrix-lookup.md` §"Public surface". Iterates `CAPABILITY_MATRIX` (imported lazily to avoid import cycle) and returns the first matching profile or `None`.
- [ ] T044 [US2] Evolve `AkuvoxUnsupportedError` in `src/pylocal_akuvox/exceptions.py` per `contracts/unsupported-error.md` §"Post-Phase-2 form" — additive: keyword-only `capability=None`, `device_class=None`, `reason=None`. Existing single-arg construction (`_http.py:201`) continues to work; existing tests (`tests/unit/test_http.py::test_unsupported_api_raises_unsupported_error` at line ~223, `tests/unit/test_exceptions.py:57`) MUST stay green without modification. Class object identity preserved (no module move). Makes T033 and T042 green; covers FR-010.
- [ ] T045 [P] [US2] Populate `CAPABILITY_MATRIX` in `src/pylocal_akuvox/capability_matrix.py` with the four entries per `data-model.md` §"`CAPABILITY_MATRIX` initial entries" — most-specific-first ordering: IT83 exact, X915S floor, E18C glob, X916 glob. Each entry's `DeviceCapabilities.capabilities` mapping populated per `data-model.md` §"Capability deltas" (legend: S/U/?). Each entry's `provenance` populated per `contracts/matrix-lookup.md` §"Initial entries"  table (test_bench_device_id, firmware_version, library_version via `importlib.metadata.version("pylocal-akuvox")`, observed_at = 2026-06-13). IT83's `RELAY_TRIGGER_FCGI=SUPPORTED` and `RELAY_TRIGGER_API=UNSUPPORTED`; X915S's `CONTACT_ADD=UNSUPPORTED` and `CONTACT_SCHEMA_APARTMENT=SUPPORTED`. Covers FR-006, FR-007, SC-004. Makes T035 green.
- [ ] T046 [P] [US2] Implement `RelayTriggerArgs`, `_api_relay_trigger`, `_fcgi_relay_trigger`, `RELAY_TRIGGER_ADAPTERS`, `_RELAY_TRIGGER_PREFERENCE`, `_CAPABILITY_TO_VARIANT` in `src/pylocal_akuvox/capability_adapters.py` per `contracts/adapter-dispatch.md` §"The shape". The FCGI adapter validates `mode`/`level`/`delay` are zero and raises `AkuvoxValidationError` otherwise (adapter-dispatch.md §"_fcgi_relay_trigger" docstring).
- [ ] T047 [US2] Modify `AkuvoxDevice.__aenter__` in `src/pylocal_akuvox/device.py` per `contracts/matrix-lookup.md` §"Connect-time integration": after `_http.__aenter__()` and `await self.get_info()`, call `lookup_capabilities(info)`. If non-`None`, set `self._capabilities = profile`. If `None`, build conservative-empty profile (capabilities={}, schema_shapes={}, field_aliases={}, `notes={"device_not_in_matrix": "..."}` mentioning `probe_capabilities()` and `attempt_unknown_capability`). Covers FR-008, FR-013. Makes T036, T037 green.
- [ ] T048 [US2] Add `attempt_unknown_capability: bool = False` settable attribute on `AkuvoxDevice` in `src/pylocal_akuvox/device.py` (FR-021). Update `DeviceCapabilities.require()` callers (initially zero — T049 introduces them) and the `require()` raise-sites in `capabilities.py` to also pass `capability=`, `device_class=`, `reason=` kwargs to `AkuvoxUnsupportedError` now that T044 has evolved the class. The `require()` body now matches `contracts/unsupported-error.md` §"Raise-site contract" verbatim for the `device.py` rows.
- [ ] T049 [US2] Add per-method capability gate **at the `AkuvoxDevice` wrapper layer only** in `src/pylocal_akuvox/device.py`. Every public service-call method on `AkuvoxDevice` gains a single line **before delegating to the underlying service function**: `self._capabilities.require(Capability.<MAPPED>, allow_unknown=self.attempt_unknown_capability)`. The full mapping (per `data-model.md` §"`Capability` enum members" — keep this list synchronised when methods are added):
  - `add_user` → `USER_ADD`; `list_users` → `USER_LIST`; `modify_user` → `USER_MODIFY`; `delete_user` → `USER_DELETE`
  - `add_contact` → `CONTACT_ADD`; `list_contacts` → `CONTACT_LIST`; `modify_contact` → `CONTACT_MODIFY`; `delete_contact` → `CONTACT_DELETE`
  - `add_schedule` → `SCHEDULE_ADD`; `list_schedules` → `SCHEDULE_LIST`; `modify_schedule` → `SCHEDULE_MODIFY`; `delete_schedule` → `SCHEDULE_DELETE`
  - `add_group` → `GROUP_ADD`; `list_groups` → `GROUP_LIST`; `modify_group` → `GROUP_MODIFY`; `delete_group` → `GROUP_DELETE`
  - `get_device_config` → `DEVICE_CONFIG_GET`; `set_device_config` → `DEVICE_CONFIG_SET`
  - `get_door_logs` → `LOG_DOOR`; `get_call_logs` → `LOG_CALL`
  - `get_relay_status` → `RELAY_STATUS`
  - `trigger_relay` → handled by T050 (adapter-dispatched; uses `RELAY_TRIGGER_API` / `RELAY_TRIGGER_FCGI`)
  - **Explicit out-of-scope** (NOT gated per `data-model.md` §"Explicit out-of-scope"): `AkuvoxDevice.get_info()`, `AkuvoxDevice.get_status()`, and `AkuvoxDevice.probe_capabilities()`. The first two run BEFORE matrix lookup (the probe and connect-time lookup both depend on them) and are unconditionally available on every device. `probe_capabilities()` is the method that CREATES the capability profile and so cannot gate itself (chicken-and-egg). Leave all three unchanged.
  - **Adapter-gated exception**: `AkuvoxDevice.trigger_relay()` is gated structurally via `RELAY_TRIGGER_ADAPTERS` (T050), not via a literal `self._capabilities.require(...)` call. The introspection audit (T038) treats it as a documented exception.
  - **Service-module functions** in `users.py`/`contacts.py`/`schedules.py`/`groups.py`/`logs.py`/`config.py`/`relay.py` remain capability-unaware — they are module-level free functions taking `http: AkuvoxHttpClient` and CANNOT access `self._capabilities`; centralising the gate on the `AkuvoxDevice` wrapper is the only correct plumbing path. (Note: `auth.py` is dataclass-only — `AuthMethod`/`AuthConfig` — and has no callable service functions to gate.)
  - Audit cross-check: T049's PR adds a test in `tests/unit/test_capability_gate.py` (folded into T038) that **mirrors T038's introspection audit byte-for-byte**: it imports the same module-level sets `_INFRA_OUT_OF_SCOPE = {"get_info", "get_status", "probe_capabilities"}` and `_ADAPTER_GATED = {"trigger_relay"}` from `tests/unit/test_capability_gate.py` (or re-defines them with identical contents), introspects `AkuvoxDevice` via `inspect.getmembers(predicate=inspect.iscoroutinefunction)`, filters to non-underscore methods, and for every remaining coroutine method:
    - if the name is in `_INFRA_OUT_OF_SCOPE`: skip (chicken-and-egg / universal endpoints, per `spec.md` FR-011 + `data-model.md` §"Explicit out-of-scope");
    - if the name is in `_ADAPTER_GATED`: assert the source contains `RELAY_TRIGGER_ADAPTERS` (or `_relay_adapter.dispatch(` if you prefer the registry-dispatch entrypoint name) instead of `self._capabilities.require(` — structural acceptance per `contracts/adapter-dispatch.md` §"Dispatch order";
    - otherwise: assert the source contains `self._capabilities.require(` (text-grep on `inspect.getsource(method)`).
    This locks FR-011 at the test level: new methods cannot land without a gate, and the two filter sets are the canonical source of truth (T038 and T049 must reference the same sets — keep in sync or import from one place).
  Covers FR-011, FR-021. Makes T038, T039 green.
- [ ] T050 [US2] Refactor `src/pylocal_akuvox/relay.py::trigger_relay` (and the `AkuvoxDevice.trigger_relay` shim) to dispatch through `RELAY_TRIGGER_ADAPTERS` per `contracts/adapter-dispatch.md` §"Dispatch order" — preference-ordered SUPPORTED scan (API before FCGI), `adapter=` caller override hook, `adapter_missing` reason for missing-registry-entry case. Covers FR-012, SC-006. Makes T040 green.
- [ ] T051 [US2] Implement the probe-vs-matrix merge in `capability_probe.probe_capabilities()` (and/or `device.probe_capabilities`) per `contracts/probe-api.md` edge case 7: probe explicit-classification wins; matrix-derived value preserved for capabilities the probe did not exercise. Covers FR-009. Makes T041 green.
- [ ] T052 [US2] Confirm `src/pylocal_akuvox/__init__.py` re-exports per `contracts/unsupported-error.md` §"What `__init__.py` exports" — `AkuvoxUnsupportedError` already re-exported (no change required); structured fields accessed off the existing re-export. Smoke-import test added if not already present.

### Phase 2 verification gate

- [ ] T053 [Gate] Run `uv run ruff check src/ tests/`, `uv run mypy src/ tests/`, `uv run interrogate src/ tests/`. All clean.
- [ ] T054 [Gate] Run `uv run pytest tests/ -x -q`. All green. Coverage non-regression vs T001 baseline AND vs T027 (Phase 1 closing) numbers.
- [ ] T055 [Phase 2 Checkpoint] Walk `quickstart.md` steps 4, 5, 6, 7 manually and confirm each command produces the expected output. This independently verifies SC-004 (matrix provenance), SC-005 (per-method gate request-log), SC-006 (adapter dispatch), SC-011 (`attempt_unknown_capability` request-log assertion). Confirm spec US2 acceptance scenarios 1–7 are each covered by at least one test in T033–T042.

### Phase 2 task-list update (separate atomic commit in PR 2)

- [ ] T056 [Phase 2 task list update] Mark T030–T055 complete in `specs/008-capability-matrix/tasks.md` as a SEPARATE atomic commit in PR 2 (`Docs(tasks): Mark Phase 2 tasks complete`). This commit is the LAST commit in PR 2 — same PR as the implementation commits, separate atomic commit per AGENTS.md §"Task List Updates Are Separate Commits". DO NOT open this as its own follow-up PR (PRs #126 / #131 retrospective).

**Phase 2 dependencies**: T030–T032 (setup, parallel) → T033–T042 (red tests, mostly parallel except those touching same file) → T043 (lookup helper, blocks T047) → T044 (exception evolution, blocks T048 / T049 / T050) → T045 (matrix data, blocks T036/T040 turning green; can land in parallel with T046 since different files) → T046 (adapters, blocks T050) → T047 (connect-time integration, blocks T038/T040) → T048 (override attribute) → T049 (per-method gate, depends on T044+T048) → T050 (relay refactor, depends on T046+T044) → T051 (merge rule) → T052 (re-exports) → T053–T055 (gates) → T056 (commit).

**Phase 2 PR exit**: PR 2 merged with quickstart steps 1–7 green.

---

## Phase 3: PR 3 — Refactor field-name aliasing and schema-shape onto the matrix (User Story 3, Priority P2)

**Goal**: Move the hardcoded `ScheduleRelay`/`Schedule-Relay`/`Schedule` aliasing from `models/users.py` and `users.py` onto capability-record-driven field-name lists. Move contact schema-shape selection (door-phone vs apartment-book) onto a capability flag. Externally observable behaviour for X916, X915S current FW, E18C current FW is byte-identical to today.

**Independent Test (mirrors spec US3 §"Independent Test")**: Run the full existing test suite — including the X916, E18C, X915S compat tests landed by issues #99 and #118 — against the refactored code with no test changes other than where tests were verifying the exact location of the conditional. All payload-shape and parse-shape assertions continue to pass.

### Setup (no new modules; modifies existing files)

- [ ] T057 Snapshot the currently-passing test list and assertion shapes in `tests/unit/test_users.py` and `tests/unit/test_models.py` for the #99/#101 (E18C dual-write) and #118/#120 (X915S `Schedule` read) regression coverage. Record file:line:test-name list in PR 3 description so Phase 3 reviewers can confirm "no logic changes" (FR-016, SC-008).

### TDD: Contract tests (red)

- [ ] T058 [P] [US3] In `tests/unit/test_users.py`, add NEW tests asserting `User.from_api_response(data, capabilities=...)` consults `capabilities.field_aliases["schedule_relay"].read` in order; with a synthetic capability record having `read=("CustomFieldName",)` the parser picks up `"CustomFieldName"` and ignores `"ScheduleRelay"`/`"Schedule-Relay"`/`"Schedule"` keys (no hardcoded fallback wins). Covers FR-014, FR-017, SC-007 (alias half).
- [ ] T059 [US3] In `tests/unit/test_users.py`, add NEW tests **at the service-function layer** (capability-unaware) asserting that `users.add_user(http, ..., field_aliases=FieldAliases(write=("Custom","Custom-Alt")))` and `users.modify_user(http, ..., field_aliases=...)` emit each name in `field_aliases.write` with the same value — matching T064's signature contract (service functions take a `field_aliases=` kwarg directly; they do NOT consult any `self._capabilities` because they have no `self`). With no `field_aliases=` kwarg (or `field_aliases=None`), the emitted payload bytes are byte-identical to today's hardcoded `("ScheduleRelay","Schedule-Relay")` dual-write — preserves #99/#101 regressions (FR-016). Then add **wrapper-layer tests** in the same file (or in `tests/unit/test_device.py` if you prefer to keep service-function tests strictly separate) asserting that `AkuvoxDevice.add_user(...)` / `AkuvoxDevice.modify_user(...)` extract `self._capabilities.field_aliases.get("schedule_relay", DEFAULT_USER_FIELD_ALIASES)` and pass it as `field_aliases=` to the service function — mock the service function and assert it was called with the wrapper-derived `FieldAliases` instance. This split mirrors T064's "service functions stay capability-unaware; gating lives on the `AkuvoxDevice` wrapper" contract and avoids T059 contradicting T064 on where capability extraction lives.
- [ ] T060 [P] [US3] In `tests/unit/test_contacts.py`, add NEW tests asserting `Contact.from_api_response(data, capabilities=...)` selects `DOOR_PHONE` vs `APARTMENT_BOOK` via `capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)`:
  - APARTMENT_BOOK path parses without an `ID` field, accepts `APTName`/`APTNum`/`Building`/`Landline`.
  - DOOR_PHONE path is byte-identical to today's parser (raises `AkuvoxParseError` on missing `Name`).
  - `Contact.from_api_response(data)` with NO `capabilities` kwarg behaves identically to today (door-phone default fallback). Covers FR-015, FR-016.
- [ ] T061 [US3] In `tests/unit/test_matrix.py`, add a NEW test `test_add_hypothetical_entry` (referenced by quickstart step 9) that programmatically constructs a synthetic `(DeviceClassPattern, DeviceCapabilities)` with custom `field_aliases` and `schema_shapes`, exercises `User.from_api_response` and `Contact.from_api_response` with that capability record, and asserts the parsers consult the synthetic record without any monkey-patch of `models/users.py` or `models/contacts.py`. Covers FR-017, SC-007.

### Implementation (green)

- [ ] T062 [US3] Define module-level `DEFAULT_USER_FIELD_ALIASES = FieldAliases(read=("ScheduleRelay","Schedule-Relay","Schedule"), write=("ScheduleRelay","Schedule-Relay"))` in `src/pylocal_akuvox/capabilities.py` (research.md Decision 3 §"Read side"). This is the no-kwarg fallback for legacy callers and matches today's hardcoded behaviour byte-for-byte.
- [ ] T063 [US3] Refactor `User.from_api_response` in `src/pylocal_akuvox/models/users.py`: add optional `capabilities: DeviceCapabilities | None = None` kwarg; replace the hardcoded `ScheduleRelay`/`Schedule-Relay`/`Schedule` chain at lines ~35–44 with a loop over `(capabilities.field_aliases.get("schedule_relay") or DEFAULT_USER_FIELD_ALIASES).read`. Preserve class identity (`__qualname__`, `dataclass.fields()`, `id(class)`). Covers FR-014, FR-016. Makes T058, T061 (user-side) green.
- [ ] T064 [US3] Refactor `users.add_user` and `users.modify_user` in `src/pylocal_akuvox/users.py` to accept a new optional keyword-only parameter `field_aliases: FieldAliases | None = None` and emit each name in `field_aliases.write` (defaulting to `DEFAULT_USER_FIELD_ALIASES` when the kwarg is `None` or omitted) with the same value. Service-module functions remain capability-unaware — `users.add_user` does NOT touch `self._capabilities` (it has no `self`); the `AkuvoxDevice.add_user` wrapper extracts `self._capabilities.field_aliases.get("schedule_relay", DEFAULT_USER_FIELD_ALIASES)` and passes it as the kwarg. The default-`None` signature preserves FR-016: existing direct callers of `users.add_user(http, ...)` without the kwarg get byte-identical payloads to today (the X916 matrix entry's `write=("ScheduleRelay","Schedule-Relay")` is the same as `DEFAULT_USER_FIELD_ALIASES.write`). Covers FR-014, FR-016. Makes T059 green.
- [ ] T064a [US3] **Read-path alias plumbing for the public `list_users()` path** (closes the gap that T063 only refactored the parser and T064 only the write paths; today's `users.list_users` at `src/pylocal_akuvox/users.py:106-120` calls `User.from_api_response(item)` with no capability context, so synthetic matrix aliases reach the parser ONLY through direct unit tests, not through `AkuvoxDevice.list_users()`). Implementation:
  - Extend `users.list_users(http, *, page=None, capabilities: DeviceCapabilities | None = None)` (new kwarg, default `None` preserves FR-016 byte-identical behaviour) and thread it to each `User.from_api_response(item, capabilities=capabilities)` call at line 120.
  - Update `AkuvoxDevice.list_users()` in `src/pylocal_akuvox/device.py` to call `users.list_users(self._http, page=page, capabilities=self._capabilities)`.
  - Add **two tests** in `tests/unit/test_users.py` (sibling to T058) that exercise the FULL read path AND prove the plumbing is actually wired (not just a parser unit test):
    1. **Non-default alias test** (proves `capabilities` is threaded end-to-end): instantiate an `AkuvoxDevice` whose `self._capabilities` carries a synthetic `field_aliases["schedule_relay"] = FieldAliases(read=("CustomScheduleField",), write=())` — `"CustomScheduleField"` is NOT in the default parser's hardcoded chain (`"ScheduleRelay"`, `"Schedule-Relay"`, `"Schedule"`). Mock `/api/user/get` to return items keyed `"CustomScheduleField"` only (no `"ScheduleRelay"`/`"Schedule-Relay"`/`"Schedule"`). Call `await device.list_users()`; assert each returned `User` has the schedule-relay field correctly parsed from `"CustomScheduleField"`. **This test MUST fail if `AkuvoxDevice.list_users()` does not pass `capabilities=self._capabilities` through to `users.list_users()` → `User.from_api_response()`** — because the default parser would raise `AkuvoxParseError("Missing required field 'ScheduleRelay'...")` on a response keyed only with `"CustomScheduleField"`.
    2. **Conflict-resolution test** (proves alias order is honoured, not just first-match-from-default-list): instantiate `AkuvoxDevice` whose `capabilities` carries `field_aliases["schedule_relay"] = FieldAliases(read=("Schedule", "ScheduleRelay"), write=())` (order intentionally reversed from the default chain). Mock `/api/user/get` to return items that carry BOTH `"ScheduleRelay": "wrong_value"` AND `"Schedule": "right_value"` keys. Assert each returned `User.schedule_relay` equals `"right_value"` — proving the parser consults `capabilities.field_aliases["schedule_relay"].read` in its declared order rather than falling back to the hardcoded `("ScheduleRelay","Schedule-Relay","Schedule")` chain. **This test would also fail with the default parser** because the default chain checks `"ScheduleRelay"` first and would return `"wrong_value"`.
  Covers FR-014, FR-017 (end-to-end through public surface), and the read-side of FR-016 (default-`None` preserves existing byte-identical behaviour for direct `users.list_users(http)` callers).
- [ ] T065 [US3] Refactor `Contact.from_api_response` in `src/pylocal_akuvox/models/contacts.py`: add optional `capabilities: DeviceCapabilities | None = None` kwarg; consult `capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)` to dispatch between two parse paths (door-phone — today's parser, byte-identical; apartment-book — additive, accepts `APTName`/`APTNum`/`Building`/`Landline` without `ID`). Preserve class identity. Covers FR-015, FR-016. Makes T060 green.
- [ ] T066 [US3] **Mutation-payload baseline + apartment-book write deferral** (this task does NOT add apartment-book write support; the current public `add_contact(name, phone, group)` / `modify_contact(id, name, phone, group)` signature has no source for the required apartment-book fields `APTName`/`APTNum`/`Building`/`Landline`, and the only door-phone-shape write evidence on an APARTMENT_BOOK device is X915S CONTACT_ADD = UNSUPPORTED per issue #121 — X915S CONTACT_MODIFY/DELETE default to UNKNOWN; IT83 CONTACT_ADD/MODIFY/DELETE default to UNKNOWN; see `data-model.md` matrix capability table). Implementation:
  - In `src/pylocal_akuvox/contacts.py`, the write-side service functions `add_contact` and `modify_contact` each accept a new optional keyword-only parameter `schema_shape: SchemaShape | None = None`. Default `None` falls back to `SchemaShape.DOOR_PHONE` and emits today's byte-identical payload. **If `schema_shape == SchemaShape.APARTMENT_BOOK`**, raise `NotImplementedError("apartment-book contact writes are not yet supported; see <follow-up issue> — current public API has no source for APTName/APTNum/Building/Landline and no hardware-bench write evidence exists")`. This passthrough lands the kwarg without committing to an apartment-book payload shape we cannot validate. **`delete_contact` does NOT take a `schema_shape=` kwarg** — delete-by-id is shape-agnostic on Akuvox firmware (the device receives only the contact ID), and the existing payload builder is reused unchanged.
  - The `AkuvoxDevice.add_contact`, `AkuvoxDevice.modify_contact`, and `AkuvoxDevice.delete_contact` wrappers each call `self._capabilities.require(<CAPABILITY>, allow_unknown=self.attempt_unknown_capability)` first, where `<CAPABILITY>` is `CONTACT_ADD` / `CONTACT_MODIFY` / `CONTACT_DELETE` respectively. **For `add_contact` and `modify_contact` only**, the wrapper additionally extracts `self._capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)` and passes it as `schema_shape=` to the service function. **For `delete_contact`**, the wrapper performs the gate check ONLY — no shape switch, no `schema_shape=` kwarg — then delegates to the existing shape-agnostic delete-by-id payload. The full dispatch matrix is:
    - **Door-phone devices (X916, E18C) — `add_contact` / `modify_contact`**: matrix marks `SUPPORTED`; gate passes; wrapper extracts `schema_shapes.get("contact", DOOR_PHONE) == DOOR_PHONE`; passes `schema_shape=SchemaShape.DOOR_PHONE`; service function uses today's payload builder, byte-identical.
    - **Door-phone devices — `delete_contact`**: matrix marks `SUPPORTED`; gate passes; wrapper delegates without `schema_shape=`; service function deletes by ID, byte-identical to today.
    - **X915S `add_contact`**: matrix marks `CONTACT_ADD = UNSUPPORTED` (issue #121 door-phone write evidence); wrapper-level `require()` raises `AkuvoxUnsupportedError(reason="capability_missing", capability=Capability.CONTACT_ADD, device_class="X915S")` immediately, regardless of `attempt_unknown_capability`. The payload-shape switch is never reached. (`UNSUPPORTED` always blocks per FR-021 last sentence.)
    - **X915S `modify_contact`**: matrix marks UNKNOWN; with default `attempt_unknown_capability=False`, wrapper raises `AkuvoxUnsupportedError(reason="capability_unknown")`. With `attempt_unknown_capability=True`, gate passes; wrapper extracts `schema_shapes["contact"] == APARTMENT_BOOK`; passes `schema_shape=SchemaShape.APARTMENT_BOOK`; service function raises `NotImplementedError` per the deferral.
    - **X915S `delete_contact`**: matrix marks UNKNOWN; with default `attempt_unknown_capability=False`, wrapper raises `AkuvoxUnsupportedError(reason="capability_unknown")`. With `attempt_unknown_capability=True`, gate passes; wrapper delegates without `schema_shape=`; service function deletes by ID. **No `NotImplementedError`** — `delete_contact` has no apartment-book variant; it is shape-agnostic. The X915S firmware behaviour for delete-by-id is itself unverified (UNKNOWN by definition), so the `attempt_unknown_capability=True` opt-in carries the documented "no positive evidence; you accepted the risk" semantics from FR-021.
    - **IT83 `add_contact` / `modify_contact`**: matrix marks UNKNOWN; same UNKNOWN path as X915S `modify_contact` above. With `attempt_unknown_capability=True` AND `schema_shapes["contact"] == APARTMENT_BOOK` (only true if a future matrix entry sets it; conservative-empty defaults to DOOR_PHONE), service function raises `NotImplementedError`.
    - **IT83 `delete_contact`**: matrix marks UNKNOWN; same as X915S `delete_contact` — gate-only, no shape switch.
    - **Unrecognised devices** (conservative-empty profile) — `schema_shapes` is empty; default falls through to `SchemaShape.DOOR_PHONE` for ADD/MODIFY (gate behaviour per FR-013); DELETE is gate-only as above.
  - **`delete_contact` is gate-only, never raises `NotImplementedError`**: there is no apartment-book DELETE payload variant — delete-by-id is the only shape Akuvox firmware accepts on either schema. The wrapper checks `CONTACT_DELETE` via `require()` and, on pass, delegates to today's existing service function unchanged.
  - `list_contacts` is owned by T066a (read-path uses `capabilities=` kwarg, not `schema_shape=`).
  - Service-module functions in `contacts.py` remain capability-unaware (no `self`).
  - **Tests** in `tests/unit/test_contacts.py` (folded into existing test classes):
    1. **Door-phone baseline pin**: `add_contact(http, name="x", phone="555")` and `add_contact(http, name="x", phone="555", schema_shape=SchemaShape.DOOR_PHONE)` produce byte-identical request bodies (preserves FR-016).
    2. **Apartment-book NotImplementedError pin**: `add_contact(http, name="x", schema_shape=SchemaShape.APARTMENT_BOOK)` raises `NotImplementedError` with the deferral message. Same for `modify_contact`.
    3. **Wrapper dispatch pin**: `AkuvoxDevice.add_contact` (when wired to a device whose matrix entry has `schema_shapes["contact"] = DOOR_PHONE`) passes `schema_shape=SchemaShape.DOOR_PHONE` through to the service function — assert via mock.
  Covers FR-015 / FR-016 for the door-phone branch; explicitly defers apartment-book write payloads to a follow-up issue (`spec.md` US3 acceptance and `plan.md` Phase 3 scope are both updated to call this out). See also: BLOCKER 3 of round 5 rubber-duck.
- [ ] T066a [US3] **Read-path schema-shape plumbing for the public `list_contacts()` path — sole owner of the `list_contacts` contract** (parallel of T064a for contacts; today's `contacts.list_contacts` at `src/pylocal_akuvox/contacts.py:39-53` calls `Contact.from_api_response(item)` with no capability context). Implementation:
  - Extend `contacts.list_contacts(http, *, page=None, capabilities: DeviceCapabilities | None = None)` (new kwarg, default `None`; **the kwarg is `capabilities=`, not `schema_shape=` — the read parser consumes the full `DeviceCapabilities` and consults `capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)` internally** to pick the parse branch). Thread it to each `Contact.from_api_response(item, capabilities=capabilities)` call at line 53.
  - Update `AkuvoxDevice.list_contacts()` in `src/pylocal_akuvox/device.py` to call `contacts.list_contacts(self._http, page=page, capabilities=self._capabilities)`.
  - Add **two tests** in `tests/unit/test_contacts.py` (sibling to T060) that prove the plumbing is wired end-to-end (analogous structure to T064a):
    1. **Apartment-book branch test** (proves `capabilities` is threaded): instantiate `AkuvoxDevice` whose `self._capabilities` carries `schema_shapes={"contact": SchemaShape.APARTMENT_BOOK}`; mock `/api/contact/get` to return apartment-book-keyed items (`APTName`/`APTNum`/`Building`/`Landline`, **no `ID`** — door-phone parser raises on missing `ID`); call `await device.list_contacts()`; assert each returned `Contact` parses without raising. **This test MUST fail if `AkuvoxDevice.list_contacts()` does not pass `capabilities=self._capabilities` through** — because the default parser branch raises on missing `ID`.
    2. **Door-phone default baseline**: instantiate `AkuvoxDevice` whose `self._capabilities` has empty `schema_shapes`; mock `/api/contact/get` to return door-phone-keyed items (`Name`/`Phone`/`ID`); assert each returned `Contact` parses byte-identically to today's behaviour. Locks FR-016 for the default-empty case.
  Covers FR-015, FR-017 (end-to-end through public surface), and the read-side of FR-016.
- [ ] T066b [US3] **Apply the same read-path audit to `list_schedules()` and `list_groups()`**: today `schedules.list_schedules` and `groups.list_groups` (`src/pylocal_akuvox/schedules.py:277`, `src/pylocal_akuvox/groups.py:52`) call their respective `from_api_response` parsers with no capability context. For each, add a regression test in `tests/unit/test_schedules.py` and `tests/unit/test_groups.py` that asserts the existing byte-identical parse behaviour is preserved for X916 default callers (no new kwarg required if the parser does not yet consult `capabilities` — only adds the plumbing if a `field_aliases`/`schema_shapes` extension is identified). If no extension is identified for schedules/groups, document explicitly in the test docstring that "no per-device-class read aliasing is known for schedule/group; this test pins the no-op baseline so future capability extensions land with a visible plumbing change." Covers FR-014 / FR-015 audit completeness; no behavioural change unless an extension is needed.
- [ ] T067 [US3] Update the four existing entries in `src/pylocal_akuvox/capability_matrix.py` (X916, X915S current, E18C current, IT83) to populate explicit `field_aliases["schedule_relay"]` and `schema_shapes["contact"]` per `data-model.md` §"`FieldAliases` and the schedule-relay logical field" and §"`SchemaShape` values":
  - X916: `field_aliases["schedule_relay"] = DEFAULT_USER_FIELD_ALIASES`, `schema_shapes["contact"] = DOOR_PHONE`.
  - E18C current: same as X916.
  - X915S current: `read=("Schedule","ScheduleRelay","Schedule-Relay")` (current FW returns `Schedule`), `write` same as X916; `schema_shapes["contact"] = APARTMENT_BOOK`.
  - IT83: alias and schema fields may be left empty or defaulted (writes are `UNKNOWN` so the parser is not exercised; the matrix entry merely declares them). Covers FR-014, FR-015, FR-017.

### Phase 3 verification gate

- [ ] T068 [Gate] Run `uv run ruff check src/ tests/`, `uv run mypy src/ tests/`, `uv run interrogate src/ tests/`. All clean.
- [ ] T069 [Gate] Run `uv run pytest tests/unit/test_users.py tests/unit/test_models.py tests/unit/test_contacts.py tests/unit/test_schedules.py tests/unit/test_groups.py tests/unit/test_matrix.py -x -v` and confirm every pre-existing test passes WITH NO LOGIC CHANGES other than where a test was specifically asserting "this conditional lives in this file" (allowed: tests that probed `users.py` line content). The new tests landed in this phase MUST also pass: T058 (alias-aware parser unit tests), T060 (schema-shape parser unit tests), T061 (synthetic-matrix-entry test in `test_matrix.py`), T064a (read-side `list_users` end-to-end alias plumbing — non-default + conflict-resolution cases), T066a (read-side `list_contacts` end-to-end schema-shape plumbing — apartment-book + door-phone baseline), and T066b (`list_schedules` / `list_groups` baseline no-op regression). Do `git diff --stat` against the PR base for `tests/unit/test_users.py`, `tests/unit/test_models.py`, `tests/unit/test_contacts.py`, `tests/unit/test_schedules.py`, `tests/unit/test_groups.py`, `tests/unit/test_matrix.py` and confirm only NEW tests added (T058, T060, T061, T064a, T066a, T066b) plus minimal location-pin removals — no payload-shape or parse-shape assertion changes against existing tests. Covers FR-016, SC-008.
- [ ] T070 [Gate] Run `uv run pytest tests/ -x -q` (full suite). All green. Coverage non-regression vs T054 (Phase 2 closing) numbers.
- [ ] T071 [Phase 3 Checkpoint] Walk `quickstart.md` steps 8 and 9 manually and confirm each command produces the expected output. This independently verifies SC-008 (existing tests stay green after refactor) and SC-007 (single matrix entry suffices for new firmware band — quickstart step 9 + T061). Confirm spec US3 acceptance scenarios 1–4 are each covered by at least one test in T058–T061 plus the new end-to-end tests added by T064a (read-side `list_users` plumbing — non-default alias + conflict resolution), T066a (read-side `list_contacts` plumbing — apartment-book branch + door-phone baseline), and T066b (`list_schedules` / `list_groups` baseline regression) plus the unchanged regression tests. Confirm Phase 1+2 quickstart steps 1–7 are still green.

### Phase 3 task-list update (separate atomic commit in PR 3)

- [ ] T072 [Phase 3 task list update] Mark T057–T071 (including T064a, T066a, T066b) complete in `specs/008-capability-matrix/tasks.md` as a SEPARATE atomic commit in PR 3 (`Docs(tasks): Mark Phase 3 tasks complete`). This commit is the LAST commit in PR 3 — same PR as the implementation commits, separate atomic commit per AGENTS.md §"Task List Updates Are Separate Commits". DO NOT open this as its own follow-up PR (PRs #126 / #131 retrospective).

**Phase 3 dependencies (DAG — no cycles)**: T057 (snapshot baseline) → T058–T061 (red tests, parallel where files differ) → T062 (default `DEFAULT_USER_FIELD_ALIASES` constant) → split into independent leaves:
- T063 (read parser `User.from_api_response` kwarg) — depends on T062
- T064 (write paths `users.add_user` / `modify_user` `field_aliases=` kwarg) — depends on T062
- T065 (read parser `Contact.from_api_response` kwarg) — depends on T062
- T064a (read-side `list_users` plumbing) — depends on T063 + T064 (needs both the kwarg-aware parser AND the write paths so the end-to-end test can instantiate `AkuvoxDevice` and call `list_users`)
- T066 (mutation-payload `contacts.add_contact` / `modify_contact` `schema_shape=` kwarg) — depends on T065
- T066a (read-side `list_contacts` plumbing with `capabilities=` kwarg) — depends on T065 (parser is the contract); independent of T066 (mutation-only)
- T066b (`list_schedules` / `list_groups` baseline regression tests) — depends on T062 only (no parser change required; baseline-pin tests)
- T067 (matrix entries population) — depends on T062 + T065 (needs both default aliases and schema-shape enum reachable for matrix wiring)

Then → T068–T071 (gates, sequential) → T072 (commit). Note T065 and T066 are no longer mutually-dependent: T066 only owns mutation payloads in `contacts.py`, and T066a is the sole owner of the `list_contacts` read-path contract.

**Phase 3 PR exit**: PR 3 merged with quickstart steps 1–9 green and existing test logic unchanged.

---

## Phase 4: PR 4 — Documentation and MVP example integration (User Story 4, Priority P3)

**Goal**: Publish a "Device support matrix" doc page kept in sync with the matrix; refactor `examples/mvp_test.py` to probe-then-skip-supported. Depends on Phases 1–3 being merged.

**Independent Test (mirrors spec US4 §"Independent Test")**: Run `examples/mvp_test.py` against each of the four supported device classes; confirm (a) the script begins by probing capabilities, (b) operations the device does not support are skipped with a clear message rather than attempted-and-failed, (c) the documentation page lists each device class and its capabilities and matches what the library actually exposes for that class.

### Setup

- [ ] T073 Create `docs/api/capabilities.rst` as a stub: SPDX comment header (per neighbouring `.rst` files), one-line title, placeholder for autodoc + matrix render directives (no content yet — content added by T079).
- [ ] T074 [P] Create `tests/unit/test_docs_matrix_consistency.py` as a stub (SPDX, docstring, pytest import).
- [ ] T075 [P] Create `tests/integration/` directory if not present; create `tests/integration/__init__.py` and `tests/integration/test_mvp_smoke.py` as stubs (SPDX, docstring, pytest + aioresponses imports).

### TDD: Contract tests (red)

- [ ] T076 [P] [US4] In `tests/unit/test_docs_matrix_consistency.py`, write the doc-vs-matrix consistency test per research.md Decision 11 (FR-018, SC-009):
  - Read `docs/api/capabilities.rst` as plain text.
  - For each entry's `pattern.model_prefix` in `CAPABILITY_MATRIX`, assert the prefix appears in the .rst body.
  - Conversely, assert that every model prefix mentioned as a heading in the .rst (collected by regex on `^X916|^X915S|^E18C|^IT83` heading lines) corresponds to an entry in `CAPABILITY_MATRIX`.
  - Pure-text scan (no sphinx parse) so the test does not require sphinx in CI.
- [ ] T077 [US4] In `tests/integration/test_mvp_smoke.py`, write `test_mvp_against_it83` per research.md Decision 9 + quickstart step 11 (FR-019, SC-010):
  - Mock all probe URLs for an IT83 device.
  - Mock `/fcgi/do?action=OpenDoor&relay=1` (success).
  - Run `examples/mvp_test.py`'s main flow under capsys; capture stdout.
  - Assert stdout contains the regex `^  SKIP: add_user: status unknown on this device class \(IT83\)`.
  - Assert stdout contains the regex `^  SKIP: add_contact: status unknown on this device class \(IT83\)`.
  - Assert stdout contains the regex `^  OK:   trigger_relay`.
  - Assert the `aioresponses` request log contains the FCGI URL exactly once and zero requests to `/api/user/set` / `/api/contact/set`.
- [ ] T078 [P] [US4] In `tests/integration/test_mvp_smoke.py`, write `test_mvp_against_x916`: against a mocked X916, every step is reported `OK:` with no `SKIP:` lines (regression check that the probe-then-skip path doesn't over-skip on supported devices).

### Implementation (green)

- [ ] T079 [US4] Author `docs/api/capabilities.rst` per research.md Decision 11: `:autoclass:` directives for `pylocal_akuvox.Capability`, `pylocal_akuvox.CapabilityStatus`, `pylocal_akuvox.DeviceCapabilities`; a `.. capability-matrix::` custom directive (or inline-Python helper invoked at conf.py load) that imports `CAPABILITY_MATRIX` and emits a reST grid table; a "Contributing a new device class" section with the worked example referenced in `contracts/matrix-lookup.md` §"Adding a new entry" (covers FR-018, SC-007 demo). Headings include `X916`, `X915S`, `E18C`, `IT83` so T076 finds them. Makes T076 green.
- [ ] T080 [US4] Update `docs/api/index.rst` to add `capabilities` to the toctree.
- [ ] T081 [US4] Implement the `.. capability-matrix::` sphinx directive (Decision 11): a small Python class in `docs/_ext/capability_matrix.py` (or inline in `docs/conf.py`) that imports `pylocal_akuvox.capability_matrix.CAPABILITY_MATRIX` at build time and produces a reST grid table with one row per entry (model prefix, firmware band, supported / unsupported / unknown counts, provenance). Register the extension in `docs/conf.py`.
- [ ] T082 [US4] Refactor `examples/mvp_test.py` per research.md Decision 9 (FR-019):
  - Call `await device.probe_capabilities()` once at startup, after `__aenter__` returns.
  - Define the `step(name, capability, fn)` helper that consults `device.capabilities.status_of(capability)` and prints `SKIP: {name}: not supported on this device class ({device_class})` for `UNSUPPORTED`, `SKIP: {name}: status unknown on this device class ({device_class}); add a matrix entry or set device.attempt_unknown_capability=True to opt in` for `UNKNOWN`, `OK:   {name}` after a successful `await fn()`, or `SKIP: {name}: {exc} (reason={exc.reason})` if `AkuvoxUnsupportedError` slipped through.
  - Wrap each existing demo step (list_users, add_user, list_contacts, add_contact, trigger_relay, etc.) through `step()` with the appropriate `Capability` member.
  - Makes T077, T078 green.

### Phase 4 verification gate

- [ ] T083 [Gate] Run `uv run ruff check src/ tests/ examples/`, `uv run mypy src/ tests/ examples/`, `uv run interrogate src/ tests/ examples/`. All clean.
- [ ] T084 [Gate] Run `uv run pytest tests/ -x -q`. All green (unit + integration). Coverage non-regression vs T070 (Phase 3 closing).
- [ ] T085 [Gate] Run `uv run --extra docs sphinx-build -W -b html docs/ docs/_build/html`. Zero warnings (quickstart step 12). If this fails for purely environmental reasons (missing optional dep in CI sandbox) but T084 + T083 + T076 pass, do NOT block the PR — record the environmental failure in PR description per quickstart step 12 caveat.
- [ ] T086 [Phase 4 Checkpoint] Walk `quickstart.md` steps 10, 11, 12 manually and confirm each produces the expected output. This independently verifies SC-009 (doc-vs-matrix consistency), SC-010 (mvp_test snapshot), and the sphinx smoke-build. Confirm spec US4 acceptance scenarios 1–3 are each covered by at least one test in T076–T078 or by direct doc inspection. Confirm Phase 1–3 quickstart steps 1–9 are still green.

### Phase 4 task-list update (separate atomic commit in PR 4)

- [ ] T087 [Phase 4 task list update] Mark T073–T086 complete in `specs/008-capability-matrix/tasks.md` as a SEPARATE atomic commit in PR 4 (`Docs(tasks): Mark Phase 4 tasks complete`). This commit is the LAST commit in PR 4 — same PR as the implementation commits, separate atomic commit per AGENTS.md §"Task List Updates Are Separate Commits". DO NOT open this as its own follow-up PR (PRs #126 / #131 retrospective).

**Phase 4 dependencies**: T073–T075 (setup, parallel) → T076–T078 (red tests, parallel where files differ) → T079 (rst content, blocks T076 turning green) → T080 (toctree) → T081 (directive) → T082 (mvp refactor) → T083–T086 (gates, sequential) → T087 (commit).

**Phase 4 PR exit**: PR 4 merged. Issue #123 closeable.

---

## Final Cleanup

- [ ] T088 After PR 4 merges, post a closing comment on issue #123 referencing the four implementation PRs (PR 1–4) plus the spec PR (PR 0). Confirm:
  - All four supported device classes (X916, X915S current FW, E18C current FW, IT83) have matrix entries with provenance (SC-004).
  - Documentation page lists every matrix entry and vice versa (SC-009).
  - `examples/mvp_test.py` skips unsupported steps with reason (SC-010).
  - Pre-existing #99/#101 and #118/#120 regression tests pass without logic changes (SC-008).
  - The eleven success criteria SC-001 … SC-011 each have at least one verifying test or quickstart step.
  Close issue #123.
- [ ] T089 [Final task list update] Mark T088 complete in `specs/008-capability-matrix/tasks.md`. This update can ride in any small subsequent docs PR or, if no further docs PR is queued, as a one-commit follow-up `Docs(tasks): Close 008-capability-matrix task list` PR — this is the ONLY task-list update permitted to land outside an implementation PR, because issue closure is itself a non-PR action.

---

## Coverage Map: FR / SC / Contract → Tasks

For pre-merge auditing. Every FR-001 … FR-021 and SC-001 … SC-011 must appear in the right column.

### Functional Requirements

| Requirement | Implementing tasks | Verifying tests |
|-------------|--------------------|-----------------|
| **FR-001** Capability enumeration, extensible | T017 | T009 |
| **FR-002** `DeviceCapabilities` three-valued status profile + `supported_set` view | T017, T018, T021 | T010, T011, T012, T015a |
| **FR-003** `probe_capabilities()` non-destructive + strict no-write-inference from read endpoints | T021, T024 | T014, T015, T016, T041 |
| **FR-004** Failure-shape classification + 401/403 abort | T020, T025 | T015 |
| **FR-005** Probe idempotence | T021 | T016 |
| **FR-006** Matrix covers four supported device classes | T045 | T035 |
| **FR-007** Provenance per entry | T045 | T035 |
| **FR-008** Connect-time matrix population (no probing) | T047 | T036 |
| **FR-009** Probe results win, with merge rule preserving matrix writes | T051 | T041 |
| **FR-010** Structured `AkuvoxUnsupportedError` | T044 | T033, T042 |
| **FR-011** Per-method capability gate (audit-locked: introspection test enumerates every public `AkuvoxDevice` coroutine method) | T048, T049 | T038 (incl. `test_every_public_device_method_has_capability_gate` introspection lock) |
| **FR-012** Adapter dispatch with caller override | T046, T050 | T040 |
| **FR-013** Conservative-on-unknown-device | T047 | T037 |
| **FR-014** Field-name aliasing from capability record (end-to-end through `list_users()` public surface) | T062, T063, T064, T064a, T067 | T058, T059, T064a (read-path integration), T066b (audit baseline) |
| **FR-015** Schema-shape selection from capability record (end-to-end through `list_contacts()` public surface) | T065, T066, T066a, T067 | T060, T066a (read-path integration), T066b (audit baseline) |
| **FR-016** No externally observable change after Phase 3 | T063, T064, T064a, T065, T066, T066a | T069 (existing tests unchanged), T066b (no-op baseline pins for schedules/groups) |
| **FR-017** Single matrix entry suffices for new firmware band | T067 | T061, T064a, T066a (each exercises a synthetic matrix entry end-to-end through a public list method) |
| **FR-018** Doc page in sync with matrix | T079, T081 | T076 |
| **FR-019** mvp_test probes + skips with reason | T082 | T077, T078 |
| **FR-020** Tests against four mocked supported device classes | T035, T036, T038, T040 | (test tasks themselves) |
| **FR-021** `attempt_unknown_capability` opt-in | T048, T049 | T039 |

### Success Criteria

| Criterion | Verifying task |
|-----------|----------------|
| **SC-001** Probe non-destructive | T014 (request-log denylist assertion) |
| **SC-002** Probe idempotent | T016 (back-to-back byte-equal: `assert a == b`) |
| **SC-003** Four failure-shape classifications | T015 (parametrised) |
| **SC-004** Provenance for four supported device classes | T035 (`test_every_entry_has_provenance`) |
| **SC-005** Per-method gate request-log | T038 (X915S add_contact, IT83 add_user, IT83 trigger_relay API) |
| **SC-006** Adapter dispatch picks API on X916, FCGI on IT83 | T040 |
| **SC-007** Single matrix entry suffices | T061 (`test_add_hypothetical_entry`) |
| **SC-008** Pre-existing #99/#101 / #118/#120 tests stay green | T069 |
| **SC-009** Doc-vs-matrix consistency | T076 |
| **SC-010** mvp_test against IT83 reports skipped-with-reason | T077 |
| **SC-011** `attempt_unknown_capability` request-log both states | T039 |

### Contracts

| Contract | Test tasks |
|----------|-----------|
| `contracts/probe-api.md` | T008a, T014, T015, T015a, T016, T025, T041 |
| `contracts/matrix-lookup.md` | T013, T034, T035, T036, T037 |
| `contracts/unsupported-error.md` | T033, T042 |
| `contracts/adapter-dispatch.md` | T040 |

---

## Implementation Strategy

**MVP scope (smallest shippable increment)**: Phase 1 (PR 1) alone.

After PR 1 merges, an integrator can call `await device.probe_capabilities()` against any Akuvox device and receive a structured `DeviceCapabilities` report with per-capability status, field aliases observed in responses, schema shapes observed, and freeform notes — without any behaviour change for existing callers and without firing any relays or modifying any data on the device. That is itself a shippable feature; the matrix, surfacing, refactor, and docs of Phases 2–4 are progressive improvements layered on top.

**Incremental delivery**:

1. **PR 0 (spec)**: artifacts only. Lands first.
2. **PR 1 (Phase 1)**: opt-in probe. Backwards compatible. SC-001/2/3 verified.
3. **PR 2 (Phase 2)**: matrix-driven fail-fast + adapter dispatch. First behaviour change visible to integrators on supported devices. SC-004/5/6/11 verified.
4. **PR 3 (Phase 3)**: refactor existing aliasing onto matrix. Externally a no-op. SC-007/8 verified.
5. **PR 4 (Phase 4)**: docs + mvp_test integration. SC-009/10 verified.

**Parallelisable work**:

- Within Phase 1: T005–T008 (stubs) all parallel. T008a, T009–T013, T015, T015a (red tests, different files or independent test functions) parallel. T017 implementation parallel with T013 verification on `DeviceClassPattern` since they touch different test focuses.
- Within Phase 2: T030–T032 (stubs) parallel. T033, T034, T035 (red tests, different files) parallel. T045 (matrix data) parallel with T046 (adapters) — different files.
- Within Phase 3: T058 and T060 (red tests in different files) parallel. T063, T064 (refactor `models/users.py` vs `users.py`) parallel because different files; both unblocked by T062.
- Within Phase 4: T073–T075 (stubs) parallel. T076 and T078 (different test files / independent tests) parallel.
- Across phases: phases are SEQUENTIAL (each phase's PR must merge before the next branches). No cross-phase parallelism.

**Risk hedges**:

- **Phase 1 require() vs Phase 2 exception evolution**: Phase 1's `DeviceCapabilities.require()` raises message-only `AkuvoxUnsupportedError` (the existing class shape). T012 asserts message text, not `.reason`. Phase 2 T044 evolves the class additively; Phase 2 T048 updates `require()` to pass kwargs. This avoids cross-phase coupling.
- **Phase 3 backward-compat blast radius**: T069 explicitly diff-checks that `tests/unit/test_users.py` and `tests/unit/test_models.py` gain only NEW tests; no payload-shape or parse-shape edits. T057 captures the snapshot the diff is checked against.
- **Phase 4 sphinx availability**: T085 sphinx-build is a soft gate (quickstart step 12 explicitly allows environmental failures); T076 plain-text consistency test is the hard gate (no sphinx required) and runs in regular pytest.
