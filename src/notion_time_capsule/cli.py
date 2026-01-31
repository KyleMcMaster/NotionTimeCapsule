"""Command-line interface for NotionTimeCapsule."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from notion_time_capsule import __version__
from notion_time_capsule.config import ConfigurationError, load_config
from notion_time_capsule.utils.logging import setup_logging
from notion_time_capsule.utils.output import ExitCode, OutputFormatter, StatusResult

if TYPE_CHECKING:
    from notion_time_capsule.config import Config


class Context:
    """CLI context holding shared state."""

    def __init__(self) -> None:
        self.config: Config | None = None
        self.json_mode: bool = False
        self.verbose: int = 0
        self.formatter: OutputFormatter | None = None


pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    help="Path to config file (default: ./config.toml)",
)
@click.option(
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="Output in JSON format",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (can repeat: -vv, -vvv)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress non-error output",
)
@click.version_option(version=__version__, prog_name="notion-time-capsule")
@pass_context
def main(
    ctx: Context,
    config_path: Path | None,
    json_mode: bool,
    verbose: int,
    quiet: bool,
) -> None:
    """NotionTimeCapsule - Backup Notion workspaces to markdown.

    Periodically backup your Notion documents and generate daily content
    from templates.
    """
    ctx.json_mode = json_mode
    ctx.verbose = verbose
    ctx.formatter = OutputFormatter(json_mode=json_mode)

    # Setup logging (to stderr per constitution)
    setup_logging(verbose=verbose, quiet=quiet, json_format=json_mode)

    # Load configuration
    try:
        ctx.config = load_config(config_path)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(ExitCode.CONFIGURATION_ERROR)


@main.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Override output directory for backups",
)
@click.option(
    "--page-id",
    type=str,
    default=None,
    help="Backup only a specific page (by ID)",
)
@click.option(
    "--incremental/--full",
    default=True,
    help="Use incremental backup (default) or full backup",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be backed up without actually doing it",
)
@pass_context
def backup(
    ctx: Context,
    output_dir: Path | None,
    page_id: str | None,
    incremental: bool,
    dry_run: bool,
) -> None:
    """Backup Notion workspace to local markdown files.

    Downloads all accessible pages and databases, converting them to
    markdown with YAML frontmatter. Attachments are downloaded to
    subdirectories.

    Examples:

        notion-time-capsule backup

        notion-time-capsule backup --output-dir ./my-backups

        notion-time-capsule backup --page-id abc123def456
    """
    assert ctx.config is not None

    # Validate token
    if not ctx.config.notion_token:
        click.echo("Error: NOTION_TOKEN environment variable is required", err=True)
        sys.exit(ExitCode.AUTHENTICATION_ERROR)

    # Override output directory if specified
    if output_dir:
        ctx.config.backup.output_dir = output_dir

    ctx.config.backup.incremental = incremental

    if dry_run:
        click.echo("Dry run mode - would backup to: " f"{ctx.config.backup.output_dir}")
        return

    # Send Discord notification if enabled
    if ctx.config.discord.enabled:
        from notion_time_capsule.utils.discord import DiscordNotifier

        notifier = DiscordNotifier(ctx.config.discord)
        notifier.notify_backup_started(str(ctx.config.backup.output_dir))
        notifier.close()

    # Import here to avoid circular imports and defer heavy imports
    from notion_time_capsule.backup.exporter import run_backup

    result = run_backup(
        config=ctx.config,
        page_id=page_id,
    )

    assert ctx.formatter is not None
    ctx.formatter.output(result)

    # Send Discord notification if enabled
    if ctx.config.discord.enabled:
        from notion_time_capsule.utils.discord import DiscordNotifier

        notifier = DiscordNotifier(ctx.config.discord)
        notifier.notify_backup_complete(result)
        notifier.close()

    if not result.success:
        sys.exit(ExitCode.PARTIAL_FAILURE if result.pages_backed_up > 0 else ExitCode.GENERAL_ERROR)


@main.command()
@click.option(
    "--template",
    "-t",
    "template_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Override template file path",
)
@click.option(
    "--target-page",
    "-p",
    type=str,
    default=None,
    help="Override target Notion page ID",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show rendered content without publishing",
)
@pass_context
def daily(
    ctx: Context,
    template_path: Path | None,
    target_page: str | None,
    dry_run: bool,
) -> None:
    """Generate and publish daily content from template.

    Reads a markdown template, substitutes date variables, and appends
    the content to the specified Notion page.

    Template variables:
        {{date}}       - Current date (YYYY-MM-DD)
        {{year}}       - Current year
        {{month}}      - Current month (01-12)
        {{day}}        - Current day (01-31)
        {{weekday}}    - Day name (Monday, Tuesday, etc.)
        {{month_name}} - Month name (January, February, etc.)

    Examples:

        notion-time-capsule daily

        notion-time-capsule daily --template ./my-template.md

        notion-time-capsule daily --dry-run
    """
    assert ctx.config is not None

    # Validate token
    if not ctx.config.notion_token:
        click.echo("Error: NOTION_TOKEN environment variable is required", err=True)
        sys.exit(ExitCode.AUTHENTICATION_ERROR)

    # Override settings if specified
    if template_path:
        ctx.config.daily.template_path = template_path

    if target_page:
        ctx.config.daily.target_page_id = target_page

    # Validate target page
    if not ctx.config.daily.target_page_id:
        click.echo("Error: Target page ID is required (--target-page or config)", err=True)
        sys.exit(ExitCode.CONFIGURATION_ERROR)

    # Import here to defer heavy imports
    from notion_time_capsule.daily.publisher import run_daily
    from notion_time_capsule.daily.template import TemplateEngine

    engine = TemplateEngine()

    # Read and render template
    template_content = ctx.config.daily.template_path.read_text()
    rendered = engine.render(template_content)

    if dry_run:
        click.echo("Dry run mode - rendered content:")
        click.echo("-" * 40)
        click.echo(rendered)
        click.echo("-" * 40)
        return

    # Send Discord notification if enabled
    if ctx.config.discord.enabled:
        from notion_time_capsule.utils.discord import DiscordNotifier

        notifier = DiscordNotifier(ctx.config.discord)
        notifier.notify_daily_started(ctx.config.daily.target_page_id)
        notifier.close()

    result = run_daily(
        config=ctx.config,
        content=rendered,
    )

    assert ctx.formatter is not None
    ctx.formatter.output(result)

    # Send Discord notification if enabled
    if ctx.config.discord.enabled:
        from notion_time_capsule.utils.discord import DiscordNotifier

        notifier = DiscordNotifier(ctx.config.discord)
        notifier.notify_daily_complete(result)
        notifier.close()

    if not result.success:
        sys.exit(ExitCode.GENERAL_ERROR)


@main.command()
@click.option(
    "--foreground",
    "-f",
    is_flag=True,
    default=False,
    help="Run in foreground (don't daemonize)",
)
@pass_context
def schedule(ctx: Context, foreground: bool) -> None:
    """Run scheduler daemon for automated tasks.

    Runs backup and daily content generation on configured schedules.
    By default runs as a background daemon.

    Examples:

        notion-time-capsule schedule

        notion-time-capsule schedule --foreground
    """
    assert ctx.config is not None

    # Validate token
    if not ctx.config.notion_token:
        click.echo("Error: NOTION_TOKEN environment variable is required", err=True)
        sys.exit(ExitCode.AUTHENTICATION_ERROR)

    # Import here to defer heavy imports
    from notion_time_capsule.scheduler.daemon import run_scheduler

    click.echo(
        f"Starting scheduler (backup: {ctx.config.scheduler.backup_schedule}, "
        f"daily: {ctx.config.scheduler.daily_time})"
    )

    run_scheduler(config=ctx.config, foreground=foreground)


@main.command()
@pass_context
def status(ctx: Context) -> None:
    """Show backup and system status.

    Displays a health check including last backup time, statistics,
    configuration validity, and notification settings.

    Examples:

        notion-time-capsule status

        notion-time-capsule --json status
    """
    import json as json_module

    assert ctx.config is not None

    # Read backup state if it exists
    state_file = ctx.config.backup.output_dir / ".state" / "checksums.json"
    last_backup_time: str | None = None
    pages_count = 0
    databases_count = 0
    attachments_count = 0

    if state_file.exists():
        with open(state_file, "rb") as f:
            state_data = json_module.load(f)

        last_backup_time = state_data.get("saved_at")
        pages = state_data.get("pages", {})
        databases = state_data.get("databases", {})

        pages_count = len(pages)
        databases_count = len(databases)

        # Count attachments across all pages
        for page_data in pages.values():
            attachments_count += len(page_data.get("attachment_hashes", {}))

    # Validate configuration
    config_errors = ctx.config.validate()
    config_valid = len(config_errors) == 0

    # Check Discord configuration
    discord_enabled = ctx.config.discord.enabled
    discord_configured = bool(ctx.config.discord.webhook_url)

    result = StatusResult(
        config_valid=config_valid,
        config_errors=config_errors,
        last_backup_time=last_backup_time,
        pages_count=pages_count,
        databases_count=databases_count,
        attachments_count=attachments_count,
        backup_dir=str(ctx.config.backup.output_dir),
        backup_dir_exists=ctx.config.backup.output_dir.exists(),
        incremental_enabled=ctx.config.backup.incremental,
        discord_enabled=discord_enabled,
        discord_configured=discord_configured,
    )

    assert ctx.formatter is not None
    ctx.formatter.output(result)

    if not config_valid:
        sys.exit(ExitCode.CONFIGURATION_ERROR)


@main.command("test-discord")
@pass_context
def test_discord(ctx: Context) -> None:
    """Test Discord webhook configuration.

    Sends a test notification to verify the Discord webhook is
    configured correctly and can receive messages.

    Examples:

        notion-time-capsule test-discord
    """
    assert ctx.config is not None

    if not ctx.config.discord.webhook_url:
        click.echo("Error: Discord webhook URL is not configured", err=True)
        sys.exit(ExitCode.CONFIGURATION_ERROR)

    from notion_time_capsule.utils.discord import DiscordNotifier

    notifier = DiscordNotifier(ctx.config.discord)
    success = notifier.send_test()
    notifier.close()

    if success:
        click.echo("Discord test notification sent successfully")
    else:
        click.echo("Error: Failed to send Discord notification", err=True)
        sys.exit(ExitCode.GENERAL_ERROR)


@main.group()
def config() -> None:
    """Manage configuration."""


@config.command("show")
@pass_context
def config_show(ctx: Context) -> None:
    """Show current configuration."""
    assert ctx.config is not None

    if ctx.json_mode:
        import json

        # Serialize config to dict
        config_dict = {
            "notion_token": "***" if ctx.config.notion_token else "(not set)",
            "backup": {
                "output_dir": str(ctx.config.backup.output_dir),
                "include_attachments": ctx.config.backup.include_attachments,
                "incremental": ctx.config.backup.incremental,
            },
            "daily": {
                "template_path": str(ctx.config.daily.template_path),
                "target_page_id": ctx.config.daily.target_page_id or "(not set)",
            },
            "scheduler": {
                "backup_schedule": ctx.config.scheduler.backup_schedule,
                "daily_time": ctx.config.scheduler.daily_time,
                "timezone": ctx.config.scheduler.timezone,
            },
        }
        click.echo(json.dumps(config_dict, indent=2))
    else:
        click.echo("Current configuration:")
        click.echo()
        click.echo(f"  NOTION_TOKEN: {'***' if ctx.config.notion_token else '(not set)'}")
        click.echo()
        click.echo("  [backup]")
        click.echo(f"    output_dir: {ctx.config.backup.output_dir}")
        click.echo(f"    include_attachments: {ctx.config.backup.include_attachments}")
        click.echo(f"    incremental: {ctx.config.backup.incremental}")
        click.echo()
        click.echo("  [daily]")
        click.echo(f"    template_path: {ctx.config.daily.template_path}")
        click.echo(f"    target_page_id: {ctx.config.daily.target_page_id or '(not set)'}")
        click.echo()
        click.echo("  [scheduler]")
        click.echo(f"    backup_schedule: {ctx.config.scheduler.backup_schedule}")
        click.echo(f"    daily_time: {ctx.config.scheduler.daily_time}")
        click.echo(f"    timezone: {ctx.config.scheduler.timezone}")


@config.command("validate")
@pass_context
def config_validate(ctx: Context) -> None:
    """Validate current configuration."""
    assert ctx.config is not None

    errors = ctx.config.validate()

    if errors:
        click.echo("Configuration errors:", err=True)
        for error in errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(ExitCode.CONFIGURATION_ERROR)
    else:
        click.echo("Configuration is valid")


if __name__ == "__main__":
    main()
