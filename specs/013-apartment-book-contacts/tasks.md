<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Tasks: Apartment-Book Contact Schema Support (X915S)

**Input**: Design documents from `/specs/013-apartment-book-contacts/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md,
contracts/apartment-book-read.md, contracts/contact-write-rejection.md,
quickstart.md (all merged to `main`).
**Branch**: `013-apartment-book-contacts` hosts the future implementation
PR. The spec PR, plan PR, and this tasks artifact each ship as separate
documentation PRs. This tasks PR leaves every checkbox **unchecked**;
checkbox flips ride on the later implementation PR (per AGENTS.md §"Task
List Updates Are Separate Commits").

**Tests are MANDATORY** per constitution §II (TDD). Each phase leads with a
failing (red) test before the production change (green). No production code
is written before a failing test pins the behaviour.

**Atomic commits** per AGENTS.md §"Atomic Commits": the implementation PR
keeps the model+parser, matrix entry, service cleanup, envelope
translation, and docs as logically separate commits. Only the
implementation PR carries the `Closes #121` keyword — this tasks PR
references #121 without closing it.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no
  incomplete dependencies between them).
- **[Story]**: Maps the task to a spec user story (US1–US5) where one
  applies. Cross-cutting setup, full-gate, and final-sweep tasks carry no
  story label.
- Every task names exact file path(s), a goal, files touched, and
  acceptance criteria.

## Path Conventions

Single Python package: `src/pylocal_akuvox/`, `tests/unit/`, `docs/`,
`README.md`. Spec artifacts in `specs/013-apartment-book-contacts/`.

## User-story → phase map

| Story | Priority | Phases |
|---|---|---|
| US1 — Read apartment-book contacts without losing metadata | P1 | Phase 2 |
| US2 — Clear "not supported" signal on write | P1 | Phase 3 (matrix), Phase 4 (service cleanup), Phase 5 (envelope) |
| US3 — Door-phone behaviour unchanged | P1 | Phase 2 (byte-identity regression) |
| US4 — Reliably reference an ID-less apartment-book record | P2 | Phase 6 (identifier docs) |
| US5 — Understand which device class uses which contact model | P3 | Phase 6 (device-class model docs) |

## Live-source validation cheat sheet

Validated against `main` at tasks-authoring time (worktree base
`23b23fb`). Re-run these checks before implementation; **live source is
canonical** if anything drifts.

- `src/pylocal_akuvox/models/contacts.py`: `@dataclass(frozen=True,
  kw_only=True) class Contact` with exactly four fields today (`name: str`;
  `id`, `phone`, `group: str | None = None`). `from_api_response(cls, data,
  *, capabilities=None)` selects `shape =
  capabilities.schema_shapes.get("contact", SchemaShape.DOOR_PHONE)`,
  requires `Name` (raises `AkuvoxParseError`), and has an **already-present
  `APARTMENT_BOOK` branch that is byte-identical to the door-phone branch**
  — both call `cls(name=name, id=data.get("ID"), phone=data.get("Phone")
  or None, group=data.get("Group") or None)`. The class docstring/branch
  comment currently say the extra apartment-book keys are "accepted but
  currently discarded" / "deferred to a follow-up issue" — **this wording
  must be updated** when the fields are surfaced. `to_api_payload()` emits
  only `Name` (always) and `ID`/`Phone`/`Group` (when not `None`).
  **Confirmed: the group API key is `Group`** (`data.get("Group")`), **not**
  `GroupID`.
- `src/pylocal_akuvox/contacts.py` (service layer): module constant
  `_APARTMENT_BOOK_WRITE_DEFERRAL_MSG`; `add_contact(http, *, name,
  phone=None, group=None, schema_shape: SchemaShape | None = None)` and
  `modify_contact(http, *, id, name=None, phone=None, group=None,
  schema_shape=None)` each contain `if shape is SchemaShape.APARTMENT_BOOK:
  raise NotImplementedError(_APARTMENT_BOOK_WRITE_DEFERRAL_MSG)`.
  `delete_contact(http, *, id)` is shape-agnostic (no `schema_shape=`).
  `list_contacts(http, *, page=None, capabilities=None)` threads
  `capabilities=` into `Contact.from_api_response`.
- `src/pylocal_akuvox/_device_contacts.py`: `_contact_shape(ctx) ->
  SchemaShape` helper; `add_contact`/`modify_contact` wrappers call
  `ctx.capabilities.require(Capability.CONTACT_ADD/MODIFY,
  allow_unknown=ctx.allow_unknown)` and pass `schema_shape=_contact_shape(ctx)`
  into the service functions. `list_contacts` requires `CONTACT_LIST` and
  threads `capabilities=ctx.capabilities` (does **not** use `_contact_shape`).
  `delete_contact` requires `CONTACT_DELETE` and delegates without a shape.
