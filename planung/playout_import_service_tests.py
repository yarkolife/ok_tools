from datetime import date
from django.conf import settings
from planung.models import PlanungConfig
from planung.services import playout_import_service
from typing import Mapping
from unittest.mock import patch
import pytest


class FakePlayoutResponse:
    """Minimal response object for requests.post tests."""

    def __init__(self, payload: Mapping[str, object]):
        self.payload = payload

    def raise_for_status(self):
        """Fake a successful HTTP response."""

    def json(self):
        """Return the fake playout JSON response."""
        return self.payload


@pytest.mark.django_db
def test__playout_import_service__posts_items_by_filename():
    """Service posts metadata items to the configured playout import endpoint."""
    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
        playout_import_timeout=7,
    )
    items = [
        {
            "filename": "clip01.mp4",
            "title": "Название сюжета",
        }
    ]
    with patch(
        "planung.services.playout_import_service.build_playout_import_items",
        return_value=items,
    ), patch(
        "planung.services.playout_import_service.requests.post",
        return_value=FakePlayoutResponse({"matched": 1, "unmatched": []}),
    ) as mocked_post:
        result = playout_import_service.send_playout_import([{"number": 1}])

    mocked_post.assert_called_once_with(
        "http://192.168.88.50/api/media/import",
        json={"items": [{"filename": "clip01.mp4", "title": "Название сюжета"}]},
        headers={"Content-Type": "application/json", "X-API-Key": "secret-key"},
        timeout=7,
    )
    assert result.configured is True
    assert result.sent == 1
    assert result.matched == 1
    assert result.unmatched == []
    assert result.error == ""


@pytest.mark.django_db
def test__playout_import_service__skips_when_not_configured():
    """Service reports skipped import when playout settings are absent."""
    PlanungConfig.objects.create()
    result = playout_import_service.send_playout_import([{"number": 1}])

    assert result.configured is False
    assert result.sent == 0
    assert result.matched is None
    assert result.unmatched == []
    assert result.error == ""


