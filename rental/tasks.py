"""Celery tasks of the rental app."""

from celery import shared_task
import logging


logger = logging.getLogger('django')


@shared_task(name='rental.tasks.send_rental_approval_emails')
def send_rental_approval_emails(rental_request_id: int) -> None:
    """Send the approval request to staff and the "pending" mail to the user.

    Runs outside the web request: the SMTP server must not keep the user
    waiting after the booking has been saved.
    """
    from .email_approval import send_admin_approval_email
    from .email_approval import send_user_pending_email
    from .models import RentalRequest

    rental_request = (
        RentalRequest.objects.select_related('user').filter(pk=rental_request_id).first())
    if rental_request is None or rental_request.status != 'draft':
        # Deleted, or already approved/denied before the mails went out.
        return
    send_admin_approval_email(rental_request=rental_request)
    send_user_pending_email(rental_request=rental_request)
