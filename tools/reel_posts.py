"""Instagram posts for rendered reels: drafts, approval and publishing.

A finished reel becomes a draft post with a caption from the template, the
collab accounts of matching partners and the broadcast day as publishing
time. Staff check and approve it; Celery publishes approved posts when they
are due. Publishing is never automatic without an approval, because a post
on Instagram cannot be taken back quietly.
"""

from .models import InstagramPartner
from .models import ReelPost
from .models import ToolsConfig
from .services import instagram
from datetime import date
from datetime import datetime
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from pathlib import Path
import logging
import re


logger = logging.getLogger('django')

WEEKDAYS = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')

# Instagram: query the container once per minute, for no more than 5 minutes.
STATUS_CHECK_INTERVAL = 60
STATUS_CHECK_LIMIT = 5
# A container expires 24 hours after it was created.
CONTAINER_LIFETIME = timedelta(hours=23)
# An approved post that is this late is not published any more.
MISSED_AFTER = timedelta(hours=24)
# How long a post waits for a missing Mediathek link (the reminder mail waits as long).
MEDIATHEK_WAIT = timedelta(hours=1)

_PLACEHOLDER = re.compile(r'\{(\w+)\}')


def reel_studio_active() -> bool:
    """Reel features exist only where the Reel Studio is switched on and set up."""
    try:
        return ToolsConfig.get_config().is_reel_configured()
    except Exception:
        return False


def instagram_active() -> bool:
    """Instagram posting is switched on (inside a working Reel Studio)."""
    try:
        return ToolsConfig.get_config().is_instagram_switched_on()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

def reel_date_from_filename(filename: str) -> date | None:
    """Return the broadcast date written in a reel name (``…_YYMMDD``)."""
    for match in reversed(re.findall(r'(?<!\d)(\d{6})(?!\d)', Path(filename).stem)):
        try:
            return datetime.strptime(match, '%y%m%d').date()
        except ValueError:
            continue
    return None


def _license_texts(license_obj, match_in: str) -> list[str]:
    if license_obj is None:
        return []
    tags = license_obj.tags if isinstance(license_obj.tags, list) else []
    author = ''
    profile = getattr(license_obj, 'profile', None)
    if profile is not None:
        author = f'{getattr(profile, "first_name", "")} {getattr(profile, "last_name", "")}'
    parts = {
        'title': [license_obj.title or '', license_obj.subtitle or ''],
        'tags': [str(t) for t in tags],
        'author': [author, license_obj.further_persons or ''],
    }
    if match_in == InstagramPartner.MATCH_ANY:
        return parts['title'] + parts['tags'] + parts['author'] + [license_obj.description or '']
    return parts.get(match_in, [])


def partners_for(license_obj) -> list[InstagramPartner]:
    """Return the active partners whose keywords appear in the license."""
    found = []
    for partner in InstagramPartner.objects.filter(is_active=True):
        text = '\n'.join(_license_texts(license_obj, partner.match_in))
        if any(re.search(rf'(?<!\w){re.escape(k)}(?!\w)', text, re.IGNORECASE)
               for k in partner.keyword_list()):
            found.append(partner)
    return found


def collaborators_for(license_obj) -> list[str]:
    """Collab usernames for a license, at most the 3 Instagram allows.

    The author's own account (profile) comes first, then matching partners.
    """
    candidates = []
    profile = getattr(license_obj, 'profile', None) if license_obj is not None else None
    own = str(getattr(profile, 'instagram', '') or '').strip().lstrip('@')
    if own:
        candidates.append(own)
    for partner in partners_for(license_obj):
        candidates.extend(partner.username_list())
    names = []
    for name in candidates:
        if name.lower() not in {n.lower() for n in names}:
            names.append(name)
    return names[:ReelPost.MAX_COLLABORATORS]


def _hashtag(tag: str) -> str:
    """One hashtag from a tag, with or without "#".

    Several words become one, each starting with a capital letter so the tag
    stays readable ("offener kanal" -> "#OffenerKanal"); "_" stays inside a word.
    """
    words = [w for w in re.split(r'[^\w]+', str(tag)) if w]
    if len(words) > 1:
        words = [w[:1].upper() + w[1:] for w in words]
    word = ''.join(words)
    return f'#{word}' if word else ''


