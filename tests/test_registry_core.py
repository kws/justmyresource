"""Tests for core registry functionality not covered by prefix resolution tests."""

from __future__ import annotations

import os
import warnings
from unittest.mock import MagicMock, patch

import pytest

from justmyresource.core import ResourceRegistry, get_default_registry
from tests.conftest import MockResourcePack, create_test_resource_content


def test_blocklist_env_var():
    """Test that RESOURCE_DISCOVERY_BLOCKLIST environment variable works."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    with (
        patch(
            "justmyresource.core.ResourceRegistry._get_entry_points",
            return_value=[("acme-icons", "lucide", pack1, [])],
        ),
        patch.dict(os.environ, {"RESOURCE_DISCOVERY_BLOCKLIST": "lucide"}),
    ):
        registry = ResourceRegistry()
        with pytest.raises(ValueError, match="Unknown resource pack prefix"):
            registry.get_resource("lucide:icon1")


def test_get_entry_points_direct_pack():
    """Test _get_entry_points() with factory returning pack directly."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        prefixes=["luc"],
    )

    # Mock entry_points to return a pack directly
    mock_ep = MagicMock()
    mock_ep.dist.name = "acme-icons"
    mock_ep.name = "lucide"
    mock_ep.load.return_value = lambda: pack  # Factory returns pack directly

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        content = registry.get_resource("lucide:icon1")
        assert content.data == b"data1"


def test_get_entry_points_2_tuple():
    """Test _get_entry_points() with factory returning (pack, metadata) tuple."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    # Mock entry_points to return (pack, metadata) tuple
    mock_ep = MagicMock()
    mock_ep.dist.name = "acme-icons"
    mock_ep.name = "lucide"
    mock_ep.load.return_value = lambda: (pack, {"prefixes": ["luc"]})

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        content = registry.get_resource("luc:icon1")
        assert content.data == b"data1"


def test_get_entry_points_3_tuple():
    """Test _get_entry_points() with factory returning (descriptor, pack, prefixes) tuple."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    # Mock entry_points to return (descriptor, pack, prefixes) tuple
    mock_ep = MagicMock()
    mock_ep.dist.name = "acme-icons"
    mock_ep.name = "lucide"
    mock_ep.load.return_value = lambda: (None, pack, ["luc"])

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        content = registry.get_resource("luc:icon1")
        assert content.data == b"data1"


def test_get_entry_points_skip_invalid():
    """Test _get_entry_points() skips invalid entry points."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    # Mock entry_points with one valid and one invalid
    valid_ep = MagicMock()
    valid_ep.dist.name = "acme-icons"
    valid_ep.name = "lucide"
    valid_ep.load.return_value = lambda: pack

    invalid_ep = MagicMock()
    invalid_ep.dist.name = "broken-pack"
    invalid_ep.name = "broken"
    invalid_ep.load.side_effect = ImportError("Cannot import")

    with patch("justmyresource.core.entry_points", return_value=[valid_ep, invalid_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should only have the valid pack
        packs = list(registry.list_packs())
        assert "acme-icons/lucide" in packs
        assert "broken-pack/broken" not in packs


def test_get_entry_points_skip_no_get_resource():
    """Test _get_entry_points() skips packs without get_resource method."""
    # Create object that doesn't implement ResourcePack
    invalid_pack = MagicMock()
    del invalid_pack.get_resource  # Remove get_resource method

    mock_ep = MagicMock()
    mock_ep.dist.name = "broken-pack"
    mock_ep.name = "broken"
    mock_ep.load.return_value = lambda: invalid_pack

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should have no packs
        packs = list(registry.list_packs())
        assert len(packs) == 0


def test_get_entry_points_skip_no_list_resources():
    """Test _get_entry_points() skips packs without list_resources method."""
    # Create object that has get_resource but not list_resources
    invalid_pack = MagicMock()
    invalid_pack.get_resource = MagicMock(return_value=create_test_resource_content(b"data"))
    del invalid_pack.list_resources  # Remove list_resources method

    mock_ep = MagicMock()
    mock_ep.dist.name = "broken-pack"
    mock_ep.name = "broken"
    mock_ep.load.return_value = lambda: invalid_pack

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should have no packs
        packs = list(registry.list_packs())
        assert len(packs) == 0


def test_get_entry_points_skip_none_result():
    """Test _get_entry_points() skips factories that return None."""
    mock_ep = MagicMock()
    mock_ep.dist.name = "broken-pack"
    mock_ep.name = "broken"
    mock_ep.load.return_value = lambda: None  # Factory returns None

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should have no packs
        packs = list(registry.list_packs())
        assert len(packs) == 0


def test_get_entry_points_skip_invalid_tuple():
    """Test _get_entry_points() skips invalid tuple returns."""
    mock_ep = MagicMock()
    mock_ep.dist.name = "broken-pack"
    mock_ep.name = "broken"
    mock_ep.load.return_value = lambda: ("not", "a", "valid", "tuple")  # Too many items

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should have no packs
        packs = list(registry.list_packs())
        assert len(packs) == 0


def test_discover_idempotency():
    """Test that discover() is idempotent (only runs once)."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    call_count = 0

    def mock_get_entry_points():
        nonlocal call_count
        call_count += 1
        return [("acme-icons", "lucide", pack, [])]

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        side_effect=mock_get_entry_points,
    ):
        registry = ResourceRegistry()
        # First call
        registry.discover()
        first_count = call_count
        # Second call should not trigger discovery again
        registry.discover()
        assert call_count == first_count


