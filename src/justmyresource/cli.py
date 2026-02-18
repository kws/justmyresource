"""Command-line interface for JustMyResource."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from justmyresource.core import ResourceRegistry
from justmyresource.types import PackInfo

if TYPE_CHECKING:
    from justmyresource.types import ResourceContent, ResourceInfo


def _get_registry(
    blocklist: set[str] | None = None,
    prefix_map: dict[str, str] | None = None,
    default_prefix: str | None = None,
) -> ResourceRegistry:
    """Create a resource registry instance.

    Args:
        blocklist: Optional set of resource pack names to block.
        prefix_map: Optional mapping of alias -> qualified pack name.
        default_prefix: Optional default prefix for bare-name lookups.

    Returns:
        ResourceRegistry instance.
    """
    return ResourceRegistry(
        blocklist=blocklist,
        prefix_map=prefix_map,
        default_prefix=default_prefix,
    )


def _format_size(size_bytes: int) -> str:
    """Format byte size as human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted size string (e.g., "1.2 KB").
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}" if size_bytes >= 1.0 else f"{int(size_bytes)} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def cmd_list(args: argparse.Namespace) -> int:
    """List all available resources.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    registry = _get_registry(
        blocklist=args.blocklist,
        prefix_map=args.prefix_map,
        default_prefix=args.default_prefix,
    )
    registry.discover()

    resources = list(registry.list_resources(pack=args.pack))

    # Apply glob filter if provided
    if args.filter:
        resources = [
            r for r in resources if fnmatch.fnmatch(r.name, args.filter)
        ]

    # Sort by pack, then by name
    resources.sort(key=lambda r: (r.pack, r.name))

    if args.json:
        output = {
            "resources": [
                {
                    "name": r.name,
                    "pack": r.pack,
                    "content_type": r.content_type,
                }
                for r in resources
            ],
            "count": len(resources),
        }
        print(json.dumps(output, indent=2))
    else:
        for resource in resources:
            if args.verbose:
                pack_info = f" ({resource.pack})"
                type_info = f" [{resource.content_type}]" if resource.content_type else ""
                print(f"{resource.name}{pack_info}{type_info}")
            else:
                print(resource.name)

    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """Get a resource (metadata-first, with optional output).

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 if found, 2 if not found, 1 on error).
    """
    registry = _get_registry(
        blocklist=args.blocklist,
        prefix_map=args.prefix_map,
        default_prefix=args.default_prefix,
    )
    registry.discover()

    try:
        resource = registry.get_resource(args.name)
    except ValueError as e:
        if args.json:
            print(json.dumps({"found": False, "error": str(e)}, indent=2))
        else:
            print(f"Resource not found: {args.name}", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
        return 2

    # If output is specified, write resource data
    if args.output:
        if args.output == "-":
            # Output to stdout
            if resource.encoding:
                # Text-based resource
                sys.stdout.write(resource.text)
            else:
                # Binary resource
                sys.stdout.buffer.write(resource.data)
            return 0
        else:
            # Output to file
            output_path = Path(args.output)
            if resource.encoding:
                # Text-based resource
                output_path.write_text(resource.text, encoding=resource.encoding)
            else:
                # Binary resource
                output_path.write_bytes(resource.data)
            if not args.json:
                print(f"Saved to: {output_path}", file=sys.stderr)
            return 0

    # Default: show metadata only
    size = len(resource.data)
    size_str = _format_size(size)

    # Resolve pack name
    pack_name = "unknown"
    registered_pack = None
    resource_path = None
    try:
        qualified_name, resource_name = registry._resolve_name(args.name)
        pack_name = qualified_name
        registered_pack = registry._packs[qualified_name]
        # Check for path support (duck-typed)
        if hasattr(registered_pack.pack, "get_resource_path"):
            path = registered_pack.pack.get_resource_path(resource_name)
            if path:
                resource_path = str(path)
    except Exception:
        pass

    if args.json:
        output = {
            "found": True,
            "name": args.name,
            "pack": pack_name,
            "content_type": resource.content_type,
            "encoding": resource.encoding,
            "size": size,
            "size_human": size_str,
            "metadata": resource.metadata,
        }
        if resource_path:
            output["path"] = resource_path
        print(json.dumps(output, indent=2))
    else:
        print(f"Resource: {args.name}")
        print(f"Pack: {pack_name}")
        print(f"Content-Type: {resource.content_type}")
        if resource.encoding:
            print(f"Encoding: {resource.encoding}")
        print(f"Size: {size_str}")
        if resource_path:
            print(f"Path: {resource_path}")

        # Show additional metadata if available
        if resource.metadata:
            for key, value in resource.metadata.items():
                if key not in ("pack",):  # Skip already shown fields
                    print(f"{key.capitalize()}: {value}")

    return 0


def cmd_packs(args: argparse.Namespace) -> int:
    """List registered resource packs.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    registry = _get_registry(
        blocklist=args.blocklist,
        prefix_map=args.prefix_map,
        default_prefix=args.default_prefix,
    )
    registry.discover()

    packs: list[dict[str, str | list[str]]] = []
    prefix_map = registry.get_prefix_map()
    collisions = registry.get_prefix_collisions()

    for qualified_name in sorted(registry.list_packs()):
        registered_pack = registry._packs[qualified_name]
        pack_info: dict[str, str | list[str] | None] = {
            "qualified_name": qualified_name,
            "dist_name": registered_pack.dist_name,
            "pack_name": registered_pack.pack_name,
            "aliases": list(registered_pack.aliases),
        }

        # Get PackInfo metadata if available
        pack_metadata: PackInfo | None = None
        if hasattr(registered_pack.pack, "get_pack_info"):
            pack_metadata = registered_pack.pack.get_pack_info()

        if pack_metadata:
            pack_info["description"] = pack_metadata.description
            pack_info["source_url"] = pack_metadata.source_url
            pack_info["license_spdx"] = pack_metadata.license_spdx

        if args.verbose:
            # Find all prefixes that map to this pack
            prefixes = [
                prefix
                for prefix, qname in prefix_map.items()
                if qname == qualified_name
            ]
            pack_info["prefixes"] = sorted(prefixes)

            # Check for collisions
            colliding_prefixes = [
                prefix
                for prefix, qnames in collisions.items()
                if qualified_name in qnames
            ]
            if colliding_prefixes:
                pack_info["colliding_prefixes"] = sorted(colliding_prefixes)

        packs.append(pack_info)

    if args.json:
        output = {"packs": packs, "count": len(packs)}
        print(json.dumps(output, indent=2))
    else:
        if args.verbose:
            print(f"Registered resource packs ({len(packs)}):")
            for pack in packs:
                print(f"  {pack['qualified_name']}")
                print(f"    Distribution: {pack['dist_name']}")
                print(f"    Pack: {pack['pack_name']}")
                if pack.get("description"):
                    print(f"    Description: {pack['description']}")
                if pack.get("source_url"):
                    print(f"    Source: {pack['source_url']}")
                if pack.get("license_spdx"):
                    print(f"    License: {pack['license_spdx']}")
                if pack["aliases"]:
                    print(f"    Aliases: {', '.join(pack['aliases'])}")
                if "prefixes" in pack:
                    print(f"    Prefixes: {', '.join(pack['prefixes'])}")
                if "colliding_prefixes" in pack:
                    print(
                        f"    Colliding prefixes: {', '.join(pack['colliding_prefixes'])}"
                    )
        else:
            for pack in packs:
                print(pack["qualified_name"])
                # Show description, source, and license if available
                if pack.get("description") or pack.get("source_url") or pack.get("license_spdx"):
                    description = pack.get("description", "")
                    source_url = pack.get("source_url", "")
                    license_spdx = pack.get("license_spdx", "")
                    parts = []
                    if description:
                        parts.append(description)
                    if source_url and license_spdx:
                        parts.append(f"{source_url} | {license_spdx}")
                    elif source_url:
                        parts.append(source_url)
                    elif license_spdx:
                        parts.append(license_spdx)
                    if parts:
                        print(f"  {' | '.join(parts)}")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show detailed information about a resource.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 if found, 2 if not found, 1 on error).
    """
    registry = _get_registry(
        blocklist=args.blocklist,
        prefix_map=args.prefix_map,
        default_prefix=args.default_prefix,
    )
    registry.discover()

    try:
        resource = registry.get_resource(args.name)
    except ValueError as e:
        if args.json:
            print(json.dumps({"found": False, "error": str(e)}, indent=2))
        else:
            print(f"Resource not found: {args.name}", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
        return 2

    size = len(resource.data)
    size_str = _format_size(size)

    # Get pack information
    pack_name = "unknown"
    try:
        qualified_name, _ = registry._resolve_name(args.name)
        pack_name = qualified_name
        registered_pack = registry._packs[qualified_name]
    except Exception:
        registered_pack = None

    if args.json:
        output = {
            "found": True,
            "name": args.name,
            "pack": {
                "qualified_name": pack_name,
                "dist_name": registered_pack.dist_name if registered_pack else None,
                "pack_name": registered_pack.pack_name if registered_pack else None,
                "aliases": list(registered_pack.aliases) if registered_pack else [],
            },
            "content": {
                "content_type": resource.content_type,
                "encoding": resource.encoding,
                "size": size,
                "size_human": size_str,
            },
            "metadata": resource.metadata,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Resource: {args.name}")
        print(f"Pack: {pack_name}")
        if registered_pack:
            print(f"  Distribution: {registered_pack.dist_name}")
            print(f"  Pack Name: {registered_pack.pack_name}")
            if registered_pack.aliases:
                print(f"  Aliases: {', '.join(registered_pack.aliases)}")

        print(f"\nContent:")
        print(f"  Content-Type: {resource.content_type}")
        if resource.encoding:
            print(f"  Encoding: {resource.encoding}")
        print(f"  Size: {size_str} ({size} bytes)")

        # Check for path support (duck-typed)
        try:
            if registered_pack and hasattr(registered_pack.pack, "get_resource_path"):
                qualified_name, resource_name = registry._resolve_name(args.name)
                path = registered_pack.pack.get_resource_path(resource_name)
                if path:
                    print(f"  Path: {path}")
        except Exception:
            pass

        # Show all metadata
        if resource.metadata:
            print(f"\nMetadata:")
            for key, value in resource.metadata.items():
                if isinstance(value, dict):
                    print(f"  {key.capitalize()}:")
                    for subkey, subvalue in value.items():
                        print(f"    {subkey}: {subvalue}")
                elif isinstance(value, list):
                    print(f"  {key.capitalize()}: {', '.join(str(v) for v in value)}")
                else:
                    print(f"  {key.capitalize()}: {value}")

    return 0


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = argparse.ArgumentParser(
        prog="justmyresource",
        description="JustMyResource - Resource discovery and resolution",
    )
    parser.add_argument(
        "--blocklist",
        type=str,
        help="Comma-separated list of resource pack names to block",
    )
    parser.add_argument(
        "--prefix-map",
        type=str,
        help='Prefix mapping overrides (format: "alias1=dist1/pack1,alias2=dist2/pack2")',
    )
    parser.add_argument(
        "--default-prefix",
        type=str,
        help="Default prefix for bare-name lookups",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List all available resources")
    list_parser.add_argument(
        "--pack",
        type=str,
        help="Filter by pack (qualified name or short name)",
    )
    list_parser.add_argument(
        "--filter",
        type=str,
        help="Glob pattern to filter resource names (e.g., 'arrow-*')",
    )
    list_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show pack and content type information",
    )

    # get command
    get_parser = subparsers.add_parser("get", help="Get a resource (metadata-first)")
    get_parser.add_argument("name", help="Resource name (optionally prefixed)")
    get_parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output destination: '-' for stdout, or file path to save",
    )

    # packs command
    packs_parser = subparsers.add_parser("packs", help="List registered resource packs")
    packs_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed pack information",
    )

    # info command
    info_parser = subparsers.add_parser("info", help="Show detailed resource information")
    info_parser.add_argument("name", help="Resource name (optionally prefixed)")

    try:
        args = parser.parse_args()
    except SystemExit:
        # argparse raises SystemExit(2) for invalid commands/arguments
        # Return 1 for invalid commands to match expected behavior
        return 1

    # Parse blocklist
    blocklist: set[str] | None = None
    if args.blocklist:
        blocklist = {
            name.strip() for name in args.blocklist.split(",") if name.strip()
        }

    # Parse prefix_map
    prefix_map: dict[str, str] | None = None
    if args.prefix_map:
        prefix_map = {}
        for entry in args.prefix_map.split(","):
            entry = entry.strip()
            if "=" in entry:
                alias, qualified_name = entry.split("=", 1)
                prefix_map[alias.strip()] = qualified_name.strip()

    # Override args with parsed values
    args.blocklist = blocklist
    args.prefix_map = prefix_map

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "list":
            return cmd_list(args)
        elif args.command == "get":
            return cmd_get(args)
        elif args.command == "packs":
            return cmd_packs(args)
        elif args.command == "info":
            return cmd_info(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

