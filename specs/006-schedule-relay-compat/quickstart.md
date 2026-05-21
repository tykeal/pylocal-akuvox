<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: Schedule-Relay Compatibility Fix

**Feature**: 006-schedule-relay-compat

## For integrators

**No integration code changes are required once the implementation ships.**
After the follow-up implementation PR is merged and released, upgrade the
`pylocal-akuvox` library and add-user / modify-user calls against Akuvox E18
devices on firmware `18.30.11.21` will start succeeding again. Calls against
all previously supported firmwares behave identically to the prior release.

```python
import asyncio

from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

async def main() -> None:
    auth = AuthConfig(method=AuthMethod.BASIC, username="admin", password="...")
    async with AkuvoxDevice(host="10.0.0.50", auth=auth) as device:
        # Exactly the same call as before — no parameter changes.
        await device.add_user(
            name="Alice",
            user_id="1001",
            schedule_relay="1001-1",   # primary-relay schedule
            lift_floor_num="",
        )

asyncio.run(main())
```

The same call shape works through the module-level helper
(`pylocal_akuvox.users.add_user`) for callers that wire their own
`AkuvoxHttpClient`.

## What changed internally

The follow-up implementation will make the outgoing JSON payload sent to
`/api/user/set` carry the primary-relay schedule under **two** keys with
identical values:

```json
{
  "ScheduleRelay":  "1001-1",
  "Schedule-Relay": "1001-1"
}
```

Secondary-relay scheduling remains out of scope for this feature: the
follow-up implementation must not introduce `ScheduleSRelay` or a hyphenated
secondary companion (see `research.md`).

## Verifying the fix locally

1. Install the dev extras and run the unit suite:

   ```sh
   uv sync --group dev
   uv run pytest tests/unit/test_users.py -v
   ```

2. The new tests (added in `tests/unit/test_users.py` as part of this
   feature) assert that both `ScheduleRelay` and `Schedule-Relay` appear
   in `add_user` and `modify_user` payloads with matching values.

## Verifying on real hardware (manual, post-CI)

Per the constitution (II. TDD), manual validation only proceeds after CI
is green. Then:

1. Against an Akuvox E18 device on firmware `18.30.11.21`: call
   `add_user` with a primary-relay schedule, read the user back, confirm
   success and that the stored schedule matches.
2. Against an X916 device on firmware `916.30.10.114` (or any other
   previously supported firmware): repeat — behavior MUST be identical to
   the prior library release.
3. Repeat with `modify_user` to confirm Acceptance Scenario 2 of User
   Story 1.
4. Confirm the captured outgoing payload does not include any new
   secondary-relay scheduling key (User Story 3 / SC-004).
