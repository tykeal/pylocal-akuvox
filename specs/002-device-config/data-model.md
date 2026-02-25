<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Device Configuration Management

**Feature**: 002-device-config
**Date**: 2026-02-24 (revised 2026-02-25)

## Entities

### DeviceConfig

Represents the full device configuration for an Akuvox device.
Frozen dataclass wrapping all autop-format key-value pairs
returned by `GET /api/config/get`. Real devices return 900+
keys spanning relay, network, SIP, display, door settings, and
more.

**Fields**:

- `data` (`dict[str, str]`): All configuration key-value pairs
  using autop-format keys as-is (e.g.,
  `Config.DoorSetting.RELAY.HoldDelayA`). Values are always
  strings matching the device API convention.

**Design rationale**: The device returns hundreds of keys across
many categories. Instead of mapping each key to a named
attribute (impractical at scale), the model stores them in a
flat dict. This preserves all keys — known, unknown, and
model-specific — without loss.

### Methods

**`from_api_response(data: dict[str, Any]) -> DeviceConfig`**

Class method. Converts the envelope `data` dict from
`GET /api/config/get` to a `DeviceConfig`. All values are
stringified.

**`to_api_payload(self) -> dict[str, str]`**

Instance method. Returns the full data dict for use in
`POST /api/config/set` envelopes.

**`keys() -> list[str]`**

Instance method. Returns the list of autop-format key names
present in this config, enabling key discovery (US3).

**`get(key, default=None) -> str | None`**

Dict-like access by autop-format key name.

**`__getitem__(key) -> str`**

Bracket access: `config["Config.DoorSetting.RELAY.HoldDelayA"]`.

**`__contains__(key) -> bool`**

Membership test: `"Config.DoorSetting.RELAY.HoldDelayA" in config`.

**`__len__() -> int`**

Number of configuration keys.

## Relationships

```text
AkuvoxDevice ──delegates──▶ config.get_device_config()
                            config.set_device_config()
                                │
                                ▼
                          AkuvoxHttpClient
                                │
                                ▼
                     GET /api/config/get
                     POST /api/config/set
                                │
                                ▼
                          DeviceConfig
```

## Validation Rules

- `set_device_config()` MUST receive at least one key-value pair
  (FR-004). Empty updates raise `AkuvoxValidationError`.
- Key names are autop-format strings (any key the device
  accepts). No client-side key validation — the device reports
  errors for unknown or invalid keys.
- Values are strings (matching device API convention). No
  additional type validation is performed — the device reports
  errors for invalid values.
