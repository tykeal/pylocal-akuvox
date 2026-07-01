<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Research: Capability Report API

**Feature**: `014-capability-report-api` | **Date**: 2026-07-01
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

This document records the design decisions that resolve the five
[NEEDS CLARIFICATION] markers the spec deferred to planning, plus the
live-source verification the extraction depends on. Format per decision:
**Decision → Rationale → Alternatives considered**.

## Decision 1 — OpenDoor credential-passing shape (resolves Clarification 1)

**Decision**: `run_capability_report` accepts two explicit keyword
parameters — `open_door_user: str | None = None` and
`open_door_password: str | None = None`. The **library never reads
`os.environ`**. The CLI keeps `--open-door-user`, `--open-door-pass`, and
the `AKUVOX_OPEN_DOOR_PASSWORD` fallback, resolves both values in
`_validate_open_door_args()` / `main()` exactly as today, and passes the two
resolved strings to the API.

**Rationale**:

- The HA service must pass **both** credentials programmatically; a library
  that reads process env is wrong for an in-process caller and couples the
  package to a CLI-only convention (the spec explicitly keeps env resolution
  in the CLI wrapper).
- Two scalars map one-to-one onto the CLI's two flags and onto the existing
  `AkuvoxDevice.open_door_http(user=, password=)` signature (verified
  `device.py:204`), so the wrapper is a trivial pass-through — byte-identity
  is preserved for free.
- The password stays out of any recorded body excerpt (redaction) and out of
  the report (FR-003 / Security Considerations).

**Alternatives considered**:

- **Single credentials object/tuple** — rejected: over-engineered for two
  strings and asymmetric with the existing `open_door_http` signature.
- **Read password from the environment inside the library** — rejected:
  insufficient for HA (which has no CLI env), and pushes env policy into the
  package when the spec makes env resolution a CLI concern.

## Decision 2 — Entered device vs. opens-its-own-connections (resolves Clarification 2)

**Decision**: **Hybrid (option c).** The API accepts an already-entered
`AkuvoxDevice` and **owns the connection lifecycle for the run**: it derives
a connection spec from the entered device and internally opens its own
short-lived, diagnostic-instrumented connections for the one-time probe,
**each** write CRUD group, and the read pass — preserving one connection per
CRUD group with a `_MUTATION_SETTLE_SECS` settle pause. The entered device
is the connection **template** and the source of
`attempt_unknown_capability`.

**Rationale** (verified against `examples/mvp_test.py`):

- `run_all()` (`~2129`) builds `device_kwargs` and calls
  `_probe_device_capabilities(device_kwargs, …)` (`~2225`), which opens its
  **own** short-lived `create_device(...)` connection just for the probe.
- `_run_write_tests(device_kwargs, …)` (`~1822`) opens **four** separate
  `async with create_device(device_kwargs, …)` connections — (1) user
  add/modify/delete/verify; (2) schedule + relay trigger + OpenDoor + config
  set; (3) group; (4) contact — with `await asyncio.sleep(_MUTATION_SETTLE_SECS * 3)`
  cooldowns between them.
- `_run_read_tests(device, …)` (`~1641`) runs on a **fifth** connection
  opened in `run_all()`.
- The multi-connection-per-group design is an explicit workaround for the
  E18 `18.30.10.72` firmware bug where rapid successive requests corrupt
  internal CGI state and silently drop mutations (comment at `~2170`). A
  single persistent connection would make write-mode **silently fail on real
  hardware**.

Therefore the API cannot run write-mode on one caller-held connection; it
**must** own connections. Accepting an entered device (not raw params)
matches the issue sketch, matches how the HA integration holds its device,
and lets read-only mode reuse the device's probe naturally.

The connection spec (host, auth, timeout, use_ssl, verify_ssl,
request_delay) currently lives on the private `AkuvoxDevice._http`
(`AkuvoxHttpClient`, verified `device.py:66`). The implementation obtains it
via a small **private** accessor (or a `# noqa: SLF001` read, as the CLI's
`_instrument_device` already does at `mvp_test.py:910`); this does not change
any public contract (FR-014).

**Alternatives considered**:

- **(a) Entered device + integration owns a single connection** — rejected:
  breaks write-mode on real E18 firmware; the reconnect-per-group + settle
  pause is load-bearing, not incidental.
- **(b) API takes raw connection parameters instead of a device** —
  rejected: contradicts the issue's "already-entered `AkuvoxDevice`" sketch,
  forces the HA integration to decompose the device it already holds, and
  loses the natural read-only probe reuse.

## Decision 3 — Partial-failure cleanup / idempotency (resolves Clarification 3)

