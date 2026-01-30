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
8. [Testing Patterns](#testing-patterns)
9. [Type Safety](#type-safety)

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

    # Environment variable overrides
    notion_token = os.environ.get("NOTION_TOKEN", "")

    if output_dir := os.environ.get("NOTION_BACKUP_DIR"):
        backup_config.output_dir = Path(output_dir)
```

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
