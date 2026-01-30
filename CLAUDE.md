# Claude Code Context

This file provides context for Claude Code when working on this project.

## Project Overview

NotionTimeCapsule is a Python CLI application that:
- Backs up Notion workspaces to local markdown files
- Generates daily content from templates and appends to Notion pages
- Runs as a scheduler daemon for automated operations

## Key Documentation

- **Implementation Plan**: `docs/implementation-plan.md` - Architecture decisions, project structure, and design rationale
- **Patterns & Best Practices**: `docs/patterns.md` - Design patterns, code conventions, and rationale
- **Configuration Example**: `config.example.toml` - Available configuration options

## Architecture

```
src/notion_time_capsule/
├── cli.py           # Click CLI entry point
├── config.py        # TOML + env var configuration
├── notion/          # Notion API client with rate limiting
├── backup/          # Backup to markdown functionality
├── daily/           # Template rendering and publishing
├── scheduler/       # Daemon with scheduled jobs
└── utils/           # Atomic writes, logging, output formatting
```

## Core Principles

1. **Data Integrity First** - Preserve complete fidelity of Notion content
2. **Idempotent Operations** - Safe to re-run without side effects
3. **CLI-Driven Interface** - All functionality via CLI with JSON output support
4. **Test Coverage** - Critical paths must have tests
5. **Simplicity & Reliability** - Prefer simple solutions over complex optimizations

## Technical Constraints

- Python 3.11+
- Notion API via `notion-client` SDK
- Authentication via `NOTION_TOKEN` environment variable
- Output: Markdown with YAML frontmatter
- Atomic file writes (write-to-temp, then rename)

## Common Tasks

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run CLI
notion-time-capsule --help

# Run tests
pytest

# Lint
ruff check src tests
```
