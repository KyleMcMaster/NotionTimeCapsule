"""Daemon process for scheduled tasks."""

from __future__ import annotations

import signal
import sys
import time
from typing import TYPE_CHECKING

import schedule

from notion_time_capsule.scheduler.jobs import backup_job, daily_job
from notion_time_capsule.utils.logging import get_logger

if TYPE_CHECKING:
    from notion_time_capsule.config import Config

logger = get_logger(__name__)


class SchedulerDaemon:
    """Daemon process that runs scheduled backup and daily jobs."""

    def __init__(self, config: Config) -> None:
        """Initialize the daemon.

        Args:
            config: Application configuration
        """
        self.config = config
        self._running = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down gracefully...", sig_name)
        self._running = False

    def _setup_schedules(self) -> None:
        """Configure job schedules based on configuration."""
        schedule.clear()

        # Set up backup schedule
        backup_schedule = self.config.scheduler.backup_schedule.lower()

        if backup_schedule == "hourly":
            schedule.every().hour.do(backup_job, self.config)
            logger.info("Backup scheduled: every hour")

        elif backup_schedule == "daily":
            schedule.every().day.at("00:00").do(backup_job, self.config)
            logger.info("Backup scheduled: daily at 00:00")

        elif self._is_cron_expression(backup_schedule):
            # Parse cron expression (simplified - just support common patterns)
            self._schedule_cron(backup_schedule, backup_job)

        else:
            logger.warning(
                "Unknown backup schedule '%s', defaulting to daily",
                backup_schedule,
            )
            schedule.every().day.at("00:00").do(backup_job, self.config)

        # Set up daily content schedule
        daily_time = self.config.scheduler.daily_time

        if self.config.daily.target_page_id:
            schedule.every().day.at(daily_time).do(daily_job, self.config)
            logger.info("Daily content scheduled: every day at %s", daily_time)
        else:
            logger.info("Daily content not scheduled: no target_page_id configured")

    def _is_cron_expression(self, expr: str) -> bool:
        """Check if expression looks like cron syntax."""
        # Simple check: cron has 5 space-separated fields
        parts = expr.split()
        return len(parts) == 5

    def _schedule_cron(
        self,
        cron_expr: str,
        job_func: object,
    ) -> None:
        """Parse and schedule a cron expression.

        Note: This is a simplified cron parser that handles common patterns.
        For full cron support, consider using a dedicated library.

        Args:
            cron_expr: Cron expression (minute hour day month weekday)
            job_func: Job function to schedule
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.warning("Invalid cron expression: %s", cron_expr)
            return

        minute, hour, day, month, weekday = parts

        # Handle simple cases
        if minute == "0" and hour == "*":
            # Every hour at minute 0
            schedule.every().hour.at(":00").do(job_func, self.config)
            logger.info("Backup scheduled: every hour at :00")

        elif minute.isdigit() and hour.isdigit():
            # Specific time daily
            time_str = f"{hour.zfill(2)}:{minute.zfill(2)}"
            schedule.every().day.at(time_str).do(job_func, self.config)
            logger.info("Backup scheduled: daily at %s", time_str)

        elif "*/2" in hour and minute == "0":
            # Every 2 hours
            schedule.every(2).hours.do(job_func, self.config)
            logger.info("Backup scheduled: every 2 hours")

        elif "*/4" in hour and minute == "0":
            # Every 4 hours
            schedule.every(4).hours.do(job_func, self.config)
            logger.info("Backup scheduled: every 4 hours")

        elif "*/6" in hour and minute == "0":
            # Every 6 hours
            schedule.every(6).hours.do(job_func, self.config)
            logger.info("Backup scheduled: every 6 hours")

        elif "*/12" in hour and minute == "0":
            # Every 12 hours
            schedule.every(12).hours.do(job_func, self.config)
            logger.info("Backup scheduled: every 12 hours")

        else:
            logger.warning(
                "Unsupported cron expression '%s', defaulting to daily",
                cron_expr,
            )
            schedule.every().day.at("00:00").do(job_func, self.config)

    def run(self) -> None:
        """Run the scheduler daemon."""
        logger.info("Starting scheduler daemon")
        self._setup_schedules()

        self._running = True
        logger.info("Scheduler running. Press Ctrl+C to stop.")

        # Show next run times
        jobs = schedule.get_jobs()
        for job in jobs:
            logger.info("Next run: %s", job.next_run)

        try:
            while self._running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute

        except Exception as e:
            logger.error("Scheduler error: %s", e)
            raise

        finally:
            logger.info("Scheduler stopped")


def run_scheduler(config: Config, foreground: bool = True) -> None:
    """Run the scheduler.

    Args:
        config: Application configuration
        foreground: If True, run in foreground (default)
    """
    if not foreground:
        # Daemonize (simplified - just fork)
        # For production, consider using python-daemon or systemd
        logger.warning(
            "Background mode not fully implemented, running in foreground"
        )

    daemon = SchedulerDaemon(config)
    daemon.run()
