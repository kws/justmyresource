# Resource Discovery Architecture

This document describes the architecture and design for JustMyResource, a generic resource discovery system that supports SVG icons, raster images, and future extensibility to other resource types (audio, video, etc.). The system combines bundled resource discovery with extensible resource pack discovery via Python EntryPoints.

## 1. Overview

### 1.1 Purpose

The resource discovery system provides a unified interface for locating and resolving resources across multiple sources:

1. **Bundled Resources**: Application-local resources (SVG icons, images, etc.)
2. **Resource Packs**: Third-party resource packages discovered via Python EntryPoints
3. **System Resources**: Platform-specific system resources (future consideration)

The system is designed to be generic enough to support multiple resource types while providing specialized support for SVG icon libraries.

### 1.2 Core Value Proposition

- **Generic Framework**: Unified interface for multiple resource types (SVG, raster images, future: audio/video)
- **Extensible**: Resource packs can be added via standard Python EntryPoints mechanism
- **Icon-Focused**: Specialized support for SVG icon libraries (Lucide, Feather, Material Design Icons, etc.)
- **Prefix-Based Resolution**: Namespace disambiguation via `pack:name` format
- **Efficient**: Lazy loading with caching support
- **Discovery Focus**: This library discovers and retrieves resources. How those resources are used (rendered, cached, transformed) is the responsibility of the consuming application.

### 1.3 Influences & Similar Systems

- **Iconify**: Universal icon framework with unified API for multiple icon libraries
- **react-icons**: React component library aggregating multiple icon sets
- **FreeDesktop Icon Theme Spec**: Hierarchical icon lookup with theme inheritance and size matching
- **Material Design Icons**: Structured icon library with variants and metadata
- **Lucide Icons**: Modern icon library with consistent design and SVG format

## 2. Architecture Overview

The resource discovery system follows a pack-based architecture:

```
┌─────────────────────────────────────────────────────────┐
│              Resource Registry                           │
│  (Unified interface for resource lookup and resolution)  │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Resource   │ │   Resource   │ │   Resource   │
│    Packs     │ │    Packs     │ │    Packs     │
│  (SVG Icons) │ │  (Raster)    │ │  (Future)    │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ EntryPoints  │ │ importlib.   │ │   Protocol   │
│ mechanism    │ │ resources    │ │   Interface  │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 2.1 Resource Types

The system supports multiple resource types through a common pack interface:

1. **SVG Icons**: Vector graphics for icons (primary use case)
2. **Raster Images**: PNG, JPEG, WebP images
3. **Future Types**: Audio files, video files, 3D models, etc.

Each resource type implements the `ResourcePack` protocol, allowing the registry to handle them uniformly while providing type-specific functionality.

## 3. Resource Pack Protocol

The core abstraction is the `ResourcePack` protocol, which defines how resources are discovered and retrieved.

### 3.1 Protocol Definition

```python
from typing import Protocol
from collections.abc import Iterator

