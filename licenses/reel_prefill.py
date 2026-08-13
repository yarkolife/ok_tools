"""Reel Studio prefill: build the ready-to-render link for a license.

The license admin offers this as a row action and as a button on the change
form. The notification "planned own production without a reel" leads to the
same screen, so nobody has to look the license up first — which is the whole
point of being told about it. Both go through this module, so the operator
always lands on the same prefilled form.

Every function degrades to an empty value instead of raising: a missing plan,
a missing video or a disabled Reel Studio must render the page without the
link, not break it.
"""

from django.apps import apps
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
import logging


logger = logging.getLogger('django')

WEEKDAYS = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag',
            'Freitag', 'Samstag', 'Sonntag')


def is_enabled() -> bool:
    """True if the Reel Studio is enabled and configured in ToolsConfig."""
    try:
        from tools.models import ToolsConfig
        return ToolsConfig.get_config().is_reel_configured()
    except Exception:
        return False


def plan_info(license_obj):
    """Find the broadcast plan entry for a license.

    Picks the latest plan (by date) that contains this license; if several
    items match within it, the last one wins. Returns (date, start_time) as
    (date|None, "HH:MM").
    """
    try:
        from planung.models import TagesPlan
    except Exception:
        return None, ''

    # Match by license_id first, fall back to the license number.
    for key, value in (('license_id', license_obj.id),
                       ('number', license_obj.number)):
        plan = (
            TagesPlan.objects
            .filter(json_plan__items__contains=[{key: value}])
            .order_by('-datum')
            .first()
        )
        if not plan:
            continue
        matches = [
            it for it in (plan.json_plan or {}).get('items', [])
            if isinstance(it, dict) and it.get(key) == value
        ]
        if not matches:
            continue
        item = matches[-1]  # last value if several
        uhr = (item.get('start') or '')[:5]  # "18:00:00" -> "18:00"
        return plan.datum, uhr
    return None, ''


def sendetermin(license_obj):
    """German broadcast day+date and time, e.g. ('Samstag, 27.06.', '18:00')."""
    plan_date, uhr = plan_info(license_obj)
    if not plan_date:
        return '', ''
    return f"{WEEKDAYS[plan_date.weekday()]}, {plan_date:%d.%m.}", uhr


def video_file(license_obj):
    """Pick the best video file for a reel: prefer playout, then archive.

    Falls back to the license's primary video file when no copy can be
    ranked (e.g. a single custom-storage file).
    """
    from media_files.utils import is_reel_filename
    from tools.services.okmq_reel import share_prefix_for

    def is_full_source(vf):
        return (
            vf is not None
            and bool(getattr(vf, 'is_available', False))
            and not bool(getattr(vf, 'is_preview', False))
            and not is_reel_filename(getattr(vf, 'filename', '') or '')
            and not is_reel_filename(getattr(vf, 'file_path', '') or '')
        )

    try:
        from media_files.models import VideoFile
        candidates = list(
            VideoFile.objects
            .filter(number=license_obj.number, is_available=True)
            .exclude(is_preview=True)
            .select_related('storage_location')
        )
    except Exception:
        candidates = []
    candidates = [vf for vf in candidates if is_full_source(vf)]

    primary = None
    try:
        primary = license_obj.get_video_file()
    except Exception:
        primary = None
    if is_full_source(primary) and primary not in candidates:
        candidates.append(primary)
    if not candidates:
        return None

    # playout (0) before archive (1) before anything else (2); newest first.
    rank = {'playout': 0, 'archive': 1}

    def sort_key(vf):
        prefix = share_prefix_for(getattr(vf, 'storage_location', None))
        return (rank.get(prefix, 2), -(vf.id or 0))

    candidates.sort(key=sort_key)
    return candidates[0]


def studio_url(license_obj) -> str:
    """Build the Reel Studio URL prefilled from a license, or '' if unavailable."""
    from tools.models import ToolsConfig

    config = ToolsConfig.get_config()
    try:
        source = video_file(license_obj)
    except Exception:
        source = None

    # Use the broadcast date for the filename (not today), fall back to now.
    plan_date, _plan_uhr = plan_info(license_obj)
    name_date = plan_date or timezone.now()
    try:
        output_name = (config.reel_output_name_pattern or '').format(
            number=license_obj.number, date=name_date)
    except Exception:
        output_name = ''

    duration = ''
    if license_obj.duration:
        duration = str(int(license_obj.duration.total_seconds()))

    autor = ''
    if license_obj.profile_id:
        autor = str(license_obj.profile).strip()

    sendung = ''
    if license_obj.category_id:
        sendung = (getattr(license_obj.category, 'name', '') or '').strip()

    se_tag, se_uhr = sendetermin(license_obj)

    params = {
        'title': license_obj.title or '',
        'output_name': output_name,
        'autor': autor,
        'sendung': sendung,
        'description': license_obj.description or '',
        'dauer': duration,
        'se_tag': se_tag,
        'se_uhr': se_uhr,
    }
    if source is not None and getattr(source, 'id', None):
        # Build a path relative to the renderer's share root
        # (playout/ = Sendedaten, archive/ = FilmArchiv).
        from tools.services.okmq_reel import share_relative_path
        params['video'] = share_relative_path(
            getattr(source, 'file_path', ''),
            getattr(source, 'storage_location', None))
        # Pass the video id so the Reel Studio can show an inline player for
        # picking the start second manually.
        params['video_id'] = source.id
    try:
        return f"{reverse('tools:reel_studio')}?{urlencode(params)}"
    except NoReverseMatch:
        return ''


def studio_url_for_number(number) -> str:
    """Return the prefilled Reel Studio URL for a license number, or ''.

    Used by the notification about a planned own production without a reel:
    the entry names the number, the reader wants the render form.
    """
    if not number or not is_enabled():
        return ''
    try:
        License = apps.get_model('licenses.License')
        license_obj = (
            License.objects
            .select_related('profile', 'category')
            .filter(number=number)
            .first()
        )
        if license_obj is None:
            return ''
        return studio_url(license_obj)
    except Exception:
        logger.exception('Could not build the Reel Studio link for %s', number)
        return ''