**Decision**: Preserve the CLI's per-step-delete behaviour as the shared,
**byte-identical** contract (each `delete_*` is a recorded diagnostic step),
and add a **best-effort teardown guard** per write CRUD group that is a
**no-op on the happy path** and fires only on an abnormal abort.

**Rationale** (verified against `_run_write_tests`):

- The dependency design already attempts `delete_*` for **every** entity
  whose `add_*` succeeded, **regardless** of the `modify_*` outcome: after a
  successful add, the code runs `modify_*` then `delete_*` unconditionally,
  gating only `verify_*_deletion` on `was_passed("delete_*")` (e.g.
  `mvp_test.py:1862-1891`). So a failed modify does **not** orphan the
  entity — its delete is still attempted.
- The only residue paths are (i) `delete_*` itself fails, or (ii) a
  connection/auth error escapes the group mid-chain. In the CLI, (ii) is
  caught by `run_all()`'s `except` blocks, which `sys.exit(1)` **before**
  the `--json-report` is written (`mvp_test.py:2206-2222`) — so no report is
  produced to compare.
- The best-effort guard therefore: tracks created IDs; on group teardown, if
  the normal `delete_*` did not confirm removal, issues one final best-effort
  delete. On the happy path the entity is already gone → guard is a **no-op**
  → the report is byte-identical. It only acts in the abnormal path, where
  the CLI writes no comparable report anyway.

This gives the API boundary an honest **best-effort "no orphaned throwaway
entities"** guarantee (SC-004) without violating byte-identity
(FR-012/SC-002). Throwaway entities keep their fixed recognizable names
(`pylocal-test`, UserID `9999`, verified `mvp_test.py:1286-1288`) so any
residue is identifiable and manually removable — identical to today.

**Alternatives considered**:

- **Strong transactional / guaranteed teardown** — rejected: no device
  transactional primitive exists, and output-visible teardown deletes would
  break byte-identity.
- **Preserve as-is with no guard** — rejected: leaves the API boundary
  silent about cleanup, which the downstream HA service needs stated
  explicitly.

## Decision 4 — Module / documentation placement (resolves Clarification 4)

**Decision**: Extract into **underscore-prefixed sibling module(s)** under
`src/pylocal_akuvox/` and re-export **only** `run_capability_report` from
`__init__.py` / `__all__`. Proposed split:
`_capability_report.py` (public function + orchestrator + connection
ownership), `_diagnostic_report.py` (report dataclasses + redaction),
`_report_steps.py` (step framework + `test_*` bodies + write suite). Docs:
new page `docs/api/report.rst`, cross-linked from `capabilities.rst` and
added to the `docs/api/` toctree.

**Rationale**:

- AGENTS.md "Refactor & Module-Layout Conventions" mandate
  underscore-prefixed sibling modules (not a package), the public symbol
  living at its stable path, and a single owned module-layout test.
- Precedent: the probe split — `_capability_probe.py`,
  `_probe_classifiers.py`, `_probe_parsers.py`, `_probe_outcomes.py` — with
  the public handle exposed via `AkuvoxDevice.probe_capabilities()` (verified
  `_capability_probe.py` header and `device.py:17`). `run_capability_report`
  follows the same pattern: internals underscore-prefixed, public re-export
  in `__init__`.
- `docs/api/capabilities.rst` documents the read-only probe and matrix
  contribution workflow; the write-capable, redaction-bearing, OpenDoor-
  gated report is a distinct concern and earns its own page (FR-013).

**Alternatives considered**:

- **A single public `capability_report.py` module** — rejected: a public
  submodule path violates the underscore-prefixed convention; the public
  symbol belongs in `__init__`.
- **Extend `capabilities.rst` only** — rejected: overloads a read-only-probe
  page with a write-capable concern; a dedicated page reads better and keeps
  the OpenDoor safety note prominent.

## Decision 5 — Read-only return-shape parity (resolves Clarification 5)

**Decision**: `run_capability_report` **always** returns the fuller
`DiagnosticReport.to_json()` dict (`device` / `auth` / `observed_schemas` /
`tests` with nested `http_events`) in both modes — never the
`DeviceCapabilities` profile. Read-only mode reuses
`device.probe_capabilities()` internally for discovery, then runs the read
suite to populate `observed_schemas` and per-test records.

**Rationale**:

- Verified: `DiagnosticReport.to_json()` (`mvp_test.py:369`) returns exactly
  the four-key structure; the CLI's `--json-report` in read-only mode
  already emits it. `DeviceCapabilities` is a different, frozen profile
  returned by the probe for capability discovery only.
- A single return type serves both modes and both consumers; the report — not
  the profile — is the artifact pasted into the `new_device` template.
