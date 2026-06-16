<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Research: Capability Probe Module Split

**Feature**: 010-capability-probe-split
**Date**: 2026-06-16

## Unknowns from Technical Context

None block authoring. The split is purely structural — all symbols,
types, and runtime behavior are preserved. The only decisions concern
layout, import-path policy, and enforcement of the breaking change.

This refactor follows the precedent set by spec
`009-capabilities-module-split` (PR #145 spec / PR #148
implementation, merged at SHA `4fc75e8`); deviations from the 009
pattern are explicitly justified below.

---

## Decision 1: Four-Way Split — Outcomes / Classifiers / Parsers / Orchestration

**Decision**: Split `capability_probe.py` into four sibling modules at
the same package level, each prefixed with `_`:

- `src/pylocal_akuvox/_probe_outcomes.py` —
  `_ProbeOutcome` enum and the three message-marker constants
- `src/pylocal_akuvox/_probe_classifiers.py` — pure
  response-classification helpers
- `src/pylocal_akuvox/_probe_parsers.py` — step-1 payload extraction,
  item extraction, schema/alias recorders
- `src/pylocal_akuvox/_capability_probe.py` — the orchestration layer
  (step-path constants, `_LATER_STEPS`, `probe_capabilities`)

**Rationale**:

1. **Issue #141 explicitly recommends this layered structure**:
   "extract pure response classifiers and schema-shape parsers first,
   then keep `probe_capabilities()` as the orchestration layer."
   The four-way split realizes that recommendation by recognizing
   that the `_ProbeOutcome` enum + marker constants are a natural
   leaf-level dependency of the classifiers (and thus deserve their
   own module rather than being bundled with the classifiers).
2. **Sibling module structure produces a clean
   `ModuleNotFoundError`** on the old import path. A
   `capability_probe/` package directory with even an empty
   `__init__.py` would resolve `import pylocal_akuvox.capability_probe`
   as a regular package, defeating the deliberate break. (009
   Decision 1 made this same call; it carries forward.)
3. **Underscore prefix on every module** signals "internal — use
   `AkuvoxDevice.probe_capabilities()` for the consumer entry."
   Consumers never had a reason to import any of these symbols
   directly (the README and quickstart already document the device
   method, not the module function); making the underscore prefix
   uniform across all four reinforces that intent.
4. **The orchestration module ALSO gets the `_` prefix** — it is the
   user's locked design decision (#1 in the prompt: "all internal").
   `device.py` imports from `_capability_probe` exactly the way it
   would import from any other internal helper module. There is no
   non-underscored "shim" module that could be misread as an
   acceptable consumer import path.
5. The four-way split keeps the largest resulting module
   (`_capability_probe.py`) well under the 400-line aislop threshold
   even after per-file overhead (SPDX header, docstring, imports,
   `__all__`).

**Alternatives considered**:

- **Three-way split (outcomes folded into classifiers)**: Rejected.
  The `_ProbeOutcome` enum is consumed by both the classifiers
  (which produce `_ProbeOutcome` values) and the orchestration
  (which switches on `_ProbeOutcome.SUPPORTED` for step-3 / step-4
  side effects). Keeping it as a leaf module makes the dependency
  graph cleaner: classifiers and orchestration both depend on
  outcomes, but the classifiers don't need to be a dependency of
  every consumer of `_ProbeOutcome`.
- **Three-way split (classifiers and parsers merged)**: Rejected.
  The 009 retro shows that maintainers value **single-concern
  modules**. Classifiers are pure functions over `(status, body)`;
  parsers carry recorder side effects (mutating a dict). They have
  different testing strategies and different review concerns; merging
  would dilute that.
- **Keep `capability_probe.py` as a thin orchestration shim
  re-exporting `probe_capabilities`**: Rejected.
  The user's locked design decision is "BREAKING — delete entirely."
  A re-export shim would silently preserve the
  `from pylocal_akuvox.capability_probe import probe_capabilities`
  path and defeat the explicit goal of breaking it. (Same reasoning
  as 009 Decision 2 for `capabilities.py`.)
