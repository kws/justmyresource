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
- **Efficient**: Lazy loading (packs load resources only when requested)
- **Capabilities Model**: Packs implement only what they support (Listable, Searchable)
- **Online Sources**: Designed for both local and online resource packs (APIs, soundboards, public image services)
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

### 2.1 Resource Types and Sources

The system supports multiple resource types through a common pack interface:

1. **SVG Icons**: Vector graphics for icons (primary use case)
2. **Raster Images**: PNG, JPEG, WebP images
3. **Future Types**: Audio files, video files, 3D models, etc.

Resource packs can be:
- **Local**: Bundled in Python packages (zip files, directories)
- **Online**: Fetched from APIs or remote services (Unsplash, Freesound, etc.)

Each resource type implements the `ResourcePack` protocol, allowing the registry to handle them uniformly while providing type-specific functionality.

## 3. Resource Pack Protocol

The core abstraction is the `ResourcePack` protocol, which defines how resources are discovered and retrieved. The protocol follows a **capabilities model** where packs implement only the methods they support.

### 3.1 Core Protocol Definition

```python
from typing import Protocol
from collections.abc import Iterator

class ResourcePack(Protocol):
    """Core protocol that all resource sources must implement.

    This is the minimal interface required for a pack to be registered.
    Pack identity is derived from Python packaging infrastructure:
    - Distribution name (from pyproject.toml [project] name)
    - Entry point name (from pyproject.toml entry-points key)

    The qualified pack name is "dist_name/pack_name" and is always unique.
    """

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
    
    def get_prefixes(self) -> list[str]:
        """Return list of optional alias prefixes that map to this pack.
        
        Prefixes are convenience aliases for namespace disambiguation.
        For example, a pack with prefix "luc" can be accessed as "luc:lightbulb".
        
        Note: The pack's entry point name and qualified name (dist/pack)
        are automatically registered as prefixes. This method only provides
        additional short aliases.
        
        Returns:
            List of prefix strings (e.g., ["luc", "mi"]).
        """
        ...
```

**Key Design Decision**: The core `ResourcePack` protocol requires `get_resource()`, `list_resources()`, and `get_prefixes()`. All packs must implement `list_resources()` to enable resource discovery.

**Future Consideration**: A capability model decomposition (separating `ListableResourcePack` and `SearchableResourcePack` protocols) may be implemented when the first online pack is built. Until then, all packs must implement `list_resources()`.

### 3.3 ResourceContent Type

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

**Design Note**: The `data` field always contains the resource bytes. Packs may include provenance URLs or other metadata in the `metadata` dict if needed.

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

The `ResourceRegistry` automatically discovers and loads resource packs. All packs must implement `get_resource()`, `list_resources()`, and `get_prefixes()`:

```python
class ResourceRegistry:
    """Registry for resource packs."""
    
    def __init__(
        self,
        blocklist: set[str] | None = None,
        prefix_map: dict[str, str] | None = None,
        default_prefix: str | None = None,
    ) -> None:
        """Initialize registry with optional blocklist, prefix_map, and default_prefix."""
        ...
    
    def discover(self) -> None:
        """Discover resource packs from EntryPoints (lazy, runs once).
        
        Loads packs from entry points, sorts by FQN for deterministic ordering,
        registers packs and their prefixes (with collision detection), and applies
        prefix_map overrides.
        """
        ...
    
    def get_resource(self, name: str) -> ResourceContent:
        """Get resource by name (sync).
        
        Execution flow: discover (I/O) → resolve (pure kernel) → execute (pack I/O)
        
        Supports multiple resolution forms:
        - "dist/pack:resource" - fully qualified (always unique)
        - "pack:resource" - short pack name (works if unique)
        - "alias:resource" - alias from get_prefixes() (works if unique)
        - "resource" - rewritten to "{default_prefix}:resource" if default_prefix is set
        """
        ...
    
    def list_resources(self, pack: str | None = None) -> Iterator[ResourceInfo]:
        """List all discovered resources.
        
        Args:
            pack: Optional qualified pack name (dist/pack format) or short pack name to filter by.
                If None, lists resources from all packs.
        
        Yields:
            ResourceInfo objects for each discovered resource.
        """
        ...
    
    def list_packs(self) -> Iterator[str]:
        """List all registered resource pack qualified names.
        
        Yields:
            Qualified resource pack names in "dist/pack" format.
        """
        ...
    
    def get_prefix_map(self) -> dict[str, str]:
        """Get current prefix to qualified pack name mapping."""
        ...
    
    def get_prefix_collisions(self) -> dict[str, list[str]]:
        """Get prefixes that are claimed by multiple packs."""
        ...
```