def split_hashtags(text: str) -> list[str]:
    """Tags typed in one field: "#Offener Kanal #OKMQ" or "OKMQ, Merseburg".

    With "#" each "#" starts a tag (spaces join words); without, spaces and
    commas separate the tags.
    """
    text = text or ''
    pattern = r'[#,]+' if '#' in text else r'[\s,]+'
    return [t.strip() for t in re.split(pattern, text) if t.strip()]


def hashtags_for(tags, fixed: str = '') -> str:
    """License tags, then the fixed hashtags; no duplicates (any case).

    Instagram allows only ``MAX_HASHTAGS`` per post: the fixed hashtags always
    get their place, the license tags fill what is left.
    """
    def unique(words, taken=()):
        found = []
        for word in words:
            tag = _hashtag(word)
            if tag and tag.lower() not in {t.lower() for t in [*taken, *found]}:
                found.append(tag)
        return found

    fixed_tags = unique(split_hashtags(fixed))[:ReelPost.MAX_HASHTAGS]
    room = ReelPost.MAX_HASHTAGS - len(fixed_tags)
    # A license tag may hold several ("#Gesang #musik"); without "#" it is one,
    # even with spaces ("Hochschule Merseburg").
    words = [w for t in (tags or []) for w in re.split(r'[#,]+', str(t)) if w.strip()]
    license_tags = unique(words, fixed_tags)[:room]
    return ' '.join(license_tags + fixed_tags)


def hook_text(hook) -> str:
    """The reel's hook (``{"zeile1", "zeile2"}``) as one line."""
    if isinstance(hook, str):
        return hook.strip()
    if not isinstance(hook, dict):
        return ''
    parts = [str(hook.get(k) or '').strip() for k in ('zeile1', 'zeile2')]
    return ' '.join(p for p in parts if p)


def _plan_entry(number, day: date | None) -> dict:
    if not number or not day:
        return {}
    try:
        from .tasks import _today_plan_matches
        matches = _today_plan_matches(day, {int(number)})
    except Exception:
        return {}
    entries = matches.get(int(number)) or []
    return entries[0] if entries else {}


def shorten(text: str, limit: int) -> str:
    """Cut ``text`` to ``limit`` characters at the end of a sentence.

    Without a sentence end in the allowed part it is cut after a word, with "…".
    """
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    if limit <= 0:
        return ''
    part = text[:limit + 1]
    ends = [m.end() for m in re.finditer(r'[.!?…](?=\s|$)', part) if m.end() <= limit]
    if ends:
        return part[:ends[-1]].strip()
    cut = text[:max(limit - 1, 0)]
    if ' ' in cut:
        cut = cut[:cut.rindex(' ')]
    return (cut.rstrip(' ,;:-') + '…') if cut else ''


def render_caption(template: str, values: dict) -> str:
    """Fill the template; drop lines whose placeholders are all empty."""
    text = _fill(template, values)
    if len(text) <= ReelPost.CAPTION_MAX_LENGTH:
        return text
    return shorten(text, ReelPost.CAPTION_MAX_LENGTH)


# Filled in only when the post is published: the Mediathek link usually exists
# only on the broadcast day, and the broadcast time may still change in the plan.
LATE_PLACEHOLDERS = ('sendetermin', 'uhrzeit', 'mediathek')
# Room kept free in a draft for the late placeholders (link, day and time).
LATE_RESERVE = 200


def fit_caption(template: str, values: dict, limit: int = ReelPost.CAPTION_MAX_LENGTH) -> str:
    """Fill the template; a too long caption loses the end of the description."""
    text = _fill(template, values)
    over = len(text) - limit
    description = str(values.get('beschreibung') or '')
    if over > 0 and description and '{beschreibung}' in (template or ''):
        values = dict(values, beschreibung=shorten(description, len(description) - over))
        text = _fill(template, values)
    return text if len(text) <= limit else shorten(text, limit)


