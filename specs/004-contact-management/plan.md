<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Contact Management (CRUD with Group Membership)

**Branch**: `004-contact-management` | **Date**: 2026-07-22
**Spec**: [spec.md](spec.md)

## Summary

Add contact CRUD management (address book / directory entries) to
pylocal-akuvox. Contacts are distinct from users — they represent
directory entries with name, phone, and group assignment. The library
will provide async functions to list, add, modify, and delete contacts
via the device's local HTTP API. A new `Contact` frozen dataclass
(ID, Name, Phone, Group — verified via live device testing) is added
to `models.py`. A new `contacts.py` module follows the established
`users.py` single-endpoint pattern: `GET /api/contact/get` for
retrieval and `POST /api/contact/set` with action routing for all
mutations. The `AkuvoxDevice` facade exposes all four contact
operations. The `Contact` model is exported from the package namespace.

Key differences from group management (003):

- **4 fields** vs 2: Contact has ID, Name, Phone, Group
- **Fetch-merge-write needed** for modify: the device requires Name on
  every set request, matching the user modify pattern
- **Single mutation endpoint** (`/api/contact/set`) with action routing,
  matching users — not separate endpoints like groups
- **Group field is writable** on contacts (unlike users where Group is
  read-only), enabling group membership management
- **Batch delete support**: multiple contact IDs per request
- **Delete is NOT idempotent**: non-existent ID returns error (unlike
  groups)

## Technical Context

**Language/Version**: Python ≥3.13.2, fully type-annotated (mypy
strict)
**Primary Dependencies**: aiohttp ≥3.13 (async HTTP)
**Storage**: N/A (device API only)
**Testing**: pytest + pytest-asyncio + aioresponses, 100% coverage
**Target Platform**: Linux / any Python 3.13.2+ environment
**Project Type**: Single Python package
**Performance Goals**: Standard LAN latency; must not block event loop
**Constraints**: Async-only; per-device lock serialization; ≤10
cyclomatic complexity per function (ruff C901)
**Scale/Scope**: 2 endpoints (1 GET + 1 POST with action routing),
1 new model, 1 new module, 5 new device facade methods, ~7 new module
functions, ~45-55 new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1
design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Code Quality | ✅ | ruff + mypy + interrogate; C901 ≤10 |
| II. TDD | ✅ | Red-green-refactor; tests precede code |
| III. UX Consistency | ✅ | Follows `users.py` single-endpoint pattern |
| IV. Performance | ✅ | Async-only; no event-loop blocking |
| V. Atomic Commits | ✅ | One change per commit; DCO sign-off |
| VI. Phased Dev | ✅ | 3 phases, independently testable w/ CI |

No violations. Gate passes.

## Project Structure

### Documentation (this feature)

```text
specs/004-contact-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── contact-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/pylocal_akuvox/
├── __init__.py          # Add Contact export
├── _http.py             # No changes
├── device.py            # Add contact facade methods
├── contacts.py          # NEW: contact CRUD functions
├── models.py            # Add Contact frozen dataclass
└── ...                  # Existing modules unchanged

tests/unit/
├── test_contacts.py     # NEW: contact validation + CRUD tests
├── test_device.py       # Add contact facade method tests
├── test_models.py       # Add Contact model tests
├── test_init.py         # Add Contact export tests
└── ...                  # Existing tests unchanged

examples/
└── mvp_test.py          # Add contact CRUD tests

docs/
├── quickstart.rst       # Add contact management section
└── api/
    └── contacts.rst     # NEW: contacts module autodoc
```

**Structure Decision**: Single project layout matching existing
repository structure. New code follows the established pattern of
domain module (`contacts.py`) + model (`Contact` in `models.py`) +
device facade methods + unit tests. Uses the `users.py`
single-endpoint pattern (not the `groups.py` separate-endpoint
pattern) because the contact API routes all mutations through
`/api/contact/set`.

## Implementation Phases

### Phase 1 — Contact Model & List (US1, US5-partial)

**Goal**: Define the `Contact` model and retrieve contacts from the
device. This is the foundation for all other contact operations.

**Scope**:

- Add `Contact` frozen dataclass to `models.py` with
  `from_api_response()` and `to_api_payload()` methods
- Create `contacts.py` module with `list_contacts()` function and
  private `_mutation_body()` helper
- Add `list_contacts()` facade method to `AkuvoxDevice`
- Export `Contact` from `__init__.py`
- TDD: Model tests (creation, parsing, missing fields, round-trip,
  optional phone/group defaults)
- TDD: List tests (populated, empty, paginated, malformed, non-list
  item field)
- TDD: Facade delegation test for list_contacts

**FR Coverage**: FR-001, FR-002, FR-014, FR-016, FR-017, FR-018,
FR-019
**SC Coverage**: SC-001 (list), SC-002 (list), SC-003, SC-005

**Acceptance**: Developer can call `device.list_contacts()` and
receive a list of `Contact` objects. Malformed responses raise
`AkuvoxParseError`. Empty collections are returned (not errors)
for devices with no contacts.

---

### Phase 2 — Contact Mutations: Add, Modify, Delete (US2-US4, US5-remainder)

**Goal**: Implement create, update, and delete operations for
contacts with client-side validation and fetch-merge-write for modify.

**Scope**:

- Add `add_contact()` to `contacts.py` with name validation; optional
  phone and group parameters
- Add `_get_contact_by_id()` private helper to fetch a single contact
  by ID across pages (matching `_get_user_by_id()` pattern)
- Add `modify_contact()` to `contacts.py` with fetch-merge-write
  pattern; validates at least one field is changed
- Add `delete_contact()` to `contacts.py` supporting single and batch
  deletion
- Add `add_contact()`, `modify_contact()`, `delete_contact()` facade
  methods to `AkuvoxDevice`
- TDD: Add tests (success, name-only, all fields, empty name
  validation, device error)
- TDD: Modify tests (name change, group change, phone change, multi-
  field update, non-existent ID, no-change validation,
  fetch-merge-write envelope verification)
- TDD: Delete tests (single success, batch success, non-existent ID
  error)
- TDD: Facade delegation tests for all mutations

**FR Coverage**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-008,
FR-009, FR-010, FR-011, FR-012, FR-013, FR-015, FR-016
**SC Coverage**: SC-001 (add/modify/delete), SC-002, SC-004, SC-006,
SC-007

**Acceptance**: Developer can call `device.add_contact(name=...)`,
`device.modify_contact(id=..., group=...)`, and
`device.delete_contact(id=...)`. Validation errors are raised
before network requests. The modify operation uses fetch-merge-write
to ensure Name is always present. Group membership changes work via
a single modify call. Device errors produce named exceptions.

---

### Phase 3 — Documentation & MVP Test Script (SC-002, FR-015)

**Goal**: Complete documentation and live device test coverage.

**Scope**:

- Add contact management section to `docs/quickstart.rst`
- Create `docs/api/contacts.rst` autodoc page
- Add contacts.rst to `docs/api/index.rst` toctree
- Update `docs/index.rst` key features list
- Extend `examples/mvp_test.py` with contact read tests
  (list_contacts) and contact write tests (add + modify + delete
  under `--write` flag)
- Add contact validation checks to `test_validation()` in
  mvp_test.py

**FR Coverage**: FR-015
**SC Coverage**: SC-001, SC-002, SC-006

**Acceptance**: Sphinx docs build cleanly with contact API
reference. `mvp_test.py --write` exercises contact CRUD against
a live device including group membership changes. All documentation
examples are accurate.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Code Quality | ✅ | Follows all patterns; C901 ≤10 |
| | | `_get_contact_by_id` reuses pagination |
| | | loop from users |
| II. TDD | ✅ | TDD scope per phase; tests first |
| III. UX Consistency | ✅ | Same facade pattern as users/groups |
| | | group membership via modify |
| IV. Performance | ✅ | Fetch-merge-write adds 1 round-trip |
| | | only for modify (same as users); async |
| | | throughout |
| V. Atomic Commits | ✅ | Phase boundaries → clean commits |
| VI. Phased Dev | ✅ | 3 phases w/ CI; independently testable |

No violations. Gate passes.