## 5. Prefix-Based Resolution

Resources can be referenced using multiple resolution forms, from most specific to least specific:

### 5.1 Resolution Forms

1. **Fully Qualified** (`dist/pack:resource`) - Always unique, guaranteed by PyPI
   - `acme-icons/lucide:lightbulb` - Explicit distribution and pack
   - `cool-icons/feather:home` - Different distribution, same pack name

2. **Short Pack Name** (`pack:resource`) - Works if pack name is unique
   - `lucide:lightbulb` - Short form when only one "lucide" pack exists
   - `feather:home` - Short form when only one "feather" pack exists

3. **Alias** (`alias:resource`) - Convenience aliases from `get_prefixes()`
   - `luc:lightbulb` - Short alias for "lucide"
   - `mi:settings` - Short alias for "material-icons"

4. **Bare Name** (`resource`) - No prefix, rewritten using `default_prefix`
   - `lightbulb` - Resolved as `{default_prefix}:lightbulb` if default_prefix is set
   - Raises error if no default_prefix is configured

### 5.2 Resolution Algorithm

1. If name contains `:`, split on last `:` to get `(prefix_part, resource_name)`
2. If `prefix_part` contains `/`, treat as fully qualified (`dist/pack` format)
   - Look up qualified name directly in `_packs`
3. If `prefix_part` has no `/`, look up in prefix map:
   - Check user `prefix_map` overrides (highest precedence)
   - Check aliases from `get_prefixes()`
   - Check short pack names (entry point names)
   - If ambiguous (collision), raise error with qualified alternatives
4. If no `:` at all (bare name):
   - If `default_prefix` is set, rewrite as `{default_prefix}:name` and resolve recursively
   - If `default_prefix` is not set, raise `ValueError` with guidance

### 5.3 Pack Identity and Qualified Names

Pack identity is derived from Python packaging infrastructure, not from pack code:

- **Distribution Name**: From `pyproject.toml` `[project] name` (globally unique on PyPI)
- **Pack Name**: From entry point key in `pyproject.toml` (unique within a distribution)
- **Qualified Name**: `dist_name/pack_name` format (always globally unique)

Example:
```toml
# In package "acme-icons" (PyPI distribution name)
[project.entry-points."justmyresource.packs"]
"lucide" = "acme_icons.lucide:get_provider"    # Qualified: acme-icons/lucide
"feather" = "acme_icons.feather:get_provider"  # Qualified: acme-icons/feather
```

The qualified name `acme-icons/lucide` is always registered as a prefix, ensuring the pack is always accessible even if the short name `lucide` collides with another pack.

### 5.4 Prefix Collision Detection

When multiple packs claim the same prefix (short name or alias), the registry:

1. **Emits `PrefixCollisionWarning`** - Alerts users to the collision
2. **Marks as Ambiguous** - No winner is picked; the prefix becomes ambiguous
3. **Tracks Collisions** - Available via `get_prefix_collisions()`
4. **Preserves Access** - Both packs remain accessible via qualified names or `prefix_map`

Example collision scenario:
```python
# Two different distributions both register "lucide" pack
# acme-icons/lucide
# cool-icons/lucide

registry = ResourceRegistry()
# Warning: Prefix 'lucide' collision: pack name 'lucide' from 'cool-icons/lucide' 
# conflicts with 'acme-icons/lucide'. The prefix is ambiguous.
# Use qualified names ('acme-icons/lucide:resource' or 'cool-icons/lucide:resource') 
# or configure prefix_map to resolve.

# Both are accessible via FQN:
content1 = registry.get_resource("acme-icons/lucide:lightbulb")  # Explicit
content2 = registry.get_resource("cool-icons/lucide:lightbulb")  # Explicit

# Short name raises error (ambiguous):
# registry.get_resource("lucide:lightbulb")  # ValueError: ambiguous

# Can be resolved via prefix_map:
registry = ResourceRegistry(prefix_map={"lucide": "acme-icons/lucide"})
content = registry.get_resource("lucide:lightbulb")  # Works, resolves to acme-icons/lucide
```

