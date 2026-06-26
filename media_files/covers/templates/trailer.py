"""TrailerCover: cinematic layout for trailers / teasers.

Darker, moodier treatment with a vertical "TRAILER" label and a play glyph,
so teasers stand out from regular episodes at a glance.
"""

import logging

from PIL import Image, ImageDraw

from media_files.covers import renderer
from media_files.covers.config import CoverConfig
from media_files.covers.data import CoverData

logger = logging.getLogger('django')


class TrailerCover:
    """Cinematic template for trailers/teasers."""

    name = 'trailer'

    def _vertical_label(self, text, font, fill):
        """Render ``text`` rotated 90° (reading bottom-to-top) as RGBA."""
        tmp = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        left, top, right, bottom = d.textbbox((0, 0), text, font=font)
        w, h = right - left, bottom - top
        label = Image.new('RGBA', (w + 8, h + 8), (0, 0, 0, 0))
        ImageDraw.Draw(label).text((4 - left, 4 - top), text, font=font, fill=fill)
        return label.rotate(90, expand=True)

    def render(self, background, data: CoverData, config: CoverConfig, theme=None):
        """Compose and return the final RGB cover image."""
        width, height = config.size
        accent = renderer.themed_accent(config, data, theme)

        style = renderer.themed_background_style(theme, 'cinematic')
        image = renderer.apply_background_style(background, style)

        # Accent bar down the left edge.
        bar_w = 14
        bar = Image.new('RGBA', (bar_w, height), accent + (255,))
        image.alpha_composite(bar, (0, 0))

        draw = ImageDraw.Draw(image)
        margin = 64

        # Vertical "TRAILER" label next to the bar.
        label_font = renderer.load_font(config.title_font_path, 40)
        label = self._vertical_label('TRAILER', label_font, (255, 255, 255, 235))
        image.alpha_composite(label, (bar_w + 14, (height - label.size[1]) // 2))

        draw = ImageDraw.Draw(image)
        left_pad = bar_w + 14 + label.size[0] + 30
        content_w = width - left_pad - margin
        y = height - margin

        # Author / subtitle.
        secondary = data.author or data.subtitle
        if secondary:
            font = renderer.load_font(config.body_font_path, 32)
            line_h = draw.textbbox((0, 0), 'Ag', font=font)[3]
            y -= line_h
            renderer.draw_text_with_stroke(
                draw, (left_pad, y), secondary, font,
                fill=(230, 230, 230), stroke_width=2)
            y -= 16

        # Title.
        if data.title:
            font, lines = renderer.fit_text(
                draw, data.title, config.title_font_path,
                max_width=content_w, max_height=int(height * 0.42),
                max_size=88, min_size=40, max_lines=3)
            line_h = draw.textbbox((0, 0), 'Ag', font=font)[3]
            block_h = int(line_h * 1.18)
            for line in reversed(lines):
                y -= block_h
                renderer.draw_text_with_stroke(
                    draw, (left_pad, y), line, font,
                    fill=(255, 255, 255), stroke_width=3)

        image = renderer.paste_logo(image, config.logo_path)
        return image.convert('RGB')
