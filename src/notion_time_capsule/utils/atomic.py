"""Atomic file operations for safe writes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import contextmanager


def atomic_write(path: Path | str, content: str | bytes, mode: str = "w") -> None:
    """Write content to file atomically using temp file + rename.

    This ensures that interrupted writes don't leave partial files.
    The temp file is created in the same directory to ensure atomic
    rename on POSIX systems.

    Args:
        path: Target file path
        content: Content to write
        mode: Write mode ('w' for text, 'wb' for binary)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory for atomic rename
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
        # Clean up temp file on any failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def safe_mkdir(path: Path | str) -> Path:
    """Create directory if it doesn't exist, returning the path.

    Args:
        path: Directory path to create

    Returns:
        The created/existing directory path
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