- `src/pylocal_akuvox/capability_matrix.py`: `_X915S_CURRENT =
  DeviceCapabilities(device_class="X915S", ...)` (≈ line 95). Its
  `capabilities={...}` has `CONTACT_LIST: SUPPORTED` and `CONTACT_ADD:
  UNSUPPORTED` (with a `# Issue #121:` comment) and **no** `CONTACT_MODIFY`
  / `CONTACT_DELETE` entries today (so both default to `UNKNOWN`).
  `schema_shapes={"contact": SchemaShape.APARTMENT_BOOK}` stays.
- `src/pylocal_akuvox/_capability_profile.py`: `DeviceCapabilities.require(
  capability, *, allow_unknown=False)` — `SUPPORTED` returns; `UNSUPPORTED`
  always raises `AkuvoxUnsupportedError(f"Device class {device_class} does
  not support {capability.value}", capability=…, device_class=…,
  reason="capability_missing")` **regardless of `allow_unknown`**; `UNKNOWN`
  with `allow_unknown=True` returns (falls through to the network);
  `UNKNOWN` otherwise raises `reason="capability_unknown"` (or
  `device_unrecognized` for the empty fallback profile). `status_of(...)`
  and `supported_set` are the pre-flight surface (FR-009).
- `src/pylocal_akuvox/_http.py`: `_UNSUPPORTED_MSG = "Api unsupported"`
  (line ≈ 31). `_handle_response` (≈ 269) does `if _UNSUPPORTED_MSG in
  message: raise AkuvoxUnsupportedError(message)` (**case-sensitive, no
  `reason`**) **before** `if retcode < 0: raise AkuvoxDeviceError(message)`.
  The raw `_request_raw(...)` path returns the body tuple and **bypasses**
  `_handle_response` (so it is unaffected by the translation change).
- `src/pylocal_akuvox/_probe_outcomes.py`: already defines
  `_API_UNSUPPORTED_MARKER = "api unsupported"` and
  `_ACTION_UNSUPPORTED_MARKERS = ("unsupported action", "unsupport action")`
  (the device typo). `_http.py` keeps its **own** local marker constants
  (research.md Decision 4 — do **not** import from the probe module, to
  avoid inverting module layering). The `unsupport action` / `unknow`
  Akuvox API strings need **no** per-line annotation: `.codespellrc`
  already ignores them repo-wide via `ignore-words-list =
  thur,unknow,unsupport`, so codespell stays green without any inline
  `# codespell:ignore`.
- `src/pylocal_akuvox/exceptions.py`: `AkuvoxUnsupportedError(message, *,
  capability=None, device_class=None, reason=None)`; `reason` closed set
  includes `capability_missing`, `capability_unknown`,
  `envelope_unsupported`, `device_unrecognized`, `None`.
- `tests/unit/test_contacts.py`: `BASE_URL` fixtures; existing tests that
  **pin the behaviour being removed** and must be rewritten in Phase 4:
  `test_add_contact_service_function_default_shape_byte_identical` (≈ 633,
  uses `schema_shape=DOOR_PHONE`),
  `test_add_contact_service_function_apartment_book_raises` (≈ 667, expects
  `NotImplementedError`),
  `test_modify_contact_service_function_apartment_book_raises` (≈ 690,
  `NotImplementedError`),
  `test_modify_contact_service_function_door_phone_byte_identical` (≈ 709,
  `schema_shape=DOOR_PHONE`),
  `test_wrapper_add_contact_passes_door_phone_for_x916` (≈ 744, asserts the
  wrapper passes `schema_shape`). The door-phone parse tests
  (`test_contact_from_api_response_door_phone_default` ≈ 522 and the
  apartment-book `_no_id` test ≈ 547) stay valid (new fields default `None`).
- `tests/unit/test_http.py`: imports `AkuvoxUnsupportedError`; `BASE_URL =
  "http://192.168.1.100"`; `test_unsupported_api_raises_unsupported_error`
  (≈ 223) **asserts `exc_info.value.reason is None`** for the `"Api
  unsupported"` envelope — this assertion **must be updated** to
  `reason == "envelope_unsupported"` in Phase 5.
  `test_request_raw_returns_tuple_for_negative_retcode_envelope` (≈ 856)
  exercises the raw path and is **unaffected**.
- Docs: `docs/api/contacts.rst`, `docs/quickstart.rst` (Manage Contacts at
  ≈ 222), `docs/changelog.rst` (`Unreleased` → `Changed` ≈ 52 / `Added`
  ≈ 67), `README.md`.

---

## Phase 1: Setup & baseline

**Purpose**: Confirm the working tree and capture the current green state
before any TDD red step.

- [ ] T001 Capture the pre-change baseline on `main`.

  - **Goal**: Record that the suite is green and that the
    soon-to-be-removed tests (the `NotImplementedError` deferral, the
    `schema_shape=` kwarg, the `reason is None` envelope assertion)
    currently pin behaviour that will change, so later red/green
    transitions are unambiguous.
  - **Files touched**: none (read-only).
  - **Steps**:
    1. `uv run pytest tests/unit/test_contacts.py tests/unit/test_http.py
       -q` — confirm green.
    2. `uv run pytest -q` then `uv run ruff check`,
       `uv run ruff format --check`, `uv run mypy src tests`,
       `uv run interrogate -c pyproject.toml`, and the project `aislop`
       gate — confirm all clean and coverage at the required 100% branch
       level.
    3. Re-grep the cheat-sheet symbols above and reconcile any drift before
       proceeding — **especially confirm the group key is `Group`** in
       `models/contacts.py`.
  - **Acceptance criteria**: full suite green; lint/format/type/docstring/
    aislop gates clean; cheat-sheet symbols confirmed present at the stated
    locations.

