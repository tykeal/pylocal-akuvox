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

- [ ] No [NEEDS CLARIFICATION] markers remain
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

## Notes

- One [NEEDS CLARIFICATION] marker is intentionally retained (see the
  spec's "Outstanding Clarifications" section): the exact
  success/failure classification of the OpenDoor response cannot be
  finalized without probing real IT83 hardware. The spec adopts a
  well-defined HTTP-status-based default (2xx success / non-2xx failure)
  so the marker does not block planning; it flags a rule that must be
  confirmed or tightened against a real device during implementation.
- All other checklist items pass. Items marked incomplete require spec
  updates before `/speckit.clarify` or `/speckit.plan` only if the
  retained clarification cannot be deferred; here it is deliberately
  deferred with a documented default.
