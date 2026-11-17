# All test descriptions are in English per project rules.

import pytest
from django.core import signing
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from rental.email_approval import send_admin_approval_email
from rental.models import RentalRequest


@pytest.mark.django_db
def test__rental__email_approval__approve_transitions_draft_to_reserved(settings, django_user_model):
    """Approve link transitions draft request to reserved."""
    user = django_user_model.objects.create_user(email="u@example.com", password="pwd")
    start = timezone.now()
    end = start + timezone.timedelta(days=1)

    rr = RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name="P",
        purpose="X",
        requested_start_date=start,
        requested_end_date=end,
        rental_type="equipment",
        notes="",
        status="draft",
    )

    token = signing.dumps({"rental_id": rr.id, "action": "approve"}, salt="rental-approval")
    url = reverse("rental:email_approval_action", kwargs={"rental_id": rr.id, "action": "approve", "token": token})

    c = Client()
    resp = c.get(url)
    assert resp.status_code == 200
    rr.refresh_from_db()
    assert rr.status == "reserved"


@pytest.mark.django_db
def test__rental__email_approval__deny_transitions_draft_to_cancelled(django_user_model):
    """Deny link transitions draft request to cancelled."""
    user = django_user_model.objects.create_user(email="u2@example.com", password="pwd")
    start = timezone.now()
    end = start + timezone.timedelta(days=1)
    rr = RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name="P",
        purpose="X",
        requested_start_date=start,
        requested_end_date=end,
        rental_type="equipment",
        notes="",
        status="draft",
    )

    token = signing.dumps({"rental_id": rr.id, "action": "deny"}, salt="rental-approval")
    url = reverse("rental:email_approval_action", kwargs={"rental_id": rr.id, "action": "deny", "token": token})

    c = Client()
    resp = c.get(url)
    assert resp.status_code == 200
    rr.refresh_from_db()
    assert rr.status == "cancelled"


@pytest.mark.django_db
def test__rental__email_approval__token_mismatch_returns_400(django_user_model):
    """If token payload does not match path params, return 400."""
    user = django_user_model.objects.create_user(email="u3@example.com", password="pwd")
    start = timezone.now()
    end = start + timezone.timedelta(days=1)
    rr = RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name="P",
        purpose="X",
        requested_start_date=start,
        requested_end_date=end,
        rental_type="equipment",
        notes="",
        status="draft",
    )

    token = signing.dumps({"rental_id": rr.id, "action": "approve"}, salt="rental-approval")
    url = reverse("rental:email_approval_action", kwargs={"rental_id": rr.id, "action": "deny", "token": token})

    c = Client()
    resp = c.get(url)
    assert resp.status_code == 400


@pytest.mark.django_db
def test__rental__email_approval__admin_email_contains_staff_view_link(settings, django_user_model):
    """Admin approval email contains a staff detail link for simple view."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.SITE_BASE_URL = "https://portal.okmq.de"

    requester = django_user_model.objects.create_user(email="requester@example.com", password="pwd")
    django_user_model.objects.create_user(
        email="staff@example.com",
        password="pwd",
        is_staff=True,
        is_active=True,
    )

    start = timezone.now()
    end = start + timezone.timedelta(days=1)
    rr = RentalRequest.objects.create(
        user=requester,
        created_by=requester,
        project_name="Project",
        purpose="Purpose",
        requested_start_date=start,
        requested_end_date=end,
        rental_type="equipment",
        notes="",
        status="draft",
    )

    send_admin_approval_email(rental_request=rr)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    expected_staff_url = f"https://portal.okmq.de/rental/rental/{rr.id}/"
    assert expected_staff_url in email.body

    assert email.alternatives
    html_body = email.alternatives[0][0]
    assert expected_staff_url in html_body



@pytest.mark.django_db
def test__rental__user_request__approval_mails_leave_after_commit_in_celery(
        settings, django_user_model, django_capture_on_commit_callbacks):
    """The booking response does not wait for SMTP: mails go to Celery after commit."""
    from datetime import timedelta
    from unittest import mock

    from rental.models import Room
    from rental.services.rental_service import RentalService
    from rental import tasks

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = django_user_model.objects.create_user(email="booker@example.com", password="pwd")
    django_user_model.objects.create_user(email="staff2@example.com", password="pwd", is_staff=True)
    room = Room.objects.create(name="Schnittraum", capacity=2, is_active=True)
    day = timezone.localdate() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    data = {
        "project_name": "Schnitt", "purpose": "x", "action": "draft", "items": [],
        "start_date": f"{day.isoformat()}T12:00", "end_date": f"{day.isoformat()}T15:00",
        "rooms": [{"room_id": room.id, "people_count": 1}], "rental_type": "room",
    }

    with mock.patch("rental.config.get_rental_user_request_requires_approval", return_value=True), \
            mock.patch.object(tasks.send_rental_approval_emails, "delay") as delay, \
            django_capture_on_commit_callbacks(execute=True):
        result = RentalService.create_rental_request(data, user, user, is_user_request=True)
        assert len(mail.outbox) == 0  # nothing is sent inside the request

    assert result["success"], result
    delay.assert_called_once_with(result["rental_id"])

    tasks.send_rental_approval_emails(result["rental_id"])
    assert sorted(m.to[0] for m in mail.outbox) == ["booker@example.com", "staff2@example.com"]


@pytest.mark.django_db
def test__rental__approval_mail_task__skips_requests_no_longer_pending(settings, django_user_model):
    """Approved before the task ran: no "please approve" mail any more."""
    from rental import tasks

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = django_user_model.objects.create_user(email="u5@example.com", password="pwd")
    start = timezone.now()
    rr = RentalRequest.objects.create(
        user=user, created_by=user, project_name="P", purpose="X",
        requested_start_date=start, requested_end_date=start + timezone.timedelta(days=1),
        rental_type="equipment", notes="", status="reserved")

    tasks.send_rental_approval_emails(rr.id)
    assert mail.outbox == []