def _fill(template: str, values: dict) -> str:
    lines = []
    for line in (template or '').replace('\r\n', '\n').split('\n'):
        keys = _PLACEHOLDER.findall(line)
        known = [k for k in keys if k in values]
        if known and not any(str(values[k]).strip() for k in known):
            continue
        lines.append(_PLACEHOLDER.sub(
            lambda m: str(values.get(m.group(1), m.group(0))), line))
    text = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def caption_values(license_obj, day: date | None, plan_entry: dict,
                   hook=None, fixed_hashtags: str = '') -> dict:
    """The values for the caption placeholders."""
    author = str(plan_entry.get('sender_responsible') or plan_entry.get('author') or '').strip()
    if not author and license_obj is not None and getattr(license_obj, 'profile', None):
        profile = license_obj.profile
        author = f'{profile.first_name} {profile.last_name}'.strip()
    start = str(plan_entry.get('start') or '')[:5]
    tags = license_obj.tags if license_obj is not None and isinstance(license_obj.tags, list) else []
    return {
        'hook': hook_text(hook),
        'titel': getattr(license_obj, 'title', '') or str(plan_entry.get('title') or ''),
        'untertitel': getattr(license_obj, 'subtitle', '') or '',
        'beschreibung': getattr(license_obj, 'description', '') or '',
        'autor': author,
        'sendetermin': (
            f'{WEEKDAYS[day.weekday()]}, {day:%d.%m.%Y}' + (f', {start} Uhr' if start else '')
            if day else ''),
        'uhrzeit': start,
        'mediathek': getattr(license_obj, 'mediathek_url', '') or '',
        'hashtags': hashtags_for(tags, fixed_hashtags),
    }


def create_draft(filename: str, number=None, cover_ms=None, hook=None) -> ReelPost | None:
    """Create the post draft for a rendered reel (once per file).

    ``cover_ms`` is the cover frame the reel renderer reports: where the hook
    is on screen (for question hooks only the question). A draft the folder
    scan created before the render result arrived gets it afterwards.
    ``hook`` is the hook shown in the reel (``{hook}`` in the caption).
    """
    config = ToolsConfig.get_config()
    if not config.is_instagram_configured():
        return None
    filename = Path(str(filename)).name
    cover_ms = _cover_ms(cover_ms)
    existing = ReelPost.objects.filter(filename=filename).first()
    if existing:
        if (cover_ms and not existing.thumb_offset_ms
                and existing.status == ReelPost.STATUS_DRAFT):
            existing.thumb_offset_ms = cover_ms
            existing.save(update_fields=['thumb_offset_ms', 'updated_at'])
        return existing

    license_obj = None
    if number:
        try:
            from licenses.models import License
            license_obj = License.objects.select_related('profile').filter(number=number).first()
        except Exception:
            license_obj = None
    day = reel_date_from_filename(filename)
    entry = _plan_entry(number, day)
    scheduled_at = None
    if day:
        # Posted in the morning of the broadcast day, together with the reminder mail.
        scheduled_at = timezone.make_aware(datetime.combine(day, config.reel_reminder_time))

    values = caption_values(license_obj, day, entry, hook=hook,
                            fixed_hashtags=config.instagram_fixed_hashtags)
    # Link, broadcast day and time stay placeholders until the post is published.
    for key in LATE_PLACEHOLDERS:
        values.pop(key)

    post, _created = ReelPost.objects.get_or_create(
        filename=filename,
        defaults={
            'license': license_obj,
            'caption': fit_caption(config.instagram_caption_template, values,
                                   ReelPost.CAPTION_MAX_LENGTH - LATE_RESERVE),
            'collaborators': ', '.join(collaborators_for(license_obj)),
            'share_to_feed': config.instagram_share_to_feed,
            'thumb_offset_ms': cover_ms or 0,
            'scheduled_at': scheduled_at,
        },
    )
    return post


