"""Template engine for daily content generation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Callable


class TemplateEngine:
    """Simple template engine for date variable substitution.

    Supports variables like {{date}}, {{year}}, {{month}}, etc.
    No arbitrary code execution - only predefined date variables.
    """

    # Mapping of variable names to formatter functions
    VARIABLES: dict[str, Callable[[datetime], str]] = {
        "date": lambda dt: dt.strftime("%Y-%m-%d"),
        "year": lambda dt: str(dt.year),
        "month": lambda dt: str(dt.month).zfill(2),
        "day": lambda dt: str(dt.day).zfill(2),
        "weekday": lambda dt: dt.strftime("%A"),
        "weekday_short": lambda dt: dt.strftime("%a"),
        "month_name": lambda dt: dt.strftime("%B"),
        "month_short": lambda dt: dt.strftime("%b"),
        "iso_date": lambda dt: dt.isoformat(),
        "iso_datetime": lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "time": lambda dt: dt.strftime("%H:%M"),
        "hour": lambda dt: str(dt.hour).zfill(2),
        "minute": lambda dt: str(dt.minute).zfill(2),
        "timestamp": lambda dt: str(int(dt.timestamp())),
        "week_number": lambda dt: str(dt.isocalendar()[1]).zfill(2),
        "day_of_year": lambda dt: str(dt.timetuple().tm_yday).zfill(3),
        "quarter": lambda dt: str((dt.month - 1) // 3 + 1),
    }

    # Pattern to match {{variable_name}}
    VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def render(self, template: str, date: datetime | None = None) -> str:
        """Render a template by substituting date variables.

        Args:
            template: Template string with {{variable}} placeholders
            date: Date to use for substitution (defaults to now)

        Returns:
            Rendered string with variables replaced
        """
        if date is None:
            date = datetime.now()

        def replace_variable(match: re.Match[str]) -> str:
            var_name = match.group(1)
            formatter = self.VARIABLES.get(var_name)
            if formatter:
                return formatter(date)
            # Unknown variable - leave as-is
            return match.group(0)

        return self.VARIABLE_PATTERN.sub(replace_variable, template)

    def get_available_variables(self) -> list[str]:
        """Get list of available variable names.

        Returns:
            Sorted list of variable names
        """
        return sorted(self.VARIABLES.keys())

    def preview_variables(self, date: datetime | None = None) -> dict[str, str]:
        """Preview all variable values for a given date.

        Args:
            date: Date to use (defaults to now)

        Returns:
            Dict mapping variable names to their values
        """
        if date is None:
            date = datetime.now()

        return {
            name: formatter(date)
            for name, formatter in sorted(self.VARIABLES.items())
        }
