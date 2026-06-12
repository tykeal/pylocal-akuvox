# Phase 0 Research — 007-models-split

**Branch**: `007-models-split`
**Date**: 2026-06-12
**Status**: Complete — all decisions settled, no `NEEDS CLARIFICATION` remaining.

This document records the design questions raised by the spec, the chosen
answers, the rationale, and the alternatives rejected.

---

## R1. Re-export surface: shim file vs `models/` package

**Decision**: Convert `pylocal_akuvox.models` from a single file
(`models.py`) to a **package** (`models/` directory with `__init__.py`
acting as the re-export shim).

**Rationale**:

1. **Namespace ↔ on-disk parity.** With a package, the public namespace
   `pylocal_akuvox.models` and the disk location of the submodules
   (`pylocal_akuvox/models/<domain>.py`) match exactly. There is one
   structure for one job.
2. **No top-level pollution.** The flat-shim alternative would either
   place `_user_models.py`, `_device_models.py`, … sibling to the
   existing service modules (`users.py`, `device.py`, …) or hide them
   under a sibling `_models/` private package. Both options introduce
   either naming pressure or *two* structures (shim + private package)
   for the same conceptual unit.
3. **No naming collision with service modules.** The existing service
   modules (`pylocal_akuvox/users.py`, `device.py`, `schedules.py`,
   `groups.py`, `logs.py`, `contacts.py`, `config.py`) all consume model
   dataclasses by the same domain name. Placing the model definitions at
   `pylocal_akuvox/models/users.py` (etc.) lets the model file and the
   service file share the domain name unambiguously across two
   different packages.
4. **Future cross-cutting room (FR-009).** The package shape leaves the
   *flat* top level (`pylocal_akuvox/capabilities.py`, etc.) available
   as the obvious home for future cross-cutting types from #123 —
   parallel to the existing service modules, not inside `models/`. This
   directly satisfies the spec's FR-009 requirement that no domain
   module be carved up to host cross-cutting types.
5. **Shim file size headroom (FR-005).** `__init__.py` will be roughly:
   header (2) + module docstring (3-4) + `from __future__ …` (2) + 7
   `from .<sub> import …` lines + `__all__` list of 10 names (~14
   lines) + blank-line spacing ≈ **~40 lines total**. Far under the
   400-line ceiling. No risk of the shim itself ever approaching the
   threshold.

**Alternatives considered**:

