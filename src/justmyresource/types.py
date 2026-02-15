"""Core type definitions for JustMyResource."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol


class PrefixCollisionWarning(UserWarning):
    """Warning emitted when two resource packs claim the same prefix.

    This warning is raised during pack discovery when multiple packs
    attempt to register the same prefix. The pack with higher priority
    (or registered first at equal priority) wins, but the warning
    alerts users to the collision so they can use qualified names
    (dist/pack:resource) or configure prefix_map if needed.
    """

    pass


class ResourcePack(Protocol):
    """Protocol that all resource sources must implement.

    Pack identity is derived from Python packaging infrastructure:
    - Distribution name (from pyproject.toml [project] name)
    - Entry point name (from pyproject.toml entry-points key)

    The qualified pack name is "dist_name/pack_name" and is always unique.
    """

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

    def get_prefixes(self) -> list[str]:
        """Return list of optional alias prefixes that map to this pack.

        Prefixes are convenience aliases for namespace disambiguation.
        For example, a pack with prefix "luc" can be accessed as "luc:lightbulb".

        Note: The pack's entry point name and qualified name (dist/pack)
        are automatically registered as prefixes. This method only provides
        additional short aliases.

        Returns:
            List of prefix strings (e.g., ["luc", "mi"]).
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
class RegisteredPack:
    """Registered resource pack with resolved identity from packaging infrastructure.

    Pack identity is derived from:
    - dist_name: Python distribution name (from ep.dist.name, globally unique on PyPI)
    - pack_name: Entry point name (from ep.name, unique within a distribution)

    The qualified_name "dist_name/pack_name" is always globally unique.
    """

    dist_name: str
    """Distribution name (from pyproject.toml [project] name)."""

    pack_name: str
    """Entry point name (from pyproject.toml entry-points key)."""

    pack: ResourcePack
    """The ResourcePack instance."""

    aliases: tuple[str, ...]
    """Optional alias prefixes from get_prefixes()."""

    @property
    def qualified_name(self) -> str:
        """Return qualified pack name in 'dist_name/pack_name' format."""
        return f"{self.dist_name}/{self.pack_name}"


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    """Lightweight metadata about a discovered resource (no content loaded)."""

    name: str
    """Resource name/identifier."""

    pack: str
    """Qualified name of the resource pack this resource belongs to (dist/pack format)."""

    content_type: str | None = None
    """MIME type if known, None if unknown."""

    tags: tuple[str, ...] | None = None
    """Optional tags for categorization/search."""
