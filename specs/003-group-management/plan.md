<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Group Management (CRUD)

**Branch**: `003-group-management` | **Date**: 2026-07-21
**Spec**: [spec.md](spec.md)

## Summary

Add group CRUD management to pylocal-akuvox. Groups organize users
on Akuvox security devices. The library will provide async functions
to list, add, modify, and delete groups via the device's local HTTP
API. A new `Group` frozen dataclass (ID + Name only, verified via
live device testing) is added to `models.py`. A new `groups.py`
module follows the established pattern of `users.py` and
`schedules.py`. The `AkuvoxDevice` facade exposes all four group
operations. The `Group` model is exported from the package namespace.

Key simplification over user/schedule management: the group model
has only two fields (ID + Name), so modify operations send the
payload directly without a fetch-merge-write cycle. Group mutations
use separate endpoints (`/api/group/{add,set,del}`) rather than the
single-endpoint pattern used by users and schedules.

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
**Scale/Scope**: 4 endpoints (1 GET + 3 POST), 1 new model, 1 new
module, 4 new device facade methods, ~6 new module functions,
~40-50 new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1
design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Code Quality | ✅ | ruff + mypy + interrogate; C901 ≤10 |
| II. TDD | ✅ | Red-green-refactor; tests precede code |
| III. UX Consistency | ✅ | Follows `users.py`/`schedules.py` patterns |
| IV. Performance | ✅ | Async-only; no event-loop blocking |
| V. Atomic Commits | ✅ | One change per commit; DCO sign-off |
| VI. Phased Dev | ✅ | 3 phases, independently testable w/ CI |

No violations. Gate passes.

## Project Structure

### Documentation (this feature)

```text
specs/003-group-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── group-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/pylocal_akuvox/
├── __init__.py          # Add Group export
├── _http.py             # No changes
├── device.py            # Add group facade methods
├── groups.py            # NEW: group CRUD functions
├── models.py            # Add Group frozen dataclass
└── ...                  # Existing modules unchanged

tests/unit/
├── test_groups.py       # NEW: group validation + CRUD tests
├── test_device.py       # Add group facade method tests
├── test_models.py       # Add Group model tests
├── test_init.py         # Add Group export tests
└── ...                  # Existing tests unchanged

examples/
└── mvp_test.py          # Add group list/add/delete tests

docs/
├── quickstart.rst       # Add group management section
└── api/
    └── groups.rst       # NEW: groups module autodoc
```

**Structure Decision**: Single project layout matching existing
repository structure. New code follows the established pattern of
domain module (`groups.py`) + model (`Group` in `models.py`) +
device facade methods + unit tests.

## Implementation Phases

### Phase 1 — Group Model & List (US1, US5-partial)

**Goal**: Define the `Group` model and retrieve groups from the
device. This is the foundation for all other group operations.

**Scope**:

- Add `Group` frozen dataclass to `models.py` with
  `from_api_response()` and `to_api_payload()` methods
- Create `groups.py` module with `list_groups()` function
- Add `list_groups()` facade method to `AkuvoxDevice`
- Export `Group` from `__init__.py`
- TDD: Model tests (creation, parsing, missing fields, round-trip)
- TDD: List tests (populated, empty, paginated, malformed)
- TDD: Facade delegation test for list_groups

**FR Coverage**: FR-001, FR-002, FR-009, FR-011, FR-012, FR-013,
FR-014
**SC Coverage**: SC-001 (list), SC-002 (list), SC-003, SC-005

**Acceptance**: Developer can call `device.list_groups()` and
receive a list of `Group` objects. Malformed responses raise
`AkuvoxParseError`. Empty collections are returned (not errors)
for devices with no groups.

---

### Phase 2 — Group Mutations: Add, Modify, Delete (US2-US4, US5-remainder)

**Goal**: Implement create, update, and delete operations for
groups with client-side validation.

**Scope**:

- Add `add_group()` to `groups.py` with name validation
- Add `modify_group()` to `groups.py` with ID + name validation;
  no fetch-merge-write needed (only 2 fields)
- Add `delete_group()` to `groups.py` (idempotent)
- Add `add_group()`, `modify_group()`, `delete_group()` facade
  methods to `AkuvoxDevice`
- TDD: Validation tests (empty name, missing name on modify)
- TDD: CRUD operation tests (add, modify, delete)
- TDD: Device error handling tests (Ret codes)
- TDD: Facade delegation tests for all mutations

**FR Coverage**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-008,
FR-010, FR-011
**SC Coverage**: SC-001 (add/modify/delete), SC-002, SC-004, SC-006

**Acceptance**: Developer can call `device.add_group(name=...)`,
`device.modify_group(id=..., name=...)`, and
`device.delete_group(id=...)`. Validation errors are raised
before network requests. Device errors produce named exceptions.

---

### Phase 3 — Documentation & MVP Test Script (SC-002, FR-010)

**Goal**: Complete documentation and live device test coverage.

**Scope**:

- Add group management section to `docs/quickstart.rst`
- Create `docs/api/groups.rst` autodoc page
- Add groups.rst to `docs/api/index.rst` toctree
- Update `docs/index.rst` key features list
- Extend `examples/mvp_test.py` with group read tests
  (list_groups) and group write tests (add + delete under
  `--write` flag)
- Add group validation checks to `test_validation()` in
  mvp_test.py

**FR Coverage**: FR-010, FR-011
**SC Coverage**: SC-001, SC-002, SC-006

**Acceptance**: Sphinx docs build cleanly with group API
reference. `mvp_test.py --write` exercises group CRUD against
a live device. All documentation examples are accurate.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Code Quality | ✅ | Follows all patterns; C901 ≤10 |
| II. TDD | ✅ | TDD scope per phase; tests first |
| III. UX Consistency | ✅ | Same facade as users/schedules |
| IV. Performance | ✅ | No fetch-merge-write; async throughout |
| V. Atomic Commits | ✅ | Phase boundaries → clean commits |
| VI. Phased Dev | ✅ | 3 phases w/ CI; independently testable |

No violations. Gate passes.
