"""SVG to PNG rendering utilities using CairoSVG.

This module provides optional rendering functionality. It requires the
`render` optional dependency group to be installed:
    pip install justmyresource[render]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from justmyresource.types import ResourceContent

if TYPE_CHECKING:
    pass

# Try to import cairosvg to determine availability
try:
    import cairosvg  # noqa: F401

    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def svg_to_png(
    resource: ResourceContent,
    width: int | None = None,
    height: int | None = None,
    scale: float | None = None,
) -> ResourceContent:
    """Convert SVG ResourceContent to PNG ResourceContent.

    Args:
        resource: SVG ResourceContent to render. Should have content_type="image/svg+xml",
            but will also accept SVG data even if content_type is incorrectly set
            (e.g., "application/octet-stream").
        width: Optional output width in pixels.
        height: Optional output height in pixels.
        scale: Optional scale factor (e.g., 2.0 for 2x resolution).

    Returns:
        ResourceContent with PNG data and content_type="image/png".

    Raises:
        ImportError: If cairosvg is not installed. Install with:
            pip install justmyresource[render]
        ValueError: If resource is not an SVG (content_type != "image/svg+xml" and
            data does not appear to be SVG).
    """
    if not AVAILABLE:
        raise ImportError(
            "cairosvg is not installed. Install the render optional dependency: "
            "pip install justmyresource[render]"
        )

    # Import here to avoid triggering ImportError at module level
    import cairosvg

    # Validate input is SVG - check content_type or detect from data
    is_svg_content_type = resource.content_type == "image/svg+xml"
    
    # If content_type is not set correctly, check if data looks like SVG
    is_svg_data = False
    if not is_svg_content_type:
        # Check if data starts with SVG indicators (after optional BOM/whitespace)
        data_start = resource.data.lstrip().lower()
        if data_start.startswith(b"<?xml") or data_start.startswith(b"<svg"):
            is_svg_data = True
    
    if not (is_svg_content_type or is_svg_data):
        raise ValueError(
            f"Resource must be SVG (content_type='image/svg+xml' or SVG data), "
            f"got content_type='{resource.content_type}'"
        )

    # Build cairosvg options
    options: dict[str, int | float] = {}
    if width is not None:
        options["output_width"] = width
    if height is not None:
        options["output_height"] = height
    if scale is not None:
        options["scale"] = scale

    # Render SVG to PNG bytes
    png_bytes = cairosvg.svg2png(
        bytestring=resource.data,
        **options,
    )

    # Build metadata preserving original with render info
    metadata = dict(resource.metadata) if resource.metadata else {}
    metadata["rendered_from"] = "svg"
    if width is not None:
        metadata["render_width"] = width
    if height is not None:
        metadata["render_height"] = height
    if scale is not None:
        metadata["render_scale"] = scale

    return ResourceContent(
        data=png_bytes,
        content_type="image/png",
        encoding=None,  # PNG is binary
        metadata=metadata,
    )