---

## Phase 2 (plan Phase 1): `Contact` model + apartment-book parse (TDD) — US1, US3

**Goal**: Preserve apartment-book metadata on read while keeping the
door-phone path byte-identical. Covers FR-001, FR-002, FR-003, FR-004;
SC-001, SC-002, SC-005.

- [ ] T002 [P] [US1] [US3] Red — author apartment-book parse + door-phone
  byte-identity tests in `tests/unit/test_contacts.py`.

  - **Goal**: Pin that the four apartment-book fields are surfaced on the
    `APARTMENT_BOOK` branch, that a missing `ID` is tolerated, that empty
    values are preserved, and that the door-phone branch and
    `to_api_payload()` are unchanged — before the model gains the fields.
  - **Files touched**: `tests/unit/test_contacts.py` only.
  - **Assertions**:
    1. Parsing the representative X915S record `{"APTName": "1", "APTNum":
       "1", "Building": "", "Landline": "", "Name": "01_monitor", "Phone":
       "192.168.0.10"}` under a `capabilities` record whose
       `schema_shapes["contact"]` is `SchemaShape.APARTMENT_BOOK` yields
       `name="01_monitor"`, `phone="192.168.0.10"`, `id is None`,
       `group is None`, `apt_name == "1"`, `apt_num == "1"`, **`building ==
       ""`** and **`landline == ""`** (empty preserved as information, **not**
       coerced to `None`) (FR-001, US1 scenario 1; SC-001; edge case
       "empty apartment-book fields").
    2. Parsing an apartment-book payload that **omits** `ID` (e.g. `{"APTName":
       "2", "Name": "02_monitor", "Phone": "192.168.0.11"}`) succeeds, with
       `id is None`, `apt_name == "2"`, and `apt_num`/`building`/`landline`
       all `None` (absent keys → `None`) (FR-003, US1 scenario 2; SC-002).
    3. Parsing a door-phone record `{"ID": "1", "Name": "Alice", "Phone":
       "555-0100", "Group": "Residents"}` under `DOOR_PHONE` (and under
       `capabilities=None`) yields the **same** `name`/`id`/`phone`/`group`
       as today **and** `apt_name == apt_num == building == landline is
       None` (FR-002, FR-004, US3 scenario 1; SC-005).
    4. `to_api_payload()` for a door-phone `Contact` **and** for a `Contact`
       constructed with apartment-book fields (e.g. `apt_name="1",
       apt_num="1"`) returns a dict containing **no** `APTName`/`APTNum`/
       `Building`/`Landline` key (only `Name` plus any of `ID`/`Phone`/
       `Group`) (FR-004, US3 scenario 2; SC-005).
    5. (Equality regression) `Contact(name="Alice", id="1",
       phone="555-0100", group="Residents")` equals the parsed door-phone
       result — confirming the new `None`-default fields do not break
       existing keyword construction/equality (FR-002).
  - **Acceptance criteria**: `uv run python -m py_compile
    tests/unit/test_contacts.py` passes; the new field/empty-string
    assertions **fail** (red) because `Contact` has no `apt_name`/`apt_num`/
    `building`/`landline` yet and the `APARTMENT_BOOK` branch discards them.

- [ ] T003 [US1] [US3] Green — add the four optional fields and populate
  them on the apartment-book branch in `src/pylocal_akuvox/models/contacts.py`.

  - **Goal**: Make T002 pass: surface the apartment-book metadata, keep the
    door-phone branch and `to_api_payload()` byte-identical.
  - **Files touched**: `src/pylocal_akuvox/models/contacts.py` only.
  - **Implementation**:
    1. Append four optional fields after `group`, each
       `str | None = None`, with an inline comment naming the source key:
       `apt_name` (`APTName`), `apt_num` (`APTNum`), `building` (`Building`),
       `landline` (`Landline`). Because the dataclass is `kw_only`, this is
       additive (construction/equality/hash preserved) (FR-002).
    2. In the `SchemaShape.APARTMENT_BOOK` branch of `from_api_response`,
       populate the four fields with **uncoerced** `data.get("APTName")`
       etc. — **no `or None`** so an empty string survives as `""` (spec
       edge case "empty values are information"). Keep `id=data.get("ID")`
       (FR-003), and leave `name` required, `phone`/`group` with their
       existing `… or None` coercion. The branch is now **distinct** from
       the door-phone branch (FR-001).
    3. Leave the **door-phone** branch and `to_api_payload()` **untouched**
       so door-phone output is byte-identical and never emits an
       apartment-book key (FR-004).
    4. Update the class/method docstring and the branch comment: remove the
       "accepted but currently discarded" / "deferred to a follow-up issue"
       wording and state that the apartment-book branch now surfaces the
       four fields (door-phone leaves them `None`). Note that
       apartment-book records carry no device `ID` and the library makes no
       library-level uniqueness guarantee (cross-reference FR-010 docs).
       Keep complete docstrings so `interrogate` stays green.
  - **Acceptance criteria**: T002 passes; `uv run pytest
    tests/unit/test_contacts.py -q` green; ruff / ruff format / mypy /
    interrogate / aislop clean; 100% branch coverage on the new lines;
    `from_api_response` stays under C901 ≤10.

