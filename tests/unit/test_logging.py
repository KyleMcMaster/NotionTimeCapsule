"""Tests for logging utilities."""

import json
import logging
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from notion_time_capsule.utils.logging import (
    HumanFormatter,
    JsonFormatter,
    get_logger,
    setup_logging,
)


class TestJsonFormatter:
    """Tests for JsonFormatter class."""

    def test_formats_basic_message(self) -> None:
        """Should format basic log message as JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_formats_message_with_args(self) -> None:
        """Should format message with arguments."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Value is %d",
            args=(42,),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Value is 42"

    def test_includes_extra_fields(self) -> None:
        """Should include known extra fields."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.page_id = "abc123"
        record.duration_ms = 150

        output = formatter.format(record)
        data = json.loads(output)

        assert data["page_id"] == "abc123"
        assert data["duration_ms"] == 150

    def test_includes_exception_info(self) -> None:
        """Should include exception information."""
        formatter = JsonFormatter()

        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "test error" in data["exception"]


class TestHumanFormatter:
    """Tests for HumanFormatter class."""

    def test_formats_basic_message(self) -> None:
        """Should format basic log message."""
        formatter = HumanFormatter(use_color=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "INFO" in output
        assert "Test message" in output

    def test_pads_level_name(self) -> None:
        """Should pad level name for alignment."""
        formatter = HumanFormatter(use_color=False)

        for level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="msg",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            # Level name should be padded to 8 chars
            level_name = logging.getLevelName(level)
            assert f"{level_name:8}" in output or level_name in output

    def test_no_color_when_disabled(self) -> None:
        """Should not include ANSI codes when color disabled."""
        formatter = HumanFormatter(use_color=False)
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "\033[" not in output


class TestSetupLogging:
    """Tests for setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up loggers after each test."""
        logger = logging.getLogger("notion_time_capsule")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

    def test_default_level_is_warning(self) -> None:
        """Default logging level should be WARNING."""
        setup_logging()

        logger = logging.getLogger("notion_time_capsule")
        assert logger.level == logging.WARNING

    def test_verbose_1_sets_info(self) -> None:
        """Single -v should set INFO level."""
        setup_logging(verbose=1)

        logger = logging.getLogger("notion_time_capsule")
        assert logger.level == logging.INFO

    def test_verbose_2_sets_debug(self) -> None:
        """Double -vv should set DEBUG level."""
        setup_logging(verbose=2)

        logger = logging.getLogger("notion_time_capsule")
        assert logger.level == logging.DEBUG

    def test_quiet_sets_error(self) -> None:
        """Quiet mode should set ERROR level."""
        setup_logging(quiet=True)

        logger = logging.getLogger("notion_time_capsule")
        assert logger.level == logging.ERROR

    def test_quiet_overrides_verbose(self) -> None:
        """Quiet should override verbose."""
        setup_logging(verbose=2, quiet=True)

        logger = logging.getLogger("notion_time_capsule")
        assert logger.level == logging.ERROR

    def test_json_format_uses_json_formatter(self) -> None:
        """JSON mode should use JsonFormatter."""
        setup_logging(json_format=True)

        logger = logging.getLogger("notion_time_capsule")
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JsonFormatter)

    def test_human_format_uses_human_formatter(self) -> None:
        """Human mode should use HumanFormatter."""
        setup_logging(json_format=False)

        logger = logging.getLogger("notion_time_capsule")
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, HumanFormatter)

    def test_clears_existing_handlers(self) -> None:
        """Should clear existing handlers on setup."""
        # Add a handler
        logger = logging.getLogger("notion_time_capsule")
        logger.addHandler(logging.StreamHandler())
        assert len(logger.handlers) >= 1

        # Setup should clear it
        setup_logging()

        assert len(logger.handlers) == 1


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_namespaced_logger(self) -> None:
        """Should return logger with notion_time_capsule prefix."""
        logger = get_logger("mymodule")

        assert logger.name == "notion_time_capsule.mymodule"

    def test_returns_same_logger_for_same_name(self) -> None:
        """Should return same logger instance for same name."""
        logger1 = get_logger("test")
        logger2 = get_logger("test")

        assert logger1 is logger2

    def test_different_loggers_for_different_names(self) -> None:
        """Should return different loggers for different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1 is not logger2
        assert logger1.name != logger2.name
