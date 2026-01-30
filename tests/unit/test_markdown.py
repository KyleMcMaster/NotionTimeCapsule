"""Tests for markdown converter."""

import pytest

from notion_time_capsule.backup.markdown import MarkdownConverter


class TestMarkdownConverter:
    """Tests for MarkdownConverter class."""

    @pytest.fixture
    def converter(self) -> MarkdownConverter:
        """Create a converter instance without client."""
        return MarkdownConverter(client=None)

    def test_converts_paragraph(self, converter: MarkdownConverter) -> None:
        """Should convert paragraph block."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Hello, world!"}],
            },
        }

        result = converter.convert_blocks([block])

        assert "Hello, world!" in result
        assert result.endswith("\n\n")

    def test_converts_heading_1(self, converter: MarkdownConverter) -> None:
        """Should convert heading_1 block."""
        block = {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"plain_text": "Main Title"}],
            },
        }

        result = converter.convert_blocks([block])

        assert result.startswith("# Main Title")

    def test_converts_heading_2(self, converter: MarkdownConverter) -> None:
        """Should convert heading_2 block."""
        block = {
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"plain_text": "Section"}],
            },
        }

        result = converter.convert_blocks([block])

        assert result.startswith("## Section")

    def test_converts_heading_3(self, converter: MarkdownConverter) -> None:
        """Should convert heading_3 block."""
        block = {
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"plain_text": "Subsection"}],
            },
        }

        result = converter.convert_blocks([block])

        assert result.startswith("### Subsection")

    def test_converts_bulleted_list_item(
        self, converter: MarkdownConverter
    ) -> None:
        """Should convert bulleted list item."""
        block = {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Item one"}],
            },
        }

        result = converter.convert_blocks([block])

        assert result.strip() == "- Item one"

    def test_converts_numbered_list_item(
        self, converter: MarkdownConverter
    ) -> None:
        """Should convert numbered list item."""
        block = {
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": [{"plain_text": "First item"}],
            },
        }

        result = converter.convert_blocks([block])

        assert result.strip() == "1. First item"

    def test_converts_to_do_unchecked(
        self, converter: MarkdownConverter
    ) -> None:
        """Should convert unchecked to-do item."""
        block = {
            "type": "to_do",
            "to_do": {
                "rich_text": [{"plain_text": "Task"}],
                "checked": False,
            },
        }

        result = converter.convert_blocks([block])

        assert result.strip() == "- [ ] Task"

    def test_converts_to_do_checked(
        self, converter: MarkdownConverter
    ) -> None:
        """Should convert checked to-do item."""
        block = {
            "type": "to_do",
            "to_do": {
                "rich_text": [{"plain_text": "Done task"}],
                "checked": True,
            },
        }

        result = converter.convert_blocks([block])

        assert result.strip() == "- [x] Done task"

    def test_converts_code_block(self, converter: MarkdownConverter) -> None:
        """Should convert code block with language."""
        block = {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": "print('hello')"}],
                "language": "python",
                "caption": [],
            },
        }

        result = converter.convert_blocks([block])

        assert "```python" in result
        assert "print('hello')" in result
        assert "```" in result

    def test_converts_code_block_with_caption(
        self, converter: MarkdownConverter
    ) -> None:
        """Should include caption for code block."""
        block = {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": "code"}],
                "language": "javascript",
                "caption": [{"plain_text": "Example code"}],
            },
        }

        result = converter.convert_blocks([block])

        assert "*Example code*" in result

    def test_converts_quote(self, converter: MarkdownConverter) -> None:
        """Should convert quote block."""
        block = {
            "type": "quote",
            "quote": {
                "rich_text": [{"plain_text": "Famous quote"}],
            },
        }

        result = converter.convert_blocks([block])

        assert "> Famous quote" in result

    def test_converts_callout(self, converter: MarkdownConverter) -> None:
        """Should convert callout block."""
        block = {
            "type": "callout",
            "callout": {
                "rich_text": [{"plain_text": "Important note"}],
                "icon": {"type": "emoji", "emoji": "💡"},
            },
        }

        result = converter.convert_blocks([block])

        assert ">" in result
        assert "Important note" in result

    def test_converts_divider(self, converter: MarkdownConverter) -> None:
        """Should convert divider block."""
        block = {
            "type": "divider",
            "divider": {},
        }

        result = converter.convert_blocks([block])

        assert "---" in result

    def test_converts_image(self, converter: MarkdownConverter) -> None:
        """Should convert image block."""
        block = {
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": "https://example.com/img.png"},
                "caption": [{"plain_text": "My image"}],
            },
        }

        result = converter.convert_blocks([block])

        assert "![My image](https://example.com/img.png)" in result

    def test_converts_bookmark(self, converter: MarkdownConverter) -> None:
        """Should convert bookmark block."""
        block = {
            "type": "bookmark",
            "bookmark": {
                "url": "https://example.com",
                "caption": [{"plain_text": "Example Site"}],
            },
        }

        result = converter.convert_blocks([block])

        assert "[Example Site](https://example.com)" in result

    def test_converts_equation(self, converter: MarkdownConverter) -> None:
        """Should convert equation block."""
        block = {
            "type": "equation",
            "equation": {
                "expression": "E = mc^2",
            },
        }

        result = converter.convert_blocks([block])

        assert "$$" in result
        assert "E = mc^2" in result

    def test_converts_table_of_contents(
        self, converter: MarkdownConverter
    ) -> None:
        """Should convert table of contents block."""
        block = {
            "type": "table_of_contents",
            "table_of_contents": {},
        }

        result = converter.convert_blocks([block])

        assert "[TOC]" in result

    def test_handles_unsupported_block_type(
        self, converter: MarkdownConverter
    ) -> None:
        """Should handle unsupported block types gracefully."""
        block = {
            "type": "unknown_future_type",
        }

        result = converter.convert_blocks([block])

        assert "[Unsupported block: unknown_future_type]" in result

    def test_converts_multiple_blocks(
        self, converter: MarkdownConverter
    ) -> None:
        """Should convert multiple blocks in sequence."""
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {"rich_text": [{"plain_text": "Title"}]},
            },
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Content"}]},
            },
        ]

        result = converter.convert_blocks(blocks)

        assert "# Title" in result
        assert "Content" in result
        # Title should come before content
        assert result.index("Title") < result.index("Content")


class TestRichTextFormatting:
    """Tests for rich text formatting."""

    @pytest.fixture
    def converter(self) -> MarkdownConverter:
        """Create a converter instance."""
        return MarkdownConverter(client=None)

    def test_formats_bold_text(self, converter: MarkdownConverter) -> None:
        """Should format bold text."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "plain_text": "bold",
                        "annotations": {"bold": True},
                    }
                ],
            },
        }

        result = converter.convert_blocks([block])

        assert "**bold**" in result

    def test_formats_italic_text(self, converter: MarkdownConverter) -> None:
        """Should format italic text."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "plain_text": "italic",
                        "annotations": {"italic": True},
                    }
                ],
            },
        }

        result = converter.convert_blocks([block])

        assert "*italic*" in result

    def test_formats_code_text(self, converter: MarkdownConverter) -> None:
        """Should format inline code."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "plain_text": "code",
                        "annotations": {"code": True},
                    }
                ],
            },
        }

        result = converter.convert_blocks([block])

        assert "`code`" in result

    def test_formats_strikethrough_text(
        self, converter: MarkdownConverter
    ) -> None:
        """Should format strikethrough text."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "plain_text": "deleted",
                        "annotations": {"strikethrough": True},
                    }
                ],
            },
        }

        result = converter.convert_blocks([block])

        assert "~~deleted~~" in result

    def test_formats_link(self, converter: MarkdownConverter) -> None:
        """Should format linked text."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "plain_text": "click here",
                        "href": "https://example.com",
                    }
                ],
            },
        }

        result = converter.convert_blocks([block])

        assert "[click here](https://example.com)" in result

    def test_combines_multiple_rich_text_items(
        self, converter: MarkdownConverter
    ) -> None:
        """Should combine multiple rich text items."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"plain_text": "Normal "},
                    {"plain_text": "bold", "annotations": {"bold": True}},
                    {"plain_text": " text"},
                ],
            },
        }

        result = converter.convert_blocks([block])

        assert "Normal **bold** text" in result

    def test_handles_empty_rich_text(
        self, converter: MarkdownConverter
    ) -> None:
        """Should handle empty rich text array."""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [],
            },
        }

        result = converter.convert_blocks([block])

        # Should produce empty paragraph or newline
        assert result.strip() == "" or result == "\n"


class TestNestedBlocks:
    """Tests for nested block handling."""

    @pytest.fixture
    def converter(self) -> MarkdownConverter:
        """Create a converter instance."""
        return MarkdownConverter(client=None)

    def test_indents_nested_list_items(
        self, converter: MarkdownConverter
    ) -> None:
        """Should indent nested content."""
        # Simulate converting at depth 1
        block = {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Nested item"}],
            },
        }

        result = converter._convert_block(block, depth=1)

        assert result.startswith("  ")  # 2 spaces for depth 1

    def test_deeper_nesting_increases_indent(
        self, converter: MarkdownConverter
    ) -> None:
        """Should increase indent with depth."""
        block = {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Deep item"}],
            },
        }

        result = converter._convert_block(block, depth=2)

        assert result.startswith("    ")  # 4 spaces for depth 2