- **Two-way split (helpers + orchestration)**: Rejected. The
  resulting "helpers" module would be ~300 lines and would mix three
  unrelated concerns (outcome vocabulary, classification, parsing),
  defeating the "focused, readable" P2 user story. Issue #141
  explicitly recommends extracting **classifiers and parsers
  separately**.

---

## Decision 2: Public-Surface Contraction — All Internal

**Decision**: No symbol from the four new modules is added to the
top-level `pylocal_akuvox.__all__`. The package `__all__` is
unchanged by this refactor.

The consumer-facing handle for the probe remains
`AkuvoxDevice.probe_capabilities()` (a method on the
already-public `AkuvoxDevice` class), exactly as it is documented
in `README.md` and `docs/quickstart.rst` today.

This IS the breaking change for the import-path layer: the
`pylocal_akuvox.capability_probe` subpath was reachable today
(used by `tests/unit/test_capability_probe.py` for 41 white-box
imports — 1 static plus 40 deferred), and post-split it raises
`ModuleNotFoundError`.

**Rationale**: The probe internals are matrix-author / maintainer
internals. None of them are consumer-facing. Promoting any of them
to top-level public would create a semver maintenance obligation
for names that were never intended to be public.

The user's locked design decision (#1 in the prompt: "BREAKING.
Delete `capability_probe.py` entirely") forecloses the
alternative.

**Alternatives considered**:

- **Promote `probe_capabilities` to top-level
  `pylocal_akuvox.__all__`**: Rejected. `AkuvoxDevice.probe_capabilities()`
  is the documented public entry. A second top-level form would
  invite confusion (which is canonical?) and would re-create a
  module-level import path that consumers might come to depend on.
- **Keep an orchestration-only re-export shim
  `capability_probe.py`** (single re-export of `probe_capabilities`):
  Rejected by user-locked decision #1. Also rejected on its own
  merits: the shim would still register a real
  `pylocal_akuvox.capability_probe` module, so the user's hard
  requirement that `import pylocal_akuvox.capability_probe` raise
  `ModuleNotFoundError` cannot be satisfied with a shim.

---

## Decision 3: Subpath-Removal Enforcement

**Decision**: Extend the existing
`tests/unit/test_capability_module_layout.py` (added by spec 009)
with new probe-specific assertions, rather than creating a parallel
`test_probe_module_layout.py`.

**Rationale**:

