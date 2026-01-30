"""Pydantic models for Notion API objects."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RichTextAnnotations(BaseModel):
    """Text formatting annotations."""

    bold: bool = False
    italic: bool = False
    strikethrough: bool = False
    underline: bool = False
    code: bool = False
    color: str = "default"


class RichTextItem(BaseModel):
    """A single rich text item."""

    type: Literal["text", "mention", "equation"]
    plain_text: str
    href: str | None = None
    annotations: RichTextAnnotations = Field(default_factory=RichTextAnnotations)

    # Type-specific content
    text: dict[str, Any] | None = None
    mention: dict[str, Any] | None = None
    equation: dict[str, Any] | None = None


class FileObject(BaseModel):
    """File reference (internal or external)."""

    type: Literal["file", "external"]
    file: dict[str, Any] | None = None  # For internal files
    external: dict[str, Any] | None = None  # For external URLs

    @property
    def url(self) -> str | None:
        """Get the file URL."""
        if self.type == "file" and self.file:
            return self.file.get("url")
        elif self.type == "external" and self.external:
            return self.external.get("url")
        return None

    @property
    def expiry_time(self) -> str | None:
        """Get expiry time for internal files."""
        if self.type == "file" and self.file:
            return self.file.get("expiry_time")
        return None


class Parent(BaseModel):
    """Block/page parent reference."""

    type: Literal["workspace", "page_id", "database_id", "block_id"]
    workspace: bool | None = None
    page_id: str | None = None
    database_id: str | None = None
    block_id: str | None = None


class User(BaseModel):
    """User reference."""

    object: Literal["user"] = "user"
    id: str
    name: str | None = None
    avatar_url: str | None = None
    type: str | None = None
    person: dict[str, Any] | None = None
    bot: dict[str, Any] | None = None


class PageProperties(BaseModel):
    """Page properties container."""

    # Properties are dynamic based on database schema
    # This is a pass-through model
    model_config = {"extra": "allow"}


class Page(BaseModel):
    """Notion page object."""

    object: Literal["page"] = "page"
    id: str
    created_time: datetime
    last_edited_time: datetime
    created_by: User
    last_edited_by: User
    archived: bool = False
    in_trash: bool = False
    parent: Parent
    properties: dict[str, Any] = Field(default_factory=dict)
    url: str
    public_url: str | None = None

    # Cover and icon
    cover: FileObject | None = None
    icon: dict[str, Any] | None = None

    @property
    def title(self) -> str:
        """Extract page title from properties."""
        for prop in self.properties.values():
            if prop.get("type") == "title":
                title_items = prop.get("title", [])
                return "".join(item.get("plain_text", "") for item in title_items)
        return "Untitled"


class Database(BaseModel):
    """Notion database object."""

    object: Literal["database"] = "database"
    id: str
    created_time: datetime
    last_edited_time: datetime
    created_by: User
    last_edited_by: User
    archived: bool = False
    in_trash: bool = False
    parent: Parent
    title: list[RichTextItem] = Field(default_factory=list)
    description: list[RichTextItem] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    url: str
    public_url: str | None = None
    is_inline: bool = False

    # Cover and icon
    cover: FileObject | None = None
    icon: dict[str, Any] | None = None

    @property
    def title_text(self) -> str:
        """Get database title as plain text."""
        return "".join(item.plain_text for item in self.title)


class Block(BaseModel):
    """Notion block object."""

    object: Literal["block"] = "block"
    id: str
    parent: Parent
    type: str
    created_time: datetime
    last_edited_time: datetime
    created_by: User
    last_edited_by: User
    has_children: bool = False
    archived: bool = False
    in_trash: bool = False

    # Block type-specific content is stored in a field matching the type
    # e.g., paragraph, heading_1, bulleted_list_item, etc.
    model_config = {"extra": "allow"}

    def get_content(self) -> dict[str, Any]:
        """Get the type-specific content for this block."""
        return getattr(self, self.type, {}) or {}


# Block type definitions for reference
BLOCK_TYPES = [
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "code",
    "child_page",
    "child_database",
    "embed",
    "image",
    "video",
    "file",
    "pdf",
    "bookmark",
    "callout",
    "quote",
    "equation",
    "divider",
    "table_of_contents",
    "column",
    "column_list",
    "link_preview",
    "synced_block",
    "template",
    "link_to_page",
    "audio",
    "breadcrumb",
    "table",
    "table_row",
]

# Property types for databases
PROPERTY_TYPES = [
    "title",
    "rich_text",
    "number",
    "select",
    "multi_select",
    "date",
    "people",
    "files",
    "checkbox",
    "url",
    "email",
    "phone_number",
    "formula",
    "relation",
    "rollup",
    "created_time",
    "created_by",
    "last_edited_time",
    "last_edited_by",
    "status",
    "unique_id",
]
