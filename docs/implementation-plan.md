# NotionTimeCapsule Implementation Plan

## Overview

Python CLI application with built-in scheduler that:
1. **Backs up** all Notion documents to local markdown files
2. **Generates daily content** from a local template and appends to a Notion page

## Requirements Summary

| Feature | Details |
|---------|---------|
| Backup | All Notion docs → local markdown with YAML frontmatter |
| Daily Content | Local `template.md` → append to existing Notion page |
| Template Variables | `{{date}}`, `{{year}}`, `{{month}}`, `{{day}}`, `{{weekday}}` |
| Scheduling | Built-in daemon with configurable backup/daily times |
| Auth | `NOTION_TOKEN` environment variable |

## Project Structure

```
NotionTimeCapsule/
├── pyproject.toml
├── config.toml                    # User configuration
├── templates/
│   └── daily.md                   # Daily content template
├── src/notion_time_capsule/
│   ├── __init__.py
│   ├── __main__.py                # Entry point
│   ├── cli.py                     # Click CLI commands
│   ├── config.py                  # TOML + env var config
│   ├── notion/
│   │   ├── client.py              # API wrapper with rate limiting
│   │   ├── models.py              # Pydantic models
│   │   └── rate_limiter.py        # Rate limit + retry logic
│   ├── backup/
│   │   ├── exporter.py            # Backup orchestration
│   │   ├── markdown.py            # Block → markdown conversion
│   │   ├── frontmatter.py         # YAML frontmatter
│   │   ├── attachments.py         # File downloads
│   │   └── state.py               # Change detection
│   ├── daily/
│   │   ├── template.py            # Variable substitution
│   │   └── publisher.py           # Append to Notion page
│   ├── scheduler/
│   │   ├── daemon.py              # Daemon process
│   │   └── jobs.py                # Scheduled jobs
│   └── utils/
│       ├── atomic.py              # Atomic file writes
│       ├── logging.py             # Structured logging
│       └── output.py              # JSON/text formatting
├── tests/
│   ├── unit/
│   └── integration/
└── backups/                       # Default output (gitignored)
```

## Dependencies

```toml
dependencies = [
    "notion-client>=2.0.0",    # Official Notion SDK
    "click>=8.0.0",            # CLI framework
    "pydantic>=2.0.0",         # Data validation
    "schedule>=1.2.0",         # Lightweight scheduler
    "pyyaml>=6.0",             # YAML frontmatter
]
```

## CLI Interface

```
notion-time-capsule [OPTIONS] COMMAND

Commands:
  backup    Backup Notion workspace to local files
  daily     Generate and publish daily content
  schedule  Run as daemon with scheduled tasks
  config    Show/validate configuration

Options:
  --config PATH   Config file path (default: ./config.toml)
  --json          JSON output format
  -v, --verbose   Increase verbosity
```

## Configuration (`config.toml`)

```toml
[backup]
output_dir = "./backups"
include_attachments = true
incremental = true

[daily]
template_path = "./templates/daily.md"
target_page_id = "your-notion-page-id"

[scheduler]
backup_schedule = "daily"      # or "hourly", cron syntax
daily_time = "06:00"
timezone = "America/New_York"
```

## Implementation Phases

### Phase 1: Foundation
- [x] Create `pyproject.toml` with dependencies
- [x] Set up package structure
- [x] Implement `utils/atomic.py` (atomic file writes)
- [x] Implement `utils/logging.py` and `utils/output.py`
- [x] Implement `config.py` (TOML + env var loading)
- [x] Basic CLI with `--version` command

### Phase 2: Notion Integration
- [x] Implement `notion/rate_limiter.py` (3 req/s limit, exponential backoff)
- [x] Implement `notion/client.py` (wrapped SDK with retry)
- [x] Implement `notion/models.py` (Pydantic models for blocks/pages)

### Phase 3: Backup Feature
- [x] Implement `backup/markdown.py` (block-to-markdown for all block types)
- [x] Implement `backup/frontmatter.py` (YAML metadata)
- [x] Implement `backup/attachments.py` (download files/images)
- [x] Implement `backup/state.py` (change detection via timestamps + hashes)
- [x] Implement `backup/exporter.py` (orchestration)
- [x] Add `backup` CLI command

