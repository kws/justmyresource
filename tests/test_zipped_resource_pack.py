"""Tests for ZippedResourcePack helper class."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, mock_open, patch

import pytest

from justmyresource.pack_utils import ZippedResourcePack


@pytest.fixture
def mock_zip_with_icons():
    """Create a mock zip file with test icons."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
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
    pack = ZippedResourcePack(
        package_name="test_package",
        archive_name="test.zip",
        default_content_type="image/svg+xml",
        prefixes=["test"]
    )

    assert pack.default_content_type == "image/svg+xml"
    assert pack.get_prefixes() == ["test"]


def test_zipped_pack_get_resource():
    """Test getting a resource from zip."""
    with patch('justmyresource.pack_utils.files') as mock_files:
        # Create a real zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("icon1.svg", b"<svg>icon1</svg>")
        zip_buffer.seek(0)

        # Mock the package filesystem
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_zip_path = MagicMock()
        mock_package.__truediv__.return_value = mock_zip_path

        # Patch ZipFile to use our in-memory zip
        with patch('zipfile.ZipFile') as mock_zipfile_class:
            mock_zipfile_class.return_value.__enter__.return_value.read.return_value = b"<svg>icon1</svg>"
            mock_zipfile_class.return_value.__enter__.return_value.namelist.return_value = ["icon1.svg"]

            pack = ZippedResourcePack(
                package_name="test_package",
                default_content_type="image/svg+xml"
            )

            content = pack.get_resource("icon1.svg")

            assert content.data == b"<svg>icon1</svg>"
            assert content.content_type == "image/svg+xml"
            assert content.encoding == "utf-8"


def test_zipped_pack_list_resources():
    """Test listing resources."""
    with patch('justmyresource.pack_utils.files') as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package

        pack = ZippedResourcePack(package_name="test_package")

        with patch('zipfile.ZipFile') as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                "icon1.svg",
                "icon2.svg",
                "outlined/icon3.svg"
            ]

            resources = list(pack.list_resources())

            assert "icon1.svg" in resources
            assert "icon2.svg" in resources
            assert "outlined/icon3.svg" in resources


def test_zipped_pack_resource_not_found():
    """Test error handling for missing resource."""
    with patch('justmyresource.pack_utils.files'):
        pack = ZippedResourcePack(package_name="test_package")

        with patch('zipfile.ZipFile') as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.read.side_effect = KeyError("not found")
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = ["icon1.svg"]

            with pytest.raises(ValueError, match="not found in pack"):
                pack.get_resource("missing.svg")


def test_zipped_pack_manifest(mock_manifest):
    """Test manifest loading."""
    with patch('justmyresource.pack_utils.files') as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package

        # Mock manifest file
        manifest_json = json.dumps(mock_manifest)
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch('builtins.open', mock_open(read_data=manifest_json)):
            pack = ZippedResourcePack(package_name="test_package")
            manifest = pack.get_manifest()

            assert manifest["pack"]["name"] == "test-pack"
            assert manifest["pack"]["version"] == "1.0.0"


def test_zipped_pack_manifest_missing():
    """Test manifest handling when file is missing."""
    with patch('justmyresource.pack_utils.files') as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        with patch('builtins.open', side_effect=FileNotFoundError):
            pack = ZippedResourcePack(package_name="test_package")
            manifest = pack.get_manifest()

            assert manifest == {}


def test_zipped_pack_normalize_name():
    """Test name normalization (default implementation)."""
    pack = ZippedResourcePack(package_name="test_package")
    assert pack._normalize_name("icon") == "icon"
    assert pack._normalize_name("icon.svg") == "icon.svg"


def test_zipped_pack_resource_list_caching():
    """Test that resource list is cached."""
    with patch('justmyresource.pack_utils.files') as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package

        pack = ZippedResourcePack(package_name="test_package")

        with patch('zipfile.ZipFile') as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = [
                "icon1.svg",
                "icon2.svg"
            ]

            # First call should open zip
            list1 = list(pack.list_resources())
            # Second call should use cache (namelist should not be called again)
            list2 = list(pack.list_resources())

            assert list1 == list2
            # Verify namelist was only called once (cached)
            assert mock_zipfile.return_value.__enter__.return_value.namelist.call_count == 1


def test_zipped_pack_encoding_detection():
    """Test encoding detection based on content type."""
    with patch('justmyresource.pack_utils.files') as mock_files:
        mock_package = MagicMock()
        mock_files.return_value = mock_package
        # Mock manifest path to raise FileNotFoundError (manifest is optional)
        mock_manifest_path = MagicMock()
        mock_package.__truediv__.return_value = mock_manifest_path

        # SVG should have utf-8 encoding
        pack_svg = ZippedResourcePack(
            package_name="test_package",
            default_content_type="image/svg+xml"
        )

        with patch('zipfile.ZipFile') as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.read.return_value = b"<svg></svg>"
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = ["icon.svg"]
            # Mock manifest file not found
            with patch('builtins.open', side_effect=FileNotFoundError):
                content = pack_svg.get_resource("icon.svg")
                assert content.encoding == "utf-8"

        # PNG should have no encoding
        pack_png = ZippedResourcePack(
            package_name="test_package",
            default_content_type="image/png"
        )

        with patch('zipfile.ZipFile') as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.read.return_value = b"\x89PNG"
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = ["icon.png"]
            # Mock manifest file not found
            with patch('builtins.open', side_effect=FileNotFoundError):
                content = pack_png.get_resource("icon.png")
                assert content.encoding is None

