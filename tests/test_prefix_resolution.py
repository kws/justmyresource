"""Tests for prefix resolution and collision handling."""

from __future__ import annotations

import warnings
from unittest.mock import patch

import pytest

from justmyresource.core import ResourceRegistry
from justmyresource.types import PrefixCollisionWarning
from tests.conftest import MockResourcePack, create_test_resource_content


def test_qualified_name_resolution():
    """Test that fully qualified names (dist/pack:resource) work."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, [])],
    ):
        registry = ResourceRegistry()
        content = registry.get_resource("acme-icons/lucide:icon1")
        assert content.data == b"data1"


def test_short_name_resolution_when_unique():
    """Test that short pack names work when there's no collision."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, [])],
    ):
        registry = ResourceRegistry()
        content = registry.get_resource("lucide:icon1")
        assert content.data == b"data1"


def test_alias_resolution():
    """Test that aliases from get_prefixes() work."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        prefixes=["luc"],
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, ["luc"])],
    ):
        registry = ResourceRegistry()
        content = registry.get_resource("luc:icon1")
        assert content.data == b"data1"


def test_prefix_collision_warning():
    """Test that prefix collisions emit PrefixCollisionWarning."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        priority=100,
    )

    pack2 = MockResourcePack(
        resources={"icon2": create_test_resource_content(b"data2")},
        dist_name="cool-icons",
        pack_name="lucide",  # Same pack name!
        priority=100,
    )

    def factory1():
        return pack1

    def factory2():
        return pack2

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[
            ("acme-icons", "lucide", pack1, []),
            ("cool-icons", "lucide", pack2, []),
        ],
    ):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            registry = ResourceRegistry()
            # Trigger discovery to emit warnings
            registry.discover()
            # Should have warned about collision
            assert len(w) > 0
            assert any(
                issubclass(warning.category, PrefixCollisionWarning) for warning in w
            )


def test_higher_priority_wins_collision():
    """Test that higher priority pack wins in collision."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        priority=100,
    )

    pack2 = MockResourcePack(
        resources={"icon2": create_test_resource_content(b"data2")},
        dist_name="cool-icons",
        pack_name="lucide",
        priority=50,  # Lower priority
    )

    def factory1():
        return pack1

    def factory2():
        return pack2

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[
            ("acme-icons", "lucide", pack1, []),
            ("cool-icons", "lucide", pack2, []),
        ],
    ):
        registry = ResourceRegistry()
        # Higher priority pack should win
        content = registry.get_resource("lucide:icon1")
        assert content.data == b"data1"

        # Lower priority pack should still be accessible via qualified name
        content = registry.get_resource("cool-icons/lucide:icon2")
        assert content.data == b"data2"


def test_prefix_map_overrides():
    """Test that prefix_map overrides auto-discovered prefixes."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    pack2 = MockResourcePack(
        resources={"icon2": create_test_resource_content(b"data2")},
        dist_name="cool-icons",
        pack_name="feather",
    )

    def factory1():
        return pack1

    def factory2():
        return pack2

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[
            ("acme-icons", "lucide", pack1, []),
            ("cool-icons", "feather", pack2, []),
        ],
    ):
        # Map "icons" to cool-icons/feather
        registry = ResourceRegistry(prefix_map={"icons": "cool-icons/feather"})
        content = registry.get_resource("icons:icon2")
        assert content.data == b"data2"


def test_prefix_map_from_env():
    """Test that prefix_map can be set via environment variable."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

    with (
        patch(
            "justmyresource.core.ResourceRegistry._get_entry_points",
            return_value=[("acme-icons", "lucide", pack1, [])],
        ),
        patch.dict("os.environ", {"RESOURCE_PREFIX_MAP": "icons=acme-icons/lucide"}),
    ):
        registry = ResourceRegistry()
        content = registry.get_resource("icons:icon1")
        assert content.data == b"data1"


def test_blocklist_accepts_qualified_names():
    """Test that blocklist accepts both short and qualified names."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

        with patch(
            "justmyresource.core.ResourceRegistry._get_entry_points",
            return_value=[("acme-icons", "lucide", pack1, [])],
        ):
            # Block by qualified name
            registry = ResourceRegistry(blocklist={"acme-icons/lucide"})
            with pytest.raises(ValueError, match="Unknown resource pack prefix"):
                registry.get_resource("lucide:icon1")


