<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Matrix Lookup and `DeviceClassPattern`

**Phase**: 2 (PR 2)
**Owning module**: `src/pylocal_akuvox/capability_matrix.py` plus the
matching helper `lookup_capabilities(device_info)` which lives in
`src/pylocal_akuvox/capabilities.py` (so the matrix module remains
data-only).
**Owning tests**: `tests/unit/test_matrix.py`,
`tests/unit/test_pattern.py`.

## Public surface

```python
# pylocal_akuvox/capabilities.py


@dataclass(frozen=True, kw_only=True)
class DeviceClassPattern:
    """A model-prefix + firmware-band matcher used as a matrix key."""

    model_prefix: str
    firmware_band: str

    def __post_init__(self) -> None: ...
    def matches(self, device_info: DeviceInfo) -> bool: ...


def lookup_capabilities(device_info: DeviceInfo) -> DeviceCapabilities | None:
    """Return the first matching CAPABILITY_MATRIX entry's profile, or None.

    None means the device is unrecognized; callers should fall back to a
    conservative-empty profile and direct the integrator to
    ``probe_capabilities()`` (FR-013).
    """
```

```python
# pylocal_akuvox/capability_matrix.py

CAPABILITY_MATRIX: tuple[tuple[DeviceClassPattern, DeviceCapabilities], ...] = (
    # Most-specific first.
    ...,
)
```

## `DeviceClassPattern` matching semantics

Construction (`__post_init__`) parses `firmware_band` into one of three
internal forms and raises `ValueError` if the band is malformed:

| Form  | Trigger              | Stored shape                              |
|-------|----------------------|-------------------------------------------|
| Glob  | trailing `*` segment | `_band_kind = "glob"`,  `_band_segments = (int, ..., "*")` |
| Floor | trailing `+` after a numeric segment | `_band_kind = "floor"`, `_band_floor = (int, int, int, int)` |
| Exact | otherwise            | `_band_kind = "exact"`, `_band_segments = (int, int, int, int)` |

`matches(device_info)` returns `True` iff:

1. `device_info.model.startswith(self.model_prefix)`, **and**
2. The parsed firmware version `tuple[int, ...]` from
   `device_info.firmware_version` satisfies the form-specific rule:

| Form  | Rule |
|-------|------|
| Glob  | `observed_segments[: len(_band_segments) - 1] == _band_segments[: -1]` (every non-`*` segment matches; `*` matches anything for the trailing segment). |
| Floor | `parse(observed) >= _band_floor`. Both sides padded with `0` to equal length. |
| Exact | `parse(observed) == _band_segments`. |

`parse(observed)` is `tuple(int(seg) for seg in observed.split("."))`,
discarding any non-numeric trailing label (e.g.
`"916.30.10.114-beta"` → `(916, 30, 10, 114)`). A wholly non-numeric
firmware string causes `matches` to return `False` (without raising —
unknown-format firmwares are simply non-matches, not errors).

## Lookup precedence

`lookup_capabilities(device_info)` iterates `CAPABILITY_MATRIX` in
declaration order and returns the first `(pattern, capabilities)` pair
whose `pattern.matches(device_info)` is `True`. Returns `None` if no
pattern matches.

The matrix is curated in **most-specific-first** order. A unit test
asserts that no two patterns in `CAPABILITY_MATRIX` match the same
synthetic test-device-info — i.e. there are no overlapping entries.

## Connect-time integration (in `device.py`)

`AkuvoxDevice.__aenter__` already calls `_http.__aenter__()`. Phase 2
adds, immediately after that:

```python
async def __aenter__(self) -> AkuvoxDevice:
    await self._http.__aenter__()
    info = await self.get_info()  # Existing call; KEY_DISCOVERY
    profile = lookup_capabilities(info)
    if profile is None:
        # Conservative unrecognized-device fallback (FR-013).
        # Empty `capabilities` mapping → status_of(any) returns UNKNOWN.
        profile = DeviceCapabilities(
            device_class=info.model,
            firmware_version=info.firmware_version,
            capabilities={},
            field_aliases={},
            schema_shapes={},
            notes={
                "device_not_in_matrix": (
                    "Device not in capability matrix. Call "
                    "device.probe_capabilities() to enumerate, or set "
                    "device.attempt_unknown_capability=True to opt in to "
                    "unknown-status operations."
                ),
            },
        )
    self._capabilities = profile
    return self
```

The `capabilities` read-only property exposes
`self._capabilities`. `probe_capabilities()` replaces it (with the
merge rule documented in `contracts/probe-api.md` edge case 7 — probe
results win for capabilities the probe explicitly classified; matrix
values are preserved for capabilities the probe did not exercise).

For an unrecognised device, every operation through the per-call gate
raises `AkuvoxUnsupportedError(reason="capability_unknown")` (since
`status_of(any) → UNKNOWN`) UNLESS the integrator has set
`device.attempt_unknown_capability = True`. The error message
distinguishes "device unrecognised" from "device recognised but
this capability has UNKNOWN status" by populating the message with
either `"Device {device_class} not in capability matrix; call ..."`
or `"Capability {capability.value} has UNKNOWN status on
{device_class}; ..."`. Both raises use `reason="capability_unknown"`;
the message text is the discriminator.

