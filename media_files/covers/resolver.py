"""Style resolver: choose a cover template + theme for given content.

Resolution order (first match wins):
    1. DB rules   -> active CoverTemplate rules by priority (editor-configured)
    2. series-rule -> JournalCover (episode marker detected in title)
    3. category-rule -> config-driven category->template mapping
    4. BaseCover  -> universal fallback

A resolved theme (dict) carries optional overrides applied at render time,
e.g. ``{"accent": "#FF6B00", "background_style": "cinematic"}``.
"""

import logging
import re

from media_files.covers.config import CoverConfig
from media_files.covers.data import CoverData
from media_files.covers.templates import JournalCover, get_template

logger = logging.getLogger('django')


def _match_db_rules(data: CoverData):
    """Return (template_name, theme) from the first matching DB rule, or None."""
    try:
        from media_files.models import CoverTemplate
    except Exception:
        return None

    try:
        rules = list(CoverTemplate.objects.filter(is_active=True).order_by('priority', 'id'))
    except Exception:
        # Table may not exist yet (pre-migration); fall back silently.
        return None

    for rule in rules:
        if rule.scope == 'channel':
            return rule.template, (rule.theme or {})
        if rule.scope == 'series':
            if not data.is_series:
                continue
            target = data.title or ''
        else:  # category
            target = data.category or ''
        pattern = (rule.match_pattern or '').strip()
        if not pattern:
            continue
        try:
            if re.search(pattern, target, re.IGNORECASE):
                return rule.template, (rule.theme or {})
        except re.error:
            logger.warning('Cover: invalid regex in CoverTemplate rule %s', rule.pk)
            continue
    return None


def resolve_overlay_rule(data: CoverData):
    """Return the first matching active CoverOverlayRule, or ``None``.

    Overlay (graphic) rules take precedence over layout-template rules.
    """
    try:
        from media_files.models import CoverOverlayRule
        rules = list(CoverOverlayRule.objects.filter(is_active=True).order_by('priority', 'id'))
    except Exception:
        return None

    for rule in rules:
        if rule.scope == 'channel':
            return rule
        if rule.scope == 'series':
            if not data.is_series and not (data.title or ''):
                continue
            target = data.title or ''
        else:  # category
            target = data.category or ''
        pattern = (rule.match_pattern or '').strip()
        if not pattern:
            continue
        try:
            if re.search(pattern, target, re.IGNORECASE):
                return rule
        except re.error:
            logger.warning('Cover: invalid regex in CoverOverlayRule %s', rule.pk)
            continue
    return None


def overlays_for_rule(rule):
    """Return the active overlays for a rule: explicit selection, else pool."""
    explicit = list(rule.overlays.filter(is_active=True).order_by('name', 'id'))
    if explicit:
        return explicit
    return overlays_in_pool(rule.pool)


def overlays_in_pool(pool: str):
    """Return active CoverOverlay instances in a pool, ordered."""
    if not pool:
        return []
    try:
        from media_files.models import CoverOverlay
        return list(CoverOverlay.objects.filter(is_active=True, pool=pool).order_by('name', 'id'))
    except Exception:
        return []


def resolve_template(data: CoverData, config: CoverConfig):
    """Return ``(template_instance, theme_dict)`` for the given cover data."""
    db_match = _match_db_rules(data)
    if db_match:
        template_name, theme = db_match
        return get_template(template_name)(), theme

    if data.is_series:
        return JournalCover(), {}

    template_name = config.template_for_category(data.category)
    return get_template(template_name)(), {}