def test_register_prefix_same_pack_no_op():
    """Test _register_prefix() no-op when same pack re-registers prefix."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        prefixes=["lucide"],  # Alias matches pack name
    )

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack, ["lucide"])],
    ):
        registry = ResourceRegistry()
        # Should not warn about collision (same pack)
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")
            registry.discover()
        # Should not have any PrefixCollisionWarning
        collision_warnings = [
            w for w in warning_list if w.category.__name__ == "PrefixCollisionWarning"
        ]
        assert len(collision_warnings) == 0


def test_resolve_name_fqn_not_found():
    """Test _resolve_name() raises ValueError for unknown FQN."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack, [])],
    ):
        registry = ResourceRegistry()
        registry.discover()
        with pytest.raises(ValueError, match="Unknown qualified resource pack"):
            registry._resolve_name("unknown-dist/unknown-pack:resource")


def test_list_resources_unknown_pack():
    """Test list_resources() returns empty for unknown pack name."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack, [])],
    ):
        registry = ResourceRegistry()
        registry.discover()
        # Unknown pack should return empty
        resources = list(registry.list_resources(pack="unknown-pack"))
        assert len(resources) == 0


def test_list_resources_unknown_qualified_pack():
    """Test list_resources() returns empty for unknown qualified pack name."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack, [])],
    ):
        registry = ResourceRegistry()
        registry.discover()
        # Unknown qualified pack should return empty
        resources = list(registry.list_resources(pack="unknown-dist/unknown-pack"))
        assert len(resources) == 0


def test_get_default_registry_singleton():
    """Test get_default_registry() returns singleton instance."""
    registry1 = get_default_registry()
    registry2 = get_default_registry()
    assert registry1 is registry2


def test_get_default_registry_reset():
    """Test get_default_registry() can be reset by clearing module-level variable."""
    # Get initial registry
    registry1 = get_default_registry()
    # Clear the module-level variable
    import justmyresource.core

    justmyresource.core._default_registry = None
    # Get new registry
    registry2 = get_default_registry()
    # Should be different instances
    assert registry1 is not registry2


def test_get_entry_points_no_dist_name():
    """Test _get_entry_points() handles missing dist.name gracefully."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    mock_ep = MagicMock()
    mock_ep.dist = None  # No dist attribute
    mock_ep.name = "lucide"
    mock_ep.load.return_value = lambda: pack

    with patch("justmyresource.core.entry_points", return_value=[mock_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should use "unknown" as dist_name
        packs = list(registry.list_packs())
        assert "unknown/lucide" in packs


def test_get_entry_points_exception_in_factory():
    """Test _get_entry_points() skips entry points that raise exceptions."""
    pack = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    # First entry point raises exception
    broken_ep = MagicMock()
    broken_ep.dist.name = "broken-pack"
    broken_ep.name = "broken"
    broken_ep.load.side_effect = RuntimeError("Factory error")

    # Second entry point works
    valid_ep = MagicMock()
    valid_ep.dist.name = "acme-icons"
    valid_ep.name = "lucide"
    valid_ep.load.return_value = lambda: pack

    with patch("justmyresource.core.entry_points", return_value=[broken_ep, valid_ep]):
        registry = ResourceRegistry()
        registry.discover()
        # Should only have the valid pack
        packs = list(registry.list_packs())
        assert "acme-icons/lucide" in packs
        assert "broken-pack/broken" not in packs

