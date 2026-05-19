<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# API Contract: Configurable Inter-Request Delay
<!-- markdownlint-disable MD013 MD060 -->

**Feature**: 005-request-delay
**Date**: 2025-07-14

## Python Public API

This feature does not introduce HTTP endpoints — it modifies the constructor signatures of existing Python classes. The "contract" is the public API surface.

### AkuvoxHttpClient Constructor

```python
class AkuvoxHttpClient:
    def __init__(
        self,
        host: str,
        timeout: int = 10,
        auth: AuthConfig | None = None,
        *,
        request_delay: float = 0.25,  # NEW — keyword-only
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None: ...
```

**Parameter: `request_delay`**

- Type: `float`
- Default: `0.25`
- Constraints: Must be ≥ 0.0
- Raises: `ValueError` if negative
- Behavior: Seconds to sleep after each successful response, before releasing the serialization lock

### AkuvoxDevice Constructor

```python
class AkuvoxDevice:
    def __init__(
        self,
        host: str,
        auth: AuthConfig | None = None,
        timeout: int = 10,
        *,
        request_delay: float = 0.25,  # NEW — keyword-only
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None: ...
```

**Parameter: `request_delay`**

- Type: `float`
- Default: `0.25`
- Constraints: Must be ≥ 0.0
- Raises: `ValueError` if negative
- Behavior: Passed directly to `AkuvoxHttpClient`

### Behavioral Contract

| Condition | Delay Applied? | Notes |
|-----------|---------------|-------|
| Successful response (any method) | ✅ Yes | Sleep `request_delay` seconds inside lock |
| Request raises exception | ❌ No | Exception propagates immediately |
| First request in session | ❌ No delay before | Delay is post-response only |
| `request_delay=0.0` | ❌ No | No sleep call made; zero overhead |
| Task cancellation during sleep | N/A | `CancelledError` propagates normally |

### Error Contract

| Condition | Exception | Message |
|-----------|-----------|---------|
| `request_delay < 0` | `ValueError` | "request_delay must be zero or a positive number" |

### Backward Compatibility

- All existing positional and keyword argument patterns remain valid
- Default behavior changes: existing code gains 0.25s delay (intentional — this is the feature's purpose)
- Consumers requiring old behavior explicitly pass `request_delay=0.0`