### 5.5 Prefix Map Overrides

Users can override prefix mappings via `prefix_map` parameter or environment variable:

```python
# Via constructor
registry = ResourceRegistry(
    prefix_map={
        "icons": "acme-icons/lucide",  # Map "icons" to specific pack
        "mi": "material-icons/core",   # Custom alias
    }
)

# Via environment variable
# RESOURCE_PREFIX_MAP="icons=acme-icons/lucide,mi=material-icons/core" python app.py
```

Prefix map overrides have **highest precedence** and are applied after discovery, allowing fine-grained control over prefix resolution.

## 6. Resource Registry Pattern

The resource registry provides a unified interface for resource lookup and resolution.

### 6.1 Registry API

The registry provides a **synchronous** API designed for local packs, CLI tools, and blocking I/O operations.

#### 6.1.1 Registry API

```python
registry = ResourceRegistry(
    blocklist={"broken-pack"},  # Block specific packs
    prefix_map={"icons": "acme-icons/lucide"},  # Override prefix mappings
    default_prefix="lucide",  # Default prefix for bare-name lookups
)

# --- Resource Retrieval ---

# Get resource with fully qualified name (always unique)
content = registry.get_resource("acme-icons/lucide:lightbulb")

# Get resource with short pack name (works if unique)
content = registry.get_resource("lucide:lightbulb")

# Get resource with alias
content = registry.get_resource("luc:lightbulb")

# Get resource with default_prefix (bare name)
registry = ResourceRegistry(default_prefix="lucide")
content = registry.get_resource("lightbulb")  # Resolves as "lucide:lightbulb"

# --- Discovery ---

# List resources from Listable packs only
for resource_info in registry.list_resources():
    print(f"{resource_info.pack}:{resource_info.name}")  # pack is qualified name

# List resources from specific pack (qualified or short name)
for resource_info in registry.list_resources(pack="acme-icons/lucide"):
    print(resource_info.name)

# List resources from all packs
for resource_info in registry.list_resources():
    print(f"{resource_info.pack}:{resource_info.name}")

# --- Pack Management ---

# List registered packs (returns qualified names)
for qualified_name in registry.list_packs():
    print(qualified_name)  # e.g., "acme-icons/lucide"

# Inspect prefix mappings
prefix_map = registry.get_prefix_map()  # prefix -> qualified_name
collisions = registry.get_prefix_collisions()  # prefix -> [qualified_names]
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

## 7. Default Prefix and Blocklist

### 7.1 Default Prefix

The registry supports a `default_prefix` for bare-name lookups (names without a colon):

```python
# Set default prefix via constructor
registry = ResourceRegistry(default_prefix="lucide")

# Bare names are rewritten using default_prefix
content = registry.get_resource("lightbulb")  # Resolves as "lucide:lightbulb"

# Can use FQN, short name, or alias as default_prefix
registry = ResourceRegistry(default_prefix="acme-icons/lucide")  # FQN
registry = ResourceRegistry(default_prefix="luc")  # Alias

# Via environment variable
# RESOURCE_DEFAULT_PREFIX="lucide" python app.py
```

**Important:** If `default_prefix` points to an ambiguous prefix (collision), it will raise an error unless resolved via `prefix_map`:

```python
# Two packs collide on "lucide"
registry = ResourceRegistry(default_prefix="lucide")  # No prefix_map
registry.get_resource("lightbulb")  # ValueError: ambiguous

# Resolve via prefix_map
registry = ResourceRegistry(
    default_prefix="lucide",
    prefix_map={"lucide": "acme-icons/lucide"},
)
registry.get_resource("lightbulb")  # Works
```

If no `default_prefix` is set and a bare name is used, a `ValueError` is raised with guidance.

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

# Get resource with default_prefix
registry = ResourceRegistry(default_prefix="lucide")
content = registry.get_resource("lightbulb")  # Resolves as "lucide:lightbulb"

# Get resource with fully qualified name (always works)
content = registry.get_resource("acme-icons/lucide:lightbulb")

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
    
    def get_prefixes(self) -> list[str]:
        return [self.prefix]  # Optional aliases (pack name is auto-registered)
```

### 8.4 Using ZippedResourcePack

The `ZippedResourcePack` helper class provides a complete implementation for packs that bundle resources in a zip file:

