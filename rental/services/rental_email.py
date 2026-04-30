"""
Email notifications for rental lifecycle events.

All user-visible strings are English and wrapped for translation.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from registration.email import send_mail

import logging


logger = logging.getLogger('django')


def send_issued_confirmation_email(*, rental_request) -> None:
    """
    Send confirmation email when a rental is issued.

    This function should not raise: failures must not block issuance.
    """
    user_email = getattr(rental_request.user, "email", None)
    if not user_email:
        logger.warning(
            "No email address for user %s, skipping issued confirmation (rental_request_id=%s)",
            rental_request.user.pk,
            rental_request.id,
        )
        return

    contact_email = getattr(settings, "OK_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "") or ""

    # Build item and room summaries (same pattern as email_approval._build_rental_summary_context)
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

    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "user_name": rental_request.user.get_full_name() or rental_request.user.email,
        "project_name": rental_request.project_name,
        "purpose": rental_request.purpose,
        "start": rental_request.requested_start_date,
        "end": rental_request.requested_end_date,
        "actual_start": rental_request.actual_start_date,
        "items": items,
        "rooms": rooms,
        "items_total": rental_request.total_items_count,
        "rooms_total": rental_request.total_rooms_count,
        "contact_email": contact_email,
    }

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    translation.activate('de')
    try:
        send_mail(
            subject_template_name="email/rental_request_issued_subject.txt",
            email_template_name="email/rental_request_issued_body.txt",
            html_email_template_name="email/rental_request_issued_body.html",
            context=context,
            from_email=from_email,
            to_email=user_email,
        )
        logger.info(
            "Issued confirmation email sent to %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    except Exception:
        logger.exception(
            "Failed to send issued confirmation email to %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    finally:
        translation.deactivate()


def send_reminder_email(*, rental_request) -> None:
    """
    Send a reminder email to the rental user about an upcoming or overdue rental.

    This function should not raise: failures must not block the reminder action.
    """
    user_email = getattr(rental_request.user, "email", None)
    if not user_email:
        logger.warning(
            "No email address for user %s, skipping reminder (rental_request_id=%s)",
            rental_request.user.pk,
            rental_request.id,
        )
        return

    contact_email = getattr(settings, "OK_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "") or ""

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

    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "user_name": rental_request.user.get_full_name() or rental_request.user.email,
        "project_name": rental_request.project_name,
        "start": rental_request.requested_start_date,
        "end": rental_request.requested_end_date,
        "status": rental_request.get_status_display(),
        "items": items,
        "rooms": rooms,
        "contact_email": contact_email,
    }

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    translation.activate('de')
    try:
        send_mail(
            subject_template_name="email/rental_request_issued_subject.txt",
            email_template_name="email/rental_request_issued_body.txt",
            html_email_template_name="email/rental_request_issued_body.html",
            context=context,
            from_email=from_email,
            to_email=user_email,
        )
        logger.info(
            "Reminder email sent to %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    except Exception:
        logger.exception(
            "Failed to send reminder email to %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    finally:
        translation.deactivate()


def send_return_receipt_email(*, rental_request, returned_items=None, note='') -> None:
    """
    Send a receipt email after equipment has been returned.

    This function should not raise: failures must not block return processing.
    """
    user_email = getattr(rental_request.user, "email", None)
    if not user_email:
        logger.warning(
            "No email address for user %s, skipping return receipt (rental_request_id=%s)",
            rental_request.user.pk,
            rental_request.id,
        )
        return

    contact_email = getattr(settings, "OK_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "") or ""
    context = {
        "ok_name": getattr(settings, "OK_NAME", ""),
        "rental_id": rental_request.id,
        "user_name": rental_request.user.get_full_name() or rental_request.user.email,
        "project_name": rental_request.project_name,
        "returned_at": rental_request.actual_end_date,
        "returned_items": returned_items or [],
        "note": note,
        "contact_email": contact_email,
    }

    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    translation.activate('de')
    try:
        send_mail(
            subject_template_name="email/rental_return_receipt_subject.txt",
            email_template_name="email/rental_return_receipt_body.txt",
            html_email_template_name="email/rental_return_receipt_body.html",
            context=context,
            from_email=from_email,
            to_email=user_email,
        )
        logger.info(
            "Return receipt email sent to %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    except Exception:
        logger.exception(
            "Failed to send return receipt email to %s (rental_request_id=%s)",
            user_email,
            rental_request.id,
        )
    finally:
        translation.deactivate()
