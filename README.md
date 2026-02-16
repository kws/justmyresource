# JustMyResource

A precise, lightweight, and extensible resource discovery library for Python. JustMyResource provides a robust "Resource Atlas" for the Python ecosystem—a definitive map of every resource available to an application, whether bundled in a Python package or provided by third-party resource packs.

## Features

- **Generic Framework**: Unified interface for multiple resource types (SVG icons, raster images, future: audio/video)
- **Extensible**: Resource packs can be added via standard Python EntryPoints mechanism
- **Efficient**: Lazy discovery with in-memory caching
- **Prefix-Based Resolution**: Namespace disambiguation via `pack:name` format
- **Type-Safe**: Returns `ResourceContent` objects with MIME types and metadata
- **Zero Dependencies**: Core library has no required dependencies

## Installation

```bash
pip install justmyresource
```

## Quick Start

```python
from justmyresource import ResourceRegistry, get_default_registry

# Get default registry
registry = get_default_registry()

# Get resource with fully qualified name (always unique)
content = registry.get_resource("acme-icons/lucide:lightbulb")

# Get resource with short pack name (works if unique)
content = registry.get_resource("lucide:lightbulb")

# Get resource with alias
content = registry.get_resource("luc:lightbulb")

# Check content type and use accordingly
if content.content_type == "image/svg+xml":
    svg_text = content.text  # Decode as UTF-8
    # Use SVG text...

# Get resource without prefix (requires default_prefix to be set)
registry = ResourceRegistry(default_prefix="lucide")
content = registry.get_resource("lightbulb")  # Resolves as "lucide:lightbulb"
```

## Basic Usage

### Getting Resources

```python
from justmyresource import ResourceRegistry

registry = ResourceRegistry()

# Get resource with fully qualified name (always unique)
content = registry.get_resource("acme-icons/lucide:lightbulb")

# Get resource with short pack name (works if unique)
content = registry.get_resource("lucide:lightbulb")

# Get resource without prefix (requires default_prefix to be set)
registry = ResourceRegistry(default_prefix="lucide")
content = registry.get_resource("lightbulb")  # Resolves as "lucide:lightbulb"

# Access resource data
if content.content_type == "image/svg+xml":
    svg_text = content.text  # UTF-8 decoded string
elif content.content_type == "image/png":
    png_bytes = content.data  # Raw bytes
```

### Listing Resources

```python
# List all resources from all packs
for resource_info in registry.list_resources():
    print(f"{resource_info.pack}:{resource_info.name} ({resource_info.content_type})")
    # pack is qualified name (e.g., "acme-icons/lucide")

# List resources from a specific pack (qualified or short name)
for resource_info in registry.list_resources(pack="acme-icons/lucide"):
    print(resource_info.name)
for resource_info in registry.list_resources(pack="lucide"):
    print(resource_info.name)

# List registered packs (returns qualified names)
for qualified_name in registry.list_packs():
    print(qualified_name)  # e.g., "acme-icons/lucide"
```

## Command-Line Interface

JustMyResource includes a CLI tool for discovering, inspecting, and extracting resources from the command line.

### Installation

The CLI is automatically available after installing justmyresource:

```bash
pip install justmyresource
justmyresource --help
```

### Commands

#### List Resources

List all available resources with optional filtering:

```bash
# List all resources from all packs
justmyresource list

# List resources from a specific pack
justmyresource list --pack lucide

# Filter by glob pattern
justmyresource list --filter "arrow-*"

# Show pack and content type information
justmyresource list --verbose

# JSON output
justmyresource list --json
```

#### Get Resource (Metadata-First)

Inspect resource metadata or extract to file/stdout:

```bash
# Show metadata only (default - safe for binary resources)
justmyresource get lucide:lightbulb

# Output to stdout (for piping)
justmyresource get lucide:lightbulb -o -

# Save to file
justmyresource get lucide:lightbulb -o icon.svg

# JSON output
justmyresource get lucide:lightbulb --json
```

The default behavior shows metadata (size, content-type, pack info) without outputting binary data to the terminal, preventing accidental terminal corruption.

#### List Resource Packs

List all registered resource packs:

```bash
# Simple list
justmyresource packs

# Detailed information (prefixes, aliases, collisions)
justmyresource packs --verbose

# JSON output
justmyresource packs --json
```

#### Resource Information

Show detailed information about a specific resource:

```bash
# Detailed resource information
justmyresource info lucide:lightbulb

# JSON output
justmyresource info lucide:lightbulb --json
```

### Global Options

All commands support these global options:

- `--json`: Output in JSON format
- `--blocklist <packs>`: Comma-separated list of pack names to block
- `--prefix-map <mappings>`: Override prefix mappings (format: `"alias1=dist1/pack1,alias2=dist2/pack2"`)
- `--default-prefix <prefix>`: Set default prefix for bare-name lookups

### Examples

