"""Template rendering for overlay text."""

from __future__ import annotations

import re
import textwrap
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict

from licenses.models import License
from django.utils.translation import gettext as _


@dataclass(frozen=True)
class TemplateContext:
    """Context used for rendering text templates."""

    license: License
    profile_display: str
    media_authority_name: str
    media_authority_full_name: str
    license_created_year: int
    labels: Dict[str, str]


def build_template_context(license_obj: License) -> TemplateContext:
    """Build a template context from a License instance."""
    from django.conf import settings
    
    profile = license_obj.profile
    media_authority = getattr(profile, "media_authority", None)
    authority_name = getattr(media_authority, "name", "") or ""
    authority_full_name = getattr(media_authority, "full_name", "") or ""
    
    # Get organization name from settings (fallback only if profile has no media_authority)
    organization_name = getattr(settings, 'OK_NAME', 'Offener Kanal Merseburg-Querfurt e.V.')
    
    # Use profile's media authority full_name (Vollständiger Name) if available,
    # otherwise use profile's media authority name (Bürgermedium), 
    # fallback to organization name only if no media_authority exists
    final_full_name = authority_full_name or authority_name or organization_name

    return TemplateContext(
        license=license_obj,
        profile_display=str(profile),
        media_authority_name=authority_name,
        media_authority_full_name=final_full_name,  # Use profile's media authority full_name (Bürgermedium Vollständiger Name)
        license_created_year=int(license_obj.created_at.year),
        labels={
            # Keep msgids in English (project rule) and rely on locale .po for output language.
            "broadcast_responsibility": _("Sendeverantwortung"),
        },
    )


def _clean_text_for_ffmpeg(text: str) -> str:
    """Clean text to remove characters that FFmpeg cannot render properly."""
    if not text:
        return ""
    # Normalize Unicode (NFD -> NFC) to combine diacritics properly
    text = unicodedata.normalize('NFC', text)
    # Remove invisible/control characters (but keep newlines and tabs for now)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    # Remove zero-width characters
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    # Remove other problematic formatting characters
    text = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F-\u206F]', '', text)
    # Keep most printable Unicode characters, but remove private use and specials
    # This is more permissive - we'll let FFmpeg/font handle what it can
    text = re.sub(r'[\uE000-\uF8FF\uFFF0-\uFFFF]', '', text)  # Private use and specials
    return text.strip()


def render_text_template(template: str, ctx: TemplateContext) -> str:
    """
    Render a simple Python-format template.

    Supported placeholders:
    - {license.number}
    - {license.title}
    - {license.subtitle}
    - {license.title_line}  (\"Title - Subtitle\" if subtitle exists)
    - {license.created_year}
    - {profile.display}
    - {profile.media_authority_full_name}
    - {profile.media_authority_name}
    - {labels.broadcast_responsibility}
    """
    # Clean source text before processing
    title = _clean_text_for_ffmpeg(ctx.license.title or "")
    subtitle = _clean_text_for_ffmpeg(ctx.license.subtitle or "")
    
    # DEBUG: Check for "und" in title to detect invisible characters
    if 'und' in title.lower() or 'un' in title.lower():
        und_pos = title.lower().find('und')
        if und_pos < 0:
            und_pos = title.lower().find('un')
        if und_pos >= 0:
            start = max(0, und_pos - 3)
            end = min(len(title), und_pos + 6)
            section = title[start:end]
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[TEMPLATE DEBUG] title section around un/und: "
                f"{repr(section)} "
                f"code_points={[ord(c) for c in section]} "
                f"hex={[hex(ord(c)) for c in section]}"
            )
    title_line = f"{title} - {subtitle}" if subtitle else title
    title_line_wrapped = _wrap_text(title_line, width=34, max_lines=3)
    
    # Title wrapped with ~32 chars per line for better text flow
    # Check if title is long (3+ lines) - if so, don't show subtitle
    title_wrapped_full = _wrap_text(title, width=32, max_lines=4)  # Allow 4 lines to avoid cutting text
    title_lines_count = len(title_wrapped_full.split('\n')) if title_wrapped_full else 0
    
    # IMPORTANT: Do not add dash to title here.
    # Dash between title and subtitle should be handled visually by spacing, not as part of title text.
    # Real title line count is determined in FFmpeg renderer with pixel-accurate measurements.
    # Do not pre-wrap the title here - title wrapping / splitting is handled in the FFmpeg renderer.
    title_wrapped_short = title
    
    # Subtitle only if title is not too long (less than 3 lines)
    subtitle_conditional = subtitle if title_lines_count < 3 else ""
    subtitle_wrapped = _wrap_text(subtitle_conditional, width=32, max_lines=3) if subtitle_conditional else ""

    mapping: Dict[str, Any] = {
        "license": _DotDict(
            {
                "number": ctx.license.number,
                "title": title,
                "subtitle": subtitle,
                "title_line": title_line,
                "title_line_wrapped": title_line_wrapped,
                "title_wrapped_short": title_wrapped_short,
                "subtitle_conditional": subtitle_conditional,
                "subtitle_wrapped": subtitle_wrapped,
                "created_year": ctx.license_created_year,
            }
        ),
        "profile": _DotDict(
            {
                "display": ctx.profile_display,
                "media_authority_full_name": ctx.media_authority_full_name or ctx.media_authority_name,
                "media_authority_name": ctx.media_authority_name,
            }
        ),
        "labels": _DotDict(ctx.labels),
    }

    return template.format_map(_DotDict(mapping))


def _wrap_text(text: str, width: int = 34, max_lines: int = None) -> str:
    """Wrap text into multiple lines for ffmpeg drawtext.
    
    Args:
        text: Text to wrap
        width: Maximum characters per line
        max_lines: Maximum number of lines (None = no limit)
    """
    text = (text or "").strip()
    if not text:
        return ""
    # Normalize text
    text = unicodedata.normalize('NFC', text)
    # Remove control characters but keep printable text
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F\u200B-\u200D\uFEFF\u2000-\u200F\u2028-\u202F]', '', text)
    
    # Wrap text - only break on spaces, never break words
    lines = textwrap.wrap(
        text, 
        width=width, 
        break_long_words=False,  # Never break words
        break_on_hyphens=False,  # Never break on hyphens
    )
    
    # Limit lines only if max_lines is specified
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    
    # Clean lines - only strip whitespace
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    
    return "\n".join(cleaned_lines)


class _DotDict(dict):
    """Allow attribute-style access for nested dicts in format strings."""

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        if isinstance(value, dict) and not isinstance(value, _DotDict):
            return _DotDict(value)
        return value

    def __getattr__(self, item: str) -> Any:
        value = self.get(item)
        if isinstance(value, dict):
            return _DotDict(value)
        return value


