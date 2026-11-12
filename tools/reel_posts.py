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

_PLACEHOLDER = re.compile(r'\{(\w+)\}')


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
    """Collab usernames for a license, at most the 3 Instagram allows."""
    names = []
    for partner in partners_for(license_obj):
        for name in partner.username_list():
            if name.lower() not in {n.lower() for n in names}:
                names.append(name)
    return names[:ReelPost.MAX_COLLABORATORS]


def _hashtag(tag: str) -> str:
    word = re.sub(r'[^\w]', '', str(tag).replace(' ', ''))
    return f'#{word}' if word else ''


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


def render_caption(template: str, values: dict) -> str:
    """Fill the template; drop lines whose placeholders are all empty."""
    lines = []
    for line in (template or '').replace('\r\n', '\n').split('\n'):
        keys = _PLACEHOLDER.findall(line)
        known = [k for k in keys if k in values]
        if known and not any(str(values[k]).strip() for k in known):
            continue
        lines.append(_PLACEHOLDER.sub(
            lambda m: str(values.get(m.group(1), m.group(0))), line))
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text[:ReelPost.CAPTION_MAX_LENGTH]


def caption_values(license_obj, day: date | None, plan_entry: dict) -> dict:
    """The values for the caption placeholders."""
    author = str(plan_entry.get('sender_responsible') or plan_entry.get('author') or '').strip()
    if not author and license_obj is not None and getattr(license_obj, 'profile', None):
        profile = license_obj.profile
        author = f'{profile.first_name} {profile.last_name}'.strip()
    start = str(plan_entry.get('start') or '')[:5]
    tags = license_obj.tags if license_obj is not None and isinstance(license_obj.tags, list) else []
    return {
        'titel': getattr(license_obj, 'title', '') or str(plan_entry.get('title') or ''),
        'untertitel': getattr(license_obj, 'subtitle', '') or '',
        'beschreibung': getattr(license_obj, 'description', '') or '',
        'autor': author,
        'sendetermin': (
            f'{WEEKDAYS[day.weekday()]}, {day:%d.%m.%Y}' + (f', {start} Uhr' if start else '')
            if day else ''),
        'uhrzeit': start,
        'mediathek': getattr(license_obj, 'mediathek_url', '') or '',
        'hashtags': ' '.join(h for h in (_hashtag(t) for t in tags) if h),
    }


def create_draft(filename: str, number=None) -> ReelPost | None:
    """Create the post draft for a rendered reel (once per file)."""
    config = ToolsConfig.get_config()
    if not config.is_instagram_configured():
        return None
    filename = Path(str(filename)).name
    existing = ReelPost.objects.filter(filename=filename).first()
    if existing:
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
        scheduled_at = timezone.make_aware(datetime.combine(day, config.instagram_post_time))

    post, _created = ReelPost.objects.get_or_create(
        filename=filename,
        defaults={
            'license': license_obj,
            'caption': render_caption(
                config.instagram_caption_template, caption_values(license_obj, day, entry)),
            'collaborators': ', '.join(collaborators_for(license_obj)),
            'share_to_feed': config.instagram_share_to_feed,
            'scheduled_at': scheduled_at,
        },
    )
    return post


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

def approve(post: ReelPost, user, *, now: bool = False) -> None:
    """Approve a draft (or failed) post; ``now`` publishes it right away."""
    post.full_clean()
    post.status = ReelPost.STATUS_APPROVED
    post.approved_by = user
    post.approved_at = timezone.now()
    post.error_message = ''
    if now or not post.scheduled_at:
        post.scheduled_at = timezone.now()
    post.save()


def back_to_draft(post: ReelPost) -> None:
    post.status = ReelPost.STATUS_DRAFT
    post.approved_by = None
    post.approved_at = None
    post.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])


# ---------------------------------------------------------------------------
# Publishing (called from Celery tasks)
# ---------------------------------------------------------------------------

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
        return 'published'

    if status_code == 'PUBLISHED':
        post.status = ReelPost.STATUS_PUBLISHED
        post.published_at = post.published_at or timezone.now()
        post.save(update_fields=['status', 'published_at', 'updated_at'])
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
