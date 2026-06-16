<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: Verifying the Capability Probe Module Split

**Feature**: 010-capability-probe-split
**Audience**: Reviewers and the implementer. This recipe validates
the refactor end-to-end against the spec's success criteria
(SC-001 through SC-009).

All commands assume `cwd` is the repository root and `uv` is on
`$PATH`.

---

## Step 1 — Test suite passes

```bash
uv run pytest tests/
```

**Expected**: All tests pass (exit 0). `tests/unit/test_capability_probe.py`
will have had its 41 `from pylocal_akuvox.capability_probe import …`
lines rewritten to point at the new underscore modules per
`data-model.md`, plus a one-line module-docstring fix at line 4
(see `data-model.md` § "Test files"). Every assertion body remains
semantically unchanged.

This verifies SC-001.

---

## Step 2 — Aislop scan on new modules

```bash
uv run aislop scan --include 'src/pylocal_akuvox/_probe_outcomes.py,src/pylocal_akuvox/_probe_classifiers.py,src/pylocal_akuvox/_probe_parsers.py,src/pylocal_akuvox/_capability_probe.py'
```

**Expected**: No `complexity/file-too-large` warnings for any of
the four new modules. Each is under the 400-line threshold.

**Carry-forward retro note** (009 retro item 3): `aislop scan
<files...>` rejects positional file arguments. Use the
`--include 'a,b,c,d'` form (comma-separated, no spaces inside
the quoted list, single quotes around the whole list to keep
shell-quoting straightforward).

This verifies SC-002.

---

## Step 3 — Subpath removal (bare import)

```bash
uv run python -c "import pylocal_akuvox.capability_probe"
```

**Expected output**:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'
```

Exit code: non-zero.

This verifies SC-003 for the `import` form.

---

## Step 4 — Subpath removal (from-import)

```bash
uv run python -c "from pylocal_akuvox.capability_probe import probe_capabilities"
```

**Expected output**:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'pylocal_akuvox.capability_probe'
```

Exit code: non-zero.

This verifies SC-003 for the `from`-import form.

---

## Step 5 — Public probe still works via device

```bash
uv run python -c "import pylocal_akuvox; assert callable(pylocal_akuvox.AkuvoxDevice.probe_capabilities); print('ok')"
```

**Expected output**:

```text
ok
```

Exit code: 0.

This verifies SC-004 (presence pin). Behavior coverage is the
test suite's responsibility (SC-001).

---

## Step 6 — Internal underscore-module imports (for white-box test authors)

```bash
uv run python -c "from pylocal_akuvox._probe_outcomes import _ProbeOutcome; print('ok')"
uv run python -c "from pylocal_akuvox._probe_classifiers import _classify_response, _outcome_to_status, _summarise_system_status; print('ok')"
uv run python -c "from pylocal_akuvox._probe_parsers import _step_1_payload, _extract_items, _record_user_aliases, _record_user_schema_keys, _record_contact_shape; print('ok')"
uv run python -c "from pylocal_akuvox._capability_probe import probe_capabilities; print('ok')"
```

**Expected**: All four print `ok` and exit 0.

---

## Step 7 — Layout-assertion test

```bash
uv run pytest tests/unit/test_capability_module_layout.py -v
```

**Expected**: 9 tests pass — the existing 5 capability-side
assertions (added by spec 009) plus the 4 new probe-side
assertions added by FR-011:

- `test_capability_probe_subpath_is_gone`
- `test_capability_probe_subpath_from_import_is_gone`
- `test_probe_underscore_modules_importable`
- `test_probe_capabilities_reachable_via_device`

This verifies SC-009.

---

## Step 8 — Sphinx -W clean

```bash
uv run --extra docs sphinx-build -W -b html docs docs/_build/html
```

**Expected**: Exit 0, no warnings. The probe is documented through
`AkuvoxDevice.probe_capabilities` (an `automethod` directive on a
device API page); the split does not affect how Sphinx renders
the probe documentation.

**Carry-forward retro note** (009 retro item 2): Sphinx-W does NOT
catch inline ``` `` … `` ``` literals that span newlines. Per
FR-014, any docstring updated during the refactor that includes
multi-line literal content MUST use indented `::` literal blocks,
not inline back-tick literals. Reviewers should manually inspect
the rendered HTML for the four new modules' docstrings (in
`docs/_build/html/`) if any were modified beyond a verbatim
cut-paste.

This verifies SC-007.

---

## Step 9 — Original file is gone

```bash
test ! -f src/pylocal_akuvox/capability_probe.py && echo "deleted"
```

**Expected output**:

```text
deleted
```

Exit code: 0 if the file is absent (the desired post-split state);
non-zero if the file still exists (refactor incomplete).

This verifies SC-008.

---

## Step 10 — Project-level aislop scan

```bash
uv run aislop scan
```

**Expected**: `capability_probe.py` no longer appears in the
`complexity/file-too-large` list (the file has been deleted).

