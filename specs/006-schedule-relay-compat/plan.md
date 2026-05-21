<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Implementation Plan: Schedule-Relay Field Compatibility for E18 Firmware

**Branch**: `006-schedule-relay-compat` | **Date**: 2025-11-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-schedule-relay-compat/spec.md`

## Summary

Akuvox E18 firmware `18.30.11.21` renamed the primary access-schedule request
field from the un-hyphenated `ScheduleRelay` to the hyphenated `Schedule-Relay`.
All add-user and modify-user operations against affected devices currently
fail with a generic `retcode: -1 / "Failed"`. The fix is to dual-write both
field names (identical values) in the outgoing request payload of
`add_user()` and `modify_user()` in `src/pylocal_akuvox/users.py`.
Secondary-relay scheduling is not exposed by the current public API and stays
out of scope; the feature must not introduce `ScheduleSRelay` or any
hyphenated secondary companion. The response-parsing path is unchanged because
all tested firmwares return the primary schedule under the un-hyphenated name.

No firmware detection or version branching is performed; the dual-write is
unconditional and backward compatible.

## Technical Context

**Language/Version**: Python 3.13.2+ (per `pyproject.toml`)
**Primary Dependencies**: `aiohttp>=3.13` (runtime); `pytest`, `pytest-asyncio`, `aioresponses` (test)
**Storage**: N/A (library only; device is the system of record)
**Testing**: pytest with `aioresponses` for HTTP stubbing; existing unit tests live in `tests/unit/`
**Target Platform**: Library consumed by async Python applications (Linux/macOS/Windows)
**Project Type**: Single Python package (`src/pylocal_akuvox/`)
**Performance Goals**: N/A — change adds one extra key to an existing dict; no measurable perf impact
**Constraints**: Backward compatible across all previously supported firmwares; no public API change; no new dependencies
**Scale/Scope**: Two functions touched (`add_user`, `modify_user`); two new unit tests minimum

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality | PASS | Adds one dict key in two functions; no new branches, no complexity increase. Existing docstrings cover behavior; minor update will note dual-key emission. Type signatures unchanged. SPDX headers already present in touched files. |
| II. Test-Driven Development | PASS | Plan adds failing unit tests in `tests/unit/test_users.py` first (FR-008 mandates them). Red → Green → Refactor cycle followed. Coverage strictly increases. |
| III. UX Consistency | PASS | Public function signatures, parameter names, return types, and error formats are unchanged (FR-005). Behavior is uniformly applied (FR-006). |
| IV. Performance | PASS | Single extra key copy per request; no benchmark needed. |
| V. Atomic Commits & Compliance | PASS | Implementation will land as a single logical commit (one fix). No new files introduced (so no new SPDX headers needed). DCO sign-off + Conventional Commits format enforced by pre-commit. |
| VI. Phased Development | PASS | Single phase: add failing tests, then implement dual-write in both functions. |

**Result**: No violations. No entries required in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/006-schedule-relay-compat/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (this command)
├── quickstart.md        # Phase 1 output (this command)
└── checklists/          # Pre-existing review checklists
```

No `data-model.md` is generated: this change introduces no new entities — it
only adds a duplicate key to an existing outgoing request payload. No
`contracts/` directory is generated: there is no public API change and no
new endpoint; the device-side contract change is documented in `research.md`.

### Source Code (repository root)

```text
src/pylocal_akuvox/
├── __init__.py          # (unchanged) re-exports public surface
├── _http.py             # AkuvoxHttpClient (unchanged)
├── auth.py              # (unchanged)
├── config.py            # (unchanged)
├── contacts.py          # (unchanged)
├── device.py            # AkuvoxDevice public facade (unchanged)
├── exceptions.py        # (unchanged)
├── groups.py            # (unchanged)
├── logs.py              # (unchanged)
├── models.py            # (unchanged)
├── relay.py             # (unchanged)
├── schedules.py         # (unchanged)
└── users.py             # MODIFIED: add_user(), modify_user()

tests/
└── unit/
    └── test_users.py    # MODIFIED: new tests for dual-key emission (FR-008)
```

The public entry point is `pylocal_akuvox.AkuvoxDevice` (from
`device.py`); there is intentionally no `client.py`. `users.py` exposes
the module-level coroutines `add_user`, `modify_user`, `list_users`,
`delete_user` that `AkuvoxDevice` delegates to.

**Structure Decision**: Existing single-package layout under `src/pylocal_akuvox/`
is retained. The change is confined to `src/pylocal_akuvox/users.py` and its
unit-test module `tests/unit/test_users.py`. No new modules, packages, or
directories are introduced.

## Phase 0: Outline & Research

All technical unknowns are resolved in [research.md](./research.md). Summary:

- **Decision**: Unconditionally dual-write the primary-relay schedule under
  both `ScheduleRelay` and `Schedule-Relay` keys in the outgoing payload,
  with identical values, on every add-user and modify-user request.
- **Rationale**: Verified empirically against firmware `18.30.11.21` (only
  hyphenated form accepted) and `916.30.10.114` (only un-hyphenated form
  accepted, hyphenated form silently ignored / harmless). Sending both
  satisfies every tested firmware with no version detection.
- **Alternatives rejected**: (a) firmware-version probing (fragile, extra
  round-trip, more code paths), (b) replacing the un-hyphenated form
  outright (breaks every older firmware), (c) adding secondary-relay
  scheduling in this fix (new API surface and unsafe hyphenated E18 behavior).

No NEEDS CLARIFICATION items remain.

## Phase 1: Design & Contracts

**Prerequisites**: `research.md` complete ✅

**Data model**: Not applicable. No new entities; no schema changes; no
storage. The only data-shape change is one extra key in the outgoing JSON
payload, fully described in `research.md` and the source diff itself.

**Contracts**: Not applicable. No public Python API change (FR-005). The
device-side request envelope shape is internal to `users.py`. The relevant
keys are documented inline below for reviewer convenience:

- Outgoing `add` payload (new shape):

  ```json
  {
    "target": "user",
    "action": "add",
    "data": {
      "item": [{
        "Name": "...", "UserID": "...",
        "ScheduleRelay": "<value>",
        "Schedule-Relay": "<same value>",
        "LiftFloorNum": "...",
        "WebRelay": "...", "PrivatePIN": "...", "CardCode": "..."
      }]
    }
  }
  ```

- Outgoing `set` (modify) payload: same dual-key treatment when
  `schedule_relay` is supplied or already present in the fetched record.

**Quickstart**: See [quickstart.md](./quickstart.md) for a minimal
integrator-facing example confirming SC-005 (zero caller code changes).

**Agent context update**: Run
`.specify/scripts/bash/update-agent-context.sh copilot` to record the
in-scope module and tech stack for downstream agent runs (executed below).

### Post-design Constitution re-check

No design changes from Phase 0 affect any gate. All six principles still
PASS. No Complexity Tracking entries required.

## Complexity Tracking

*No violations — section intentionally empty.*
