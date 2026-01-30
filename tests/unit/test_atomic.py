"""Tests for atomic file operations."""

import os
import tempfile
from pathlib import Path

import pytest

from notion_time_capsule.utils.atomic import atomic_write, safe_mkdir


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def test_writes_text_content(self, tmp_path: Path) -> None:
        """Should write text content to file."""
        file_path = tmp_path / "test.txt"
        content = "Hello, World!"

        atomic_write(file_path, content)

        assert file_path.read_text() == content

    def test_writes_binary_content(self, tmp_path: Path) -> None:
        """Should write binary content to file."""
        file_path = tmp_path / "test.bin"
        content = b"\x00\x01\x02\x03"

        atomic_write(file_path, content, mode="wb")

        assert file_path.read_bytes() == content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if they don't exist."""
        file_path = tmp_path / "nested" / "deep" / "test.txt"

        atomic_write(file_path, "content")

        assert file_path.exists()
        assert file_path.read_text() == "content"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Should overwrite existing file content."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("old content")

        atomic_write(file_path, "new content")

        assert file_path.read_text() == "new content"

    def test_no_partial_file_on_exception(self, tmp_path: Path) -> None:
        """Should not leave partial file if write fails."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("original")

        class WriteError(Exception):
            pass

        # Create a content that will cause write to fail
        class FailingContent:
            def __str__(self) -> str:
                raise WriteError("simulated failure")

        with pytest.raises((WriteError, TypeError)):
            atomic_write(file_path, FailingContent())  # type: ignore

        # Original file should be unchanged
        assert file_path.read_text() == "original"

    def test_no_temp_files_left_on_success(self, tmp_path: Path) -> None:
        """Should not leave temp files after successful write."""
        file_path = tmp_path / "test.txt"

        atomic_write(file_path, "content")

        # Check for temp files (start with . and end with .tmp)
        temp_files = list(tmp_path.glob(".*tmp"))
        assert len(temp_files) == 0

    def test_accepts_path_as_string(self, tmp_path: Path) -> None:
        """Should accept path as string."""
        file_path = str(tmp_path / "test.txt")

        atomic_write(file_path, "content")

        assert Path(file_path).read_text() == "content"

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Should handle unicode content correctly."""
        file_path = tmp_path / "test.txt"
        content = "Hello, \u4e16\u754c! \U0001f600"

        atomic_write(file_path, content)

        assert file_path.read_text() == content


class TestSafeMkdir:
    """Tests for safe_mkdir function."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Should create directory."""
        dir_path = tmp_path / "new_dir"

        result = safe_mkdir(dir_path)

        assert dir_path.is_dir()
        assert result == dir_path

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Should create nested directories."""
        dir_path = tmp_path / "a" / "b" / "c"

        result = safe_mkdir(dir_path)

        assert dir_path.is_dir()
        assert result == dir_path

    def test_returns_existing_directory(self, tmp_path: Path) -> None:
        """Should return existing directory without error."""
        dir_path = tmp_path / "existing"
        dir_path.mkdir()

        result = safe_mkdir(dir_path)

        assert dir_path.is_dir()
        assert result == dir_path

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Should accept string path."""
        dir_path = str(tmp_path / "new_dir")

        result = safe_mkdir(dir_path)

        assert Path(dir_path).is_dir()
        assert result == Path(dir_path)
