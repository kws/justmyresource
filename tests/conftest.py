"""Pytest configuration and fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from justmyresource.core import ResourceRegistry
from justmyresource.types import ResourceContent, ResourceInfo

if TYPE_CHECKING:
    pass


@pytest.fixture
def resource_registry() -> ResourceRegistry:
    """Create a ResourceRegistry instance for testing."""
    return ResourceRegistry()


@pytest.fixture
def empty_resource_registry() -> ResourceRegistry:
    """Create a ResourceRegistry instance with all packs blocked."""
    return ResourceRegistry(blocklist={"*"})


class MockResourcePack:
    """Mock ResourcePack for testing."""

    def __init__(
        self,
        resources: dict[str, ResourceContent],
        priority: int = 100,
        dist_name: str = "test-dist",
        pack_name: str = "test-pack",
        prefixes: list[str] | None = None,
    ) -> None:
        """Initialize mock resource pack.

        Args:
            resources: Dictionary mapping resource names to ResourceContent.
            priority: Priority of this pack.
            dist_name: Distribution name (for testing qualified names).
            pack_name: Pack name (entry point name).
            prefixes: List of alias prefixes for this pack.
        """
        self.resources = resources
        self._priority = priority
        self._dist_name = dist_name
        self._pack_name = pack_name
        self._prefixes = prefixes or []

    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content."""
        if name not in self.resources:
            raise ValueError(f"Resource not found: {name}")
        return self.resources[name]

    def list_resources(self) -> Iterator[str]:
        """List all resource names."""
        yield from self.resources.keys()

    def get_priority(self) -> int:
        """Return priority."""
        return self._priority

    def get_prefixes(self) -> list[str]:
        """Return prefixes."""
        return self._prefixes


def create_test_resource_content(
    data: bytes | str = b"test data",
    content_type: str = "application/octet-stream",
    encoding: str | None = None,
) -> ResourceContent:
    """Create a test ResourceContent object.

    Args:
        data: Resource data (bytes or string).
        content_type: MIME type.
        encoding: Encoding for text resources.

    Returns:
        ResourceContent object.
    """
    if isinstance(data, str):
        if encoding is None:
            encoding = "utf-8"
        data_bytes = data.encode(encoding)
    else:
        data_bytes = data

    return ResourceContent(
        data=data_bytes,
        content_type=content_type,
        encoding=encoding,
    )


def create_test_resource_info(
    name: str = "test-resource",
    pack: str = "test-pack",
    content_type: str | None = None,
) -> ResourceInfo:
    """Create a test ResourceInfo object.

    Args:
        name: Resource name.
        pack: Pack name.
        content_type: MIME type.

    Returns:
        ResourceInfo object.
    """
    return ResourceInfo(
        name=name,
        pack=pack,
        content_type=content_type,
    )
