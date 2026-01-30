"""Convert Notion blocks to markdown."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from notion_time_capsule.notion.client import NotionClient


class MarkdownConverter:
    """Convert Notion blocks to markdown format."""

    def __init__(self, client: NotionClient | None = None) -> None:
        """Initialize converter.

        Args:
            client: Notion client for fetching nested blocks
        """
        self._client = client

    def convert_blocks(self, blocks: list[dict[str, Any]], depth: int = 0) -> str:
        """Convert a list of blocks to markdown.

        Args:
            blocks: List of Notion block objects
            depth: Nesting depth for indentation

        Returns:
            Markdown string
        """
        result: list[str] = []
        list_type: str | None = None

        for block in blocks:
            block_type = block.get("type", "")

            # Handle list continuity
            is_list_item = block_type in (
                "bulleted_list_item",
                "numbered_list_item",
            )
            if not is_list_item and list_type:
                list_type = None
            elif is_list_item:
                list_type = block_type

            # Convert block
            markdown = self._convert_block(block, depth)
            if markdown:
                result.append(markdown)

        return "".join(result)

    def _convert_block(self, block: dict[str, Any], depth: int = 0) -> str:
        """Convert a single block to markdown.

        Args:
            block: Notion block object
            depth: Nesting depth

        Returns:
            Markdown string for this block
        """
        block_type = block.get("type", "unsupported")
        converter: Callable[[dict[str, Any], int], str] = getattr(
            self, f"_convert_{block_type}", self._convert_unsupported
        )
        return converter(block, depth)

    def _rich_text_to_markdown(self, rich_text: list[dict[str, Any]]) -> str:
        """Convert rich text array to markdown with formatting.

        Args:
            rich_text: List of rich text items

        Returns:
            Formatted markdown string
        """
        result: list[str] = []

        for item in rich_text:
            text = item.get("plain_text", "")
            annotations = item.get("annotations", {})
            href = item.get("href")

            # Apply formatting
            if annotations.get("code"):
                text = f"`{text}`"
            if annotations.get("bold"):
                text = f"**{text}**"
            if annotations.get("italic"):
                text = f"*{text}*"
            if annotations.get("strikethrough"):
                text = f"~~{text}~~"
            if href:
                text = f"[{text}]({href})"

            result.append(text)

        return "".join(result)

    def _rich_text_to_plain(self, rich_text: list[dict[str, Any]]) -> str:
        """Convert rich text array to plain text.

        Args:
            rich_text: List of rich text items

        Returns:
            Plain text string
        """
        return "".join(item.get("plain_text", "") for item in rich_text)

    def _get_indent(self, depth: int) -> str:
        """Get indentation string for nested content."""
        return "  " * depth

    def _convert_children(self, block: dict[str, Any], depth: int) -> str:
        """Convert child blocks if present.

        Args:
            block: Parent block
            depth: Current depth

        Returns:
            Markdown for children
        """
        if not block.get("has_children") or not self._client:
            return ""

        children = list(self._client.iter_block_children(block["id"]))
        return self.convert_blocks(children, depth + 1)

    # Block type converters

    def _convert_paragraph(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("paragraph", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        indent = self._get_indent(depth)
        result = f"{indent}{text}\n\n" if text else "\n"
        result += self._convert_children(block, depth)
        return result

    def _convert_heading_1(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("heading_1", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        return f"# {text}\n\n"

    def _convert_heading_2(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("heading_2", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        return f"## {text}\n\n"

    def _convert_heading_3(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("heading_3", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        return f"### {text}\n\n"

    def _convert_bulleted_list_item(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("bulleted_list_item", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        indent = self._get_indent(depth)
        result = f"{indent}- {text}\n"
        result += self._convert_children(block, depth)
        return result

    def _convert_numbered_list_item(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("numbered_list_item", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        indent = self._get_indent(depth)
        # Note: Actual numbering would require tracking state
        result = f"{indent}1. {text}\n"
        result += self._convert_children(block, depth)
        return result

    def _convert_to_do(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("to_do", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        checked = content.get("checked", False)
        checkbox = "[x]" if checked else "[ ]"
        indent = self._get_indent(depth)
        result = f"{indent}- {checkbox} {text}\n"
        result += self._convert_children(block, depth)
        return result

    def _convert_toggle(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("toggle", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        indent = self._get_indent(depth)
        result = f"{indent}<details>\n{indent}<summary>{text}</summary>\n\n"
        result += self._convert_children(block, depth)
        result += f"{indent}</details>\n\n"
        return result

    def _convert_code(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("code", {})
        language = content.get("language", "")
        text = self._rich_text_to_plain(content.get("rich_text", []))
        caption = self._rich_text_to_markdown(content.get("caption", []))
        result = f"```{language}\n{text}\n```\n"
        if caption:
            result += f"*{caption}*\n"
        result += "\n"
        return result

    def _convert_quote(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("quote", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        lines = text.split("\n")
        quoted = "\n".join(f"> {line}" for line in lines)
        result = f"{quoted}\n\n"
        result += self._convert_children(block, depth)
        return result

    def _convert_callout(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("callout", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        icon = content.get("icon", {})
        emoji = icon.get("emoji", "") if icon.get("type") == "emoji" else ""
        result = f"> {emoji} {text}\n\n"
        result += self._convert_children(block, depth)
        return result

    def _convert_divider(self, block: dict[str, Any], depth: int) -> str:
        return "---\n\n"

    def _convert_image(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("image", {})
        caption = self._rich_text_to_markdown(content.get("caption", []))
        url = self._get_file_url(content)
        alt_text = caption or "image"
        return f"![{alt_text}]({url})\n\n"

    def _convert_video(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("video", {})
        caption = self._rich_text_to_markdown(content.get("caption", []))
        url = self._get_file_url(content)
        if caption:
            return f"[{caption}]({url})\n\n"
        return f"[Video]({url})\n\n"

    def _convert_file(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("file", {})
        caption = self._rich_text_to_markdown(content.get("caption", []))
        url = self._get_file_url(content)
        name = caption or content.get("name", "File")
        return f"[{name}]({url})\n\n"

    def _convert_pdf(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("pdf", {})
        caption = self._rich_text_to_markdown(content.get("caption", []))
        url = self._get_file_url(content)
        name = caption or "PDF"
        return f"[{name}]({url})\n\n"

    def _convert_bookmark(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("bookmark", {})
        url = content.get("url", "")
        caption = self._rich_text_to_markdown(content.get("caption", []))
        title = caption or url
        return f"[{title}]({url})\n\n"

    def _convert_embed(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("embed", {})
        url = content.get("url", "")
        caption = self._rich_text_to_markdown(content.get("caption", []))
        if caption:
            return f"[{caption}]({url})\n\n"
        return f"Embed: {url}\n\n"

    def _convert_equation(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("equation", {})
        expression = content.get("expression", "")
        return f"$$\n{expression}\n$$\n\n"

    def _convert_table_of_contents(self, block: dict[str, Any], depth: int) -> str:
        return "[TOC]\n\n"

    def _convert_child_page(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("child_page", {})
        title = content.get("title", "Untitled")
        page_id = block.get("id", "")
        return f"[{title}](./pages/{page_id}/index.md)\n\n"

    def _convert_child_database(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("child_database", {})
        title = content.get("title", "Untitled Database")
        db_id = block.get("id", "")
        return f"[{title}](./databases/{db_id}/)\n\n"

    def _convert_link_to_page(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("link_to_page", {})
        link_type = content.get("type", "")
        page_id = content.get(link_type, "")
        return f"[Linked page](./pages/{page_id}/index.md)\n\n"

    def _convert_column_list(self, block: dict[str, Any], depth: int) -> str:
        # Columns don't translate well to markdown; flatten them
        return self._convert_children(block, depth)

    def _convert_column(self, block: dict[str, Any], depth: int) -> str:
        return self._convert_children(block, depth)

    def _convert_table(self, block: dict[str, Any], depth: int) -> str:
        # Tables need special handling - get children which are table_row blocks
        if not self._client:
            return "[Table]\n\n"

        rows = list(self._client.iter_block_children(block["id"]))
        if not rows:
            return ""

        result: list[str] = []
        for i, row in enumerate(rows):
            cells = row.get("table_row", {}).get("cells", [])
            cell_texts = [self._rich_text_to_markdown(cell) for cell in cells]
            result.append("| " + " | ".join(cell_texts) + " |")

            # Add header separator after first row
            if i == 0:
                result.append("| " + " | ".join("---" for _ in cells) + " |")

        return "\n".join(result) + "\n\n"

    def _convert_table_row(self, block: dict[str, Any], depth: int) -> str:
        # Handled by _convert_table
        return ""

    def _convert_synced_block(self, block: dict[str, Any], depth: int) -> str:
        return self._convert_children(block, depth)

    def _convert_breadcrumb(self, block: dict[str, Any], depth: int) -> str:
        return ""  # Breadcrumbs don't translate to markdown

    def _convert_audio(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("audio", {})
        url = self._get_file_url(content)
        caption = self._rich_text_to_markdown(content.get("caption", []))
        name = caption or "Audio"
        return f"[{name}]({url})\n\n"

    def _convert_link_preview(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("link_preview", {})
        url = content.get("url", "")
        return f"[{url}]({url})\n\n"

    def _convert_template(self, block: dict[str, Any], depth: int) -> str:
        content = block.get("template", {})
        text = self._rich_text_to_markdown(content.get("rich_text", []))
        return f"*Template: {text}*\n\n"

    def _convert_unsupported(self, block: dict[str, Any], depth: int) -> str:
        block_type = block.get("type", "unknown")
        return f"[Unsupported block: {block_type}]\n\n"

    def _get_file_url(self, content: dict[str, Any]) -> str:
        """Extract URL from file content."""
        file_type = content.get("type", "")
        if file_type == "file":
            return content.get("file", {}).get("url", "")
        elif file_type == "external":
            return content.get("external", {}).get("url", "")
        return ""
