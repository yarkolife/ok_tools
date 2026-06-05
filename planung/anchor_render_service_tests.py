from datetime import date
from datetime import timedelta
from licenses.models import License
from licenses.models import default_category
from media_files.models import StorageLocation
from media_files.models import VideoFile
from planung.models import PlanungConfig
from planung.models import TagesPlan
from planung.services.anchor_render_service import AnchorRenderResult
from planung.services.anchor_render_service import AnchorJobStatus
from planung.services.anchor_render_service import build_anchor_payload
from planung.services.anchor_render_service import render_anchor_preview
from planung.tasks import poll_anchor_render_job
from registration.models import Profile
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
    assert "startFromSeconds" not in payload["beitraege"][0]
    assert "kontakt" not in payload
    assert "musik" not in payload


@pytest.mark.django_db
def test__anchor_render__payload_adds_random_start_from_seconds_near_middle(verified_profile):
    """Anchor payload sends a bounded random source start for known playout videos."""
    license_obj = License.objects.create(
        profile=verified_profile,
        category=default_category(),
        title="Short programme",
        description="Description",
        duration=timedelta(minutes=2),
        further_persons="",
        repetitions_allowed=True,
        media_authority_exchange_allowed=False,
        youth_protection_necessary=False,
        store_in_ok_media_library=False,
        confirmed=True,
    )
    storage = StorageLocation.objects.create(
        name="Playout",
        storage_type="PLAYOUT",
        path="/mnt/nas/playout",
    )
    VideoFile.objects.create(
        number=license_obj.number,
        filename="clip.mp4",
        storage_location=storage,
        file_path="000_Sendungen/clip.mp4",
        duration=timedelta(minutes=2),
    )

    with patch("planung.services.anchor_render_service.triangular", return_value=50.4) as mocked_random:
        payload, rejected = build_anchor_payload(
            plan_date=date(2026, 6, 8),
            plan_items=[
                {
                    "number": license_obj.number,
                    "start": "18:00:00",
                    "duration": 20,
                    "title": "Short programme",
                }
            ],
            output_name="16573_Programmvorschau_260608.mp4",
        )

    assert rejected == []
    contribution = payload["beitraege"][0]
    assert contribution["video"] == "playout/000_Sendungen/clip.mp4"
    assert contribution["durationInSeconds"] == 20
    assert contribution["startFromSeconds"] == 50
    random_args = mocked_random.call_args.args
    assert random_args[0] == pytest.approx(38.84)
    assert random_args[1] == pytest.approx(61.16)
    assert random_args[2] == 50


@pytest.mark.django_db
def test__anchor_render__payload_uses_wide_random_window_for_long_videos(verified_profile):
    """Long source videos get a wider random window than short clips."""
    license_obj = License.objects.create(
        profile=verified_profile,
        category=default_category(),
        title="Long programme",
        description="Description",
        duration=timedelta(hours=1),
        further_persons="",
        repetitions_allowed=True,
        media_authority_exchange_allowed=False,
        youth_protection_necessary=False,
        store_in_ok_media_library=False,
        confirmed=True,
    )
    storage = StorageLocation.objects.create(
        name="Playout Long",
        storage_type="PLAYOUT",
        path="/mnt/nas/playout",
    )
    VideoFile.objects.create(
        number=license_obj.number,
        filename="long.mp4",
        storage_location=storage,
        file_path="000_Sendungen/long.mp4",
        duration=timedelta(hours=1),
    )

    with patch("planung.services.anchor_render_service.triangular", return_value=2400) as mocked_random:
        payload, rejected = build_anchor_payload(
            plan_date=date(2026, 6, 8),
            plan_items=[
                {
                    "number": license_obj.number,
                    "start": "18:00:00",
                    "duration": 20,
                    "title": "Long programme",
                }
            ],
            output_name="16573_Programmvorschau_260608.mp4",
        )

    assert rejected == []
    assert payload["beitraege"][0]["startFromSeconds"] == 2400
    random_args = mocked_random.call_args.args
    assert random_args[0] == pytest.approx(182.15)
    assert random_args[1] == pytest.approx(3397.85)
    assert random_args[2] == 1790