```python
from justmyresource.pack_utils import ZippedResourcePack

class LucideIconPack(ZippedResourcePack):
    """Lucide icon pack using zip storage."""
    
    def __init__(self):
        super().__init__(
            package_name="jmr_lucide",
            archive_name="icons.zip",
            default_content_type="image/svg+xml",
            prefixes=["luc"]
        )
    
    def _normalize_name(self, name: str) -> str:
        """Add .svg extension if not present."""
        if not name.endswith('.svg'):
            return f"{name}.svg"
        return name

def get_resource_provider():
    return LucideIconPack()
```

This eliminates boilerplate and ensures consistent behavior across packs. The helper provides:

- **Lazy loading**: Zip only opened when resources are accessed
- **Efficient listing**: Resource list is cached, no content loading during listing
- **Manifest support**: Optional `pack_manifest.json` for metadata
- **Variant support**: Handles subdirectories (e.g., `outlined/icon.svg`)
- **Error handling**: Helpful error messages with suggestions for missing resources

### 8.5 Online Source Pack Implementation

Online sources (APIs, soundboards, public image services) can be supported with synchronous, blocking I/O. The key design principle: **packs own their I/O layer** (HTTP clients, connection pooling, caching). The registry is a stateless router and does not manage these concerns.

#### 8.5.1 Blocking Fetch Pattern

Online packs perform blocking network I/O inside `get_resource()`. This is acceptable for CLI tools, scripts, and applications where blocking is acceptable:

```python
from justmyresource.types import ResourceContent, ResourcePack
from collections.abc import Iterator
import requests

class UnsplashImagePack:
    """Example online image pack using Unsplash API (synchronous)."""
    
    def __init__(self, api_key: str):
        """Initialize Unsplash pack.
        
        Args:
            api_key: Unsplash API key.
        """
        self.api_key = api_key
        self.base_url = "https://api.unsplash.com"
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Client-ID {api_key}"})
    
    def get_resource(self, name: str) -> ResourceContent:
        """Fetch image from Unsplash API (blocking).
        
        Args:
            name: Unsplash photo ID.
        """
        # Fetch photo metadata
        resp = self._session.get(f"{self.base_url}/photos/{name}")
        resp.raise_for_status()
        photo_data = resp.json()
        
        # Fetch the actual image bytes (blocking)
        download_url = photo_data["urls"]["regular"]
        image_resp = self._session.get(download_url)
        image_resp.raise_for_status()
        
        return ResourceContent(
            data=image_resp.content,
            content_type="image/jpeg",
            metadata={
                "width": photo_data["width"],
                "height": photo_data["height"],
                "photographer": photo_data["user"]["name"],
                "source_url": download_url,  # Optional provenance metadata in metadata dict
            }
        )
    
    def list_resources(self) -> Iterator[str]:
        """List available resource IDs (may be limited for online sources)."""
        # For online sources, this might return a limited set or raise NotImplementedError
        # depending on the pack's design
        ...
    
    def get_prefixes(self) -> list[str]:
        return ["unsplash", "us"]
```

**Why blocking I/O?**
- Keeps the core library simple and dependency-free
- Acceptable for CLI tools, scripts, and many application contexts
- Packs can use `requests`, `httpx.Client`, or any blocking HTTP library
- For future async considerations, see [async-notes.md](async-notes.md)

**Connection pooling**: `requests.Session` (or `httpx.Client`) pools connections automatically. Creating one session/client in `__init__` and reusing it provides efficient connection reuse.

#### 8.5.2 Alternative: Limited List Pattern

For very large online resources, packs may implement `list_resources()` to return a limited set or raise `NotImplementedError`:

```python
class UnsplashImagePack:
    def list_resources(self) -> Iterator[str]:
        """List available resource IDs (may be limited for online sources)."""
        # For online sources, this might return a limited set or raise NotImplementedError
        # depending on the pack's design
        ...
    
    def get_resource(self, name: str) -> ResourceContent:
        """Get resource content (performs blocking network I/O)."""
        # Fetch from API and return ResourceContent
        ...
```

**Key differences from local packs**:
- Implements `ResourcePack` (sync `get_resource` and `list_resources`)
- Performs blocking network I/O inside methods
- May include provenance URLs or metadata in `ResourceContent.metadata` if needed

## 9. Best Practices

### 9.1 Implementation Recommendations

1. **Protocol Implementation**: All packs must implement `ResourcePack` with `get_resource()`, `list_resources()`, and `get_prefixes()` methods.

