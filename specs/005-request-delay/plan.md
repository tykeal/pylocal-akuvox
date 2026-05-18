<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Branch**: `005-request-delay` | **Date**: 2025-07-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-request-delay/spec.md`

## Summary

Add a configurable inter-request delay to `AkuvoxHttpClient` that pauses for a default of 0.25 seconds after each successful HTTP response before releasing the serialization lock. This protects resource-constrained Akuvox intercom devices from being overwhelmed during batch operations. The delay is configurable (including 0.0 for no delay), skipped on errors, and propagated through the `AkuvoxDevice` wrapper.

## Technical Context

**Language/Version**: Python ≥3.13.2
**Primary Dependencies**: aiohttp ≥3.13
**Storage**: N/A
**Testing**: pytest + pytest-asyncio + aioresponses
**Target Platform**: Linux / any platform with Python 3.13+
**Project Type**: Single Python library
**Performance Goals**: `request_delay=0.0` must add <1ms latency; default 0.25s must be within ±10% (SC-002, SC-003)
**Constraints**: Must not block the event loop (uses `asyncio.sleep`); no breaking API changes (FR-010)
**Scale/Scope**: Two files modified (`_http.py`, `device.py`), one test file added/extended

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality | ✅ PASS | New parameter has type annotation; docstrings will be updated; complexity stays well under C901 limit |
| II. Test-Driven Development | ✅ PASS | Plan requires TDD red-green-refactor for each acceptance scenario |
| III. User Experience Consistency | ✅ PASS | `request_delay` uses sensible default (0.25s); existing API unchanged; negative values produce clear error |
| IV. Performance Requirements | ✅ PASS | SC-002/SC-003 define measurable thresholds; `asyncio.sleep` is non-blocking |
| V. Atomic Commits & Compliance | ✅ PASS | Feature is a single logical change; SPDX headers already present on modified files |
| VI. Phased Development | ✅ PASS | Single phase sufficient for this feature's scope |

**Gate result**: PASS — no violations, no complexity justification needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-request-delay/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/pylocal_akuvox/
├── _http.py             # AkuvoxHttpClient — add request_delay parameter & sleep logic
└── device.py            # AkuvoxDevice — pass request_delay through to HTTP client

tests/unit/
└── test_http.py         # Add/extend tests for delay behavior
```

**Structure Decision**: Single Python library project. Changes are localized to the HTTP client layer (`_http.py`) and its device wrapper (`device.py`). Tests extend the existing `tests/unit/test_http.py`.

## Complexity Tracking

> No violations — table not applicable.
