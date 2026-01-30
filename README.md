# NotionTimeCapsule

A Python CLI application to periodically backup your Notion workspace to markdown files and generate daily content from templates.

## Features

- **Backup**: Export all Notion pages and databases to local markdown files with YAML frontmatter
- **Incremental**: Only backup changed content using timestamp and hash-based change detection
- **Attachments**: Download images and file attachments
- **Daily Content**: Generate content from templates and append to Notion pages
- **Scheduler**: Built-in daemon for automated backups and daily content generation

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/kylemcmaster/NotionTimeCapsule.git
cd NotionTimeCapsule

# Create virtual environment and install dependencies
uv venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate
uv pip install -e ".[dev]"
```

## Configuration

### Notion Integration Token

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration with read content capability
3. Copy the integration token
4. Set the environment variable:

```bash
export NOTION_TOKEN="your-integration-token"
```

5. Share pages/databases with your integration in Notion

### Configuration File

Copy the example config and customize:

```bash
cp config.example.toml config.toml
```

```toml
[backup]
output_dir = "./backups"
include_attachments = true
incremental = true

[daily]
template_path = "./templates/daily.md"
target_page_id = "your-page-id-here"

[scheduler]
backup_schedule = "daily"  # or "hourly", or cron syntax
daily_time = "06:00"
timezone = "America/New_York"
```

## Usage

### Backup

```bash
# Full workspace backup
notion-time-capsule backup

# Backup to specific directory
notion-time-capsule backup --output-dir ./my-backups

# Backup specific page
notion-time-capsule backup --page-id abc123def456

# Full backup (ignore incremental state)
notion-time-capsule backup --full

# Dry run (see what would be backed up)
notion-time-capsule backup --dry-run
```

### Daily Content

Create a template file (e.g., `templates/daily.md`):

```markdown
# Daily Entry - {{date}}

## {{weekday}}, {{month_name}} {{day}}, {{year}}

### Morning Reflection

-

### Today's Goals

1.
2.
3.
```

Generate and publish:

```bash
# Publish daily content
notion-time-capsule daily

# Use custom template
notion-time-capsule daily --template ./my-template.md

# Target specific page
notion-time-capsule daily --target-page abc123def456

# Preview without publishing
notion-time-capsule daily --dry-run
```

#### Available Template Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `{{date}}` | 2025-01-15 | ISO date |
| `{{year}}` | 2025 | Year |
| `{{month}}` | 01 | Month (zero-padded) |
| `{{day}}` | 15 | Day (zero-padded) |
| `{{weekday}}` | Wednesday | Full weekday name |
| `{{weekday_short}}` | Wed | Short weekday |
| `{{month_name}}` | January | Full month name |
| `{{month_short}}` | Jan | Short month name |
| `{{time}}` | 14:30 | Current time |
| `{{week_number}}` | 03 | Week of year |
| `{{quarter}}` | 1 | Quarter (1-4) |

### Scheduler

Run as a daemon for automated backups and daily content:

```bash
# Run scheduler in foreground
notion-time-capsule schedule --foreground

# Run scheduler (default)
notion-time-capsule schedule
```

### Configuration Management

```bash
# Show current configuration
notion-time-capsule config show

# Validate configuration
notion-time-capsule config validate

# JSON output
notion-time-capsule config show --json
```

### Global Options

```bash
# Verbose output
notion-time-capsule -v backup

# Very verbose (debug)
notion-time-capsule -vv backup

# JSON output format
notion-time-capsule --json backup

# Custom config file
notion-time-capsule --config ./my-config.toml backup
```

## Backup Output Structure

```
backups/
├── .state/
│   └── checksums.json         # Change detection state
├── pages/
│   └── {page-id}/
│       ├── index.md           # Page content with frontmatter
│       └── attachments/       # Downloaded files
└── databases/
    └── {database-id}/
        ├── _schema.yaml       # Database schema
        └── {row-id}.md        # Each row as markdown
```

### Page Frontmatter

```yaml
---
notion_id: "abc123-def456"
title: "Page Title"
created_time: "2025-01-15T10:30:00.000Z"
last_edited_time: "2025-01-20T14:22:00.000Z"
url: "https://notion.so/Page-Title-abc123def456"
parent_type: "workspace"
parent_id: null
properties: {}  # For database pages
---
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src tests

# Run type checker
mypy src
```

## License

MIT