class ResourcePack(Protocol):
    """Protocol that all resource sources must implement."""

    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content for a name.
        
        Args:
            name: Resource name/identifier within this pack.
            
        Returns:
            ResourceContent object containing the resource data and metadata.
            
        Raises:
            ValueError: If the resource cannot be found.
        """
        ...
    
    def list_resources(self) -> Iterator[str]:
        """List all available resource names/identifiers.
        
        Yields:
            Resource name/identifier strings.
        """
        ...
    
    def get_priority(self) -> int:
        """Return priority for this pack (higher = processed first).
        
        Standard priorities:
        - Resource Packs: 100
        - System Resources: 0 (future consideration)
        
        Returns:
            Integer priority value (higher = higher priority).
        """
        ...
    
    def get_name(self) -> str:
        """Return canonical name for this pack (used in blocklist).
        
        Returns:
            String identifier for this resource pack.
        """
        ...
    
    def get_prefixes(self) -> list[str]:
        """Return list of prefixes that map to this pack.
        
        Prefixes are used for namespace disambiguation in `pack:name` format.
        
        Returns:
            List of prefix strings (e.g., ["lucide", "luc"]).
        """
        ...
```

### 3.2 ResourceContent Type

Resources are returned as `ResourceContent` objects, which provide both the raw data and metadata:

```python
@dataclass(frozen=True, slots=True)
class ResourceContent:
    """Content returned by a resource provider."""
    
    data: bytes
    """Raw resource bytes (SVG as UTF-8 bytes, PNG as-is, etc.)."""
    
    content_type: str
    """MIME type: 'image/svg+xml', 'image/png', 'audio/wav', etc."""
    
    encoding: str | None = None
    """Encoding for text-based resources (e.g., 'utf-8'), None for binary."""
    
    metadata: dict[str, Any] | None = None
    """Optional descriptive details (dimensions, tags, variants, etc.)."""
    
    @property
    def text(self) -> str:
        """Decode data as text. Raises if encoding is None."""
        ...
```

This wrapper allows consumers to:
- Branch on `content_type` to handle different resource types
- Access text content via `.text` property for text-based resources
- Access pack-specific metadata via `.metadata` dict
- Handle mixed-format packs (e.g., a samples pack with both SVG and PNG)

## 4. Resource Pack Discovery

Resource packs are third-party packages that provide resources via Python EntryPoints.

### 4.1 EntryPoints Mechanism

Resource packs register themselves using the EntryPoints mechanism (`importlib.metadata.entry_points`).

**Entry Point Group**: `justmyresource.packs`

**Entry Point Format**: Factory function that returns a pack instance and optional metadata

### 4.2 Resource Pack Structure

A resource pack package should define an entry point in its `pyproject.toml`:

```toml
[project.entry-points."justmyresource.packs"]
"my-icon-pack" = "my_icon_pack:get_resource_provider"
```

### 4.3 Resource Pack Implementation

The entry point factory function can return the pack in several formats:

```python
# my_icon_pack/__init__.py
from my_icon_pack.provider import MyIconProvider

def get_resource_provider():
    """Entry point factory returning resource provider."""
    # Option 1: Return pack instance directly
    return MyIconProvider()
    
    # Option 2: Return tuple with pack and metadata dict
    # return (MyIconProvider(), {"prefixes": ["myicons", "mi"], "version": "1.0.0"})
    
    # Option 3: Return tuple with descriptor_type, pack, and prefixes
    # return (MyIconDescriptor, MyIconProvider(), ["myicons", "mi"])
```

### 4.4 Discovery Implementation

The `ResourceRegistry` automatically discovers and loads resource packs:

```python
class ResourceRegistry:
    """Registry for resource packs."""
    
    def __init__(self, blocklist: set[str] | None = None) -> None:
        """Initialize registry with optional blocklist."""
        self._packs: dict[str, ResourcePack] = {}
        self._prefixes: dict[str, str] = {}  # prefix -> pack_name
        self._discovered = False
        self._blocklist = self._parse_blocklist(blocklist)
    
    def discover(self) -> None:
        """Discover resource packs from EntryPoints (lazy, runs once)."""
        if self._discovered:
            return
        
        # Load packs from entry points, sort by priority
        # Register packs and their prefixes
        ...
    
    def get_resource(self, name: str) -> ResourceContent:
        """Get resource by name (supports 'pack:name' format)."""
        ...
```

## 5. Prefix-Based Resolution

Resources can be referenced using a `pack:name` format for namespace disambiguation:

- `lucide:lightbulb` - Lucide icon named "lightbulb"
- `feather:home` - Feather icon named "home"
- `material:settings` - Material Design icon named "settings"
- `samples:logo` - Sample resource named "logo" (could be SVG or PNG)

If no prefix is provided, the registry searches packs in priority order (highest priority first).

### 5.1 Resolution Algorithm

1. If name contains `:`, split into `(prefix, resource_name)`
2. Look up prefix in `_prefixes` dict to get pack name
3. Call `pack.get_resource(resource_name)`
4. If no prefix, iterate packs by priority until resource is found

## 6. Resource Registry Pattern

The resource registry provides a unified interface for resource lookup and resolution.

### 6.1 Registry API

```python
registry = ResourceRegistry()

# Get resource with prefix
content = registry.get_resource("lucide:lightbulb")

# Get resource without prefix (searches by priority)
content = registry.get_resource("lightbulb")

# List all resources
for resource_info in registry.list_resources():
    print(f"{resource_info.pack}:{resource_info.name}")

# List resources from specific pack
for resource_info in registry.list_resources(pack="lucide"):
    print(resource_info.name)

# List registered packs
for pack_name in registry.list_packs():
    print(pack_name)
```

### 6.2 Factory Functions

```python
_default_registry: ResourceRegistry | None = None

def get_default_registry() -> ResourceRegistry:
    """Get the default global resource registry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ResourceRegistry()
    return _default_registry
