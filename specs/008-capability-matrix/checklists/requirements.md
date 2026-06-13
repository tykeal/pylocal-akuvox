<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Specification Quality Checklist: Device Capability Probe, Capabilities Matrix, and Capability-Aware API Surfacing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Coverage of Issue #123 Acceptance Criteria

The 10 acceptance-criteria items in issue #123 each map to one or more functional requirements and success criteria:

- [x] AC1 — `Capability` enum covering current operations → FR-001
- [x] AC2 — `DeviceCapabilities` dataclass with capability set, field aliases, schema variants, quirks, provenance → FR-002
- [x] AC3 — `await device.probe_capabilities()` non-destructive, idempotent, side-effect-free → FR-003, FR-005, SC-001, SC-002
- [x] AC4 — Built-in matrix covering X916, X915S current, E18C current, IT83, with provenance → FR-006, FR-007, SC-004
- [x] AC5 — Operations raise `AkuvoxUnsupportedError` with structured info → FR-010, FR-011, SC-005
- [x] AC6 — Relay-trigger adapter dispatch (`/api/relay/trig` vs. `/fcgi/do?action=OpenDoor`) → FR-012, SC-006
- [x] AC7 — Field-name aliasing for user.schedule and contact schema driven by capability record → FR-014, FR-015
- [x] AC8 — `examples/mvp_test.py` runs probe first and skips unsupported steps → FR-019, SC-010
- [x] AC9 — Documentation: device support matrix page kept in sync → FR-018, SC-009
- [x] AC10 — Tests: probe behavior against mocked responses for each device class → FR-020

## Edge Case Coverage

- [x] `"No handlers for this request"` typo is recognized → FR-004
- [x] `"unsupported action"` is distinguished from "endpoint missing" → FR-004, edge cases section
- [x] HTTP 500 is recorded but not classified as supported/unsupported → FR-004
- [x] HTTP 401/403 aborts probe with auth error rather than partial report → FR-004
- [x] Provenance staleness path documented (firmware update invalidating entries) → FR-007, edge cases section
- [x] Unknown-device first contact behavior is conservative → FR-013
- [x] Probe-vs-matrix precedence is defined (probe wins) → FR-009

## Phasing Coverage

- [x] Phase 1 (probe) maps to User Story 1 (P1) and FR-001..FR-005
- [x] Phase 2 (matrix + dispatch + Unsupported) maps to User Story 2 (P1) and FR-006..FR-013
- [x] Phase 3 (refactor) maps to User Story 3 (P2) and FR-014..FR-017
- [x] Phase 4 (docs + mvp) maps to User Story 4 (P3) and FR-018..FR-020
- [x] Each phase is independently shippable per issue #123

## Notes

- All checklist items pass on initial draft; no `[NEEDS CLARIFICATION]` markers were introduced.
- The spec deliberately surfaces the `AkuvoxUnsupportedError` class name and the `probe_capabilities()` method name because they are part of the public API contract this feature commits to. It does not specify internal class structure, file layout, or implementation strategy beyond the cross-cutting `capabilities.py` location dictated by spec 007's merged data-model note.
- Matrix entry shape and the `DeviceClassPattern` form are described at the entity level, leaving concrete dataclass design to the planning phase.
- Out-of-scope items are taken verbatim from issue #123.
- Items marked incomplete (none in this iteration) would require spec updates before `/speckit.clarify` or `/speckit.plan`.
