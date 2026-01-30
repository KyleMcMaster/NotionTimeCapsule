"""Command-line interface for NotionTimeCapsule."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from notion_time_capsule import __version__
from notion_time_capsule.config import ConfigurationError, load_config
from notion_time_capsule.utils.logging import setup_logging
from notion_time_capsule.utils.output import ExitCode, OutputFormatter

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

    # Import here to avoid circular imports and defer heavy imports
    from notion_time_capsule.backup.exporter import run_backup

    result = run_backup(
        config=ctx.config,
        page_id=page_id,
    )

    assert ctx.formatter is not None
    ctx.formatter.output(result)

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

    result = run_daily(
        config=ctx.config,
        content=rendered,
    )

    assert ctx.formatter is not None
    ctx.formatter.output(result)

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
