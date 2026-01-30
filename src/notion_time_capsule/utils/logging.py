"""Structured logging configuration."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra fields
        for key in ("page_id", "block_id", "file_path", "duration_ms"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data)


class HumanFormatter(logging.Formatter):
    """Format log records for human readability."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        super().__init__()
        self.use_color = use_color and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        message = record.getMessage()

        if self.use_color:
            color = self.LEVEL_COLORS.get(level, "")
            level_str = f"{color}{level:8}{self.RESET}"
        else:
            level_str = f"{level:8}"

        formatted = f"{level_str} {message}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logging(
    verbose: int = 0,
    quiet: bool = False,
    json_format: bool = False,
) -> None:
    """Configure logging for the application.

    Per constitution: Progress reporting goes to stderr.

    Args:
        verbose: Verbosity level (0=WARNING, 1=INFO, 2=DEBUG)
        quiet: Suppress non-error output (ERROR level only)
        json_format: Use JSON formatting for machine parsing
    """
    if quiet:
        level = logging.ERROR
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose >= 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    # Configure root logger
    root = logging.getLogger("notion_time_capsule")
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    # Add stderr handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"notion_time_capsule.{name}")
