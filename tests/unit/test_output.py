"""Tests for output formatting."""

import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from notion_time_capsule.utils.output import (
    BackupResult,
    DailyResult,
    ExitCode,
    OutputFormatter,
)


class TestBackupResult:
    """Tests for BackupResult dataclass."""

    def test_creates_with_all_fields(self) -> None:
        """Should create result with all fields."""
        result = BackupResult(
            success=True,
            pages_backed_up=10,
            pages_skipped=5,
            attachments_downloaded=3,
            errors=[],
            duration_seconds=12.5,
        )

        assert result.success is True
        assert result.pages_backed_up == 10
        assert result.pages_skipped == 5
        assert result.attachments_downloaded == 3
        assert result.errors == []
        assert result.duration_seconds == 12.5

    def test_errors_list(self) -> None:
        """Should store error details."""
        errors = [
            {"type": "page_error", "page_id": "abc", "message": "failed"},
            {"type": "network_error", "message": "timeout"},
        ]
        result = BackupResult(
            success=False,
            pages_backed_up=0,
            pages_skipped=0,
            attachments_downloaded=0,
            errors=errors,
            duration_seconds=1.0,
        )

        assert len(result.errors) == 2
        assert result.errors[0]["type"] == "page_error"


class TestDailyResult:
    """Tests for DailyResult dataclass."""

    def test_creates_success_result(self) -> None:
        """Should create successful result."""
        result = DailyResult(
            success=True,
            page_id="abc123",
            blocks_added=5,
        )

        assert result.success is True
        assert result.page_id == "abc123"
        assert result.blocks_added == 5
        assert result.error is None

    def test_creates_error_result(self) -> None:
        """Should create error result."""
        result = DailyResult(
            success=False,
            page_id="abc123",
            blocks_added=0,
            error="API timeout",
        )

        assert result.success is False
        assert result.error == "API timeout"


class TestOutputFormatter:
    """Tests for OutputFormatter class."""

    def test_json_mode_outputs_json(self) -> None:
        """Should output JSON when json_mode is True."""
        formatter = OutputFormatter(json_mode=True)
        result = BackupResult(
            success=True,
            pages_backed_up=5,
            pages_skipped=2,
            attachments_downloaded=1,
            errors=[],
            duration_seconds=3.5,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            formatter.output(result)
            output = mock_stdout.getvalue()

        data = json.loads(output)
        assert data["success"] is True
        assert data["pages_backed_up"] == 5
        assert data["pages_skipped"] == 2
        assert data["duration_seconds"] == 3.5

    def test_human_mode_outputs_text(self) -> None:
        """Should output human-readable text when json_mode is False."""
        formatter = OutputFormatter(json_mode=False)
        result = BackupResult(
            success=True,
            pages_backed_up=5,
            pages_skipped=2,
            attachments_downloaded=1,
            errors=[],
            duration_seconds=3.5,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            formatter.output(result)
            output = mock_stdout.getvalue()

        assert "5 pages backed up" in output
        assert "2 skipped" in output
        assert "3.5s" in output

    def test_human_mode_shows_errors(self) -> None:
        """Should show errors in human mode."""
        formatter = OutputFormatter(json_mode=False)
        result = BackupResult(
            success=False,
            pages_backed_up=0,
            pages_skipped=0,
            attachments_downloaded=0,
            errors=[
                {"message": "Error 1"},
                {"message": "Error 2"},
            ],
            duration_seconds=1.0,
        )

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            formatter.output(result)
            output = mock_stderr.getvalue()

        assert "2 errors" in output
        assert "Error 1" in output

    def test_daily_result_json(self) -> None:
        """Should output DailyResult as JSON."""
        formatter = OutputFormatter(json_mode=True)
        result = DailyResult(
            success=True,
            page_id="abc123",
            blocks_added=3,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            formatter.output(result)
            output = mock_stdout.getvalue()

        data = json.loads(output)
        assert data["success"] is True
        assert data["page_id"] == "abc123"
        assert data["blocks_added"] == 3

    def test_daily_result_human_success(self) -> None:
        """Should output successful DailyResult as text."""
        formatter = OutputFormatter(json_mode=False)
        result = DailyResult(
            success=True,
            page_id="abc123def456",
            blocks_added=3,
        )

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            formatter.output(result)
            output = mock_stdout.getvalue()

        assert "3 blocks" in output
        assert "abc123de" in output  # Truncated ID

    def test_daily_result_human_error(self) -> None:
        """Should output failed DailyResult with error."""
        formatter = OutputFormatter(json_mode=False)
        result = DailyResult(
            success=False,
            page_id="abc123",
            blocks_added=0,
            error="Connection refused",
        )

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            formatter.output(result)
            output = mock_stderr.getvalue()

        assert "failed" in output.lower()
        assert "Connection refused" in output


class TestExitCode:
    """Tests for ExitCode constants."""

    def test_success_is_zero(self) -> None:
        """SUCCESS should be 0 per Unix convention."""
        assert ExitCode.SUCCESS == 0

    def test_errors_are_nonzero(self) -> None:
        """Error codes should be non-zero."""
        assert ExitCode.GENERAL_ERROR != 0
        assert ExitCode.CONFIGURATION_ERROR != 0
        assert ExitCode.AUTHENTICATION_ERROR != 0
        assert ExitCode.NETWORK_ERROR != 0
        assert ExitCode.RATE_LIMITED != 0
        assert ExitCode.PARTIAL_FAILURE != 0

    def test_codes_are_distinct(self) -> None:
        """All error codes should be distinct."""
        codes = [
            ExitCode.SUCCESS,
            ExitCode.GENERAL_ERROR,
            ExitCode.CONFIGURATION_ERROR,
            ExitCode.AUTHENTICATION_ERROR,
            ExitCode.NETWORK_ERROR,
            ExitCode.RATE_LIMITED,
            ExitCode.PARTIAL_FAILURE,
        ]
        assert len(codes) == len(set(codes))