1. The existing file already establishes the precise idiom: bare
   `import` form goes through `importlib.import_module`, `from`-import
   form goes through `exec()` (so static collection-time evaluation
   doesn't crash the test module). Reusing this idiom is cheaper and
   less error-prone than re-implementing it.
2. A single canonical "module shape pinning" file is the right place
   for layout assertions across the library. Splitting them by
   feature spec would invite fragmentation.
3. The file is short (~90 lines today); adding ~50 lines for the
   probe assertions keeps it well under any size threshold.
4. The file's docstring already references "spec
   `009-capabilities-module-split`"; updating it to also mention
   spec 010 documents that its scope has expanded.

The carry-forward retro from 009 (item 4) — use bare
`pytest.raises(ModuleNotFoundError)`, never the
`(ModuleNotFoundError, ImportError)` tuple — is honored.

**Alternatives considered**:

- **Create a new `tests/unit/test_probe_module_layout.py`**:
  Rejected. Doubles the file count for what is structurally the
  same kind of assertion, and risks divergence (e.g., one file
  using bare `ModuleNotFoundError` and the other using the looser
  `ImportError` superclass).
- **Rely on aislop scan + ruff**: Rejected for the same reasons
  009 Decision 3 rejected them. Aislop checks file size, not
  import-path semantics. No standard ruff rule asserts "module X
  must not exist."

---

## Decision 4: Module Size Targets

**Decision**: Target sizes for the four new modules, all comfortably
under the 400-line aislop threshold:

| Module | Estimated lines | Content |
|---|---|---|
| `_probe_outcomes.py` | ~50 | SPDX (~3) + docstring (~10) + imports `enum` (~3) + `_ProbeOutcome` enum (~9) + `_NO_HANDLER_MARKERS` / `_API_UNSUPPORTED_MARKER` / `_ACTION_UNSUPPORTED_MARKERS` (~9) + `__all__` (~7) + whitespace (~9) |
| `_probe_classifiers.py` | ~140 | SPDX (~3) + docstring (~10) + imports (`json`, `_probe_outcomes`, `_capability_types`) (~10) + `_extract_message` (~17) + `_summarise_system_status` (~36) + `_classify_response` (~36) + `_outcome_to_status` (~8) + `__all__` (~9) + whitespace (~11) |
| `_probe_parsers.py` | ~175 | SPDX (~3) + docstring (~10) + imports (`json`, `Any`, `AkuvoxParseError`, `FieldAliases`, `SchemaShape`) (~12) + `_step_1_payload` (~31) + `_extract_items` (~26) + `_record_user_aliases` (~27) + `_record_user_schema_keys` (~28) + `_record_contact_shape` (~23) + `__all__` (~9) + whitespace (~6) |
| `_capability_probe.py` | ~175 | SPDX (~3) + docstring (~22) + imports (TYPE_CHECKING + multiple submodules + `Capability` / `CapabilityStatus` / `DeviceCapabilities` / `FieldAliases` / `SchemaShape` / exceptions / `DeviceInfo` + `_ProbeOutcome` from `_probe_outcomes` + classifiers from `_probe_classifiers` + recorders from `_probe_parsers`) (~25) + step-path constants `_PROBE_STEP_3_PATH` … `_PROBE_STEP_9_PATH` (~8) + `_LATER_STEPS` (~12) + `probe_capabilities` async function (~104) + `__all__` (~3) |

**Arithmetic from the current 465-line file**:

- SPDX + module docstring + imports + TYPE_CHECKING block: ~46 lines
- `_ProbeOutcome` + 3 marker constants: ~22 lines
- 7 step-path constants + `_LATER_STEPS`: ~32 lines
- `_extract_message`: ~17 lines
- `_summarise_system_status`: ~36 lines
- `_classify_response`: ~36 lines
- `_outcome_to_status`: ~8 lines
- `_step_1_payload`: ~31 lines
- `_extract_items`: ~26 lines
- `_record_user_aliases`: ~27 lines
- `_record_user_schema_keys`: ~28 lines
- `_record_contact_shape`: ~23 lines
- `probe_capabilities` async function: ~104 lines
- `__all__` + trailing whitespace: ~6 lines
- **Total: ~442 lines of source content** (~23 lines of internal
  whitespace round to the 465 reported by `wc -l`)

Each new file adds its own SPDX header (~3 lines), module docstring
(~10 lines), imports (~10–25 lines), and `__all__` (~5–9 lines).
Even with this overhead (~60 net additional lines distributed
across four files), all four stay well under 400 lines, with the
largest hovering around 175 lines — well below the threshold.

---

## Decision 5: Internal-Import Paths Within the Library

**Decision**: Internal modules use direct underscore-module imports:

```python
from pylocal_akuvox._probe_outcomes import _ProbeOutcome
from pylocal_akuvox._capability_types import Capability, CapabilityStatus
```

They do NOT import via the top-level `pylocal_akuvox` re-export.
This matches 009 Decision 5 verbatim and is consistent with the
package's existing style.

**Rationale**:

1. Avoids circular-import risk during package bootstrap. The
   top-level `__init__.py` does not import from the new probe
   modules at all (none of them are re-exported), so there is no
   bootstrap-cycle concern; but maintaining the established style
   keeps the code uniform.
2. Makes intent explicit: "this is internal-to-internal usage."
3. Top-level `pylocal_akuvox` import path is for consumers and for
   tests verifying the consumer surface — neither applies here.

**Alternatives considered**:

- **Relative imports** (`from ._probe_outcomes import ...`):
  Acceptable but not preferred. Project style uses absolute
  imports throughout.

---

## Decision 6: White-Box Test Imports

**Decision**: Tests asserting on probe internals will import from
the underscore modules directly:

```python
from pylocal_akuvox._probe_classifiers import _classify_response, _outcome_to_status
from pylocal_akuvox._probe_outcomes import _ProbeOutcome
from pylocal_akuvox._probe_parsers import _record_user_aliases, _extract_items
from pylocal_akuvox._capability_probe import probe_capabilities
```

This is intentional. The white-box surface is the underscore module,
not the (no-longer-existent) `pylocal_akuvox.capability_probe`.

The single test file affected is
`tests/unit/test_capability_probe.py` (41 import-line rewrites
across the file's lines 29, 674, 739, 748, 756, 766, 773, 782,
791, 800, 809, 820, 829, 838, 847, 866, 875, 884, 893, 900, 907,
914, 921, 929, 940, 950, 965, 977, 994, 1008, 1016, 1023, 1036,
1048, 1122, 1142, 1152, 1161, 1170, 1179, 1188 — full grep result
in `data-model.md`), plus a one-line module-docstring fix at the
same file's line 4 (the docstring references the dropped subpath
verbatim).

