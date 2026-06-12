<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# pylocal-akuvox Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-06-12

## Active Technologies
- Python ≥3.13.2, fully type-annotated (mypy strict)
- aiohttp ≥3.13 (async HTTP client with built-in auth)
- pytest, pytest-asyncio, aioresponses (test tooling)

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
- 007-models-split: Added spec/design artifacts for splitting
  `models.py` into a domain-grouped `models/` package
- 006-schedule-relay-compat: Added spec/design artifacts for
  Schedule-Relay field compatibility
- 005-request-delay: Added spec/design artifacts for configurable
  inter-request delay
- 004-address-book-groups: Added membership support for the device
  address book (list, add, modify, delete) using aiohttp-based async
  HTTP client

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
