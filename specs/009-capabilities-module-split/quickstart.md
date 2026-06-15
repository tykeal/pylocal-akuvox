<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: Verifying the Capabilities Module Split

**Feature**: 009-capabilities-module-split
**Audience**: Reviewers and the implementer. This recipe validates the
refactor end-to-end against the spec's success criteria.

All commands assume `cwd` is the repository root and `uv` is on `$PATH`.

---

## Step 1 — Test suite passes

```bash
uv run pytest tests/
```

**Expected**: All tests pass (exit 0). Test imports will have been
rewritten to use the new underscore module paths, but all assertions
remain semantically unchanged.

This verifies SC-001.

---

## Step 2 — Aislop scan on new modules

```bash
uv run aislop scan src/pylocal_akuvox/_capability_*.py
```

**Expected**: No `complexity/file-too-large` warnings for any of the
four new modules. Each is under the 400-line threshold.

This verifies SC-002.

---

## Step 3 — Subpath removal

```bash
uv run python -c "import pylocal_akuvox.capabilities"
```

**Expected output**:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'pylocal_akuvox.capabilities'
```

Exit code: non-zero.

This verifies SC-003.

---

## Step 4 — Top-level imports work

```bash
uv run python -c "from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities, FieldAliases, SchemaShape; print('ok')"
```

**Expected output**:

```text
ok
```

Exit code: 0.

This verifies SC-004.

---

## Step 5 — Internal underscore-module imports (for white-box test authors)

```bash
uv run python -c "from pylocal_akuvox._capability_matching import DeviceClassPattern, lookup_capabilities; print('ok')"
```

**Expected output**:

```text
ok
```

Exit code: 0.

Additional internal imports to verify:

```bash
uv run python -c "from pylocal_akuvox._capability_types import Capability, CapabilityStatus, SchemaShape; print('ok')"
uv run python -c "from pylocal_akuvox._capability_profile import FieldAliases, Provenance, DeviceCapabilities; print('ok')"
uv run python -c "from pylocal_akuvox._capability_defaults import DEFAULT_USER_FIELD_ALIASES; print('ok')"
```

All should print `ok` and exit 0.

---

## Step 6 — Layout-assertion test

```bash
uv run pytest tests/unit/test_capability_module_layout.py -v
```

**Expected**: All assertions pass:

- `import pylocal_akuvox.capabilities` raises `ModuleNotFoundError`
- Each underscore module is importable
- The 5 public symbols round-trip via the top-level re-export

---

## Step 7 — Aislop project-level scan

```bash
uv run aislop scan
```

**Expected**: `capabilities.py` no longer appears in the
`complexity/file-too-large` list (the file has been deleted).

**Note**: `device.py` and `capability_probe.py` will continue to be
flagged — those are tracked in issues #142 and #141 respectively and
are out of scope for this spec.

This verifies SC-002 at project level and confirms the original file is
gone.

---

## Step 8 — Changelog entry

```bash
grep -A 5 "Breaking changes" docs/changelog.rst
```

**Expected**: The Unreleased section contains a "Breaking changes"
subsection naming:

- The dropped `pylocal_akuvox.capabilities` subpath
- The 4 no-longer-publicly-reachable internal symbols
- The migration path (use `from pylocal_akuvox import ...`)

This verifies SC-005.

---

## Step 9 — Commit subject marker

```bash
git log -1 --format=%s
```

**Expected**: The subject contains `!` before the colon, e.g.:

```text
Refactor(capabilities)!: Split module into focused submodules
```

This verifies SC-006.
