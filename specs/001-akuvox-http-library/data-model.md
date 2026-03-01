<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Akuvox Local HTTP API Library

## Entity Relationship Overview

```text
AkuvoxDevice 1──* Relay
AkuvoxDevice 1──1 DeviceInfo
AkuvoxDevice 1──1 DeviceStatus
AkuvoxDevice 1──1 AuthConfig
AkuvoxDevice 1──* User
AkuvoxDevice 1──* AccessSchedule
AkuvoxDevice 1──* DoorLogEntry
AkuvoxDevice 1──* CallLogEntry
```

## Field Name Convention

The Akuvox HTTP API uses PascalCase field names (e.g. `UserID`,
`PrivatePIN`). The Python library exposes these as snake_case
attributes (e.g. `user_id`, `private_pin`). The data model below
uses Python names; the contract in `contracts/akuvox-api.yaml`
uses API names. Notable non-obvious mappings:

- API `Type` → Python name varies by entity (`user_type`,
  `door_type`, `call_type`, `schedule_type`)
- API `Num` (CallLogItem) → `count`
- API `Code` (DoorLogItem) → `code` (card/PIN/public code used)

## Entities

### AuthConfig

Represents the authentication configuration for connecting to an
Akuvox device. Immutable after construction.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| method | AuthMethod (enum) | Yes | NONE, ALLOWLIST, BASIC, DIGEST |
| username | str | No | Required for BASIC and DIGEST |
| password | str | No | Required for BASIC and DIGEST |

#### Enum: AuthMethod

| Value | Description |
| ----- | ----------- |
| NONE | No authentication (development only) |
| ALLOWLIST | IP-based allow list (no credentials sent) |
| BASIC | HTTP Basic authentication |
| DIGEST | HTTP Digest authentication |

**Validation rules**:

- BASIC and DIGEST require both username and password
- NONE and ALLOWLIST must not have credentials
- Token is not a valid value (reserved by Akuvox, not implemented)

### DeviceInfo

Read-only snapshot of static device identification data returned
by `GET /api/system/info`.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| model | str | Yes | Product model name |
| mac_address | str | Yes | MAC address |
| firmware_version | str | Yes | Firmware version string |
| hardware_version | str | Yes | Hardware version string |
| uptime | str | No | Device uptime |
| web_language | int | No | Web UI language code (0=EN) |

### DeviceStatus

Point-in-time snapshot of device operational state returned
by `GET /api/system/status`. Returns system time and uptime
only; relay states are queried via `/api/relay/status`.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| unix_time | int | Yes | Device Unix timestamp (SystemTime) |
| uptime | int | Yes | Device online time in seconds (UpTime) |

### Relay

Represents a controllable relay on the device.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| number | int | Yes | Relay ID (1=A, 2=B, 3=C, 11=SecA, 12=SecB) |
| state | str | No | Current state from relay/status |

**Trigger parameters** (for `POST /api/relay/trig`):

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| num | int | Yes | Relay number |
| mode | int | No | 0=Auto Close (default), 1=Manual |
| level | int | No | 0=NO-COM (default), 1=NC-COM |
| delay | int | No | Close delay 0-65535 seconds |

### User

Represents a local user account stored on the device.

| Field | Type | Required (add) | Description |
| ----- | ---- | --------------- | ----------- |
| id | str | No (auto) | Internal DB ID (returned by device) |
| name | str | Yes | Display name |
| user_id | str | Yes | External user/PerID identifier |
| private_pin | str | No | PIN code for keypad access (4-8 digits) |
| card_code | str | No | RFID card code |
| web_relay | str | Yes | Assigned relay ("0" if none) |
| schedule_relay | str | Yes | Schedule-relay mapping (see format below) |
| lift_floor_num | str | Yes | Floor number ("0" if not applicable) |
| user_type | str | No | User type (ordinary/admin) |
| source | str | No | Record source |
| source_type | str | No | Source type (Local/Cloud/SDMC) |
| auth_mode | int | No | 0=Any, 1=Face+PIN, 2=Face+RF, 3=RF+PIN |

**`schedule_relay` format**: `<ScheduleID>-<RelayID>` with multiple
entries separated by commas.  A single trailing comma is tolerated.
Example: `"1001-1"` or `"1001-1,1002-2"`.

> **E18 firmware note**: The device uses comma as the separator for
> multiple schedule-relay pairs.  Semicolons are silently truncated
> to only the first entry.

