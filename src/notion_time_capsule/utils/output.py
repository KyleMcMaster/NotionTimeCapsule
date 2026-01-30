"""Output formatting for CLI results."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    pages_backed_up: int
    pages_skipped: int
    attachments_downloaded: int
    errors: list[dict[str, Any]]
    duration_seconds: float


@dataclass
class DailyResult:
    """Result of a daily content operation."""

    success: bool
    page_id: str
    blocks_added: int
    error: str | None = None


class OutputFormatter:
    """Format and output results to stdout.

    Per constitution: Data output goes to stdout (not stderr).
    """

    def __init__(self, json_mode: bool = False) -> None:
        self.json_mode = json_mode

    def output(self, result: BackupResult | DailyResult) -> None:
        """Output the result in the configured format."""
        if self.json_mode:
            self._output_json(result)
        else:
            self._output_human(result)

    def _output_json(self, result: BackupResult | DailyResult) -> None:
        """Output result as JSON to stdout."""
        data = asdict(result)
        json.dump(data, sys.stdout, indent=2)
        print()  # Newline

    def _output_human(self, result: BackupResult | DailyResult) -> None:
        """Output result in human-readable format."""
        if isinstance(result, BackupResult):
            self._output_backup_human(result)
        elif isinstance(result, DailyResult):
            self._output_daily_human(result)

    def _output_backup_human(self, result: BackupResult) -> None:
        """Output backup result in human-readable format."""
        if result.success:
            print(
                f"Backup complete: {result.pages_backed_up} pages backed up, "
                f"{result.pages_skipped} skipped, "
                f"{result.attachments_downloaded} attachments downloaded "
                f"({result.duration_seconds:.1f}s)"
            )
        else:
            print(
                f"Backup completed with {len(result.errors)} errors",
                file=sys.stderr,
            )
            for error in result.errors[:5]:  # Show first 5 errors
                print(f"  - {error.get('message', 'Unknown error')}", file=sys.stderr)
            if len(result.errors) > 5:
                print(f"  ... and {len(result.errors) - 5} more errors", file=sys.stderr)

    def _output_daily_human(self, result: DailyResult) -> None:
        """Output daily result in human-readable format."""
        if result.success:
            print(f"Daily content added: {result.blocks_added} blocks to page {result.page_id}")
        else:
            print(f"Daily content failed: {result.error}", file=sys.stderr)


# Exit codes per constitution (Unix conventions)
class ExitCode:
    """Exit codes following Unix conventions."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIGURATION_ERROR = 2
    AUTHENTICATION_ERROR = 3
    NETWORK_ERROR = 4
    RATE_LIMITED = 5
    PARTIAL_FAILURE = 6  # Some items succeeded, others failed
