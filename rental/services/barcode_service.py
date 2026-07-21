"""
Barcode service module for generating barcode SVGs from inventory numbers.

This module provides a service for generating Code 128 barcode SVGs
in-memory from inventory number strings.
"""

from __future__ import annotations

import barcode
import re
from barcode.writer import SVGWriter


# python-barcode sizes the SVG root in millimetres but writes no viewBox, so
# the drawing keeps its absolute size and CSS width/height would crop rather
# than scale it. Adding a viewBox in user units (1mm = 96/25.4 px) makes the
# label templates able to shrink a barcode into a roll label.
_SVG_ROOT_RE = re.compile(
    r'(<svg\b[^>]*?)width="(?P<w>[\d.]+)mm"\s+height="(?P<h>[\d.]+)mm"'
)
_USER_UNITS_PER_MM = 96 / 25.4


class BarcodeService:
    """Service class for barcode generation operations.

    Provides static methods for generating barcode SVGs from inventory numbers
    without writing to disk.
    """

    @staticmethod
    def generate_svg(inventory_number: str, **writer_options) -> str:
        """Generate a Code 128 barcode SVG from an inventory number.

        Args:
            inventory_number: The inventory number string to encode.
            **writer_options: Options passed to ``SVGWriter`` (``module_width``
                and ``module_height`` in mm, ``quiet_zone``, ``write_text``,
                ``font_size``). Defaults are used when omitted.

        Returns:
            The rendered SVG markup as a string, carrying a ``viewBox`` so it
            scales with the CSS box it is placed in.

        Raises:
            ValueError: If inventory_number is empty or whitespace-only.
        """
        if not inventory_number or not inventory_number.strip():
            raise ValueError("Inventory number must not be empty or whitespace-only.")

        barcode_obj = barcode.get("code128", inventory_number.strip(), writer=SVGWriter())
        svg_bytes = barcode_obj.render(writer_options or None)
        return BarcodeService._add_viewbox(svg_bytes.decode("utf-8"))

    @staticmethod
    def _add_viewbox(svg: str) -> str:
        """Return ``svg`` with a viewBox matching its millimetre dimensions.

        Returns the markup unchanged when the root element does not carry the
        expected mm width/height, so a writer change cannot break rendering.
        """
        match = _SVG_ROOT_RE.search(svg)
        if not match or 'viewBox' in svg:
            return svg
        width = float(match.group('w')) * _USER_UNITS_PER_MM
        height = float(match.group('h')) * _USER_UNITS_PER_MM
        return _SVG_ROOT_RE.sub(
            lambda m: (
                f'{m.group(1)}width="{m.group("w")}mm" height="{m.group("h")}mm" '
                f'viewBox="0 0 {width:.3f} {height:.3f}"'
            ),
            svg,
            count=1,
        )