**Checkpoint**: Apartment-book reads preserve all four fields and tolerate a
missing `ID`; door-phone reads and write payloads are byte-identical.

---

## Phase 3 (plan Phase 2): Matrix — uniform unsupported contact writes (TDD) — US2

**Goal**: All three mutating ops reject uniformly via the existing
capability gate. Covers FR-005, FR-006, FR-012, FR-013; SC-003, SC-004.

- [ ] T004 [US2] Red — author the uniform-rejection device tests for the
  X915S profile in `tests/unit/test_contacts.py`.

  - **Goal**: Pin that `add_contact`, `modify_contact`, and `delete_contact`
    on an X915S device each raise `AkuvoxUnsupportedError` with
    `reason="capability_missing"`, the matching `CONTACT_*` capability, the
    `X915S` device class, and **zero** network requests — before the matrix
    marks modify/delete unsupported.
  - **Files touched**: `tests/unit/test_contacts.py` only.
  - **Assertions** (build an `AkuvoxDevice` whose effective capabilities are
    the `_X915S_CURRENT` profile, e.g. via the existing matrix lookup /
    capability-injection pattern used in the wrapper tests; use
    `aioresponses` to assert no request is issued):
    1. `await device.add_contact(name="Bob")` raises
       `AkuvoxUnsupportedError` with `reason == "capability_missing"`,
       `device_class == "X915S"`, `capability is Capability.CONTACT_ADD`
       (US2 scenario 1; FR-005).
    2. `await device.modify_contact(id="1", name="Bob")` raises
       `AkuvoxUnsupportedError` with `reason == "capability_missing"` and
       `capability is Capability.CONTACT_MODIFY` (US2 scenario 2; FR-006).
    3. `await device.delete_contact(id="1")` raises
       `AkuvoxUnsupportedError` with `reason == "capability_missing"` and
       `capability is Capability.CONTACT_DELETE` (US2 scenario 2; FR-006).
    4. All three raise the **same** exception type and **same** `reason`,
       and **none** issues an HTTP request (assert the `aioresponses`
       mock recorded zero matching requests — the gate fires before I/O)
       (FR-012; SC-003; SC-004).
  - **Acceptance criteria**: `py_compile` passes; assertion 1 may already
    pass (`CONTACT_ADD` is `UNSUPPORTED` today) but assertions 2-3 **fail**
    (red) because `CONTACT_MODIFY`/`CONTACT_DELETE` are `UNKNOWN` and raise
    `reason="capability_unknown"` (default `allow_unknown=False`) instead of
    `capability_missing`.

- [ ] T005 [US2] Green — mark `CONTACT_MODIFY`/`CONTACT_DELETE` `UNSUPPORTED`
  on the X915S matrix entry in `src/pylocal_akuvox/capability_matrix.py`.

  - **Goal**: Make T004 pass by making the X915S contact-mutation
    capabilities uniformly unsupported — the **only** permitted matrix
    change (FR-013).
  - **Files touched**: `src/pylocal_akuvox/capability_matrix.py` only.
  - **Implementation**:
    1. In `_X915S_CURRENT.capabilities`, add
       `Capability.CONTACT_MODIFY: CapabilityStatus.UNSUPPORTED` and
       `Capability.CONTACT_DELETE: CapabilityStatus.UNSUPPORTED` alongside
       the existing `CONTACT_ADD: UNSUPPORTED`. Extend the `# Issue #121:`
       comment to note all three contact mutations are unsupported over
       HTTP on this firmware (FR-006).
    2. Leave `CONTACT_LIST: SUPPORTED` and `schema_shapes={"contact":
       SchemaShape.APARTMENT_BOOK}` **unchanged**; do **not** touch the
       door-phone (X916/E18C) entries (FR-013).
  - **Acceptance criteria**: T004 passes; `uv run pytest
    tests/unit/test_contacts.py -q` green; ruff / ruff format / mypy /
    interrogate / aislop clean; 100% branch coverage. (No new branches are
    introduced — this is data; verify existing capability/matrix tests that
    enumerate X915S statuses, if any, still pass.)

**Checkpoint**: All three mutating ops reject uniformly with
`AkuvoxUnsupportedError(reason="capability_missing")` before any I/O.

---

## Phase 4 (plan Phase 3): Service cleanup — remove the deferral (TDD) — US2

