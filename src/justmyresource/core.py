"""Resource registry for discovering and resolving resources from multiple sources."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

from justmyresource.types import ResourceContent, ResourceInfo, ResourcePack

if TYPE_CHECKING:
    pass


class ResourceRegistry:
    """Registry for discovering and resolving resources from multiple sources.

    The registry discovers resources from:
    1. Resource packs via EntryPoints (priority 100)

    Resources are discovered lazily on first use and cached in memory.
    Higher priority packs override lower priority packs.
    """

    def __init__(self, blocklist: set[str] | None = None) -> None:
        """Initialize resource registry.

        Args:
            blocklist: Set of resource pack names to exclude from discovery.
                Can also be set via RESOURCE_DISCOVERY_BLOCKLIST environment variable.
        """
        self._packs: dict[str, ResourcePack] = {}  # pack_name -> ResourcePack
        self._prefixes: dict[str, str] = {}  # prefix -> pack_name
        self._discovered = False
        self._blocklist = self._parse_blocklist(blocklist)

    def _parse_blocklist(self, blocklist: set[str] | None) -> set[str]:
        """Parse blocklist from constructor and environment variable.

        Args:
            blocklist: Blocklist from constructor.

        Returns:
            Merged set of blocked pack names.
        """
        result = set(blocklist) if blocklist else set()

        # Merge with environment variable
        env_blocklist = os.environ.get("RESOURCE_DISCOVERY_BLOCKLIST", "")
        if env_blocklist:
            result.update(
                name.strip() for name in env_blocklist.split(",") if name.strip()
            )

        return result

    def _get_entry_points(self) -> Iterator[tuple[str, ResourcePack, list[str]]]:
        """Get resource packs from EntryPoints.

        Yields:
            Tuples of (entry_point_name, ResourcePack instance, prefixes list).
        """
        try:
            from importlib.metadata import entry_points

            eps = entry_points(group="justmyresource.packs")
        except ImportError:
            # Python < 3.10 fallback
            try:
                import importlib_metadata

                eps = importlib_metadata.entry_points(group="justmyresource.packs")
            except ImportError:
                return

        for ep in eps:
            try:
                factory = ep.load()
                result = factory()

                # Handle various return types from entry point factory
                prefixes: list[str] = []
                provider: ResourcePack | None = None

                if isinstance(result, tuple):
                    if len(result) == 2:
                        # Option 1: (provider, metadata)
                        provider, metadata = result
                        # Extract prefixes from metadata if it's a dict
                        if isinstance(metadata, dict) and "prefixes" in metadata:
                            prefixes = (
                                metadata["prefixes"]
                                if isinstance(metadata["prefixes"], list)
                                else []
                            )
                    elif len(result) >= 3:
                        # Option 2: (descriptor_type, provider, prefixes)
                        _, provider, prefixes = result[0], result[1], result[2]
                        if not isinstance(prefixes, list):
                            prefixes = []
                elif hasattr(result, "get_resource"):
                    # Option 3: Direct ResourcePack instance
                    provider = result
                    # Get prefixes from the pack if it has the method
                    if hasattr(provider, "get_prefixes"):
                        prefixes = provider.get_prefixes()
                    else:
                        prefixes = []
                else:
                    continue

                if provider is None:
                    continue

                # Verify it implements ResourcePack protocol
                if not (
                    hasattr(provider, "get_resource")
                    and hasattr(provider, "list_resources")
                    and hasattr(provider, "get_priority")
                    and hasattr(provider, "get_name")
                ):
                    continue

                yield (ep.name, provider, prefixes)
            except Exception:
                # Skip invalid entry points
                continue

    def discover(self) -> None:
        """Discover resource packs from all registered EntryPoints (high-priority first).

        Resource packs are discovered lazily—this method only runs once per registry instance.
        Higher priority packs override lower priority packs.
        """
        if self._discovered:
            return

        # Collect all packs with their priorities
        packs: list[tuple[str, ResourcePack, int, list[str]]] = []

        # Load External Packs via EntryPoints
        for ep_name, pack, prefixes in self._get_entry_points():
            if ep_name in self._blocklist:
                continue  # Skip blocked packs

            try:
                pack_name = pack.get_name()
                if pack_name in self._blocklist:
                    continue  # Skip if pack name is blocked

                priority = pack.get_priority()
                packs.append((pack_name, pack, priority, prefixes))
            except Exception:
                continue

        # Sort packs by priority (highest first)
        packs.sort(key=lambda x: x[2], reverse=True)

        # Process packs in priority order
        for pack_name, pack, priority, prefixes in packs:
            # Register pack
            self._packs[pack_name] = pack

            # Register prefixes
            for prefix in prefixes:
                # Higher priority packs override lower priority prefix mappings
                if prefix.lower() not in self._prefixes:
                    self._prefixes[prefix.lower()] = pack_name
                else:
                    # Check if existing pack has lower priority
                    existing_pack_name = self._prefixes[prefix.lower()]
                    existing_pack = self._packs.get(existing_pack_name)
                    if existing_pack and priority > existing_pack.get_priority():
                        self._prefixes[prefix.lower()] = pack_name

        self._discovered = True

    def _resolve_name(self, name: str) -> tuple[str, str]:
        """Resolve a resource name to (pack_name, resource_name).

        Args:
            name: Resource name, optionally with prefix (e.g., "lucide:lightbulb" or "lightbulb").

        Returns:
            Tuple of (pack_name, resource_name).

        Raises:
            ValueError: If prefix is specified but pack is not found.
        """
        if ":" in name:
            prefix, resource_name = name.split(":", 1)
            prefix_lower = prefix.lower()

            if prefix_lower not in self._prefixes:
                raise ValueError(f"Unknown resource pack prefix: {prefix}")

            pack_name = self._prefixes[prefix_lower]
            return (pack_name, resource_name)
        else:
            # No prefix: search packs in priority order
            # Sort packs by priority (highest first)
            sorted_packs = sorted(
                self._packs.items(),
                key=lambda x: x[1].get_priority(),
                reverse=True,
            )

            # Try each pack in priority order
            for pack_name, pack in sorted_packs:
                try:
                    # Check if resource exists by attempting to list (or just try get_resource)
                    # For now, we'll just try get_resource and catch the error
                    # In a future optimization, we could cache resource lists
                    pack.get_resource(name)
                    return (pack_name, name)
                except ValueError:
                    continue

            raise ValueError(f"Resource not found: {name}")

    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content by name.

        Supports prefix-based resolution (e.g., "lucide:lightbulb") or
        priority-based search (e.g., "lightbulb" searches packs in priority order).

        Args:
            name: Resource name, optionally with prefix.

        Returns:
            ResourceContent object containing the resource data and metadata.

        Raises:
            ValueError: If the resource cannot be found.
        """
        self.discover()

        pack_name, resource_name = self._resolve_name(name)
        pack = self._packs[pack_name]

        return pack.get_resource(resource_name)

    def list_resources(self, pack: str | None = None) -> Iterator[ResourceInfo]:
        """List all discovered resources.

        Args:
            pack: Optional pack name to filter by. If None, lists resources from all packs.

        Yields:
            ResourceInfo objects for each discovered resource.
        """
        self.discover()

        if pack:
            if pack not in self._packs:
                return
            pack_instance = self._packs[pack]
            for resource_name in pack_instance.list_resources():
                # Try to get content type from pack if possible
                content_type: str | None = None
                try:
                    resource_content = pack_instance.get_resource(resource_name)
                    content_type = resource_content.content_type
                except Exception:
                    pass

                yield ResourceInfo(
                    name=resource_name,
                    pack=pack,
                    content_type=content_type,
                )
        else:
            # List from all packs
            for pack_name, pack_instance in self._packs.items():
                for resource_name in pack_instance.list_resources():
                    # Try to get content type from pack if possible
                    content_type: str | None = None
                    try:
                        resource_content = pack_instance.get_resource(resource_name)
                        content_type = resource_content.content_type
                    except Exception:
                        pass

                    yield ResourceInfo(
                        name=resource_name,
                        pack=pack_name,
                        content_type=content_type,
                    )

    def list_packs(self) -> Iterator[str]:
        """List all registered resource pack names.

        Yields:
            Resource pack names.
        """
        self.discover()
        yield from self._packs.keys()


# Global default registry instance
_default_registry: ResourceRegistry | None = None


def get_default_registry() -> ResourceRegistry:
    """Get the default global resource registry instance.

    Returns:
        Singleton ResourceRegistry instance.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = ResourceRegistry()
    return _default_registry
