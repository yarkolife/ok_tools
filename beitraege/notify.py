"""Tell approvers about new posts and authors about the outcome.

Approvers get an OK-Tools notification and, if switched on, a mail with a
personal signed link: it opens the check page on the phone without logging
in. The link is bound to the approver, so the approval is recorded with the
right name, and it expires after a week.
"""

from .models import Beitrag
from .models import BeitragsConfig
from .models import person_name
from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import translation
import logging


logger = logging.getLogger('django')

TOKEN_SALT = 'beitraege.freigabe'
TOKEN_MAX_AGE = 7 * 24 * 60 * 60


def approval_token(beitrag: Beitrag, user) -> str:
    return signing.dumps({'b': beitrag.pk, 'u': user.pk}, salt=TOKEN_SALT)


def from_token(token: str):
    """``(beitrag, user)`` of a valid link, else ``(None, None)``."""
    from django.contrib.auth import get_user_model

    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None, None
    beitrag = Beitrag.objects.select_related('thema').filter(pk=data.get('b')).first()
    user = get_user_model().objects.filter(pk=data.get('u'), is_active=True).first()
    if beitrag is None or user is None:
        return None, None
    return beitrag, user


def approval_url(beitrag: Beitrag, user) -> str:
    from .workflow import absolute_url

    return absolute_url(reverse('beitraege:freigabe', args=[approval_token(beitrag, user)]))


def _emit(code, beitrag, payload, recipients=None):
    try:
        from notifications.services import emit
    except ImportError:
        return
    try:
        emit(code, obj=beitrag, payload=payload, recipients=recipients,
             dedup_key=f'{code}|{beitrag.pk}|{beitrag.updated_at:%Y%m%d%H%M%S}')
    except Exception:
        logger.exception('Could not raise %s for post %s', code, beitrag.pk)


def _mail(to_email, template, context):
    from registration.email import send_mail

    language = (getattr(settings, 'LANGUAGE_CODE', 'de') or 'de').split('-')[0]
    try:
        with translation.override(language):
            send_mail(
                subject_template_name=f'email/beitrag_{template}_subject.txt',
                email_template_name=f'email/beitrag_{template}_body.txt',
                context=context,
                from_email=(getattr(settings, 'DEFAULT_FROM_EMAIL', '')
                            or getattr(settings, 'EMAIL_HOST_USER', '') or ''),
                to_email=to_email,
            )
    except Exception:
        logger.exception('Could not send the %s mail for a post to %s', template, to_email)


def tell_approvers(beitrag: Beitrag) -> None:
    approvers = list(beitrag.approvers())
    author = beitrag.created_by
    _emit('beitraege.submitted', beitrag, {
        'titel': beitrag.titel,
        'thema': beitrag.thema.name,
        'autor': person_name(author),
    }, recipients=approvers)
    if not BeitragsConfig.get_config().approval_mail:
        return
    for user in approvers:
        _mail(user.email, 'freigabe', {
            'beitrag': beitrag,
            'empfaenger': person_name(user),
            'autor': person_name(author),
            'url': approval_url(beitrag, user),
        })


def tell_author_rejected(beitrag: Beitrag, by) -> None:
    author = beitrag.created_by
    if author is None:
        return
    _emit('beitraege.rejected', beitrag, {
        'titel': beitrag.titel,
        'grund': beitrag.rejection_note[:200],
    }, recipients=[author])
    if author.email:
        from .workflow import absolute_url
        _mail(author.email, 'abgelehnt', {
            'beitrag': beitrag,
            'von': person_name(by),
            'url': absolute_url(reverse('admin:beitraege_beitrag_change', args=[beitrag.pk])),
        })


def tell_failed(beitrag: Beitrag) -> None:
    errors = '; '.join(
        f'{z.get_plattform_display()}: {z.error[:120]}'
        for z in beitrag.ziele.filter(aktiv=True, status='failed'))
    recipients = [u for u in [beitrag.approved_by, beitrag.created_by] if u is not None]
    _emit('beitraege.failed', beitrag, {
        'titel': beitrag.titel,
        'fehler': errors[:300],
    }, recipients=recipients or None)
