"""Tests for ZippedResourcePack helper class."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, mock_open, patch

import pytest

from justmyresource.pack_utils import ZippedResourcePack
from justmyresource.types import PackInfo


@pytest.fixture
def mock_zip_with_icons():
    """Create a mock zip file with test icons."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("icon1.svg", b"<svg>icon1</svg>")
        zf.writestr("icon2.svg", b"<svg>icon2</svg>")
        zf.writestr("outlined/icon3.svg", b"<svg>icon3</svg>")
    zip_buffer.seek(0)
    return zip_buffer


@pytest.fixture
def mock_manifest():
    """Create a mock pack manifest."""
    return {
        "pack": {
            "name": "test-pack",
            "version": "1.0.0",
        }
    }


def test_zipped_pack_init():
    """Test basic initialization."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch("builtins.open", side_effect=FileNotFoundError):
            pack = ZippedResourcePack(
                package_name="test_package",
                archive_name="test.zip",
                default_content_type="image/svg+xml",
                prefixes=["test"],
            )

            assert pack.default_content_type == "image/svg+xml"
            assert pack.get_prefixes() == ["test"]


def test_zipped_pack_get_resource():
    """Test getting a resource from zip."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        # Create a real zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("icon1.svg", b"<svg>icon1</svg>")
        zip_buffer.seek(0)

        # Mock the package filesystem
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_zip_path = MagicMock()
        mock_package.__truediv__.return_value = mock_zip_path

        # Patch ZipFile to use our in-memory zip
        with patch("zipfile.ZipFile") as mock_zipfile_class:
            mock_zipfile_class.return_value.__enter__.return_value.read.return_value = (
                b"<svg>icon1</svg>"
            )
            mock_zipfile_class.return_value.__enter__.return_value.namelist.return_value = [
                "icon1.svg"
            ]

            pack = ZippedResourcePack(
                package_name="test_package", default_content_type="image/svg+xml"
            )

            content = pack.get_resource("icon1.svg")

            assert content.data == b"<svg>icon1</svg>"
            assert content.content_type == "image/svg+xml"
            assert content.encoding == "utf-8"


def test_zipped_pack_list_resources():
    """Test listing resources."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package

        pack = ZippedResourcePack(package_name="test_package")

        with patch("zipfile.ZipFile") as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                "icon1.svg",
                "icon2.svg",
                "outlined/icon3.svg",
            ]

            resources = list(pack.list_resources())

            assert "icon1.svg" in resources
            assert "icon2.svg" in resources
            assert "outlined/icon3.svg" in resources


def test_zipped_pack_resource_not_found():
    """Test error handling for missing resource."""
    with patch("justmyresource.pack_utils.files"):
        pack = ZippedResourcePack(package_name="test_package")

        with patch("zipfile.ZipFile") as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.read.side_effect = (
                KeyError("not found")
            )
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                "icon1.svg"
            ]

            with pytest.raises(ValueError, match="not found in pack"):
                pack.get_resource("missing.svg")


def test_zipped_pack_manifest(mock_manifest):
    """Test manifest loading."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package

        # Mock manifest file
        manifest_json = json.dumps(mock_manifest)
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch("builtins.open", mock_open(read_data=manifest_json)):
            pack = ZippedResourcePack(package_name="test_package")
            manifest = pack.get_manifest()

            assert manifest["pack"]["name"] == "test-pack"
            assert manifest["pack"]["version"] == "1.0.0"


def test_zipped_pack_manifest_missing():
    """Test manifest handling when file is missing."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch("builtins.open", side_effect=FileNotFoundError):
            pack = ZippedResourcePack(package_name="test_package")
            manifest = pack.get_manifest()

            assert manifest == {}


def test_zipped_pack_normalize_name():
    """Test name normalization (default implementation)."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch("builtins.open", side_effect=FileNotFoundError):
            pack = ZippedResourcePack(package_name="test_package")
            assert pack._normalize_name("icon") == "icon"
            assert pack._normalize_name("icon.svg") == "icon.svg"