> **Note**: an alternate option is to use `reason="device_unrecognized"`
> for the no-matrix-match case and reserve `reason="capability_unknown"`
> for the matrix-recognised-but-UNKNOWN case. Either is acceptable per
> the contract in `contracts/unsupported-error.md`; the implementer
> chooses based on whichever gives the cleanest test fixtures.

## Provenance contract

Every entry in `CAPABILITY_MATRIX` has a non-`None` `provenance` field.
A unit test (`test_matrix.py::test_every_entry_has_provenance`) asserts
this. This is the SC-004 verification.

## Initial entries (Phase 2)

See `data-model.md` §"`CAPABILITY_MATRIX` initial entries" — four entries
covering X916, X915S (current FW), E18C (current FW), IT83. Capability
deltas listed there. Each entry's `provenance` is populated as:

| Entry | `test_bench_device_id` | `firmware_version` | `library_version` | `observed_at` |
|-------|------------------------|---------------------|--------------------|---------------|
| X916        | maintainer's bench unit | `916.30.10.114`   | (current) | 2026-06-13 |
| X915S       | maintainer's bench unit | `2915.30.10.114`  | (current) | 2026-06-13 |
| E18C        | maintainer's bench unit | `18.30.11.21`     | (current) | 2026-06-13 |
| IT83        | community-reporter unit (issue #130 / #122) | `83.30.10.4` | (current) | 2026-06-13 |

`library_version` is the `__version__` string at the commit landing the
entry, sampled from `importlib.metadata.version("pylocal-akuvox")`.

## Adding a new entry (FR-017, SC-007)

Adding support for a hypothetical new firmware band whose variation is
limited to known axes (endpoint availability, field-name aliasing,
schema shape, action availability) requires:

1. Add a new `(DeviceClassPattern(...), DeviceCapabilities(...))` tuple
   to `CAPABILITY_MATRIX` in the most-specific-first position.
2. Populate the entry's `capabilities` mapping with the per-capability
   `CapabilityStatus` values for which there is positive evidence.
   Capabilities for which there is no positive evidence either way may
   be omitted from the mapping (they default to `UNKNOWN`); maintainers
   are encouraged to omit rather than guess. Confirmed-negative
   evidence (e.g. an `unsupported action` envelope was specifically
   observed for the operation) is recorded as `UNSUPPORTED` so the
   per-call gate fails fast instead of suggesting the integrator
   opt in.
3. If the entry uses field aliases or schema shapes that already have
   matrix-language coverage (e.g. another existing entry has
   `SchemaShape.APARTMENT_BOOK`), no further code change is required.
4. If the entry uses a brand-new alias key or schema shape, add the new
   key/shape to `Capability` / `SchemaShape` and to the corresponding
   parser's known-keys list — this is **not** a Phase 3-style refactor;
   it is a one-line addition to the central enum.
5. Add a new test case in `tests/unit/test_matrix.py` asserting the
   entry's provenance and selected capability deltas.
6. Update `docs/api/capabilities.rst` to mention the new device class
   (the consistency test in `test_docs_matrix_consistency.py` will fail
   the build if you forget).

## Probe-vs-matrix interaction (cross-reference)

When the integrator explicitly calls `probe_capabilities()` against a
device that also has a matrix entry, the **9-cell merge table** in
`contracts/probe-api.md` §"Edge cases" item 7 applies. Reproduced
here for convenience:

| Probe \ Matrix     | `SUPPORTED`               | `UNSUPPORTED`               | `UNKNOWN` (or absent) |
|--------------------|---------------------------|------------------------------|------------------------|
| **`SUPPORTED`**    | `SUPPORTED` (probe wins)  | `SUPPORTED` (probe wins; newer evidence) | `SUPPORTED` (probe wins) |
| **`UNSUPPORTED`**  | `UNSUPPORTED` (probe wins; newer evidence) | `UNSUPPORTED` (probe wins) | `UNSUPPORTED` (probe wins) |
| **`UNKNOWN`**      | **`SUPPORTED`** (matrix preserved) | **`UNSUPPORTED`** (matrix preserved) | `UNKNOWN` |

Driving principle: **probe `UNKNOWN` never regresses a
matrix-confirmed status** (absence of evidence is not evidence of
absence); **probe `SUPPORTED`/`UNSUPPORTED` always wins** as newer
first-hand observation. This satisfies FR-009 ("probe results take
precedence over matrix defaults") for the read paths the probe
explicitly classifies, while preserving the matrix's authoritative
knowledge of write behaviour — and of any read capability the probe
could not classify on this run (HTTP 500, transient 4xx, etc.) — on
recognised devices. Capabilities the probe did not touch at all are
merge-irrelevant; the matrix value carries through unchanged.

## Out-of-scope

- Hot-reload of the matrix at runtime.
- Persisting probe results into the matrix (out-of-scope per spec
  out-of-scope item 3).
- Vendor-doc-driven matrix entries (the matrix is grounded in observed
  device behavior).