def _cover_ms(value) -> int:
    """The renderer's cover time in ms; anything unusable counts as none."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return value if 0 < value < 15 * 60 * 1000 else 0


REEL_VIDEO_SUFFIXES = ('.mp4', '.mov', '.m4v')
_REEL_NAME = re.compile(r'(^|_)reel($|_)')


def is_reel_file(filename: str) -> bool:
    """``…_Reel_…`` files; the folder also holds full programme previews."""
    return bool(_REEL_NAME.search(Path(filename or '').stem.lower()))


def drafts_for_existing_reels(today: date | None = None) -> list[ReelPost]:
    """Create drafts for reels already in the output folder; return the new ones.

    Only reels (``Reel`` in the name, not the full programme previews) whose
    broadcast day (``…_YYMMDD`` in the name) is today or later: a preview
    of a broadcast that is over is not worth posting.
    """
    config = ToolsConfig.get_config()
    folder = config.get_reel_output_dir()
    if not config.is_instagram_configured() or folder is None:
        return []
    today = today or timezone.localdate()
    known = set(ReelPost.objects.values_list('filename', flat=True))
    try:
        from media_files.utils import extract_number_from_filename
    except Exception:  # media_files is optional
        extract_number_from_filename = None
    created = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in REEL_VIDEO_SUFFIXES:
            continue
        if not is_reel_file(path.name):
            continue
        if path.name in known:
            continue
        day = reel_date_from_filename(path.name)
        if day is None or day < today:
            continue
        number = extract_number_from_filename(path.name) if extract_number_from_filename else None
        try:
            post = create_draft(path.name, number)
        except Exception:
            logger.exception('Could not create the Instagram post draft for %s', path.name)
            continue
        if post is not None:
            created.append(post)
    return created


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

def approve(post: ReelPost, user, *, now: bool = False) -> None:
    """Approve a draft (or failed) post; ``now`` publishes it right away."""
    post.full_clean()
    moment = timezone.now()
    post.status = ReelPost.STATUS_APPROVED
    post.approved_by = user
    post.approved_at = moment
    post.error_message = ''
    if now or not post.scheduled_at:
        post.scheduled_at = moment
    post.save()


def _published_on_demand(post: ReelPost) -> bool:
    """True for "publish now": approved at (or after) its publishing time."""
    return bool(post.approved_at and post.scheduled_at and post.approved_at >= post.scheduled_at)


def back_to_draft(post: ReelPost) -> None:
    post.status = ReelPost.STATUS_DRAFT
    post.approved_by = None
    post.approved_at = None
    post.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])


# ---------------------------------------------------------------------------
# Publishing (called from Celery tasks)
# ---------------------------------------------------------------------------

def mediathek_url(license_obj) -> str:
    """The license's Mediathek link; looked up once more if it is still missing."""
    if license_obj is None:
        return ''
    if license_obj.mediathek_url:
        return license_obj.mediathek_url
    try:
        from .tasks import _try_refresh_mediathek_url
        return _try_refresh_mediathek_url(license_obj) or ''
    except Exception:
        logger.exception('Mediathek lookup for the Instagram post failed')
        return ''


def broadcast_values(post: ReelPost) -> dict:
    """``{sendetermin}`` and ``{uhrzeit}`` from the plan as it is now."""
    day = reel_date_from_filename(post.filename)
    values = caption_values(post.license, day, _plan_entry(post.number, day))
    return {'sendetermin': values['sendetermin'], 'uhrzeit': values['uhrzeit']}


def public_video_url(filename: str) -> str:
    from .tasks import _reel_public_download_url
    return _reel_public_download_url(filename)


def _fail(post: ReelPost, message: str) -> None:
    post.status = ReelPost.STATUS_FAILED
    post.error_message = message
    post.save(update_fields=['status', 'error_message', 'updated_at'])
    logger.warning('Instagram post %s failed: %s', post.pk, message)
    try:
        from notifications.services import emit
        emit('tools.instagram_post_failed', obj=post,
             payload={'post': post.filename, 'error': message[:200]},
             dedup_key=f'tools.instagram_post_failed|{post.pk}|{timezone.now():%Y%m%d%H%M}')
    except Exception:
        logger.exception('Could not report the failed Instagram post %s', post.pk)


def due_posts():
    """Approved posts whose time has come."""
    return ReelPost.objects.filter(
        status=ReelPost.STATUS_APPROVED, scheduled_at__lte=timezone.now())


