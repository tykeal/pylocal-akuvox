<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Agent Development Guidelines

This document codifies git and development practices for AI agents working on
this repository. These practices are derived from the project constitution and
established development conventions.

## Constitution

If `.specify/memory/constitution.md` exists in this repository, read it and
follow its principles. The constitution takes precedence over this file if
there is any conflict between the two documents.

## Git Commit Requirements

### Commit Message Format

Use **Conventional Commits** with **capitalized types**:

```plaintext
Type(scope): Short description

Optional body with more details. Wrap at 80 characters.

Co-Authored-By: <AI Model Name> <appropriate-email@provider.com>
```

**Allowed types** (capitalized):

- `Fix` - Bug fixes
- `Feat` - New features
- `Chore` - Maintenance tasks
- `Docs` - Documentation changes
- `Style` - Code style/formatting (no logic change)
- `Refactor` - Code refactoring (no behavior change)
- `Perf` - Performance improvements
- `Test` - Adding or updating tests
- `Revert` - Reverting previous commits
- `CI` - CI/CD configuration changes
- `Build` - Build system changes

### Commit Command

Always use the `-s` flag for Developer Certificate of Origin sign-off:

```bash
git commit -s -m "Type(scope): Description

Body text here.

Co-Authored-By: <AI Model> <email@provider.com>"
```

### Line Length Limits

- **Subject line**: Maximum 50 characters (required per constitution)
- **Body lines**: Maximum 80 characters
- URLs in body are exempt from line length (gitlint configured)

### Co-Authorship

All AI-assisted commits MUST include a Co-Authored-By trailer identifying the
AI model used. Use the appropriate name and email for your model:

| Model | Co-Authored-By |
| ------- | ---------------- |
| Claude | `Co-Authored-By: Claude <claude@anthropic.com>` |
| ChatGPT | `Co-Authored-By: ChatGPT <chatgpt@openai.com>` |
| Gemini | `Co-Authored-By: Gemini <gemini@google.com>` |
| Copilot | `Co-Authored-By: GitHub Copilot <copilot@github.com>` |

This trailer goes at the end of the commit message body.

## Pre-Commit Hooks

This repository uses pre-commit hooks that run automatically on `git commit`.
The hooks may enforce (non-exhaustive list):

- **reuse** - SPDX license header compliance
- **ruff** - Python linting and formatting
- **mypy** - Python type checking
- **interrogate** - Docstring coverage
- **yamllint** - YAML linting
- **gitlint** - Commit message format validation
- **actionlint** - GitHub Actions workflow validation
- **aislop** - AI-slop / code-quality gate (full-tree, every commit)

Additional hooks may be configured. Check `.pre-commit-config.yaml` for the
complete list.

### If Pre-Commit Fails

**CRITICAL**: Do NOT use `git reset` after a failed commit attempt.

1. Fix the issues identified by the pre-commit hooks
2. Stage the fixes: `git add <files>`
3. Attempt the commit again as if you hadn't tried before
4. The pre-commit hooks will run again on the new attempt

Pre-commit hooks may auto-fix some issues (e.g., ruff format). If files were
modified by hooks, stage them and commit again.

### Never Bypass Hooks

Using `--no-verify` to bypass pre-commit hooks is **PROHIBITED**.

### aislop Quality Gate

The `aislop` hook runs `aislop ci` over the WHOLE project on every
commit (not just staged files) and must report `100 / 100` with zero
issues. The project currently holds a clean 100/100 score; keep it
there.

- The hook is a `local` pre-commit hook wired to:
  `additional_dependencies: ['aislop@0.12.0']` (the npm-published
  package). It is NOT installed from the upstream `scanaislop/aislop`
  git tag, because that tag does not ship the built `dist/` directory
  and registers a broken bin.
- To scan specific files manually, use the comma-separated `--include`
  form — positional path arguments are rejected:

  ```bash
  npx --yes aislop@0.12.0 scan \
    --include 'src/pylocal_akuvox/device.py,src/pylocal_akuvox/_device_users.py'
  ```

- Run a full local gate with `npx --yes aislop@0.12.0 ci --human` before
  pushing.

## Atomic Commits

Each commit MUST represent exactly one logical change:

