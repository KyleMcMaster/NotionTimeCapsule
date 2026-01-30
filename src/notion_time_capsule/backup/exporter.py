"""Main backup orchestration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from notion_time_capsule.backup.attachments import (
    AttachmentDownloader,
    process_blocks_for_attachments,
)
from notion_time_capsule.backup.frontmatter import (
    generate_database_schema,
    generate_frontmatter,
)
from notion_time_capsule.backup.markdown import MarkdownConverter
from notion_time_capsule.backup.state import BackupState
from notion_time_capsule.notion.client import NotionClient
from notion_time_capsule.utils.atomic import atomic_write, safe_mkdir
from notion_time_capsule.utils.logging import get_logger
from notion_time_capsule.utils.output import BackupResult

if TYPE_CHECKING:
    from notion_time_capsule.config import Config

logger = get_logger(__name__)


def run_backup(
    config: Config,
    page_id: str | None = None,
) -> BackupResult:
    """Run a backup operation.

    Args:
        config: Application configuration
        page_id: Optional specific page ID to backup

    Returns:
        BackupResult with statistics
    """
    start_time = time.monotonic()
    errors: list[dict[str, Any]] = []
    pages_backed_up = 0
    pages_skipped = 0
    attachments_downloaded = 0

    # Initialize components
    client = NotionClient.from_config(config)
    output_dir = safe_mkdir(config.backup.output_dir)
    state_dir = output_dir / ".state"
    state = BackupState(state_dir)
    converter = MarkdownConverter(client)

    try:
        if page_id:
            # Backup specific page
            result = _backup_single_page(
                client=client,
                converter=converter,
                state=state,
                output_dir=output_dir,
                page_id=page_id,
                include_attachments=config.backup.include_attachments,
                incremental=config.backup.incremental,
            )
            if result["backed_up"]:
                pages_backed_up = 1
                attachments_downloaded = result["attachments"]
            elif result["skipped"]:
                pages_skipped = 1
            if result["error"]:
                errors.append(result["error"])
        else:
            # Full workspace backup
            logger.info("Starting workspace backup to %s", output_dir)

            # Backup all pages
            for page in client.iter_all_pages():
                try:
                    result = _backup_single_page(
                        client=client,
                        converter=converter,
                        state=state,
                        output_dir=output_dir,
                        page_id=page["id"],
                        page_data=page,
                        include_attachments=config.backup.include_attachments,
                        incremental=config.backup.incremental,
                    )
                    if result["backed_up"]:
                        pages_backed_up += 1
                        attachments_downloaded += result["attachments"]
                    elif result["skipped"]:
                        pages_skipped += 1
                    if result["error"]:
                        errors.append(result["error"])
                except Exception as e:
                    logger.error("Error backing up page %s: %s", page["id"][:8], e)
                    errors.append({
                        "type": "page_backup_error",
                        "page_id": page["id"],
                        "message": str(e),
                    })

            # Backup all databases
            for database in client.iter_all_databases():
                try:
                    _backup_database(
                        client=client,
                        converter=converter,
                        state=state,
                        output_dir=output_dir,
                        database=database,
                        incremental=config.backup.incremental,
                    )
                except Exception as e:
                    logger.error("Error backing up database %s: %s",
                               database["id"][:8], e)
                    errors.append({
                        "type": "database_backup_error",
                        "database_id": database["id"],
                        "message": str(e),
                    })

        # Save state
        state.save()

    except Exception as e:
        logger.error("Backup failed: %s", e)
        errors.append({
            "type": "backup_error",
            "message": str(e),
        })

    duration = time.monotonic() - start_time
    success = len(errors) == 0 or pages_backed_up > 0

    logger.info(
        "Backup complete: %d pages backed up, %d skipped, %d attachments, "
        "%d errors (%.1fs)",
        pages_backed_up,
        pages_skipped,
        attachments_downloaded,
        len(errors),
        duration,
    )

    return BackupResult(
        success=success,
        pages_backed_up=pages_backed_up,
        pages_skipped=pages_skipped,
        attachments_downloaded=attachments_downloaded,
        errors=errors,
        duration_seconds=duration,
    )


def _backup_single_page(
    client: NotionClient,
    converter: MarkdownConverter,
    state: BackupState,
    output_dir: Path,
    page_id: str,
    page_data: dict[str, Any] | None = None,
    include_attachments: bool = True,
    incremental: bool = True,
) -> dict[str, Any]:
    """Backup a single page.

    Returns:
        Dict with backed_up, skipped, attachments, error keys
    """
    result = {
        "backed_up": False,
        "skipped": False,
        "attachments": 0,
        "error": None,
    }

    try:
        # Fetch page if not provided
        if page_data is None:
            page_data = client.get_page(page_id)

        last_edited = page_data.get("last_edited_time", "")

        # Check if backup needed (incremental mode)
        if incremental and not state.needs_backup(page_id, last_edited):
            result["skipped"] = True
            return result

        # Get page title for logging
        title = _extract_title(page_data)
        logger.info("Backing up page: %s (%s)", title[:50], page_id[:8])

        # Fetch all blocks
        blocks = list(client.iter_block_children(page_id))

        # Process attachments
        attachments_downloaded = 0
        if include_attachments:
            with AttachmentDownloader(output_dir) as downloader:
                blocks, attachments_downloaded = process_blocks_for_attachments(
                    blocks, downloader, page_id
                )

        # Generate markdown content
        frontmatter = generate_frontmatter(page_data)
        body = converter.convert_blocks(blocks)
        content = frontmatter + body

        # Determine output path
        page_dir = output_dir / "pages" / page_id
        safe_mkdir(page_dir)
        output_file = page_dir / "index.md"

        # Write atomically
        atomic_write(output_file, content)

        # Update state
        state.update_page(
            page_id=page_id,
            last_edited_time=last_edited,
            content=content,
        )

        result["backed_up"] = True
        result["attachments"] = attachments_downloaded

    except Exception as e:
        logger.error("Failed to backup page %s: %s", page_id[:8], e)
        result["error"] = {
            "type": "page_error",
            "page_id": page_id,
            "message": str(e),
        }

    return result


def _backup_database(
    client: NotionClient,
    converter: MarkdownConverter,
    state: BackupState,
    output_dir: Path,
    database: dict[str, Any],
    incremental: bool = True,
) -> None:
    """Backup a database and its entries."""
    database_id = database["id"]
    last_edited = database.get("last_edited_time", "")

    # Check if schema changed
    existing = state.get_database_state(database_id)
    schema_changed = existing is None or existing.last_edited_time != last_edited

    # Get database title
    title_items = database.get("title", [])
    title = "".join(item.get("plain_text", "") for item in title_items) or "Untitled"
    logger.info("Backing up database: %s (%s)", title[:50], database_id[:8])

    # Create database directory
    db_dir = output_dir / "databases" / database_id
    safe_mkdir(db_dir)

    # Write schema if changed
    if schema_changed or not incremental:
        schema = generate_database_schema(database)
        atomic_write(db_dir / "_schema.yaml", schema)
        state.update_database(database_id, last_edited, schema)

    # Backup all pages in database
    for page in client.iter_database_pages(database_id):
        page_id = page["id"]
        page_last_edited = page.get("last_edited_time", "")

        if incremental and not state.needs_backup(page_id, page_last_edited):
            continue

        # Generate page content
        blocks = list(client.iter_block_children(page_id))
        frontmatter = generate_frontmatter(page)
        body = converter.convert_blocks(blocks)
        content = frontmatter + body

        # Write page file
        output_file = db_dir / f"{page_id}.md"
        atomic_write(output_file, content)

        # Update state
        state.update_page(page_id, page_last_edited, content)


def _extract_title(page: dict[str, Any]) -> str:
    """Extract title from page properties."""
    properties = page.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            title_items = prop.get("title", [])
            return "".join(item.get("plain_text", "") for item in title_items)
    return "Untitled"
