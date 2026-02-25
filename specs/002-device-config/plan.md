<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Device Configuration Management

**Branch**: `002-device-config` | **Date**: 2026-02-24
**Spec**: [spec.md](spec.md)

## Summary

Add relay configuration get/set capabilities to pylocal-akuvox. The
library already supports relay triggering and status queries; this
feature extends it with `GET /api/relay/get` (read all relay settings)
and `POST /api/relay/set` (update settings using autop-format keys).
A new `RelayConfig` dataclass maps device keys to developer-friendly
attributes. The existing module pattern (separate module + device
facade + TDD) is followed exactly.

## Technical Context

**Language/Version**: Python ≥3.13.2, fully type-annotated (mypy
strict)
**Primary Dependencies**: aiohttp ≥3.13 (async HTTP)
**Storage**: N/A (device API only)
**Testing**: pytest + pytest-asyncio + aioresponses, 100% coverage
**Target Platform**: Linux / any Python 3.13.2+ environment
  (note: spec 001 referenced Python 3.14; the project now
  requires ≥3.13.2 per pyproject.toml)
**Project Type**: Single Python package
**Performance Goals**: Standard LAN latency; must not block event loop
**Constraints**: Async-only; per-device lock serialization; ≤10
cyclomatic complexity per function (ruff C901)
**Scale/Scope**: 2 new endpoints, 1 new model, 1 new module, 2 new
device facade methods, ~4 new model/module functions, ~40-60 new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1
design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Code Quality | ✅ | ruff + mypy + interrogate; C901 ≤10 |
| II. TDD | ✅ | Red-green-refactor per phase |
| III. UX Consistency | ✅ | Follows existing `device.py` facade |
| IV. Performance | ✅ | Async; no event-loop blocking |
| V. Atomic Commits | ✅ | One logical change per commit |
| VI. Phased Development | ✅ | 5 task phases, each independently testable |

No violations. Gate passes.

## Project Structure

### Documentation (this feature)

```text
specs/002-device-config/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 0 output (all phases)
├── contracts/           # Phase 1 output
│   └── relay-config-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/pylocal_akuvox/
├── __init__.py          # Add RelayConfig export
├── _http.py             # No changes
├── config.py            # NEW: get/set relay config functions
├── device.py            # Add config facade methods
├── models.py            # Add RelayConfig dataclass
└── ...                  # Existing modules unchanged

tests/unit/
├── test_config.py       # NEW: config module unit tests
├── test_device.py       # Extend with config method tests
├── test_models.py       # Extend with RelayConfig tests
└── ...                  # Existing tests unchanged

examples/
└── mvp_test.py          # Extend with config read/write tests
```

**Structure Decision**: Single project layout matching existing
repository structure. New code follows the established pattern of
domain module (`config.py`) + model (`RelayConfig` in `models.py`)

+ device facade methods + unit tests.

## Implementation Phases

### Phase 1 — Read Relay Configuration (US1, FR-001, FR-002)

**Goal**: Retrieve relay configuration from a device and return a
structured `RelayConfig` dataclass.

**Scope**:

+ Add `RelayConfig` frozen dataclass to `models.py` with
  `from_api_response()` class method
+ Create `config.py` module with `get_relay_config()` function
+ Add `get_relay_config()` method to `AkuvoxDevice`
+ Export `RelayConfig` from `__init__.py`
+ TDD: Unit tests for model parsing and config retrieval
+ Update `examples/mvp_test.py` with relay config read test

**FR Coverage**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008,
FR-010
**SC Coverage**: SC-001, SC-003, SC-004, SC-005, SC-006

**Acceptance**: Developer can call `device.get_relay_config()` and
receive a `RelayConfig` object. Live device test reads config
successfully.

---

### Phase 2 — Update Relay Configuration (US2, FR-003, FR-004)

**Goal**: Update one or more relay configuration settings on the
device.

**Scope**:

+ Add `set_relay_config()` to `config.py` with validation
+ Add `set_relay_config()` method to `AkuvoxDevice`
+ Validate at least one key-value pair provided (FR-004)
+ Use autop-format keys for the request (FR-009)
+ TDD: Unit tests for set operations, validation errors
+ Update `examples/mvp_test.py` with relay config write test

**FR Coverage**: FR-003, FR-004, FR-005, FR-009, FR-010
**SC Coverage**: SC-002, SC-003, SC-005, SC-006

**Acceptance**: Developer can call `device.set_relay_config()`
with key-value pairs. Live device test writes and reads back
config to verify.

---

### Phase 3 — Discover Configuration Keys (US3, Documentation)

**Goal**: Expose available configuration keys through the read
response and provide comprehensive documentation.

**Scope**:

+ Add key-listing helper to `RelayConfig` (e.g., `keys()` or
  attribute introspection)
+ Ensure all model attributes map to documented autop-format keys
+ Update Sphinx API docs for new module and model
+ Final `examples/mvp_test.py` updates for key discovery test
+ Full integration verification against live device

**FR Coverage**: FR-010, FR-011
**SC Coverage**: SC-006, SC-007

**Acceptance**: Developer can inspect a `RelayConfig` object to
discover all available configuration keys. Documentation is
complete and published.
