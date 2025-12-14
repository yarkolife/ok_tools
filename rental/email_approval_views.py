"""
Email approval endpoints for rental requests.

These views are intentionally simple and do not require authentication:
access is protected by signed tokens with expiration.
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from rental.email_approval import load_approval_token
from rental.models import RentalRequest


@require_GET
def email_approval_action(request: HttpRequest, rental_id: int, action: str, token: str) -> HttpResponse:
    max_age = int(getattr(settings, "RENTAL_APPROVAL_TOKEN_MAX_AGE_SECONDS", 60 * 60 * 24 * 7))

    try:
        data = load_approval_token(token, max_age_seconds=max_age)
    except Exception:
        return render(
            request,
            "rental/email_approval_result.html",
            {
                "ok": False,
                "title": _("Invalid or expired link"),
                "message": _("This approval link is invalid or has expired."),
            },
            status=400,
        )

    if int(data.get("rental_id", -1)) != int(rental_id) or str(data.get("action")) != str(action):
        return render(
            request,
            "rental/email_approval_result.html",
            {
                "ok": False,
                "title": _("Invalid link"),
                "message": _("This approval link does not match the request."),
            },
            status=400,
        )

    if action not in ("approve", "deny"):
        return render(
            request,
            "rental/email_approval_result.html",
            {
                "ok": False,
                "title": _("Invalid action"),
                "message": _("Unsupported approval action."),
            },
            status=400,
        )

    rr = get_object_or_404(RentalRequest, id=rental_id)

    # Only draft requests are eligible for email approval workflow.
    if rr.status != "draft":
        return render(
            request,
            "rental/email_approval_result.html",
            {
                "ok": True,
                "title": _("Nothing to do"),
                "message": _("This request has already been processed."),
            },
            status=200,
        )

    if action == "approve":
        rr.status = "reserved"
        rr.save(update_fields=["status"])
        # Notify user about approval
        try:
            from rental.email_approval import send_user_approved_email
            send_user_approved_email(rental_request=rr)
        except Exception:
            # Do not fail approval on email errors
            import logging
            logging.getLogger('django').exception(
                "Failed to send approved email to user (rental_request_id=%s)", rr.id
            )
        return render(
            request,
            "rental/email_approval_result.html",
            {
                "ok": True,
                "title": _("Approved"),
                "message": _("The request has been approved and reserved."),
            },
            status=200,
        )

    # deny
    rr.status = "cancelled"
    rr.save(update_fields=["status"])
    # Notify user about decline
    try:
        from rental.email_approval import send_user_declined_email
        send_user_declined_email(rental_request=rr)
    except Exception:
        # Do not fail decline on email errors
        import logging
        logging.getLogger('django').exception(
            "Failed to send declined email to user (rental_request_id=%s)", rr.id
        )
    return render(
        request,
        "rental/email_approval_result.html",
        {
            "ok": True,
            "title": _("Declined"),
            "message": _("The request has been declined."),
        },
        status=200,
    )


