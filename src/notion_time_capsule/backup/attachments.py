"""Download and manage file attachments."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

import httpx

from notion_time_capsule.utils.atomic import atomic_write
from notion_time_capsule.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class AttachmentDownloader:
    """Download attachments from Notion pages."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize the downloader.

        Args:
            output_dir: Base directory for saving attachments
        """
        self.output_dir = output_dir
        self._client = httpx.Client(timeout=60.0, follow_redirects=True)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> AttachmentDownloader:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def download_attachment(
        self,
        url: str,
        page_id: str,
        block_id: str,
        file_type: str = "file",
    ) -> str | None:
        """Download an attachment and return the local path.

        Args:
            url: URL to download from
            page_id: Parent page ID for directory structure
            block_id: Block ID for unique filename
            file_type: Type hint (image, file, video, etc.)

        Returns:
            Relative path to downloaded file, or None if failed
        """
        if not url:
            return None

        try:
            # Determine filename
            filename = self._get_filename(url, block_id, file_type)

            # Create attachments directory
            attachments_dir = self.output_dir / "pages" / page_id / "attachments"
            attachments_dir.mkdir(parents=True, exist_ok=True)

            file_path = attachments_dir / filename

            # Download the file
            logger.debug("Downloading attachment: %s", url)
            response = self._client.get(url)
            response.raise_for_status()

            # Write atomically
            atomic_write(file_path, response.content, mode="wb")

            logger.info("Downloaded attachment: %s", filename)

            # Return relative path from page directory
            return f"attachments/{filename}"

        except httpx.HTTPError as e:
            logger.warning("Failed to download attachment %s: %s", url, e)
            return None
        except Exception as e:
            logger.error("Error downloading attachment %s: %s", url, e)
            return None

    def _get_filename(self, url: str, block_id: str, file_type: str) -> str:
        """Generate a filename for the attachment.

        Args:
            url: Original URL
            block_id: Block ID for uniqueness
            file_type: Type hint for extension

        Returns:
            Generated filename
        """
        # Try to extract filename from URL
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Get the filename part
        url_filename = Path(path).name if path else ""

        # Clean the filename
        url_filename = re.sub(r'[^\w\-_\.]', '_', url_filename)

        # If we have a decent filename from URL, use it with block_id prefix
        if url_filename and '.' in url_filename:
            ext = Path(url_filename).suffix
            name = Path(url_filename).stem[:50]  # Truncate long names
            return f"{block_id[:8]}_{name}{ext}"

        # Otherwise, generate based on file type
        ext = self._get_extension(file_type, url)
        return f"{block_id[:8]}{ext}"

    def _get_extension(self, file_type: str, url: str) -> str:
        """Determine file extension based on type and URL.

        Args:
            file_type: Type hint (image, video, file, pdf)
            url: Original URL

        Returns:
            File extension including dot
        """
        # Try to get from URL
        parsed = urlparse(url)
        path_ext = Path(parsed.path).suffix.lower()
        if path_ext in (
            '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico',
            '.mp4', '.webm', '.mov', '.avi',
            '.mp3', '.wav', '.ogg', '.m4a',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.md', '.json', '.csv',
            '.zip', '.tar', '.gz',
        ):
            return path_ext

        # Fall back to type-based defaults
        defaults = {
            "image": ".png",
            "video": ".mp4",
            "audio": ".mp3",
            "pdf": ".pdf",
            "file": ".bin",
        }
        return defaults.get(file_type, ".bin")


def process_blocks_for_attachments(
    blocks: list[dict[str, Any]],
    downloader: AttachmentDownloader,
    page_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """Process blocks to download attachments and update URLs.

    Args:
        blocks: List of Notion blocks
        downloader: Attachment downloader instance
        page_id: Page ID for directory structure

    Returns:
        Tuple of (updated blocks, download count)
    """
    download_count = 0

    for block in blocks:
        block_type = block.get("type", "")
        block_id = block.get("id", "")

        # Handle different block types with attachments
        if block_type == "image":
            content = block.get("image", {})
            url = _get_block_file_url(content)
            if url and _is_notion_hosted(url):
                local_path = downloader.download_attachment(
                    url, page_id, block_id, "image"
                )
                if local_path:
                    # Store local path for markdown generation
                    content["_local_path"] = local_path
                    download_count += 1

        elif block_type == "video":
            content = block.get("video", {})
            url = _get_block_file_url(content)
            if url and _is_notion_hosted(url):
                local_path = downloader.download_attachment(
                    url, page_id, block_id, "video"
                )
                if local_path:
                    content["_local_path"] = local_path
                    download_count += 1

        elif block_type == "audio":
            content = block.get("audio", {})
            url = _get_block_file_url(content)
            if url and _is_notion_hosted(url):
                local_path = downloader.download_attachment(
                    url, page_id, block_id, "audio"
                )
                if local_path:
                    content["_local_path"] = local_path
                    download_count += 1

        elif block_type == "file":
            content = block.get("file", {})
            url = _get_block_file_url(content)
            if url and _is_notion_hosted(url):
                local_path = downloader.download_attachment(
                    url, page_id, block_id, "file"
                )
                if local_path:
                    content["_local_path"] = local_path
                    download_count += 1

        elif block_type == "pdf":
            content = block.get("pdf", {})
            url = _get_block_file_url(content)
            if url and _is_notion_hosted(url):
                local_path = downloader.download_attachment(
                    url, page_id, block_id, "pdf"
                )
                if local_path:
                    content["_local_path"] = local_path
                    download_count += 1

    return blocks, download_count


def _get_block_file_url(content: dict[str, Any]) -> str:
    """Extract URL from block file content."""
    file_type = content.get("type", "")
    if file_type == "file":
        return content.get("file", {}).get("url", "")
    elif file_type == "external":
        return content.get("external", {}).get("url", "")
    return ""


def _is_notion_hosted(url: str) -> bool:
    """Check if URL is hosted on Notion's servers."""
    return "secure.notion-static.com" in url or "prod-files-secure" in url
