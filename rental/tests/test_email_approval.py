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

