<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Specification Quality Checklist: OpenDoor HTTP Relay Unlock

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-17
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Public API and endpoint details are limited to contract clarity
- [x] Focused on user value and business needs
- [x] Written for library integrators and maintainers
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain — **intentionally deferred** (two markers retained by design; see Notes and the spec's "Outstanding Clarifications" section)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria focus on externally visible behavior
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] Implementation-specific terms are intentional and public-facing

## Coverage of Issue #122 Acceptance Criteria

Each acceptance-criteria item from issue #122 maps to functional
requirements, scenarios, and success criteria:

| Issue #122 acceptance criterion | Spec coverage |
|---|---|
| New method exposes the documented `/fcgi/do?action=OpenDoor` endpoint | FR-001; US1 scenarios 1-3; SC-001 |
| Credentials are URL-encoded, not interpolated raw | FR-002; US2 scenario 1; SC-002 |
| Password is redacted from any logged URLs | FR-003; US2 scenarios 2-3; SC-003 |
| Docstring states clear-text trade-off and device-side prerequisite | FR-009; US3 scenario 2; Security Considerations |
| Unit tests cover URL construction, encoding, one success + one failure shape | FR-011; SC-002, SC-005 |
| `examples/mvp_test.py --write` optionally exercises it (gated flag) | FR-012; US4 scenarios 1-2 |
| Docs note on when to use `/fcgi/do?action=OpenDoor` vs `/api/relay/trig` | FR-010; US3 scenario 1; SC-006 |
| Out of scope: other `/fcgi/` commands, IT83 broader gaps, auto-detection | Out of Scope section; FR-013 |

### Reconciliation with existing codebase

This spec is **not** purely additive: the codebase already ships a
partial FCGI relay variant. The following spec elements address the
divergence raised in review:

| Existing-code reality | Spec coverage |
|---|---|
| `Capability.RELAY_TRIGGER_FCGI` + `_fcgi_relay_trigger` + IT83 matrix entry already present | Overview "not a greenfield addition" paragraph; "Existing Partial Implementation" subsection; Dependencies |
| Existing adapter sends no `UserName`/`Password` | FR-002, FR-003, FR-015 |
| Existing adapter uses `relay=<num>`, not `DoorNum` | FR-014 |
| Out-of-scope previously contradicted the present matrix entry | Corrected Out-of-Scope bullets (static matrix retained; no new probe/matrix surface) |
| Standalone method vs capability dispatch relationship | Outstanding Clarifications (2nd marker) |

## Notes

- Two [NEEDS CLARIFICATION] markers are intentionally retained (see the
  spec's "Outstanding Clarifications" section): (1) the exact
  success/failure classification of the OpenDoor response, which cannot
  be finalized without probing real IT83 hardware (the spec adopts a
  well-defined HTTP-status-based default so it does not block planning);
  and (2) the relationship between the new credentialed entry point and
  the existing capability-dispatched FCGI adapter, which materially
  affects the public API surface and is a deliberate planning decision.
  Both are deferred with well-defined defaults/constraints and neither
  blocks `/speckit.plan`.
- All other checklist items pass. Items marked incomplete require spec
  updates before `/speckit.clarify` or `/speckit.plan` only if the
  retained clarifications cannot be deferred; here they are deliberately
  deferred with documented defaults and constraints.
