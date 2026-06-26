"""Single entry point for cover generation."""

import logging

from media_files.covers import frames
from media_files.covers import storage
from media_files.covers import variations
from media_files.covers.config import get_cover_config
from media_files.covers.data import CoverData
from media_files.covers.resolver import (
    overlays_for_rule,
    resolve_overlay_rule,
    resolve_template,
)
from media_files.covers.series import parse_series
from media_files.covers.storage import save_cover

logger = logging.getLogger('django')


def _duration_seconds(*candidates):
    """Return seconds from the first non-empty timedelta candidate."""
    for value in candidates:
        if value:
            try:
                return value.total_seconds()
            except AttributeError:
                continue
    return None


def _build_cover_data(video_file, license_obj) -> CoverData:
    """Assemble :class:`CoverData` from a VideoFile and its License."""
    author = ''
    category = ''
    title = ''
    subtitle = ''
    number = video_file.number

    if license_obj is not None:
        title = license_obj.title or ''
        subtitle = license_obj.subtitle or ''
        number = license_obj.number
        if license_obj.profile_id:
            author = str(license_obj.profile)
        if license_obj.category_id:
            category = license_obj.category.name

    duration = _duration_seconds(
        video_file.duration,
        getattr(license_obj, 'duration', None),
    )

    series = parse_series(title)

    return CoverData(
        title=title,
        subtitle=subtitle,
        author=author,
        category=category,
        number=number,
        duration_seconds=duration,
        series=series.series,
        episode_marker=series.marker,
        episode_part=series.part,
        episode_total=series.total,
    )


def generate_cover(video_file, force=False, config=None):
    """Generate a cover for a single ``VideoFile``.

    Args:
        video_file: The ``VideoFile`` providing the background frame.
        force: Regenerate even if a cover path is already recorded.
        config: Optional pre-loaded :class:`CoverConfig` (for batch runs).

    Returns:
        The absolute path of the written cover, or ``None`` on skip/failure.
    """
    config = config or get_cover_config()

    if video_file.thumbnail and not force:
        logger.info('Cover: %s already has a thumbnail; skipping (use force).',
                    video_file.number)
        return video_file.thumbnail

    license_obj = video_file.get_license()
    data = _build_cover_data(video_file, license_obj)

    background = frames.extract_background(
        video_file.full_path,
        duration_seconds=data.duration_seconds,
        size=config.size,
    )

    # Graphic-overlay rules take precedence over layout templates.
    rule = resolve_overlay_rule(data)
    if rule:
        pool_overlays = overlays_for_rule(rule)
        if pool_overlays:
            return _generate_with_overlays(
                video_file, data, config, background, pool_overlays, rule.selection_mode)
        logger.warning('Cover: overlay rule %r has no graphics; using layout template.',
                       rule.name)

    if background is None:
        logger.warning('Cover: could not extract a frame for %s; skipping.',
                       video_file.number)
        return None

    template, theme = resolve_template(data, config)
    image = template.render(background, data, config, theme=theme)

    path = save_cover(image, data.number, config.output_dir)

    video_file.thumbnail = path
    video_file.save(update_fields=['thumbnail', 'updated_at'])
    return path


def _generate_with_overlays(video_file, data, config, background, pool_overlays, mode):
    """Render covers using a pool of graphic overlays.

    ``random`` -> one deterministic variant becomes the canonical cover.
    ``all`` -> every overlay is rendered into candidates/ plus a contact sheet
    for an operator to review; no canonical cover is set yet.
    """
    from media_files.covers.templates.overlay import OverlayCover

    if mode == 'all':
        images = [OverlayCover(ov).render(background, data, config)
                  for ov in pool_overlays]
        storage.save_variants(images, data.number, config.output_dir)
        sheet = storage.build_contact_sheet(images, data.number, config.output_dir)
        logger.info('Cover: %s variants for %s; review %s',
                    len(images), data.number, sheet)
        return sheet

    overlay = pool_overlays[variations.variant_index(data.number, len(pool_overlays))]
    image = OverlayCover(overlay).render(background, data, config)
    path = save_cover(image, data.number, config.output_dir)
    video_file.thumbnail = path
    video_file.save(update_fields=['thumbnail', 'updated_at'])
    return path


def generate_cover_for_license(license_obj, force=False, config=None):
    """Generate a cover for a ``License`` by locating its primary video.

    Returns the cover path, or ``None`` if no accessible video was found.
    """
    from media_files.models import VideoFile

    versions = (
        VideoFile.objects
        .filter(number=license_obj.number)
        .exclude(is_preview=True)
    )
    candidates = list(versions)
    if not candidates:
        logger.warning('Cover: no video file for license %s.', license_obj.number)
        return None

    video_file = _pick_video(candidates)
    return generate_cover(video_file, force=force, config=config)


def _pick_video(candidates):
    """Prefer an available primary version, else any available, else first."""
    return (
        next((v for v in candidates if v.is_available and v.is_primary_version()), None)
        or next((v for v in candidates if v.is_available), None)
        or candidates[0]
    )


def generate_cover_candidates(video_file, config=None, background=None):
    """Render every overlay in the matched pool into candidates/ + contact sheet.

    On first run (``background`` is None) it also extracts a strip of frames to
    ``candidates/{number}/frames/`` so the operator can pick a different one,
    and uses the best-scoring frame by default. When ``background`` is given
    (operator chose a frame) the strip is left untouched and that frame is used.

    Returns the contact-sheet path, or ``None`` if no overlay-pool rule matches
    or the pool is empty.
    """
    from media_files.covers.templates.overlay import OverlayCover

    config = config or get_cover_config()
    license_obj = video_file.get_license()
    data = _build_cover_data(video_file, license_obj)

    rule = resolve_overlay_rule(data)
    if not rule:
        return None
    pool_overlays = overlays_for_rule(rule)
    if not pool_overlays:
        return None

    if background is None:
        strip = frames.extract_frames(
            video_file.full_path, duration_seconds=data.duration_seconds,
            count=3, size=config.size)
        if strip:
            storage.save_frames(strip, data.number, config.output_dir)
            background = frames.best_frame(strip)
        else:
            background = frames.extract_background(
                video_file.full_path, duration_seconds=data.duration_seconds, size=config.size)

    images = [OverlayCover(ov).render(background, data, config) for ov in pool_overlays]
    storage.save_variants(images, data.number, config.output_dir)
    storage.save_manifest(
        data.number, config.output_dir,
        {str(i): ov.name for i, ov in enumerate(pool_overlays, start=1)})
    return storage.build_contact_sheet(images, data.number, config.output_dir)


def generate_cover_candidates_for_license(license_obj, config=None, background=None):
    """Generate overlay candidates for a license's primary video."""
    from media_files.models import VideoFile

    candidates = list(
        VideoFile.objects.filter(number=license_obj.number).exclude(is_preview=True))
    if not candidates:
        logger.warning('Cover: no video file for license %s.', license_obj.number)
        return None
    return generate_cover_candidates(
        _pick_video(candidates), config=config, background=background)