**Goal**: Eliminate the `NotImplementedError` deferral and the now-dead
`schema_shape=` kwarg so the recognisable capability error is the only
write outcome. Covers FR-005, FR-006, FR-012.

- [ ] T006 [US2] Red — rewrite the deferral/kwarg tests in
  `tests/unit/test_contacts.py`.

  - **Goal**: Replace the assertions that pin the soon-to-be-removed
    `NotImplementedError` branch and `schema_shape=` kwarg, so the suite
    expects the new shape-agnostic service surface.
  - **Files touched**: `tests/unit/test_contacts.py` only.
  - **Assertions** (update the cheat-sheet-listed tests):
    1. Remove/rewrite `test_add_contact_service_function_apartment_book_raises`
       and `test_modify_contact_service_function_apartment_book_raises` so
       they no longer expect `NotImplementedError`; assert instead that the
       service `contacts.add_contact` / `contacts.modify_contact` (called
       directly, without any `schema_shape=`) issue the normal door-phone
       `POST /api/contact/set` payload and do **not** raise
       `NotImplementedError` (FR-005: "never a bare `NotImplementedError`").
    2. Update `test_add_contact_service_function_default_shape_byte_identical`
       and `test_modify_contact_service_function_door_phone_byte_identical`
       to drop the `schema_shape=SchemaShape.DOOR_PHONE` argument — the
       byte-identical door-phone payload is now produced with no
       shape kwarg at all (FR-004 at the service layer).
    3. Update `test_wrapper_add_contact_passes_door_phone_for_x916`: its
       on-the-wire payload assertions still hold, but its docstring/narrative
       references the now-removed `schema_shape` extraction — rewrite it to
       describe the wrapper delegating `name`/`phone`/`group` only (no
       `schema_shape`). Keep the `list_contacts` capability-threading test
       (`test_list_contacts_threads_apartment_book_through_wrapper`)
       unchanged — `list_contacts` still threads `capabilities=`.
    4. (Uniformity belt-and-braces) keep/confirm the Phase 3 device-level
       tests (T004) as the authoritative gated-path assertions; this phase
       only changes the **service-layer** expectations.
  - **Acceptance criteria**: `py_compile` passes; the rewritten tests
    **fail** (red) because the service functions still raise
    `NotImplementedError` on `APARTMENT_BOOK` and still accept
    `schema_shape=` / the wrapper still passes it.

- [ ] T007 [US2] Green — remove the deferral, the dead kwarg, and the dead
  `_contact_shape` pass-through.

  - **Goal**: Make T006 pass by deleting the obsolete write-deferral and the
    vestigial schema-shape plumbing.
  - **Files touched**: `src/pylocal_akuvox/contacts.py`,
    `src/pylocal_akuvox/_device_contacts.py`.
  - **Implementation**:
    1. In `contacts.py`: delete `_APARTMENT_BOOK_WRITE_DEFERRAL_MSG` and the
       `if shape is SchemaShape.APARTMENT_BOOK: raise NotImplementedError(...)`
       block from both `add_contact` and `modify_contact`; drop the
       `schema_shape: SchemaShape | None = None` parameter and the local
       `shape = …` lines from both. Remove the now-unused `SchemaShape`
       import if nothing else in the module references it. Update both
       docstrings to drop the deferral/`schema_shape` wording.
       `delete_contact` and `list_contacts` are unchanged.
    2. In `_device_contacts.py`: delete the `_contact_shape(ctx)` helper and
       stop passing `schema_shape=_contact_shape(ctx)` from the `add_contact`
       and `modify_contact` wrappers (they now delegate `name`/`phone`/
       `group` only). The `require(Capability.CONTACT_ADD/MODIFY, …)` gate
       calls stay. `list_contacts` (threads `capabilities=`) and
       `delete_contact` are unchanged. Remove the now-unused `SchemaShape`
       import if it becomes dead.
  - **Acceptance criteria**: T006 passes; `uv run pytest
    tests/unit/test_contacts.py -q` green; full `uv run pytest -q` green
    (no orphaned reference to `schema_shape`/`_contact_shape`/the deferral
    constant remains — `grep -rn "schema_shape\|_contact_shape\|
    _APARTMENT_BOOK_WRITE_DEFERRAL" src/` returns nothing); ruff / ruff
    format / mypy / interrogate / aislop clean; 100% branch coverage
    (deleting the dead branch keeps coverage at 100%).

**Checkpoint**: The service layer is shape-agnostic for writes; the gated
capability error is the only write outcome — no `NotImplementedError` path
survives.

---

## Phase 5 (plan Phase 4): Envelope translation (TDD) — US2 scenario 3

**Goal**: Route the device `"unsupport action"` envelope to the recognisable
capability error for the opt-in / unrecognised-device path. Covers FR-007,
FR-012; SC-003 (opt-in path).

