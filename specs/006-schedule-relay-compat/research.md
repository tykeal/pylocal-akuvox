<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Phase 0 Research: Schedule-Relay Field Compatibility

**Feature**: 006-schedule-relay-compat
**Date**: 2025-11-14

## Unknowns from Technical Context

None. Language, runtime, dependencies, testing framework, project structure,
and target platform are all already established in the repository
(`pyproject.toml`, `ruff.toml`, existing `tests/unit/`). The change is a
behaviorally-scoped fix to two functions inside an existing module.

## Decision 1: Dual-write the primary-relay schedule field

**Decision**: In the outgoing payload of both `add_user()` and
`modify_user()` in `src/pylocal_akuvox/users.py`, include the primary
access-schedule value under **both** keys:

- `ScheduleRelay` (existing, un-hyphenated)
- `Schedule-Relay` (new, hyphenated)

with **identical values**. Apply unconditionally — no firmware probing.

**Rationale**:

- Akuvox E18 firmware `18.30.11.21` (issue #99) only recognizes the
  hyphenated form; requests sent with only the un-hyphenated form fail with
  `retcode: -1, "Failed"`.
- All previously supported firmwares (e.g., X916 `916.30.10.114`) only
  recognize the un-hyphenated form; the hyphenated form is silently ignored
  (harmless) on those devices.
- Sending both keys with the same value is therefore correct on every
  tested firmware: the device picks up whichever name it understands, and a
  hypothetical future firmware that understands both will see consistent
  values (FR-007, edge cases).
- On read, every tested firmware returns the value under the un-hyphenated
  name only, so the response-parsing path requires no change (FR-004).

**Alternatives considered**:

1. **Probe firmware version and branch**. Rejected: introduces an extra
   request, more code paths, and a maintenance burden every time Akuvox
   ships new firmware. Violates FR-006 (no version-conditional branching).
2. **Replace `ScheduleRelay` with `Schedule-Relay` outright**. Rejected:
   instantly breaks every previously supported firmware in the field. Fails
   SC-002 and User Story 2.
3. **Send only the hyphenated form going forward and document the break**.
   Rejected: same problem as #2, plus violates the "zero caller code
   changes" success criterion (SC-005) for users on old firmware.

## Decision 2: Keep secondary-relay scheduling out of scope

**Decision**: Do not add `ScheduleSRelay`, `Schedule-SRelay`, or any other
secondary-relay request key as part of this primary-relay compatibility fix.

**Rationale**:

- The current library API exposes the primary-relay schedule only; adding a
  secondary-relay schedule would be a separate public API change.
- Empirical testing on E18 `18.30.11.21` showed a hyphenated secondary-relay
  field is *silently accepted but discards the value* — i.e., the device
  returns success but stores an empty schedule. This makes an accidental
  symmetric dual-write unsafe.

**Alternatives considered**:

1. **Symmetric dual-write for both relays**. Rejected: would introduce new API
   scope and risks data loss on the affected firmware.
2. **Wait for upstream firmware fix before shipping**. Rejected: blocks
   integrators indefinitely on a regression that has a safe workaround.

## Decision 3: Test strategy

**Decision**: Add unit tests in `tests/unit/test_users.py` that intercept
the HTTP `post` call and assert on the request payload's `item[0]` dict:

- `add_user` test: assert both `ScheduleRelay` and `Schedule-Relay` are
  present with identical values; assert no secondary-relay request key is
  introduced.
- `modify_user` test: same assertions on the modified payload after a
  schedule update.

**Rationale**: FR-008 explicitly mandates automated tests for this
behavior. Unit tests at the HTTP-payload boundary are the cheapest way to
lock in the dual-write contract without requiring a live device. They
follow the same shape as existing tests in `tests/unit/test_users.py`,
which already use `aioresponses` / mocked HTTP clients.

**Alternatives considered**:

1. **Integration tests against a live device**. Out of scope for CI; the
   firmware matrix lives only in the maintainer's lab. Acceptance scenarios
   in the spec remain the manual sign-off path for SC-001 through SC-004.

## Resolved NEEDS CLARIFICATION

None. The spec, prior issue, and source code together define every
relevant detail.
