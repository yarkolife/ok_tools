"""Branding / configuration for cover generation.

Reads installation-specific settings from :class:`MediaFilesConfig` (singleton)
with sensible bundled fallbacks, so the same code serves any channel.
"""

from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger('django')

# Bundled assets shipped with the project (used as fallbacks).
ASSETS_DIR = Path(__file__).resolve().parent.parent / 'video_presets' / 'assets'
FONTS_DIR = ASSETS_DIR / 'fonts'

DEFAULT_LOGO_PATH = ASSETS_DIR / 'logo.png'
DEFAULT_TITLE_FONT = FONTS_DIR / 'Roboto-Bold.ttf'
DEFAULT_BODY_FONT = FONTS_DIR / 'Roboto-Regular.ttf'

COVER_SIZE = (1280, 720)

# Fallback accent palette, cycled deterministically per category when no
# explicit color is configured.
DEFAULT_PALETTE = [
    '#E6007E',  # magenta
    '#0098D8',  # blue
    '#F39200',  # orange
    '#3AAA35',  # green
    '#9B2FAE',  # purple
    '#E2001A',  # red
    '#00A19A',  # teal
]

# Built-in accent colors for the common installation categories. Used when no
# explicit override is configured; unknown categories fall back to the palette.
BUILTIN_CATEGORY_COLORS = {
    'Kulturelles und soziales Engagement': '#E6007E',
    'Gastbeitrag': '#00A19A',
    'Politisch orientiertes Bürgerfernsehen': '#9B2FAE',
    'Familie und Freizeit': '#F39200',
    'Medienpädagogische Produktionen': '#0098D8',
    'Heimatdoku': '#3AAA35',
    'Sonstiges': '#6C7A89',
    'Experimentierfeld "Video"': '#E2001A',
    'Orientierungshilfen': '#1B998B',
    'Kurzfilm': '#C0392B',
    'Trailer': '#FF6B00',
}

# Built-in category -> template mapping (defaults for this installation).
# Any channel can override via MediaFilesConfig.cover_template_rules. Unknown
# categories fall back to BaseCover, so the system stays channel-agnostic.
BUILTIN_CATEGORY_TEMPLATES = {
    'Trailer': 'trailer',
}


@dataclass
class CoverConfig:
    """Resolved cover-generation settings for the current installation."""

    enabled: bool = False
    logo_path: str = str(DEFAULT_LOGO_PATH)
    title_font_path: str = str(DEFAULT_TITLE_FONT)
    body_font_path: str = str(DEFAULT_BODY_FONT)
    category_colors: dict = field(default_factory=dict)
    category_templates: dict = field(default_factory=dict)
    output_dir: str = ''
    size: tuple = COVER_SIZE

    def accent_for_category(self, category_name: str) -> str:
        """Return an accent color hex for a category name.

        Priority: explicit config override -> built-in category color ->
        stable color from the default palette (by category name hash).
        """
        if category_name and category_name in self.category_colors:
            return self.category_colors[category_name]
        if category_name and category_name in BUILTIN_CATEGORY_COLORS:
            return BUILTIN_CATEGORY_COLORS[category_name]
        key = category_name or ''
        index = sum(ord(c) for c in key) % len(DEFAULT_PALETTE)
        return DEFAULT_PALETTE[index]

    def template_for_category(self, category_name: str) -> str:
        """Return the template name for a category.

        Priority: explicit config override -> built-in mapping -> 'base'.
        """
        if category_name and category_name in self.category_templates:
            return self.category_templates[category_name]
        return BUILTIN_CATEGORY_TEMPLATES.get(category_name, 'base')


def _first_existing(*candidates) -> str:
    """Return the first candidate path that exists, else the last one."""
    last = ''
    for candidate in candidates:
        if not candidate:
            continue
        last = str(candidate)
        if Path(candidate).exists():
            return str(candidate)
    return last


def _resolve_output_dir(cfg) -> str:
    """Resolve the cover output directory.

    Priority: selected storage location (+ optional subdir) -> manual path ->
    austausch export thumbnail storage path.
    """
    if cfg.cover_output_storage_id:
        base = (cfg.cover_output_storage.path or '').strip()
        subdir = (cfg.cover_output_subdir or '').strip().strip('/')
        if base:
            return str(Path(base) / subdir) if subdir else base

    manual = (cfg.cover_output_dir or '').strip()
    if manual:
        return manual

    # Fall back to the austausch export hand-off directory.
    try:
        from austausch.models import ExchangeConfig
        return (ExchangeConfig.get_config().thumbnail_storage_path or '').strip()
    except Exception:
        logger.warning('Could not read austausch thumbnail_storage_path for covers.')
        return ''


def get_cover_config() -> CoverConfig:
    """Build a :class:`CoverConfig` from the MediaFilesConfig singleton."""
    from media_files.models import MediaFilesConfig

    cfg = MediaFilesConfig.get_config()
    output_dir = _resolve_output_dir(cfg)

    return CoverConfig(
        enabled=bool(cfg.cover_enabled),
        logo_path=_first_existing(cfg.cover_logo_path, DEFAULT_LOGO_PATH),
        title_font_path=_first_existing(cfg.cover_title_font_path, DEFAULT_TITLE_FONT),
        body_font_path=_first_existing(cfg.cover_body_font_path, DEFAULT_BODY_FONT),
        category_colors=dict(cfg.cover_category_colors or {}),
        category_templates=dict(getattr(cfg, 'cover_template_rules', None) or {}),
        output_dir=output_dir,
    )
