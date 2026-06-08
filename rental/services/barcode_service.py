"""
Barcode service module for generating barcode SVGs from inventory numbers.

This module provides a service for generating Code 128 barcode SVGs
in-memory from inventory number strings.
"""

from __future__ import annotations

import barcode
from barcode.writer import SVGWriter


class BarcodeService:
    """Service class for barcode generation operations.

    Provides static methods for generating barcode SVGs from inventory numbers
    without writing to disk.
    """

    @staticmethod
    def generate_svg(inventory_number: str) -> str:
        """Generate a Code 128 barcode SVG from an inventory number.

        Args:
            inventory_number: The inventory number string to encode.

        Returns:
            The rendered SVG markup as a string.

        Raises:
            ValueError: If inventory_number is empty or whitespace-only.
        """
        if not inventory_number or not inventory_number.strip():
            raise ValueError("Inventory number must not be empty or whitespace-only.")

        barcode_obj = barcode.get("code128", inventory_number.strip(), writer=SVGWriter())
        svg_bytes = barcode_obj.render()
        return svg_bytes.decode("utf-8")
