<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: `run_capability_report()` public API

**Feature**: `014-capability-report-api` | **Date**: 2026-07-01
**Plan**: [../plan.md](../plan.md) | **Spec**: [../spec.md](../spec.md)

The observable contract for the extracted public API. Symbol names for the
internal modules are finalized in `tasks.md`; the **observable** signature,
behaviour, and return shape below are fixed by the spec and this plan.

## Public surface

```python
# Importable from the package root:
from pylocal_akuvox import run_capability_report

async def run_capability_report(
    device: AkuvoxDevice,
    *,
    write: bool = False,
    open_door: bool = False,
    open_door_user: str | None = None,
    open_door_password: str | None = None,
    timeout: float | None = None,
    redact_stdout: bool = False,
    emit: Callable[[str], None] | None = None,
) -> dict[str, object]: ...
```

## Parameters

| Param | Default | Meaning |
|---|---|---|
| `device` | — | An `AkuvoxDevice` used as the connection template; the API opens its own diagnostic child connections for probe, write, and read passes (Clarification 2). |
| `write` | `False` | `False` → read-only, **zero** create/modify/delete requests (FR-004). `True` → full CRUD suite against throwaway entities + cleanup (FR-005). |
| `open_door` | `False` | Opt into the physical OpenDoor relay test. Requires `write=True` **and** both credentials to actuate (FR-006). |
| `open_door_user` | `None` | OpenDoor relay username (Clarification 1). |
| `open_door_password` | `None` | OpenDoor relay password, passed programmatically; **never** read from env by the library (Clarification 1). |
| `timeout` | `None` | Caller-supplied request timeout; falls back to the device's timeout when `None` (FR-010). |
| `redact_stdout` | `False` | Display-only seam mirroring the CLI `--redact-stdout`: field-aware in-string redaction of emitted lines; **never** affects the returned report, which is always fully redacted. |
| `emit` | `None` | Console-emitter seam. `None` → **silent** (library is quiet). The CLI passes a `print`-based emitter for byte-identical stdout. |

## Returns

A JSON-serializable `dict` — **always** the fuller report structure
(`device` / `auth` / `observed_schemas` / `tests`, with `http_events` nested
per test), in **both** read-only and write modes (Clarification 5). Never the
`DeviceCapabilities` profile. Full schema:
[report-json-schema.md](./report-json-schema.md).

## Behavioural guarantees

1. **Read-only default** — `write=False` issues no create/modify/delete
   requests and reuses `AkuvoxDevice.probe_capabilities()` for discovery
   (FR-004); it does **not** reimplement the 9-call probe.
2. **Write evidence + cleanup** — `write=True` records add/modify/delete
   `capability_status` evidence for user, schedule, group, and contact, and
   deletes every throwaway entity it created on success (SC-004); dependent
   steps skip when their parent `add_*` fails or is skipped (FR-009).
3. **OpenDoor safety** — the relay actuates **iff** `open_door=True`,
   `write=True`, **and** both credentials are supplied (FR-006). Otherwise
   the step is skipped with the CLI's exact skip reason and no actuation
   (FR-007). When `open_door=True` but `write=False` the library **skips**
   OpenDoor (never actuates) rather than raising — consistent with the
   skip-never-actuate safety model; the **CLI** keeps its stricter
   `--open-door requires --write` `parser.error` guard as a CLI-layer
   concern (resolves the US3-scenario-4 inline marker).
4. **Redaction** — the returned structure is unconditionally redacted
   (FR-003): each `body_snippet` is a clipped, redacted JSON **string**
   (every parsed leaf `"<redacted>"`), `host` `"<redacted>"`, successful
   bodies omitted, non-JSON/scalar sentinels, no secrets anywhere.
5. **Capability gating** — consults the shared probe-merged
   `DeviceCapabilities`; `UNSUPPORTED` / `UNKNOWN` steps skip; honors
   `attempt_unknown_capability` from the caller's device (FR-008).
6. **Error propagation** — auth/connection/parse errors the CLI surfaces
   propagate unchanged (FR-015); no half-built report is returned when the
   probe aborts at step 1.
7. **Connection ownership** — the API opens its own short-lived,
   diagnostic-instrumented connections (one per write CRUD group + settle
   pause) to preserve the E18 CGI-state workaround (Clarification 2).
8. **Quiet by default** — with `emit=None` the library prints nothing; the
   JSON report and return value are independent of `emit`.
9. **Display-only stdout redaction** — `redact_stdout` is orthogonal to the
   returned report and only changes values sent through `emit`.

## Invariants preserved (FR-014)

- `probe_capabilities()` behaviour and output shape are unchanged.
- The report JSON schema is unchanged (this contract == live `to_json()`).
- The redaction policy is unchanged.

## CLI parity (FR-011/FR-012/SC-002)

`examples/mvp_test.py` derives its report solely from this function. For the
same device interactions the CLI's `--json-report` output and stdout are
**byte-identical** before and after the extraction. There is no second copy
of the report/step/redaction logic.