def test_zipped_pack_resource_list_caching():
    """Test that resource list is cached."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package

        pack = ZippedResourcePack(package_name="test_package")

        with patch("zipfile.ZipFile") as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                "icon1.svg",
                "icon2.svg",
            ]

            # First call should open zip
            list1 = list(pack.list_resources())
            # Second call should use cache (namelist should not be called again)
            list2 = list(pack.list_resources())

            assert list1 == list2
            # Verify namelist was only called once (cached)
            assert (
                mock_zipfile.return_value.__enter__.return_value.namelist.call_count
                == 1
            )


def test_zipped_pack_encoding_detection():
    """Test encoding detection based on content type."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        # Mock manifest path to raise FileNotFoundError (manifest is optional)
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        # Mock manifest file not found - must be patched before pack creation
        with patch("builtins.open", side_effect=FileNotFoundError):
            # SVG should have utf-8 encoding
            pack_svg = ZippedResourcePack(
                package_name="test_package", default_content_type="image/svg+xml"
            )

            with patch("zipfile.ZipFile") as mock_zipfile:
                mock_zipfile.return_value.__enter__.return_value.read.return_value = (
                    b"<svg></svg>"
                )
                mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                    "icon.svg"
                ]
                content = pack_svg.get_resource("icon.svg")
                assert content.encoding == "utf-8"

            # PNG should have no encoding
            pack_png = ZippedResourcePack(
                package_name="test_package", default_content_type="image/png"
            )

            with patch("zipfile.ZipFile") as mock_zipfile:
                mock_zipfile.return_value.__enter__.return_value.read.return_value = (
                    b"\x89PNG"
                )
                mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                    "icon.png"
                ]
                content = pack_png.get_resource("icon.png")
                assert content.encoding is None


def test_zipped_pack_explicit_pack_info():
    """Test ZippedResourcePack with explicit pack_info parameter."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        explicit_pack_info = PackInfo(
            description="Explicit pack info",
            source_url="https://example.com/explicit",
            license_spdx="MIT",
        )

        with patch("builtins.open", side_effect=FileNotFoundError):
            pack = ZippedResourcePack(
                package_name="test_package",
                pack_info=explicit_pack_info,
            )

            # Should use explicit pack_info, not manifest
            assert pack.get_pack_info() == explicit_pack_info
            assert pack.get_pack_info().description == "Explicit pack info"
            assert pack.get_pack_info().source_url == "https://example.com/explicit"
            assert pack.get_pack_info().license_spdx == "MIT"


def test_zipped_pack_get_pack_info():
    """Test get_pack_info() return value."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch("builtins.open", side_effect=FileNotFoundError):
            pack = ZippedResourcePack(
                package_name="test_package",
                pack_info=PackInfo(description="Test pack"),
            )

            pack_info = pack.get_pack_info()
            assert isinstance(pack_info, PackInfo)
            assert pack_info.description == "Test pack"


def test_zipped_pack_prefixes_from_manifest():
    """Test ZippedResourcePack reading prefixes from manifest."""
    manifest_with_prefixes = {
        "pack": {
            "name": "test-pack",
            "version": "1.0.0",
            "prefixes": ["test", "t"],
        }
    }

    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        manifest_json = json.dumps(manifest_with_prefixes)
        with patch("builtins.open", mock_open(read_data=manifest_json)):
            # Don't provide prefixes explicitly - should read from manifest
            pack = ZippedResourcePack(package_name="test_package")

            assert pack.get_prefixes() == ["test", "t"]


def test_zipped_pack_explicit_prefixes_override_manifest():
    """Test that explicit prefixes override manifest prefixes."""
    manifest_with_prefixes = {
        "pack": {
            "name": "test-pack",
            "version": "1.0.0",
            "prefixes": ["manifest-prefix"],
        }
    }

    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        manifest_json = json.dumps(manifest_with_prefixes)
        with patch("builtins.open", mock_open(read_data=manifest_json)):
            # Provide explicit prefixes - should override manifest
            pack = ZippedResourcePack(
                package_name="test_package",
                prefixes=["explicit-prefix"],
            )

            assert pack.get_prefixes() == ["explicit-prefix"]


def test_zipped_pack_pack_info_from_manifest():
    """Test ZippedResourcePack reading PackInfo from manifest."""
    manifest_with_info = {
        "pack": {
            "name": "test-pack",
            "version": "1.0.0",
            "description": "Pack from manifest",
            "source_url": "https://example.com/manifest",
            "upstream_license": "ISC",
        }
    }

    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        manifest_json = json.dumps(manifest_with_info)
        with patch("builtins.open", mock_open(read_data=manifest_json)):
            # Don't provide pack_info explicitly - should read from manifest
            pack = ZippedResourcePack(package_name="test_package")

            pack_info = pack.get_pack_info()
            assert pack_info.description == "Pack from manifest"
            assert pack_info.source_url == "https://example.com/manifest"
            assert pack_info.license_spdx == "ISC"


def test_zipped_pack_default_pack_info():
    """Test ZippedResourcePack default PackInfo when manifest is missing."""
    with patch("justmyresource.pack_utils.files") as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch("builtins.open", side_effect=FileNotFoundError):
            # No pack_info and no manifest - should use defaults
            pack = ZippedResourcePack(package_name="test_package")

            pack_info = pack.get_pack_info()
            assert pack_info.description == "Resource pack"
            assert pack_info.source_url is None
            assert pack_info.license_spdx is None
