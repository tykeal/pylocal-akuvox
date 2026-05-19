<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# pylocal-akuvox Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-18

## Active Technologies
- Python ≥3.13.2, fully type-annotated (mypy strict)
- aiohttp ≥3.13 (async HTTP client with built-in auth)

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
- 005-request-delay: Added spec/design artifacts for configurable
  inter-request delay
- 004-contact-management: Added contact CRUD with group
  membership support for the device address book
- 003-group-management: Added group CRUD operations
  (list, add, modify, delete) for device access groups
  using aiohttp-based async HTTP client

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