@pytest.mark.django_db
def test__anchor_render__payload_uses_configured_clip_duration_not_plan_item_duration(verified_profile):
    """Anchor clip length must not use the full planned broadcast duration."""
    license_obj = License.objects.create(
        profile=verified_profile,
        category=default_category(),
        title="Full length programme",
        description="Description",
        duration=timedelta(hours=1),
        further_persons="",
        repetitions_allowed=True,
        media_authority_exchange_allowed=False,
        youth_protection_necessary=False,
        store_in_ok_media_library=False,
        confirmed=True,
    )
    storage = StorageLocation.objects.create(
        name="Playout Full Length",
        storage_type="PLAYOUT",
        path="/mnt/nas/playout",
    )
    VideoFile.objects.create(
        number=license_obj.number,
        filename="full.mp4",
        storage_location=storage,
        file_path="000_Sendungen/full.mp4",
        duration=timedelta(hours=1),
    )
    config = PlanungConfig.get_config()
    config.anchor_contribution_duration_seconds = 20
    config.save()

    with patch("planung.services.anchor_render_service.triangular", return_value=1790):
        payload, rejected = build_anchor_payload(
            plan_date=date(2026, 6, 8),
            plan_items=[
                {
                    "number": license_obj.number,
                    "start": "18:00:00",
                    "duration": 3600,
                    "title": "Full length programme",
                }
            ],
            output_name="16573_Programmvorschau_260608.mp4",
        )

    assert rejected == []
    contribution = payload["beitraege"][0]
    assert contribution["durationInSeconds"] == 20
    assert contribution["startFromSeconds"] == 1790


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
def test__anchor_render__endpoint_returns_202_with_task_id(client, staff_user):
    """The render endpoint queues a Celery chain and returns 202 with task_id."""
    client.force_login(staff_user)
    TagesPlan.objects.create(
        datum="2026-06-08",
        json_plan={
            "items": [{"start": "19:00:00", "duration": 20, "title": "Preview"}],
            "draft": False,
            "planned": True,
        },
    )
    celery_result = Mock(id="chain-task-1")
    chain_mock = Mock(delay=Mock(return_value=celery_result))

    with patch(
        "planung.views._check_plan_copy_state",
        return_value={"status": "ready", "missing": [], "ready": []},
    ), patch(
        "planung.views.anchor_render_chain", chain_mock
    ):
        response = client.post(
            "/api/planning/anchor/render/",
            data=json.dumps({"date": "2026-06-08"}),
            content_type="application/json",
        )

    assert response.status_code == 202
    chain_mock.delay.assert_called_once()
    body = response.json()
    assert body["status"] == "queued"
    assert body["task_id"] == "chain-task-1"


