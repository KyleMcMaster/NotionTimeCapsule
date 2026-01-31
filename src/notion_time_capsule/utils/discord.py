"""Discord webhook notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from notion_time_capsule.utils.logging import get_logger

if TYPE_CHECKING:
    from notion_time_capsule.config import DiscordConfig
    from notion_time_capsule.utils.output import BackupResult, DailyResult

logger = get_logger(__name__)

# Discord embed colors
COLOR_SUCCESS = 0x2ECC71  # Green
COLOR_FAILURE = 0xE74C3C  # Red
COLOR_INFO = 0x3498DB  # Blue


class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(self, config: DiscordConfig) -> None:
        self.config = config
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def notify_backup_started(self, output_dir: str) -> bool:
        """Send notification when backup starts.

        Args:
            output_dir: The backup output directory

        Returns:
            True if notification was sent successfully
        """
        if not self.config.enabled or not self.config.notify_on_start:
            return True

        embed = self._create_embed(
            title="Backup Started",
            description="Notion workspace backup has started.",
            color=COLOR_INFO,
            fields=[
                {"name": "Output Directory", "value": output_dir, "inline": True},
            ],
        )

        return self._send_embed(embed)

    def notify_backup_complete(self, result: BackupResult) -> bool:
        """Send notification when backup completes.

        Args:
            result: The backup result

        Returns:
            True if notification was sent successfully
        """
        if not self.config.enabled:
            return True

        if result.success and not self.config.notify_on_success:
            return True

        if not result.success and not self.config.notify_on_failure:
            return True

        if result.success:
            embed = self._create_embed(
                title="Backup Complete",
                description="Notion workspace backup completed successfully.",
                color=COLOR_SUCCESS,
                fields=[
                    {"name": "Pages Backed Up", "value": str(result.pages_backed_up), "inline": True},
                    {"name": "Pages Skipped", "value": str(result.pages_skipped), "inline": True},
                    {"name": "Attachments", "value": str(result.attachments_downloaded), "inline": True},
                    {"name": "Duration", "value": f"{result.duration_seconds:.1f}s", "inline": True},
                ],
            )
        else:
            error_summary = f"{len(result.errors)} error(s)"
            if result.errors:
                first_error = result.errors[0].get("message", "Unknown error")
                if len(result.errors) > 1:
                    error_summary = f"{first_error}\n... and {len(result.errors) - 1} more"
                else:
                    error_summary = first_error

            embed = self._create_embed(
                title="Backup Failed",
                description="Notion workspace backup completed with errors.",
                color=COLOR_FAILURE,
                fields=[
                    {"name": "Pages Backed Up", "value": str(result.pages_backed_up), "inline": True},
                    {"name": "Errors", "value": error_summary, "inline": False},
                    {"name": "Duration", "value": f"{result.duration_seconds:.1f}s", "inline": True},
                ],
            )

        return self._send_embed(embed)

    def notify_daily_started(self, page_id: str) -> bool:
        """Send notification when daily content generation starts.

        Args:
            page_id: The target Notion page ID

        Returns:
            True if notification was sent successfully
        """
        if not self.config.enabled or not self.config.notify_on_start:
            return True

        embed = self._create_embed(
            title="Daily Content Started",
            description="Daily content generation has started.",
            color=COLOR_INFO,
            fields=[
                {"name": "Target Page", "value": page_id[:8] + "...", "inline": True},
            ],
        )

        return self._send_embed(embed)

    def notify_daily_complete(self, result: DailyResult) -> bool:
        """Send notification when daily content completes.

        Args:
            result: The daily result

        Returns:
            True if notification was sent successfully
        """
        if not self.config.enabled:
            return True

        if result.success and not self.config.notify_on_success:
            return True

        if not result.success and not self.config.notify_on_failure:
            return True

        if result.success:
            embed = self._create_embed(
                title="Daily Content Published",
                description="Daily content was successfully added to Notion.",
                color=COLOR_SUCCESS,
                fields=[
                    {"name": "Blocks Added", "value": str(result.blocks_added), "inline": True},
                    {"name": "Page ID", "value": result.page_id[:8] + "...", "inline": True},
                ],
            )
        else:
            embed = self._create_embed(
                title="Daily Content Failed",
                description="Daily content generation failed.",
                color=COLOR_FAILURE,
                fields=[
                    {"name": "Error", "value": result.error or "Unknown error", "inline": False},
                    {"name": "Page ID", "value": result.page_id[:8] + "...", "inline": True},
                ],
            )

        return self._send_embed(embed)

    def send_test(self) -> bool:
        """Send a test notification to verify webhook configuration.

        Returns:
            True if notification was sent successfully
        """
        embed = self._create_embed(
            title="Test Notification",
            description="Discord webhook is configured correctly.",
            color=COLOR_INFO,
            fields=[
                {"name": "Status", "value": "Connected", "inline": True},
            ],
        )

        return self._send_embed(embed)

    def _create_embed(
        self,
        title: str,
        description: str,
        color: int,
        fields: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a Discord embed object.

        Args:
            title: Embed title
            description: Embed description
            color: Embed color (hex integer)
            fields: Optional list of field dicts

        Returns:
            Discord embed dict
        """
        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now(UTC).isoformat(),
            "footer": {"text": "NotionTimeCapsule"},
        }

        if fields:
            embed["fields"] = fields

        return embed

    def _send_embed(self, embed: dict[str, Any]) -> bool:
        """Send an embed to the Discord webhook.

        Args:
            embed: Discord embed dict

        Returns:
            True if sent successfully
        """
        if not self.config.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        payload = {"embeds": [embed]}

        try:
            response = self.client.post(
                self.config.webhook_url,
                json=payload,
            )
            response.raise_for_status()
            logger.debug("Discord notification sent successfully")
            return True

        except httpx.HTTPStatusError as e:
            logger.error("Discord webhook returned error: %s", e.response.status_code)
            return False

        except httpx.RequestError as e:
            logger.error("Failed to send Discord notification: %s", e)
            return False
