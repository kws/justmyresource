"""Resource registry for discovering and resolving resources from multiple sources."""

from __future__ import annotations

import os
import warnings
from collections.abc import Iterator
from typing import TYPE_CHECKING

from justmyresource.types import (
    PrefixCollisionWarning,
    RegisteredPack,
    ResourceContent,
    ResourceInfo,
    ResourcePack,
)

if TYPE_CHECKING:
    pass


class ResourceRegistry:
    """Registry for discovering and resolving resources from multiple sources.

    The registry discovers resources from:
    1. Resource packs via EntryPoints

    Resources are discovered lazily on first use and cached in memory.
    All packs are equal; they are uniquely identified by their FQN (dist/pack).
    """

    def __init__(
        self,
        blocklist: set[str] | None = None,
        prefix_map: dict[str, str] | None = None,
        default_prefix: str | None = None,
    ) -> None:
        """Initialize resource registry.

        Args:
            blocklist: Set of resource pack names (short or qualified) to exclude from discovery.
                Can also be set via RESOURCE_DISCOVERY_BLOCKLIST environment variable.
                Accepts both short names (pack_name) and qualified names (dist_name/pack_name).
            prefix_map: Optional mapping of alias -> qualified pack name (dist/pack format).
                Applied with highest precedence after discovery. Can also be set via
                RESOURCE_PREFIX_MAP environment variable (format: "alias1=dist1/pack1,alias2=dist2/pack2").
            default_prefix: Optional default prefix for bare-name lookups (no colon).
                Bare names like "lightbulb" will be resolved as "{default_prefix}:lightbulb".
                Can be a FQN (acme-icons/lucide), short name (lucide), or alias.
                Can also be set via RESOURCE_DEFAULT_PREFIX environment variable.
        """
        self._packs: dict[str, RegisteredPack] = {}  # qualified_name -> RegisteredPack
        self._prefixes: dict[str, str] = {}  # prefix -> qualified_name
        self._collisions: dict[
            str, list[str]
        ] = {}  # prefix -> list of qualified_names that claimed it
        self._discovered = False
        self._blocklist = self._parse_blocklist(blocklist)
        self._prefix_map = self._parse_prefix_map(prefix_map)
        self._default_prefix = self._parse_default_prefix(default_prefix)

    def _parse_blocklist(self, blocklist: set[str] | None) -> set[str]:
        """Parse blocklist from constructor and environment variable.

        Args:
            blocklist: Blocklist from constructor.

        Returns:
            Merged set of blocked pack names (can be short or qualified).
        """
        result = set(blocklist) if blocklist else set()

        # Merge with environment variable
        env_blocklist = os.environ.get("RESOURCE_DISCOVERY_BLOCKLIST", "")
        if env_blocklist:
            result.update(
                name.strip() for name in env_blocklist.split(",") if name.strip()
            )

        return result

    def _parse_prefix_map(self, prefix_map: dict[str, str] | None) -> dict[str, str]:
        """Parse prefix_map from constructor and environment variable.

        Args:
            prefix_map: Prefix map from constructor.

        Returns:
            Dictionary mapping alias -> qualified pack name.
        """
        result = dict(prefix_map) if prefix_map else {}

        # Merge with environment variable
        env_prefix_map = os.environ.get("RESOURCE_PREFIX_MAP", "")
        if env_prefix_map:
            for entry in env_prefix_map.split(","):
                entry = entry.strip()
                if "=" in entry:
                    alias, qualified_name = entry.split("=", 1)
                    result[alias.strip()] = qualified_name.strip()

        return result

    def _parse_default_prefix(self, default_prefix: str | None) -> str | None:
        """Parse default_prefix from constructor and environment variable.

        Args:
            default_prefix: Default prefix from constructor.

        Returns:
            Default prefix string, or None if not set.
        """
        # Constructor takes precedence over env var
        if default_prefix is not None:
            return default_prefix

        # Check environment variable
        env_default = os.environ.get("RESOURCE_DEFAULT_PREFIX", "")
        if env_default:
            return env_default.strip()

        return None

    def _get_entry_points(
        self,
    ) -> Iterator[tuple[str, str, ResourcePack, list[str]]]:
        """Get resource packs from EntryPoints.

        Yields:
            Tuples of (dist_name, pack_name, ResourcePack instance, aliases list).
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
                # Get distribution name (available Python 3.9+)
                dist_name = (
                    ep.dist.name if hasattr(ep, "dist") and ep.dist else "unknown"
                )
                pack_name = ep.name

                factory = ep.load()
                result = factory()

                # Handle various return types from entry point factory
                aliases: list[str] = []
                provider: ResourcePack | None = None

                if isinstance(result, tuple):
                    if len(result) == 2:
                        # Option 1: (provider, metadata)
                        provider, metadata = result
                        # Extract prefixes from metadata if it's a dict
                        if isinstance(metadata, dict) and "prefixes" in metadata:
                            aliases = (
                                metadata["prefixes"]
                                if isinstance(metadata["prefixes"], list)
                                else []
                            )
                    elif len(result) >= 3:
                        # Option 2: (descriptor_type, provider, prefixes)
                        _, provider, aliases = result[0], result[1], result[2]
                        if not isinstance(aliases, list):
                            aliases = []
                elif hasattr(result, "get_resource"):
                    # Option 3: Direct ResourcePack instance
                    provider = result
                    # Get prefixes from the pack if it has the method
                    if hasattr(provider, "get_prefixes"):
                        aliases = provider.get_prefixes()
                    else:
                        aliases = []
                else:
                    continue

                if provider is None:
                    continue

                # Verify it implements ResourcePack protocol
                if not (
                    hasattr(provider, "get_resource")
                    and hasattr(provider, "list_resources")
                ):
                    continue

                yield (dist_name, pack_name, provider, aliases)
            except Exception:
                # Skip invalid entry points
                continue

    def discover(self) -> None:
        """Discover resource packs from all registered EntryPoints.

        Resource packs are discovered lazily—this method only runs once per registry instance.
        Packs are processed in deterministic order (sorted by FQN) for stable behavior.

        Pack identity is derived from:
        - dist_name: Python distribution name (ep.dist.name)
        - pack_name: Entry point name (ep.name)

        The qualified name "dist_name/pack_name" is always registered as a prefix.
        The pack_name is also registered as a short prefix (with collision detection).
        Aliases from get_prefixes() are registered with the same collision rules.
        """
        if self._discovered:
            return

        # Collect all packs
        packs: list[tuple[str, str, ResourcePack, list[str]]] = []

        # Load External Packs via EntryPoints
        for dist_name, pack_name, pack, aliases in self._get_entry_points():
            qualified_name = f"{dist_name}/{pack_name}"

            # Check blocklist (accepts both short and qualified names)
            if pack_name in self._blocklist or qualified_name in self._blocklist:
                continue  # Skip blocked packs

            packs.append((dist_name, pack_name, pack, aliases))

        # Sort packs by qualified name for deterministic ordering
        packs.sort(key=lambda x: f"{x[0]}/{x[1]}")

        # Process packs
        for dist_name, pack_name, pack, aliases in packs:
            qualified_name = f"{dist_name}/{pack_name}"

            # Create RegisteredPack
            registered_pack = RegisteredPack(
                dist_name=dist_name,
                pack_name=pack_name,
                pack=pack,
                aliases=tuple(aliases),
            )

            # Register pack by qualified name
            self._packs[qualified_name] = registered_pack

            # Register qualified name as prefix (always unique, always available)
            self._prefixes[qualified_name.lower()] = qualified_name

            # Register pack_name as short prefix (with collision detection)
            self._register_prefix(
                pack_name.lower(),
                qualified_name,
                f"pack name '{pack_name}'",
            )

            # Register aliases from get_prefixes() (with collision detection)
            for alias in aliases:
                self._register_prefix(
                    alias.lower(),
                    qualified_name,
                    f"alias '{alias}'",
                )

        # Apply user prefix_map overrides (highest precedence)
        for alias, target_qualified in self._prefix_map.items():
            if target_qualified in self._packs:
                self._prefixes[alias.lower()] = target_qualified
            # Note: We don't warn if target doesn't exist - user might be pre-configuring

        self._discovered = True

    def _register_prefix(
        self, prefix: str, qualified_name: str, description: str
    ) -> None:
        """Register a prefix with collision detection and warning.

        All collisions are treated as ambiguous. No winner is picked.
        The prefix becomes ambiguous and cannot be used without explicit
        resolution via FQN or prefix_map.

        Args:
            prefix: The prefix to register (already lowercased).
            qualified_name: The qualified pack name claiming this prefix.
            description: Human-readable description for warning messages.
        """
        if prefix not in self._prefixes:
            # No collision, register it
            self._prefixes[prefix] = qualified_name
        else:
            # Collision detected - mark as ambiguous
            existing_qualified = self._prefixes[prefix]

            # Track both qualified names in collisions
            if prefix not in self._collisions:
                self._collisions[prefix] = [existing_qualified]
            if qualified_name not in self._collisions[prefix]:
                self._collisions[prefix].append(qualified_name)

            warnings.warn(
                f"Prefix '{prefix}' collision: {description} from '{qualified_name}' "
                f"conflicts with '{existing_qualified}'. The prefix is ambiguous. "
                f"Use qualified names ('{existing_qualified}:resource' or "
                f"'{qualified_name}:resource') or configure prefix_map to resolve.",
                PrefixCollisionWarning,
                stacklevel=3,
            )

    def _resolve_name(self, name: str) -> tuple[str, str]:
        """Resolve a resource name to (qualified_pack_name, resource_name).

        **Resolution Kernel Invariant**: This method is intentionally a **pure function**
        with no side effects. It must:
        - Perform **no I/O** (no filesystem, network, environment variable reads, or discovery)
        - Only read from in-memory registry state: `_packs`, `_prefixes`, `_collisions`, `_default_prefix`
        - Remain deterministic and testable in isolation

        This purity enables future extraction into a reusable kernel that can be shared
        between sync and async registry implementations without logic duplication.

        Supports multiple resolution forms:
        - "dist/pack:resource" - fully qualified (always unique)
        - "pack:resource" - short pack name (works if unique)
        - "alias:resource" - alias from get_prefixes() (works if unique)
        - "resource" - rewritten to "{default_prefix}:resource" if default_prefix is set

        Args:
            name: Resource name, optionally with prefix.

        Returns:
            Tuple of (qualified_pack_name, resource_name).

        Raises:
            ValueError: If prefix is specified but pack is not found, if collision
                prevents unambiguous resolution, or if bare name is used without default_prefix.
        """
        if ":" in name:
            # Split on last ":" to handle qualified names with colons in dist/pack
            parts = name.rsplit(":", 1)
            if len(parts) == 2:
                prefix_part, resource_name = parts
            else:
                # Shouldn't happen, but handle gracefully
                prefix_part = name
                resource_name = ""

            prefix_lower = prefix_part.lower()

            # Check if it's a fully qualified name (contains /)
            if "/" in prefix_part:
                # Fully qualified: dist/pack format
                if prefix_lower in self._packs:
                    return (prefix_lower, resource_name)
                else:
                    raise ValueError(
                        f"Unknown qualified resource pack: {prefix_part}. "
                        f"Available packs: {', '.join(sorted(self._packs.keys()))}"
                    )

            # Short prefix: look up in prefix map
            # Check prefix_map overrides first (highest precedence, resolves collisions)
            if prefix_lower in self._prefix_map:
                target_qualified = self._prefix_map[prefix_lower]
                if target_qualified in self._packs:
                    return (target_qualified, resource_name)

            # Check for collisions (ambiguous and unresolved by prefix_map)
            if prefix_lower in self._collisions:
                qualified_names = self._collisions[prefix_lower]
                msg = (
                    f"Prefix '{prefix_part}' is ambiguous (claimed by multiple packs). "
                    f"Use a qualified name: "
                )
                alternatives = [f"'{q}:{resource_name}'" for q in qualified_names]
                msg += ", ".join(alternatives) + "."
                raise ValueError(msg)

            # Check if prefix exists in _prefixes (unique prefix, no collision)
            if prefix_lower in self._prefixes:
                qualified_name = self._prefixes[prefix_lower]
                return (qualified_name, resource_name)

            # Prefix not found at all
            raise ValueError(
                f"Unknown resource pack prefix: {prefix_part}. "
                f"Available prefixes: {', '.join(sorted(self._prefixes.keys()))}"
            )
        else:
            # No prefix: rewrite using default_prefix
            if self._default_prefix is None:
                raise ValueError(
                    "No default prefix configured. Use a prefixed name "
                    "(e.g., 'pack:resource' or 'dist/pack:resource') or set "
                    "default_prefix on the registry (or RESOURCE_DEFAULT_PREFIX env var)."
                )

            # Rewrite bare name to use default_prefix
            rewritten = f"{self._default_prefix}:{name}"
            # Recursively resolve (will handle FQN, short name, alias, or error if ambiguous)
            return self._resolve_name(rewritten)

    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content by name.

        Execution flow: **discover (I/O) → resolve (pure kernel) → execute (pack I/O)**
        1. `discover()` - Loads packs from EntryPoints (I/O: filesystem, environment)
        2. `_resolve_name()` - Pure resolution logic (no I/O, reads only in-memory state)
        3. `pack.get_resource()` - Pack-specific I/O (filesystem, network, etc.)

        Supports multiple resolution forms:
        - "dist/pack:resource" - fully qualified (always unique)
        - "pack:resource" - short pack name (works if unique)
        - "alias:resource" - alias from get_prefixes() (works if unique)
        - "resource" - rewritten to "{default_prefix}:resource" if default_prefix is set

        Args:
            name: Resource name, optionally with prefix.

        Returns:
            ResourceContent object containing the resource data and metadata.

        Raises:
            ValueError: If the resource cannot be found, prefix is ambiguous, or
                bare name is used without default_prefix.
        """
        self.discover()

        qualified_name, resource_name = self._resolve_name(name)
        registered_pack = self._packs[qualified_name]

        return registered_pack.pack.get_resource(resource_name)

    def list_resources(self, pack: str | None = None) -> Iterator[ResourceInfo]:
        """List all discovered resources.

        Args:
            pack: Optional qualified pack name (dist/pack format) or short pack name to filter by.
                If None, lists resources from all packs.

        Yields:
            ResourceInfo objects for each discovered resource.
        """
        self.discover()

        if pack:
            # Resolve pack name (could be short or qualified)
            pack_lower = pack.lower()
            if pack_lower in self._packs:
                qualified_name = pack_lower
            elif pack_lower in self._prefixes:
                qualified_name = self._prefixes[pack_lower]
            else:
                return

            if qualified_name not in self._packs:
                return

            registered_pack = self._packs[qualified_name]
            # Get content type hint from pack if available (duck-typed, optional)
            content_type: str | None = getattr(
                registered_pack.pack, "default_content_type", None
            )
            for resource_name in registered_pack.pack.list_resources():
                yield ResourceInfo(
                    name=resource_name,
                    pack=qualified_name,
                    content_type=content_type,
                )
        else:
            # List from all packs
            for qualified_name, registered_pack in self._packs.items():
                # Get content type hint from pack if available (duck-typed, optional)
                content_type: str | None = getattr(
                    registered_pack.pack, "default_content_type", None
                )
                for resource_name in registered_pack.pack.list_resources():
                    yield ResourceInfo(
                        name=resource_name,
                        pack=qualified_name,
                        content_type=content_type,
                    )

    def list_packs(self) -> Iterator[str]:
        """List all registered resource pack qualified names.

        Yields:
            Qualified resource pack names in "dist/pack" format.
        """
        self.discover()
        yield from self._packs.keys()

    def get_prefix_map(self) -> dict[str, str]:
        """Get current prefix to qualified pack name mapping.

        Returns:
            Dictionary mapping prefix -> qualified pack name (dist/pack format).
            Includes qualified names, short pack names, and aliases.
        """
        self.discover()
        return dict(self._prefixes)

    def get_prefix_collisions(self) -> dict[str, list[str]]:
        """Get prefixes that are claimed by multiple packs.

        Returns:
            Dictionary mapping prefix -> list of qualified pack names that claimed it.
        """
        self.discover()
        return dict(self._collisions)


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