**Rationale**: The old `from pylocal_akuvox.capability_probe import …`
path is removed. Tests that need internal symbols must use the new
canonical internal path. Tests verifying the consumer surface use
`AkuvoxDevice.probe_capabilities()` via a mocked HTTP client (the
test file already does this for the integration path; only the
white-box helper imports change).

---

## Decision 7: README, Quickstart, and Sphinx Docs Sweep — Confirmed Zero Hits

**Decision**: No documentation update is required for `README.md`,
`docs/quickstart.rst`, `docs/api/*.rst`, or
`docs/_ext/capability_matrix.py` other than the changelog entry
mandated by FR-008.

**Sweep performed during spec authoring**:

```bash
$ grep -rn "capability_probe" docs/ README.md examples/
# (zero matches in non-changelog files)

$ grep -rn "probe_capabilities" docs/ README.md examples/
docs/quickstart.rst:35:firmware update, call :meth:`pylocal_akuvox.AkuvoxDevice.probe_capabilities`
docs/quickstart.rst:36:to run the deterministic, non-destructive read probe.
docs/quickstart.rst:40:Use the probe-then-act pattern so provisioning code only runs operations
docs/quickstart.rst:50:           capabilities = await device.probe_capabilities()
docs/quickstart.rst:77:   code, guard each operation with the probed or matrix profile as
docs/changelog.rst:52:* Safe ``probe_capabilities()`` using a deterministic 9-call read-only
README.md:64:        capabilities = await device.probe_capabilities()
examples/mvp_test.py:2098:        capabilities = await device.probe_capabilities()
```

Every reference to the probe in README / quickstart / examples uses
the public `device.probe_capabilities()` form, not the module path.
The split does not affect any of these. The Sphinx extension
`docs/_ext/capability_matrix.py` only imports from
`pylocal_akuvox._capability_types` and `pylocal_akuvox.capability_matrix`
— it never touches `capability_probe` (verified at lines 30–31).
The API page `docs/api/capabilities.rst` does not mention the probe
module at all (the probe is documented through `AkuvoxDevice` on a
different page).

**Rationale**: Documenting the sweep result here in the spec
prevents the implementation agent from re-discovering it (which
would waste a Copilot review round). The user explicitly called this
out in the prompt: "Spec must explicitly note the result of the
sweep."

**Carry-forward note** (009 retro item 1): Despite this confirmed
zero-hit sweep, the implementation agent still performs a final
pre-commit `grep -rn "pylocal_akuvox.capability_probe"
src/ tests/ docs/ README.md examples/` to catch any docstring
references inside the four new modules that may have been
mechanically copy-pasted from the old module's docstring (which
mentions itself as "this module"). Per FR-013, those are
addressed in the implementation commit.

---

## Decision 8: Cycle-Risk Analysis Between Classifiers and Parsers

**Decision**: `_probe_classifiers.py` and `_probe_parsers.py` have
NO cross-import in either direction. They are siblings at the same
dependency level under `_capability_probe.py` (which imports from
both).

