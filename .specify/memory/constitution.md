<!--
  Sync Impact Report
  ==================================================
  Version change: 0.0.0 (template) → 1.0.0
  Modified principles: N/A (initial population)
  Added sections:
    - I. Code Quality (NON-NEGOTIABLE)
    - II. Test-Driven Development (NON-NEGOTIABLE)
    - III. User Experience Consistency
    - IV. Performance Requirements
    - V. Atomic Commits & Compliance (NON-NEGOTIABLE)
    - VI. Phased Development
    - Development Workflow & Quality Gates
    - Additional Constraints
  Removed sections: None
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ aligned (Constitution Check gate)
    - .specify/templates/spec-template.md ✅ aligned (user stories + acceptance)
    - .specify/templates/tasks-template.md ✅ aligned (TDD task ordering)
    - .specify/templates/checklist-template.md ✅ aligned (generic)
    - .specify/templates/agent-file-template.md ✅ aligned (generic)
  Follow-up TODOs: None
  ==================================================
-->

# pylocal-akuvox Constitution

## Core Principles

### I. Code Quality (NON-NEGOTIABLE)

- All source code MUST pass configured linting and static analysis
  checks (ruff, mypy, interrogate) with zero errors or warnings.
- Every function and class MUST include a docstring that describes its
  purpose, parameters, return values, and raised exceptions.
- Type annotations MUST be present on all public function signatures.
- Code complexity MUST remain low; functions exceeding a cyclomatic
  complexity threshold MUST be refactored before merge.
- All new source files MUST include SPDX license headers as defined
  in `REUSE.toml`. Files missing headers MUST NOT be committed.

### II. Test-Driven Development (NON-NEGOTIABLE)

- Development MUST follow TDD best practices: tests are written
  **before** the production code they verify.
- The Red-Green-Refactor cycle is strictly enforced:
  1. Write a failing test that defines the desired behavior.
  2. Implement the minimum code required to make the test pass.
  3. Refactor while keeping all tests green.
- Tests for a development phase MUST be written during that phase or
  a subsequent phase — they are NOT required to be written all up
  front.
- CI tests MUST pass before any manual or exploratory testing is
  performed. Manual testing without green CI is prohibited.
- Test coverage MUST be maintained or increased with every change;
  coverage regressions MUST be justified and approved.

### III. User Experience Consistency

- Public APIs and user-facing interfaces MUST follow consistent
  naming conventions, error formats, and response structures.
- Error messages MUST be actionable: they MUST describe what went
  wrong and suggest corrective steps where feasible.
- Breaking changes to public interfaces MUST be documented, versioned,
  and communicated before release.
- Configuration surfaces MUST use sensible defaults so that minimal
  setup is required for common use cases.

### IV. Performance Requirements

- Performance-sensitive paths MUST have defined benchmarks with
  measurable acceptance thresholds documented in the feature spec.
- Regressions against established benchmarks MUST block merge until
  resolved or explicitly justified.
- Resource consumption (memory, CPU, I/O) MUST be considered during
  design; implementations that exceed stated constraints MUST be
  refactored.
- Asynchronous operations MUST NOT block the event loop; blocking
  calls MUST be offloaded to executor threads.

### V. Atomic Commits & Compliance (NON-NEGOTIABLE)

- Every commit MUST represent exactly one logical change (one feature,
  one fix, or one refactor).
- All commits MUST include SPDX license headers on new files and MUST
  carry a DCO sign-off (`git commit -s`).
- Pre-commit hooks MUST pass on every commit. Bypassing hooks with
  `--no-verify` is **PROHIBITED** under all circumstances.
- Commit messages MUST follow Conventional Commits with capitalized
  types as defined in `AGENTS.md`.

### VI. Phased Development

- Development MUST proceed in defined phases; each phase delivers an
  independently testable increment of functionality.
- Tests for a phase MUST be written during that phase or a later
  phase, not all up front. This allows requirements to stabilize
  before tests are locked in.
- Each phase MUST conclude with a checkpoint where all CI tests pass
  and the increment is validated before the next phase begins.
- Phase boundaries MUST be documented in the implementation plan
  (`plan.md`) and task list (`tasks.md`).

## Additional Constraints

- **Language & Runtime**: Python 3.x with full type annotation
  coverage enforced by mypy.
- **Dependency Management**: Dependencies MUST be managed via `uv`
  with a locked dependency file (`uv.lock`) committed to the
  repository.
- **License Compliance**: The project follows the REUSE specification.
  Every file MUST be covered by an SPDX header or an entry in
  `REUSE.toml`.
- **Security**: Secrets MUST NOT be committed to source control.
  Credentials MUST be injected via environment variables or secret
  management tooling.

## Development Workflow & Quality Gates

1. **Write tests** for the current phase or story (TDD red phase).
2. **Implement** the minimum code to pass those tests (TDD green).
3. **Refactor** while keeping all tests green.
4. **Run linting & type checks** locally (`ruff`, `mypy`).
5. **Stage and commit** atomically with sign-off and SPDX headers.
6. **Pre-commit hooks** run automatically — fix any failures and
   re-commit (do NOT reset; do NOT bypass).
7. **CI pipeline** MUST pass. No manual or exploratory testing is
   permitted until CI is green.
8. **Manual validation** may proceed only after CI confirms all
   automated checks pass.

## Governance

- This constitution supersedes all other development practices. In
  case of conflict, this document prevails.
- Amendments MUST be documented with a version bump, rationale, and
  migration plan if existing code is affected.
- Version increments follow semantic versioning:
  - **MAJOR**: Backward-incompatible principle removals or
    redefinitions.
  - **MINOR**: New principles or materially expanded guidance.
  - **PATCH**: Clarifications, wording, or non-semantic refinements.
- All pull requests and code reviews MUST verify compliance with
  these principles. Non-compliance MUST block merge.
- Use `AGENTS.md` for runtime development guidance that supplements
  this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-02-13 | **Last Amended**: 2026-02-13
