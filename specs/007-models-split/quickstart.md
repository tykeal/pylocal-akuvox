# Quickstart — 007-models-split

**Purpose**: Reviewer / maintainer verification recipe. Run these checks on the
`007-models-split` branch (post-implementation) to confirm the refactor is a
pure structural move with no behavior, public-API, or quality-gate regression.

Run all commands from the repository root.

---

## 0. Prerequisites

```bash
# Sync the locked dev environment (per AGENTS.md / pyproject.toml)
uv sync --all-extras --all-groups
```

---

## 1. Verify the new package layout exists

```bash
ls src/pylocal_akuvox/models/
```

Expected output (exactly these files; alphabetical order may vary):

```text
__init__.py  config.py  contacts.py  device.py  groups.py  logs.py  schedules.py  users.py
```

```bash
test ! -e src/pylocal_akuvox/models.py && echo "OK: monolith deleted"
```

Expected: `OK: monolith deleted` — the old single-file `models.py` is gone
(replaced by the `models/` package).

---

## 2. Verify file-size compliance (FR-005, SC-001)

```bash
wc -l src/pylocal_akuvox/models/*.py
```

Every file must be ≤ 400 lines. The user and contact submodules should be
≤ 250 lines (SC-006).

**aislop note**: aislop is an external code-review tool that originally
surfaced the 400-line warning on `models.py` via issue #126; it is **not**
wired into this project's local lint config (`ruff.toml`) or CI workflows
(`.github/workflows/`). Verification reduces to: (a) `models.py` no longer
exists, so the previously-reported warning has nowhere to attach; and
(b) `wc -l` above shows every new file well under 400 lines. If aislop is
re-run externally on this branch, no `complexity/file-too-large` warnings
should appear under `src/pylocal_akuvox/models/`.

---

## 3. Verify import compatibility (FR-001, FR-003, FR-004, SC-002)

```bash
uv run python -c "
import pylocal_akuvox
from pylocal_akuvox.models import (
    AccessSchedule, CallLogEntry, Contact, DeviceConfig, DeviceInfo,
    DeviceStatus, DoorLogEntry, Group, Relay, User,
)
expected = [
    'AccessSchedule', 'CallLogEntry', 'Contact', 'DeviceConfig',
    'DeviceInfo', 'DeviceStatus', 'DoorLogEntry', 'Group', 'Relay', 'User',
]
import pylocal_akuvox.models as shim
assert sorted(shim.__all__) == expected, shim.__all__
for n in expected:
    assert n in pylocal_akuvox.__all__, n
print('OK: all ten public names import; __all__ stable')
"
```

Expected: `OK: all ten public names import; __all__ stable`.

---

## 4. Verify class identity through the shim (FR-002)

```bash
uv run python -c "
from pylocal_akuvox.models import User, Contact, DeviceInfo, DeviceStatus, Relay
from pylocal_akuvox.models import DeviceConfig, Group, AccessSchedule
from pylocal_akuvox.models import DoorLogEntry, CallLogEntry
from pylocal_akuvox.models import users, contacts, device, config, groups, schedules, logs
assert User is users.User
assert Contact is contacts.Contact
assert DeviceInfo is device.DeviceInfo
assert DeviceStatus is device.DeviceStatus
assert Relay is device.Relay
assert DeviceConfig is config.DeviceConfig
assert Group is groups.Group
assert AccessSchedule is schedules.AccessSchedule
assert DoorLogEntry is logs.DoorLogEntry
assert CallLogEntry is logs.CallLogEntry
print('OK: shim re-exports same class objects (isinstance/identity preserved)')
"
```

Expected: `OK: shim re-exports same class objects (isinstance/identity preserved)`.

---

## 5. Verify star-import behavior (FR-004 edge case)

```bash
uv run python -c "
ns = {}
exec('from pylocal_akuvox.models import *', ns)
imported = sorted(k for k in ns if not k.startswith('_'))
expected = ['AccessSchedule', 'CallLogEntry', 'Contact', 'DeviceConfig',
            'DeviceInfo', 'DeviceStatus', 'DoorLogEntry', 'Group', 'Relay', 'User']
assert imported == expected, imported
print('OK: star-import yields exactly the ten public names')
"
```

Expected: `OK: star-import yields exactly the ten public names`.

**Note**: The pre-split `models.py` has no `__all__`, so star-imports
today leak four extra names (`AkuvoxParseError`, `Any`, `annotations`,
`dataclass`). The new shim's explicit `__all__` drops those leaks — this
is a deliberate clarification of the public contract per FR-004, not a
regression. To confirm there are no in-repo star-import consumers that
depended on the leaks:

```bash
git grep -nE "from pylocal_akuvox\.models import \*" -- src/ tests/ examples/ docs/
```

Expected: **no output** (no in-repo consumer uses `import *` against
this module).

---

## 6. Run the full quality gate (FR-013, SC-004)

