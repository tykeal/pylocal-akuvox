<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Feature**: 005-request-delay
**Date**: 2025-07-14

## Research Tasks

### R1: Best practice for async inter-request throttling in Python

**Decision**: Use `asyncio.sleep(delay)` within the existing `asyncio.Lock` context, placed after the successful response is received but before the lock is released.

**Rationale**: `asyncio.sleep` is the standard non-blocking delay mechanism in asyncio. Placing it inside the existing lock ensures serialized requests observe the delay without needing additional synchronization primitives. This is the simplest approach that respects task cancellation semantics (CancelledError propagates through `asyncio.sleep`).

**Alternatives considered**:

- `asyncio.Semaphore` with token bucket — overkill for serialized single-request-at-a-time; adds complexity without benefit since the lock already serializes.
- External rate-limiting middleware (e.g., `aiolimiter`) — unnecessary dependency for a simple fixed delay; the library targets minimal dependencies.
- `time.sleep` in an executor — would work but adds thread pool overhead; `asyncio.sleep` is simpler and native.

---

### R2: Where to place delay relative to lock lifecycle

**Decision**: Place the delay **after** `_request()` returns successfully and **before** the `async with self._lock` block exits (i.e., before lock release).

**Rationale**: The spec requires that "a pause occurs between the first response completing and the second request being sent" (FR-003). Placing the sleep inside the lock means the next caller waiting on the lock observes the full delay. This matches the spec's mental model exactly.

**Implementation approach**: Refactor `get()` and `post()` methods to call `_request()` and then conditionally sleep, all within the lock:

```python
async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with self._lock:
        result = await self._request("GET", path, params=params)
        await self._post_request_delay()
        return result
```

**Alternatives considered**:

- Sleep outside the lock (after release) — doesn't guarantee the delay is observed by the next request because another coroutine could acquire the lock immediately.
- Unconditional sleep before every request — contradicts FR-005 ("no delay before the first request") and adds latency ahead of every call.
- Timestamp-based pre-request throttling after a prior success — feasible, but more complex than a post-response sleep inside the existing lock for this feature.

---

### R3: Error handling — when to skip delay

**Decision**: Only call `await self._post_request_delay()` when `_request()` returns successfully. If `_request()` raises any exception, the delay is naturally skipped because the sleep line is never reached.

**Rationale**: FR-004 states the delay MUST NOT be applied when a request results in an error. Since exceptions propagate past the sleep call, no explicit error-checking is needed — the control flow handles it automatically.

**Alternatives considered**:

- try/except with a flag — unnecessary; Python's exception propagation already gives the correct behavior.
- Always delay, even on error — violates FR-004 and slows error handling.

---

### R4: Validation of request_delay parameter

**Decision**: Validate at `__init__` time. Raise `ValueError` with a clear message if the value is negative.

**Rationale**: FR-009 requires rejection at initialization time. `ValueError` is the standard Python exception for invalid argument values. This fails fast before any network operations occur.

**Implementation**:

```python
if request_delay < 0:
    msg = "request_delay must be zero or a positive number"
    raise ValueError(msg)
self._request_delay = request_delay
```

**Alternatives considered**:

- Clamp to 0 silently — violates FR-009's requirement for "a clear error."
- Custom exception type — `ValueError` is idiomatic Python; a custom type would be over-engineering.

---

### R5: Zero-delay optimization (FR-006)

**Decision**: Skip the `asyncio.sleep` call entirely when `request_delay == 0.0` to avoid any overhead.

**Rationale**: SC-003 requires less than 1ms added latency when delay is 0.0. While `asyncio.sleep(0)` is cheap, it still yields to the event loop which could add scheduling jitter. A simple `if` check eliminates this entirely.

**Implementation**:

```python
async def _post_request_delay(self) -> None:
    if self._request_delay > 0:
        await asyncio.sleep(self._request_delay)
```

**Alternatives considered**:

- Always call `asyncio.sleep(self._request_delay)` — even `sleep(0)` yields, adding measurable (though small) overhead that might fail SC-003's strict <1ms threshold.

---

### R6: Backward compatibility (FR-010)

**Decision**: Add `request_delay` as a keyword-only parameter with default value `0.25` to both `AkuvoxHttpClient.__init__` and `AkuvoxDevice.__init__`. Existing callers passing positional or keyword arguments remain unaffected.

**Rationale**: FR-010 requires no breaking changes. Adding a new keyword-only parameter with a default value is fully backward-compatible in Python.

**Current signatures**:

- `AkuvoxHttpClient.__init__(self, host, timeout=10, auth=None, *, use_ssl=False, verify_ssl=True)`
- `AkuvoxDevice.__init__(self, host, auth=None, timeout=10, *, use_ssl=False, verify_ssl=True)`

**New signatures** (keyword-only addition):

- `AkuvoxHttpClient.__init__(self, host, timeout=10, auth=None, *, request_delay=0.25, use_ssl=False, verify_ssl=True)`
- `AkuvoxDevice.__init__(self, host, auth=None, timeout=10, *, request_delay=0.25, use_ssl=False, verify_ssl=True)`

**Alternatives considered**:

- Default to 0.0 for full backward compat — the spec explicitly requires 0.25s default (FR-002) as the core value proposition.

## Summary

All NEEDS CLARIFICATION items resolved. The implementation is straightforward:

1. Add `request_delay` parameter to both constructors (keyword-only, default 0.25)
2. Validate non-negative at init time
3. Add `_post_request_delay()` helper method with zero-skip optimization
4. Call it after successful `_request()` in both `get()` and `post()`, inside the lock
5. Exceptions naturally bypass the delay
