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

# Get resource with prefix
content = registry.get_resource("lucide:lightbulb")

# Check content type and use accordingly
if content.content_type == "image/svg+xml":
    svg_text = content.text  # Decode as UTF-8
    # Use SVG text...

# Get resource without prefix (searches by priority)
content = registry.get_resource("logo")
```

## Basic Usage

### Getting Resources

```python
from justmyresource import ResourceRegistry

registry = ResourceRegistry()

# Get resource with prefix (explicit pack)
content = registry.get_resource("lucide:lightbulb")

# Get resource without prefix (searches packs by priority)
content = registry.get_resource("logo")

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

# List resources from a specific pack
for resource_info in registry.list_resources(pack="lucide"):
    print(resource_info.name)

# List registered packs
for pack_name in registry.list_packs():
    print(pack_name)
```

### Blocking Resource Packs

```python
# Block specific packs
registry = ResourceRegistry(blocklist={"broken-pack", "test-pack"})

# Block via environment variable
# RESOURCE_DISCOVERY_BLOCKLIST="broken-pack,test-pack" python app.py
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
    
    def get_priority(self) -> int:
        return 100
    
    def get_name(self) -> str:
        return "myapp-resources"
    
    def get_prefixes(self) -> list[str]:
        return ["myapp"]

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

## Architecture

JustMyResource follows a unified "Resource Pack" architecture where all resource sources implement the same `ResourcePack` protocol. This ensures:

- **Consistency**: All resources are discovered and resolved the same way
- **Extensibility**: New resource sources can be added via EntryPoints
- **Priority**: Resource packs (priority 100) override system resources (priority 0, future)

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

