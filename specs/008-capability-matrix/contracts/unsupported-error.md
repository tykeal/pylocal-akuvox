<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: `AkuvoxUnsupportedError` (Structured Form)

**Phase**: 2 (PR 2) — additive evolution of the existing class
**Owning module**: `src/pylocal_akuvox/exceptions.py`
**Owning tests**: `tests/unit/test_unsupported_error.py` and the
unchanged `tests/unit/test_http.py::test_unsupported_api_raises_unsupported_error`
(line ~223) and `tests/unit/test_exceptions.py:57`.

## Pre-Phase-2 form (current code, kept working)

```python
class AkuvoxUnsupportedError(AkuvoxError):
    """API endpoint not supported by the device firmware."""
```

Single existing call site:
`src/pylocal_akuvox/_http.py:201` →
`raise AkuvoxUnsupportedError(message)`.

Existing tests:

- `tests/unit/test_exceptions.py:57` — asserts isinstance + message.
- `tests/unit/test_http.py::test_unsupported_api_raises_unsupported_error`
  (line ~223) — asserts the `_http.py` raise on
  envelope `"Api unsupported"`.

Both MUST continue to pass without modification (FR-016 spirit applied
to the exception surface; UX consistency principle III).

## Post-Phase-2 form

```python
class AkuvoxUnsupportedError(AkuvoxError):
    """Operation unsupported by the connected device.

    Carries optional structured fields when raised from the
    capability-aware surfacing layer; falls back to a message-only form
    when raised from the legacy HTTP-envelope classifier in ``_http.py``.

    Attributes:
        capability: The Capability whose absence triggered this error,
            or None when raised from a layer without capability context.
        device_class: The detected device class string (e.g. "IT83"),
            or None if unrecognized at the time of the raise.
        reason: Structured reason code. One of:
            - "capability_missing": the matrix or probe records this
              capability with status ``UNSUPPORTED`` for this device
              (confirmed-negative evidence).
            - "capability_unknown": the matrix or probe records this
              capability with status ``UNKNOWN`` for this device (no
              positive evidence either way) and the caller has not
              opted in via ``device.attempt_unknown_capability=True``.
              This is the new reason introduced by the three-valued
              status model in ``research.md`` Decision 2.
            - "device_unrecognized": no matrix entry matched and the
              caller has not yet probed; direct them to
              ``probe_capabilities()``. Functionally similar to
              ``capability_unknown`` (the unrecognised-device profile
              has every capability at ``UNKNOWN``), but kept as a
              separate reason so the message can be specifically
              actionable ("the device class itself is not in the
              matrix" vs. "the device is recognised but this
              specific capability has unknown status"). Implementer
              may choose to fold both into ``capability_unknown`` if
              the resulting test fixtures are simpler.
            - "adapter_missing": the capability is supported but no
              adapter is registered for the device's variant of it
              (distinguishes "device cannot do this" from "library does
              not yet implement this for this device class" per spec
              edge case "Adapter dispatch with no matching adapter").
            - "envelope_unsupported": the device returned the
              well-known ``Api unsupported`` envelope at runtime, even
              though the matrix said the capability was supported, OR
              the integrator opted in via
              ``attempt_unknown_capability`` and the runtime attempt
              landed on the well-known unsupported envelope. Used by
              the legacy ``_http.py`` raise; useful as a probe-vs-
              matrix staleness signal and as the post-hoc
              classification of opt-in attempts on UNKNOWN
              capabilities.
            - None: legacy raise from a code path without context
              (preserves backward compatibility with single-arg
              construction).

    """

    def __init__(
        self,
        message: str,
        *,
        capability: Capability | None = None,
        device_class: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.capability = capability
        self.device_class = device_class
        self.reason = reason
```

## Backward-compatibility guarantees

1. `AkuvoxUnsupportedError(msg)` continues to construct an instance with
   `.args == (msg,)`, `str(exc) == msg`, and
   `exc.capability is exc.device_class is exc.reason is None`.
