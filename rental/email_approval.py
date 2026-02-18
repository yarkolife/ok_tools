"""
Email-based approval for user-created rental requests.

All user-visible strings are English and wrapped for translation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from registration.email import send_mail

import logging


UserModel = get_user_model()
logger = logging.getLogger('django')


APPROVAL_SALT = "rental-approval"


@dataclass(frozen=True)
class ApprovalLinks:
    approve_url: str
    deny_url: str


def _get_site_base_url() -> str:
    from .config import get_rental_site_base_url
    base_url = get_rental_site_base_url() or ""
    return base_url.rstrip("/")


def _build_rental_request_urls(*, rental_request) -> dict[str, str]:
    from .config import get_rental_request_url_template
    user_url = ""
    url_template = get_rental_request_url_template() or ""
    if url_template:
        try:
            user_url = url_template.format(rental_id=int(rental_request.id))
        except Exception:
            user_url = ""

    base = _get_site_base_url()
    staff_url = ""
    if base:
        try:
            path = reverse("rental:rental_detail", kwargs={"rental_id": int(rental_request.id)})
            staff_url = f"{base}{path}"
        except Exception:
            staff_url = ""

    return {
        "user_rental_url": user_url,
        "staff_rental_url": staff_url,
    }


def _build_rental_summary_context(*, rental_request) -> dict[str, Any]:
    items = []
    for item in rental_request.items.select_related("inventory_item").all():
        items.append({
            "name": str(item.inventory_item),
            "quantity": item.quantity_requested,
        })

    rooms = []
    for room_rental in rental_request.room_rentals.select_related("room").all():
        rooms.append({
            "name": room_rental.room.name,
            "people_count": room_rental.people_count,
            "start": room_rental.get_start_date(),
            "end": room_rental.get_end_date(),
        })

    return {
        "items": items,
        "rooms": rooms,
        "items_total": rental_request.total_items_count,
        "rooms_total": rental_request.total_rooms_count,
        **_build_rental_request_urls(rental_request=rental_request),
    }


def _get_recipients() -> list[str]:
    from .config import get_rental_approval_recipient_emails
    explicit = get_rental_approval_recipient_emails()
    if explicit:
        return explicit

    # Fallback: notify all active staff users with an email.
    qs = UserModel.objects.filter(is_active=True, is_staff=True).exclude(email__isnull=True).exclude(email="")
    return [u.email for u in qs]


def make_approval_token(*, rental_id: int, action: str) -> str:
    """
    Create a signed, timestamped token for approve/deny actions.

    Token is URL-safe.
    """
    payload = {"rental_id": int(rental_id), "action": str(action)}
    return signing.dumps(payload, salt=APPROVAL_SALT)


def load_approval_token(token: str, *, max_age_seconds: int = None) -> dict[str, Any]:
    """Validate and decode a signed token."""
    if max_age_seconds is None:
        from .config import get_rental_approval_token_max_age_seconds
        max_age_seconds = get_rental_approval_token_max_age_seconds()
    return signing.loads(token, salt=APPROVAL_SALT, max_age=max_age_seconds)


def build_approval_links(*, rental_id: int) -> ApprovalLinks:
    base = _get_site_base_url()

    approve_token = make_approval_token(rental_id=rental_id, action="approve")
    deny_token = make_approval_token(rental_id=rental_id, action="deny")

    approve_path = reverse("rental:email_approval_action", kwargs={"rental_id": rental_id, "action": "approve", "token": approve_token})
    deny_path = reverse("rental:email_approval_action", kwargs={"rental_id": rental_id, "action": "deny", "token": deny_token})

    return ApprovalLinks(
        approve_url=f"{base}{approve_path}",
        deny_url=f"{base}{deny_path}",
    )


def send_admin_approval_email(*, rental_request) -> None:
    """
    Notify admins about a new user-created rental request that needs approval.

    This function should not raise: failures must not block rental creation.
    """
    recipients = _get_recipients()
    if not recipients:
        return

    links = build_approval_links(rental_id=int(rental_request.id))

    # Get user name from profile if available
    user_first_name = ""
    user_last_name = ""
    user_email = getattr(rental_request.user, "email", "")
    
    try:
        profile = getattr(rental_request.user, "profile", None)
        if profile:
            user_first_name = getattr(profile, "first_name", "") or ""
            user_last_name = getattr(profile, "last_name", "") or ""
    except Exception:
        pass  # Profile might not exist, use empty strings

    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "project_name": rental_request.project_name,
        "purpose": rental_request.purpose,
        "user_first_name": user_first_name,
        "user_last_name": user_last_name,
        "user_email": user_email,
        "start": rental_request.requested_start_date,
        "end": rental_request.requested_end_date,
        "approve_url": links.approve_url,
        "deny_url": links.deny_url,
    }
    context.update(_build_rental_request_urls(rental_request=rental_request))

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    # Activate German language for email
    translation.activate('de')
    try:
        for to_email in recipients:
            try:
                send_mail(
                    subject_template_name="email/rental_request_approval_subject.txt",
                    email_template_name="email/rental_request_approval_body.txt",
                    html_email_template_name="email/rental_request_approval_body.html",
                    context=context,
                    from_email=from_email,
                    to_email=to_email,
                )
            except Exception:
                # Email failures must not block the main flow.
                logger.exception(
                    "Failed to send rental approval email to %s (rental_request_id=%s)",
                    to_email,
                    rental_request.id,
                )
    finally:
        translation.deactivate()


def send_user_pending_email(*, rental_request) -> None:
    """
    Notify user that their rental request is pending approval.

    This function should not raise: failures must not block rental creation.
    """
    user_email = getattr(rental_request.user, "email", None)
    if not user_email:
        return

    # Get contact email from settings (OK_EMAIL or fallback to EMAIL_HOST_USER)
    contact_email = getattr(settings, "OK_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "") or ""

    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "project_name": rental_request.project_name,
        "purpose": rental_request.purpose,
        "start": rental_request.requested_start_date,
        "end": rental_request.requested_end_date,
        "contact_email": contact_email,
    }
    context.update(_build_rental_summary_context(rental_request=rental_request))

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    # Activate German language for email
    translation.activate('de')
    try:
        send_mail(
            subject_template_name="email/rental_request_pending_subject.txt",
            email_template_name="email/rental_request_pending_body.txt",
            html_email_template_name="email/rental_request_pending_body.html",
            context=context,
            from_email=from_email,
            to_email=user_email,
        )
    except Exception:
        logger.exception(
            "Failed to send pending email to user %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    finally:
        translation.deactivate()


def send_user_approved_email(*, rental_request) -> None:
    """
    Notify user that their rental request has been approved.

    This function should not raise: failures must not block approval.
    """
    user_email = getattr(rental_request.user, "email", None)
    if not user_email:
        return

    # Get contact email from settings (OK_EMAIL or fallback to EMAIL_HOST_USER)
    contact_email = getattr(settings, "OK_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "") or ""

    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "project_name": rental_request.project_name,
        "purpose": rental_request.purpose,
        "start": rental_request.requested_start_date,
        "end": rental_request.requested_end_date,
        "contact_email": contact_email,
    }
    context.update(_build_rental_summary_context(rental_request=rental_request))

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    # Activate German language for email
    translation.activate('de')
    try:
        send_mail(
            subject_template_name="email/rental_request_approved_subject.txt",
            email_template_name="email/rental_request_approved_body.txt",
            html_email_template_name="email/rental_request_approved_body.html",
            context=context,
            from_email=from_email,
            to_email=user_email,
        )
    except Exception:
        logger.exception(
            "Failed to send approved email to user %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    finally:
        translation.deactivate()


def send_user_declined_email(*, rental_request) -> None:
    """
    Notify user that their rental request has been declined.

    This function should not raise: failures must not block decline.
    """
    user_email = getattr(rental_request.user, "email", None)
    if not user_email:
        return

    # Get contact email from settings (OK_EMAIL or fallback to EMAIL_HOST_USER)
    contact_email = getattr(settings, "OK_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "") or ""

    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "project_name": rental_request.project_name,
        "purpose": rental_request.purpose,
        "start": rental_request.requested_start_date,
        "end": rental_request.requested_end_date,
        "contact_email": contact_email,
    }
    context.update(_build_rental_summary_context(rental_request=rental_request))

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    # Activate German language for email
    translation.activate('de')
    try:
        send_mail(
            subject_template_name="email/rental_request_declined_subject.txt",
            email_template_name="email/rental_request_declined_body.txt",
            html_email_template_name="email/rental_request_declined_body.html",
            context=context,
            from_email=from_email,
            to_email=user_email,
        )
    except Exception:
        logger.exception(
            "Failed to send declined email to user %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    finally:
        translation.deactivate()

