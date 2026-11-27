"""QR signing sessions: lifetime, creation, e-mailed links, revocation.

Every session lives ``LicensesConfig.sign_session_minutes`` (default 10).
Only a session created for one license from its admin page may live longer
(``LONG_LINK_DAYS``), e.g. for a link e-mailed to someone who signs days
later. Such a session is bound to the license, so the signature is stored
on the license when it is submitted, with no page open on the staff side.
"""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from licenses.models import SigningSession
from licenses.models import SigningSessionStatus
import datetime
import logging
import uuid


logger = logging.getLogger('django')

DEFAULT_SESSION_MINUTES = 10
# Lifetimes staff can choose for one license's link (days).
LONG_LINK_DAYS = (1, 3, 7)


def default_session_lifetime() -> datetime.timedelta:
    """Lifetime of an ordinary QR session, from the licenses configuration."""
    minutes = DEFAULT_SESSION_MINUTES
    try:
        from licenses.models import LicensesConfig
        minutes = int(LicensesConfig.get_config().sign_session_minutes or 0)
    except Exception:
        logger.debug('Licenses configuration not readable; QR session lifetime %d min',
                     DEFAULT_SESSION_MINUTES, exc_info=True)
    if minutes <= 0:
        minutes = DEFAULT_SESSION_MINUTES
    return datetime.timedelta(minutes=minutes)


def create_session(owner, license_obj=None, lifetime=None) -> SigningSession:
    """Create a pending session; ``lifetime`` defaults to the configured one."""
    return SigningSession.objects.create(
        license=license_obj,
        owner=owner,
        token=uuid.uuid4().hex,
        status=SigningSessionStatus.PENDING,
        expires_at=timezone.now() + (lifetime or default_session_lifetime()),
    )


def create_long_link(license_obj, owner, days: int) -> SigningSession:
    """Create a session for one license that stays open for ``days`` days."""
    if days not in LONG_LINK_DAYS:
        raise ValueError(f'days must be one of {LONG_LINK_DAYS}')
    if license_obj.confirmed:
        raise ValueError('confirmed license')
    return create_session(owner, license_obj, datetime.timedelta(days=days))


def open_links(license_obj):
    """Pending, not yet expired sessions bound to this license."""
    return SigningSession.objects.filter(
        license=license_obj,
        status=SigningSessionStatus.PENDING,
        expires_at__gt=timezone.now(),
    ).order_by('expires_at')


def revoke(session: SigningSession) -> bool:
    """Close a pending session; returns False when it was no longer pending."""
    updated = SigningSession.objects.filter(
        pk=session.pk, status=SigningSessionStatus.PENDING,
    ).update(status=SigningSessionStatus.CANCELLED)
    return bool(updated)


def sign_url(session: SigningSession, request=None) -> str:
    """Absolute URL of the public signing page of ``session``."""
    path = reverse('licenses:sign_session_page', kwargs={'token': session.token})
    if request is not None:
        return request.build_absolute_uri(path)
    from licenses.tasks import _absolute_url
    return _absolute_url(path) or path


def recipient_email(license_obj) -> str:
    """E-mail address of the license holder, '' when there is none."""
    profile = getattr(license_obj, 'profile', None)
    user = getattr(profile, 'okuser', None) if profile else None
    return (getattr(user, 'email', None) or '').strip()


def send_link_email(session: SigningSession, url: str) -> str:
    """Send the signing link to the license holder; returns the address.

    Raises ``ValueError`` when the holder has no e-mail address. Mail errors
    propagate, so the admin can tell the staff member it was not sent.
    """
    from licenses.tasks import _get_contact_email
    from licenses.tasks import _get_ok_name
    from registration.email import send_mail

    license_obj = session.license
    to_email = recipient_email(license_obj)
    if not to_email:
        raise ValueError('no e-mail address')
    profile = license_obj.profile
    context = {
        'ok_name': _get_ok_name(),
        'contact_email': _get_contact_email(),
        'first_name': getattr(profile, 'first_name', '') or '',
        'license_number': int(license_obj.number),
        'license_title': license_obj.title or str(license_obj),
        'sign_url': url,
        'expires_at': timezone.localtime(session.expires_at),
    }
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '')
                  or getattr(settings, 'EMAIL_HOST_USER', '') or '')
    language = (getattr(settings, 'LANGUAGE_CODE', 'de') or 'de').split('-')[0]
    with translation.override(language):
        send_mail(
            subject_template_name='email/license_sign_link_subject.txt',
            email_template_name='email/license_sign_link_body.txt',
            html_email_template_name='email/license_sign_link_body.html',
            context=context,
            from_email=from_email,
            to_email=to_email,
        )
    logger.info('Signing link for license %s sent to %s (expires %s)',
                license_obj.number, to_email, session.expires_at.isoformat())
    return to_email
