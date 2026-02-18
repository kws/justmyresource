"""Tests for the command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from justmyresource.cli import cmd_get, cmd_info, cmd_list, cmd_packs, main
from justmyresource.types import ResourceInfo
from tests.conftest import MockResourcePack, create_test_resource_content


@pytest.fixture
def mock_registry():
    """Create a mock registry with test packs."""
    pack1 = MockResourcePack(
        resources={
            "icon1": create_test_resource_content(
                b"<svg>icon1</svg>", "image/svg+xml", "utf-8"
            ),
            "icon2": create_test_resource_content(
                b"<svg>icon2</svg>", "image/svg+xml", "utf-8"
            ),
            "arrow-left": create_test_resource_content(
                b"<svg>arrow</svg>", "image/svg+xml", "utf-8"
            ),
        },
        dist_name="acme-icons",
        pack_name="lucide",
        prefixes=["luc"],
    )

    pack2 = MockResourcePack(
        resources={"icon3": create_test_resource_content(b"data", "image/png")},
        dist_name="cool-icons",
        pack_name="feather",
    )

    with patch("justmyresource.cli.ResourceRegistry") as mock_registry_class:
        registry = MagicMock()
        mock_registry_class.return_value = registry

        # Mock discover
        registry.discover = MagicMock()

        # Mock list_resources
        def list_resources(pack=None):
            if pack == "acme-icons/lucide" or pack == "lucide":
                return [
                    ResourceInfo(
                        name="icon1",
                        pack="acme-icons/lucide",
                        content_type="image/svg+xml",
                    ),
                    ResourceInfo(
                        name="icon2",
                        pack="acme-icons/lucide",
                        content_type="image/svg+xml",
                    ),
                    ResourceInfo(
                        name="arrow-left",
                        pack="acme-icons/lucide",
                        content_type="image/svg+xml",
                    ),
                ]
            elif pack == "cool-icons/feather" or pack == "feather":
                return [
                    ResourceInfo(
                        name="icon3",
                        pack="cool-icons/feather",
                        content_type="image/png",
                    ),
                ]
            else:
                # All packs
                return [
                    ResourceInfo(
                        name="icon1",
                        pack="acme-icons/lucide",
                        content_type="image/svg+xml",
                    ),
                    ResourceInfo(
                        name="icon2",
                        pack="acme-icons/lucide",
                        content_type="image/svg+xml",
                    ),
                    ResourceInfo(
                        name="arrow-left",
                        pack="acme-icons/lucide",
                        content_type="image/svg+xml",
                    ),
                    ResourceInfo(
                        name="icon3",
                        pack="cool-icons/feather",
                        content_type="image/png",
                    ),
                ]

        registry.list_resources = MagicMock(side_effect=list_resources)

        # Mock get_resource
        def get_resource(name):
            if name == "lucide:icon1":
                return create_test_resource_content(
                    b"<svg>icon1</svg>", "image/svg+xml", "utf-8"
                )
            elif name == "lucide:icon2":
                return create_test_resource_content(
                    b"<svg>icon2</svg>", "image/svg+xml", "utf-8"
                )
            elif name == "lucide:missing":
                raise ValueError("Resource not found: missing")
            else:
                raise ValueError(f"Unknown resource: {name}")

        registry.get_resource = MagicMock(side_effect=get_resource)

        # Mock list_packs
        registry.list_packs = MagicMock(
            return_value=["acme-icons/lucide", "cool-icons/feather"]
        )

        # Mock get_prefix_map
        registry.get_prefix_map = MagicMock(
            return_value={
                "acme-icons/lucide": "acme-icons/lucide",
                "lucide": "acme-icons/lucide",
                "luc": "acme-icons/lucide",
                "cool-icons/feather": "cool-icons/feather",
                "feather": "cool-icons/feather",
            }
        )

        # Mock get_prefix_collisions
        registry.get_prefix_collisions = MagicMock(return_value={})

        # Mock _packs for internal access
        registry._packs = {
            "acme-icons/lucide": MagicMock(
                dist_name="acme-icons",
                pack_name="lucide",
                aliases=("luc",),
                pack=pack1,
            ),
            "cool-icons/feather": MagicMock(
                dist_name="cool-icons",
                pack_name="feather",
                aliases=(),
                pack=pack2,
            ),
        }

        # Mock _resolve_name
        def resolve_name(name):
            if name == "lucide:icon1":
                return ("acme-icons/lucide", "icon1")
            elif name == "lucide:icon2":
                return ("acme-icons/lucide", "icon2")
            elif name == "lucide:missing":
                return ("acme-icons/lucide", "missing")
            else:
                raise ValueError(f"Unknown resource: {name}")

        registry._resolve_name = MagicMock(side_effect=resolve_name)

        yield registry


def test_cmd_list_basic(capsys, mock_registry):
    """Test basic list command with grouped output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search=None,
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    # Check for pack headers
    assert "acme-icons/lucide" in captured.out
    assert "cool-icons/feather" in captured.out
    # Check for resource names (indented)
    assert "  icon1" in captured.out or "icon1" in captured.out
    assert "  icon2" in captured.out or "icon2" in captured.out
    assert "  icon3" in captured.out or "icon3" in captured.out
    # Check for summary in stderr
    assert "4 resources" in captured.err
    assert "2 packs" in captured.err


