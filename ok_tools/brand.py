"""
Brand colour of an installation and the palette derived from it.

One hex colour (``BRAND_COLOR`` in .env) drives the admin (Unfold
``COLORS["primary"]``), the top bar of the pages outside the admin and the
shared tokens in ok_tools/static/ok_tools/css/ok_theme.css.

The palette keeps the hue of the brand colour and uses fixed lightness
steps, so buttons and links stay readable whatever colour is chosen. The
top bar shows the brand colour itself.

Plain Python (no Django imports): settings.py uses it.
"""

from __future__ import annotations
import math
import re


DEFAULT_BRAND_COLOR = "#417690"

# Brand colour of the user interface themes (DASHBOARD_THEME), used when
# BRAND_COLOR is not set. "default" and "dark" keep the admin blue.
THEME_BRAND_COLORS = {
    "vibrant": "#6366f1",
}

# Lightness (OKLCH, %) and chroma factor of each palette step.
_STEPS = {
    "50": (97.4, 0.16),
    "100": (94.4, 0.33),
    "200": (89.0, 0.57),
    "300": (81.0, 0.83),
    "400": (70.5, 1.0),
    "500": (62.0, 1.05),
    "600": (54.0, 1.0),
    "700": (45.6, 0.9),
    "800": (39.0, 0.79),
    "900": (33.0, 0.67),
    "950": (25.0, 0.54),
}
_MAX_CHROMA = 0.16   # keeps generated steps inside sRGB for strong colours

_HEX = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def normalize_hex(value: str | None) -> str | None:
    """'#AbC' / 'aabbcc' -> '#aabbcc'; None for anything else."""
    match = _HEX.match((value or "").strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.lower()


def resolve_brand_color(brand_color: str | None, dashboard_theme: str | None) -> str:
    return (normalize_hex(brand_color)
            or THEME_BRAND_COLORS.get((dashboard_theme or "").strip().lower())
            or DEFAULT_BRAND_COLOR)


# ---- colour math (sRGB <-> OKLab/OKLCH) ----

def _to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(value: str) -> tuple[float, float, float]:
    """Return (L 0..1, C, h degrees)."""
    value = normalize_hex(value) or DEFAULT_BRAND_COLOR
    r, g, b = (_to_linear(int(value[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness, math.hypot(a, b2), math.degrees(math.atan2(b2, a)) % 360


def oklch_to_rgb(lightness: float, chroma: float, hue: float) -> tuple[int, int, int]:
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return tuple(round(_from_linear(x) * 255) for x in (r, g, bl))


def palette(brand: str) -> dict[str, str]:
    """Unfold-style palette 50..950 (CSS oklch() strings) in the brand hue."""
    _lightness, chroma, hue = hex_to_oklch(brand)
    chroma = min(chroma, _MAX_CHROMA)
    return {
        step: f"oklch({lightness:.1f}% {chroma * factor:.3f} {hue:.1f})"
        for step, (lightness, factor) in _STEPS.items()
    }


def palette_rgb(brand: str, step: str) -> tuple[int, int, int]:
    _lightness, chroma, hue = hex_to_oklch(brand)
    lightness, factor = _STEPS[step]
    return oklch_to_rgb(lightness / 100, min(chroma, _MAX_CHROMA) * factor, hue)


def css_variables(brand: str) -> str:
    """:root block for pages that do not get Unfold's injected colours."""
    colors = palette(brand)
    lines = [f"--color-primary-{step}: {value};" for step, value in colors.items()]
    lines.append(f"--ok-brand-bar: {normalize_hex(brand) or DEFAULT_BRAND_COLOR};")
    lines.append("--ok-brand-rgb-light: %d, %d, %d;" % palette_rgb(brand, "600"))
    lines.append("--ok-brand-rgb-dark: %d, %d, %d;" % palette_rgb(brand, "500"))
    return ":root{" + "".join(lines) + "}"