```

## 7. Priority and Blocklist

### 7.1 Priority System

Resource packs have priorities (higher = processed first):

- **Resource Packs**: Priority 100 (highest)
- **System Resources**: Priority 0 (future consideration, lowest)

When multiple packs provide the same resource name, the highest priority pack wins.

### 7.2 Blocklist Support

Packs can be blocked via constructor or environment variable:

```python
# Block specific packs
registry = ResourceRegistry(blocklist={"broken-pack", "test-pack"})

# Block via environment variable
# RESOURCE_DISCOVERY_BLOCKLIST="broken-pack,test-pack" python app.py
```

This is critical for infrastructure: if a pack causes issues in production, Ops can disable it without code changes.

## 8. Example Usage

### 8.1 Basic Resource Usage

```python
from justmyresource import ResourceRegistry, get_default_registry

# Get default registry
registry = get_default_registry()

# Get resource with prefix
content = registry.get_resource("lucide:lightbulb")

# Check content type
if content.content_type == "image/svg+xml":
    svg_text = content.text  # Decode as UTF-8
    # Use SVG text...

# Get resource without prefix (searches by priority)
content = registry.get_resource("logo")  # Could be from any pack

# Access metadata
if content.metadata:
    dimensions = content.metadata.get("dimensions")
```

### 8.2 Resource Pack Implementation

```python
# my_icon_pack/__init__.py
from my_icon_pack.provider import MyIconProvider
from my_icon_pack.descriptors import MyIconDescriptor

def get_resource_provider():
    """Entry point factory for icon pack."""
    return (MyIconDescriptor, MyIconProvider(), ["myicons", "mi"])

# pyproject.toml
# [project.entry-points."justmyresource.packs"]
# "my-icon-pack" = "my_icon_pack:get_resource_provider"
```

### 8.3 Example Pack Implementation

```python
from collections.abc import Iterator
from pathlib import Path
from importlib.resources import files
from justmyresource.types import ResourceContent, ResourcePack

class FileBasedResourcePack:
    """Example resource pack that loads files from package."""
    
    def __init__(self, package_name: str, prefix: str):
        self.package_name = package_name
        self.prefix = prefix
        self._base_path = Path(str(files(package_name)))
    
    def get_resource(self, name: str) -> ResourceContent:
        """Get resource from file."""
        # Try SVG first
        svg_path = self._base_path / f"{name}.svg"
        if svg_path.exists():
            with open(svg_path, "rb") as f:
                return ResourceContent(
                    data=f.read(),
                    content_type="image/svg+xml",
                    encoding="utf-8",
                )
        
        # Try PNG
        png_path = self._base_path / f"{name}.png"
        if png_path.exists():
            with open(png_path, "rb") as f:
                return ResourceContent(
                    data=f.read(),
                    content_type="image/png",
                )
        
        raise ValueError(f"Resource not found: {name}")
    
    def list_resources(self) -> Iterator[str]:
        """List all resources."""
        for path in self._base_path.iterdir():
            if path.suffix in (".svg", ".png"):
                yield path.stem
    
    def get_priority(self) -> int:
        return 100
    
    def get_name(self) -> str:
        return self.package_name
    
    def get_prefixes(self) -> list[str]:
        return [self.prefix]
