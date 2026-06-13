<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: Verifying Each Phase Ships Independently

**Feature**: 008-capability-matrix
**Audience**: Reviewers and the maintainer working through the four
implementation PRs. This recipe lets you confirm each phase delivers its
user-visible value on its own and that nothing earlier breaks.

The recipe is twelve numbered steps. Steps 1–3 cover Phase 1 (PR 1).
Steps 4–7 cover Phase 2 (PR 2). Steps 8–9 cover Phase 3 (PR 3). Steps
10–12 cover Phase 4 (PR 4).

All commands assume `cwd` is the repository root and `uv` is on `$PATH`.

---

## Phase 1 — Capability model and probe (PR 1)

### Step 1 — Imports resolve and types are inspectable

```bash
uv run python -c "
from pylocal_akuvox import Capability, CapabilityStatus, DeviceCapabilities
print(sorted(c.value for c in Capability))
print([s.value for s in CapabilityStatus])
print(DeviceCapabilities.__dataclass_fields__.keys())
"
```

**Expected**: a list of capability strings (`relay.trigger.api`,
`relay.trigger.fcgi`, `user.list`, etc.); the three status values
`['supported', 'unsupporteded', 'unknown']`; and a `dict_keys` view
including at least `device_class`, `firmware_version`, `capabilities`,
`field_aliases`, `schema_shapes`, `notes`, `provenance`.

If this fails, the Phase 1 imports are not wired. Stop and fix.

### Step 2 — Probe is non-destructive against a mocked X916

```bash
uv run pytest tests/unit/test_capability_probe.py -k non_destructive -v
```

**Expected**: the `test_probe_is_non_destructive` test
passes. Internally it stubs every probe URL with `aioresponses` and
asserts the request log contains no `*/add`, `*/set`, `*/del`,
`*/trig`, or `/fcgi/do?action=OpenDoor` URL.

This is SC-001 verification.

### Step 3 — Probe is idempotent

```bash
uv run pytest tests/unit/test_capability_probe.py -k idempotent -v
```

**Expected**: the `test_probe_is_idempotent` test passes — two
back-to-back probe runs against the same mocked device produce
`DeviceCapabilities` instances comparing **exactly** equal (no
per-field normalisation needed: probe-derived profiles carry
`provenance=None` and no timestamp is written into `notes`, per
`contracts/probe-api.md` §"Idempotence").

This is SC-002 verification.

After Phase 1 ships, `device.probe_capabilities()` is the only public
behavior change; existing callers see no difference because Phase 1
does not yet gate any operation behind capabilities.

---

## Phase 2 — Matrix, dispatch, and structured `AkuvoxUnsupportedError` (PR 2)

### Step 4 — Connect populates the effective profile from the matrix

```bash
uv run pytest tests/unit/test_device.py -k connect_populates_capabilities -v
```

**Expected**: a parametrised test exercises four mocked devices
(`/api/system/info` returns each of X916, X915S, E18C, IT83 model +
firmware) and asserts that, after `__aenter__`, `device.capabilities`
holds a `DeviceCapabilities` whose `provenance` is non-`None` and
matches the corresponding `CAPABILITY_MATRIX` entry — *without any
list endpoints being probed* (FR-008).

### Step 5 — Calling an unsupporteded operation raises before any HTTP request

```bash
uv run pytest tests/unit/test_device.py -k unsupporteded_raises_before_request -v
```

**Expected**: against a mocked X915S, calling `await
device.add_contact(...)` raises `AkuvoxUnsupportedError` with
`reason="capability_missing"`, `capability=Capability.CONTACT_ADD`,
`device_class="X915S"` (the matrix marks it `UNSUPPORTED`), **and**
the `aioresponses` request log contains zero entries for the contact
endpoint. Against a mocked IT83, calling `await device.add_user(...)`
raises `AkuvoxUnsupportedError` with `reason="capability_unknown"`,
`capability=Capability.USER_ADD`, `device_class="IT83"` (the matrix
records only positive evidence; writes remain `UNKNOWN` until probed
or curated), with the same zero-write request-log assertion.

This is SC-005 verification.

### Step 6 — Adapter dispatch picks the right URL per device class

```bash
uv run pytest tests/unit/test_dispatch.py -v
```

**Expected**: the parametrised `test_relay_trigger_dispatch` runs with
four rows. For X916 / X915S / E18C, calling
`await device.trigger_relay(num=1)` issues exactly
`POST /api/relay/trig`. For IT83, the same call issues exactly
`GET /fcgi/do?action=OpenDoor&relay=1`. Override paths
(`adapter=Capability.RELAY_TRIGGER_API` against IT83) raise
`AkuvoxUnsupportedError(reason="capability_missing")` with no HTTP
request issued.

This is SC-006 verification.