@pytest.mark.django_db
def test__playout_import_service__fetches_missing_media():
    """Service fetches playout files that are missing metadata."""
    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
        playout_import_timeout=7,
        playout_missing_page_size=100,
    )
    payload = {
        "items": [
            {
                "id": 123,
                "filename": "clip01.mp4",
                "fs_path": "/srv/media/clip01.mp4",
                "duration_sec": 42.5,
                "file_size": 123456789,
                "status": "ok",
                "updated_at": "2026-05-28T12:00:00Z",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 100,
    }
    with patch(
        "planung.services.playout_import_service.requests.get",
        return_value=FakePlayoutResponse(payload),
    ) as mocked_get:
        result = playout_import_service.fetch_playout_missing_media(page=1, page_size=100)

    mocked_get.assert_called_once_with(
        "http://192.168.88.50/api/media/import/missing",
        params={"page": 1, "page_size": 100},
        headers={"X-API-Key": "secret-key"},
        timeout=7,
    )
    assert result.configured is True
    assert result.items == payload["items"]
    assert result.total == 1
    assert result.page == 1
    assert result.page_size == 100
    assert result.error == ""


@pytest.mark.django_db
def test__playout_import_service__missing_media_skips_when_not_configured():
    """Missing metadata service skips when no API key or URL is configured."""
    PlanungConfig.objects.create()
    result = playout_import_service.fetch_playout_missing_media(page=1, page_size=100)

    assert result.configured is False
    assert result.items == []
    assert result.total == 0
    assert result.page == 1
    assert result.page_size == 100
    assert result.error == ""


@pytest.mark.django_db
def test__planung_config__creates_missing_media_periodic_task():
    """Planning config controls the periodic missing-metadata Celery task."""
    from django_celery_beat.models import IntervalSchedule
    from django_celery_beat.models import PeriodicTask

    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
        playout_missing_sync_enabled=True,
        playout_missing_sync_interval_minutes=15,
        playout_missing_page_size=100,
    )

    task = PeriodicTask.objects.get(task="planung.tasks.sync_playout_missing_media")
    assert task.enabled is True
    assert task.interval.every == 15
    assert task.interval.period == IntervalSchedule.MINUTES
    assert task.kwargs == '{"page_size": 100}'


class FakeScheduleResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.mark.django_db
def test__playout_schedule__sends_payload_when_configured():
    """Service sends schedule payload to configured playout schedule endpoint."""
    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
        playout_import_timeout=7,
        playout_schedule_url="http://192.168.88.50/api/schedule/import/oktools",
    )
    plan_items = [{"number": 100, "start": "08:00", "duration": 1800, "title": "Morning Show"}]
    with patch(
        "planung.services.playout_import_service.build_playout_schedule_payload",
        return_value={
            "date": "2026-05-29",
            "block_id": None,
            "status": "planned",
            "items": [
                {
                    "position": 1,
                    "start": "08:00:00",
                    "duration_sec": 1800,
                    "kind": "placeholder",
                    "title": "Morning Show",
                    "youth_protection": "0+",
                }
            ],
        },
    ) as mock_build, patch(
        "planung.services.playout_import_service.requests.post",
        return_value=FakeScheduleResponse({"created": 1, "unmatched": [], "rejected": []}),
    ) as mocked_post:
        result = playout_import_service.send_playout_schedule(
            plan_date=date(2026, 5, 29),
            plan_items=plan_items,
            draft=False,
            planned=True,
        )

    mocked_post.assert_called_once_with(
        "http://192.168.88.50/api/schedule/import/oktools",
        json={
            "date": "2026-05-29",
            "block_id": None,
            "status": "planned",
            "items": [
                {
                    "position": 1,
                    "start": "08:00:00",
                    "duration_sec": 1800,
                    "kind": "placeholder",
                    "title": "Morning Show",
                    "youth_protection": "0+",
                }
            ],
        },
        headers={"Content-Type": "application/json", "X-API-Key": "secret-key"},
        timeout=7,
    )
    assert result.configured is True
    assert result.sent == 1
    assert result.created == 1
    assert result.unmatched == []
    assert result.rejected == []
    assert result.error == ""


@pytest.mark.django_db
def test__playout_schedule__builds_live_item_with_metadata(license):
    """Live schedule rows match the external playout import contract."""
    from licenses.models import YouthProtectionCategory

    license.is_live = True
    license.title = "Direkt Stadtrat"
    license.description = "Zasedanie city council"
    license.youth_protection_category = YouthProtectionCategory.NONE
    license.save(update_fields=["is_live", "title", "description", "youth_protection_category"])

    payload = playout_import_service.build_playout_schedule_payload(
        plan_date=date(2026, 9, 15),
        plan_items=[{"number": license.number, "start": "5:00", "duration": "01:00:00"}],
        draft=False,
        planned=True,
    )

    assert payload["date"] == "2026-09-15"
    assert payload["block_id"] is None
    item = payload["items"][0]
    assert item["position"] == 1
    assert item["start"] == "05:00:00"
    assert item["duration_sec"] == 3600
    assert item["kind"] == "live"
    assert item["is_live"] is True
    assert item["live_source_name"] == "Direkt Stadtrat"
    assert item["title"] == "Direkt Stadtrat"
    assert item["description"] == "Zasedanie city council"
    assert item["author"] == "john doe"
    assert item["language"] == settings.LANGUAGE_CODE.lower().split("-")[0]
    assert item["category"] == str(license.category.name)
    assert item["youth_protection"] == "0+"