**Verification**: Trace through the live source.

- `_extract_message`, `_summarise_system_status`, `_classify_response`,
  `_outcome_to_status` (the classifiers) operate on raw `(status,
  body)` tuples and return primitive values or `_ProbeOutcome` /
  `CapabilityStatus`. They do not call any of the parsers.
- `_step_1_payload`, `_extract_items`, `_record_user_aliases`,
  `_record_user_schema_keys`, `_record_contact_shape` (the parsers)
  operate on bodies and dict accumulators and return `None` or
  `dict[str, Any]` or `list[Any] | None`. They do not call any of
  the classifiers.
- Both call `json.loads` directly on bodies; neither delegates the
  parse step to the other.

**Rationale**: This non-circularity is what makes the split clean.
If the classifiers had called any parser (or vice versa), the
two-module split would have to be reorganized to break the cycle —
likely by introducing a third "primitives" module. Confirming the
absence of cross-calls upfront preempts that rabbit hole.

**Alternatives considered**:

- **Co-locate classifiers and parsers in one module**: Rejected
  per Decision 1 (separation-of-concerns argument).

---

## Decision 9: Step-Path Constants and `_LATER_STEPS` Ownership

**Decision**: The seven step-path constants
(`_PROBE_STEP_3_PATH` … `_PROBE_STEP_9_PATH`) and the `_LATER_STEPS`
tuple live in the orchestration module `_capability_probe.py`.

**Rationale**:

1. Both are consumed only by `probe_capabilities()` itself (the
   constants are also referenced inline in `probe_capabilities`'s
   step-3 / step-4 side-effect dispatch: `if path ==
   _PROBE_STEP_3_PATH and outcome is _ProbeOutcome.SUPPORTED`).
2. Neither the classifiers nor the parsers reference these
   constants. Moving them out would require introducing a new
   import dependency for no semantic benefit.
3. Keeping them with the orchestration preserves the live-source
   layout adjacency: the constant block, the `_LATER_STEPS` tuple,
   and the `probe_capabilities` driver are all in one file today
   and remain in one file post-split.

**Alternatives considered**:

- **Move step-path constants to `_probe_outcomes.py`**: Rejected.
  They are not "outcomes" — they are orchestration data. Keeping
  the outcomes module pure (just the enum + markers) maximizes its
  reusability if a future maintainer wants to widen the probe
  vocabulary independently.

---

## Decision 10: Implementation-Commit Subject Form and Length

**Decision**: The implementation commit subject is:

```text
Refactor(probe)!: Split into submodules
```

That is **39 characters** — well under the 50-character ceiling
gitlint enforces — and contains the conventional-commits `!`
breaking-change marker before the colon. The verb is `Split` (the
009 implementation locked in `Refactor(capabilities)!: Split module
into focused submodules` at 56 characters, which required the
`gitlint-line-length` exception on the 009 PR; this 010 subject
deliberately fits within the 50-char default).

**Rationale**:

1. Gitlint enforces a 50-character subject ceiling by default;
   staying inside it avoids needing per-commit exceptions.
2. The `!` is non-negotiable per FR-007 — the 009 retro confirmed
   that consumers reading `git log --oneline` rely on it as the
   only at-a-glance signal of a breaking change.
3. The scope `(probe)` is shorter and clearer than
   `(capability_probe)` would be; both are unambiguous in context
   (the file being split is the only "probe" file in the package).

**Alternatives considered**:

- `Refactor(capability_probe)!: Split module` (40 chars):
  Acceptable but not preferred — the longer scope name doesn't add
  information.
- `Refactor!: Split capability_probe into submodules` (49 chars):
  Acceptable. The scope-less form is uglier in `git log` and breaks
  the (capability)! / (probe)! / (matrix)! family that 009 and
  future splits will share.

The implementation agent MUST verify the exact length with
`git log -1 --format=%s | wc -c` (which includes a trailing
newline, so the result should be 40 for the suggested subject) and
adjust if the suggested form differs from what they commit.