```

## 9. Best Practices

### 9.1 Implementation Recommendations

1. **Lazy Loading**: Load resource packs only when needed
2. **Caching**: Cache resource content and metadata at the pack level
3. **Error Handling**: Gracefully handle missing resources and invalid packs
4. **Extensibility**: Use protocols and EntryPoints for extensibility
5. **Prefix Resolution**: Support both prefix-based and priority-based resource references
6. **Content Type**: Always set `content_type` correctly to enable consumer branching

### 9.2 Performance Considerations

- **Lazy Discovery**: Load entry points only when registry is accessed
- **Resource Caching**: Cache frequently accessed resources at pack level
- **Lazy Resource Loading**: Load resource content only when requested
- **Parallel Loading**: Consider parallel resource pack discovery for large installations

### 9.3 Resource Bundling Strategies

**Package-Based**:
- Resources bundled in Python package
- Accessed via `importlib.resources`
- Versioned with package version

**External Files**:
- Resources in separate directory
- Referenced via path configuration
- Can be updated independently

**Remote Resources**:
- Resources fetched from CDN or API
- Cached locally
- Versioned via URL or metadata

## 10. Resource Usage (Out of Scope)

**Note**: This library focuses on discovery and retrieval of resources. How those resources are used (rendered, cached, transformed) is the responsibility of the consuming application.

The library returns `ResourceContent` objects:
- **SVG icons**: SVG bytes (UTF-8 encoded) with `content_type="image/svg+xml"`
- **Raster images**: Image bytes in their native format with appropriate `content_type`
- **Other resources**: Raw content in their native format

Consuming applications may:
- Render SVG to raster formats using libraries like CairoSVG, Pillow, or custom renderers
- Cache resources for performance
- Apply transformations (tinting, resizing, etc.)
- Integrate resources into their own rendering pipelines

These concerns are outside the scope of the discovery library.

## 11. Future Considerations

### 11.1 Audio Resources

Support for audio files with appropriate `ResourceContent`:
- Audio files (MP3, OGG, WAV)
- Sound effects, music tracks
- Metadata: duration, format, sample rate

### 11.2 Video Resources

Support for video files:
- Video files (MP4, WebM)
- Animated content
- Metadata: duration, resolution, codec

### 11.3 3D Models

Support for 3D model files:
- 3D model files (GLTF, OBJ)
- Mesh data, textures
- Metadata: vertices, materials, animations

### 11.4 Resource Search and Discovery

Add resource search capabilities:
- **Name Search**: Search resources by name
- **Tag Search**: Search resources by tags
- **Category Search**: Search resources by category
- **Metadata Search**: Search resources by metadata fields

## 12. Comparison with Existing Solutions

| Feature | JustMyResource | Iconify | react-icons | FreeDesktop |
|---------|----------------|---------|-------------|-------------|
| SVG Icons | ✅ | ✅ | ✅ | ✅ |
| Raster Images | ✅ | ❌ | ❌ | ✅ |
| EntryPoints | ✅ | ❌ | ❌ | ❌ |
| Prefix Resolution | ✅ | ✅ | ❌ | ❌ |
| Multiple Formats | ✅ | ❌ | ❌ | ✅ |
| Extensible | ✅ | ✅ | ❌ | ✅ |
| Language | Python | JS/TS | JS/TS | C/Spec |

**Key Differentiators**:
- Generic resource framework (not icon-specific)
- Python-native with EntryPoints extensibility
- Support for multiple resource types (SVG, raster, future: audio/video)
- Prefix-based namespace resolution
- `ResourceContent` wrapper for type-safe content handling

