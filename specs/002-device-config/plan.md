<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Device Configuration Management

**Branch**: `002-device-config` | **Date**: 2026-02-24
**Spec**: [spec.md](spec.md)

## Summary

Add device configuration get/set capabilities to pylocal-akuvox.
The endpoint `GET /api/config/get` returns all device configuration
as autop-format key-value pairs (900+ keys on real devices spanning
relay, network, SIP, display, and more). `POST /api/config/set`
updates settings. A new `DeviceConfig` frozen dataclass wraps the
full key-value dict. The existing module pattern (separate module +
device facade + TDD) is followed exactly.

**Note**: The original implementation (PR #39) incorrectly scoped
this to relay-only (`/api/relay/get`, `RelayConfig`, 6-key
`KEY_MAP`). This plan corrects that to use `/api/config/get` with
a generic `DeviceConfig` model that holds all device keys.

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
device facade methods, ~5-6 new model/module functions, ~40-60 new tests

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
| VI. Phased Development | ✅ | Phased tasks, each independently testable |

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
├── __init__.py          # Add DeviceConfig export
├── _http.py             # No changes
├── config.py            # REWRITE: get/set device config functions
├── device.py            # Rewrite config facade methods
├── models.py            # Replace RelayConfig with DeviceConfig
└── ...                  # Existing modules unchanged

tests/unit/
├── test_config.py       # REWRITE: config module unit tests
├── test_device.py       # Update config method tests
├── test_models.py       # Replace RelayConfig with DeviceConfig tests
└── ...                  # Existing tests unchanged

examples/
└── mvp_test.py          # Rewrite config read/write tests
```

**Structure Decision**: Single project layout matching existing
repository structure. New code follows the established pattern of
domain module (`config.py`) + model (`DeviceConfig` in `models.py`)

+ device facade methods + unit tests.

## Implementation Phases

### Phase 1 — Read Device Configuration (US1, FR-001, FR-002)

**Goal**: Retrieve full device configuration from a device and
return a structured `DeviceConfig` dataclass wrapping all
autop-format key-value pairs.

**Scope**:

+ Replace `RelayConfig` with `DeviceConfig` frozen dataclass in
  `models.py` with `from_api_response()`, `to_api_payload()`,
  `keys()`, `get()`, `__getitem__()`, `__contains__()`,
  `__len__()`
+ Rewrite `config.py` module: remove `KEY_MAP` and
  `reverse_key_map()`, implement `get_device_config()` using
  `/api/config/get`
+ Replace `get_relay_config()` with `get_device_config()` in
  `AkuvoxDevice`
+ Export `DeviceConfig` from `__init__.py` (replace `RelayConfig`)
+ TDD: Rewrite tests for new model and config retrieval
+ Rewrite `examples/mvp_test.py` config read test to show all keys

**FR Coverage**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008,
FR-010
**SC Coverage**: SC-001, SC-003, SC-004, SC-005, SC-006

**Acceptance**: Developer can call `device.get_device_config()` and
receive a `DeviceConfig` object containing all device keys. Live
device test reads config successfully and shows all keys.

---

### Phase 2 — Update Device Configuration (US2, FR-003, FR-004)

**Goal**: Update one or more device configuration settings on the
device.

**Scope**:

+ Add `set_device_config()` to `config.py` with validation
+ Add `set_device_config()` method to `AkuvoxDevice`
+ Validate at least one key-value pair provided (FR-004)
+ Use autop-format keys for the request (FR-009)
+ TDD: Unit tests for set operations, validation errors
+ Update `examples/mvp_test.py` with config write test

**FR Coverage**: FR-003, FR-004, FR-005, FR-009, FR-010
**SC Coverage**: SC-002, SC-003, SC-005, SC-006

**Acceptance**: Developer can call `device.set_device_config()`
with key-value pairs. Live device test writes and reads back
config to verify.

---

### Phase 3 — Discover Configuration Keys (US3, Documentation)

**Goal**: Expose available configuration keys through the read
response and provide comprehensive documentation.

**Scope**:

+ Verify `DeviceConfig.keys()` works with real device data
+ Update Sphinx API docs for new module and model
+ Final `examples/mvp_test.py` updates for key discovery test
+ Full integration verification against live device

**FR Coverage**: FR-010, FR-011
**SC Coverage**: SC-006, SC-007

**Acceptance**: Developer can inspect a `DeviceConfig` object to
discover all available configuration keys. Documentation is
complete and published.