- [ ] T008 [US2] Red — author the envelope-translation tests in
  `tests/unit/test_http.py`.

  - **Goal**: Pin that the action-unsupported envelopes translate to
    `AkuvoxUnsupportedError(reason="envelope_unsupported")` and that the
    existing `"Api unsupported"` envelope now also carries that reason.
  - **Files touched**: `tests/unit/test_http.py` only.
  - **Assertions**:
    1. A response whose envelope is `{"retcode": -1, "action": "unknow",
       "message": "unsupport action"}` (verbatim Akuvox strings, already
       in `.codespellrc` `ignore-words-list`)
       routed through the public `get()`/`post()` path raises
       `AkuvoxUnsupportedError` with `reason == "envelope_unsupported"` —
       **not** `AkuvoxDeviceError` (FR-007; US2 scenario 3).
    2. A `"unsupported action"` variant likewise raises
       `AkuvoxUnsupportedError(reason="envelope_unsupported")`.
    3. Case-insensitivity: a mixed-case message (e.g. `"Unsupport Action"`)
       still translates (FR-007).
    4. **Update** `test_unsupported_api_raises_unsupported_error`: the
       `"Api unsupported"` envelope still raises `AkuvoxUnsupportedError`,
       but the assertion `reason is None` becomes `reason ==
       "envelope_unsupported"` (the existing translation is preserved and
       now classified — FR-007). `capability`/`device_class` stay `None`.
    5. A non-matching negative-retcode envelope (e.g. `{"retcode": -1,
       "message": "Some other failure"}`) still raises `AkuvoxDeviceError`
       (no over-broadening; the `retcode < 0` fallthrough is intact).
  - **Acceptance criteria**: `py_compile` passes; assertions 1-3 **fail**
    (red) because `_handle_response` matches only the case-sensitive `"Api
    unsupported"` literal and raises `AkuvoxDeviceError` for the action
    markers; assertion 4 **fails** because the current raise carries no
    `reason`.

- [ ] T009 [US2] Green — broaden the envelope match in
  `src/pylocal_akuvox/_http.py`.

  - **Goal**: Make T008 pass by recognising the action-unsupported markers
    case-insensitively and classifying every translated raise.
  - **Files touched**: `src/pylocal_akuvox/_http.py` only.
  - **Implementation**:
    1. Add **local** marker constants (do **not** import from
       `_probe_outcomes` — research.md Decision 4, layering): e.g.
       `_UNSUPPORTED_MARKERS = ("api unsupported", "unsupported action",
       "unsupport action")` (all lowercase). No inline `# codespell:ignore`
       is needed — `.codespellrc` already ignores `unsupport`/`unknow`
       repo-wide. Keep or fold in the existing `_UNSUPPORTED_MSG`.
    2. In `_handle_response`, replace the case-sensitive `if
       _UNSUPPORTED_MSG in message:` test with a case-insensitive membership
       check (e.g. `lowered = message.lower(); if any(m in lowered for m in
       _UNSUPPORTED_MARKERS):`) that raises
       `AkuvoxUnsupportedError(message, reason="envelope_unsupported")`.
       Keep this **before** the `if retcode < 0: raise
       AkuvoxDeviceError(message)` fallthrough so non-matching negative
       retcodes are unaffected (FR-007).
    3. Preserve the `"Api unsupported"` behaviour (now matched
       case-insensitively and carrying the reason). Keep the `_request_raw`
       path untouched (it bypasses `_handle_response`).
  - **Acceptance criteria**: T008 passes; `uv run pytest
    tests/unit/test_http.py -q` green; full `uv run pytest -q` green; ruff /
    ruff format / mypy / interrogate / aislop / codespell clean; 100% branch
    coverage on the new match (cover a matching message, a non-matching
    negative-retcode message, and a success); `_handle_response` stays under
    C901 ≤10.

**Checkpoint**: The `"unsupport action"` / `"unsupported action"` / `"Api
unsupported"` envelopes all surface as
`AkuvoxUnsupportedError(reason="envelope_unsupported")`.

---

## Phase 6 (plan Phase 5): Documentation (US4, US5)

**Goal**: Document the device-class contact model split, the read-only
constraint, and the apartment-book identifier strategy. Covers FR-008
(out-of-band management wording), FR-009 (pre-flight pattern), FR-010,
FR-011; SC-006.

- [ ] T010 [P] [US5] Device-class contact models section in
  `docs/api/contacts.rst` and `README.md`.

  - **Goal**: Let a developer state, from the docs, which device class uses
    which contact model, what fields each carries, and that apartment-book
    contacts are read-only over HTTP (FR-011; SC-006; US5 scenario 1).
  - **Files touched**: `docs/api/contacts.rst`, `README.md`.
  - **Content**:
    1. A comparison (door-phone vs apartment-book): example classes (X916 /
       E18C vs X915S), distinguishing fields (`ID`, `Name`, `Phone`, `Group`
       vs `Name`, `Phone`, `APTName`, `APTNum`, `Building`, `Landline` — **no
       `ID`, no `Group`**), and reads/writes support per class
       (apartment-book = read-only over the HTTP API).
    2. State the new `Contact` fields (`apt_name`/`apt_num`/`building`/
       `landline`, `None` on door-phone) and that contact management on
       apartment-book devices happens out-of-band (device web UI /
       provisioning), matching the actionable-error wording (FR-008).
    3. Note the behaviour is device-class-driven
       (`schema_shapes["contact"]`), not X915S-hard-coded.
  - **Acceptance criteria**: `uv run --extra docs sphinx-build -W -b html
    docs docs/_build/html` is warnings-clean; aislop clean on the changed
    docs; no clear-text/secret leakage.

