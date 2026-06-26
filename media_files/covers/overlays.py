"""Loading and compositing uploadable graphic overlays (PNG/SVG)."""

import logging
import os

from PIL import Image

logger = logging.getLogger('django')


def load_overlay_image(path: str, size=(1280, 720)):
    """Load a PNG or SVG overlay as an RGBA image scaled to ``size``.

    SVG is rasterized with cairosvg at the target resolution. Returns ``None``
    if the file is missing or cannot be read.
    """
    if not path or not os.path.isfile(path):
        logger.warning('Cover overlay not found: %s', path)
        return None

    try:
        if path.lower().endswith('.svg'):
            import cairosvg
            png_bytes = cairosvg.svg2png(
                url=path, output_width=size[0], output_height=size[1])
            from io import BytesIO
            image = Image.open(BytesIO(png_bytes)).convert('RGBA')
        else:
            image = Image.open(path).convert('RGBA')
    except Exception:
        logger.exception('Cover: failed to load overlay %s', path)
        return None

    if image.size != size:
        image = image.resize(size, Image.LANCZOS)
    return image


def composite_overlay(base: Image.Image, overlay: Image.Image) -> Image.Image:
    """Alpha-composite ``overlay`` over ``base`` (both sized equally)."""
    base = base.convert('RGBA')
    base.alpha_composite(overlay)
    return base