### Step 7 — Existing `_http.py` legacy raise still works

```bash
uv run pytest tests/unit/test_http.py::test_unsupporteded_api_raises_unsupporteded_error -v
uv run pytest tests/unit/test_exceptions.py -v
```

**Expected**: both pre-existing tests still pass after the additive
`AkuvoxUnsupportedError` evolution. This is the
backward-compatibility verification for `contracts/unsupporteded-error.md`.

---

## Phase 3 — Refactor field-name aliasing onto the matrix (PR 3)

### Step 8 — Existing #99 / #101 and #118 / #120 regression tests still green

```bash
uv run pytest tests/unit/test_users.py tests/unit/test_models.py -v
```

**Expected**: every pre-existing test passes **with no logic changes**.
Specifically, the tests covering:

- E18C dual-write of `ScheduleRelay` + `Schedule-Relay` in
  `add_user` / `modify_user` (#99 / PR #101)
- X915S `Schedule` read in `User.from_api_response` (#118 / PR #120)

continue to assert their current behavior. The only legal test
modifications in Phase 3 are to tests that were specifically asserting
*the location of a conditional* (e.g. "this `if firmware ==` branch
lives in `users.py`"). No payload-shape or parse-shape assertion
changes.

This is FR-016 / SC-008 verification.

### Step 9 — Adding a hypothetical new firmware band touches one file

Run the synthetic-fixture test that Phase 3 ships
(`test_add_hypothetical_entry`). This example will also be written up as
a worked walkthrough in `docs/api/capabilities.rst` in Phase 4, but the
fixture itself is exercisable as soon as Phase 3 lands:

```bash
uv run pytest tests/unit/test_matrix.py::test_add_hypothetical_entry -v
```

**Expected**: the test programmatically adds a synthetic
`(DeviceClassPattern, DeviceCapabilities)` to a copy of the matrix,
parses a synthetic user-list response with the synthetic entry's
field-aliases, and asserts the parser consults the entry's alias list
without any monkey-patch of `models/users.py` or `users.py`.

This is FR-017 / SC-007 verification.

---

## Phase 4 — Documentation and MVP example (PR 4)

### Step 10 — Doc page lists every device class and vice versa

```bash
uv run pytest tests/unit/test_docs_matrix_consistency.py -v
```

**Expected**: passes. This test reads
`docs/api/capabilities.rst` as plain text and asserts:

1. Every `model_prefix` in `CAPABILITY_MATRIX` appears in the .rst.
2. Every `X916`/`X915S`/`E18C`/`IT83`-style heading in the .rst
   corresponds to a matrix entry.

This is SC-009 verification.

### Step 11 — `examples/mvp_test.py` skips unsupporteded steps

Run the example against a mocked IT83 (the snapshot harness lives in
`tests/integration/test_mvp_smoke.py`):

```bash
uv run pytest tests/integration/test_mvp_smoke.py::test_mvp_against_it83 -v
```

**Expected**: the captured stdout contains lines matching the regex
`^  SKIP: add_user: status unknown on this device class \(IT83\)$` and
`^  SKIP: add_contact: status unknown on this device class \(IT83\)$`
and `^  OK:   trigger_relay$`. (The example distinguishes UNSUPPORTED
"not supported on …" from UNKNOWN "status unknown on …" wording per
research §9, since IT83 has no positive evidence for these writes.)
The test asserts both presences and the FCGI URL was actually issued
for the relay step.

This is SC-010 verification.

### Step 12 — Sphinx docs build clean (smoke check)

```bash
uv run --extra docs sphinx-build -W -b html docs/ docs/_build/html
```

**Expected**: the build completes with zero warnings. The new
`capabilities.rst` page is rendered with the matrix table and autodoc
entries for `Capability`, `CapabilityStatus`, and `DeviceCapabilities`.

The `docs` extra exists today in `pyproject.toml` under
`[project.optional-dependencies]` (sphinx, furo,
sphinx-autodoc-typehints, sphinx-copybutton); no Phase-4 task is
required to add the extra itself. Step 12 is a nice-to-have layered on
top of step 10 (which is sphinx-free); if step 12 fails for an
environmental reason but step 10 passes, do not block the PR.

---

## Order-of-operations rules (for reviewers)

- Steps 1–3 MUST pass against PR 1 before PR 1 is mergeable.
- Steps 4–7 MUST pass against PR 2; steps 1–3 MUST also still pass.
- Step 8 MUST pass against PR 3 with **no test logic changes**;
  steps 1–7 MUST also still pass.
- Steps 10–12 MUST pass against PR 4; steps 1–9 MUST also still pass.

If any earlier step regresses at a later phase, the regression is
blocking — phase boundaries (constitution §VI) require each phase to
end at a CI-green checkpoint.