2. **Blocking I/O**: Online packs perform blocking network I/O inside `get_resource()`. This is acceptable for CLI tools, scripts, and many application contexts. Packs can use `requests`, `httpx.Client`, or any blocking HTTP library.

3. **Lazy Loading**: Load resource packs only when needed

4. **Error Handling**: Gracefully handle missing resources and invalid packs

5. **Extensibility**: Use protocols and EntryPoints for extensibility

6. **Prefix Resolution**: Support prefix-based resource references with collision detection. When collisions occur, prefixes become ambiguous and require explicit resolution via FQN or `prefix_map`.

7. **Content Type**: Always set `content_type` correctly to enable consumer branching

8. **Metadata**: Packs may include provenance URLs or other metadata in the `metadata` dict if needed. The `data` field always contains the actual resource bytes.

9. **Caching**: Packs may implement their own caching (in-memory, HTTP-level via client injection, etc.), but the registry and core library do not provide caching infrastructure. See section 9.2 for rationale.

### 9.2 Caching Strategy

**Design Decision**: JustMyResource does **not** provide a caching layer in the core library or registry. Caching is handled at multiple existing layers in the ecosystem, and adding our own would be redundant complexity.

#### 9.2.1 Existing Caching Layers

| Layer | Who Owns It | Already Exists? | Example |
|-------|-------------|-----------------|---------|
| **Application-level** | Consumer (e.g. invariant_gfx `ArtifactStore`) | ✅ Yes | DiskStore/MemoryStore cache by manifest digest |
| **HTTP-level** | HTTP client library | ✅ Yes | `hishel` for httpx, `requests-cache` for requests |
| **OS-level** | TCP/DNS stack | ✅ Yes | Automatic connection reuse, DNS caching |
| **Pack-level** | Pack implementation | ✅ Yes | `ZippedResourcePack._resource_list` caches namelist |

#### 9.2.2 Why No Registry-Level Caching?

The registry is a **stateless routing layer**. It resolves `"lucide:lightbulb"` → `(acme-icons/lucide, lightbulb)` and delegates to the pack. It has no business owning caching.

For `invariant_gfx` (the primary consumer), the executor already caches by manifest digest:

```python
# In invariant Executor.execute()
if self.store.exists(digest):
    artifact = self.store.get(digest)  # Cache hit
else:
    artifact = op(manifest)  # Cache miss
    self.store.put(digest, artifact)
```

When `fetch_resource` op calls `registry.get_resource()`, the result gets hashed and cached in the `ArtifactStore`. Second call with same inputs → cache hit, network call never happens. Adding a registry-level cache would be **double-caching with no benefit**.

