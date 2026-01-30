"""Shared pytest fixtures for NotionTimeCapsule tests."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_page() -> dict[str, Any]:
    """Create a sample Notion page object."""
    return {
        "object": "page",
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "created_time": "2025-01-15T10:30:00.000Z",
        "last_edited_time": "2025-01-20T14:22:00.000Z",
        "created_by": {"id": "user123"},
        "last_edited_by": {"id": "user123"},
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "title": {
                "type": "title",
                "title": [{"plain_text": "Test Page"}],
            }
        },
        "url": "https://notion.so/Test-Page-a1b2c3d4e5f67890abcdef1234567890",
    }


@pytest.fixture
def sample_database() -> dict[str, Any]:
    """Create a sample Notion database object."""
    return {
        "object": "database",
        "id": "db123456-7890-abcd-ef12-34567890abcd",
        "created_time": "2025-01-10T08:00:00.000Z",
        "last_edited_time": "2025-01-18T12:00:00.000Z",
        "created_by": {"id": "user123"},
        "last_edited_by": {"id": "user123"},
        "parent": {"type": "workspace", "workspace": True},
        "title": [{"plain_text": "Test Database"}],
        "properties": {
            "Name": {"type": "title", "title": {}},
            "Status": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": "Todo"},
                        {"name": "Done"},
                    ]
                },
            },
        },
        "url": "https://notion.so/db12345678906abcdef1234567890abcd",
    }


@pytest.fixture
def sample_blocks() -> list[dict[str, Any]]:
    """Create sample Notion blocks for testing."""
    return [
        {
            "object": "block",
            "id": "block1",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"plain_text": "Main Title"}],
            },
            "has_children": False,
        },
        {
            "object": "block",
            "id": "block2",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Some paragraph text."}],
            },
            "has_children": False,
        },
        {
            "object": "block",
            "id": "block3",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "First item"}],
            },
            "has_children": False,
        },
        {
            "object": "block",
            "id": "block4",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Second item"}],
            },
            "has_children": False,
        },
    ]


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[backup]
output_dir = "./backups"
include_attachments = true
incremental = true

[daily]
template_path = "./templates/daily.md"
target_page_id = ""

[scheduler]
backup_schedule = "daily"
daily_time = "06:00"
timezone = "America/New_York"
""")
    return config_path


@pytest.fixture
def temp_template_file(tmp_path: Path) -> Path:
    """Create a temporary template file."""
    template_path = tmp_path / "template.md"
    template_path.write_text("""# Daily Entry - {{date}}

## {{weekday}}, {{month_name}} {{day}}, {{year}}

### Notes

""")
    return template_path