def test_blocklist_accepts_short_names():
    """Test that blocklist accepts short pack names."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

        with patch(
            "justmyresource.core.ResourceRegistry._get_entry_points",
            return_value=[("acme-icons", "lucide", pack1, [])],
        ):
            # Block by short name
            registry = ResourceRegistry(blocklist={"lucide"})
            with pytest.raises(ValueError, match="Unknown resource pack prefix"):
                registry.get_resource("lucide:icon1")


def test_get_prefix_collisions():
    """Test that get_prefix_collisions() returns correct data."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        priority=100,
    )

    pack2 = MockResourcePack(
        resources={"icon2": create_test_resource_content(b"data2")},
        dist_name="cool-icons",
        pack_name="lucide",
        priority=100,
    )

    def factory1():
        return pack1

    def factory2():
        return pack2

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[
            ("acme-icons", "lucide", pack1, []),
            ("cool-icons", "lucide", pack2, []),
        ],
    ):
        registry = ResourceRegistry()
        collisions = registry.get_prefix_collisions()
        assert "lucide" in collisions
        assert "acme-icons/lucide" in collisions["lucide"]
        assert "cool-icons/lucide" in collisions["lucide"]


def test_get_prefix_map():
    """Test that get_prefix_map() returns full mapping."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        prefixes=["luc"],
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, ["luc"])],
    ):
        registry = ResourceRegistry()
        prefix_map = registry.get_prefix_map()

        # Should include qualified name
        assert "acme-icons/lucide" in prefix_map.values()
        # Should include short pack name
        assert prefix_map.get("lucide") == "acme-icons/lucide"
        # Should include alias
        assert prefix_map.get("luc") == "acme-icons/lucide"


def test_ambiguous_prefix_error():
    """Test that ambiguous prefixes raise helpful errors."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
        priority=100,
    )

    pack2 = MockResourcePack(
        resources={"icon2": create_test_resource_content(b"data2")},
        dist_name="cool-icons",
        pack_name="lucide",
        priority=100,
    )

    def factory1():
        return pack1

    def factory2():
        return pack2

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[
            ("acme-icons", "lucide", pack1, []),
            ("cool-icons", "lucide", pack2, []),
        ],
    ):
        registry = ResourceRegistry()
        # Should raise error with helpful message
        with pytest.raises(ValueError, match="ambiguous"):
            registry.get_resource("lucide:icon1")


def test_priority_order_search():
    """Test that resources without prefix search by priority order."""
    pack1 = MockResourcePack(
        resources={"common": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="pack1",
        priority=100,
    )

    pack2 = MockResourcePack(
        resources={"common": create_test_resource_content(b"data2")},
        dist_name="cool-icons",
        pack_name="pack2",
        priority=50,
    )

    def factory1():
        return pack1

    def factory2():
        return pack2

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[
            ("acme-icons", "pack1", pack1, []),
            ("cool-icons", "pack2", pack2, []),
        ],
    ):
        registry = ResourceRegistry()
        # Should find from higher priority pack
        content = registry.get_resource("common")
        assert content.data == b"data1"


def test_list_packs_returns_qualified_names():
    """Test that list_packs() returns qualified names."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, [])],
    ):
        registry = ResourceRegistry()
        packs = list(registry.list_packs())
        assert "acme-icons/lucide" in packs


def test_list_resources_with_qualified_pack():
    """Test that list_resources() works with qualified pack names."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, [])],
    ):
        registry = ResourceRegistry()
        resources = list(registry.list_resources(pack="acme-icons/lucide"))
        assert len(resources) == 1
        assert resources[0].name == "icon1"
        assert resources[0].pack == "acme-icons/lucide"


def test_list_resources_with_short_pack_name():
    """Test that list_resources() works with short pack names."""
    pack1 = MockResourcePack(
        resources={"icon1": create_test_resource_content(b"data1")},
        dist_name="acme-icons",
        pack_name="lucide",
    )

    def factory1():
        return pack1

    with patch(
        "justmyresource.core.ResourceRegistry._get_entry_points",
        return_value=[("acme-icons", "lucide", pack1, [])],
    ):
        registry = ResourceRegistry()
        resources = list(registry.list_resources(pack="lucide"))
        assert len(resources) == 1
        assert resources[0].name == "icon1"
        assert resources[0].pack == "acme-icons/lucide"
