<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Input**: Design documents from `/specs/005-request-delay/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Unit-level tests are MANDATORY per the project constitution (Principle II: TDD). Tests are written first and must FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/pylocal_akuvox/`
- **Tests**: `tests/unit/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No project initialization needed — this feature modifies an existing codebase. This phase covers branch and test infrastructure preparation.

- [ ] T001 Create feature branch `005-request-delay` from main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the `_post_request_delay()` helper method and `request_delay` parameter validation to `AkuvoxHttpClient` — all user stories depend on this infrastructure.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T002 [P] Write test for `ValueError` on negative `request_delay` in `tests/unit/test_http.py`
- [ ] T003 [P] Write test that `_post_request_delay()` calls `asyncio.sleep` when delay > 0 in `tests/unit/test_http.py`
- [ ] T004 [P] Write test that `_post_request_delay()` does NOT call `asyncio.sleep` when delay == 0.0 in `tests/unit/test_http.py`

### Implementation for Foundational Phase

- [ ] T005 Add `request_delay` keyword-only parameter to `AkuvoxHttpClient.__init__` with default 0.25, validate non-negative, store as `self._request_delay` in `src/pylocal_akuvox/_http.py`
- [ ] T006 Implement `async def _post_request_delay(self) -> None` helper with zero-skip optimization in `src/pylocal_akuvox/_http.py`

**Checkpoint**: Foundation ready — `_post_request_delay` exists and is validated but not yet called from `get()`/`post()`

---

## Phase 3: User Story 1 — Default Delay Protects Device (Priority: P1) 🎯 MVP

**Goal**: Automatically pause 0.25s between consecutive successful requests to prevent device lockup during batch operations.

**Independent Test**: Issue multiple sequential requests through the HTTP client and verify a 0.25s pause occurs between each successful response and the next request being sent.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T007 [P] [US1] Write test that two sequential successful requests have ~0.25s delay between them (default settings) in `tests/unit/test_http.py`
- [ ] T008 [P] [US1] Write test that a single request is sent immediately with no pre-request delay in `tests/unit/test_http.py`
- [ ] T009 [P] [US1] Write test that five sequential requests each have ~0.25s delay after the previous success in `tests/unit/test_http.py`

### Implementation for User Story 1

- [ ] T010 [US1] Call `await self._post_request_delay()` after successful `_request()` in `get()` method, inside the lock in `src/pylocal_akuvox/_http.py`
- [ ] T011 [US1] Call `await self._post_request_delay()` after successful `_request()` in `post()` method, inside the lock in `src/pylocal_akuvox/_http.py`

**Checkpoint**: Default delay behavior works — sequential requests pause 0.25s between successes. User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 — Consumer Configures Custom Delay (Priority: P2)

**Goal**: Allow consumers to configure a custom delay value (including 0.0 for no delay) and propagate through `AkuvoxDevice`.

**Independent Test**: Create HTTP client and device instances with different delay values and verify the actual pause matches the configured value.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US2] Write test that `request_delay=0.5` produces ~0.5s pause between sequential requests in `tests/unit/test_http.py`
- [ ] T013 [P] [US2] Write test that `request_delay=0.0` produces no pause (backward-compatible) in `tests/unit/test_http.py`
- [ ] T014 [P] [US2] Write test that `AkuvoxDevice` accepts `request_delay` parameter and passes it to `AkuvoxHttpClient` in `tests/unit/test_device.py`

### Implementation for User Story 2

- [ ] T015 [US2] Add `request_delay` keyword-only parameter to `AkuvoxDevice.__init__` with default 0.25 and pass through to `AkuvoxHttpClient` in `src/pylocal_akuvox/device.py`

**Checkpoint**: Custom delay values work end-to-end through both `AkuvoxHttpClient` and `AkuvoxDevice`. Zero delay restores pre-feature behavior.

---

## Phase 5: User Story 3 — Delay Skipped on Errors (Priority: P3)

**Goal**: Ensure the inter-request delay is skipped when a request fails, so errors are reported immediately.

**Independent Test**: Issue a request that results in an error and verify no inter-request delay occurs.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T016 [P] [US3] Write test that no delay occurs when a request raises `AkuvoxConnectionError` in `tests/unit/test_http.py`
- [ ] T017 [P] [US3] Write test that after a failed request, a subsequent successful request DOES apply the delay in `tests/unit/test_http.py`

### Implementation for User Story 3

No implementation changes needed — the exception propagation in `_request()` naturally skips the `_post_request_delay()` call (placed after the `_request()` return). This phase validates that the existing control flow is correct.

- [ ] T018 [US3] Verify and document that exception propagation in `get()` and `post()` bypasses `_post_request_delay()` — add inline comment in `src/pylocal_akuvox/_http.py`

**Checkpoint**: All three user stories are independently functional. Error paths skip delay, success paths apply delay.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, docstring updates, and final validation

- [ ] T019 [P] Update `AkuvoxHttpClient.__init__` docstring to document `request_delay` parameter in `src/pylocal_akuvox/_http.py`
- [ ] T020 [P] Update `AkuvoxDevice.__init__` docstring to document `request_delay` parameter in `src/pylocal_akuvox/device.py`
- [ ] T021 Run full test suite and verify all tests pass with `uv run pytest tests/`
- [ ] T022 Run linting and type checking with `uv run ruff check src/ tests/` and `uv run mypy src/`
- [ ] T023 Run quickstart.md validation scenarios manually or as integration smoke tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion (independent of US1 for HTTP client; device test depends on US1 integration being complete)
- **User Story 3 (Phase 5)**: Depends on Phase 3 (needs delay call in get/post to validate error bypass)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — Device wrapper (T015) is independent work; test T014 validates passthrough
- **User Story 3 (P3)**: Depends on US1 completion (needs `_post_request_delay()` wired into `get()`/`post()` to validate skip behavior)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundational infrastructure before behavior
- Behavior before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T003, T004 can all run in parallel (independent test cases)
- T007, T008, T009 can all run in parallel (US1 tests)
- T010, T011 can NOT run in parallel (same methods in same file, but logically independent edits)
- T012, T013, T014 can all run in parallel (US2 tests, different scenarios)
- T016, T017 can run in parallel (US3 tests)
- T019, T020 can run in parallel (different files)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Write test for two sequential requests with default delay in tests/unit/test_http.py"
Task: "Write test for single request with no added delay in tests/unit/test_http.py"
Task: "Write test for five sequential requests with delay in tests/unit/test_http.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (branch)
2. Complete Phase 2: Foundational (parameter + helper method)
3. Complete Phase 3: User Story 1 (wire delay into get/post)
4. **STOP and VALIDATE**: Test US1 independently — sequential requests show 0.25s delay
5. This alone delivers the core value: device protection during batch operations

### Incremental Delivery

1. Complete Setup + Foundational → Parameter accepted, helper ready
2. Add User Story 1 → Default delay works → MVP delivers device protection
3. Add User Story 2 → Custom delay + Device wrapper → Full configurability
4. Add User Story 3 → Validate error bypass → Complete feature
5. Polish → Docs, lint, type-check → Ready for merge

---

## Notes

- All delay timing tests should use `unittest.mock.patch` on `asyncio.sleep` to avoid real waits
- Performance tests (SC-002, SC-003) may optionally use real timing with tolerance assertions
- The feature modifies only 2 source files: `_http.py` and `device.py`
- Existing tests must continue to pass — consider adding `request_delay=0.0` to existing test fixtures if default delay causes timing issues