**Note**: `device.py` (issue #142) will continue to be flagged —
that is tracked separately and is out of scope for this spec.
`capabilities.py` is already gone (shipped under spec 009).

This verifies SC-002 at project level.

---

## Step 11 — Changelog entry

```bash
grep -B 2 -A 5 "capability_probe" docs/changelog.rst
```

**Expected**: A "Breaking changes" subsection in the Unreleased
section names:

- The dropped `pylocal_akuvox.capability_probe` import subpath
- The migration path: continue calling
  `AkuvoxDevice.probe_capabilities()` (the documented public method)

The entry MUST appear at the same RST nesting level as the existing
009-spec "Breaking changes" subsection (level: `^^^^^^^^^^^^^^^^`
underline) so it does not re-parent existing top-level subsections
(carry-forward retro from 009 item 5).

This verifies SC-005.

---

## Step 12 — Commit subject marker and length

```bash
git log -1 --format=%s
git log -1 --format=%s | wc -c
```

**Expected**: The subject contains `!` before the colon and the
character count (which `wc -c` reports including the trailing
newline) is ≤51. Suggested subject (39 chars):

```text
Refactor(probe)!: Split into submodules
```

`wc -c` on that returns 40 (39 chars + newline).

This verifies SC-006.

---

## Step 13 — Pre-commit docstring sweep (FR-013)

Run all of the following as a single check (concatenate or run
sequentially):

```bash
# (a) old module name in every file outside specs/
grep -rn "pylocal_akuvox\.capability_probe\|capability_probe\.py" \
  src/ tests/ docs/ README.md examples/

# (b) stale phrasing inside the four new modules and the consuming code
grep -rn "defined here\|this module\|lazy import\|cycle\|dataclass" \
  src/pylocal_akuvox/_probe_outcomes.py \
  src/pylocal_akuvox/_probe_classifiers.py \
  src/pylocal_akuvox/_probe_parsers.py \
  src/pylocal_akuvox/_capability_probe.py \
  src/pylocal_akuvox/device.py \
  tests/unit/test_capability_probe.py
```

**Expected**:

- (a) Zero matches outside `docs/changelog.rst` and `specs/`. The
  changelog ENTRY (added by FR-008) is allowed to mention the old
  subpath because that is the migration message — review the
  changelog hit manually to confirm it is the intended Breaking-changes
  entry, not stale phrasing in another section.
- (b) Surviving matches must each be reviewed manually. The
  `"this module"` phrasing IS allowed when it is a self-reference
  inside a single new module's docstring (e.g.,
  `_capability_probe`'s top-level docstring saying "this module
  implements the runtime side of the capability profile"). It is
  NOT allowed when it points back at the old monolithic
  `capability_probe.py`. The `"dataclass"`, `"lazy import"`,
  and `"cycle"` matches are 009-flavored stale phrases — none
  apply to the live capability_probe.py source today, so any
  survivor here means the implementer accidentally pasted from
  spec 009 or its test file.

**Critical sweep items** (must all show **zero** matches):

```bash
# (c) the test file's module docstring at line 4 must no longer name the dropped subpath
grep -n "pylocal_akuvox\.capability_probe" tests/unit/test_capability_probe.py
```

`grep` (c) MUST return zero matches post-rewrite — the test file's
existing docstring at line 4 (`"""Tests for the capability probe in
``pylocal_akuvox.capability_probe``."""`) must be updated alongside
the import rewrites.

**Carry-forward retro note** (009 retro item 1): These greps hit
BOTH the new modules' bodies AND the consumer (`device.py`) AND
the test file (`test_capability_probe.py`). Run them as a single
pre-commit check before staging the implementation commit.

---

## Step 14 — Sphinx role / data reference sweep

```bash
grep -rn ":mod:\`pylocal_akuvox\.capability_probe\`\|:func:\`pylocal_akuvox\.capability_probe\.\|:data:\`pylocal_akuvox\.capability_probe\." \
  docs/ src/ tests/ README.md
```

**Expected**: Zero matches. The pre-spec sweep (research.md
Decision 7) confirmed zero hits today; this final-check rerun
catches any hits that may have been re-introduced via
copy-paste during the refactor.

This is the implementation phase's belt-and-suspenders for
FR-009 / FR-010.

---

## Verification Matrix

| Step | Verifies | Notes |
|---|---|---|
| 1 | SC-001 | Full test suite |
| 2 | SC-002 | New-module aislop |
| 3, 4 | SC-003 | Both import forms raise |
| 5 | SC-004 | Public method present |
| 6 | FR-005 | Underscore modules importable |
| 7 | SC-009 / FR-011 | Layout-assertion file extension |
| 8 | SC-007 / FR-014 | Sphinx-W clean |
| 9 | SC-008 | Original file deleted |
| 10 | SC-002 | Project-level aislop |
| 11 | SC-005 / FR-008 | Changelog entry |
| 12 | SC-006 / FR-007 | Commit subject `!` and length |
| 13 | FR-013 | Pre-commit docstring sweep |
| 14 | FR-009 / FR-010 | Sphinx role sweep |
