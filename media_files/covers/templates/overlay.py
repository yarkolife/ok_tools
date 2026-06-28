"""OverlayCover: composes an uploadable graphic overlay over the frame.

Unlike the code-defined templates, the visual design comes from an admin-
uploaded ``CoverOverlay`` (PNG/SVG). Text is drawn into the overlay's
configured ``text_area`` so it never lands on the artwork.
"""

import logging

from PIL import Image, ImageDraw

from media_files.covers import overlays as overlay_utils
from media_files.covers import renderer
from media_files.covers.config import CoverConfig
from media_files.covers.data import CoverData

logger = logging.getLogger('django')


class OverlayCover:
    """Renders a cover from an uploaded graphic overlay instance."""

    name = 'overlay'

    def __init__(self, overlay):
        """``overlay`` is a media_files.models.CoverOverlay instance."""
        self.overlay = overlay

    def _text_box(self, config):
        """Return the (x, y, w, h, align, color) text box, with defaults."""
        width, height = config.size
        area = self.overlay.text_area or {}
        x = int(area.get('x', 56))
        h = int(area.get('h', 180))
        y = int(area.get('y', height - h - 70))
        w = int(area.get('w', width - 2 * x))
        align = area.get('align', 'left')
        color = area.get('color', '#FFFFFF')
        return x, y, w, h, align, color

    def _title_layout(self, height, has_secondary):
        """Return title layout limits adapted to the selected text box."""
        reserved = 36 if has_secondary else 0
        title_height = max(80, height - reserved)
        max_lines = max(3, min(14, title_height // 30))
        max_size = max(72, min(112, title_height // 3))
        return title_height, max_lines, max_size

    @staticmethod
    def _line_height(draw, font, stroke):
        """Return the actual rendered line height including stroke."""
        box = draw.textbbox((0, 0), 'Ag', font=font, stroke_width=stroke)
        return box[3] - box[1]

    def _fit_text_block(self, draw, title, secondary, config, width, height, stroke):
        """Fit title and secondary text into the exact selected text box."""
        _, max_lines, max_size = self._title_layout(height, bool(secondary))
        size = max_size
        while size >= 8:
            font = renderer.load_font(config.title_font_path, size)
            lines = renderer._wrap_text(draw, title, font, width)
            if len(lines) > max_lines:
                size -= 2
                continue
            if any(
                draw.textbbox((0, 0), line, font=font, stroke_width=stroke)[2] > width
                for line in lines
            ):
                size -= 2
                continue

            line_h = self._line_height(draw, font, stroke)
            line_step = max(1, int(line_h * 1.12))
            block_h = line_h + max(0, len(lines) - 1) * line_step
            sfont = None
            if secondary:
                sfont_size = max(8, min(30, int(size * 0.45)))
                sfont = renderer.load_font(config.body_font_path, sfont_size)
                sbox = draw.textbbox((0, 0), secondary, font=sfont,
                                     stroke_width=stroke)
                block_h += 6 + (sbox[3] - sbox[1])
                if sbox[2] - sbox[0] > width:
                    size -= 2
                    continue

            if block_h <= height:
                return font, lines, line_step, sfont
            size -= 2

        font = renderer.load_font(config.title_font_path, 8)
        return font, renderer._wrap_text(draw, title, font, width), (
            max(1, int(self._line_height(draw, font, stroke) * 1.12))), None

    def render(self, background, data: CoverData, config: CoverConfig, theme=None):
        """Compose and return the final RGB cover image."""
        width, height = config.size

        # 1. Base layer: video frame (optionally darkened) or a solid canvas.
        if self.overlay.use_video_frame and background is not None:
            if self.overlay.darken_frame:
                image = renderer.bottom_gradient(background, height_frac=0.6, max_alpha=210)
            else:
                image = background.convert('RGBA')
        else:
            image = Image.new('RGBA', (width, height), (255, 255, 255, 255))

        # 2. Graphic overlay (PNG/SVG) on top.
        overlay_img = overlay_utils.load_overlay_image(
            self.overlay.image.path, size=(width, height))
        if overlay_img is not None:
            image = overlay_utils.composite_overlay(image, overlay_img)

        # 3. Text into the configured area.
        draw = ImageDraw.Draw(image)
        x, y, w, h, align, color = self._text_box(config)
        fill = renderer.hex_to_rgb(color)
        # Light text gets a stroke for legibility; dark text none.
        stroke = 3 if sum(fill) > 380 else 0

        if data.title and getattr(self.overlay, 'draw_title', True):
            secondary = data.author or data.subtitle
            font, lines, line_step, sfont = self._fit_text_block(
                draw, data.title, secondary, config, w, h, stroke)
            ty = y
            for line in lines:
                tx = x
                if align == 'center':
                    lw = draw.textbbox(
                        (0, 0), line, font=font, stroke_width=stroke)[2]
                    tx = x + (w - lw) // 2
                renderer.draw_text_with_stroke(
                    draw, (tx, ty), line, font, fill=fill,
                    stroke_width=stroke)
                ty += line_step

            if secondary:
                sfont = sfont or renderer.load_font(config.body_font_path, 14)
                sx = x
                if align == 'center':
                    sw = draw.textbbox(
                        (0, 0), secondary, font=sfont,
                        stroke_width=stroke)[2]
                    sx = x + (w - sw) // 2
                renderer.draw_text_with_stroke(
                    draw, (sx, ty + 6), secondary, sfont, fill=fill,
                    stroke_width=stroke)

        # 4. Logo (unless the artwork already carries branding).
        if self.overlay.draw_logo:
            area = self.overlay.logo_area or {}
            if area.get('w'):
                image = renderer.paste_logo_at(
                    image, config.logo_path,
                    area.get('x', width - int(area['w']) - 40),
                    area.get('y', 40), area['w'])
            else:
                image = renderer.paste_logo(image, config.logo_path)

        return image.convert('RGB')
