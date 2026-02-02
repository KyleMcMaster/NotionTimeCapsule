# Patterns and Best Practices

This document describes the design patterns and best practices used throughout the NotionTimeCapsule codebase.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Configuration Management](#configuration-management)
3. [API Client Patterns](#api-client-patterns)
4. [File I/O Patterns](#file-io-patterns)
5. [CLI Patterns](#cli-patterns)
6. [Logging Patterns](#logging-patterns)
7. [Error Handling](#error-handling)
8. [Webhook Notifications](#webhook-notifications)
9. [Status/Health Check](#statushealth-check)
10. [Testing Patterns](#testing-patterns)
11. [Type Safety](#type-safety)

---

## Project Structure

### Layered Architecture

The codebase follows a domain-driven, layered structure:

```
src/notion_time_capsule/
├── cli.py              # Presentation layer (CLI commands)
├── config.py           # Configuration management
├── notion/             # External API integration
├── backup/             # Backup feature domain
├── daily/              # Daily content domain
├── scheduler/          # Scheduling domain
└── utils/              # Cross-cutting utilities
```

**Benefits:**
- Clear separation of concerns
- Each module has single responsibility
- Easy to locate and maintain functionality
- Scales well as features are added

### Entry Points

```python
# __main__.py - Module execution support
from notion_time_capsule.cli import main

if __name__ == "__main__":
    main()
```

This enables running via `python -m notion_time_capsule`.

---

## Configuration Management

### Hierarchical Dataclasses

Configuration uses nested dataclasses with sensible defaults:

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class BackupConfig:
    output_dir: Path = field(default_factory=lambda: Path("./backups"))
    include_attachments: bool = True
    incremental: bool = True

@dataclass
class Config:
    notion_token: str = ""
    backup: BackupConfig = field(default_factory=BackupConfig)
    # ... other nested configs

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = []
        if not self.notion_token:
            errors.append("NOTION_TOKEN is required")
        return errors
```

**Benefits:**
- Type-safe without runtime overhead
- Self-documenting defaults
- Built-in validation method
- Easily serializable

### Priority-Based Loading

Configuration follows a clear priority order:

```python
def load_config(config_path: Path | None = None) -> Config:
    """Load configuration.

    Priority (highest to lowest):
    1. Environment variables
    2. Config file values
    3. Default values
    """
    # Load TOML file
    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)

    # Get notion_token from config file first, then env var override
    notion_token = config_data.get("notion_token", "")
    if env_token := os.environ.get("NOTION_TOKEN"):
        notion_token = env_token

    if output_dir := os.environ.get("NOTION_BACKUP_DIR"):
        backup_config.output_dir = Path(output_dir)
```

**Supported configuration sources:**

| Setting | Config File | Environment Variable |
|---------|-------------|---------------------|
| `notion_token` | `notion_token = "..."` | `NOTION_TOKEN` |
| Backup enabled | `[backup] enabled` | `NOTION_BACKUP_ENABLED` |
| Backup directory | `[backup] output_dir` | `NOTION_BACKUP_DIR` |
| Daily enabled | `[daily] enabled` | `NOTION_DAILY_ENABLED` |
| Daily target page | `[daily] target_page_id` | `NOTION_DAILY_PAGE` |
| Discord webhook | `[discord] webhook_url` | `DISCORD_WEBHOOK_URL` |

---

## API Client Patterns

### Rate Limiting

The rate limiter ensures API calls don't exceed limits:

```python
class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_second: float = 3.0) -> None:
        self.min_interval = 1.0 / requests_per_second
        self._last_request: float = 0.0

    def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request

        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        self._last_request = time.monotonic()
```

**Key points:**
- Uses `time.monotonic()` (immune to system clock changes)
- Simple token bucket implementation
- Called before each API request

### Retry Decorator with Exponential Backoff

```python
def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying on transient errors."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    status_code = _get_status_code(e)

                    if status_code not in retryable_status_codes:
                        raise

                    if attempt < max_retries:
                        sleep_time = backoff_factor ** attempt
                        time.sleep(sleep_time)
                    else:
                        raise
        return wrapper
    return decorator

# Usage
@with_retry(max_retries=3)
def search(self, query: str) -> dict:
    return self._client.search(query=query)
```

**Key points:**
- Exponential backoff (1s, 2s, 4s)
- Respects HTTP Retry-After header
- Only retries transient errors (429, 5xx)
- Preserves function signature with `@wraps`

### Pagination Iterators

Generator-based pagination hides cursor management:

```python
def iter_all_pages(self) -> Iterator[dict]:
    """Iterate through all pages with automatic pagination."""
    cursor = None

    while True:
        results = self.search(filter_type="page", start_cursor=cursor)

        for item in results.get("results", []):
            yield item

        if not results.get("has_more"):
            break

        cursor = results.get("next_cursor")
```

**Benefits:**
- Memory efficient (doesn't load all at once)
- Clean for-in syntax for callers
- Automatic rate limiting per request

---

## File I/O Patterns

### Atomic Writes

All file writes use atomic operations to prevent corruption:

```python
def atomic_write(path: Path, content: str | bytes, mode: str = "w") -> None:
    """Write atomically using temp file + rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (required for atomic rename)
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )

    try:
        with os.fdopen(fd, mode) as f:
            f.write(content)
        os.replace(temp_path, path)  # Atomic on POSIX
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
```

**Key points:**
- Temp file in same directory ensures atomic rename on POSIX
- Cleanup on any exception
- No partial files on crash

### Context Managers for Resources

```python
class AttachmentDownloader:
    def __init__(self, output_dir: Path) -> None:
        self._client = httpx.Client(timeout=60.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AttachmentDownloader:
        return self

    def __exit__(self, *args) -> None:
        self.close()

# Usage
with AttachmentDownloader(output_dir) as downloader:
    downloader.download(url, path)
# Client automatically closed
```

---

## CLI Patterns

### Click Command Groups with Context

```python
class Context:
    """Shared state across commands."""
    def __init__(self) -> None:
        self.config: Config | None = None
        self.json_mode: bool = False
        self.formatter: OutputFormatter | None = None

pass_context = click.make_pass_decorator(Context, ensure=True)

@click.group()
@click.option("--json", is_flag=True, help="JSON output")
@click.option("-v", "--verbose", count=True)
@pass_context
def main(ctx: Context, json: bool, verbose: int) -> None:
    ctx.json_mode = json
    setup_logging(verbose=verbose, json_format=json)

@main.command()
@pass_context
def backup(ctx: Context) -> None:
    # Access shared context
    if ctx.json_mode:
        ...
```

### Lazy Imports

Defer heavy imports until needed:

```python
@main.command()
def backup(ctx: Context) -> None:
    # Import here to avoid slow startup
    from notion_time_capsule.backup.exporter import run_backup

    result = run_backup(ctx.config)
```

**Benefits:**
- Faster CLI startup
- Avoids circular imports
- Only loads what's needed

---

## Logging Patterns

### Dual Formatters

Support both human and machine-readable output:

```python
class JsonFormatter(logging.Formatter):
    """JSON format for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        })

class HumanFormatter(logging.Formatter):
    """Colored format for terminals."""

    COLORS = {"ERROR": "\033[31m", "WARNING": "\033[33m", ...}

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        return f"{color}{record.levelname}\033[0m {record.getMessage()}"
```

### Verbosity Levels

```python
def setup_logging(verbose: int = 0, quiet: bool = False) -> None:
    if quiet:
        level = logging.ERROR
    elif verbose >= 2:
        level = logging.DEBUG      # -vv
    elif verbose >= 1:
        level = logging.INFO       # -v
    else:
        level = logging.WARNING    # default
```

---

## Error Handling

### Categorized Exit Codes

```python
class ExitCode:
    """Unix-standard exit codes."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIGURATION_ERROR = 2
    AUTHENTICATION_ERROR = 3
    NETWORK_ERROR = 4
    RATE_LIMITED = 5
    PARTIAL_FAILURE = 6  # Some items succeeded
```

### Error Collection with Partial Success

```python
def run_backup(config: Config) -> BackupResult:
    errors: list[dict] = []
    pages_backed_up = 0

    for page in client.iter_all_pages():
        try:
            _backup_page(page)
            pages_backed_up += 1
        except Exception as e:
            errors.append({
                "type": "page_error",
                "page_id": page["id"],
                "message": str(e),
            })

    # Partial success: some pages backed up despite errors
    success = len(errors) == 0 or pages_backed_up > 0

    return BackupResult(success=success, errors=errors, ...)
```

---

## Webhook Notifications

### Discord Notifier Pattern

The Discord notifier follows a simple, fire-and-forget pattern for sending notifications:

```python
class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(self, config: DiscordConfig) -> None:
        self.config = config
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()

    def notify_backup_complete(self, result: BackupResult) -> bool:
        """Send notification when backup completes."""
        if result.success and not self.config.notify_on_success:
            return True

        if not result.success and not self.config.notify_on_failure:
            return True

        embed = self._create_embed(...)
        return self._send_embed(embed)
```

**Key patterns:**
- Lazy client initialization (only create when first used)
- Explicit `close()` method for resource cleanup
- Early returns based on config flags
- Returns `bool` for success/failure (doesn't throw)
- Notifications activate when `webhook_url` is configured (no separate `enabled` flag needed)

### Configuration-Driven Notifications

Notifications respect granular config flags:

```python
@dataclass
class DiscordConfig:
    webhook_url: str = ""           # Presence enables notifications
    notify_on_start: bool = True    # Send when job starts
    notify_on_success: bool = True  # Send on successful completion
    notify_on_failure: bool = True  # Send on failure
```

**Benefits:**
- Users can enable/disable specific notification types
- Reduces noise (e.g., only notify on failures)
- Environment variable override for webhook URL
- No separate `enabled` flag required; `webhook_url` presence activates notifications

### Notification Integration Points

Both CLI and scheduler send start + completion notifications:

```python
# CLI: Start + completion notifications
def backup(ctx: Context) -> None:
    # Send start notification if webhook configured
    if ctx.config.discord.webhook_url:
        notifier = DiscordNotifier(ctx.config.discord)
        notifier.notify_backup_started(str(ctx.config.backup.output_dir))
        notifier.close()

    result = run_backup(ctx.config)
    ctx.formatter.output(result)

    # Send completion notification
    if ctx.config.discord.webhook_url:
        notifier = DiscordNotifier(ctx.config.discord)
        notifier.notify_backup_complete(result)
        notifier.close()

# Scheduler: Same pattern
def backup_job(config: Config) -> None:
    notifier = None
    if config.discord.webhook_url:
        notifier = DiscordNotifier(config.discord)
        notifier.notify_backup_started(str(config.backup.output_dir))

    try:
        result = run_backup(config)
        if notifier:
            notifier.notify_backup_complete(result)
    finally:
        if notifier:
            notifier.close()
```

**Key points:**
- Both CLI and scheduler send start notifications
- Check for `webhook_url` presence (not `enabled` flag)
- Users can disable start notifications via `notify_on_start = false`

### Discord Embed Format

Rich embeds provide structured information:

```python
def _create_embed(
    self,
    title: str,
    description: str,
    color: int,
    fields: list[dict] | None = None,
) -> dict:
    return {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(UTC).isoformat(),
        "footer": {"text": "NotionTimeCapsule"},
        "fields": fields or [],
    }
```

**Color conventions:**
- `0x2ECC71` (green) - Success
- `0xE74C3C` (red) - Failure
- `0x3498DB` (blue) - Info/Started

---

## Status/Health Check

### Result Dataclass Pattern

Status checks use a dedicated result dataclass for structured output:

```python
@dataclass
class StatusResult:
    """Result of a status check."""
    config_valid: bool
    config_errors: list[str]
    last_backup_time: str | None
    pages_count: int
    databases_count: int
    attachments_count: int
    backup_dir: str
    backup_dir_exists: bool
    incremental_enabled: bool
    discord_enabled: bool
    discord_configured: bool
```

**Benefits:**
- Type-safe result structure
- Easy serialization to JSON via `asdict()`
- Consistent with `BackupResult` and `DailyResult` patterns

### Reading Persisted State

The status command reads from the backup state file without modifying it:

```python
state_file = config.backup.output_dir / ".state" / "checksums.json"

if state_file.exists():
    with open(state_file, "rb") as f:
        state_data = json.load(f)

    last_backup_time = state_data.get("saved_at")
    pages_count = len(state_data.get("pages", {}))
    databases_count = len(state_data.get("databases", {}))
```

**Key points:**
- Read-only access to state file
- Graceful handling when no backups exist
- Extracts counts from persisted dictionaries

### Aggregating Multiple Data Sources

Status checks combine information from multiple sources:

| Data | Source |
|------|--------|
| Configuration validity | `config.validate()` |
| Last backup time | `.state/checksums.json` |
| Page/database counts | `.state/checksums.json` |
| Backup directory status | Filesystem check |
| Discord configuration | `config.discord.*` |

**Pattern:**
```python
# Validate config
config_errors = ctx.config.validate()
config_valid = len(config_errors) == 0

# Check filesystem
backup_dir_exists = ctx.config.backup.output_dir.exists()

# Check feature flags
discord_enabled = ctx.config.discord.enabled
discord_configured = bool(ctx.config.discord.webhook_url)
```

### Dual Output Format

Status supports both human-readable and JSON output via the `OutputFormatter`:

```python
def _output_status_human(self, result: StatusResult) -> None:
    print("Status Check")
    print("=" * 40)

    print("Configuration:")
    if result.config_valid:
        print("  Status: valid")
    else:
        print("  Status: INVALID", file=sys.stderr)
        for error in result.config_errors:
            print(f"    - {error}", file=sys.stderr)
    # ... more sections
```

**Human output sections:**
1. Configuration (validity, backup dir, incremental mode)
2. Last Backup (time, pages, databases, attachments)
3. Notifications (Discord status)

---

## Testing Patterns

### Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Fast, isolated tests
│   ├── test_atomic.py
│   ├── test_template.py
│   └── test_markdown.py
└── integration/         # End-to-end with mocks
    └── test_backup.py
```

### Pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=notion_time_capsule --cov-report=term-missing"
```

### HTTP Mocking with responses

```python
import responses

@responses.activate
def test_api_retry():
    responses.add(responses.GET, "https://api.notion.com/...",
                  status=429)
    responses.add(responses.GET, "https://api.notion.com/...",
                  json={"results": []})

    result = client.search()
    assert len(responses.calls) == 2  # Retried once
```

---

## Type Safety

### Strict Mypy Configuration

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
```

### Key Type Patterns

```python
# Literal types for constrained values
type: Literal["file", "external"]

# ParamSpec for decorator type preservation
P = ParamSpec("P")
T = TypeVar("T")

def decorator(func: Callable[P, T]) -> Callable[P, T]:
    ...

# TYPE_CHECKING for import cycles
if TYPE_CHECKING:
    from notion_time_capsule.config import Config

# Union types
def get_config() -> Config | None:
    ...
```

---

## Summary

| Pattern | Location | Purpose |
|---------|----------|---------|
| Layered architecture | Project structure | Separation of concerns |
| Dataclass config | `config.py` | Type-safe configuration |
| Rate limiter | `notion/rate_limiter.py` | API compliance |
| Retry decorator | `notion/rate_limiter.py` | Resilient API calls |
| Atomic writes | `utils/atomic.py` | Crash-safe file I/O |
| Context managers | `backup/attachments.py` | Resource cleanup |
| Click context | `cli.py` | Shared CLI state |
| Dual log formatters | `utils/logging.py` | Human + machine logs |
| Error collection | `backup/exporter.py` | Partial success handling |
| Pagination iterators | `notion/client.py` | Memory-efficient API |
| Signal handlers | `scheduler/daemon.py` | Graceful shutdown |
| Webhook notifications | `utils/discord.py` | External alerting |
| Status result dataclass | `utils/output.py` | Structured health checks |

---

## Updates

### 2026-01-31

**Configuration Management:**
- `notion_token` can now be set in config file with env var override
- Added configuration source table showing all supported settings

**Webhook Notifications:**
- Removed `enabled` flag requirement; `webhook_url` presence activates notifications
- CLI commands now send both start and completion notifications (previously completion only)
- Updated code examples to use `webhook_url` check instead of `enabled`

**Docker Support:**
- Added Docker deployment patterns in `docs/docker.md`
- Container uses non-root user and health checks
- Graceful shutdown via SIGTERM handling

### 2026-02-01

**Feature Toggles:**
- Added `backup.enabled` and `daily.enabled` configuration options (default: true)
- Added `NOTION_BACKUP_ENABLED` and `NOTION_DAILY_ENABLED` environment variable overrides
- Updated configuration sources table with new settings

**Configuration Display on Startup:**
- CLI commands (`backup`, `daily`, `schedule`) now display configuration summary on startup
- Secrets (tokens, webhook URLs) are masked with `***` for security
