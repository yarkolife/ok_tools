"""JournalCover: layout for recurring series / magazine episodes.

Emphasizes the recurring series name (brand) plus a large episode number so
all episodes of a series share an instantly recognizable look, while the big
number makes neighboring episodes easy to tell apart.
"""

import logging

from PIL import ImageDraw

from media_files.covers import renderer
from media_files.covers.config import CoverConfig
from media_files.covers.data import CoverData

logger = logging.getLogger('django')


class JournalCover:
    """Series/magazine template with a large episode number."""

    name = 'journal'

    def render(self, background, data: CoverData, config: CoverConfig, theme=None):
        """Compose and return the final RGB cover image."""
        width, height = config.size
        accent = renderer.themed_accent(config, data, theme)

        style = renderer.themed_background_style(theme, 'bottom')
        image = renderer.apply_background_style(background, style)
        draw = ImageDraw.Draw(image)

        margin = 56

        # --- Large episode number (bottom-right accent block) ---
        if data.episode_part is not None:
            marker = (data.episode_marker or 'Folge').upper()
            number_text = str(data.episode_part)

            num_font = renderer.load_font(config.title_font_path, 150)
            label_font = renderer.load_font(config.title_font_path, 36)

            nb = draw.textbbox((0, 0), number_text, font=num_font)
            num_w, num_h = nb[2] - nb[0], nb[3] - nb[1]
            lb = draw.textbbox((0, 0), marker, font=label_font)
            label_w, label_h = lb[2] - lb[0], lb[3] - lb[1]

            block_w = max(num_w, label_w)
            x_right = width - margin
            y_num = height - margin - num_h - nb[1]
            # Label sits above the number.
            renderer.draw_text_with_stroke(
                draw, (x_right - label_w, y_num - label_h - 14), marker,
                label_font, fill=accent, stroke_width=2)
            renderer.draw_text_with_stroke(
                draw, (x_right - num_w, y_num - nb[1]), number_text,
                num_font, fill=(255, 255, 255), stroke_width=4)
            if data.episode_total:
                total_font = renderer.load_font(config.body_font_path, 34)
                total_text = f'/ {data.episode_total}'
                renderer.draw_text_with_stroke(
                    draw, (x_right - block_w, height - margin + 4), total_text,
                    total_font, fill=(220, 220, 220), stroke_width=2)
            # Reserve the right column so title text avoids the number.
            content_right = x_right - block_w - 48
        else:
            content_right = width - margin

        content_w = content_right - margin
        y = height - margin

        # --- Author / subtitle ---
        secondary = data.author or data.subtitle
        if secondary:
            font = renderer.load_font(config.body_font_path, 32)
            line_h = draw.textbbox((0, 0), 'Ag', font=font)[3]
            y -= line_h
            renderer.draw_text_with_stroke(
                draw, (margin, y), secondary, font,
                fill=(235, 235, 235), stroke_width=2)
            y -= 16

        # --- Series brand name (the headline for series episodes) ---
        headline = data.series or data.title or ''
        if headline:
            font, lines = renderer.fit_text(
                draw, headline, config.title_font_path,
                max_width=content_w, max_height=int(height * 0.38),
                max_size=78, min_size=38, max_lines=2)
            line_h = draw.textbbox((0, 0), 'Ag', font=font)[3]
            block_h = int(line_h * 1.18)
            for line in reversed(lines):
                y -= block_h
                renderer.draw_text_with_stroke(
                    draw, (margin, y), line, font,
                    fill=(255, 255, 255), stroke_width=3)
            y -= 18

        # --- Category badge ---
        if data.category:
            badge_font = renderer.load_font(config.title_font_path, 26)
            label = data.category.upper()
            bh = draw.textbbox((0, 0), label, font=badge_font)[3]
            y -= (bh + 24)
            renderer.accent_badge(draw, (margin, y), label, badge_font, accent)

        image = renderer.paste_logo(image, config.logo_path)
        return image.convert('RGB')