**Validation rules**:

- Name must not be empty
- UserID must not be empty
- PIN must be 4-8 digits only. The API accepts other characters
  but the resulting PIN is unusable at the device. `0000` is valid.
- WebRelay and LiftFloorNum default to "0" if not applicable
- schedule_relay entries must match `<int>-<int>` comma-separated

**State transitions**: None (CRUD only, no state machine)

### AccessSchedule

Represents a time-based access rule on the device.

| Field | Type | Required (add) | Description |
| ----- | ---- | --------------- | ----------- |
| id | str | No (auto) | Internal DB ID |
| name | str | No | Schedule display name |
| schedule_type | int | Yes | 0=Normal, 1=Weekly, 2=Daily |
| date_start | str | No | Start date (YYYYMMDD) |
| date_end | str | No | End date (YYYYMMDD) |
| time_start | str | No | Start time (HH:MM) |
| time_end | str | No | End time (HH:MM) |
| week | str | No | Day codes (0=Sun..6=Sat, e.g. "01" for Sun+Mon) |
| daily | str | No | Daily time range (HH:MM-HH:MM) |
| sun | str | No | Sunday flag ("0" or "1") |
| mon | str | No | Monday flag ("0" or "1") |
| tue | str | No | Tuesday flag ("0" or "1") |
| wed | str | No | Wednesday flag ("0" or "1") |
| thur | str | No | Thursday flag ("0" or "1") |
| fri | str | No | Friday flag ("0" or "1") |
| sat | str | No | Saturday flag ("0" or "1") |
| display_id | str | No | Display identifier |
| source_type | str | No | 1=Local, 2=Cloud, 3=ACMS, 4=SDMC |
| mode | str | No | 0=Normal, 1=Weekly, 2=Daily |

**Validation rules**:

- Type must be 0, 1, or 2
- Time ranges must be valid HH:MM format
- Date ranges must be valid YYYYMMDD format
- Week codes must be digits 0-6
- Day-of-week flags must be "0" or "1"

**Note**: For weekly schedules (type `1`), the device uses the
individual day-of-week flags (`sun`..`sat`) to control which days
are active. The `week` code string is stored but does not activate
days on E18 firmware. Always set the individual day flags when
creating or modifying weekly schedules.

### DoorLogEntry

Read-only record from the device's door access log.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| id | str | Yes | Log entry DB ID |
| date | str | Yes | Date string |
| time | str | Yes | Time string |
| name | str | Yes | User name |
| code | str | Yes | Card/PIN/public code used |
| door_type | str | Yes | Open door type |
| relay | str | Yes | Which relay was triggered |
| status | str | Yes | "Succ" or "Failed" |
| access_mode | str | No | 0=normal, 1=entry, 2=exit |

### CallLogEntry

Read-only record from the device's call log.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| id | str | Yes | Log entry DB ID |
| date | str | Yes | Date string |
| time | str | Yes | Time string |
| name | str | Yes | Remote display name |
| call_type | str | Yes | Dialed/Received/Missed/Forwarded/Unknow |
| local_identity | str | Yes | SIP server identity |
| count | str | Yes | Total count |
| pic_url | str | No | Picture URL (device-specific) |

## API Response Envelope

All Akuvox API responses share this envelope structure:

| Field | Type | Description |
| ----- | ---- | ----------- |
| retcode | int | 0=success, non-zero=error |
| action | str | Echo of the API action name |
| message | str | Human-readable status message |
| data | object | Response payload (absent on error) |

## Exception Hierarchy

```text
AkuvoxError (base)
├── AkuvoxConnectionError      # Network/timeout failures
├── AkuvoxAuthenticationError  # HTTP 401, auth rejection
├── AkuvoxRequestError         # HTTP 400, bad parameters
├── AkuvoxDeviceError          # HTTP 500, device-side errors
├── AkuvoxParseError           # Non-JSON or malformed response
├── AkuvoxUnsupportedError     # API not supported by firmware
└── AkuvoxValidationError      # Local validation failures
```

## Pagination

User, schedule, and log endpoints support server-side pagination:

- `page` parameter: 1-indexed, 10 items per page (device-fixed)
- Response includes `curPageNum` (items on this page) and `num`
  (total matching items)
- `page=-1` or omitted returns all items (where supported)

The library will provide both single-page and iterate-all-pages
methods.
