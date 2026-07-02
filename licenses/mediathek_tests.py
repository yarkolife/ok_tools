from contributions.models import Contribution
from django.utils import timezone
from licenses.services.peertube_service import compute_lookup_eta
from licenses.services.peertube_service import compute_publish_time_for_license
from licenses.services.peertube_service import find_video_by_number_in_channel
from licenses.services.peertube_service import normalize_channel_handle
from licenses.services.peertube_service import parse_target_channel
from licenses.services.peertube_service import resolve_peertube_endpoint
from licenses.tasks import rescan_mediathek_links_from_contributions
from licenses.tasks import rescan_mediathek_links_from_planung
from planung.models import TagesPlan
import datetime
import pytest


@pytest.mark.django_db
def test__licenses__peertube_service__parse_target_channel():
    """Target channel parser returns handle and domain."""
    handle, domain = parse_target_channel('@ok_dessau@lokalmedial.de')
    assert handle == 'ok_dessau'
    assert domain == 'lokalmedial.de'


@pytest.mark.django_db
def test__licenses__peertube_service__resolve_endpoint_prefers_org_channel():
    """Endpoint resolver uses OrganizationConfig channel when provided."""
    endpoint = resolve_peertube_endpoint(
        target_channel='@ok_dessau@lokalmedial.de',
        organization_channel='ok_org',
    )
    assert endpoint.base_url == 'https://lokalmedial.de'
    assert endpoint.channel_handle == 'ok_org'


@pytest.mark.django_db
def test__licenses__peertube_service__compute_publish_time_from_contribution(license):
    """Publish time uses contribution broadcast date with highest priority."""
    dt = timezone.now() + datetime.timedelta(hours=2)
    Contribution.objects.create(license=license, broadcast_date=dt, live=False)

    publish_time = compute_publish_time_for_license(license)
    assert publish_time is not None
    assert publish_time == dt


@pytest.mark.django_db
def test__licenses__peertube_service__compute_publish_time_from_tagesplan(license):
    """Publish time falls back to planned TagesPlan start time."""
    TagesPlan.objects.create(
        datum=datetime.date(2025, 1, 15),
        json_plan={
            'items': [{'number': license.number, 'start': '18:00'}],
            'draft': False,
            'planned': True,
        },
    )

    publish_time = compute_publish_time_for_license(license)
    assert publish_time is not None
    assert publish_time.date().isoformat() == '2025-01-15'
    assert publish_time.hour == 18


@pytest.mark.django_db
def test__licenses__peertube_service__compute_lookup_eta_adds_5_minutes():
    """ETA is publish_time plus 5 minutes."""
    now = timezone.now()
    eta = compute_lookup_eta(now)
    assert eta == now + datetime.timedelta(minutes=5)


@pytest.mark.django_db
def test__licenses__peertube_service__normalize_channel_handle():
    """Channel handle normalizer strips @ and optional host part."""
    assert normalize_channel_handle('@okmq@lokalmedial.de') == 'okmq'
    assert normalize_channel_handle('okmq@lokalmedial.de') == 'okmq'
    assert normalize_channel_handle('okmq') == 'okmq'


@pytest.mark.django_db
def test__licenses__peertube_service__find_video_uses_normalized_handle(monkeypatch):
    """Video search uses normalized handle in channel videos endpoint."""
    calls = []

    def _fake_peertube_get_json(base_url, path, params=None, timeout=15):
        calls.append(path)
        if path == '/api/v1/video-channels/okmq/videos':
            return {
                'data': [
                    {
                        'uuid': 'video-uuid-1',
                        'pluginData': {'videoNumber': '123'},
                    }
                ]
            }

        if path == '/api/v1/videos/video-uuid-1':
            return {'uuid': 'video-uuid-1', 'shortUUID': 'short-1', 'pluginData': {'videoNumber': '123'}}

        raise AssertionError(f'Unexpected path: {path}')

    monkeypatch.setattr('licenses.services.peertube_service.peertube_get_json', _fake_peertube_get_json)

    video = find_video_by_number_in_channel(
        'https://lokalmedial.de',
        'okmq@lokalmedial.de',
        '123',
    )

    assert video is not None
    assert video.get('shortUUID') == 'short-1'
    assert '/api/v1/video-channels/okmq/videos' in calls
    assert '/api/v1/video-channels/okmq%40lokalmedial.de/videos' not in calls


@pytest.mark.django_db
def test__licenses__tasks__rescan_mediathek_links_from_planung_queues_missing_url(license, monkeypatch):
    """Planning periodic task queues refreshes for planned licenses without mediathek URL."""
    calls = []

    def _fake_apply_async(args=None, kwargs=None, eta=None):
        calls.append({'args': args, 'kwargs': kwargs, 'eta': eta})

    monkeypatch.setattr('licenses.tasks.refresh_license_mediathek_url.apply_async', _fake_apply_async)
    license.store_in_ok_media_library = True
    license.mediathek_url = ''
    license.save(update_fields=['store_in_ok_media_library', 'mediathek_url'])
    TagesPlan.objects.create(
        datum=timezone.localdate(),
        json_plan={
            'items': [{'number': license.number, 'start': '18:00'}],
            'draft': False,
            'planned': True,
        },
    )

    result = rescan_mediathek_links_from_planung()

    assert result['source'] == 'planung'
    assert result['queued_count'] == 1
    assert calls[0]['args'] == [license.number]
    assert calls[0]['kwargs'] == {'force': True, 'send_notification_email': False}


@pytest.mark.django_db
def test__licenses__tasks__rescan_mediathek_links_from_contributions_skips_existing_url(license, monkeypatch):
    """Contribution periodic task does not queue licenses that already have mediathek URL."""
    calls = []

    def _fake_apply_async(args=None, kwargs=None, eta=None):
        calls.append({'args': args, 'kwargs': kwargs, 'eta': eta})

    monkeypatch.setattr('licenses.tasks.refresh_license_mediathek_url.apply_async', _fake_apply_async)
    license.store_in_ok_media_library = True
    license.mediathek_url = 'https://lokalmedial.de/w/existing'
    license.save(update_fields=['store_in_ok_media_library', 'mediathek_url'])
    Contribution.objects.create(
        license=license,
        broadcast_date=timezone.now(),
        live=False,
    )

    result = rescan_mediathek_links_from_contributions()

    assert result['source'] == 'contributions'
    assert result['queued_count'] == 0
    assert calls == []
