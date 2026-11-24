"""Posts from submission to publication.

draft -> submitted (approvers are told) -> approved (by one approver) ->
publishing (at ``publish_at`` or right away) -> published / partial / failed.

Every platform of a post (:class:`BeitragZiel`) is published on its own and
keeps its own status; a failure on one platform never undoes the others, and
publishing again only retries the platforms that are not published yet.
"""

from .models import PLATFORM_FACEBOOK
from .models import PLATFORM_INSTAGRAM
from .models import PLATFORM_MASTODON
from .models import PLATFORM_WEBSITE
from .models import Beitrag
from .models import BeitragZiel
from .models import BeitragsConfig
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
import logging
import re
import time


logger = logging.getLogger('django')

INSTAGRAM_CAPTION_MAX = 2200
INSTAGRAM_MAX_HASHTAGS = 5
# Photo containers are usually ready within seconds.
INSTAGRAM_CHECKS = 20
INSTAGRAM_CHECK_PAUSE = 3


# ---------------------------------------------------------------------------
# Texts per platform
# ---------------------------------------------------------------------------

def hashtags(text: str) -> str:
    """Normalise "a, #b c" to "#a #b #c"."""
    words = [w.strip().lstrip('#') for w in re.split(r'[\s,;]+', text or '') if w.strip().lstrip('#')]
    seen, result = set(), []
    for word in words:
        if word.lower() not in seen:
            seen.add(word.lower())
            result.append(f'#{word}')
    return ' '.join(result)


def _join(*parts) -> str:
    return '\n\n'.join(part.strip() for part in parts if part and part.strip())


URL_LINE = re.compile(r'https?://\S+')


def _kind(line: str) -> str:
    line = line.strip()
    if not line:
        return 'blank'
    if URL_LINE.fullmatch(line):
        return 'link'
    if all(word.startswith('#') for word in line.split()):
        return 'tags'
    return 'text'


def tidy(text: str) -> str:
    """An empty line before and after a link line and before the hashtags.

    People edit the platform texts by hand and often leave the link and the
    hashtags glued to the text; on Facebook and Instagram that reads badly.
    """
    out, last = [], None
    for line in (text or '').replace('\r\n', '\n').split('\n'):
        kind = _kind(line)
        if kind != 'blank' and last not in (None, 'blank', kind) and (
                'link' in (kind, last) or kind == 'tags'):
            out.append('')
        out.append(line.rstrip())
        last = kind
    return '\n'.join(out).strip()


def compose(beitrag: Beitrag, plattform: str) -> str:
    """The text of a platform as built from the post and its topic."""
    thema = beitrag.thema
    if plattform == PLATFORM_INSTAGRAM:
        # Links are not clickable on Instagram; the signature may say "Link in Bio".
        return _join(beitrag.titel, beitrag.text, thema.signatur_instagram, hashtags(thema.hashtags))
    if plattform == PLATFORM_FACEBOOK:
        return _join(beitrag.titel, beitrag.text, beitrag.link, thema.signatur_facebook,
                     hashtags(thema.hashtags))
    if plattform == PLATFORM_MASTODON:
        return _join(beitrag.titel, beitrag.text, beitrag.link, thema.signatur_mastodon,
                     hashtags(thema.hashtags))
    # Website: the title is the post title; the photos are added when
    # publishing, the topic's tags become WordPress tags.
    return _join(beitrag.text, beitrag.link, thema.signatur_website)


