"""Tests for SVG to PNG rendering functionality."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from justmyresource.render import AVAILABLE, svg_to_png
from justmyresource.types import ResourceContent
from tests.conftest import create_test_resource_content

# Simple valid SVG for testing
SIMPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="red"/>
</svg>"""


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_produces_valid_png():
    """Test that svg_to_png produces valid PNG bytes."""
    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content)

    # PNG files start with magic bytes
    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.content_type == "image/png"
    assert png_content.encoding is None  # PNG is binary
    assert png_content.metadata is not None
    assert png_content.metadata["rendered_from"] == "svg"


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_width():
    """Test svg_to_png with width parameter."""
    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content, width=64)

    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.metadata is not None
    assert png_content.metadata["render_width"] == 64


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_height():
    """Test svg_to_png with height parameter."""
    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content, height=128)

    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.metadata is not None
    assert png_content.metadata["render_height"] == 128


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_scale():
    """Test svg_to_png with scale parameter."""
    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content, scale=2.0)

    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.metadata is not None
    assert png_content.metadata["render_scale"] == 2.0


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_preserves_metadata():
    """Test that svg_to_png preserves original metadata."""
    from justmyresource.types import ResourceContent

    svg_content = ResourceContent(
        data=SIMPLE_SVG.encode("utf-8"),
        content_type="image/svg+xml",
        encoding="utf-8",
        metadata={"original_key": "original_value", "width": 24},
    )

    png_content = svg_to_png(svg_content)

    assert png_content.metadata is not None
    assert png_content.metadata["original_key"] == "original_value"
    assert png_content.metadata["width"] == 24
    assert png_content.metadata["rendered_from"] == "svg"


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_all_parameters():
    """Test svg_to_png with width, height, and scale."""
    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content, width=64, height=64, scale=1.5)

    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.metadata is not None
    assert png_content.metadata["render_width"] == 64
    assert png_content.metadata["render_height"] == 64
    assert png_content.metadata["render_scale"] == 1.5


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_octet_stream_content_type():
    """Test that svg_to_png accepts SVG data even with incorrect content_type."""
    # Some packs return SVG as application/octet-stream
    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="application/octet-stream",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content)

    # Should still render successfully by detecting SVG from data
    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.content_type == "image/png"


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_whitespace_before_svg():
    """Test that svg_to_png handles SVG data with leading whitespace."""
    svg_with_whitespace = b"  \n  " + SIMPLE_SVG.encode("utf-8")
    svg_content = create_test_resource_content(
        data=svg_with_whitespace,
        content_type="application/octet-stream",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content)

    # Should still render successfully by detecting SVG from data after stripping whitespace
    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.content_type == "image/png"


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_svg_to_png_with_xml_declaration():
    """Test that svg_to_png handles SVG data with XML declaration."""
    svg_with_xml = b'<?xml version="1.0"?>\n' + SIMPLE_SVG.encode("utf-8")
    svg_content = create_test_resource_content(
        data=svg_with_xml,
        content_type="application/octet-stream",
        encoding="utf-8",
    )

    png_content = svg_to_png(svg_content)

    # Should still render successfully by detecting SVG from XML declaration
    assert png_content.data.startswith(b"\x89PNG")
    assert png_content.content_type == "image/png"


def test_svg_to_png_raises_value_error_for_non_svg():
    """Test that svg_to_png raises ValueError for non-SVG content."""
    png_content = create_test_resource_content(
        data=b"\x89PNG",
        content_type="image/png",
    )

    if AVAILABLE:
        with pytest.raises(ValueError, match="Resource must be SVG"):
            svg_to_png(png_content)
    else:
        # If cairosvg is not available, we get ImportError first
        with pytest.raises(ImportError):
            svg_to_png(png_content)


def test_svg_to_png_raises_import_error_when_unavailable():
    """Test that svg_to_png raises ImportError when cairosvg is not installed."""
    if AVAILABLE:
        pytest.skip("cairosvg is installed, cannot test ImportError")

    svg_content = create_test_resource_content(
        data=SIMPLE_SVG,
        content_type="image/svg+xml",
        encoding="utf-8",
    )

    with pytest.raises(ImportError, match="cairosvg is not installed"):
        svg_to_png(svg_content)


def test_available_flag():
    """Test that AVAILABLE flag correctly reflects cairosvg availability."""
    # This test always runs - it just checks the flag is set correctly
    # We can't easily test both states, but we can verify the flag exists
    assert isinstance(AVAILABLE, bool)


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_cli_render_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test the CLI render subcommand end-to-end."""
    from justmyresource.cli import main

    # Create a test SVG file in a mock pack
    test_svg = SIMPLE_SVG
    output_file = tmp_path / "output.png"

    # Mock the registry to return our test SVG
    with patch("justmyresource.cli.ResourceRegistry") as mock_registry_class:
        mock_registry = mock_registry_class.return_value
        mock_registry.discover.return_value = None
        mock_registry.get_resource.return_value = create_test_resource_content(
            data=test_svg,
            content_type="image/svg+xml",
            encoding="utf-8",
        )

        # Run the render command
        sys.argv = [
            "justmyresource",
            "render",
            "test:icon",
            "--output",
            str(output_file),
            "--width",
            "64",
        ]

        result = main()

        # Verify command succeeded
        assert result == 0

        # Verify output file was created and is valid PNG
        assert output_file.exists()
        assert output_file.read_bytes().startswith(b"\x89PNG")

        # Verify registry was called correctly
        mock_registry.discover.assert_called_once()
        mock_registry.get_resource.assert_called_once_with("test:icon")


@pytest.mark.skipif(not AVAILABLE, reason="cairosvg not installed")
def test_cli_render_command_stdout(monkeypatch: pytest.MonkeyPatch):
    """Test the CLI render command with stdout output."""
    from io import BytesIO

    from justmyresource.cli import main

    test_svg = SIMPLE_SVG
    stdout_buffer = BytesIO()

    # Create a mock stdout object with a buffer attribute
    class MockStdout:
        def __init__(self, buffer: BytesIO) -> None:
            self.buffer = buffer

    mock_stdout = MockStdout(stdout_buffer)

    # Replace sys.stdout with our mock
    monkeypatch.setattr("sys.stdout", mock_stdout)

    with patch("justmyresource.cli.ResourceRegistry") as mock_registry_class:
        mock_registry = mock_registry_class.return_value
        mock_registry.discover.return_value = None
        mock_registry.get_resource.return_value = create_test_resource_content(
            data=test_svg,
            content_type="image/svg+xml",
            encoding="utf-8",
        )

        sys.argv = [
            "justmyresource",
            "render",
            "test:icon",
            "--output",
            "-",
        ]

        result = main()

        assert result == 0

        # Verify PNG was written to stdout
        stdout_buffer.seek(0)
        output_data = stdout_buffer.read()
        assert output_data.startswith(b"\x89PNG")

        mock_registry.discover.assert_called_once()
        mock_registry.get_resource.assert_called_once_with("test:icon")

