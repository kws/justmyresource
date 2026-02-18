"""Tests for core type definitions."""

from __future__ import annotations

import pytest

from justmyresource.types import PackInfo, RegisteredPack, ResourceContent, ResourceInfo
from tests.conftest import MockResourcePack, create_test_resource_content


def test_resource_content_text_with_encoding():
    """Test ResourceContent.text property successfully decodes when encoding is set."""
    content = ResourceContent(
        data=b"Hello, world!",
        content_type="text/plain",
        encoding="utf-8",
    )
    assert content.text == "Hello, world!"


def test_resource_content_text_with_utf8_svg():
    """Test ResourceContent.text property with UTF-8 SVG."""
    svg_data = b'<svg><text>\xe2\x9c\x93</text></svg>'  # Checkmark character
    content = ResourceContent(
        data=svg_data,
        content_type="image/svg+xml",
        encoding="utf-8",
    )
    assert content.text == '<svg><text>✓</text></svg>'


def test_resource_content_text_no_encoding():
    """Test ResourceContent.text property raises ValueError when encoding is None."""
    content = ResourceContent(
        data=b"\x89PNG",
        content_type="image/png",
        encoding=None,
    )
    with pytest.raises(ValueError, match="Cannot decode binary resource as text"):
        _ = content.text


def test_resource_content_text_invalid_encoding():
    """Test ResourceContent.text property raises UnicodeDecodeError for invalid encoding."""
    content = ResourceContent(
        data=b"\xff\xfe",  # Invalid UTF-8 sequence
        content_type="text/plain",
        encoding="utf-8",
    )
    with pytest.raises(UnicodeDecodeError):
        _ = content.text


def test_registered_pack_qualified_name():
    """Test RegisteredPack.qualified_name property."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    registered = RegisteredPack(
        dist_name="acme-icons",
        pack_name="lucide",
        pack=pack,
        aliases=("luc",),
    )

    assert registered.qualified_name == "acme-icons/lucide"


def test_registered_pack_qualified_name_different_dist():
    """Test RegisteredPack.qualified_name with different distribution."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="cool-icons",
        pack_name="feather",
    )

    registered = RegisteredPack(
        dist_name="cool-icons",
        pack_name="feather",
        pack=pack,
        aliases=(),
    )

    assert registered.qualified_name == "cool-icons/feather"


def test_resource_info_with_tags():
    """Test ResourceInfo with tags field."""
    info = ResourceInfo(
        name="icon1",
        pack="acme-icons/lucide",
        content_type="image/svg+xml",
        tags=("icon", "arrow", "navigation"),
    )

    assert info.name == "icon1"
    assert info.pack == "acme-icons/lucide"
    assert info.content_type == "image/svg+xml"
    assert info.tags == ("icon", "arrow", "navigation")


def test_resource_info_without_tags():
    """Test ResourceInfo without tags (default None)."""
    info = ResourceInfo(
        name="icon1",
        pack="acme-icons/lucide",
        content_type="image/svg+xml",
    )

    assert info.name == "icon1"
    assert info.pack == "acme-icons/lucide"
    assert info.content_type == "image/svg+xml"
    assert info.tags is None


def test_resource_info_without_content_type():
    """Test ResourceInfo without content_type (default None)."""
    info = ResourceInfo(
        name="icon1",
        pack="acme-icons/lucide",
    )

    assert info.name == "icon1"
    assert info.pack == "acme-icons/lucide"
    assert info.content_type is None
    assert info.tags is None


def test_pack_info_basic():
    """Test PackInfo with all fields."""
    pack_info = PackInfo(
        description="Test icon pack",
        source_url="https://example.com",
        license_spdx="MIT",
    )

    assert pack_info.description == "Test icon pack"
    assert pack_info.source_url == "https://example.com"
    assert pack_info.license_spdx == "MIT"


def test_pack_info_minimal():
    """Test PackInfo with only required description."""
    pack_info = PackInfo(description="Minimal pack info")

    assert pack_info.description == "Minimal pack info"
    assert pack_info.source_url is None
    assert pack_info.license_spdx is None


def test_resource_content_metadata():
    """Test ResourceContent with metadata."""
    content = ResourceContent(
        data=b"data",
        content_type="image/svg+xml",
        encoding="utf-8",
        metadata={"width": 24, "height": 24, "tags": ["icon"]},
    )

    assert content.metadata is not None
    assert content.metadata["width"] == 24
    assert content.metadata["height"] == 24
    assert content.metadata["tags"] == ["icon"]


def test_resource_content_no_metadata():
    """Test ResourceContent without metadata (default None)."""
    content = ResourceContent(
        data=b"data",
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    assert content.metadata is None


def test_registered_pack_aliases():
    """Test RegisteredPack with aliases."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    registered = RegisteredPack(
        dist_name="acme-icons",
        pack_name="lucide",
        pack=pack,
        aliases=("luc", "lucide-icons"),
    )

    assert registered.aliases == ("luc", "lucide-icons")


def test_registered_pack_no_aliases():
    """Test RegisteredPack without aliases (empty tuple)."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    registered = RegisteredPack(
        dist_name="acme-icons",
        pack_name="lucide",
        pack=pack,
        aliases=(),
    )

    assert registered.aliases == ()