- ✅ One feature per commit
- ✅ One bug fix per commit
- ✅ One refactor per commit
- ❌ Multiple unrelated changes in one commit

### Task List Updates Are Separate Commits

Changes to task tracking documents (e.g., `tasks.md`) MUST be committed
separately from the code or documentation they track. Bundling a task
list update into the same commit as the work it describes breaks commit
atomicity — even when both changes are classified as documentation.

- ✅ Commit 1: `Feat(core): Add HTTP client` (code + tests)
- ✅ Commit 2: `Docs(tasks): Mark T015 complete` (tasks.md only)
- ❌ Single commit with code changes **and** tasks.md update

## SPDX License Headers

All new source files MUST include SPDX headers:

```python
# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0
```

Check `REUSE.toml` for file-type-specific header requirements.

## Testing Requirements

The Python project lives under `src/`. Run commands from that
directory using `uv`:

- Run tests before committing: `uv run pytest tests/`
- Run linting before committing: `uv run ruff check src/ tests/`
- All tests must pass before pushing
- New features should include appropriate test coverage
- Maintain **100% branch coverage**:

  ```bash
  uv run pytest tests/ \
    --cov=pylocal_akuvox \
    --cov-branch \
    --cov-report=term-missing
  ```

- The suite is the regression baseline; never let the test count
  regress without explicit justification

## Documentation (Sphinx/RST)

User-facing docs live in `docs/` and are published via Read the Docs.

- Build with warnings-as-errors before pushing doc changes:
  `uv run --extra docs sphinx-build -W -b html docs docs/_build/html`
- `docs/_build/` is build output and is gitignored — never commit it.
- **Do not put GitHub issue/PR references in reader-facing docs**
  (guide pages, capability notes). They add no value for readers.
  `docs/changelog.rst` is the ONE exception — issue/PR references are
  intentionally retained there.
- Multi-line inline RST literals (for example, ``literal``) confuse
  Sphinx; use an indented `::` literal block instead. Sphinx may accept
  the inline form silently, but reviewers flag it.
- In `docs/changelog.rst`, the "Breaking changes" subsection uses a
  sibling-level 16-caret `^^^^^^^^^^^^^^^^` underline; using a deeper
  underline depth reparents existing bullets.

## Refactor & Module-Layout Conventions

When splitting a large module into focused submodules:

- Use underscore-prefixed sibling modules (`_device_users.py`,
  `_capability_profile.py`), not a package — an empty `__init__.py`
  would still let the old subpath resolve.
- For a BREAKING split that drops a public import path, DELETE the
  original module entirely so `import pkg.oldmodule` raises
  `ModuleNotFoundError`. For a NON-breaking split, keep the public
  class in its original module and move only internal helpers.
- Cover module layout with a single owned test
  (`tests/unit/test_capability_module_layout.py`). When asserting a
  dropped subpath, use a BARE `pytest.raises(ModuleNotFoundError)` —
  never the tuple `(ModuleNotFoundError, ImportError)`, which would
  mask a partial-shim regression. When asserting a PRESERVED path,
  import it and assert the public symbol resolves.
- Re-validate every moved symbol/import against the LIVE source before
  creating modules; planning docs drift and cause ruff `F401`.
- "Make no other change" refactor steps implicitly allow automatic
  ruff/isort import-block reordering and format normalization.

## Development Workflow Summary

1. Make changes to code
2. Run tests locally to verify: `uv run pytest tests/ -x -q`
3. Run linting: `uv run ruff check src/ tests/`
4. Stage changes: `git add <files>`
5. Commit with sign-off and co-authorship:

   ```bash
   git commit -s -m "Type(scope): Description

   Body if needed.

   Co-Authored-By: <AI Model> <email@provider.com>"
   ```

6. If pre-commit fails, fix issues and commit again (don't reset)
7. Push when ready

## Quick Reference

| Requirement | Command/Format |
| ------------ | ---------------- |
| Sign-off | `git commit -s` |
| Co-author | `Co-Authored-By: <Model> <email@provider.com>` |
| Subject format | `Type(scope): description` |
| Type case | Capitalized (e.g., `Fix`, `Feat`) |
| Subject length | ≤50 chars required |
| Body line length | ≤80 chars |
| After failed commit | Fix and retry (no reset) |