def claim(post_id: int) -> ReelPost | None:
    """Move an approved post to "publishing"; None if someone else has it."""
    with transaction.atomic():
        claimed = ReelPost.objects.filter(
            pk=post_id, status=ReelPost.STATUS_APPROVED).update(
                status=ReelPost.STATUS_PUBLISHING, updated_at=timezone.now())
    return ReelPost.objects.get(pk=post_id) if claimed else None


def start_publishing(post: ReelPost) -> bool:
    """Create the container (or reuse a fresh one); True if checks should follow."""
    config = ToolsConfig.get_config()
    if not config.is_instagram_configured():
        _fail(post, 'Instagram posting is switched off or not configured.')
        return False
    if post.scheduled_at and timezone.now() - post.scheduled_at > MISSED_AFTER:
        _fail(post, 'The publishing time is more than 24 hours ago; check the post and approve it again.')
        return False
    if config.resolve_reel_output_file(post.filename) is None:
        _fail(post, 'The reel file was not found in the reel output folder.')
        return False

    fresh = (post.container_id and post.container_created_at
             and timezone.now() - post.container_created_at < CONTAINER_LIFETIME)
    if not fresh:
        video_url = public_video_url(post.filename)
        if not video_url.startswith('https://'):
            _fail(post, 'SITE_BASE_URL must be a public https address, Instagram downloads the video from there.')
            return False
        late = {}
        if '{mediathek}' in post.caption:
            link = mediathek_url(post.license)
            if (not link and not _published_on_demand(post) and post.scheduled_at
                    and timezone.now() - post.scheduled_at < MEDIATHEK_WAIT):
                # Like the reminder mail: wait a while for the link, retried every 5 minutes.
                post.status = ReelPost.STATUS_APPROVED
                post.save(update_fields=['status', 'updated_at'])
                return False
            late['mediathek'] = link
        if '{sendetermin}' in post.caption or '{uhrzeit}' in post.caption:
            late.update(broadcast_values(post))
        if late:
            post.caption = render_caption(post.caption, late)
            post.save(update_fields=['caption', 'updated_at'])
        try:
            post.container_id = instagram.create_reel_container(
                config,
                video_url=video_url,
                caption=post.caption,
                collaborators=post.collaborator_list(),
                share_to_feed=post.share_to_feed,
                thumb_offset_ms=post.thumb_offset_ms,
            )
        except instagram.InstagramError as exc:
            _fail(post, str(exc))
            return False
        post.container_created_at = timezone.now()
    post.status_checks = 0
    post.save(update_fields=['container_id', 'container_created_at', 'status_checks', 'updated_at'])
    return True


def check_and_publish(post: ReelPost) -> str:
    """Check the container once; publish when ready.

    Returns ``'published'``, ``'failed'`` or ``'wait'`` (check again later).
    """
    config = ToolsConfig.get_config()
    try:
        status_code, status_text = instagram.container_status(config, post.container_id)
    except instagram.InstagramError as exc:
        _fail(post, str(exc))
        return 'failed'

    if status_code == 'FINISHED':
        try:
            post.media_id = instagram.publish_container(config, post.container_id)
        except instagram.InstagramError as exc:
            _fail(post, str(exc))
            return 'failed'
        post.permalink = instagram.media_permalink(config, post.media_id)
        post.status = ReelPost.STATUS_PUBLISHED
        post.published_at = timezone.now()
        post.error_message = ''
        post.save()
        queue_facebook(post)
        return 'published'

    if status_code == 'PUBLISHED':
        post.status = ReelPost.STATUS_PUBLISHED
        post.published_at = post.published_at or timezone.now()
        post.save(update_fields=['status', 'published_at', 'updated_at'])
        queue_facebook(post)
        return 'published'

    if status_code in ('ERROR', 'EXPIRED'):
        post.container_id = ''
        post.container_created_at = None
        post.save(update_fields=['container_id', 'container_created_at', 'updated_at'])
        _fail(post, f'Instagram could not process the video: {status_code} {status_text}'.strip())
        return 'failed'

    post.status_checks += 1
    post.save(update_fields=['status_checks', 'updated_at'])
    if post.status_checks >= STATUS_CHECK_LIMIT:
        _fail(post, 'Instagram is still processing the video after 5 minutes. '
                    'Approve the post again later; the upload is kept for 24 hours.')
        return 'failed'
    return 'wait'


