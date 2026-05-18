<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Feature**: 005-request-delay
**Date**: 2025-07-14

## Entities

### RequestDelay (Configuration Value)

| Field | Type | Constraints | Default |
|-------|------|-------------|---------|
| `request_delay` | `float` | ≥ 0.0 | 0.25 |

**Validation rules**:

- MUST be a numeric value (int or float accepted, stored as float)
- MUST be ≥ 0.0; negative values raise `ValueError` at initialization
- No upper bound enforced (consumer responsibility per edge case spec)

**Behavior**:

- When > 0.0: `asyncio.sleep(request_delay)` called after successful response, inside lock
- When == 0.0: No sleep called (zero overhead)
- On request error: Sleep is never reached (exception propagates)

### AkuvoxHttpClient (Modified)

| Attribute | Type | Access | Description |
|-----------|------|--------|-------------|
| `_request_delay` | `float` | private | Configured delay duration in seconds |
| `_lock` | `asyncio.Lock` | private | Existing serialization lock (unchanged) |

**New method**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `_post_request_delay` | `async def _post_request_delay(self) -> None` | Sleeps for `_request_delay` seconds if > 0 |

### AkuvoxDevice (Modified)

No new attributes. Passes `request_delay` through to `AkuvoxHttpClient` constructor.

## State Transitions

```text
                    ┌─────────────┐
                    │  Lock Idle  │
                    └──────┬──────┘
                           │ acquire lock
                           ▼
                    ┌─────────────┐
                    │  Requesting │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │ success                 │ error
              ▼                         ▼
    ┌──────────────────┐      ┌──────────────┐
    │  Delay (sleep)   │      │ Release Lock │──→ raise exception
    └────────┬─────────┘      └──────────────┘
             │ sleep complete
             ▼
    ┌──────────────────┐
    │  Release Lock    │──→ return result
    └──────────────────┘
```

## Relationships

```text
AkuvoxDevice  ──creates──▶  AkuvoxHttpClient
                              │
                              ├── _request_delay: float
                              ├── _lock: asyncio.Lock
                              └── _post_request_delay(): async
```

No new entities, models, or database tables. This feature adds a behavioral configuration parameter to existing classes.