For **non-invariant consumers** (Flask apps, CLI tools), if they need caching, they can:
1. Use HTTP-level caching on the pack's client (`hishel`, `requests-cache`)
2. Cache `ResourceContent` themselves (it's a frozen dataclass — trivially cacheable)
3. Use `functools.lru_cache` on their own wrapper

#### 9.2.3 Pack-Level Caching

Packs are free to implement their own caching strategies:

```python
from functools import lru_cache

class UnsplashImagePack:
    def __init__(self, api_key: str):
        self._session = requests.Session()
        self._cache: dict[str, ResourceContent] = {}  # Simple in-memory cache
    
    def get_resource(self, name: str) -> ResourceContent:
        if name in self._cache:
            return self._cache[name]
        
        # ... fetch from API (blocking) ...
        content = ResourceContent(...)
        self._cache[name] = content
        return content
```

Or use HTTP-level caching via `requests-cache`:

```python
import requests_cache
session = requests_cache.CachedSession()
pack = UnsplashImagePack(api_key="xxx")
pack._session = session  # Inject cached session
```

**Verdict**: Don't build caching in the registry or core. The existing ecosystem handles it at every layer. Inventing our own cache protocol would add complexity for a problem that's already solved.

### 9.3 Performance Considerations

- **Lazy Discovery**: Load entry points only when registry is accessed
- **Lazy Resource Loading**: Load resource content only when requested
- **Connection Pooling**: Reuse HTTP clients/sessions across requests (`requests.Session` and `httpx.Client` do this automatically)
- **Parallel Loading**: Consider parallel resource pack discovery for large installations

### 9.4 Resource Bundling Strategies

**Package-Based (Local)**:
- Resources bundled in Python package (zip files, directories)
- Accessed via `importlib.resources`
- Versioned with package version
- Implements `ResourcePack` with `list_resources()` for finite, enumerable resources

**External Files (Local)**:
- Resources in separate directory
- Referenced via path configuration
- Can be updated independently
- Implements `ResourcePack` with `list_resources()` for finite, enumerable resources

**Remote Resources (Online)**:
- Resources fetched from CDN or API (Unsplash, Freesound, etc.)
- Implements `ResourcePack` (sync `get_resource` and `list_resources` with blocking I/O)
- Uses blocking HTTP client (`requests`, `httpx.Client`) inside pack methods
- May include provenance URLs in `ResourceContent.metadata` if needed
- Versioned via URL or metadata

### 9.5 Runtime Configuration

Online packs often require API keys, authentication tokens, or custom HTTP client configuration. Two patterns are supported:

#### 9.5.1 Environment Variables (Entry Point Discovery)

Entry point factories can read environment variables for configuration:

```python
# Entry point factory
def get_resource_provider():
    api_key = os.environ.get("UNSPLASH_API_KEY")
    if not api_key:
        return None  # Pack can't initialize without API key
    return UnsplashImagePack(api_key=api_key)
```

**Usage**:
```bash
UNSPLASH_API_KEY="xxx" python app.py
```

This works well for:
- Simple configuration (API keys, base URLs)
- Deployment environments (Docker, Kubernetes)
- CLI tools and scripts

#### 9.5.2 Manual Registration (Programmatic Configuration)

For advanced use cases requiring dependency injection (custom HTTP clients, caching middleware, shared connection pools), packs can be registered manually:

```python
registry = ResourceRegistry()

# Register pack with configuration
registry.register_pack(
    "my-app/unsplash",
    UnsplashImagePack(api_key="xxx"),
    aliases=["unsplash", "us"],
)
```

**Status**: Manual registration is **designed but not yet implemented**. Entry point discovery provides sufficient functionality for current use cases. Manual registration will be added when the first online pack is built and requires programmatic configuration.

Both patterns are well-established in the Python ecosystem and align with the principle of staying lean — no new configuration systems are invented.

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

## 11. Future Considerations & Implementation Status

### 11.0 Implementation Status

This section clarifies what features are currently implemented versus designed for future implementation.

| Feature | Status | Location | Notes |
|---------|--------|----------|-------|
| **Core Protocols** | | | |
| `ResourcePack` (sync) | ✅ Implemented | [types.py](justmyresource/src/justmyresource/types.py) | Currently requires `list_resources()` |
| `ListableResourcePack` | 🔮 Designed | Section 3.2.1 | Will be separated from core protocol |
| `SearchableResourcePack` | 🔮 Designed | Section 3.2.2 | Query-based discovery (sync) |
| **Data Types** | | | |
| `ResourceContent` | ✅ Implemented | [types.py](justmyresource/src/justmyresource/types.py) | Includes data, content_type, encoding, metadata |
| `ResourceInfo` | ✅ Implemented | [types.py](justmyresource/src/justmyresource/types.py) | Lightweight metadata |
| `RegisteredPack` | ✅ Implemented | [types.py](justmyresource/src/justmyresource/types.py) | Pack registration metadata |
| **Registry API** | | | |
| `get_resource()` | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Sync resource retrieval |
| `list_resources()` | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Lists from all packs |
| `list_packs()` | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Lists registered pack names |
| `get_prefix_map()` | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Prefix → pack mapping |
| `get_prefix_collisions()` | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Collision detection |
| `search_resources()` | 🔮 Designed | Section 6.1.1 | Search API (sync) |
| `get_pack_capabilities()` | 🔮 Designed | Section 4.4 | Runtime capability detection |
| `register_pack()` | 🔮 Designed | Section 9.5.2 | Manual pack registration |
| **Infrastructure** | | | |
| Prefix resolution | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | FQN, short name, alias, bare name |
| Collision detection | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Warns on prefix conflicts |
| Blocklist support | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Via constructor or env var |
| Prefix map overrides | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | Via constructor or env var |
| Default prefix | ✅ Implemented | [core.py](justmyresource/src/justmyresource/core.py) | For bare-name lookups |
| **Helpers** | | | |
| `ZippedResourcePack` | ✅ Implemented | [pack_utils.py](justmyresource/src/justmyresource/pack_utils.py) | Base class for zip-based packs |

**Legend:**
- ✅ **Implemented**: Feature exists in current codebase
- 🔮 **Designed**: Architecture specified, implementation pending

**Migration Path**: The capability model decomposition will be implemented when the first online pack is built. This will relax the core `ResourcePack` protocol to only require `get_resource()` and `get_prefixes()`, moving `list_resources()` into the optional `ListableResourcePack` capability.

### 11.1 Async Support (Future Consideration)

**Status**: 🔮 **Out of Scope for Current Architecture**

The current architecture is **synchronous-only** by design. This keeps the core library simple, dependency-free, and suitable for CLI tools, scripts, and many application contexts where blocking I/O is acceptable.

For future exploration of async support, see [async-notes.md](async-notes.md), which discusses potential async patterns, trade-offs, and design considerations. Async support is intentionally deferred to maintain simplicity and avoid premature complexity.

### 11.2 Audio Resources

Support for audio files with appropriate `ResourceContent`:
- Audio files (MP3, OGG, WAV)
- Sound effects, music tracks
- Metadata: duration, format, sample rate

### 11.3 Video Resources

Support for video files:
- Video files (MP4, WebM)
- Animated content
- Metadata: duration, resolution, codec

### 11.4 3D Models

Support for 3D model files:
- 3D model files (GLTF, OBJ)
- Mesh data, textures
- Metadata: vertices, materials, animations

### 11.5 Resource Search and Discovery

**Status**: 🔮 **Designed for Future Implementation**

A capability model decomposition is planned for future implementation:
- **SearchableResourcePack Protocol**: Packs could implement `search_resources()` for query-based discovery (sync)
- **Registry Search API**: `registry.search_resources()` would provide unified search across packs
- **Fallback Strategy**: For packs that don't implement search, the registry could provide client-side name filtering

This capability model will be implemented when the first online pack is built. Until then, all packs must implement `list_resources()` for resource discovery.

## 12. Outstanding Questions

### 12.1 Manual Pack Registration

**Question**: Should the registry support manual registration of packs via a `register_pack()` method, in addition to entry point discovery?

**Status**: ✅ **Designed** (see section 9.5.2 for details). **Not yet implemented**.

**Rationale**: 
- Entry point discovery works well for simple configuration (API keys via env vars)
- Manual registration enables dependency injection (custom HTTP clients, caching middleware, shared connection pools)
- Required for advanced online pack use cases

**Design**:
- `registry.register_pack(qualified_name: str, pack: ResourcePack, aliases: list[str] | None = None)`
- Caller provides `qualified_name` explicitly (e.g., `"my-app/unsplash"`)
- Allows programmatic configuration without `pyproject.toml` entry points
- Enables HTTP client injection, caching middleware, and other advanced patterns

**Implementation Priority**: Will be added when the first online pack is built and requires programmatic configuration. Entry point discovery provides sufficient functionality for current use cases.

## 13. Comparison with Existing Solutions

| Feature | JustMyResource | Iconify | react-icons | FreeDesktop |
|---------|----------------|---------|-------------|-------------|
| SVG Icons | ✅ | ✅ | ✅ | ✅ |
| Raster Images | ✅ | ❌ | ❌ | ✅ |
| EntryPoints | ✅ | ❌ | ❌ | ❌ |
| Prefix Resolution | ✅ | ✅ | ❌ | ❌ |
| Multiple Formats | ✅ | ❌ | ❌ | ✅ |
| Extensible | ✅ | ✅ | ❌ | ✅ |
| Search API | ✅ | ✅ | ❌ | ❌ |
| Async Support | ❌ | ✅ | ✅ | ❌ |
| Online Sources | ✅ | ✅ | ❌ | ❌ |
| Capabilities Model | ✅ | ❌ | ❌ | ❌ |
| Language | Python | JS/TS | JS/TS | C/Spec |

**Key Differentiators**:
- Generic resource framework (not icon-specific)
- Python-native with EntryPoints extensibility
- Support for multiple resource types (SVG, raster, future: audio/video)
- Prefix-based namespace resolution
- `ResourceContent` wrapper for type-safe content handling
- Capabilities model (Listable, Searchable) - packs implement only what they support
- Designed for both local and online sources (APIs, soundboards, public image services) with synchronous blocking I/O
- Simple, dependency-free core suitable for CLI tools and scripts