- `probe_capabilities()`'s own contract (returning `DeviceCapabilities` to
  its direct callers) is untouched (FR-014, Out of Scope).

**Alternatives considered**:

- **Return `DeviceCapabilities` in read-only mode** — rejected: diverges the
  two modes' return types, breaks the "one artifact consumers paste" goal,
  and duplicates what `probe_capabilities()` already provides publicly.

## Design decision (non-clarification) — Console emitter seam

`mvp_test.py` prints from `run_all`, `_run_*_tests`, the `step` framework,
and every `test_*` body (e.g. `print_header`, `OK:`/`SKIP:`/`✗` lines). A
library must not print by default, yet US5 requires **unchanged** CLI stdout.
Resolution: thread one injected emitter `emit: Callable[[str], None]` through
the extracted core (carried on `TestResults`, passed to the step/`test_*`
helpers). `run_capability_report` defaults `emit` to a **silent sink**; the
CLI passes an emitter that calls `print(...)`, reproducing byte-identical
stdout. `write_json`, argparse, `getpass`, env resolution, and `sys.exit`
stay in the CLI. The JSON report and return value are independent of `emit`.

## Source verification

Symbols and behaviours confirmed against the live source before designing:

| Claim | Verified location |
|---|---|
| `DiagnosticReport.to_json()` → four top-level keys, `tests[]` from records | `examples/mvp_test.py:369-388` |
| `http_events` nested **inside** each test record (not top-level) | `DiagnosticTestRecord.to_json()` `~252`; issue shorthand is wrong |
| Redaction: `_REDACTED_VALUE`, `_redact_json_values`, `_redact_sensitive_value`, `_failure_body_snippet`, `_SENSITIVE_FIELD_MARKERS`, non-JSON/scalar sentinels | `examples/mvp_test.py:92-112, 600-651` |
| `host` always `"<redacted>"` in the report | `examples/mvp_test.py:376` |
| Step framework: `TestResults`, `step`, `skip_step`, `run_step`, `_effective_status`, `_record_capability_skip` | `examples/mvp_test.py:437-800` |
| Probe once + thread profile: `_probe_device_capabilities`, `_install_probed_capabilities` | `examples/mvp_test.py:879-896, 2225-2244` |
| Write suite opens one connection per CRUD group + settle pauses | `examples/mvp_test.py:1845, 1897, 1984, 2025` + `asyncio.sleep(_MUTATION_SETTLE_SECS * 3)` |
| OpenDoor opt-in: `_run_open_door_write_step`, `test_open_door`, `_open_door_skip_reason`, `_validate_open_door_args`, `AKUVOX_OPEN_DOOR_PASSWORD` | `examples/mvp_test.py:95, 1359-1378, 2077-2126` |
| CLI derives report; `run_all` catches errors then `sys.exit(1)` before writing JSON | `examples/mvp_test.py:2129-2222` |
| Read-only probe reused (do not reimplement) | `src/pylocal_akuvox/_capability_probe.py`; `AkuvoxDevice.probe_capabilities()` `device.py:95-105` |
| `AkuvoxDevice.open_door_http(user=, password=)` signature | `src/pylocal_akuvox/device.py:204` |
| Connection params live on private `_http` (`AkuvoxHttpClient`) | `src/pylocal_akuvox/device.py:66-73` |
| `__all__` in `__init__` (where `run_capability_report` is added) | `src/pylocal_akuvox/__init__.py:49-75` |
| Existing tests import `examples.mvp_test` and monkeypatch its `test_*` symbols | `tests/unit/test_mvp_test.py:12, 236-243` |

### Live-source corrections to planning-doc / issue assumptions

- **`http_events` is NOT a top-level report key.** Issue #208's schema
  shorthand lists it top-level; the live `to_json()` nests it inside each
  `tests[]` record. The extraction preserves the **nested** shape.
- **There is no single long-lived "entered device" for the whole CLI run.**
  The issue sketches an "already-entered `AkuvoxDevice`", but `run_all()`
  actually opens 1 (probe) + up to 4 (write groups) + 1 (read) short-lived
  connections. Decision 2's hybrid reconciles the issue's mental model with
  this reality: the API accepts an entered device but owns its own
  connections.
- **Connection parameters are private.** They live on
  `AkuvoxDevice._http`, not as public attributes, so re-opening connections
  from an entered device needs a private accessor / `# noqa: SLF001` read —
  noted so the implementation does not assume a public getter exists.
- **Existing tests monkeypatch module-level `test_*` functions on
  `mvp_test`.** After extraction those symbols live in the library module;
  `tests/unit/test_mvp_test.py` must be re-pointed (and a new
  `tests/unit/test_capability_report.py` added) — flagged for the tasks
  stage so coverage does not regress.