- **Shim file `models.py` + sibling private package `_models/`.**
  Rejected because it requires two structures for one job (point 1), and
  because the `_` prefix implies "private", which is misleading: the
  submodules are perfectly fine import targets for users who want to
  reach past the shim (the spec's FR-012 explicitly permits this).
- **Shim file `models.py` + sibling per-domain files at top level
  (`_models_user.py`, `_models_device.py`, …).** Rejected because it
  pollutes the top-level namespace, the `_models_` prefix is ugly, and
  the resulting `models.py` file would still be the only re-export
  point, gaining nothing over the package approach while losing the
  per-domain folder grouping.
- **`__getattr__`-based lazy-loading shim.** Rejected — explicitly
  forbidden by spec Out-of-Scope ("The re-export surface is expected to
  be a plain, explicit import block.").

---

## R2. `AccessSchedule` and `Group`: combine into one module or split?

**Decision**: Split into two submodules — `models/schedules.py` (owns
`AccessSchedule`) and `models/groups.py` (owns `Group`).

**Rationale**:

- Mirrors the existing service-module structure 1:1
  (`pylocal_akuvox/schedules.py` and `pylocal_akuvox/groups.py` already
  exist as separate modules). Domain locality is maximised.
- Sizes stay tiny — `models/schedules.py` ≈ 95 lines incl. headers,
  `models/groups.py` ≈ 40 lines incl. headers. No file-size pressure.
- The spec key-entity description explicitly permits both groupings;
  splitting is the cleaner of the two for this codebase.

**Alternatives considered**:

- **Combine into one `models/access.py`.** Rejected because it diverges
  from the existing service-module layout and forces two unrelated
  parsers (`AccessSchedule.from_api_response` and
  `Group.from_api_response`) to share a file for no concrete benefit.

---

## R3. `DeviceConfig`: with the device-domain module, or standalone?

**Decision**: Standalone in `models/config.py`.

**Rationale**:

- The existing service split has `device.py` (consumes
  `DeviceInfo` / `DeviceStatus` / `Relay`) and `config.py` (consumes
  `DeviceConfig`) as separate modules. Mirroring that split in the model
  layer keeps "where do I edit thing X?" a one-step question.
- `DeviceConfig` is fetched via a different API endpoint than the
  device-info/status/relay triple, and tends to change for different
  reasons (firmware feature additions vs the stable identity/status
  trio). Keeping it standalone aligns the file boundary with the change
  boundary.
- Sizes stay tiny — `models/config.py` ≈ 60 lines, `models/device.py` ≈
  130 lines. Both well under the 400-line ceiling, both have room to
  grow.

**Alternatives considered**:

- **Combine `DeviceConfig` with the device-domain module.** Rejected
  because it would diverge from the existing service split, mixing two
  different change vectors in one file, for the sake of saving one tiny
  file. Spec permits either, but the split better serves future-change
  locality (US3).

---

## R4. Split `tests/unit/test_models.py` to mirror the new layout?

**Decision**: **No** — keep `tests/unit/test_models.py` as a single file
in this feature.

**Rationale**:

- The spec explicitly marks this as optional and out of scope as a
  requirement (Out-of-Scope bullet 5).
- Keeping the file intact preserves `git blame` continuity on the
  parsing test history, which is exactly the history that #121 and #123
  will want to read when they extend the same parsers.
- The minimal-diff principle: this feature is supposed to be a
  byte-displacement refactor with zero behavior change. Reshuffling the
  test file adds noise that obscures the production-code move in
  review.
- A future test-split can be done at zero risk in its own commit once
  the production split is stable — better to defer than to bundle.

**Alternatives considered**:

- **Split `test_models.py` 1:1 with the new modules.** Rejected for the
  three reasons above. Can be revisited as a follow-up if a future
  contributor finds the single file unwieldy.

---

## R5. `Model.__module__` change — any consumer affected?

**Decision**: Confirmed non-issue. No action required.

**Investigation**:

- `git grep '__module__'` against `src/`, `tests/`, `examples/`, and
  `docs/` shows zero hits that reference any model class's `__module__`
  attribute.
- The Sphinx docs config uses `automodule` against
  `pylocal_akuvox.models`, which renders members regardless of their
  `__module__` value (it walks `__all__` and the module's bound names).

**Outcome**: After the move, `User.__module__ ==
'pylocal_akuvox.models.users'` rather than `'pylocal_akuvox.models'`.
This is acceptable per spec edge-case note. No consumer relies on the
old value.

---

## R6. Pickling / serialization risk

**Decision**: Confirmed non-issue. No action required.

**Investigation**:

- `git grep -E 'pickle|cloudpickle|dill' src/ tests/ examples/` returns
  no production or test code that pickles model instances.
- `git grep -E 'shelve|joblib' src/ tests/ examples/` similarly empty.
- No cache layer in `pylocal_akuvox/` serializes dataclass instances to
  disk; everything is in-memory per request.

**Outcome**: No pickled fixtures, no on-disk caches, no shelve usage —
the `__module__` change cannot break a deserialization round-trip
because no such round-trip exists.

---

## R7. Sphinx documentation impact

**Decision**: No source-doc edit required for correctness in this
feature.

**Investigation**:

- `docs/api/models.rst` contains:
  ```rst
  .. automodule:: pylocal_akuvox.models
     :members:
     :undoc-members:
     :show-inheritance:
  ```
- `automodule` with `:members:` walks the module's `__all__` (when
  defined) or its bound names. The `models/__init__.py` shim re-exports
  the same ten public model classes and **newly introduces** an
  explicit `pylocal_akuvox.models.__all__` listing exactly those ten
  names (the pre-split `models.py` defines no `__all__` — see spec
  FR-004 and the `from pylocal_akuvox.models import *` edge case).
  Autodoc therefore walks exactly the ten names and renders the same
  classes with the same docstrings. The four accidental helper-name
  leaks (`AkuvoxParseError`, `Any`, `annotations`, `dataclass`) that
  bare star-import would expose today were never rendered by autodoc
  anyway (they have no docstrings or are imported names from other
  modules), so dropping them via the new `__all__` is invisible to the
  docs build.
- No other `.rst` file in `docs/` hard-codes a model class path; all
  cross-references go through autodoc.

**Outcome**: Docs build remains green without source-doc edits. An
optional follow-up to render per-domain pages
(`docs/api/models/users.rst`, etc.) is **out of scope** for this
feature.

---

## R8. aislop / file-size gate behavior

**Decision**: Threshold is 400 lines per file (per issue #126 text
"max: 400" / "current: 448"; `wc -l src/pylocal_akuvox/models.py` reports
447 today — the one-line delta between the issue text and the current
file is immaterial, both exceed the gate). Plan sizes every new file
with a safety margin.

**Projected line counts** (computed from current class line ranges plus
preamble of SPDX (2) + blank (1) + docstring (1) + `from __future__`
(2) + imports (~3) ≈ 9-line header):

| New file               | Classes                                | Body lines | + Header | Total est. |
|------------------------|----------------------------------------|------------|----------|------------|
| `models/device.py`     | DeviceInfo + DeviceStatus + Relay      | 106        | 9        | **~115**   |
| `models/config.py`     | DeviceConfig                           | 46         | 9        | **~55**    |
| `models/users.py`      | User                                   | 72         | 9        | **~81**    |
| `models/schedules.py`  | AccessSchedule                         | 84         | 9        | **~93**    |
| `models/groups.py`     | Group                                  | 27         | 9        | **~36**    |
| `models/logs.py`       | DoorLogEntry + CallLogEntry            | 66         | 9        | **~75**    |
| `models/contacts.py`   | Contact                                | 33         | 9        | **~42**    |
| `models/__init__.py`   | (re-exports + `__all__`)               | ~30        | 9        | **~40**    |

Every file is well under 400 (largest is ≈ 115). The user and contact
modules are 81 and 42 lines respectively — well within the ≤ 250-line
target from SC-006, leaving generous headroom for #123 (User parser
rewrite) and #121 (apartment-book fields on Contact).

---

## R9. Where will `pylocal_akuvox.capabilities` live?

**Decision** (documentation-only — no file created in this feature):
**Flat at the top level** as `pylocal_akuvox/capabilities.py`,
parallel to the existing service modules (`device.py`, `users.py`,
`schedules.py`, …).

**Rationale**:

- Capability types are cross-cutting (they describe what a device
  *can* do, used by `User.from_api_response` to pick a field alias,
  and prospectively used by every model parser). Putting them inside
  `models/` would force one domain module to claim them or invent
  a `models/capabilities.py` that other domain modules import,
  re-introducing the cross-module coupling FR-010/FR-011 are meant to
  prevent.
- The flat location keeps the parallel between service modules and
  model submodules clean: services live at the top, model dataclasses
  live in `models/`, cross-cutting concerns live at the top alongside
  services.
- This is documentation-only for this feature — no file is created, no
  import added. The location is recorded so #123 has an unambiguous
  landing site.

---

## Summary

All eight design questions raised by the spec or implied by the
codebase are resolved. The implementation phase can proceed straight to
TDD-red on `tests/unit/test_models_reexport.py` followed by the file
moves and the shim.