def test_cmd_list_verbose(capsys, mock_registry):
    """Test list command with verbose output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search=None,
        verbose=True,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    # Check for pack headers
    assert "acme-icons/lucide" in captured.out
    # Check for resource names with content type
    assert "icon1" in captured.out
    assert "[image/svg+xml]" in captured.out


def test_cmd_list_json(capsys, mock_registry):
    """Test list command with JSON output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search=None,
        verbose=False,
        json=True,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "resources" in data
    assert "count" in data
    assert data["count"] == 4
    assert len(data["resources"]) == 4


def test_cmd_list_filter(capsys, mock_registry):
    """Test list command with filter."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter="arrow-*",
        search=None,
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "arrow-left" in captured.out
    assert "icon1" not in captured.out
    assert "icon2" not in captured.out


def test_cmd_list_pack_filter(capsys, mock_registry):
    """Test list command with pack filter (flat output)."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack="lucide",
        filter=None,
        search=None,
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    # With --pack, output should be flat (no grouping headers)
    assert "icon1" in captured.out
    assert "icon2" in captured.out
    assert "icon3" not in captured.out
    # Should not have pack header when filtering to single pack
    assert "acme-icons/lucide" not in captured.out


def test_cmd_list_search_substring(capsys, mock_registry):
    """Test list command with search (substring matching)."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search="arrow",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "arrow-left" in captured.out
    assert "icon1" not in captured.out
    assert "icon2" not in captured.out
    assert "icon3" not in captured.out


def test_cmd_list_search_subsequence(capsys, mock_registry):
    """Test list command with search (subsequence matching)."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search="icn1",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "icon1" in captured.out
    assert "icon2" not in captured.out
    assert "icon3" not in captured.out


def test_cmd_list_search_pack_name(capsys, mock_registry):
    """Test list command with search matching pack name."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search="lucide",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    # Should find all resources from lucide pack
    assert "icon1" in captured.out
    assert "icon2" in captured.out
    assert "arrow-left" in captured.out
    assert "icon3" not in captured.out  # From different pack


def test_cmd_list_search_case_insensitive(capsys, mock_registry):
    """Test list command with search (case-insensitive)."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search="ARROW",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "arrow-left" in captured.out


def test_cmd_list_search_no_results(capsys, mock_registry):
    """Test list command with search that matches nothing."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter=None,
        search="nonexistent",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "icon1" not in captured.out
    assert "icon2" not in captured.out
    assert "icon3" not in captured.out
    # Should still show summary
    assert "0 resources" in captured.err


def test_cmd_list_search_with_pack_filter(capsys, mock_registry):
    """Test list command with search combined with pack filter."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack="lucide",
        filter=None,
        search="icon",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    # Should find all resources from lucide pack because "icon" matches pack name "acme-icons/lucide"
    assert "icon1" in captured.out
    assert "icon2" in captured.out
    assert "arrow-left" in captured.out  # Included because pack name matches "icon"
    assert "icon3" not in captured.out  # From different pack


