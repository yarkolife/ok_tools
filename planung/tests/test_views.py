from datetime import timedelta
from django.urls import reverse
from licenses.models import License
from licenses.models import default_category
from planung.models import TagesPlan
import pytest


@pytest.fixture
def staff_user(user):
    """Upgrade default user fixture to staff user for admin-protected endpoints."""
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def license_obj(staff_user):
    """Create one license used by API tests."""
    profile = staff_user.profile
    profile.verified = True
    profile.save()
    return License.objects.create(
        profile=profile,
        category=default_category(),
        title="Planning API License",
        subtitle="",
        description="",
        duration=timedelta(minutes=20),
        further_persons="",
        suggested_date=None,
        repetitions_allowed=True,
        media_authority_exchange_allowed=True,
        youth_protection_necessary=False,
        store_in_ok_media_library=True,
    )


@pytest.mark.django_db
def test__planung__get_license_endpoint(client, staff_user, license_obj):
    """License endpoint returns metadata for known license number."""
    client.force_login(staff_user)
    response = client.get(f"/api/license/{license_obj.number}/")
    assert response.status_code == 200
    data = response.json()
    assert data["number"] == license_obj.number
    assert data["title"] == "Planning API License"


@pytest.mark.django_db
def test__planung__day_plan_crud_flow(client, staff_user, license_obj):
    """POST/GET/DELETE workflow works for day plan endpoint."""
    client.force_login(staff_user)

    payload = {
        "date": "2026-02-10",
        "items": [
            {
                "number": license_obj.number,
                "start": "18:00:00",
                "duration": 1200,
                "title": "Planning API License",
                "subtitle": "",
            }
        ],
        "draft": True,
        "comment": "API test",
    }
    post_resp = client.post(
        reverse("save_day_plan"),
        data=payload,
        content_type="application/json",
    )
    assert post_resp.status_code == 200
    assert TagesPlan.objects.filter(datum="2026-02-10").exists()

    get_resp = client.get("/api/day-plan/2026-02-10/")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["date"] == "2026-02-10"
    assert get_data["draft"] is True
    assert len(get_data["items"]) == 1

    del_resp = client.delete("/api/day-plan/2026-02-10/")
    assert del_resp.status_code == 204
    assert not TagesPlan.objects.filter(datum="2026-02-10").exists()


@pytest.mark.django_db
def test__planung__save_day_plan_validation_error(client, staff_user, license_obj):
    """Endpoint returns structured validation errors for invalid payload."""
    client.force_login(staff_user)
    payload = {
        "date": "2026-02-10",
        "items": [
            {"number": license_obj.number, "start": "18:00:00", "duration": 1200},
            {"number": license_obj.number + 1, "start": "18:10:00", "duration": 1200},
        ],
        "draft": True,
    }
    response = client.post(
        reverse("save_day_plan"),
        data=payload,
        content_type="application/json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]
    assert isinstance(body.get("errors"), list)
    assert len(body["errors"]) > 0


@pytest.mark.django_db
def test__planung__week_stats_endpoint(client, staff_user):
    """Week stats endpoint responds with aggregated week rows."""
    client.force_login(staff_user)
    response = client.get("/api/planning/week-stats/?start=2026-02-09&weeks=2")
    assert response.status_code == 200
    data = response.json()
    assert "weeks" in data
    assert len(data["weeks"]) == 2

