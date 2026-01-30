"""YAML frontmatter generation for markdown files."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import yaml


def generate_frontmatter(
    page: dict[str, Any],
    include_properties: bool = True,
) -> str:
    """Generate YAML frontmatter for a page.

    Args:
        page: Notion page object
        include_properties: Whether to include all properties

    Returns:
        YAML frontmatter string with delimiters
    """
    data: dict[str, Any] = {
        "notion_id": page.get("id", ""),
        "title": _extract_title(page),
        "created_time": page.get("created_time", ""),
        "last_edited_time": page.get("last_edited_time", ""),
        "url": page.get("url", ""),
    }

    # Add parent info
    parent = page.get("parent", {})
    parent_type = parent.get("type", "")
    data["parent_type"] = parent_type
    if parent_type == "page_id":
        data["parent_id"] = parent.get("page_id")
    elif parent_type == "database_id":
        data["parent_id"] = parent.get("database_id")
    else:
        data["parent_id"] = None

    # Add creator/editor if available
    created_by = page.get("created_by", {})
    if created_by:
        data["created_by"] = created_by.get("id", "")

    last_edited_by = page.get("last_edited_by", {})
    if last_edited_by:
        data["last_edited_by"] = last_edited_by.get("id", "")

    # Add properties for database pages
    if include_properties:
        properties = _extract_properties(page.get("properties", {}))
        if properties:
            data["properties"] = properties

    # Add cover and icon
    cover = page.get("cover")
    if cover:
        data["cover"] = _extract_file_url(cover)

    icon = page.get("icon")
    if icon:
        icon_type = icon.get("type", "")
        if icon_type == "emoji":
            data["icon"] = icon.get("emoji", "")
        elif icon_type in ("file", "external"):
            data["icon"] = _extract_file_url(icon)

    # Format as YAML with delimiters
    yaml_content = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    return f"---\n{yaml_content}---\n\n"


def generate_database_schema(database: dict[str, Any]) -> str:
    """Generate YAML schema for a database.

    Args:
        database: Notion database object

    Returns:
        YAML schema string
    """
    data: dict[str, Any] = {
        "notion_id": database.get("id", ""),
        "title": _extract_database_title(database),
        "created_time": database.get("created_time", ""),
        "last_edited_time": database.get("last_edited_time", ""),
        "url": database.get("url", ""),
        "is_inline": database.get("is_inline", False),
    }

    # Extract property schema
    properties_schema: dict[str, Any] = {}
    for name, prop in database.get("properties", {}).items():
        prop_type = prop.get("type", "")
        prop_data: dict[str, Any] = {
            "type": prop_type,
            "id": prop.get("id", ""),
        }

        # Add type-specific configuration
        if prop_type == "select":
            options = prop.get("select", {}).get("options", [])
            prop_data["options"] = [opt.get("name", "") for opt in options]
        elif prop_type == "multi_select":
            options = prop.get("multi_select", {}).get("options", [])
            prop_data["options"] = [opt.get("name", "") for opt in options]
        elif prop_type == "status":
            groups = prop.get("status", {}).get("groups", [])
            prop_data["groups"] = [
                {
                    "name": g.get("name", ""),
                    "options": [
                        opt.get("name", "")
                        for opt in g.get("option_ids", [])
                    ],
                }
                for g in groups
            ]
        elif prop_type == "relation":
            relation = prop.get("relation", {})
            prop_data["database_id"] = relation.get("database_id", "")
            prop_data["type"] = relation.get("type", "")
        elif prop_type == "formula":
            formula = prop.get("formula", {})
            prop_data["expression"] = formula.get("expression", "")

        properties_schema[name] = prop_data

    data["properties"] = properties_schema

    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def _extract_title(page: dict[str, Any]) -> str:
    """Extract title from page properties."""
    properties = page.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            title_items = prop.get("title", [])
            return "".join(item.get("plain_text", "") for item in title_items)
    return "Untitled"


def _extract_database_title(database: dict[str, Any]) -> str:
    """Extract title from database."""
    title_items = database.get("title", [])
    return "".join(item.get("plain_text", "") for item in title_items)


def _extract_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Extract property values from page properties.

    Converts Notion property format to simpler key-value pairs.
    """
    result: dict[str, Any] = {}

    for name, prop in properties.items():
        prop_type = prop.get("type", "")
        value = _extract_property_value(prop, prop_type)
        if value is not None:
            result[name] = value

    return result


def _extract_property_value(prop: dict[str, Any], prop_type: str) -> Any:
    """Extract the value from a property based on its type."""
    if prop_type == "title":
        items = prop.get("title", [])
        return "".join(item.get("plain_text", "") for item in items)

    elif prop_type == "rich_text":
        items = prop.get("rich_text", [])
        return "".join(item.get("plain_text", "") for item in items)

    elif prop_type == "number":
        return prop.get("number")

    elif prop_type == "select":
        select = prop.get("select")
        return select.get("name") if select else None

    elif prop_type == "multi_select":
        options = prop.get("multi_select", [])
        return [opt.get("name", "") for opt in options]

    elif prop_type == "status":
        status = prop.get("status")
        return status.get("name") if status else None

    elif prop_type == "date":
        date = prop.get("date")
        if date:
            start = date.get("start", "")
            end = date.get("end")
            if end:
                return f"{start} - {end}"
            return start
        return None

    elif prop_type == "checkbox":
        return prop.get("checkbox", False)

    elif prop_type == "url":
        return prop.get("url")

    elif prop_type == "email":
        return prop.get("email")

    elif prop_type == "phone_number":
        return prop.get("phone_number")

    elif prop_type == "people":
        people = prop.get("people", [])
        return [p.get("name", p.get("id", "")) for p in people]

    elif prop_type == "files":
        files = prop.get("files", [])
        return [_extract_file_url(f) for f in files]

    elif prop_type == "relation":
        relations = prop.get("relation", [])
        return [r.get("id", "") for r in relations]

    elif prop_type == "formula":
        formula = prop.get("formula", {})
        formula_type = formula.get("type", "")
        return formula.get(formula_type)

    elif prop_type == "rollup":
        rollup = prop.get("rollup", {})
        rollup_type = rollup.get("type", "")
        if rollup_type == "array":
            return [_extract_property_value(item, item.get("type", ""))
                    for item in rollup.get("array", [])]
        return rollup.get(rollup_type)

    elif prop_type in ("created_time", "last_edited_time"):
        return prop.get(prop_type)

    elif prop_type in ("created_by", "last_edited_by"):
        user = prop.get(prop_type, {})
        return user.get("name", user.get("id", ""))

    elif prop_type == "unique_id":
        unique_id = prop.get("unique_id", {})
        prefix = unique_id.get("prefix", "")
        number = unique_id.get("number", 0)
        return f"{prefix}-{number}" if prefix else str(number)

    return None


def _extract_file_url(file_obj: dict[str, Any]) -> str:
    """Extract URL from a file object."""
    file_type = file_obj.get("type", "")
    if file_type == "file":
        return file_obj.get("file", {}).get("url", "")
    elif file_type == "external":
        return file_obj.get("external", {}).get("url", "")
    return ""