def ensure_ziele(beitrag: Beitrag, platforms=None) -> list[BeitragZiel]:
    """Create the platforms of a post and refresh texts nobody has edited.

    ``platforms`` (a list) switches platforms on or off; by default new
    platforms follow the topic and the configured channels.
    """
    config = BeitragsConfig.get_config()
    available = config.configured_platforms()
    defaults = {
        PLATFORM_INSTAGRAM: beitrag.thema.instagram,
        PLATFORM_FACEBOOK: beitrag.thema.facebook,
        PLATFORM_WEBSITE: beitrag.thema.website,
        PLATFORM_MASTODON: beitrag.thema.mastodon,
    }
    ziele = []
    for plattform in (PLATFORM_INSTAGRAM, PLATFORM_FACEBOOK, PLATFORM_WEBSITE, PLATFORM_MASTODON):
        ziel = beitrag.ziele.filter(plattform=plattform).first()
        if ziel is None:
            if plattform not in available:
                continue
            ziel = BeitragZiel(beitrag=beitrag, plattform=plattform, aktiv=defaults[plattform])
        if platforms is not None:
            ziel.aktiv = plattform in platforms and plattform in available
        if not ziel.text_bearbeitet and ziel.status not in DONE:
            ziel.text = compose(beitrag, plattform)
        ziel.save()
        ziele.append(ziel)
    return ziele


def mark_edited(ziel: BeitragZiel) -> None:
    """Keep a hand-written text from being rebuilt."""
    ziel.text = tidy(ziel.text)
    ziel.text_bearbeitet = ziel.text.strip() != compose(ziel.beitrag, ziel.plattform).strip()


# ---------------------------------------------------------------------------
# Checks before approval
# ---------------------------------------------------------------------------

def problems(beitrag: Beitrag) -> list[str]:
    """What would stop the post; empty if it can be approved."""
    found = []
    ziele = [z for z in beitrag.ziele.all() if z.aktiv and z.status not in DONE]
    if not ziele:
        found.append(_('No platform is switched on for this post.'))
    fotos = beitrag.fotos.count()
    if fotos > Beitrag.MAX_PHOTOS:
        found.append(_('At most %(max)s photos.') % {'max': Beitrag.MAX_PHOTOS})
    if fotos and not beitrag.einwilligung:
        found.append(_('Confirm that the people on the photos agreed to the publication.'))
    for ziel in ziele:
        if ziel.plattform == PLATFORM_INSTAGRAM:
            if not fotos:
                found.append(_('Instagram needs at least one photo.'))
            if len(ziel.text) > INSTAGRAM_CAPTION_MAX:
                found.append(_('The Instagram text has %(count)s of at most %(max)s characters.') % {
                    'count': len(ziel.text), 'max': INSTAGRAM_CAPTION_MAX})
            tags = len(re.findall(r'#\w', ziel.text))
            if tags > INSTAGRAM_MAX_HASHTAGS:
                found.append(_('The Instagram text has %(count)s hashtags; Instagram allows %(max)s.') % {
                    'count': tags, 'max': INSTAGRAM_MAX_HASHTAGS})
        if ziel.plattform == PLATFORM_FACEBOOK and not (fotos or ziel.text.strip()):
            found.append(_('The Facebook post is empty.'))
        if ziel.plattform == PLATFORM_MASTODON:
            from .services import mastodon

            limit = BeitragsConfig.get_config().mastodon_max_characters
            count = mastodon.length(ziel.text)
            if count > limit:
                found.append(_('The Mastodon text has %(count)s of at most %(max)s characters '
                               '(links count as 23).') % {'count': count, 'max': limit})
            if not (fotos or ziel.text.strip()):
                found.append(_('The Mastodon post is empty.'))
    return found


# ---------------------------------------------------------------------------
# Submission, approval, rejection
# ---------------------------------------------------------------------------

# Platforms that are finished: published, or taken off again.
DONE = (BeitragZiel.STATUS_PUBLISHED, BeitragZiel.STATUS_WITHDRAWN)


def submit(beitrag: Beitrag) -> None:
    """Hand the post to the approvers."""
    ensure_ziele(beitrag)
    beitrag.status = Beitrag.STATUS_SUBMITTED
    beitrag.rejection_note = ''
    beitrag.save(update_fields=['status', 'rejection_note', 'updated_at'])
    from .notify import tell_approvers
    tell_approvers(beitrag)


