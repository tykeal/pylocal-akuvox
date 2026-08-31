<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->
<!-- markdownlint-disable MD013 MD060 -->

# Quickstart: Capability Report API

**Feature**: `014-capability-report-api` | **Date**: 2026-07-01
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

How a consumer (the Home Assistant integration, or any code) produces the
redacted capability report without shelling out to the CLI. This describes
the **planned** public API; it lands in the later implementation PR.

## Read-only report (default)

```python
from pylocal_akuvox import AkuvoxDevice, run_capability_report

async with AkuvoxDevice("192.0.2.10") as device:
    report = await run_capability_report(device)

# report is a JSON-serializable dict with exactly:
#   report["device"]            -> {"class", "model", "firmware", "host"="<redacted>"}
#   report["auth"]              -> {"method", "ssl", "verify_ssl"}
#   report["observed_schemas"]  -> {endpoint: [sorted field names]}
#   report["tests"]             -> [ per-step records, each with nested "http_events" ]
assert set(report) == {"device", "auth", "observed_schemas", "tests"}
```

Read-only mode issues **zero** create/modify/delete requests and reuses the
device's existing capability probe internally. It never returns the
`DeviceCapabilities` profile — always the fuller report dict.

## Write-mode report (CRUD evidence + cleanup)

```python
from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
    run_capability_report,
)

# Supply the device credential however you manage secrets.
device_secret = "changeme"
auth = AuthConfig(
    method=AuthMethod.DIGEST,
    username="admin",
    password=device_secret,
)

async with AkuvoxDevice("192.0.2.10", auth=auth) as device:
    report = await run_capability_report(device, write=True)

# report["tests"] now includes add/modify/delete records for
# user, schedule, group, and contact, each with a "capability_status"
# (supported / unsupported / inconclusive). Throwaway entities created during
# the run are deleted before the call returns (best-effort cleanup).
```

Dependent steps (`modify_*` / `delete_*` / `verify_*_deletion`) are recorded
as skipped when their parent `add_*` fails or is skipped.

## Opt into the credentialed OpenDoor relay test

```python
report = await run_capability_report(
    device,
    write=True,  # OpenDoor requires write mode
    open_door=True,
    open_door_user="relay-user",
    open_door_password="relay-secret",  # passed programmatically; the library never reads env
)
```

The relay is physically actuated **only** when `open_door=True` **and** both
credentials are supplied. Without the credentials the OpenDoor step is
skipped (never silently actuated); with `open_door=False` (default) it is
skipped too.

## Redaction guarantee (safe to paste into public issues)

The returned structure is designed to be pasted into the `new_device` issue
template. It is unconditionally redacted:

```python
report = await run_capability_report(device, write=True)

assert report["device"]["host"] == "<redacted>"
# Each recorded failure body_snippet is a clipped JSON string whose parsed
# content has all leaves == "<redacted>"; successful bodies are omitted
# entirely; no credential/PIN/MAC/name/phone/OpenDoor password appears
# anywhere in the structure.
```

## Serializing the report

```python
import json

text = json.dumps(report, indent=2, sort_keys=True) + "\n"
```

This matches the CLI's `--json-report` serialization exactly.

## The CLI becomes a thin wrapper

After the implementation PR lands, `examples/mvp_test.py` will keep its full
flag surface (`--write`, `--open-door`, `--open-door-user`,
`--open-door-pass`, `AKUVOX_OPEN_DOOR_PASSWORD`, `--json-report`,
`--redact-stdout`, auth/SSL flags) and will derive its report from
`run_capability_report()`. For the same device interactions its stdout and
`--json-report` output will be byte-identical to the pre-extraction script.

```console
$ uv run examples/mvp_test.py 192.0.2.10 --write --json-report report.json
$ uv run examples/mvp_test.py 192.0.2.10 --write --open-door \
    --open-door-user relay-user   # prompts / reads AKUVOX_OPEN_DOOR_PASSWORD
```