Run each command and confirm a clean exit:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run interrogate
uv run reuse lint
uv run --extra docs sphinx-build -W -b html docs docs/_build/html
```

Expected: each command exits 0 with no new warnings or errors compared to
`main`. In particular:

- `pytest` — full suite (including the existing `tests/unit/test_models.py`
  and the new `tests/unit/test_models_reexport.py`) passes with zero
  failures, zero skips compared to baseline.
- `ruff check` — no new lint errors, no new `C901` complexity violations.
- `ruff format --check` — formatting is clean.
- `mypy` — no new type errors (the moved dataclasses keep their original
  type annotations).
- `interrogate` — every new module and class has a docstring (preserved
  from the original).
- `reuse lint` — every new `.py` file carries the SPDX header pair and the
  REUSE compliance check passes.
- `sphinx-build -W` — docs build is clean (warnings promoted to errors).
  Confirms that `docs/api/models.rst`'s `automodule pylocal_akuvox.models`
  directive still resolves the ten model classes through the new shim
  (spec edge case "Sphinx / docs cross-references").

---

## 7. Verify coverage non-regression (SC-005)

```bash
uv run pytest -q
uv run coverage report --include='src/pylocal_akuvox/models/*'
```

Compare the single aggregate **Cover %** reported by
`coverage report --include='src/pylocal_akuvox/models/*'` against the
pre-split baseline (the same command on `main` reports
`src/pylocal_akuvox/models.py 240 0 32 0 100%` — i.e. 100%). The
post-split aggregate (now spanning the eight files inside the new
`models/` package) MUST be ≥ baseline. A small *increase* is acceptable
(the new re-export contract test adds coverage on the new shim
`__init__.py`).

Per-class numbers are not required — the aggregate is the enforceable
measurement. Because the moved classes are unchanged bytes-for-bytes,
the only way the aggregate can regress is via an uncovered line in the
new shim, and the T015 contract test already covers it. If `coverage.xml`
is produced by CI, diffing the pre- and post-refactor reports is the
most precise check.

---

## 8. Confirm zero downstream import edits required (SC-003)

```bash
git diff main \
    -- 'src/' 'tests/' 'examples/' 'docs/' \
       ':!src/pylocal_akuvox/models/**' \
       ':!specs/**' \
       ':!tests/unit/test_models_reexport.py' \
    | grep -E '^[-+].*from pylocal_akuvox\.models' \
    | grep -v '^[-+]\{3\}'
```

Expected: **no output** (no added or removed `from pylocal_akuvox.models …`
lines in any consumer file). The pathspec exclusions are necessary because
without them the grep would falsely flag two sources of *expected* churn:
the new shim's own `from pylocal_akuvox.models.<sub> import …` lines
inside `src/pylocal_akuvox/models/__init__.py`, and the new TDD contract
test's submodule imports inside `tests/unit/test_models_reexport.py`.
Both are part of *introducing* the contract, not signs of a downstream
break. Step 9 below verifies the shim's own re-export block is correctly
populated.

---

## 9. Confirm the shim's re-export imports are exactly the seven expected submodule lines

```bash
git diff main -- src/pylocal_akuvox/models/__init__.py \
    | grep -E '^\+from pylocal_akuvox.models\.'
```

Expected: exactly seven `+from pylocal_akuvox.models.<submodule> import …`
lines (one per domain submodule: `config`, `contacts`, `device`, `groups`,
`logs`, `schedules`, `users`), all inside `models/__init__.py`. This step
verifies that the **shim's own** re-export block is correctly populated;
it intentionally does NOT scan the rest of the tree because the new TDD
contract test (`tests/unit/test_models_reexport.py`) legitimately adds
similar `from pylocal_akuvox.models import <sub> as <sub>_mod` lines per
`contracts/import-contract.md` §3, and those are part of *introducing*
the contract, not signs of a downstream regression. Step 8 already
confirmed no consumer code outside the shim and the contract test added
or removed any `from pylocal_akuvox.models …` imports, which together
with this step closes the loop.

---

## 10. Confirm domain submodules have no cross-module re-export imports (FR-010, FR-011)

```bash
grep -nE "from pylocal_akuvox\.models($|[. ])|from pylocal_akuvox\.models import" \
    src/pylocal_akuvox/models/*.py
```

Expected: the only matches are inside `models/__init__.py`. No domain
submodule (`device.py`, `users.py`, …) imports from the shim or from a
sibling submodule. They should only import from stdlib and
`pylocal_akuvox.exceptions`.

---

## 11. Spot-check end-to-end behavior

```bash
uv run python -c "
from pylocal_akuvox.models import User, Contact, AccessSchedule
# Same parsing behavior as pre-split
u = User.from_api_response({'Name': 'a', 'UserID': '1', 'ScheduleRelay': '1001'})
assert u.name == 'a' and u.user_id == '1' and u.schedule_relay == '1001'
c = Contact.from_api_response({'Name': 'b'})
assert c.name == 'b' and c.phone is None and c.group is None
print('OK: parsing behavior unchanged for spot-checked classes')
"
```

Expected: `OK: parsing behavior unchanged for spot-checked classes`.

---

## Success Criteria recap

If all eleven steps above pass without modification, every spec success
criterion (SC-001 through SC-007) is satisfied:

- SC-001 — step 2 (file sizes + aislop)
- SC-002 — steps 3 & 4 (importability + class identity)
- SC-003 — step 8 (zero downstream edits required)
- SC-004 — step 6 (full quality gate)
- SC-005 — step 7 (coverage non-regression)
- SC-006 — step 2 (user & contact modules ≤ 250 lines)
- SC-007 — step 1 (layout is intuitive at-a-glance from filenames alone)
