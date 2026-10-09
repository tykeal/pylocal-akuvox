<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Apartment-Book Contact Schema Support (X915S)

**Branch**: `013-apartment-book-contacts` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-apartment-book-contacts/spec.md`

## Summary

Issue #121 reports that Akuvox **X915S** apartment intercoms expose an
**apartment-book** `/api/contact/*` schema (`APTName`, `APTNum`, `Building`,
`Landline`, `Name`, `Phone` — **no `ID`, no `Group`**) that is
fundamentally different from the **door-phone** model (X916 / E18C:
`ID`, `Name`, `Phone`, `Group`) the `Contact` dataclass was built around.
Two device-class problems follow: (1) **read fidelity** — `list_contacts()`
succeeds on the X915S but the parser silently **discards** the four
apartment-book fields and yields `id=None`; (2) **write signalling** — the
firmware rejects every contact mutation with
`{"retcode":-1,"action":"unknow","message":"unsupport action"}`, which today
leaks as `AkuvoxDeviceError` (or, on the deferred service path, a bare
`NotImplementedError`).

This is **not a greenfield addition — it completes existing partial
support.** `main` already carries the capability scaffolding for this
device-class split: `SchemaShape.APARTMENT_BOOK`, the X915S matrix entry
(`schema_shapes={"contact": APARTMENT_BOOK}`, `CONTACT_LIST: SUPPORTED`,
`CONTACT_ADD: UNSUPPORTED`), a parser that already tolerates the extra keys
and the missing `ID` (but discards them), the structured
`AkuvoxUnsupportedError` reason taxonomy, and the `AkuvoxDevice.capabilities`
pre-flight surface. The work here is **additive and reconciling**:

1. **Surface** the four apartment-book fields on `Contact` as optional,
   default-`None` fields (`apt_name`, `apt_num`, `building`, `landline`) and
   populate them on the apartment-book parse path **without** changing the
   door-phone output (FR-001/FR-002/FR-003).
2. **Make the unsupported-write signal uniform** across `add_contact`,
   `modify_contact`, and `delete_contact` by marking `CONTACT_MODIFY` and
   `CONTACT_DELETE` `UNSUPPORTED` on the X915S matrix entry (the **only**
   permitted matrix change, per FR-006/FR-013) so the existing capability
   gate raises `AkuvoxUnsupportedError(reason="capability_missing")` for all
   three (FR-005/FR-006), and **route the `"unsupport action"` envelope** in
   `_http.py` to `AkuvoxUnsupportedError(reason="envelope_unsupported")` for
   the opt-in / unrecognised-device path (FR-007/FR-012).
3. **Document** the device-class model split and the apartment-book record
   identifier strategy (FR-010/FR-011).

This `plan.md` PR is **documentation only**. It does **not** modify `src/`,
`tests/`, `examples/`, or `docs/`, and it does **not** close #121 — the later
implementation PR carries the closing keyword. Both deliberate
[NEEDS CLARIFICATION] markers from the spec are resolved here (see "Resolved
Clarifications").

## Technical Context

**Language/Version**: Python ≥3.13.2 (per `pyproject.toml`); CI also exercises
forward versions.
**Primary Dependencies**: No new runtime or test dependencies. Runtime:
`aiohttp` (already present); the parse/gate/envelope work uses only existing
internal modules and the standard library. Tooling (`ruff`, `mypy`,
`interrogate`, `aislop`, `sphinx`, `pytest`, `pytest-asyncio`, `aioresponses`)
is unchanged.
**Storage**: N/A — async Python library; no persistence.
**Testing**: pytest + pytest-asyncio + `aioresponses`. New / extended unit
tests in `tests/unit/test_contacts.py` (apartment-book parse, door-phone
byte-identity regression, the three write ops raising uniformly) and
`tests/unit/test_http.py` (the `"unsupport action"` envelope translation).
100% branch coverage is required and enforced.
**Target Platform**: Async Python applications on Linux/macOS/Windows; no
platform-specific behaviour.
**Project Type**: Single Python package under `src/pylocal_akuvox/`.
**Performance Goals**: No new network round-trips, async boundaries, retries,
or throttling. The read path gains four `dict.get()` lookups per record; the
write path's rejection is a pure in-memory capability check that fires
**before** any I/O. No performance-sensitive path is introduced, so no
benchmark is required (Constitution IV).

**Constraints**:

- **FR-004 (byte-identity) is non-negotiable**: the door-phone parse result
  and any door-phone write payload MUST be unchanged; the apartment-book
  fields MUST default to `None` and MUST never be emitted in a door-phone
  write payload. `Contact.to_api_payload()` is therefore **not** extended.
- **FR-013 (matrix consistency)**: the X915S entry keeps `contact` mapped to
  `APARTMENT_BOOK` and `CONTACT_LIST: SUPPORTED`; the **only** permitted
  matrix change is making `CONTACT_MODIFY` / `CONTACT_DELETE` uniformly
  `UNSUPPORTED` (FR-006). Door-phone classes (X916, E18C) are untouched.
- **FR-007**: the existing `"Api unsupported"` translation MUST be preserved
  while adding the `"unsupport action"` / `"unsupported action"` markers.
- **Empty values are information** (spec Edge Cases): apartment-book fields
  are preserved **as the device returns them**, including empty strings —
  the parser does not coerce `""` to `None` on the apartment-book fields and
  does not raise on emptiness.
- **Device-class-driven, not X915S-hard-coded**: behaviour is selected by
  `schema_shapes["contact"]`; any future apartment-book device inherits it.
- `src/`, `tests/`, `examples/`, and `docs/` are **not** touched by this plan
  PR; all code changes belong to the later implementation PR.

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.0.2. Re-checked
after the phase plan — see "Post-Design Re-Check".*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (NON-NEGOTIABLE)** | PASS | Changes are confined to `models/contacts.py` (four optional fields + the apartment-book parse branch), `capability_matrix.py` (two status entries), `_http.py` (envelope marker match), and a small cleanup in `contacts.py`. SPDX headers already present on every touched file; no new source file is required. Every changed function keeps its docstring (purpose, params, returns, raises) and full type annotations; new fields are typed `str | None`. No function approaches the C901 ≤10 cyclomatic limit (the parse branch is a flat constructor call; the envelope match stays a single membership test). ruff / mypy / interrogate / aislop must pass. |
| **II. Test-Driven Development (NON-NEGOTIABLE)** | PASS | Each behaviour is authored test-first (red): apartment-book field preservation, missing-`ID` tolerance, door-phone byte-identity, the three write ops each raising `AkuvoxUnsupportedError` uniformly, and the `"unsupport action"` envelope translation. No production change precedes its failing test. |
| **III. User Experience Consistency** | PASS | One recognisable error type (`AkuvoxUnsupportedError`) with one reason classification across all three mutating ops; the message names the device class and operation and points the integrator at the out-of-band management channel (FR-008). The new model fields are additive and keyword-only; existing field names/types/meanings are unchanged. |
| **IV. Performance Requirements** | PASS | No new I/O, async boundary, or benchmarked path; the write rejection is an in-memory capability check before any request. No benchmark required. |
| **V. Atomic Commits & Compliance (NON-NEGOTIABLE)** | PASS | Implementation lands as small atomic commits (model+parser, matrix, envelope translation, service cleanup, docs) per `AGENTS.md` Conventional Commits with capitalized types and DCO sign-off; AI co-authorship is attributed in `Co-Authored-By` only. This plan PR is a single `Docs(plan)` commit. No new files in the code phase, so no new SPDX headers are required there; any new artifact carries one. |
| **VI. Phased Development** | PASS | Decomposed into ordered phases below, each with a green checkpoint (targeted tests + ruff + mypy + 100% branch coverage) before the next. Phase boundaries are documented here and carried into `tasks.md` at the next stage. |

**Result**: All gates pass. **Complexity Tracking** remains empty.

## Resolved Clarifications

The spec deliberately retained two [NEEDS CLARIFICATION] markers. The user
deferred **both** to planning for a recommendation. Both are resolved here for
design purposes; full rationale and rejected alternatives live in
[research.md](./research.md).

### Resolved Clarification 1 — Apartment-book record identifier strategy (RECOMMEND c + documented composite)

**Decision**: **Option (c) — expose the raw apartment-book fields and let the
caller choose a key** — as the **library-level** stance, paired with
**documentation that recommends the `(apt_num, phone)` composite** as the
suggested caller-side key and states its limitations. The model assigns **no
synthetic identity**: `id` stays `None` on the apartment-book shape.

**Why (c) over (a)/(b)**:

- The device provides **no `ID`** and the candidate key fields can be **empty
  or duplicated** (`Building` / `Landline` are frequently `""`; `Phone` may
  be empty; `Name` is editable and not guaranteed unique). The library
  therefore **cannot honestly guarantee** uniqueness or stability for any
  composite. Minting a synthetic `id` (option a) or overloading `Name`
  (option b) would advertise a guarantee the data cannot back.
- FR-001 **already** requires surfacing all four apartment-book fields, so
  (c) is essentially free and fully additive — no extra model surface, and
  `id=None` remains truthful (FR-003).
- US4 is still satisfied: the published docs **recommend** keying on the
  `(apt_num, phone)` composite (the most stable pair when both are
  populated), falling back to `name`, and **state the constraint** that the
  device assigns no `ID` on this class and the library makes no
  library-level uniqueness guarantee (FR-010). Two records that differ only
  in their apartment-book fields are distinguishable under that documented
  rule (US4 acceptance #1).

**Rejected**: **(a) composite `(APTNum, Phone)` minted as a synthetic `id`** —
ambiguous when `Phone` is empty or two records share `(APTNum, Phone)`, and a
device-assigned-looking `id` would mislead callers into assuming stability.
**(b) use `Name` as the identifier** — always present and human-meaningful but
editable and not unique; collapses US4's same-`Name` case. Both are recorded
in [research.md](./research.md).

### Resolved Clarification 2 — Capability signalling: raise-only vs probe accessor (RECOMMEND a, raise-only)

**Decision**: **Option (a) — raise-only.** Rely on the **existing**
capability gate plus the **already-exposed** `AkuvoxDevice.capabilities`
surface (`status_of(...)`, `supported_set`). Do **not** add a bespoke
`contacts_writable` / `supports(...)` accessor.

**Why (a) over (b)**:

- FR-009's minimum bar is **already met today**: a caller can run
  `device.capabilities.status_of(Capability.CONTACT_ADD)` (or read
  `supported_set`) **before** issuing any write and get `UNSUPPORTED` on the
  X915S without triggering a failed request.
- Adding a contact-specific convenience accessor **expands the public API
  surface** for marginal ergonomic gain, risks **divergence** from the
  canonical capability profile (a second source of truth to keep in sync),
  and runs against the spec's additive/minimal intent and the Out-of-Scope
  note ("no new capability subsystem"). It also mirrors the conservative
  choice taken in the sibling OpenDoor plan (012), which selected the minimal
  option.
- The ergonomic gap is closed with **documentation**, not new API: the
  quickstart shows the one-line pre-flight `status_of(...)` pattern.

**Rejected**: **(b) add a convenience accessor** — recorded in
[research.md](./research.md) as viable but rejected for surface-area and
single-source-of-truth reasons.

## Design Overview

### Model extension (FR-001/FR-002/FR-004)

`Contact` (frozen, `kw_only=True` dataclass in `models/contacts.py`) gains
**four** optional fields, all defaulting to `None`:

```python
apt_name: str | None = None  # source key: APTName
apt_num: str | None = None  # source key: APTNum
building: str | None = None  # source key: Building
landline: str | None = None  # source key: Landline
```

Because the dataclass is `kw_only`, appending fields with defaults is a
backward-compatible, additive change: existing positional-free construction
and equality semantics are preserved, and door-phone `Contact`s simply carry
the four new fields as `None`. `id`, `name`, `phone`, `group` keep their
names, types, and meanings (FR-002).

### Parser change (FR-001/FR-003 + empty-as-information)

In `Contact.from_api_response`, the `SchemaShape.APARTMENT_BOOK` branch —
**currently byte-identical to the door-phone branch** — is changed to also
populate the four apartment-book fields from the source record using plain
`data.get("APTName")` etc., with **no `or None` coercion** so an empty string
is preserved as information (spec Edge Cases). Absent keys naturally yield
`None` via `dict.get`. `Name` stays required on both branches; `ID` stays
optional on the apartment-book branch (`data.get("ID")` → `None`), preserving
FR-003. The **door-phone branch is left exactly as-is**, so its output is
byte-identical and the four new fields default to `None` (FR-004).

`Contact.to_api_payload()` is **not** modified: it continues to emit only
`Name` / `ID` / `Phone` / `Group`, guaranteeing the door-phone write payload
never carries an apartment-book key (FR-004) and that apartment-book devices
(read-only) never produce one.

### Uniform write rejection (FR-005/FR-006/FR-012)

The **capability gate is the single uniform rejection mechanism.** The X915S
matrix entry already marks `CONTACT_ADD: UNSUPPORTED`; this feature adds
`CONTACT_MODIFY: UNSUPPORTED` and `CONTACT_DELETE: UNSUPPORTED` (the **only**
permitted matrix change, FR-006/FR-013). All three
`AkuvoxDevice.{add,modify,delete}_contact` wrappers in `_device_contacts.py`
already call `ctx.capabilities.require(Capability.CONTACT_*, ...)`, which for
an `UNSUPPORTED` status raises
`AkuvoxUnsupportedError(capability=…, device_class="X915S",
reason="capability_missing")` **before any network I/O** — uniformly, with
the same type and reason, satisfying FR-005/FR-006 and SC-003.

The now-obsolete `APARTMENT_BOOK` → `NotImplementedError` deferral in the
service-layer `add_contact` / `modify_contact` (`contacts.py`,
`_APARTMENT_BOOK_WRITE_DEFERRAL_MSG`) is **removed**: it predates this feature
as a write-deferral placeholder (issue #121), the gate is now authoritative,
and keeping a **different** exception type (`NotImplementedError`) at the
service layer would contradict FR-005 ("never a bare `NotImplementedError`")
and the FR-006 uniformity goal. Removing the branch makes the `schema_shape=`
kwarg on `add_contact` / `modify_contact` vestigial (it was consumed only by
that branch); it is dropped along with the `_contact_shape(ctx)` argument the
`_device_contacts.py` wrappers passed into those two functions.
`delete_contact` is already shape-agnostic and unchanged at the service layer.

### Envelope translation (FR-007)

`_http._handle_response` currently translates only the literal
`_UNSUPPORTED_MSG = "Api unsupported"` (case-sensitive membership) to
`AkuvoxUnsupportedError(message)` with no `reason`. This feature:

1. Broadens the match to also recognise the `"unsupport action"` (device
   typo) and `"unsupported action"` markers — **case-insensitively** so the
   existing `"Api unsupported"` translation is preserved (FR-007).
2. Sets `reason="envelope_unsupported"` on the raised
   `AkuvoxUnsupportedError` (a member of the closed taxonomy already
   documented in `exceptions.py`), so the envelope-level signal is
   classifiable.

This covers US2 scenario 3 (the `attempt_unknown_capability=True` opt-in or an
unrecognised device class that bypasses the static `UNSUPPORTED` gate and
reaches the device): the `"unsupport action"` envelope now surfaces as
`AkuvoxUnsupportedError(reason="envelope_unsupported")` instead of
`AkuvoxDeviceError` (FR-007/FR-012). The markers mirror the
`_ACTION_UNSUPPORTED_MARKERS` / `_API_UNSUPPORTED_MARKER` constants in
`_probe_outcomes.py`; to avoid inverting the module layering (`_http` is lower
than the probe), `_http.py` keeps its own local marker constants rather than
importing from the probe module (research.md Decision 4).

### Capability discoverability (FR-009)

No new API. Callers determine write support pre-flight via the existing
`AkuvoxDevice.capabilities` →
`status_of(Capability.CONTACT_ADD/MODIFY/DELETE)` (returns `UNSUPPORTED` on
X915S) or membership in `supported_set`. Documented in the quickstart.

### Documentation (FR-010/FR-011)

`docs/api/contacts.rst` / `README.md` gain a **device-class contact models**
section contrasting door-phone vs apartment-book (fields each carries, example
classes X916 / E18C vs X915S, the read-only-over-HTTP constraint) and the
**identifier strategy** (no device `ID`; recommended `(apt_num, phone)`
composite key with its limitations). `docs/changelog.rst` gets an `Added`
bullet (apartment-book fields) and a `Changed` bullet (uniform unsupported
write signalling + envelope translation), referencing #121.

## Project Structure

### Documentation (this feature)

```text
specs/013-apartment-book-contacts/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 — decisions, both clarifications resolved
├── data-model.md        # Phase 1 — Contact extension (the model is changing)
├── contracts/
│   ├── apartment-book-read.md     # apartment-book read contract
│   └── contact-write-rejection.md # uniform write-rejection + envelope contract
├── quickstart.md        # Phase 1 — read + pre-flight + write-rejection usage
├── checklists/
│   └── requirements.md  # (from the spec stage)
├── spec.md              # (merged spec stage)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

A standalone `data-model.md` **is** produced here (unlike the OpenDoor plan)
because this feature **changes the `Contact` domain model** — four new fields
and a parse-path behaviour change worth pinning precisely.

### Source Code (repository root) — touched by the LATER implementation PR

```text
src/pylocal_akuvox/
├── models/contacts.py       # + apt_name/apt_num/building/landline fields;
│                            #   apartment-book parse branch populates them;
│                            #   to_api_payload() UNCHANGED (FR-004)
├── capability_matrix.py     # X915S entry: + CONTACT_MODIFY/CONTACT_DELETE
│                            #   = UNSUPPORTED (only permitted matrix change)
├── _http.py                 # _handle_response: match "unsupport action" /
│                            #   "unsupported action" (case-insensitive),
│                            #   reason="envelope_unsupported"; keep
│                            #   "Api unsupported"
├── contacts.py              # remove APARTMENT_BOOK NotImplementedError
│                            #   deferral + dead schema_shape= kwarg
└── _device_contacts.py      # drop _contact_shape() pass-through into
│                            #   add/modify (gate is authoritative); list_
│                            #   contacts still threads capabilities=

tests/unit/
├── test_contacts.py         # + apartment-book parse (4 fields preserved,
│                            #   missing ID tolerated, empty-string kept);
│                            #   door-phone byte-identity regression;
│                            #   three write ops raise AkuvoxUnsupportedError
│                            #   uniformly on X915S
└── test_http.py             # + "unsupport action" envelope ->
│                            #   AkuvoxUnsupportedError(envelope_unsupported);
│                            #   "Api unsupported" still translated

docs/api/contacts.rst, README.md, docs/changelog.rst
                             # + device-class model split, identifier
                             #   strategy, read-only constraint, changelog
```

**Structure Decision**: Single Python package; the change is additive and
reconciling, confined to the contact model, the X915S matrix entry, the HTTP
envelope classifier, and a service-layer cleanup. No new module is required.

### Agent context

`update-agent-context.sh` is **not** run for this feature: it introduces no
new technology (no new runtime/test dependency, same Python, same tooling),
and recent specs (009–012) likewise did not regenerate
`.github/agents/copilot-instructions.md`. Re-running it would add only a
churn-only "Recent Changes" bullet, so it is intentionally skipped per the
workflow rule "Add only new technology from current plan".

## Phases

Phases are ordered so each lands as an atomic, independently testable commit
with a green checkpoint (targeted tests + ruff + mypy + 100% branch coverage)
before the next begins.

### Phase 1 — `Contact` model + apartment-book parse (TDD) — US1, US3

**Goal**: preserve apartment-book metadata on read; keep door-phone
byte-identical.

- Red: tests in `test_contacts.py` — (a) apartment-book parse of the
  representative X915S record exposes `apt_name`/`apt_num`/`building`/
  `landline` (empty `Building`/`Landline` preserved as `""`), `id=None`;
  (b) apartment-book parse tolerates a missing `ID`; (c) door-phone parse is
  unchanged with all four new fields `None`; (d) `to_api_payload()` for a
  door-phone `Contact` (and a `Contact` carrying apt fields) emits **no**
  apartment-book key.
- Green: add the four optional fields; populate them in the `APARTMENT_BOOK`
  branch via uncoerced `data.get(...)`; leave the door-phone branch and
  `to_api_payload()` untouched.
- Covers FR-001, FR-002, FR-003, FR-004; SC-001, SC-002, SC-005.

### Phase 2 — Matrix: uniform unsupported contact writes (TDD) — US2

**Goal**: all three mutating ops reject uniformly via the gate.

- Red: tests asserting `AkuvoxDevice.add_contact` / `modify_contact` /
  `delete_contact` on the X915S profile each raise `AkuvoxUnsupportedError`
  with `reason="capability_missing"`, the `X915S` device class, and the
  matching `CONTACT_*` capability — and that **no** network request is
  issued.
- Green: add `CONTACT_MODIFY: UNSUPPORTED` and `CONTACT_DELETE: UNSUPPORTED`
  to the `_X915S_CURRENT` matrix entry (only permitted matrix change).
- Covers FR-006, FR-012, FR-013; SC-003, SC-004.

### Phase 3 — Service cleanup: remove the deferral (TDD) — US2

**Goal**: eliminate the `NotImplementedError` path so the recognisable signal
is the only outcome.

- Red: update/replace existing `test_contacts.py` assertions that pin the
  `APARTMENT_BOOK` → `NotImplementedError` deferral; assert the gated path
  yields `AkuvoxUnsupportedError` (Phase 2) and that direct service calls no
  longer raise `NotImplementedError`.
- Green: remove the `APARTMENT_BOOK` branch + `_APARTMENT_BOOK_WRITE_DEFERRAL_MSG`
  from `contacts.add_contact` / `modify_contact`; drop the now-dead
  `schema_shape=` kwarg and the `_contact_shape(ctx)` pass-through from the
  `_device_contacts.py` add/modify wrappers (`list_contacts` keeps
  threading `capabilities=`).
- Covers FR-005, FR-006, FR-012.

### Phase 4 — Envelope translation (TDD) — US2 scenario 3

**Goal**: route `"unsupport action"` to the capability error.

- Red: tests in `test_http.py` — a POST whose envelope is
  `{"retcode":-1,"action":"unknow","message":"unsupport action"}` raises
  `AkuvoxUnsupportedError` with `reason="envelope_unsupported"`; a
  `"unsupported action"` variant likewise; the existing `"Api unsupported"`
  envelope **still** translates (now also carrying `envelope_unsupported`).
- Green: broaden `_handle_response`'s match to the action-unsupported markers
  (case-insensitive, local constants) and set `reason="envelope_unsupported"`
  on the raise; preserve the `"Api unsupported"` behaviour.
- Covers FR-007, FR-012; SC-003 (opt-in path).

### Phase 5 — Documentation (FR-010/FR-011) — US4, US5

**Goal**: device-class model split + identifier constraint.

- `docs/api/contacts.rst` / `README.md` gain the door-phone vs
  apartment-book comparison (fields, example classes, read-only-over-HTTP
  constraint) and the identifier strategy (no device `ID`; recommended
  `(apt_num, phone)` composite key + limitations). `docs/changelog.rst` gets
  `Added` + `Changed` bullets referencing #121. Model field docstrings note
  the apartment-book source keys.
- Covers FR-010, FR-011; SC-006.

### Phase boundary checkpoints

Each phase ends green: targeted pytest subset, `ruff check`, `mypy`,
`interrogate`, and `aislop ci` clean, with **100% branch coverage** on
new / changed lines. CI must pass before any manual hardware validation
against the maintainer's X915S (Constitution II/VI).

## Post-Design Re-Check (Constitution)

Re-evaluated after the phase plan:

- **I. Code Quality** — still PASS. Small, well-scoped edits; docstrings and
  type annotations on every changed symbol; no complexity growth; SPDX
  headers intact (no new source file).
- **II. TDD** — still PASS. Every phase leads with a failing test; the removed
  deferral and the broadened envelope match are both pinned before the source
  edit.
- **III. UX Consistency** — still PASS. One error type + one reason across all
  three writes; additive, keyword-only model fields; documented identifier
  rule and pre-flight pattern.
- **IV. Performance** — still PASS. No new I/O or benchmarked path.
- **V. Atomic Commits** — still PASS. Five focused phases map to atomic,
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
- `research.md` — design decisions; both clarifications resolved with rejected
  alternatives; live-source verification
- `data-model.md` — the `Contact` extension and parse-path behaviour
- `contracts/apartment-book-read.md` — apartment-book read contract
- `contracts/contact-write-rejection.md` — uniform write-rejection +
  envelope-translation contract
- `quickstart.md` — read, pre-flight capability check, and write-rejection
  usage

`tasks.md` is **not** produced by this stage (`/speckit.tasks` follows).

## Remaining [NEEDS CLARIFICATION]

Both spec markers are resolved at the design level (see "Resolved
Clarifications"): the identifier strategy is **option (c)** (expose raw
fields; documented `(apt_num, phone)` composite recommendation), and capability
signalling is **raise-only (option a)**. No [NEEDS CLARIFICATION] markers
remain for the implementation stage.
