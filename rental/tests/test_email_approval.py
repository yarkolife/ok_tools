# All test descriptions are in English per project rules.

import pytest
from django.core import signing
from django.test import Client
from django.urls import reverse
from django.utils import timezone

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