def approve(beitrag: Beitrag, user) -> None:
    """One approval publishes the post on every platform switched on for it."""
    if not beitrag.may_approve(user):
        raise PermissionDenied(_('You may not approve posts of this topic.'))
    if beitrag.status not in (Beitrag.STATUS_DRAFT, Beitrag.STATUS_SUBMITTED,
                              Beitrag.STATUS_REJECTED, Beitrag.STATUS_FAILED,
                              Beitrag.STATUS_PARTIAL):
        raise ValidationError(_('This post is already %(status)s.') % {
            'status': beitrag.get_status_display().lower()})
    found = problems(beitrag)
    if found:
        raise ValidationError(found)
    beitrag.status = Beitrag.STATUS_APPROVED
    beitrag.approved_by = user
    beitrag.approved_at = timezone.now()
    beitrag.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
    if is_due(beitrag):
        from .tasks import publish_beitrag
        transaction.on_commit(lambda: publish_beitrag.delay(beitrag.pk))


def reject(beitrag: Beitrag, user, note: str = '') -> None:
    """Send the post back to its author."""
    if not beitrag.may_approve(user):
        raise PermissionDenied(_('You may not approve posts of this topic.'))
    beitrag.status = Beitrag.STATUS_REJECTED
    beitrag.rejection_note = note
    beitrag.save(update_fields=['status', 'rejection_note', 'updated_at'])
    from .notify import tell_author_rejected
    tell_author_rejected(beitrag, user)


def unapprove(beitrag: Beitrag, user) -> bool:
    """Hold back an approved post that has not started; it waits for approval again."""
    if not beitrag.may_approve(user):
        raise PermissionDenied(_('You may not approve posts of this topic.'))
    held = Beitrag.objects.filter(pk=beitrag.pk, status=Beitrag.STATUS_APPROVED).update(
        status=Beitrag.STATUS_SUBMITTED, approved_by=None, approved_at=None, updated_at=timezone.now())
    beitrag.refresh_from_db()
    return bool(held)


def withdraw(beitrag: Beitrag, user, platforms=None) -> list[str]:
    """Take the post off the chosen platforms (all published ones by default).

    The website post goes to the trash of WordPress (it can be restored
    there), Facebook, Instagram and Mastodon delete it. A platform that refuses keeps
    its state and its error; the errors are returned.
    """
    if not beitrag.may_approve(user):
        raise PermissionDenied(_('You may not approve posts of this topic.'))
    removers = {
        PLATFORM_INSTAGRAM: _withdraw_instagram,
        PLATFORM_FACEBOOK: _withdraw_facebook,
        PLATFORM_WEBSITE: _withdraw_website,
        PLATFORM_MASTODON: _withdraw_mastodon,
    }
    errors = []
    ziele = beitrag.ziele.filter(status=BeitragZiel.STATUS_PUBLISHED)
    if platforms is not None:
        ziele = ziele.filter(plattform__in=list(platforms))
    for ziel in ziele:
        try:
            if ziel.remote_id:
                removers[ziel.plattform](ziel.remote_id)
        except Exception as exc:
            logger.warning('Withdrawing post %s from %s failed: %r', beitrag.pk, ziel.plattform, exc)
            ziel.error = str(exc)[:2000]
            ziel.save(update_fields=['error'])
            errors.append(f'{ziel.get_plattform_display()}: {exc}')
            continue
        ziel.status = BeitragZiel.STATUS_WITHDRAWN
        ziel.error = ''
        ziel.save(update_fields=['status', 'error'])
    if not beitrag.ziele.filter(status=BeitragZiel.STATUS_PUBLISHED).exists():
        beitrag.status = Beitrag.STATUS_WITHDRAWN
    elif not beitrag.ziele.filter(aktiv=True).exclude(status__in=DONE).exists():
        beitrag.status = Beitrag.STATUS_PUBLISHED
    beitrag.save(update_fields=['status', 'updated_at'])
    return errors


def _withdraw_instagram(remote_id):
    from tools.services import instagram
    instagram.delete_media(BeitragsConfig.meta_config(), remote_id)


def _withdraw_facebook(remote_id):
    from tools.services import facebook
    facebook.delete_post(BeitragsConfig.meta_config(), remote_id)


def _withdraw_website(remote_id):
    from .services import wordpress
    wordpress.trash_post(BeitragsConfig.get_config(), remote_id)


