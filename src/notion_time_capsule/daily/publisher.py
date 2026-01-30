"""Publish daily content to Notion pages."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from notion_time_capsule.notion.client import NotionClient
from notion_time_capsule.utils.logging import get_logger
from notion_time_capsule.utils.output import DailyResult

if TYPE_CHECKING:
    from notion_time_capsule.config import Config

logger = get_logger(__name__)


def run_daily(
    config: Config,
    content: str,
) -> DailyResult:
    """Run daily content generation.

    Args:
        config: Application configuration
        content: Rendered template content to append

    Returns:
        DailyResult with status
    """
    page_id = config.daily.target_page_id

    try:
        client = NotionClient.from_config(config)

        # Convert markdown to Notion blocks
        blocks = markdown_to_blocks(content)

        if not blocks:
            return DailyResult(
                success=False,
                page_id=page_id,
                blocks_added=0,
                error="No content to add",
            )

        # Append blocks to page
        logger.info("Appending %d blocks to page %s", len(blocks), page_id[:8])
        client.append_block_children(page_id, blocks)

        return DailyResult(
            success=True,
            page_id=page_id,
            blocks_added=len(blocks),
        )

    except Exception as e:
        logger.error("Failed to publish daily content: %s", e)
        return DailyResult(
            success=False,
            page_id=page_id,
            blocks_added=0,
            error=str(e),
        )


def markdown_to_blocks(content: str) -> list[dict[str, Any]]:
    """Convert markdown content to Notion block format.

    This is a simplified converter that handles common markdown elements.
    For full markdown support, consider using a proper parser.

    Args:
        content: Markdown content string

    Returns:
        List of Notion block objects
    """
    blocks: list[dict[str, Any]] = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Headings
        if line.startswith("### "):
            blocks.append(_heading_block(line[4:], 3))
            i += 1
            continue

        if line.startswith("## "):
            blocks.append(_heading_block(line[3:], 2))
            i += 1
            continue

        if line.startswith("# "):
            blocks.append(_heading_block(line[2:], 1))
            i += 1
            continue

        # Bulleted list
        if line.startswith("- ") or line.startswith("* "):
            blocks.append(_bulleted_list_block(line[2:]))
            i += 1
            continue

        # Numbered list
        numbered_match = re.match(r"^\d+\.\s+(.+)$", line)
        if numbered_match:
            blocks.append(_numbered_list_block(numbered_match.group(1)))
            i += 1
            continue

        # To-do items
        if line.startswith("- [ ] "):
            blocks.append(_todo_block(line[6:], checked=False))
            i += 1
            continue

        if line.startswith("- [x] ") or line.startswith("- [X] "):
            blocks.append(_todo_block(line[6:], checked=True))
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            quote_lines = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                quote_lines.append(lines[i][2:])
                i += 1
            blocks.append(_quote_block("\n".join(quote_lines)))
            continue

        # Code block
        if line.startswith("```"):
            language = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # Skip closing ```
            blocks.append(_code_block("\n".join(code_lines), language))
            continue

        # Divider
        if line.strip() in ("---", "***", "___"):
            blocks.append(_divider_block())
            i += 1
            continue

        # Default: paragraph
        blocks.append(_paragraph_block(line))
        i += 1

    return blocks


def _rich_text(text: str) -> list[dict[str, Any]]:
    """Create rich text array from plain text.

    Handles basic inline formatting: **bold**, *italic*, `code`, [links](url)

    Args:
        text: Text with potential formatting

    Returns:
        Rich text array for Notion API
    """
    # Simple approach: handle plain text for now
    # Full markdown parsing would require a proper parser
    result: list[dict[str, Any]] = []

    # Handle links
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    last_end = 0

    for match in link_pattern.finditer(text):
        # Add text before link
        if match.start() > last_end:
            before_text = text[last_end:match.start()]
            result.extend(_format_text_segment(before_text))

        # Add link
        link_text = match.group(1)
        link_url = match.group(2)
        result.append({
            "type": "text",
            "text": {
                "content": link_text,
                "link": {"url": link_url},
            },
        })

        last_end = match.end()

    # Add remaining text
    if last_end < len(text):
        result.extend(_format_text_segment(text[last_end:]))

    return result if result else [{"type": "text", "text": {"content": text}}]


def _format_text_segment(text: str) -> list[dict[str, Any]]:
    """Format a text segment with inline styles.

    Args:
        text: Text segment

    Returns:
        Rich text items
    """
    result: list[dict[str, Any]] = []

    # Handle inline code
    code_pattern = re.compile(r'`([^`]+)`')
    # Handle bold
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
    # Handle italic
    italic_pattern = re.compile(r'\*([^*]+)\*')

    # Simple approach: process each pattern
    # Note: This doesn't handle nested formatting well
    remaining = text

    # Process code first
    for match in code_pattern.finditer(text):
        before = text[:match.start()]
        if before:
            result.append({
                "type": "text",
                "text": {"content": before},
            })
        result.append({
            "type": "text",
            "text": {"content": match.group(1)},
            "annotations": {"code": True},
        })
        remaining = text[match.end():]

    if not result:
        result.append({
            "type": "text",
            "text": {"content": text},
        })

    return result


def _paragraph_block(text: str) -> dict[str, Any]:
    """Create a paragraph block."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": _rich_text(text),
        },
    }


def _heading_block(text: str, level: int) -> dict[str, Any]:
    """Create a heading block."""
    heading_type = f"heading_{level}"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": _rich_text(text),
        },
    }


def _bulleted_list_block(text: str) -> dict[str, Any]:
    """Create a bulleted list item block."""
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": _rich_text(text),
        },
    }


def _numbered_list_block(text: str) -> dict[str, Any]:
    """Create a numbered list item block."""
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": _rich_text(text),
        },
    }


def _todo_block(text: str, checked: bool = False) -> dict[str, Any]:
    """Create a to-do block."""
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": _rich_text(text),
            "checked": checked,
        },
    }


def _quote_block(text: str) -> dict[str, Any]:
    """Create a quote block."""
    return {
        "object": "block",
        "type": "quote",
        "quote": {
            "rich_text": _rich_text(text),
        },
    }


def _code_block(code: str, language: str = "") -> dict[str, Any]:
    """Create a code block."""
    # Notion has specific language values
    # Map common aliases
    lang_map = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "rb": "ruby",
        "sh": "bash",
        "": "plain text",
    }
    language = lang_map.get(language.lower(), language.lower()) or "plain text"

    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": code}}],
            "language": language,
        },
    }


def _divider_block() -> dict[str, Any]:
    """Create a divider block."""
    return {
        "object": "block",
        "type": "divider",
        "divider": {},
    }
