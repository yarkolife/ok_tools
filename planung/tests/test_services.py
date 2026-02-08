from datetime import timedelta
from django.utils import timezone
from licenses.models import License
from licenses.models import default_category
from planung.services.validation_service import PlanningValidationError
from planung.services.validation_service import validate_day_plan_payload
import pytest


@pytest.fixture
def license_obj(user):
    """Create a valid license for planning tests."""
    profile = user.profile
    profile.verified = True
    profile.save()
    return License.objects.create(
        profile=profile,
        category=default_category(),
        title="Planning Test License",
        subtitle="",
        description="",
        duration=timedelta(minutes=15),
        further_persons="",
        suggested_date=timezone.now().date(),
        repetitions_allowed=True,
        media_authority_exchange_allowed=True,
        youth_protection_necessary=False,
        store_in_ok_media_library=True,
    )


def test__planung__validation__rejects_overlap():
    """Validation fails when schedule contains overlapping items."""
    payload = {
        "date": "2026-02-07",
        "items": [
            {"number": 100, "start": "18:00:00", "duration": 600},
            {"number": 200, "start": "18:05:00", "duration": 600},
        ],
        "draft": True,
    }

    with pytest.raises(PlanningValidationError) as exc:
        validate_day_plan_payload(payload)

    assert any("overlap" in e["message"].lower() for e in exc.value.errors)


def test__planung__validation__normalizes_valid_payload():
    """Validation returns normalized strongly typed payload."""
    payload = {
        "date": "2026-02-07",
        "items": [
            {"number": "123", "start": "18:00", "duration": "300"},
        ],
        "draft": False,
        "planned": True,
        "comment": "ok",
    }

    validated = validate_day_plan_payload(payload)
    assert validated.plan_date.isoformat() == "2026-02-07"
    assert validated.items[0]["number"] == 123
    assert validated.items[0]["duration"] == 300
    assert validated.planned is True