@pytest.mark.django_db
def test__anchor_render__endpoint_blocks_when_copying(client, staff_user):
    """409 when videos are still being copied to playout."""
    client.force_login(staff_user)
    TagesPlan.objects.create(
        datum="2026-06-08",
        json_plan={
            "items": [{"start": "19:00:00", "duration": 20, "title": "Preview", "number": 1}],
            "draft": False,
            "planned": True,
        },
    )

    with patch(
        "planung.views._check_plan_copy_state",
        return_value={"status": "copying", "missing": [1], "ready": []},
    ):
        response = client.post(
            "/api/planning/anchor/render/",
            data=json.dumps({"date": "2026-06-08"}),
            content_type="application/json",
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "videos_still_copying"
    assert body["missing"] == [1]


@pytest.mark.django_db
def test__anchor_render__endpoint_returns_409_with_details_on_copy_failed(client, staff_user):
    """409 with missing/ready lists when copy_videos_for_plan failed."""
    client.force_login(staff_user)
    TagesPlan.objects.create(
        datum="2026-06-08",
        json_plan={
            "items": [{"start": "19:00:00", "duration": 20, "title": "Preview", "number": 1}],
            "draft": False,
            "planned": True,
        },
        copy_task_id="failed-task-id",
    )

    with patch(
        "planung.views._check_plan_copy_state",
        return_value={"status": "copy_failed", "missing": [1, 2], "ready": [3]},
    ):
        response = client.post(
            "/api/planning/anchor/render/",
            data=json.dumps({"date": "2026-06-08"}),
            content_type="application/json",
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "copy_failed"
    assert body["copy_task_id"] == "failed-task-id"
    assert body["missing"] == [1, 2]
    assert body["ready"] == [3]


@pytest.mark.django_db
def test__anchor_render__endpoint_force_bypasses_copy_failed(client, staff_user):
    """force=true allows render even when copy_videos_for_plan failed."""
    client.force_login(staff_user)
    TagesPlan.objects.create(
        datum="2026-06-08",
        json_plan={
            "items": [{"start": "19:00:00", "duration": 20, "title": "Preview", "number": 1}],
            "draft": False,
            "planned": True,
        },
    )
    celery_result = Mock(id="forced-task-1")
    chain_mock = Mock(delay=Mock(return_value=celery_result))

    with patch(
        "planung.views._check_plan_copy_state",
        return_value={"status": "copy_failed", "missing": [1], "ready": [2]},
    ), patch(
        "planung.views.anchor_render_chain", chain_mock
    ):
        response = client.post(
            "/api/planning/anchor/render/",
            data=json.dumps({"date": "2026-06-08", "force": True}),
            content_type="application/json",
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["forced"] is True
    chain_mock.delay.assert_called_once()


@pytest.mark.django_db
def test__anchor_render__creates_license_and_posts_payload(verified_profile):
    """Rendering creates the output license before calling the external service."""
    org_profile = Profile.objects.create(
        first_name="Offener Kanal",
        last_name="Merseburg-Querfurt e.V.",
        gender="none",
        birthday="2000-01-01",
        street="Geusaer Straße",
        house_number="86 b",
        zipcode="06217",
        city="Merseburg",
        verified=True,
    )
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
    assert license_obj.category.name == "Sonstiges"
    assert license_obj.profile == org_profile
    assert license_obj.infoblock is True
    assert result.output_name == f"{license_obj.number}_Programmvorschau_260608.mp4"
    assert result.status == "done"

    mocked_post.assert_called_once()
    call = mocked_post.call_args
    assert "params" not in call.kwargs
    assert call.kwargs["headers"]["X-API-Key"] == "secret"
    assert call.kwargs["timeout"] == 17
    payload = call.kwargs["json"]
    assert payload["stimme"] == "w"
    assert payload["output_name"] == result.output_name
    assert payload["beitraege"][0]["video"] == "playout/placeholder/default.mp4"


@pytest.mark.django_db
def test__anchor_render__reuses_license_and_requires_confirmation_for_existing_video(verified_profile, tmp_path):
    """Rendering does not duplicate the preview license and blocks overwrites without confirmation."""
    StorageLocation.objects.create(
        name="Playout",
        storage_type="PLAYOUT",
        path=str(tmp_path),
        is_active=True,
    )
    config = PlanungConfig.get_config()
    config.anchor_render_url = "http://renderer.example/api/anchor"
    config.anchor_render_api_key = "secret"
    config.anchor_default_placeholder_video = "playout/placeholder/default.mp4"
    config.save()

    response = Mock()
    response.json.return_value = {"job_id": "job-1", "status": "done", "error": None}
    response.raise_for_status.return_value = None
    plan_items = [{"start": "19:00:00", "duration": 20, "title": "Preview"}]

    with patch(
        "planung.services.anchor_render_service.requests.post",
        return_value=response,
    ) as mocked_post:
        first_result = render_anchor_preview(
            plan_date=date(2026, 6, 8),
            plan_items=plan_items,
            profile=verified_profile,
        )
        output_path = tmp_path / "003_Programmvorschau" / first_result.output_name
        output_path.parent.mkdir(parents=True)
        output_path.write_text("rendered")

        second_result = render_anchor_preview(
            plan_date=date(2026, 6, 8),
            plan_items=plan_items,
            profile=verified_profile,
        )

    assert mocked_post.call_count == 1
    assert first_result.license_id == second_result.license_id
    assert first_result.license_created is True
    assert second_result.license_created is False
    assert second_result.video_exists is True
    assert second_result.requires_confirmation is True
    assert second_result.error == "output_video_exists"
    assert License.objects.filter(title="Programmvorschau vom 08.06.2026").count() == 1


@pytest.mark.django_db
def test__anchor_render__endpoint_checks_job_status(client, staff_user):
    """The status endpoint proxies anchor job polling and preserves status errors."""
    client.force_login(staff_user)
    config = PlanungConfig.get_config()
    config.anchor_render_url = "http://renderer.example/api/anchor"
    config.anchor_render_api_key = "secret"
    config.anchor_render_timeout = 17
    config.save()

    response = Mock()
    response.json.return_value = {
        "job_id": "job-1",
        "status": "error",
        "file": "",
        "error": "render failed",
    }
    response.raise_for_status.return_value = None

    with patch(
        "planung.services.anchor_render_service.requests.get",
        return_value=response,
    ) as mocked_get:
        result = client.get("/api/planning/anchor/status/job-1/")

    assert result.status_code == 200
    body = result.json()
    assert body["job_id"] == "job-1"
    assert body["status"] == "error"
    assert body["error"] == "render failed"
    mocked_get.assert_called_once_with(
        "http://renderer.example/api/anchor/job-1",
        headers={"X-API-Key": "secret"},
        timeout=17,
    )


def test__anchor_render__celery_task_polls_until_done():
    """Celery polling returns the final renderer status in TaskResult."""
    results = [
        AnchorJobStatus(True, "job-1", "queued", "", ""),
        AnchorJobStatus(True, "job-1", "rendering", "", ""),
        AnchorJobStatus(True, "job-1", "done", "preview.mp4", ""),
    ]

    with patch(
        "planung.tasks.get_anchor_job_status",
        side_effect=results,
    ), patch("planung.tasks.time.sleep") as mocked_sleep, patch.object(
        poll_anchor_render_job,
        "update_state",
    ) as mocked_update_state:
        payload = poll_anchor_render_job.run(
            job_id="job-1",
            output_name="preview.mp4",
            poll_interval=1,
            max_attempts=5,
        )

    assert payload["status"] == "done"
    assert payload["file"] == "preview.mp4"
    assert payload["output_name"] == "preview.mp4"
    assert mocked_sleep.call_count == 2
    assert mocked_update_state.call_count == 3
