"""Pillow rendering helpers for cover composition."""

import logging

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger('django')


def hex_to_rgb(value: str) -> tuple:
    """Convert ``#RRGGBB`` (or ``RRGGBB``) to an (r, g, b) tuple."""
    value = (value or '').lstrip('#')
    if len(value) != 6:
        return (230, 0, 126)  # sane magenta fallback
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def themed_accent(config, data, theme) -> tuple:
    """Return the accent RGB, honoring a theme ``accent`` override."""
    if theme and theme.get('accent'):
        return hex_to_rgb(theme['accent'])
    return hex_to_rgb(config.accent_for_category(data.category))


def themed_background_style(theme, default_style: str) -> str:
    """Return the background style, honoring a theme override."""
    if theme and theme.get('background_style'):
        return theme['background_style']
    return default_style


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font, falling back to Pillow's default on failure."""
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        logger.warning('Cover: could not load font %s; using default.', path)
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple:
    """Return (width, height) of a single line of text."""
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _wrap_text(draw, text, font, max_width) -> list:
    """Greedy word-wrap ``text`` to fit ``max_width`` at the given font."""
    words = text.split()
    if not words:
        return []

    def chunks_for_word(word):
        if _text_size(draw, word, font)[0] <= max_width:
            return [word]
        chunks, current = [], ''
        for char in word:
            candidate = current + char
            if current and _text_size(draw, candidate, font)[0] > max_width:
                chunks.append(current)
                current = char
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    lines, current = [], ''
    for word in words:
        for chunk in chunks_for_word(word):
            candidate = chunk if not current else f'{current} {chunk}'
            if not current or _text_size(draw, candidate, font)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = chunk
    if current:
        lines.append(current)
    return lines


def fit_text(draw, text, font_path, max_width, max_height, max_size,
             min_size=18, max_lines=3):
    """Shrink font until wrapped ``text`` fits a box; return (font, lines).

    Tries decreasing point sizes until the wrapped text fits both within
    ``max_width`` per line and ``max_height`` total, capped at ``max_lines``.
    """
    size = max_size
    while size >= min_size:
        font = load_font(font_path, size)
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            if any(_text_size(draw, line, font)[0] > max_width for line in lines):
                size -= 4
                continue
            line_h = _text_size(draw, 'Ag', font)[1]
            total_h = int(line_h * 1.2 * len(lines))
            if total_h <= max_height:
                return font, lines
        size -= 4
    font = load_font(font_path, min_size)
    return font, _wrap_text(draw, text, font, max_width)[:max_lines]


def draw_text_with_stroke(draw, position, text, font, fill=(255, 255, 255),
                          stroke_fill=(0, 0, 0), stroke_width=2):
    """Draw text with an outline for readability over any frame."""
    draw.text(position, text, font=font, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill)


def bottom_gradient(image: Image.Image, height_frac=0.55, max_alpha=210,
                    color=(0, 0, 0)) -> Image.Image:
    """Overlay a transparent->opaque gradient on the lower part of the image."""
    width, height = image.size
    grad_h = int(height * height_frac)
    gradient = Image.new('L', (1, grad_h), color=0)
    for y in range(grad_h):
        gradient.putpixel((0, y), int(max_alpha * (y / max(grad_h - 1, 1))))
    alpha = gradient.resize((width, grad_h))
    overlay = Image.new('RGBA', (width, grad_h), color + (0,))
    overlay.putalpha(alpha)
    base = image.convert('RGBA')
    base.alpha_composite(overlay, (0, height - grad_h))
    return base


def left_gradient(image: Image.Image, width_frac=0.6, max_alpha=190,
                  color=(0, 0, 0)) -> Image.Image:
    """Overlay a left->right opaque->transparent gradient (a side scrim).

    Useful when the subject sits centered/right (e.g. portrait interviews) and
    the text column on the left needs a readable backing.
    """
    width, height = image.size
    grad_w = int(width * width_frac)
    gradient = Image.new('L', (grad_w, 1), color=0)
    for x in range(grad_w):
        gradient.putpixel((x, 0), int(max_alpha * (1 - x / max(grad_w - 1, 1))))
    alpha = gradient.resize((grad_w, height))
    overlay = Image.new('RGBA', (grad_w, height), color + (0,))
    overlay.putalpha(alpha)
    base = image.convert('RGBA')
    base.alpha_composite(overlay, (0, 0))
    return base


def apply_background_style(image: Image.Image, style: str) -> Image.Image:
    """Apply a named background treatment, returning an RGBA image.

    Styles:
        'bottom'      - bottom gradient only (default).
        'bottom_left' - bottom gradient + left side scrim (portrait-friendly).
        'cinematic'   - taller, denser bottom gradient for a moodier look.
    """
    if style == 'bottom_left':
        image = bottom_gradient(image, height_frac=0.66, max_alpha=225)
        return left_gradient(image, width_frac=0.58, max_alpha=175)
    if style == 'cinematic':
        return bottom_gradient(image, height_frac=0.85, max_alpha=245)
    return bottom_gradient(image, height_frac=0.72, max_alpha=235)


def paste_logo(image: Image.Image, logo_path: str, margin=40,
               max_width_frac=0.20) -> Image.Image:
    """Paste a logo into the top-right corner, scaled to a max width."""
    try:
        logo = Image.open(logo_path).convert('RGBA')
    except Exception:
        logger.warning('Cover: could not load logo %s', logo_path)
        return image

    max_w = int(image.size[0] * max_width_frac)
    if logo.size[0] > max_w:
        ratio = max_w / logo.size[0]
        logo = logo.resize((max_w, int(logo.size[1] * ratio)), Image.LANCZOS)

    base = image.convert('RGBA')
    x = base.size[0] - logo.size[0] - margin
    base.alpha_composite(logo, (x, margin))
    return base


def paste_logo_at(image: Image.Image, logo_path: str, x: int, y: int, width: int):
    """Paste a logo at an exact position, scaled to ``width`` (keeps aspect)."""
    try:
        logo = Image.open(logo_path).convert('RGBA')
    except Exception:
        logger.warning('Cover: could not load logo %s', logo_path)
        return image
    width = max(20, int(width))
    ratio = width / logo.size[0]
    logo = logo.resize((width, int(logo.size[1] * ratio)), Image.LANCZOS)
    base = image.convert('RGBA')
    base.alpha_composite(logo, (int(x), int(y)))
    return base


def accent_badge(draw, position, text, font, bg_color, text_color=(255, 255, 255),
                 pad_x=20, pad_y=12):
    """Draw a filled rounded badge with a centered label; return its box.

    Sizes the badge from the text's actual bounding box (accounting for the
    font's top/bottom bearing) and centers the label with anchor='mm', so the
    text never drifts below the pill.
    """
    x, y = position
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    box_w = tw + 2 * pad_x
    box_h = th + 2 * pad_y
    box = (x, y, x + box_w, y + box_h)
    radius = box_h // 2
    draw.rounded_rectangle(box, radius=radius, fill=bg_color)
    draw.text((x + box_w / 2, y + box_h / 2), text, font=font,
              fill=text_color, anchor='mm')
    return box
