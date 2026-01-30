"""Job definitions for the scheduler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from notion_time_capsule.backup.exporter import run_backup
from notion_time_capsule.daily.publisher import run_daily
from notion_time_capsule.daily.template import TemplateEngine
from notion_time_capsule.utils.logging import get_logger

if TYPE_CHECKING:
    from notion_time_capsule.config import Config

logger = get_logger(__name__)


def backup_job(config: Config) -> None:
    """Execute a backup job.

    Args:
        config: Application configuration
    """
    logger.info("Starting scheduled backup job")

    try:
        result = run_backup(config)

        if result.success:
            logger.info(
                "Backup job completed: %d pages backed up, %d skipped",
                result.pages_backed_up,
                result.pages_skipped,
            )
        else:
            logger.error(
                "Backup job completed with errors: %d errors",
                len(result.errors),
            )

    except Exception as e:
        logger.error("Backup job failed: %s", e)


def daily_job(config: Config) -> None:
    """Execute a daily content generation job.

    Args:
        config: Application configuration
    """
    logger.info("Starting scheduled daily content job")

    try:
        # Check if daily is configured
        if not config.daily.target_page_id:
            logger.warning("Daily job skipped: no target_page_id configured")
            return

        if not config.daily.template_path.exists():
            logger.warning(
                "Daily job skipped: template not found at %s",
                config.daily.template_path,
            )
            return

        # Read and render template
        engine = TemplateEngine()
        template_content = config.daily.template_path.read_text()
        rendered = engine.render(template_content)

        # Publish
        result = run_daily(config, rendered)

        if result.success:
            logger.info(
                "Daily job completed: %d blocks added to %s",
                result.blocks_added,
                result.page_id[:8],
            )
        else:
            logger.error("Daily job failed: %s", result.error)

    except Exception as e:
        logger.error("Daily job failed: %s", e)