- [ ] T011 [P] [US4] Apartment-book read, identifier strategy, and
  pre-flight check in `docs/quickstart.rst`.

  - **Goal**: Document the recommended identifier strategy for ID-less
    records and the raise-only pre-flight pattern (FR-009, FR-010; SC-004
    documentation; US4 scenarios 1-2).
  - **Files touched**: `docs/quickstart.rst`.
  - **Content** (mirroring `quickstart.md`):
    1. An apartment-book read example showing the four preserved fields and
       `id is None`; note empty `building`/`landline` are preserved as `""`.
    2. The identifier strategy: no device-assigned `ID`; recommend the
       `(apt_num, phone)` composite key (fallback `name`), and **state the
       limitation** that the library makes no uniqueness guarantee (FR-010;
       US4 scenario 2). Show that two records with the same `name` but
       different `apt_num`/`phone` are distinguishable under the rule (US4
       scenario 1).
    3. The pre-flight pattern using
       `device.capabilities.status_of(Capability.CONTACT_ADD)` /
       `supported_set` (no bespoke accessor — raise-only, FR-009) and a
       `try/except AkuvoxUnsupportedError` example for the write path
       (assert `reason == "capability_missing"`).
  - **Acceptance criteria**: sphinx `-W` build clean; aislop clean; the
    documented composite distinguishes the same-`name` records (US4).

- [ ] T012 [P] Changelog entries in `docs/changelog.rst`.

  - **Goal**: Record the additive fields and the changed write-rejection
    behaviour under `Unreleased`, referencing #121.
  - **Files touched**: `docs/changelog.rst`.
  - **Content**:
    1. `Added`: the four optional apartment-book `Contact` fields
       (`apt_name`/`apt_num`/`building`/`landline`) preserved on
       apartment-book (X915S) reads. `Refs #121.`
    2. `Changed`: contact writes (`add`/`modify`/`delete`) on apartment-book
       device classes now raise a uniform `AkuvoxUnsupportedError`
       (`reason="capability_missing"`) before any I/O; the device
       `"unsupport action"` / `"unsupported action"` envelope now translates
       to `AkuvoxUnsupportedError(reason="envelope_unsupported")`; the
       internal `schema_shape=` deferral path was removed. `Refs #121.`
  - **Acceptance criteria**: sphinx `-W` build clean; entries follow the
    existing `^^^` subsection convention; aislop clean.

**Checkpoint**: The published docs describe both contact models, the
read-only constraint, the identifier strategy, and the pre-flight pattern.

---

## Phase 7: Polish, full validation & pre-PR sweep

**Purpose**: Whole-suite green, coverage gate, and conventions compliance
before the implementation PR.

- [ ] T013 Run the full quality gate.

  - **Goal**: Confirm every gate is green across the whole change.
  - **Files touched**: none (read-only), modulo auto-formatting fixes.
  - **Steps**: `uv run pytest -q` (100% branch coverage enforced);
    `uv run ruff check`; `uv run ruff format --check`;
    `uv run mypy src tests`; `uv run interrogate -c pyproject.toml`; the
    project `aislop` gate over the affected modules (`models/contacts.py`,
    `contacts.py`, `_device_contacts.py`, `capability_matrix.py`,
    `_http.py`, and the touched tests + docs); `codespell` (the verbatim
    Akuvox `unsupport action` / `unknow` strings are already ignored
    repo-wide via `.codespellrc`, so no inline annotation is needed); the
    canonical warnings-as-errors docs build `uv run --extra docs
    sphinx-build -W -b html docs docs/_build/html`.
  - **Acceptance criteria**: all gates green; 100% branch coverage.

- [ ] T014 Pre-PR conventions & REUSE/SPDX sweep.

  - **Goal**: Ensure changed files carry SPDX headers (no **new** source
    file is expected) and the diffs are Conventional-Commit-ready.
  - **Files touched**: none new (verification); fix headers if any new file
    was added.
  - **Steps**: confirm SPDX headers intact on every touched file;
    `grep -rn "GroupID" src/ tests/` returns nothing (the key is `Group`);
    `grep -rn "NotImplementedError\|schema_shape\|_contact_shape\|
    _APARTMENT_BOOK_WRITE_DEFERRAL" src/` returns nothing; run full
    `pre-commit` after staging the implementation files (fix-and-restage on
    failure, never `--no-verify`).
  - **Acceptance criteria**: `pre-commit` clean; REUSE compliant; no dead
    deferral/kwarg/`GroupID` reference remains in `src/`.

---

## Dependencies

- **T001** → everything (baseline first).
- **T002 → T003** (model red before green).
- **T004 → T005** (matrix red before green). Phase 3 is independent of
  Phase 2 at the source level (different files) but is ordered after it for
  a clean per-story narrative.
