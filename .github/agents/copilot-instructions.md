<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# pylocal-akuvox Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-24

## Active Technologies
- Python ≥3.13.2, fully type-annotated (mypy strict)
- aiohttp ≥3.13 (async HTTP client with built-in auth)
- Python ≥3.13.2, fully type-annotated (mypy + aiohttp ≥3.13 (async HTTP) (003-group-management)
- N/A (device API only) (003-group-management)

## Project Structure

```text
src/pylocal_akuvox/
tests/
```

## Commands

```bash
uv run pytest tests/
uv run ruff check src/ tests/
```

## Code Style

Python ≥3.13.2: Follow standard conventions

## Recent Changes
- 003-group-management: Added Python ≥3.13.2, fully type-annotated (mypy + aiohttp ≥3.13 (async HTTP)
- 002-device-config: Introduced device configuration support
  using aiohttp-based async HTTP client
- 001-akuvox-http-library: Akuvox local HTTP API library

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