def test_cmd_list_search_with_filter(capsys, mock_registry):
    """Test list command with search combined with glob filter."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        pack=None,
        filter="icon*",
        search="1",
        verbose=False,
        json=False,
    )
    result = cmd_list(args)
    assert result == 0
    captured = capsys.readouterr()
    # Should find icon1 (matches both glob and search)
    assert "icon1" in captured.out
    assert "icon2" not in captured.out  # Matches glob but not search
    assert "icon3" not in captured.out  # Matches glob but not search
    assert "arrow-left" not in captured.out  # Doesn't match glob


def test_cmd_get_metadata_only(capsys, mock_registry):
    """Test get command showing metadata only."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        output=None,
        json=False,
    )
    result = cmd_get(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "Resource: lucide:icon1" in captured.out
    assert "Pack: acme-icons/lucide" in captured.out
    assert "Content-Type: image/svg+xml" in captured.out


def test_cmd_get_output_stdout(capsys, mock_registry):
    """Test get command outputting to stdout."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        output="-",
        json=False,
    )
    result = cmd_get(args)
    assert result == 0
    captured = capsys.readouterr()
    assert captured.out == "<svg>icon1</svg>"


def test_cmd_get_output_file(tmp_path, mock_registry):
    """Test get command saving to file."""
    output_file = tmp_path / "icon.svg"
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        output=str(output_file),
        json=False,
    )
    result = cmd_get(args)
    assert result == 0
    assert output_file.exists()
    assert output_file.read_text() == "<svg>icon1</svg>"


def test_cmd_get_resource_not_found(capsys, mock_registry):
    """Test get command with resource not found."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:missing",
        output=None,
        json=False,
    )
    result = cmd_get(args)
    assert result == 2
    captured = capsys.readouterr()
    assert "Resource not found" in captured.err
    assert "Error:" in captured.err


def test_cmd_get_json(capsys, mock_registry):
    """Test get command with JSON output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        output=None,
        json=True,
    )
    result = cmd_get(args)
    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["found"] is True
    assert data["name"] == "lucide:icon1"
    assert data["pack"] == "acme-icons/lucide"
    assert data["content_type"] == "image/svg+xml"


def test_cmd_get_json_not_found(capsys, mock_registry):
    """Test get command with JSON output when resource not found."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:missing",
        output=None,
        json=True,
    )
    result = cmd_get(args)
    assert result == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["found"] is False
    assert "error" in data