```bash
# Discover available icon packs
justmyresource packs

# Find all arrow icons
justmyresource list --filter "*arrow*"

# Inspect a specific icon
justmyresource get lucide:arrow-right

# Extract icon to file
justmyresource get lucide:arrow-right -o arrow.svg

# Use with default prefix
justmyresource --default-prefix lucide get lightbulb

# Pipe SVG to another tool
justmyresource get lucide:lightbulb -o - | grep "path"
```

### Blocking Resource Packs

```python
# Block specific packs (accepts short or qualified names)
registry = ResourceRegistry(blocklist={"broken-pack", "acme-icons/lucide"})

# Block via environment variable
# RESOURCE_DISCOVERY_BLOCKLIST="broken-pack,acme-icons/lucide" python app.py
```

### Handling Prefix Collisions

When multiple packs claim the same prefix, the registry emits warnings and marks the prefix as ambiguous. No winner is picked—you must use qualified names or `prefix_map` to resolve:

```python
import warnings

# Filter collision warnings if desired
warnings.filterwarnings("ignore", category=PrefixCollisionWarning)

registry = ResourceRegistry()

# Both packs remain accessible via qualified names
content1 = registry.get_resource("acme-icons/lucide:lightbulb")
content2 = registry.get_resource("cool-icons/lucide:lightbulb")

# Short name raises error (ambiguous):
# registry.get_resource("lucide:lightbulb")  # ValueError: ambiguous

# Inspect collisions
collisions = registry.get_prefix_collisions()
# {"lucide": ["acme-icons/lucide", "cool-icons/lucide"]}
```

### Custom Prefix Mapping

Override prefix mappings to resolve collisions or add custom aliases:

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

# Inspect current mappings
prefix_map = registry.get_prefix_map()
# {"icons": "acme-icons/lucide", "mi": "material-icons/core", ...}
```

## Creating Resource Packs

Resource packs can be registered via Python EntryPoints. This allows applications to bundle resources or third-party packages to provide resources.

### First-Party Resource Pack (Application's Own Resources)

```python
# myapp/resources.py
from collections.abc import Iterator
from pathlib import Path
from importlib.resources import files
from justmyresource.types import ResourceContent, ResourcePack

class MyAppResourcePack:
    """Resource pack for application's bundled resources."""
    
    def __init__(self):
        package = files("myapp.resources")
        self._base_path = Path(str(package))
    
    def get_resource(self, name: str) -> ResourceContent:
        """Get resource from bundled files."""
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
        return ["myapp"]  # Optional aliases (pack name is auto-registered)

# myapp/__init__.py
def get_resource_provider():
    """Entry point factory for application's bundled resources."""
    from myapp.resources import MyAppResourcePack
    return MyAppResourcePack()
```

```toml
# pyproject.toml
[project.entry-points."justmyresource.packs"]
"myapp-resources" = "myapp:get_resource_provider"
```

### Third-Party Resource Pack

```python
# my_resource_pack/__init__.py
from my_resource_pack.provider import MyResourcePack

def get_resource_provider():
    """Entry point factory for resource pack."""
    return MyResourcePack()
```

### Using ZippedResourcePack Helper

For packs that bundle resources in a zip file, use the provided helper class:

```python
# my_icon_pack/__init__.py
from justmyresource.pack_utils import ZippedResourcePack

class MyIconPack(ZippedResourcePack):
    def __init__(self):
        super().__init__(
            package_name="my_icon_pack",
            archive_name="icons.zip",
            default_content_type="image/svg+xml",
            prefixes=["myicons"]
        )

def get_resource_provider():
    return MyIconPack()
```

This provides zip reading, caching, manifest support, and error handling out of the box.

## Architecture

JustMyResource follows a unified "Resource Pack" architecture where all resource sources implement the same `ResourcePack` protocol. This ensures:

- **Consistency**: All resources are discovered and resolved the same way
- **Extensibility**: New resource sources can be added via EntryPoints
- **Flat Pack Model**: All packs are equal; uniquely identified by their FQN (dist/pack)

See `docs/architecture.md` for detailed architecture documentation.

## ResourceContent Type

Resources are returned as `ResourceContent` objects:

```python
@dataclass(frozen=True, slots=True)
class ResourceContent:
    data: bytes                    # Raw resource bytes
    content_type: str              # MIME type: "image/svg+xml", "image/png", etc.
    encoding: str | None = None    # Encoding for text resources (e.g., "utf-8")
    metadata: dict[str, Any] | None = None  # Optional pack-specific metadata
    
    @property
    def text(self) -> str:
        """Decode data as text (raises if encoding is None)."""
        ...
```

This wrapper allows consumers to:
- Branch on `content_type` to handle different resource types
- Access text content via `.text` property for text-based resources
- Access pack-specific metadata via `.metadata` dict
- Handle mixed-format packs (e.g., a samples pack with both SVG and PNG)

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/kws/justmyresource.git
cd justmyresource

# Install with development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run tests with coverage
pytest

# Run with coverage report
pytest --cov=justmyresource --cov-report=html
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/
```

## Requirements

- Python 3.10+
- No required dependencies (core library)
- Resource packs may have their own dependencies

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read the architecture documentation in `docs/architecture.md` and follow the project philosophy outlined in `AGENTS.md`.

