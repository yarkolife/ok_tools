"""
Tests for BarcodeService in rental application.
"""

import pytest

from rental.services.barcode_service import BarcodeService


class TestBarcodeServiceGenerateSvg:
    """Test cases for BarcodeService.generate_svg static method."""

    def test_generate_svg_valid_inventory_number(self):
        """Test generate_svg returns a string containing SVG/Code128 markup."""
        result = BarcodeService.generate_svg("OK-12345")

        assert isinstance(result, str)
        assert result.startswith("<?xml") or result.startswith("<svg")
        assert "python-barcode" in result or "barcode_group" in result

    def test_generate_svg_empty_string(self):
        """Test generate_svg raises ValueError for empty string."""
        with pytest.raises(ValueError):
            BarcodeService.generate_svg("")

    def test_generate_svg_whitespace_only(self):
        """Test generate_svg raises ValueError for whitespace-only string."""
        with pytest.raises(ValueError):
            BarcodeService.generate_svg("   ")

    def test_generate_svg_returns_valid_svg(self):
        """Test generate_svg returns structurally valid SVG markup."""
        result = BarcodeService.generate_svg("OK-TEST")

        assert isinstance(result, str)
        assert result.startswith("<?xml") or result.startswith("<svg")
        assert result.strip().endswith("</svg>")
        assert "<svg" in result

    def test_generate_svg_different_formats(self):
        """Test generate_svg works with various OK-XXXXX formats."""
        test_values = ["OK-00001", "OK-99999", "OK-ABC-123"]

        for inventory_number in test_values:
            result = BarcodeService.generate_svg(inventory_number)

            assert isinstance(result, str)
            assert "<svg" in result
            assert result.strip().endswith("</svg>")