def _withdraw_mastodon(remote_id):
    from .services import mastodon
    mastodon.delete_status(BeitragsConfig.get_config(), remote_id)


def is_due(beitrag: Beitrag) -> bool:
    return beitrag.status == Beitrag.STATUS_APPROVED and (
        beitrag.publish_at is None or beitrag.publish_at <= timezone.now())


def due_posts():
    from django.db.models import Q

    return Beitrag.objects.filter(status=Beitrag.STATUS_APPROVED).filter(
        Q(publish_at__isnull=True) | Q(publish_at__lte=timezone.now()))


# ---------------------------------------------------------------------------
# Publishing (Celery)
# ---------------------------------------------------------------------------

def claim(beitrag_id: int) -> Beitrag | None:
    """Move an approved post to "publishing"; None if somebody else has it."""
    with transaction.atomic():
        claimed = Beitrag.objects.filter(pk=beitrag_id, status=Beitrag.STATUS_APPROVED).update(
            status=Beitrag.STATUS_PUBLISHING, updated_at=timezone.now())
    return Beitrag.objects.select_related('thema').get(pk=beitrag_id) if claimed else None


def publish(beitrag: Beitrag) -> str:
    """Publish every open platform; return the resulting post status."""
    for ziel in beitrag.ziele.filter(aktiv=True).exclude(status__in=DONE):
        ziel.status = BeitragZiel.STATUS_PUBLISHING
        ziel.error = ''
        ziel.save(update_fields=['status', 'error'])
        try:
            publisher = {
                PLATFORM_INSTAGRAM: _publish_instagram,
                PLATFORM_FACEBOOK: _publish_facebook,
                PLATFORM_WEBSITE: _publish_website,
                PLATFORM_MASTODON: _publish_mastodon,
            }[ziel.plattform]
            remote_id, link = publisher(beitrag, ziel)
        except Exception as exc:  # any platform error stays with that platform
            logger.warning('Post %s on %s failed: %r', beitrag.pk, ziel.plattform, exc)
            ziel.status = BeitragZiel.STATUS_FAILED
            ziel.error = str(exc)[:2000]
            ziel.save(update_fields=['status', 'error'])
            continue
        ziel.status = BeitragZiel.STATUS_PUBLISHED
        ziel.remote_id = str(remote_id)
        ziel.permalink = link or ''
        ziel.published_at = timezone.now()
        ziel.save(update_fields=['status', 'remote_id', 'permalink', 'published_at', 'error'])

    active = list(beitrag.ziele.filter(aktiv=True).exclude(status=BeitragZiel.STATUS_WITHDRAWN))
    done = [z for z in active if z.status == BeitragZiel.STATUS_PUBLISHED]
    if active and len(done) == len(active):
        beitrag.status = Beitrag.STATUS_PUBLISHED
    elif done:
        beitrag.status = Beitrag.STATUS_PARTIAL
    else:
        beitrag.status = Beitrag.STATUS_FAILED
    beitrag.save(update_fields=['status', 'updated_at'])
    if beitrag.status != Beitrag.STATUS_PUBLISHED:
        from .notify import tell_failed
        tell_failed(beitrag)
    return beitrag.status


def retry(beitrag: Beitrag) -> bool:
    """Publish the platforms that failed once more; True if started."""
    if beitrag.status not in (Beitrag.STATUS_PARTIAL, Beitrag.STATUS_FAILED):
        return False
    beitrag.status = Beitrag.STATUS_APPROVED
    beitrag.save(update_fields=['status', 'updated_at'])
    from .tasks import publish_beitrag
    transaction.on_commit(lambda: publish_beitrag.delay(beitrag.pk))
    return True


def absolute_url(path: str) -> str:
    """``SITE_BASE_URL`` + path, or '' while the base address is not set."""
    from django.conf import settings

    base = (getattr(settings, 'SITE_BASE_URL', '') or '').rstrip('/')
    return f'{base}{path}' if base else ''


def photo_url(foto, variant: str) -> str:
    """Public address of a photo rendition (Meta downloads it from there)."""
    from django.urls import reverse

    return absolute_url(reverse('beitraege:foto', args=[foto.token, variant]))


