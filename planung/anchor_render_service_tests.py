from datetime import date
from datetime import timedelta
from licenses.models import License
from licenses.models import default_category
from planung.models import PlanungConfig
from planung.models import TagesPlan
from planung.services.anchor_render_service import AnchorRenderResult
from planung.services.anchor_render_service import build_anchor_payload
from planung.services.anchor_render_service import render_anchor_preview
from unittest.mock import Mock
from unittest.mock import patch
import json
import pytest


@pytest.fixture
def verified_profile(user):
    """Return a verified profile for generated preview licenses."""
    profile = user.profile
    profile.verified = True
    profile.save(update_fields=["verified"])
    return profile


@pytest.fixture
def staff_user(user):
    """Return a staff user for admin-protected endpoints."""
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


def test__anchor_render__payload_uses_first_eight_items_without_contact_or_music():
    """Anchor payload follows the renderer contract and caps contributions."""
    config = PlanungConfig(
        anchor_default_placeholder_video="playout/placeholder/default.mp4",
    )
    plan_items = [
        {
            "start": f"18:{index:02d}:00",
            "duration": 20,
            "title": f"Title {index}",
            "subtitle": "Subtitle",
            "sender_responsible": "Author",
        }
        for index in range(9)
    ]

    payload, rejected = build_anchor_payload(
        plan_date=date(2026, 6, 8),
        plan_items=plan_items,
        output_name="16573_Programmvorschau_260608.mp4",
        config=config,
    )

    assert rejected == []
    assert payload["wochentag"] == "Montag"
    assert payload["output_name"] == "16573_Programmvorschau_260608.mp4"
    assert len(payload["beitraege"]) == 8
    assert payload["beitraege"][0]["video"] == "playout/placeholder/default.mp4"
    assert "kontakt" not in payload
    assert "musik" not in payload


@pytest.mark.django_db
def test__anchor_render__endpoint_requires_planned_day(client, staff_user):
    """The render endpoint only accepts already planned days."""
    client.force_login(staff_user)
    TagesPlan.objects.create(
        datum="2026-06-08",
        json_plan={
            "items": [{"start": "19:00:00", "duration": 20, "title": "Preview"}],
            "draft": True,
            "planned": False,
        },
    )

    response = client.post(
        "/api/planning/anchor/render/",
        data=json.dumps({"date": "2026-06-08"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Plan the day first"


@pytest.mark.django_db
def test__anchor_render__endpoint_returns_renderer_result(client, staff_user):
    """The render endpoint returns the service result for planned days."""
    client.force_login(staff_user)
    TagesPlan.objects.create(
        datum="2026-06-08",
        json_plan={
            "items": [{"start": "19:00:00", "duration": 20, "title": "Preview"}],
            "draft": False,
            "planned": True,
        },
    )
    result = AnchorRenderResult(
        configured=True,
        sent=True,
        license_id=12,
        license_number=16573,
        output_name="16573_Programmvorschau_260608.mp4",
        job_id="job-1",
        status="done",
        file="16573_Programmvorschau_260608.mp4",
        error="",
    )

    with patch("planung.views.render_anchor_preview", return_value=result) as mocked_render:
        response = client.post(
            "/api/planning/anchor/render/",
            data=json.dumps({"date": "2026-06-08"}),
            content_type="application/json",
        )

    assert response.status_code == 200
    mocked_render.assert_called_once()
    body = response.json()
    assert body["output_name"] == "16573_Programmvorschau_260608.mp4"
    assert body["status"] == "done"


@pytest.mark.django_db
def test__anchor_render__creates_license_and_posts_payload(verified_profile):
    """Rendering creates the output license before calling the external service."""
    config = PlanungConfig.get_config()
    config.anchor_render_url = "http://renderer.example/api/anchor"
    config.anchor_render_api_key = "secret"
    config.anchor_render_timeout = 17
    config.anchor_render_wait = True
    config.anchor_default_placeholder_video = "playout/placeholder/default.mp4"
    config.save()

    response = Mock()
    response.json.return_value = {
        "job_id": "job-1",
        "status": "done",
        "file": "1_Programmvorschau_260608.mp4",
        "error": None,
    }
    response.raise_for_status.return_value = None

    with patch("planung.services.anchor_render_service.choice", return_value="w"), patch(
        "planung.services.anchor_render_service.requests.post",
        return_value=response,
    ) as mocked_post:
        result = render_anchor_preview(
            plan_date=date(2026, 6, 8),
            plan_items=[
                {
                    "start": "19:00:00",
                    "duration": 20,
                    "title": "Programmvorschau item",
                    "subtitle": "",
                    "sender_responsible": "Author",
                }
            ],
            profile=verified_profile,
        )

    license_obj = License.objects.get(pk=result.license_id)
    assert license_obj.title == "Programmvorschau vom 08.06.2026"
    assert license_obj.description == "Information für unsere Zuschauer."
    assert license_obj.duration == timedelta(minutes=1)
    assert license_obj.category == default_category()
    assert result.output_name == f"{license_obj.number}_Programmvorschau_260608.mp4"
    assert result.status == "done"

    mocked_post.assert_called_once()
    call = mocked_post.call_args
    assert call.kwargs["params"] == {"wait": "1"}
    assert call.kwargs["headers"]["X-API-Key"] == "secret"
    assert call.kwargs["timeout"] == 17
    payload = call.kwargs["json"]
    assert payload["stimme"] == "w"
    assert payload["output_name"] == result.output_name
    assert payload["beitraege"][0]["video"] == "playout/placeholder/default.mp4"