@pytest.mark.django_db
def test__playout_schedule__builds_license_without_video_as_placeholder(license):
    """Licenses without an attached video are exported as playout placeholders."""
    from licenses.models import YouthProtectionCategory

    license.title = "Abendnachrichten"
    license.description = "Tagesueberblick"
    license.youth_protection_category = YouthProtectionCategory.FROM_12
    license.save(update_fields=["title", "description", "youth_protection_category"])

    payload = playout_import_service.build_playout_schedule_payload(
        plan_date=date(2026, 10, 2),
        plan_items=[
            {
                "number": license.number,
                "start": "19:00",
                "duration": "00:20:00",
                "placeholder_filename": "news_1900.mp4",
            }
        ],
        draft=False,
        planned=True,
    )

    item = payload["items"][0]
    assert item["position"] == 1
    assert item["start"] == "19:00:00"
    assert item["duration_sec"] == 1200
    assert item["kind"] == "placeholder"
    assert item["title"] == "Abendnachrichten"
    assert item["description"] == "Tagesueberblick"
    assert item["author"] == "john doe"
    assert item["language"] == settings.LANGUAGE_CODE.lower().split("-")[0]
    assert item["category"] == str(license.category.name)
    assert item["youth_protection"] == "12"
    assert item["placeholder_filename"] == "news_1900.mp4"
    assert "filename" not in item


@pytest.mark.django_db
def test__playout_schedule__returns_placeholders_created():
    """Service exposes placeholder count returned for live items without source."""
    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
        playout_schedule_url="http://192.168.88.50/api/schedule/import/oktools",
    )

    with patch(
        "planung.services.playout_import_service.build_playout_schedule_payload",
        return_value={"date": "2026-09-15", "block_id": None, "items": [{"position": 1}]},
    ), patch(
        "planung.services.playout_import_service.requests.post",
        return_value=FakeScheduleResponse({"created": 0, "placeholders_created": 1}),
    ):
        result = playout_import_service.send_playout_schedule(
            plan_date=date(2026, 9, 15),
            plan_items=[{"number": 1}],
            draft=False,
            planned=True,
        )

    assert result.created == 0
    assert result.placeholders_created == 1


@pytest.mark.django_db
def test__playout_schedule__skips_when_not_configured():
    """Service reports skipped schedule when playout_schedule_url is absent."""
    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
    )
    result = playout_import_service.send_playout_schedule(
        plan_date=date(2026, 5, 29),
        plan_items=[{"number": 1}],
        draft=False,
        planned=True,
    )

    assert result.configured is False
    assert result.sent == 0
    assert result.error == ""


@pytest.mark.django_db
def test__playout_schedule__handles_request_error():
    """Service handles connection errors gracefully."""
    from requests import RequestException

    PlanungConfig.objects.create(
        playout_import_url="http://192.168.88.50/api/media/import",
        playout_import_api_key="secret-key",
        playout_schedule_url="http://192.168.88.50/api/schedule/import/oktools",
    )
    with patch(
        "planung.services.playout_import_service.build_playout_schedule_payload",
        return_value={"date": "2026-05-29", "status": "planned", "items": [{"position": 1}]},
    ), patch(
        "planung.services.playout_import_service.requests.post",
        side_effect=RequestException("Connection refused"),
    ):
        result = playout_import_service.send_playout_schedule(
            plan_date=date(2026, 5, 29),
            plan_items=[{"number": 1}],
            draft=False,
            planned=True,
        )

    assert result.configured is True
    assert result.sent == 1
    assert result.error != ""


@pytest.mark.django_db
def test__youth_protection_mapping():
    """Youth protection category values map to external labels."""
    from licenses.models import YouthProtectionCategory

    assert playout_import_service.YOUTH_PROTECTION_MAP[YouthProtectionCategory.NONE] == "0+"
    assert playout_import_service.YOUTH_PROTECTION_MAP[YouthProtectionCategory.FROM_12] == "12"
    assert playout_import_service.YOUTH_PROTECTION_MAP[YouthProtectionCategory.FROM_16] == "16"
    assert playout_import_service.YOUTH_PROTECTION_MAP[YouthProtectionCategory.FROM_18] == "18"
