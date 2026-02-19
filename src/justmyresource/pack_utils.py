"""Utility classes for resource pack implementations."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from typing import Any

from justmyresource.types import PackInfo, ResourceContent


class ZippedResourcePack:
    """Base class for resource packs that store resources in a zip archive.

    This class provides a generic implementation for packs that bundle resources
    in a single zip file within their package. It handles:
    - Lazy loading (zip only opened when resources accessed)
    - Efficient listing without loading resource content
    - Optional pack manifest support (pack_manifest.json)
    - Variant/subdirectory support (e.g., outlined/icon.svg)

    Subclasses typically only need to call __init__ and optionally override
    get_prefixes() and default_content_type.
    """

    def __init__(
        self,
        package_name: str,
        archive_name: str = "icons.zip",
        manifest_name: str = "pack_manifest.json",
        default_content_type: str | None = None,
        prefixes: list[str] | None = None,
        pack_info: PackInfo | None = None,
    ) -> None:
        """Initialize zipped resource pack.

        Args:
            package_name: Python package name containing the zip (e.g., "justmyresource_lucide").
            archive_name: Name of zip file within package (e.g., "icons.zip").
            manifest_name: Name of manifest JSON file (e.g., "pack_manifest.json").
            default_content_type: MIME type for resources (e.g., "image/svg+xml").
                If None, reads from manifest contents.format, falling back to
                "application/octet-stream" if not found.
            prefixes: Optional list of prefix aliases. If None, reads from manifest.
            pack_info: Optional PackInfo metadata describing this pack. If None, reads from manifest.
        """
        self._package_name = package_name
        self._archive_name = archive_name
        self._manifest_name = manifest_name
        self._manifest: dict[str, Any] | None = None
        self._resource_list: list[str] | None = None

        # Load manifest to auto-populate if needed
        manifest = self.get_manifest()
        pack_data = manifest.get("pack", {})

        # Auto-populate content type from manifest if not provided
        if default_content_type is None:
            self.default_content_type = (
                manifest.get("contents", {}).get("format", "application/octet-stream")
            )
        else:
            self.default_content_type = default_content_type

        # Auto-populate prefixes from manifest if not provided
        if prefixes is None:
            self._prefixes = pack_data.get("prefixes", [])
        else:
            self._prefixes = prefixes

        # Auto-populate PackInfo from manifest if not provided
        if pack_info is None:
            self._pack_info = PackInfo(
                description=pack_data.get("description", "Resource pack"),
                source_url=pack_data.get("source_url"),
                license_spdx=pack_data.get("upstream_license"),
            )
        else:
            self._pack_info = pack_info

    @contextmanager
    def _open_zip(self):
        """Context manager for opening the zip file.

        Yields:
            ZipFile instance for reading resources.
        """
        package = files(self._package_name)
        zip_path = package / self._archive_name

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            yield zip_file

    def get_manifest(self) -> dict[str, Any]:
        """Get pack manifest metadata.

        Returns:
            Parsed pack manifest (from pack_manifest.json).
        """
        if self._manifest is None:
            try:
                package = files(self._package_name)
                manifest_path = package / self._manifest_name
                with open(manifest_path, encoding="utf-8") as f:
                    self._manifest = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                self._manifest = {}

        return self._manifest

    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content for a name.

        Args:
            name: Resource name (e.g., "icon.svg" or "outlined/icon.svg").

        Returns:
            ResourceContent object with resource data and metadata.

        Raises:
            ValueError: If resource not found in zip.
        """
        # Ensure .svg extension if not present (for icon packs)
        # Subclasses can override this behavior
        resource_name = self._normalize_name(name)

        try:
            with self._open_zip() as zip_file:
                resource_bytes = zip_file.read(resource_name)
        except KeyError:
            # Provide helpful error with suggestions
            available = self._get_resource_list()
            suggestions = [
                n
                for n in available
                if name.lower() in n.lower() or n.lower() in name.lower()
            ][:5]
            suggestion_text = (
                f" Similar names: {', '.join(suggestions)}" if suggestions else ""
            )
            raise ValueError(
                f"Resource '{name}' not found in pack.{suggestion_text}"
            ) from None

        # Determine encoding based on content type
        encoding = (
            "utf-8"
            if self.default_content_type.startswith("text/")
            or self.default_content_type == "image/svg+xml"
            else None
        )

        # Build metadata
        manifest = self.get_manifest()
        metadata = {
            "pack_version": manifest.get("pack", {}).get("version"),
        }

        return ResourceContent(
            data=resource_bytes,
            content_type=self.default_content_type,
            encoding=encoding,
            metadata=metadata,
        )

    def _normalize_name(self, name: str) -> str:
        """Normalize resource name for lookup in zip.

        Default implementation returns name as-is. Subclasses can override
        to add extensions or perform other transformations.

        Args:
            name: Resource name from user.

        Returns:
            Normalized name for zip lookup.
        """
        return name

    def _get_resource_list(self) -> list[str]:
        """Get cached list of all resource names in zip.

        Returns:
            Sorted list of resource names.
        """
        if self._resource_list is None:
            with self._open_zip() as zip_file:
                # Get all files (not directories)
                self._resource_list = sorted(
                    name for name in zip_file.namelist() if not name.endswith("/")
                )
        return self._resource_list

    def list_resources(self) -> Iterator[str]:
        """List all available resource names.

        Yields:
            Resource name strings (as stored in zip).
        """
        yield from self._get_resource_list()

    def get_prefixes(self) -> list[str]:
        """Return list of optional alias prefixes.

        Returns:
            List of prefix aliases.
        """
        return self._prefixes

    def get_pack_info(self) -> PackInfo:
        """Return metadata describing this resource pack.

        Returns:
            PackInfo object containing description, source URL, and license information.
        """
        return self._pack_info