2. The existing import path
   `from pylocal_akuvox.exceptions import AkuvoxUnsupportedError`
   continues to resolve to the *same Python class object* — Phase 2 does
   **not** redefine the class in a different module, replace it with a
   subclass, or wrap it.
3. The `pylocal_akuvox.AkuvoxUnsupportedError` re-export at
   `__init__.py:17,49` is unchanged.
4. `isinstance(exc, AkuvoxError)` continues to be `True` (parent class
   unchanged).

## Reason taxonomy (closed set)

Reason values are a closed set, validated by the test suite:

```python
{
    "capability_missing",
    "capability_unknown",
    "device_unrecognized",
    "adapter_missing",
    "envelope_unsupported",
    None,
}
```

A test in `test_unsupported_error.py` enumerates this set and ensures
no production raise uses an off-list string. Adding a new reason
requires updating the docstring AND this test.

## Raise-site contract

| Site | Reason | `capability` | `device_class` | Message format |
|------|--------|--------------|-----------------|----------------|
| `device.py` per-method gate (`require()`), capability status is `UNSUPPORTED` | `"capability_missing"` | the missing `Capability` | from effective profile | `"Device class {device_class} does not support {capability.value}"` |
| `device.py` per-method gate (`require()`), capability status is `UNKNOWN` and `attempt_unknown_capability` is `False` | `"capability_unknown"` | the unknown `Capability` | from effective profile | `"Capability {capability.value} has unknown status on {device_class}; add a matrix entry or set device.attempt_unknown_capability=True to opt in"` |
| `device.py` per-method gate against an unrecognised-device profile (no matrix match, no probe) | `"device_unrecognized"` | the requested `Capability` | observed device class | `"Device {device_class} not in capability matrix; call device.probe_capabilities() to enumerate, or set device.attempt_unknown_capability=True to opt in"` |
| `device.py` adapter dispatch with no adapter for the device's variant | `"adapter_missing"` | the variant `Capability` (e.g. `RELAY_TRIGGER_FCGI`) | from effective profile | `"No adapter registered for {capability.value} on {device_class}"` |
| `_http.py:201` (legacy envelope) | `"envelope_unsupported"` (Phase 2 may pass this kwarg explicitly when raising) | `None` (HTTP layer has no capability context) | `None` | the device's `message` string verbatim |

The implementer may choose to fold the `device_unrecognized` row into
the `capability_unknown` row (returning `reason="capability_unknown"`
in both cases, with the message text discriminating). Either
implementation satisfies the contract; the closed-set test in
`test_unsupported_error.py` accepts both reasons.

The legacy `_http.py:201` raise MAY be enriched in Phase 2 to pass
`reason="envelope_unsupported"`, but is not required to. The default
`None` is acceptable; the existing test only asserts the exception
class, not the reason field.

## What `__init__.py:17,49` exports

```python
from pylocal_akuvox.exceptions import (
    ...,
    AkuvoxUnsupportedError,
    ...,
)

__all__: list[str] = [
    ...,
    "AkuvoxUnsupportedError",
    ...,
]
```

UNCHANGED. The structured fields are accessed off the existing exported
class.

## Test coverage required (Phase 2)

`tests/unit/test_unsupported_error.py` adds:

1. `test_default_constructor_message_only` — `AkuvoxUnsupportedError("x")`
   yields `.capability is None`, `.device_class is None`,
   `.reason is None`, `str(exc) == "x"`.
2. `test_structured_constructor_capability_missing` — every kwarg
   round-trips.
3. `test_structured_constructor_capability_unknown` — the new
   three-valued status reason round-trips identically to
   `capability_missing`.
4. `test_reason_taxonomy_closed` — production raises only use values in
   the documented closed set (which now includes
   `capability_unknown`).
5. `test_isinstance_akuvox_error` — class hierarchy preserved.

Not added (intentionally): a test that asserts the legacy `_http.py`
raise *does* pass `reason="envelope_unsupported"`. The contract leaves
that optional.
