<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Contract: Capability report JSON schema (frozen)

**Feature**: `014-capability-report-api` | **Date**: 2026-07-01
**Plan**: [../plan.md](../plan.md) | **Spec**: [../spec.md](../spec.md)

The **frozen** returned/serialized schema. It is exactly what the live
`DiagnosticReport.to_json()` / `DiagnosticTestRecord.to_json()` /
`DiagnosticHttpEvent.to_json()` produce today; the extraction preserves it
byte-for-byte (FR-002/FR-012/FR-014, SC-002). Any change to this schema is a
separate feature (Out of Scope).

## Top-level object (exactly four keys)

```jsonc
{
  "device": {
    "class": "E18C",                 // string | null — null when identity not inferred (see note)
    "model": "E18C",                 // string | null — equals "class"
    "firmware": "18.30.10.72",       // string | null
    "host": "<redacted>"             // ALWAYS redacted
  },
  "auth": {
    "method": "none",                // "none" | "basic" | "digest" ("none" also represents allowlist / no-auth)
    "ssl": false,
    "verify_ssl": true
  },
  "observed_schemas": {
    "/api/user/get": ["ID", "Name", "Phone", "..."]  // endpoint -> SORTED field names
  },
  "tests": [ /* test records — see below */ ]
}
```

> **Invariant**: there is **no** top-level `http_events` key. `http_events`
> is nested **inside each `tests[]` record**.
>
> **`device.*` nullability**: `class` / `model` / `firmware` default to
> `None` and are populated only when a system-info response returns strings.
> `DiagnosticReport.to_json()` emits these keys **without** `_drop_none`
> (`examples/mvp_test.py:286-287, 372-377`), so they serialize as `null`
> (not omitted) when device identity could not be inferred.
>
> **`auth.method`**: allowlist / no-auth is represented as the string
> `"none"`; the report never emits a distinct `allowlist` value.

## Test record (`tests[]` element)

```jsonc
{
  "name": "add_user",
  "label": "ADD USER (/api/user/set action:add)",
  "status": "passed",                         // passed | failed | skipped (inconclusive = default pre-resolution)
  "capability_status": "supported",           // supported | unsupported | inconclusive (NOT "unknown" — see note)
  // "reason": "...",                          // OMITTED when absent (dropped via _drop_none, never null)
  "endpoint": "/api/user/set",
  "request_fields": ["Name", "UserID", "..."],
  "observed_fields": ["ID", "..."],
  // "failure_shape": { ... },                 // OMITTED when there is no failure (dropped via _drop_none, never null)
  "http_events": [ /* HTTP events — see below */ ]
}
```

> **`capability_status` never emits `unknown`**: `unknown` is a
> capability-**gating input** state; a gated skip records `status="skipped"`
> → `capability_status="inconclusive"` (`DiagnosticTestRecord.capability_status()`,
> `examples/mvp_test.py:236-250`).
>
> **`_drop_none` omission**: `to_json()` passes its dict through `_drop_none`
> (`examples/mvp_test.py:499-501`), so `reason` / `failure_shape` (and any
> other `None` field) are **absent** from the object, never serialized as
> `null`.

## HTTP event (`tests[].http_events[]` element)

```jsonc
// Example of a FAILURE event (body_snippet present only on HTTP/retcode failure):
{
  "method": "POST",
  "endpoint": "/api/user/set",
  "http": 500,                                // HTTP status; OMITTED when None (via _drop_none)
  "retcode": -1,                              // Akuvox envelope code; OMITTED when None
  "retmsg": "error",                          // Akuvox envelope message; OMITTED when None
  "observed_fields": ["..."],
  "request_fields": ["..."],
  "exception_class": "...",                   // OMITTED unless a transport failure occurred
  "exception_message": "...",                 // OMITTED unless a transport failure occurred
  "body_snippet": "{\"field\":\"<redacted>\"}"  // clipped JSON STRING; OMITTED unless HTTP/retcode FAILURE
}
// A SUCCESS event (http 200 / retcode 0) has NO body_snippet and NO exception_class/exception_message keys.
```

> Every optional key above is dropped via `_drop_none`
> (`examples/mvp_test.py:143-158, 499-501`) — absent when unavailable,
> never serialized as `null`. `body_snippet` is a **clipped JSON string**
> (`_failure_body_snippet() -> str | None`, `mvp_test.py:600-617`), not an
> embedded object; it and the `exception_class`/`exception_message` keys
> never co-occur with a success (`http` < 400 and `retcode` >= 0) event.

## Redaction (unconditional — security boundary)

- `device.host` → **always** `"<redacted>"`.
- `body_snippet` present **only** for HTTP or Akuvox-retcode **failures**;
  successful bodies are **omitted** (not redacted).
- When present, `body_snippet` is a **clipped JSON string** whose parsed
  content has every JSON leaf `"<redacted>"` (redacted before `json.dumps`).
- Non-JSON body → `"<non-json response body omitted for privacy>"`.
- Scalar JSON body → `"<scalar JSON response body omitted for privacy>"`.
- No credential, PIN, MAC, name, phone, host, or OpenDoor password appears
  anywhere in the serialized structure.

## Serialization

The CLI writes the report with `json.dumps(..., indent=2, sort_keys=True)`
plus a trailing newline (via `DiagnosticReport.write_json`). The extraction
preserves this exact serialization so `--json-report` output is
byte-identical.
