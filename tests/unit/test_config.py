"""Tests for configuration loading and validation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from notion_time_capsule.config import (
    BackupConfig,
    Config,
    ConfigurationError,
    DailyConfig,
    SchedulerConfig,
    load_config,
)


class TestBackupConfig:
    """Tests for BackupConfig dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = BackupConfig()

        assert config.output_dir == Path("./backups")
        assert config.include_attachments is True
        assert config.incremental is True

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = BackupConfig(
            output_dir=Path("/custom/path"),
            include_attachments=False,
            incremental=False,
        )

        assert config.output_dir == Path("/custom/path")
        assert config.include_attachments is False
        assert config.incremental is False


class TestDailyConfig:
    """Tests for DailyConfig dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = DailyConfig()

        assert config.template_path == Path("./templates/daily.md")
        assert config.target_page_id == ""

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = DailyConfig(
            template_path=Path("/my/template.md"),
            target_page_id="abc123def456",
        )

        assert config.template_path == Path("/my/template.md")
        assert config.target_page_id == "abc123def456"


class TestSchedulerConfig:
    """Tests for SchedulerConfig dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = SchedulerConfig()

        assert config.backup_schedule == "daily"
        assert config.daily_time == "06:00"
        assert config.timezone == "America/New_York"

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = SchedulerConfig(
            backup_schedule="hourly",
            daily_time="09:30",
            timezone="Europe/London",
        )

        assert config.backup_schedule == "hourly"
        assert config.daily_time == "09:30"
        assert config.timezone == "Europe/London"


class TestConfig:
    """Tests for main Config dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = Config()

        assert config.notion_token == ""
        assert isinstance(config.backup, BackupConfig)
        assert isinstance(config.daily, DailyConfig)
        assert isinstance(config.scheduler, SchedulerConfig)

    def test_nested_configs_are_independent(self) -> None:
        """Each config instance should have independent nested configs."""
        config1 = Config()
        config2 = Config()

        config1.backup.incremental = False

        assert config2.backup.incremental is True  # Unchanged


class TestConfigValidation:
    """Tests for Config.validate() method."""

    def test_validation_requires_token(self) -> None:
        """Should require NOTION_TOKEN."""
        config = Config(notion_token="")

        errors = config.validate()

        assert any("NOTION_TOKEN" in e for e in errors)

    def test_validation_passes_with_token(self) -> None:
        """Should pass with valid token."""
        config = Config(notion_token="secret_abc123")

        errors = config.validate()

        assert not any("NOTION_TOKEN" in e for e in errors)

    def test_validation_checks_notion_id_format(self) -> None:
        """Should validate Notion ID format."""
        config = Config(
            notion_token="secret_abc123",
            daily=DailyConfig(target_page_id="invalid"),
        )

        errors = config.validate()

        assert any("target_page_id" in e for e in errors)

    def test_validation_accepts_valid_notion_id(self) -> None:
        """Should accept valid Notion ID (32 hex chars)."""
        config = Config(
            notion_token="secret_abc123",
            daily=DailyConfig(target_page_id="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"),
        )

        errors = config.validate()

        assert not any("target_page_id" in e for e in errors)

    def test_validation_accepts_notion_id_with_dashes(self) -> None:
        """Should accept Notion ID with dashes."""
        config = Config(
            notion_token="secret_abc123",
            daily=DailyConfig(
                target_page_id="a1b2c3d4-e5f6-a1b2-c3d4-e5f6a1b2c3d4"
            ),
        )

        errors = config.validate()

        assert not any("target_page_id" in e for e in errors)

    def test_validation_checks_template_exists(self, tmp_path: Path) -> None:
        """Should check if template file exists."""
        config = Config(
            notion_token="secret_abc123",
            daily=DailyConfig(template_path=tmp_path / "nonexistent.md"),
        )

        errors = config.validate()

        assert any("Template file not found" in e for e in errors)

    def test_validation_passes_for_existing_template(
        self, tmp_path: Path
    ) -> None:
        """Should pass if template exists."""
        template = tmp_path / "template.md"
        template.write_text("# Template")

        config = Config(
            notion_token="secret_abc123",
            daily=DailyConfig(template_path=template),
        )

        errors = config.validate()

        assert not any("Template" in e for e in errors)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_defaults_without_file(self, tmp_path: Path) -> None:
        """Should use defaults when no config file."""
        config_path = tmp_path / "nonexistent.toml"

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_path)

        assert config.notion_token == ""
        assert config.backup.output_dir == Path("./backups")

    def test_loads_from_toml_file(self, tmp_path: Path) -> None:
        """Should load values from TOML file."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[backup]
output_dir = "/custom/backups"
include_attachments = false
incremental = false

[daily]
template_path = "/custom/template.md"
target_page_id = "abc123"

[scheduler]
backup_schedule = "hourly"
daily_time = "08:00"
timezone = "UTC"
""")

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_path)

        assert config.backup.output_dir == Path("/custom/backups")
        assert config.backup.include_attachments is False
        assert config.daily.template_path == Path("/custom/template.md")
        assert config.daily.target_page_id == "abc123"
        assert config.scheduler.backup_schedule == "hourly"
        assert config.scheduler.daily_time == "08:00"

    def test_env_var_overrides_file(self, tmp_path: Path) -> None:
        """Environment variables should override file values."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[backup]
output_dir = "/file/path"
""")

        env = {
            "NOTION_TOKEN": "env_token",
            "NOTION_BACKUP_DIR": "/env/path",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_config(config_path)

        assert config.notion_token == "env_token"
        assert config.backup.output_dir == Path("/env/path")

    def test_loads_notion_token_from_env(self) -> None:
        """Should load NOTION_TOKEN from environment."""
        env = {"NOTION_TOKEN": "secret_token_123"}

        with patch.dict(os.environ, env, clear=True):
            config = load_config(None)

        assert config.notion_token == "secret_token_123"

    def test_loads_daily_page_from_env(self) -> None:
        """Should load NOTION_DAILY_PAGE from environment."""
        env = {"NOTION_DAILY_PAGE": "page123"}

        with patch.dict(os.environ, env, clear=True):
            config = load_config(None)

        assert config.daily.target_page_id == "page123"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Should accept path as string."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("[backup]\noutput_dir = '/test'")

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(str(config_path))

        assert config.backup.output_dir == Path("/test")

    def test_default_config_path(self, tmp_path: Path, monkeypatch) -> None:
        """Should use ./config.toml by default."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create config.toml in current directory
        config_path = tmp_path / "config.toml"
        config_path.write_text('[backup]\noutput_dir = "/from/default"')

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(None)

        assert config.backup.output_dir == Path("/from/default")

    def test_partial_config_file(self, tmp_path: Path) -> None:
        """Should handle partial config files."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[backup]
incremental = false
""")  # Only specifies one value

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_path)

        # Specified value should be loaded
        assert config.backup.incremental is False
        # Unspecified values should be defaults
        assert config.backup.output_dir == Path("./backups")
        assert config.backup.include_attachments is True
