"""Backup state tracking for incremental backups."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from notion_time_capsule.utils.atomic import atomic_write, safe_mkdir
from notion_time_capsule.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PageState:
    """State of a backed-up page."""

    page_id: str
    last_edited_time: str
    content_hash: str
    attachment_hashes: dict[str, str] = field(default_factory=dict)
    backed_up_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "last_edited_time": self.last_edited_time,
            "content_hash": self.content_hash,
            "attachment_hashes": self.attachment_hashes,
            "backed_up_at": self.backed_up_at,
        }

    @classmethod
    def from_dict(cls, page_id: str, data: dict[str, Any]) -> PageState:
        """Create from dictionary."""
        return cls(
            page_id=page_id,
            last_edited_time=data.get("last_edited_time", ""),
            content_hash=data.get("content_hash", ""),
            attachment_hashes=data.get("attachment_hashes", {}),
            backed_up_at=data.get("backed_up_at", ""),
        )


class BackupState:
    """Manages backup state for incremental backups."""

    VERSION = 1

    def __init__(self, state_dir: Path) -> None:
        """Initialize state manager.

        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = safe_mkdir(state_dir)
        self.state_file = self.state_dir / "checksums.json"
        self._pages: dict[str, PageState] = {}
        self._databases: dict[str, PageState] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if not self.state_file.exists():
            logger.debug("No existing state file found")
            return

        try:
            with open(self.state_file) as f:
                data = json.load(f)

            version = data.get("version", 1)
            if version != self.VERSION:
                logger.warning(
                    "State file version mismatch (got %d, expected %d), "
                    "starting fresh",
                    version,
                    self.VERSION,
                )
                return

            for page_id, page_data in data.get("pages", {}).items():
                self._pages[page_id] = PageState.from_dict(page_id, page_data)

            for db_id, db_data in data.get("databases", {}).items():
                self._databases[db_id] = PageState.from_dict(db_id, db_data)

            logger.debug(
                "Loaded state: %d pages, %d databases",
                len(self._pages),
                len(self._databases),
            )

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load state file: %s", e)

    def save(self) -> None:
        """Save state to disk."""
        data = {
            "version": self.VERSION,
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "pages": {
                page_id: state.to_dict()
                for page_id, state in self._pages.items()
            },
            "databases": {
                db_id: state.to_dict()
                for db_id, state in self._databases.items()
            },
        }

        content = json.dumps(data, indent=2)
        atomic_write(self.state_file, content)
        logger.debug("Saved state: %d pages, %d databases",
                    len(self._pages), len(self._databases))

    def needs_backup(
        self,
        page_id: str,
        last_edited_time: str,
        content: str | None = None,
    ) -> bool:
        """Check if a page needs to be backed up.

        Uses fast path (timestamp) first, then content hash if needed.

        Args:
            page_id: Notion page ID
            last_edited_time: Page's last_edited_time from API
            content: Optional content for hash verification

        Returns:
            True if backup is needed
        """
        state = self._pages.get(page_id)

        # New page
        if state is None:
            logger.debug("Page %s is new, needs backup", page_id[:8])
            return True

        # Fast path: check timestamp
        if state.last_edited_time != last_edited_time:
            logger.debug("Page %s timestamp changed, needs backup", page_id[:8])
            return True

        # If content provided, verify hash
        if content is not None:
            content_hash = self._compute_hash(content)
            if state.content_hash != content_hash:
                logger.debug("Page %s content hash changed, needs backup", page_id[:8])
                return True

        logger.debug("Page %s unchanged, skipping", page_id[:8])
        return False

    def update_page(
        self,
        page_id: str,
        last_edited_time: str,
        content: str,
        attachment_hashes: dict[str, str] | None = None,
    ) -> None:
        """Update state for a backed-up page.

        Args:
            page_id: Notion page ID
            last_edited_time: Page's last_edited_time
            content: Backed up content
            attachment_hashes: Hash of each attachment file
        """
        self._pages[page_id] = PageState(
            page_id=page_id,
            last_edited_time=last_edited_time,
            content_hash=self._compute_hash(content),
            attachment_hashes=attachment_hashes or {},
            backed_up_at=datetime.utcnow().isoformat() + "Z",
        )

    def update_database(
        self,
        database_id: str,
        last_edited_time: str,
        schema: str,
    ) -> None:
        """Update state for a backed-up database.

        Args:
            database_id: Notion database ID
            last_edited_time: Database's last_edited_time
            schema: Database schema content
        """
        self._databases[database_id] = PageState(
            page_id=database_id,
            last_edited_time=last_edited_time,
            content_hash=self._compute_hash(schema),
            backed_up_at=datetime.utcnow().isoformat() + "Z",
        )

    def get_page_state(self, page_id: str) -> PageState | None:
        """Get state for a page."""
        return self._pages.get(page_id)

    def get_database_state(self, database_id: str) -> PageState | None:
        """Get state for a database."""
        return self._databases.get(database_id)

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return "sha256:" + hashlib.sha256(content.encode()).hexdigest()
