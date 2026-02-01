"""Configuration loading and validation."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from notion_time_capsule.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""


@dataclass
class BackupConfig:
    """Backup configuration settings."""

    output_dir: Path = field(default_factory=lambda: Path("./backups"))
    include_attachments: bool = True
    incremental: bool = True


@dataclass
class DailyConfig:
    """Daily content generation settings."""

    template_path: Path = field(default_factory=lambda: Path("./templates/daily.md"))
    target_page_id: str = ""


@dataclass
class SchedulerConfig:
    """Scheduler daemon settings."""

    backup_schedule: str = "daily"  # "hourly", "daily", or cron syntax
    daily_time: str = "06:00"  # 24-hour format
    timezone: str = "America/New_York"


@dataclass
class DiscordConfig:
    """Discord notification settings."""

    webhook_url: str = ""
    enabled: bool = False
    notify_on_start: bool = True
    notify_on_success: bool = True
    notify_on_failure: bool = True


@dataclass
class Config:
    """Main application configuration."""

    notion_token: str = ""
    backup: BackupConfig = field(default_factory=BackupConfig)
    daily: DailyConfig = field(default_factory=DailyConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)

    def validate(self) -> list[str]:
        """Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if not self.notion_token:
            errors.append("notion_token is required (set in config or NOTION_TOKEN env var)")

        if self.daily.target_page_id and not self._is_valid_notion_id(
            self.daily.target_page_id
        ):
            errors.append(f"Invalid target_page_id: {self.daily.target_page_id}")

        if self.daily.template_path and not self.daily.template_path.exists():
            errors.append(f"Template file not found: {self.daily.template_path}")

        if self.discord.enabled and not self.discord.webhook_url:
            errors.append("Discord webhook_url is required when notifications are enabled")

        return errors

    @staticmethod
    def _is_valid_notion_id(id_str: str) -> bool:
        """Check if a string looks like a valid Notion ID."""
        # Notion IDs are 32 hex chars, sometimes with dashes
        clean_id = id_str.replace("-", "")
        return len(clean_id) == 32 and all(c in "0123456789abcdef" for c in clean_id)


def load_config(config_path: Path | str | None = None) -> Config:
    """Load configuration from TOML file and environment variables.

    Priority (highest to lowest):
    1. Environment variables
    2. Config file values
    3. Default values

    Args:
        config_path: Path to TOML config file. If None, tries ./config.toml

    Returns:
        Loaded and merged configuration
    """
    config_data: dict[str, Any] = {}

    # Load from file if it exists
    if config_path is None:
        config_path = Path("./config.toml")

    config_path = Path(config_path)
    if config_path.exists():
        logger.debug("Loading config from %s", config_path)
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
    else:
        logger.debug("No config file found at %s, using defaults", config_path)

    # Build configuration with defaults
    backup_data = config_data.get("backup", {})
    daily_data = config_data.get("daily", {})
    scheduler_data = config_data.get("scheduler", {})
    discord_data = config_data.get("discord", {})

    backup_config = BackupConfig(
        output_dir=Path(backup_data.get("output_dir", "./backups")),
        include_attachments=backup_data.get("include_attachments", True),
        incremental=backup_data.get("incremental", True),
    )

    daily_config = DailyConfig(
        template_path=Path(daily_data.get("template_path", "./templates/daily.md")),
        target_page_id=daily_data.get("target_page_id", ""),
    )

    scheduler_config = SchedulerConfig(
        backup_schedule=scheduler_data.get("backup_schedule", "daily"),
        daily_time=scheduler_data.get("daily_time", "06:00"),
        timezone=scheduler_data.get("timezone", "America/New_York"),
    )

    discord_config = DiscordConfig(
        webhook_url=discord_data.get("webhook_url", ""),
        enabled=discord_data.get("enabled", False),
        notify_on_start=discord_data.get("notify_on_start", True),
        notify_on_success=discord_data.get("notify_on_success", True),
        notify_on_failure=discord_data.get("notify_on_failure", True),
    )

    # Get notion_token from config file first, then env var override
    notion_token = config_data.get("notion_token", "")
    if env_token := os.environ.get("NOTION_TOKEN"):
        notion_token = env_token

    # Allow env var overrides for common settings
    if output_dir := os.environ.get("NOTION_BACKUP_DIR"):
        backup_config.output_dir = Path(output_dir)

    if target_page := os.environ.get("NOTION_DAILY_PAGE"):
        daily_config.target_page_id = target_page

    if webhook_url := os.environ.get("DISCORD_WEBHOOK_URL"):
        discord_config.webhook_url = webhook_url

    return Config(
        notion_token=notion_token,
        backup=backup_config,
        daily=daily_config,
        scheduler=scheduler_config,
        discord=discord_config,
    )
