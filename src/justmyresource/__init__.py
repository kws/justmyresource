"""JustMyResource - Resource discovery and resolution library."""

from justmyresource.core import ResourceRegistry, get_default_registry
from justmyresource.pack_utils import ZippedResourcePack
from justmyresource.types import (
    PrefixCollisionWarning,
    RegisteredPack,
    ResourceContent,
    ResourceInfo,
    ResourcePack,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "PrefixCollisionWarning",
    "RegisteredPack",
    "ResourceContent",
    "ResourceInfo",
    "ResourcePack",
    "ResourceRegistry",
    "ZippedResourcePack",
    "get_default_registry",
]
