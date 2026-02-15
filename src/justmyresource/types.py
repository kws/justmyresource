"""Core type definitions for JustMyResource."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol


class ResourcePack(Protocol):
    """Protocol that all resource sources must implement."""

    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content for a name.

        Args:
            name: Resource name/identifier within this pack.

        Returns:
            ResourceContent object containing the resource data and metadata.

        Raises:
            ValueError: If the resource cannot be found.
        """
        ...

    def list_resources(self) -> Iterator[str]:
        """List all available resource names/identifiers.

        Yields:
            Resource name/identifier strings.
        """
        ...

    def get_priority(self) -> int:
        """Return priority for this pack (higher = processed first, overrides lower priority).

        Standard priorities:
        - Resource Packs: 100
        - System Resources: 0 (future consideration)

        Returns:
            Integer priority value (higher = higher priority).
        """
        ...

    def get_name(self) -> str:
        """Return canonical name for this pack (used in blocklist).

        Must be unique and stable.

        Returns:
            String identifier for this resource pack.
        """
        ...

    def get_prefixes(self) -> list[str]:
        """Return list of prefixes that map to this pack.

        Prefixes are used for namespace disambiguation in `pack:name` format.
        For example, a pack with prefix "lucide" can be accessed as "lucide:lightbulb".

        Returns:
            List of prefix strings (e.g., ["lucide", "luc"]).
        """
        ...


@dataclass(frozen=True, slots=True)
class ResourceContent:
    """Content returned by a resource provider."""

    data: bytes
    """Raw resource bytes (SVG as UTF-8 bytes, PNG as-is, etc.)."""

    content_type: str
    """MIME type: 'image/svg+xml', 'image/png', 'audio/wav', etc."""

    encoding: str | None = None
    """Encoding for text-based resources (e.g., 'utf-8'), None for binary."""

    metadata: dict[str, Any] | None = None
    """Optional descriptive details (dimensions, tags, variants, etc.)."""

    @property
    def text(self) -> str:
        """Decode data as text.

        Returns:
            Decoded text content.

        Raises:
            ValueError: If encoding is None or decoding fails.
        """
        if self.encoding is None:
            raise ValueError("Cannot decode binary resource as text (encoding is None)")
        return self.data.decode(self.encoding)


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    """Lightweight metadata about a discovered resource (no content loaded)."""

    name: str
    """Resource name/identifier."""

    pack: str
    """Name of the resource pack this resource belongs to."""

    content_type: str | None = None
    """MIME type if known, None if unknown."""

    tags: tuple[str, ...] | None = None
    """Optional tags for categorization/search."""