def _require_https(url: str) -> str:
    if not url.startswith('https://'):
        raise ValidationError(
            'SITE_BASE_URL must be a public https address; Instagram and Facebook download the photos from there.')
    return url


def _publish_instagram(beitrag: Beitrag, ziel: BeitragZiel):
    from tools.services import instagram

    config = BeitragsConfig.meta_config()
    fotos = list(beitrag.fotos.all())
    urls = [_require_https(photo_url(f, 'instagram')) for f in fotos]
    if len(urls) == 1:
        container = instagram.create_image_container(config, image_url=urls[0], caption=ziel.text)
    else:
        children = [instagram.create_image_container(config, image_url=u, carousel_item=True)
                    for u in urls]
        for child in children:
            _wait_for_container(config, child)
        container = instagram.create_carousel_container(config, children=children, caption=ziel.text)
    _wait_for_container(config, container)
    media_id = instagram.publish_container(config, container)
    return media_id, instagram.media_permalink(config, media_id)


def _wait_for_container(config, container_id: str) -> None:
    from tools.services import instagram

    for _attempt in range(INSTAGRAM_CHECKS):
        code, text = instagram.container_status(config, container_id)
        if code in ('FINISHED', 'PUBLISHED'):
            return
        if code in ('ERROR', 'EXPIRED'):
            raise instagram.InstagramError(f'Instagram could not process the photo: {code} {text}'.strip())
        time.sleep(INSTAGRAM_CHECK_PAUSE)
    raise instagram.InstagramError('Instagram is still processing the photos; publish the post again later.')


def _publish_facebook(beitrag: Beitrag, ziel: BeitragZiel):
    from tools.services import facebook

    config = BeitragsConfig.meta_config()
    urls = [_require_https(photo_url(f, 'web')) for f in beitrag.fotos.all()]
    post_id = facebook.publish_photos(config, image_urls=urls, message=ziel.text)
    return post_id, facebook.post_permalink(config, post_id)


def _publish_mastodon(beitrag: Beitrag, ziel: BeitragZiel):
    from .services import images
    from .services import mastodon

    config = BeitragsConfig.get_config()
    media_ids = []
    for index, foto in enumerate(beitrag.fotos.all()[:config.mastodon_max_photos], start=1):
        with foto.bild.open('rb') as handle:
            content = images.rendition(handle, 'web')
        media_ids.append(mastodon.upload_media(
            config, f'beitrag-{beitrag.pk}-{index}.jpg', content, description=beitrag.titel))
    status = mastodon.post_status(config, ziel.text, media_ids, visibility=config.mastodon_visibility,
                                  key=f'oktools-beitrag-{beitrag.pk}-{ziel.pk}')
    return status['id'], status['url']


def _publish_website(beitrag: Beitrag, ziel: BeitragZiel):
    from .services import images
    from .services import wordpress

    config = BeitragsConfig.get_config()
    media = []
    for index, foto in enumerate(beitrag.fotos.all(), start=1):
        with foto.bild.open('rb') as handle:
            content = images.rendition(handle, 'web')
        media.append(wordpress.upload_media(
            config, f'beitrag-{beitrag.pk}-{index}.jpg', content, alt=beitrag.titel))
    content = wordpress.paragraphs(ziel.text)
    if beitrag.link and beitrag.link not in ziel.text:  # texts written before 4.85
        from html import escape
        content += f'\n<p><a href="{escape(beitrag.link)}">{escape(beitrag.link)}</a></p>'
    if len(media) > 1:
        content += '\n' + wordpress.gallery_block(media)
    thema = beitrag.thema
    post = wordpress.create_post(
        config,
        title=beitrag.titel,
        content=content,
        featured_media=media[0]['id'] if media else None,
        categories=wordpress.term_ids(config, 'categories', thema.wordpress_categories.split(',')),
        tags=wordpress.term_ids(config, 'tags', thema.wordpress_tags.split(',')),
        comments=config.wordpress_comments,
    )
    return post['id'], post['link']