def test_cmd_packs_basic(capsys, mock_registry):
    """Test packs command basic output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        verbose=False,
        json=False,
    )
    result = cmd_packs(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "acme-icons/lucide" in captured.out
    assert "cool-icons/feather" in captured.out


def test_cmd_packs_verbose(capsys, mock_registry):
    """Test packs command with verbose output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        verbose=True,
        json=False,
    )
    result = cmd_packs(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "acme-icons/lucide" in captured.out
    assert "Distribution: acme-icons" in captured.out
    assert "Pack: lucide" in captured.out


def test_cmd_packs_json(capsys, mock_registry):
    """Test packs command with JSON output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        verbose=False,
        json=True,
    )
    result = cmd_packs(args)
    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "packs" in data
    assert "count" in data
    assert data["count"] == 2
    assert len(data["packs"]) == 2


def test_cmd_packs_with_pack_info(capsys, mock_registry):
    """Test packs command with PackInfo metadata."""
    # Add PackInfo to mock pack
    from justmyresource.types import PackInfo

    pack_info = PackInfo(
        description="Test icon pack",
        source_url="https://example.com",
        license_spdx="MIT",
    )
    mock_registry._packs["acme-icons/lucide"].pack.get_pack_info = MagicMock(
        return_value=pack_info
    )

    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        verbose=False,
        json=False,
    )
    result = cmd_packs(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "Test icon pack" in captured.out
    assert "https://example.com" in captured.out
    assert "MIT" in captured.out


def test_cmd_info_basic(capsys, mock_registry):
    """Test info command basic output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        json=False,
    )
    result = cmd_info(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "Resource: lucide:icon1" in captured.out
    assert "Pack: acme-icons/lucide" in captured.out
    assert "Content-Type: image/svg+xml" in captured.out


def test_cmd_info_json(capsys, mock_registry):
    """Test info command with JSON output."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        json=True,
    )
    result = cmd_info(args)
    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["found"] is True
    assert data["name"] == "lucide:icon1"
    assert "pack" in data
    assert data["pack"]["qualified_name"] == "acme-icons/lucide"


def test_cmd_info_not_found(capsys, mock_registry):
    """Test info command with resource not found."""
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:missing",
        json=False,
    )
    result = cmd_info(args)
    assert result == 2
    captured = capsys.readouterr()
    assert "Resource not found" in captured.err


def test_main_no_command(capsys):
    """Test main() with no subcommand."""
    with patch("sys.argv", ["justmyresource"]):
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "help" in captured.out.lower()


def test_main_list_command(capsys, mock_registry):
    """Test main() with list command."""
    with patch("sys.argv", ["justmyresource", "list"]):
        result = main()
        assert result == 0


def test_main_get_command(capsys, mock_registry):
    """Test main() with get command."""
    with patch("sys.argv", ["justmyresource", "get", "lucide:icon1"]):
        result = main()
        assert result == 0


def test_main_packs_command(capsys, mock_registry):
    """Test main() with packs command."""
    with patch("sys.argv", ["justmyresource", "packs"]):
        result = main()
        assert result == 0


def test_main_info_command(capsys, mock_registry):
    """Test main() with info command."""
    with patch("sys.argv", ["justmyresource", "info", "lucide:icon1"]):
        result = main()
        assert result == 0


def test_main_keyboard_interrupt(capsys, mock_registry):
    """Test main() handling KeyboardInterrupt."""
    with (
        patch("sys.argv", ["justmyresource", "list"]),
        patch("justmyresource.cli.cmd_list", side_effect=KeyboardInterrupt),
    ):
        result = main()
        assert result == 130
        captured = capsys.readouterr()
        assert "Interrupted by user" in captured.err


def test_main_exception(capsys, mock_registry):
    """Test main() handling general exceptions."""
    with (
        patch("sys.argv", ["justmyresource", "list"]),
        patch("justmyresource.cli.cmd_list", side_effect=RuntimeError("Test error")),
    ):
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err or "Test error" in captured.err


def test_main_exception_json(capsys, mock_registry):
    """Test main() handling exceptions with JSON output."""
    with (
        patch("sys.argv", ["justmyresource", "--json", "list"]),
        patch("justmyresource.cli.cmd_list", side_effect=RuntimeError("Test error")),
    ):
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "error" in data
        assert data["error"] == "Test error"


def test_cmd_get_binary_resource(tmp_path, mock_registry):
    """Test get command with binary resource (PNG)."""

    # Mock binary resource
    def get_resource(name):
        if name == "feather:icon3":
            return create_test_resource_content(b"\x89PNG", "image/png")
        raise ValueError(f"Unknown resource: {name}")

    mock_registry.get_resource = MagicMock(side_effect=get_resource)

    output_file = tmp_path / "icon.png"
    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="feather:icon3",
        output=str(output_file),
        json=False,
    )
    result = cmd_get(args)
    assert result == 0
    assert output_file.exists()
    assert output_file.read_bytes() == b"\x89PNG"


def test_cmd_get_with_resource_path(capsys, mock_registry):
    """Test get command with resource path support."""
    # Mock pack with get_resource_path method
    mock_pack = MagicMock()
    mock_pack.get_resource_path = MagicMock(return_value=Path("/path/to/icon.svg"))
    mock_registry._packs["acme-icons/lucide"].pack = mock_pack

    args = argparse.Namespace(
        blocklist=None,
        prefix_map=None,
        default_prefix=None,
        name="lucide:icon1",
        output=None,
        json=False,
    )
    result = cmd_get(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "Path:" in captured.out
    assert "/path/to/icon.svg" in captured.out
