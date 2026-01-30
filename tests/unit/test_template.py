"""Tests for template engine."""

from datetime import datetime

import pytest

from notion_time_capsule.daily.template import TemplateEngine


class TestTemplateEngine:
    """Tests for TemplateEngine class."""

    @pytest.fixture
    def engine(self) -> TemplateEngine:
        """Create a template engine instance."""
        return TemplateEngine()

    @pytest.fixture
    def fixed_date(self) -> datetime:
        """Create a fixed date for testing."""
        return datetime(2025, 3, 15, 14, 30, 45)

    def test_renders_date_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{date}} as YYYY-MM-DD."""
        result = engine.render("Today is {{date}}", fixed_date)

        assert result == "Today is 2025-03-15"

    def test_renders_year_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{year}}."""
        result = engine.render("Year: {{year}}", fixed_date)

        assert result == "Year: 2025"

    def test_renders_month_variable_padded(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{month}} zero-padded."""
        result = engine.render("Month: {{month}}", fixed_date)

        assert result == "Month: 03"

    def test_renders_day_variable_padded(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{day}} zero-padded."""
        result = engine.render("Day: {{day}}", fixed_date)

        assert result == "Day: 15"

    def test_renders_weekday_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{weekday}} as full name."""
        result = engine.render("Day: {{weekday}}", fixed_date)

        assert result == "Day: Saturday"

    def test_renders_weekday_short_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{weekday_short}} as abbreviated name."""
        result = engine.render("Day: {{weekday_short}}", fixed_date)

        assert result == "Day: Sat"

    def test_renders_month_name_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{month_name}} as full name."""
        result = engine.render("Month: {{month_name}}", fixed_date)

        assert result == "Month: March"

    def test_renders_month_short_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{month_short}} as abbreviated name."""
        result = engine.render("Month: {{month_short}}", fixed_date)

        assert result == "Month: Mar"

    def test_renders_time_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{time}} as HH:MM."""
        result = engine.render("Time: {{time}}", fixed_date)

        assert result == "Time: 14:30"

    def test_renders_hour_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{hour}} zero-padded."""
        result = engine.render("Hour: {{hour}}", fixed_date)

        assert result == "Hour: 14"

    def test_renders_minute_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{minute}} zero-padded."""
        result = engine.render("Minute: {{minute}}", fixed_date)

        assert result == "Minute: 30"

    def test_renders_iso_date_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{iso_date}} in ISO format."""
        result = engine.render("ISO: {{iso_date}}", fixed_date)

        assert result == "ISO: 2025-03-15T14:30:45"

    def test_renders_week_number_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{week_number}} zero-padded."""
        result = engine.render("Week: {{week_number}}", fixed_date)

        # March 15, 2025 is in week 11
        assert result == "Week: 11"

    def test_renders_quarter_variable(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render {{quarter}} as 1-4."""
        result = engine.render("Q{{quarter}}", fixed_date)

        assert result == "Q1"

    def test_renders_multiple_variables(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should render multiple variables in one template."""
        template = "# {{weekday}}, {{month_name}} {{day}}, {{year}}"
        result = engine.render(template, fixed_date)

        assert result == "# Saturday, March 15, 2025"

    def test_leaves_unknown_variables_unchanged(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should leave unknown variables as-is."""
        result = engine.render("Hello {{unknown}}", fixed_date)

        assert result == "Hello {{unknown}}"

    def test_handles_empty_template(self, engine: TemplateEngine) -> None:
        """Should handle empty template."""
        result = engine.render("")

        assert result == ""

    def test_handles_template_without_variables(
        self, engine: TemplateEngine
    ) -> None:
        """Should return template unchanged if no variables."""
        result = engine.render("Plain text without variables")

        assert result == "Plain text without variables"

    def test_handles_adjacent_variables(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should handle adjacent variables."""
        result = engine.render("{{year}}{{month}}{{day}}", fixed_date)

        assert result == "20250315"

    def test_uses_current_time_by_default(self, engine: TemplateEngine) -> None:
        """Should use current time when no date provided."""
        now = datetime.now()
        result = engine.render("{{year}}")

        assert result == str(now.year)

    def test_preserves_newlines(
        self, engine: TemplateEngine, fixed_date: datetime
    ) -> None:
        """Should preserve newlines in template."""
        template = "Line 1: {{date}}\nLine 2: {{year}}"
        result = engine.render(template, fixed_date)

        assert result == "Line 1: 2025-03-15\nLine 2: 2025"

    def test_quarter_calculations(self, engine: TemplateEngine) -> None:
        """Should calculate quarter correctly for all months."""
        test_cases = [
            (datetime(2025, 1, 1), "1"),
            (datetime(2025, 3, 31), "1"),
            (datetime(2025, 4, 1), "2"),
            (datetime(2025, 6, 30), "2"),
            (datetime(2025, 7, 1), "3"),
            (datetime(2025, 9, 30), "3"),
            (datetime(2025, 10, 1), "4"),
            (datetime(2025, 12, 31), "4"),
        ]

        for date, expected_quarter in test_cases:
            result = engine.render("{{quarter}}", date)
            assert result == expected_quarter, f"Failed for {date}"


class TestTemplateEngineHelpers:
    """Tests for TemplateEngine helper methods."""

    @pytest.fixture
    def engine(self) -> TemplateEngine:
        """Create a template engine instance."""
        return TemplateEngine()

    def test_get_available_variables(self, engine: TemplateEngine) -> None:
        """Should return list of available variables."""
        variables = engine.get_available_variables()

        assert isinstance(variables, list)
        assert "date" in variables
        assert "year" in variables
        assert "month" in variables
        assert "weekday" in variables
        assert sorted(variables) == variables  # Should be sorted

    def test_preview_variables(self, engine: TemplateEngine) -> None:
        """Should preview all variable values."""
        date = datetime(2025, 6, 20, 10, 15, 0)
        preview = engine.preview_variables(date)

        assert isinstance(preview, dict)
        assert preview["date"] == "2025-06-20"
        assert preview["year"] == "2025"
        assert preview["month"] == "06"
        assert preview["day"] == "20"
        assert preview["weekday"] == "Friday"
        assert preview["quarter"] == "2"

    def test_preview_variables_uses_current_time(
        self, engine: TemplateEngine
    ) -> None:
        """Should use current time when no date provided."""
        now = datetime.now()
        preview = engine.preview_variables()

        assert preview["year"] == str(now.year)
