<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Data Model: Capability Report API

**Feature**: `014-capability-report-api` | **Date**: 2026-07-01
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The "data" for this feature is the **returned report structure** — a
JSON-serializable `dict` — plus the internal fixtures the write suite
mutates. Nothing is persisted. This model documents the **frozen** shape the
extraction MUST preserve exactly (from the live `to_json()` methods); the
authoritative machine-readable version is
[contracts/report-json-schema.md](./contracts/report-json-schema.md).

## Entity: Capability report (the return value)

The top-level object returned by `run_capability_report()` and written by the
CLI's `--json-report`. Produced by `DiagnosticReport.to_json()`.

### Top-level keys (exactly four)

| Key | Type | Notes |
|---|---|---|
| `device` | object | `{class, model, firmware, host}`; `host` is **always** the literal `"<redacted>"`. `class` == `model` in the live code. `class` / `model` / `firmware` are `string \| null` — they default to `None` and are populated only when a system-info response returns strings; `to_json()` includes these keys **without** `_drop_none`, so they serialize as `null` (not omitted) when identity could not be inferred. |
| `auth` | object | `{method, ssl, verify_ssl}` — the connection's auth method and SSL toggles. `method` is the string `"none"` / `"basic"` / `"digest"`; **allowlist / no-auth is represented as `"none"`** (the report never emits a distinct `allowlist` value). |
| `observed_schemas` | object | Mapping of endpoint → **sorted** list of field names observed in successful responses. |
| `tests` | array | List of **test records** (below); each carries its own nested `http_events`. |

> **Invariant**: there is **no** top-level `http_events` key. `http_events`
> is nested **inside each `tests[]` record**. (Issue #208's shorthand is
> wrong; the live code is authoritative.)

## Entity: Test record (`tests[]` element)

One diagnostic step. Produced by `DiagnosticTestRecord.to_json()`.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Step name (e.g. `add_user`, `list_contacts`). |
| `label` | string | Human label. |
| `status` | string | `passed` / `failed` / `skipped` (`inconclusive` is the default before a step resolves). |
| `capability_status` | string | `supported` / `unsupported` / `inconclusive` — the capability-matrix evidence signal. **`unknown` is NOT an emitted value**: it is a capability-**gating input** state; a gated skip records `status="skipped"` → `capability_status="inconclusive"` (verified `DiagnosticTestRecord.capability_status()`, `mvp_test.py:236-250`). |
| `reason` | string | Skip/failure reason (matches the CLI's reason strings). **Omitted when `None`** via `_drop_none` (`mvp_test.py:499-501`) — not serialized as `null`. |
| `endpoint` | string | Primary endpoint exercised. **Omitted when `None`** via `_drop_none`. |
| `request_fields` | array | Field names sent in the request. |
| `observed_fields` | array | Field names observed in the response. |
| `failure_shape` | object | Redacted failure descriptor (the failing event's `to_json()`). **Present only on failure; omitted when there is no failure** via `_drop_none` — not serialized as `null`. |
| `http_events` | array | Nested **HTTP event** records for this step. |

> **`_drop_none` omission semantics**: both `DiagnosticTestRecord.to_json()`
> and `DiagnosticHttpEvent.to_json()` pass their dict through `_drop_none`,
> which drops every key whose value is `None`. Optional fields are therefore
> **absent** from the serialized object, never present as `null`.

## Entity: HTTP event (`tests[].http_events[]` element)

One captured request/response exchange. Produced by
`DiagnosticHttpEvent.to_json()`.

| Field | Type | Notes |
|---|---|---|
| `method` | string | HTTP method. |
| `endpoint` | string | Request path. |
| `http` | int | HTTP status code. **Omitted when `None`** via `_drop_none`. |
| `retcode` | int | Akuvox envelope return code. **Omitted when `None`**. |
| `retmsg` | string | Akuvox envelope message. **Omitted when `None`**. |
| `observed_fields` | array | Response field names. |
| `request_fields` | array | Request field names. |
| `exception_class` / `exception_message` | string | Exception class/message on transport failure. **Each omitted when `None`** via `_drop_none`. |
| `body_snippet` | string | **Present only for HTTP or Akuvox-retcode failures** (omitted otherwise via `_drop_none`). A **clipped JSON string** — the redacted body serialized with `json.dumps(...)` then clipped to `_BODY_SNIPPET_CHARS` (`_failure_body_snippet() -> str | None`, `mvp_test.py:600-617`). The **parsed** JSON of that string has every leaf `"<redacted>"`; non-JSON/scalar bodies are the fixed privacy sentinel **strings**. |

## Redaction rules (security boundary — FR-003 / US4)

Applied unconditionally to the returned structure:

- `device.host` is **always** `"<redacted>"`.
- Any recorded `body_snippet` is a **clipped JSON string** whose parsed
  content has **every** JSON leaf replaced with `"<redacted>"` (via
  `_redact_json_values()` before `json.dumps()`).
- Successful (non-failure) responses record **no** `body_snippet` at all
  (omitted, not redacted).
- Non-JSON bodies → `"<non-json response body omitted for privacy>"`;
  scalar JSON bodies → `"<scalar JSON response body omitted for privacy>"`.
- No credential, PIN, MAC, name, phone, host, or OpenDoor password appears
  anywhere in the serialized structure.
- The CLI's `--redact-stdout` (terminal redaction) is **orthogonal** — the
  returned-structure redaction is unconditional and independent of it.

## Entity: Throwaway test entity (write-mode only)

A user / schedule / group / contact created **solely** to exercise write CRUD
and deleted before the run completes (SC-004). Fixed, recognizable
identifiers so any residue from an abnormal abort is identifiable:

| Entity | Fixture (from live CLI) |
|---|---|
| User | name `pylocal-test`, UserID `9999`, PIN `1234` → modified to `5678` |
| Schedule / Group / Contact | analogous fixed test fixtures created then deleted |

Lifecycle: `add_* → (modify_*) → delete_* → verify_*_deletion`. `delete_*` is
attempted for every entity whose `add_*` succeeded, regardless of the
`modify_*` outcome. A best-effort teardown guard per CRUD group issues a
final delete only if the normal `delete_*` did not confirm removal (no-op on
the happy path — see plan Clarification 3).

## Entity: OpenDoor credentials (opt-in only)

The dedicated relay username + password, distinct from the device's general
auth, required to opt into the physical relay test. Passed programmatically
as `open_door_user` + `open_door_password` (plan Clarification 1). **Never**
recorded in the report, logs, or any body excerpt.

## State transitions

The report is **append-only** during a run: steps append test records; each
step appends HTTP events; `observed_schemas` accumulates field names from
successful responses; `to_json()` serializes the final immutable snapshot.
There are no in-place mutations of already-recorded records.