### Phase 4: Daily Content
- [x] Implement `daily/template.py` (variable substitution)
- [x] Implement `daily/publisher.py` (append blocks to Notion page)
- [x] Add `daily` CLI command

### Phase 5: Scheduler
- [x] Implement `scheduler/jobs.py` (job definitions)
- [x] Implement `scheduler/daemon.py` (signal handling, graceful shutdown)
- [x] Add `schedule` CLI command

### Phase 6: Testing & Polish
- [x] Unit tests for markdown conversion, templates, rate limiter
- [ ] Integration tests for backup/daily workflows
- [ ] CLI tests with Click's `CliRunner`
- [x] Update README with usage docs
- [x] Document patterns and best practices in `docs/patterns.md`

### Phase 7: Discord Notifications
- [x] Add `DiscordConfig` dataclass to `config.py`
- [x] Create `utils/discord.py` with `DiscordNotifier` class
- [x] Integrate notifications in CLI commands (completion only)
- [x] Integrate notifications in scheduler jobs (start + completion)
- [x] Add `[discord]` section to `config.example.toml`
- [x] Add `httpx` dependency for webhook requests

### Phase 8: Status/Health Check
- [x] Add `StatusResult` dataclass to `utils/output.py`
- [x] Add `status` command to CLI
- [x] Read backup state from `.state/checksums.json`
- [x] Display configuration validity, backup stats, Discord status
- [x] Support JSON output with `--json` flag

### Phase 9: Docker Support
- [x] Create multi-stage `Dockerfile` with Python 3.12-slim
- [x] Create `docker-compose.yml` for easy deployment
- [x] Create `.dockerignore` to exclude dev files
- [x] Run as non-root user with health checks
- [x] Document Docker usage in `docs/docker.md`

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI Framework | click | Mature, minimal deps, easy testing |
| Scheduler | schedule | Lightweight, pure Python, simple |
| Config Format | TOML | Python 3.11+ stdlib, human-readable |
| API Client | notion-client SDK | Official, well-maintained |
| Change Detection | timestamp + SHA-256 hash | Fast path via timestamp, verified by hash |

## Backup Output Structure

```
backups/
├── .state/
│   └── checksums.json             # Change detection state
├── pages/
│   └── {page-id}/
│       ├── index.md               # Page with frontmatter
│       └── attachments/           # Downloaded files
└── databases/
    └── {database-id}/
        ├── _schema.yaml           # Database schema
        └── {row-id}.md            # Each row as markdown
```

## Verification Plan

1. **Unit tests**: `pytest tests/unit/`
2. **Integration tests**: `pytest tests/integration/`
3. **Manual verification**:
   - Set `NOTION_TOKEN` and run `notion-time-capsule backup --output-dir ./test-backup`
   - Verify markdown files match Notion content
   - Run `notion-time-capsule daily --template ./templates/daily.md --target-page <id>`
   - Verify content appended to Notion page
   - Run `notion-time-capsule schedule` and verify jobs execute on schedule

---

## Updates

### 2026-01-31

**Configuration Changes:**
- `notion_token` can now be set in `config.toml` (previously only via `NOTION_TOKEN` env var)
- Environment variable still takes priority over config file value
- Discord notifications no longer require `enabled = true`; they activate automatically when `webhook_url` is configured

**New CLI Commands:**
- Added `test-discord` command to verify webhook configuration

**Discord Notifications:**
- CLI commands (`backup`, `daily`) now send both start and completion notifications
- Removed `enabled` flag requirement; presence of `webhook_url` enables notifications
- Updated `notify_on_start` to work for CLI commands (previously scheduler only)

**Docker Support:**
- Added `Dockerfile` with multi-stage build (Python 3.12-slim base)
- Added `docker-compose.yml` for easy deployment
- Added `.dockerignore` to exclude dev files
- Container runs as non-root user (UID 1000)
- Health check via `notion-time-capsule status` command
- Default command runs scheduler daemon
- See `docs/docker.md` for complete documentation