# ---------------------------------------------------------------------------
# Facebook: the same reel on the page, after Instagram
# ---------------------------------------------------------------------------

# Facebook usually needs a minute or two; checked every minute, then given up.
FACEBOOK_CHECK_INTERVAL = 60
FACEBOOK_CHECK_LIMIT = 15


def facebook_active() -> bool:
    """Reels also go to the Facebook page (gate for the Facebook notification)."""
    try:
        return ToolsConfig.get_config().is_facebook_configured()
    except Exception:
        return False


def reel_seconds(post: ReelPost) -> float | None:
    """Length of the reel file in seconds, or None if it cannot be read."""
    import subprocess

    from django.conf import settings

    config = ToolsConfig.get_config()
    path = config.resolve_reel_output_file(post.filename)
    if path is None:
        return None
    ffprobe = getattr(settings, 'TOOLS_FFPROBE_PATH', '') or config.ffprobe_path or 'ffprobe'
    try:
        result = subprocess.run(
            [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
            capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.warning('Could not read the length of reel %s', post.filename)
        return None


def facebook_problem(post: ReelPost) -> str:
    """Why the reel cannot go to Facebook, or '' if nothing is known against it."""
    seconds = reel_seconds(post)
    if seconds is not None and not (
            ReelPost.FACEBOOK_MIN_SECONDS <= seconds <= ReelPost.FACEBOOK_MAX_SECONDS):
        return str(_('Facebook accepts reels of %(min)s to %(max)s seconds; this one is %(len)s seconds.') % {
            'min': ReelPost.FACEBOOK_MIN_SECONDS, 'max': ReelPost.FACEBOOK_MAX_SECONDS,
            'len': round(seconds)})
    today = ReelPost.objects.filter(
        facebook_published_at__gte=timezone.now() - timedelta(hours=24)).exclude(pk=post.pk).count()
    if today >= ReelPost.FACEBOOK_DAILY_LIMIT:
        return str(_('Facebook allows %(max)s reels through the API within 24 hours.') % {
            'max': ReelPost.FACEBOOK_DAILY_LIMIT})
    return ''


def _fail_facebook(post: ReelPost, message: str, *, status=ReelPost.FACEBOOK_FAILED) -> None:
    post.facebook_status = status
    post.facebook_error = message
    post.save(update_fields=['facebook_status', 'facebook_error', 'updated_at'])
    logger.warning('Facebook reel of post %s: %s', post.pk, message)
    if status != ReelPost.FACEBOOK_FAILED:
        return
    try:
        from notifications.services import emit
        emit('tools.facebook_post_failed', obj=post,
             payload={'post': post.filename, 'error': message[:200]},
             dedup_key=f'tools.facebook_post_failed|{post.pk}|{timezone.now():%Y%m%d%H%M}')
    except Exception:
        logger.exception('Could not report the failed Facebook reel %s', post.pk)


def queue_facebook(post: ReelPost) -> bool:
    """Mark a post published on Instagram for Facebook; True if it should go there."""
    if not facebook_active() or post.facebook_status:
        return False
    post.facebook_status = ReelPost.FACEBOOK_PENDING
    post.save(update_fields=['facebook_status', 'updated_at'])
    return True


def claim_facebook(post_id: int, *, retry: bool = False) -> ReelPost | None:
    """Move a post to Facebook "publishing"; None if it is not waiting for it."""
    allowed = [ReelPost.FACEBOOK_PENDING]
    if retry:
        allowed += [ReelPost.FACEBOOK_FAILED, ReelPost.FACEBOOK_SKIPPED]
    with transaction.atomic():
        claimed = ReelPost.objects.filter(
            pk=post_id, status=ReelPost.STATUS_PUBLISHED, facebook_status__in=allowed,
        ).update(facebook_status=ReelPost.FACEBOOK_PUBLISHING, facebook_error='',
                 facebook_checks=0, updated_at=timezone.now())
    return ReelPost.objects.get(pk=post_id) if claimed else None


def start_facebook(post: ReelPost) -> bool:
    """Upload and publish the reel on the page; True if status checks should follow."""
    from .services import facebook

    config = ToolsConfig.get_config()
    if not config.is_facebook_configured():
        _fail_facebook(post, 'Facebook posting is switched off or not configured.')
        return False
    problem = facebook_problem(post)
    if problem:
        _fail_facebook(post, problem, status=ReelPost.FACEBOOK_SKIPPED)
        return False
    if config.resolve_reel_output_file(post.filename) is None:
        _fail_facebook(post, 'The reel file was not found in the reel output folder.')
        return False
    video_url = public_video_url(post.filename)
    if not video_url.startswith('https://'):
        _fail_facebook(post, 'SITE_BASE_URL must be a public https address, Facebook downloads the video from there.')
        return False
    def remember(video_id):
        post.facebook_video_id = video_id
        post.save(update_fields=['facebook_video_id', 'updated_at'])

    try:
        # The caption already carries the broadcast time and Mediathek link
        # filled in for Instagram.
        post.facebook_video_id = facebook.publish_reel(
            config, video_url=video_url, description=post.caption, started=remember)
    except facebook.FacebookError as exc:
        _fail_facebook(post, str(exc))
        return False
    post.save(update_fields=['facebook_video_id', 'updated_at'])
    _set_facebook_cover(post)
    return True


def cover_frame(post: ReelPost) -> bytes | None:
    """The reel's cover frame (``thumb_offset_ms``) as JPEG, or None."""
    import subprocess
    import tempfile

    from django.conf import settings

    config = ToolsConfig.get_config()
    path = config.resolve_reel_output_file(post.filename)
    if path is None:
        return None
    ffmpeg = getattr(settings, 'TOOLS_FFMPEG_PATH', '') or config.ffmpeg_path or 'ffmpeg'
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / 'cover.jpg'
        try:
            subprocess.run(
                [ffmpeg, '-v', 'error', '-ss', f'{post.thumb_offset_ms / 1000:.3f}', '-i', str(path),
                 '-frames:v', '1', '-q:v', '2', '-y', str(target)],
                capture_output=True, timeout=60, check=True)
            return target.read_bytes()
        except (OSError, subprocess.SubprocessError):
            logger.warning('Could not cut the cover frame of reel %s', post.filename)
            return None


def _set_facebook_cover(post: ReelPost) -> None:
    """Give the Facebook reel the cover frame Instagram gets.

    Without a frame (0, reels from before the renderer chose one) Facebook
    picks its own. A failure only costs the cover, never the reel.
    """
    from .services import facebook

    if post.thumb_offset_ms <= 0:
        return
    image = cover_frame(post)
    if not image:
        return
    try:
        facebook.set_cover(ToolsConfig.get_config(), post.facebook_video_id, image)
    except facebook.FacebookError as exc:
        logger.warning('Facebook cover of post %s not set: %s', post.pk, exc)


def check_facebook(post: ReelPost) -> str:
    """Check the Facebook reel once; ``'published'``, ``'failed'`` or ``'wait'``."""
    from .services import facebook

    config = ToolsConfig.get_config()
    try:
        state, detail = facebook.reel_status(config, post.facebook_video_id)
    except facebook.FacebookError as exc:
        _fail_facebook(post, str(exc))
        return 'failed'
    if state == 'error':
        _fail_facebook(post, f'Facebook could not process the reel: {detail}'.strip(': '))
        return 'failed'
    if state == 'published':
        post.facebook_status = ReelPost.FACEBOOK_PUBLISHED
        post.facebook_permalink = detail
        post.facebook_published_at = timezone.now()
        post.facebook_error = ''
        post.save(update_fields=['facebook_status', 'facebook_permalink', 'facebook_published_at',
                                 'facebook_error', 'updated_at'])
        return 'published'
    post.facebook_checks += 1
    post.save(update_fields=['facebook_checks', 'updated_at'])
    if post.facebook_checks >= FACEBOOK_CHECK_LIMIT:
        _fail_facebook(post, 'Facebook is still processing the reel after 15 minutes; '
                             'check the page before publishing it there again.')
        return 'failed'
    return 'wait'


def renew_token() -> bool:
    """Renew an Instagram Login token older than a week; True if renewed."""
    config = ToolsConfig.get_config()
    if not config.is_instagram_configured() or config.instagram_api_host != 'graph.instagram.com':
        return False
    last = config.instagram_token_refreshed_at
    if last and timezone.now() - last < timedelta(days=7):
        return False
    token, _expires = instagram.refresh_token(config)
    ToolsConfig.objects.filter(pk=config.pk).update(
        instagram_access_token=token, instagram_token_refreshed_at=timezone.now())
    return True


# ---------------------------------------------------------------------------
# Mail links: approve from the morning reminder, story reminder afterwards
# ---------------------------------------------------------------------------

APPROVAL_SALT = 'tools.reel_post_approval'
# The link in the morning mail stays valid for the broadcast day and the night.
APPROVAL_MAX_AGE = 36 * 60 * 60
# Reposting the reel as a story follows half an hour after publishing.
STORY_REMINDER_DELAY = 30 * 60


def approval_token(post: ReelPost) -> str:
    from django.core import signing
    return signing.dumps({'post': post.pk}, salt=APPROVAL_SALT)


def post_from_token(token: str) -> ReelPost | None:
    from django.core import signing
    try:
        data = signing.loads(token, salt=APPROVAL_SALT, max_age=APPROVAL_MAX_AGE)
    except signing.BadSignature:
        return None
    return ReelPost.objects.select_related('license').filter(pk=data.get('post')).first()


def approval_url(post: ReelPost) -> str:
    from .tasks import _absolute_url
    from django.urls import reverse
    return _absolute_url(reverse('tools:reel_post_approve', args=[approval_token(post)]))


def reminder_info(filename: str, number=None) -> dict | None:
    """What the morning mail says about the Instagram post of a reel."""
    config = ToolsConfig.get_config()
    if not config.is_instagram_configured():
        return None
    post = ReelPost.objects.filter(filename=Path(str(filename)).name).first()
    if post is None:
        # Reels rendered before posting was switched on get their draft now.
        post = create_draft(filename, number)
    if post is None:
        return None
    info = {
        'status': post.status,
        'status_label': str(post.get_status_display()),
        'scheduled_at': post.scheduled_at,
        'permalink': post.permalink,
        'error': post.error_message,
        'approve_url': '',
    }
    if post.status in (ReelPost.STATUS_DRAFT, ReelPost.STATUS_FAILED):
        info['approve_url'] = approval_url(post)
    return info


def approve_from_mail(post: ReelPost) -> None:
    """Approval through the mail link: publish right away."""
    approve(post, None, now=True)
    from .tasks import publish_due_reel_posts
    publish_due_reel_posts.delay()


def send_story_reminder(post: ReelPost) -> None:
    """Remind staff to share the published reel as a story with the link sticker."""
    from django.conf import settings
    from django.utils import translation

    config = ToolsConfig.get_config()
    license_obj = post.license
    context = {
        'post': post,
        'title': getattr(license_obj, 'title', '') or post.filename,
        'number': getattr(license_obj, 'number', ''),
        'permalink': post.permalink,
        'mediathek_url': mediathek_url(license_obj),
    }
    try:
        from notifications.services import emit
        emit('tools.instagram_story_reminder', obj=post,
             payload={'title': context['title'], 'mediathek': context['mediathek_url']},
             dedup_key=f'tools.instagram_story_reminder|{post.pk}')
    except Exception:
        logger.exception('Could not raise the story reminder for post %s', post.pk)

    if not config.reel_reminder_recipient_email:
        return
    try:
        from registration.email import send_mail
        language = (getattr(settings, 'LANGUAGE_CODE', 'de') or 'de').split('-')[0]
        with translation.override(language):
            send_mail(
                subject_template_name='email/reel_story_reminder_subject.txt',
                email_template_name='email/reel_story_reminder_body.txt',
                html_email_template_name='email/reel_story_reminder_body.html',
                context=context,
                from_email=(getattr(settings, 'DEFAULT_FROM_EMAIL', '')
                            or getattr(settings, 'EMAIL_HOST_USER', '') or ''),
                to_email=config.reel_reminder_recipient_email,
            )
    except Exception:
        logger.exception('Could not send the story reminder for post %s', post.pk)
