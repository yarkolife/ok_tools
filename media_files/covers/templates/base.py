"""BaseCover: the universal fallback layout.

Layers (bottom to top): background frame -> bottom gradient -> accent badge
(category) -> title -> author/subtitle -> logo.
"""

import logging

from PIL import ImageDraw

from media_files.covers import renderer
from media_files.covers import variations
from media_files.covers.config import CoverConfig
from media_files.covers.data import CoverData

logger = logging.getLogger('django')


class BaseCover:
    """Universal cover template used as the default fallback."""

    name = 'base'

    # Background treatments cycled deterministically per video for variety.
    BACKGROUND_STYLES = ('bottom', 'bottom_left', 'cinematic')

    def render(self, background, data: CoverData, config: CoverConfig, theme=None):
        """Compose and return the final RGB cover image."""
        width, height = config.size
        accent = renderer.themed_accent(config, data, theme)

        # Darken parts of the frame so text stays readable; the exact treatment
        # is picked deterministically per video so neighbors look different
        # while one video's cover stays stable across regenerations.
        style = renderer.themed_background_style(
            theme, variations.pick(data.number, self.BACKGROUND_STYLES))
        image = renderer.apply_background_style(background, style)
        draw = ImageDraw.Draw(image)

        margin = 56
        content_w = width - 2 * margin
        y = height - margin

        # --- Author / subtitle (bottom-most line) ---
        secondary = data.author or data.subtitle
        if secondary:
            font = renderer.load_font(config.body_font_path, 34)
            _, line_h = draw.textbbox((0, 0), 'Ag', font=font)[2:]
            y -= line_h
            renderer.draw_text_with_stroke(
                draw, (margin, y), secondary, font,
                fill=(235, 235, 235), stroke_width=2)
            y -= 16

        # --- Title (wrapped, auto-fit) ---
        title = data.title or ''
        if title:
            font, lines = renderer.fit_text(
                draw, title, config.title_font_path,
                max_width=content_w, max_height=int(height * 0.4),
                max_size=84, min_size=40, max_lines=3)
            line_h = draw.textbbox((0, 0), 'Ag', font=font)[3]
            block_h = int(line_h * 1.18)
            for line in reversed(lines):
                y -= block_h
                renderer.draw_text_with_stroke(
                    draw, (margin, y), line, font,
                    fill=(255, 255, 255), stroke_width=3)
            y -= 18

        # --- Category badge (above the title) ---
        if data.category:
            badge_font = renderer.load_font(config.title_font_path, 26)
            label = data.category.upper()
            _, bh = draw.textbbox((0, 0), label, font=badge_font)[2:]
            y -= (bh + 24)
            renderer.accent_badge(draw, (margin, y), label, badge_font, accent)

        # --- Logo (top-right) ---
        image = renderer.paste_logo(image, config.logo_path)

        return image.convert('RGB')