- **T005 → T006 → T007** (the matrix change makes the gated device path
  authoritative first; only then is the service-layer deferral safe to
  remove). T006 red depends on T005 being green so the device-level
  uniformity holds while the service surface is rewritten.
- **T008 → T009** (envelope red before green). Phase 5 touches `_http.py`/
  `test_http.py` only — disjoint from Phases 2-4.
- **T010, T011, T012** depend on T003/T005/T007/T009 (docs describe the
  final behaviour); they touch different files and are mutually **[P]**.
- **T013, T014** depend on all prior tasks.

## Parallel-execution opportunities

- **Phase 5** (T008/T009, `_http.py` + `test_http.py`) can be developed in
  parallel with Phases 2-4 — it edits disjoint files. Keep separate commits.
- **T010, T011, T012** are `[P]` — different files (`docs/api/contacts.rst`
  + `README.md` vs `docs/quickstart.rst` vs `docs/changelog.rst`).
- **T002** is `[P]` relative to the Phase 5 red test (T008) — different test
  files.
- Read-only validation in T013/T014 runs once the source is final.

## Coverage Map: FR / SC / scenario → Tasks

| Requirement / criterion | Implementing tasks | Verifying tasks |
|---|---|---|
| FR-001 preserve apartment-book metadata on read | T003 | T002 |
| FR-002 apt fields default `None` for door-phone | T003 | T002 |
| FR-003 tolerate a missing `ID` (apartment-book) | T003 | T002 |
| FR-004 door-phone read/write byte-identical | T003 | T002 |
| FR-005 single recognisable write error | T005, T007 | T004, T006 |
| FR-006 uniform across add/modify/delete (+ matrix) | T005 | T004 |
| FR-007 translate `"unsupport action"` envelope | T009 | T008 |
| FR-008 actionable error message (gate + docs) | T005 (gate), T010 | T004, T013 (docs build) |
| FR-009 caller determines write support pre-flight | T011 (docs of existing surface) | T013 |
| FR-010 documented identifier strategy | T011 | T013 |
| FR-011 docs of device-class contact models | T010 | T013 |
| FR-012 no silent/failing writes | T005, T007, T009 | T004, T006, T008 |
| FR-013 consistency with the static matrix | T005 | T004 |
| FR-014 unit test coverage (a)-(e) | — | T002, T004, T006, T008 |
| SC-001 100% of four apt fields preserved | T003 | T002 |
| SC-002 record count + missing-`ID` never raises | T003 | T002 |
| SC-003 three ops → `AkuvoxUnsupportedError`, one reason | T005, T009 | T004, T008 |
| SC-004 write support determinable before any write | T005, T011 | T004 |
| SC-005 door-phone reads/writes unchanged | T003 | T002 |
| SC-006 docs convey model/fields/read-only/identifier | T010, T011 | T013 |
| US1 scenarios 1-3 | T003 | T002 |
| US2 scenarios 1-2 | T005, T007 | T004, T006 |
| US2 scenario 3 (envelope, opt-in) | T009 | T008 |
| US3 scenarios 1-3 | T003 | T002 |
| US4 scenarios 1-2 | T011 | T013 |
| US5 scenario 1 | T010 | T013 |

## Anomalies / open questions

- **Existing tests pin removed behaviour.** Five tests in
  `tests/unit/test_contacts.py` assert the `NotImplementedError` deferral or
  the `schema_shape=` kwarg, and one test in `tests/unit/test_http.py`
  (`test_unsupported_api_raises_unsupported_error`) asserts `reason is None`
  for the `"Api unsupported"` envelope. These are rewritten in T006 (service
  cleanup) and T008 (envelope) respectively — both are intentional,
  spec-driven behaviour changes (FR-005/FR-006/FR-007), recorded in the
  changelog (T012).
- **Group key.** The live source uses the `Group` API key
  (`data.get("Group")`), **not** `GroupID`. All tasks reference `Group`;
  T014 greps `src/`/`tests/` for any stray `GroupID`.
- **Markers not imported.** `_probe_outcomes.py` already defines
  `_API_UNSUPPORTED_MARKER` / `_ACTION_UNSUPPORTED_MARKERS`, but `_http.py`
  keeps **local** copies (research.md Decision 4) to avoid inverting module
  layering. T009 duplicates the markers deliberately; if a future refactor
  unifies them, it must not make `_http` depend on the probe module.
- **`unsupport action` is a verbatim device string (looks like a typo).**
  No inline `# codespell:ignore` is required — `.codespellrc` already
  ignores `unsupport` and `unknow` repo-wide via `ignore-words-list =
  thur,unknow,unsupport`. T013 runs `codespell` to confirm the gate stays
  green.
- **No new public API / no new source file.** Per the plan (raise-only,
  option a), no `contacts_writable` accessor is added; the change is
  confined to existing modules, so no new SPDX header is expected (T014
  verifies).

All symbol and file references above were validated against the live `main`
source at authoring time. Re-run the live-source validation cheat sheet
before implementation if `main` changes.
