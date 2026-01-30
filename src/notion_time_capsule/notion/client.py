"""Notion API client wrapper with rate limiting and retry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from notion_client import Client
from notion_client.errors import APIResponseError

from notion_time_capsule.notion.rate_limiter import RateLimiter, with_retry
from notion_time_capsule.utils.logging import get_logger

if TYPE_CHECKING:
    from notion_time_capsule.config import Config

logger = get_logger(__name__)


class NotionClient:
    """Wrapped Notion API client with rate limiting and retry logic."""

    def __init__(self, token: str) -> None:
        """Initialize the client.

        Args:
            token: Notion integration token
        """
        self._client = Client(auth=token)
        self._rate_limiter = RateLimiter(requests_per_second=3.0)

    @classmethod
    def from_config(cls, config: Config) -> NotionClient:
        """Create client from configuration.

        Args:
            config: Application configuration

        Returns:
            Configured NotionClient instance
        """
        return cls(token=config.notion_token)

    def _rate_limited_call(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        """Make a rate-limited API call."""
        self._rate_limiter.wait()
        return method(*args, **kwargs)

    @with_retry(max_retries=3)
    def search(
        self,
        query: str = "",
        filter_type: str | None = None,
        sort_direction: str = "descending",
        page_size: int = 100,
        start_cursor: str | None = None,
    ) -> dict[str, Any]:
        """Search for pages and databases.

        Args:
            query: Search query string
            filter_type: Filter to "page" or "database"
            sort_direction: Sort by last_edited_time ("ascending" or "descending")
            page_size: Number of results per page (max 100)
            start_cursor: Cursor for pagination

        Returns:
            Search results from Notion API
        """
        params: dict[str, Any] = {
            "page_size": page_size,
            "sort": {
                "direction": sort_direction,
                "timestamp": "last_edited_time",
            },
        }

        if query:
            params["query"] = query

        if filter_type:
            params["filter"] = {"property": "object", "value": filter_type}

        if start_cursor:
            params["start_cursor"] = start_cursor

        return self._rate_limited_call(self._client.search, **params)

    @with_retry(max_retries=3)
    def get_page(self, page_id: str) -> dict[str, Any]:
        """Retrieve a page by ID.

        Args:
            page_id: Notion page ID

        Returns:
            Page object from Notion API
        """
        return self._rate_limited_call(self._client.pages.retrieve, page_id=page_id)

    @with_retry(max_retries=3)
    def get_block_children(
        self,
        block_id: str,
        page_size: int = 100,
        start_cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get children blocks of a block.

        Args:
            block_id: Parent block ID (can be a page ID)
            page_size: Number of blocks per page
            start_cursor: Cursor for pagination

        Returns:
            Block children from Notion API
        """
        params: dict[str, Any] = {
            "block_id": block_id,
            "page_size": page_size,
        }

        if start_cursor:
            params["start_cursor"] = start_cursor

        return self._rate_limited_call(self._client.blocks.children.list, **params)

    @with_retry(max_retries=3)
    def get_database(self, database_id: str) -> dict[str, Any]:
        """Retrieve a database by ID.

        Args:
            database_id: Notion database ID

        Returns:
            Database object from Notion API
        """
        return self._rate_limited_call(
            self._client.databases.retrieve, database_id=database_id
        )

    @with_retry(max_retries=3)
    def query_database(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 100,
        start_cursor: str | None = None,
    ) -> dict[str, Any]:
        """Query a database for pages.

        Args:
            database_id: Notion database ID
            filter_obj: Filter conditions
            sorts: Sort conditions
            page_size: Number of results per page
            start_cursor: Cursor for pagination

        Returns:
            Query results from Notion API
        """
        params: dict[str, Any] = {
            "database_id": database_id,
            "page_size": page_size,
        }

        if filter_obj:
            params["filter"] = filter_obj

        if sorts:
            params["sorts"] = sorts

        if start_cursor:
            params["start_cursor"] = start_cursor

        return self._rate_limited_call(self._client.databases.query, **params)

    @with_retry(max_retries=3)
    def append_block_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Append children blocks to a block.

        Args:
            block_id: Parent block ID (can be a page ID)
            children: List of block objects to append

        Returns:
            Created blocks from Notion API
        """
        return self._rate_limited_call(
            self._client.blocks.children.append,
            block_id=block_id,
            children=children,
        )

    def iter_all_pages(self) -> Any:
        """Iterate through all accessible pages.

        Yields:
            Page objects from search results
        """
        cursor = None

        while True:
            results = self.search(filter_type="page", start_cursor=cursor)

            for item in results.get("results", []):
                yield item

            if not results.get("has_more"):
                break

            cursor = results.get("next_cursor")

    def iter_all_databases(self) -> Any:
        """Iterate through all accessible databases.

        Yields:
            Database objects from search results
        """
        cursor = None

        while True:
            results = self.search(filter_type="database", start_cursor=cursor)

            for item in results.get("results", []):
                yield item

            if not results.get("has_more"):
                break

            cursor = results.get("next_cursor")

    def iter_block_children(self, block_id: str) -> Any:
        """Iterate through all children of a block.

        Args:
            block_id: Parent block ID

        Yields:
            Block objects
        """
        cursor = None

        while True:
            results = self.get_block_children(block_id, start_cursor=cursor)

            for block in results.get("results", []):
                yield block

            if not results.get("has_more"):
                break

            cursor = results.get("next_cursor")

    def iter_database_pages(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Iterate through all pages in a database.

        Args:
            database_id: Notion database ID
            filter_obj: Filter conditions
            sorts: Sort conditions

        Yields:
            Page objects from database
        """
        cursor = None

        while True:
            results = self.query_database(
                database_id,
                filter_obj=filter_obj,
                sorts=sorts,
                start_cursor=cursor,
            )

            for page in results.get("results", []):
                yield page

            if not results.get("has_more"):
                break

            cursor = results.get("next_cursor")
