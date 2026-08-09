"""Tests for the individual checks of the event catalogue (stage 2).

Every check builds its own data instead of relying on whatever the local
database happens to contain, so a result here means the query is right, not
that the fixture database was in a convenient state.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from notifications import config
from notifications import registry
from notifications.models import NotificationEvent
from notifications.tasks import run_scan
import pytest


def run_check(code):
    """Run one registered check with its effective parameters."""
    return registry.get_check(code)(config.get_params(code))


@pytest.fixture(scope='function')
def synced(db):
    """Make sure the configuration table mirrors the registry."""
    config.sync_event_type_configs()


@pytest.fixture(scope='function')
def rental_request(db, user):
    """Return a reserved rental request starting and ending today."""
    from rental.models import RentalRequest

    now = timezone.now()
    return RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name='Testdreh',
        purpose='Test',
        requested_start_date=now,
        requested_end_date=now,
        status='reserved',
    )


# ---------------------------------------------------------------------------
# rental
# ---------------------------------------------------------------------------

def test_pickup_due_reports_reserved_rentals(synced, rental_request):
    """A reservation starting today is expected today."""
    findings = run_check('rental.pickup_due_today')

    assert [item.obj.pk for item in findings] == [rental_request.pk]
    assert findings[0].payload['project_name'] == 'Testdreh'


def test_links_point_at_the_working_screens(synced, rental_request):
    """A rental notification opens the affected request, not a list."""
    findings = run_check('rental.pickup_due_today')

    assert findings[0].payload['url'] == (
        f'/rental/rental/{rental_request.pk}/')
    assert '/admin/rental/rentalrequest/' not in findings[0].payload['url']


def test_pickup_due_ignores_issued_rentals(synced, rental_request):
    """Once handed out, a rental is no longer a pick-up."""
    rental_request.status = 'issued'
    rental_request.save()

    assert run_check('rental.pickup_due_today') == []
    assert len(run_check('rental.return_due_today')) == 1


def test_overdue_respects_the_grace_period(synced, rental_request):
    """A rental one hour late is not yet overdue with a one day grace."""
    rental_request.status = 'issued'
    rental_request.requested_end_date = timezone.now() - timedelta(hours=1)
    rental_request.save()

    assert run_check('rental.return_overdue') == []

    rental_request.requested_end_date = timezone.now() - timedelta(days=10)
    rental_request.save()
    findings = run_check('rental.return_overdue')

    assert len(findings) == 1
    assert findings[0].payload['days_late'] == 10


def test_overdue_escalates_in_steps(synced, rental_request):
    """The key changes every escalation period, so it comes back once."""
    rental_request.status = 'issued'
    rental_request.requested_end_date = timezone.now() - timedelta(days=3)
    rental_request.save()
    first = run_check('rental.return_overdue')[0].dedup_key

    rental_request.requested_end_date = timezone.now() - timedelta(days=5)
    rental_request.save()
    same_bucket = run_check('rental.return_overdue')[0].dedup_key

    rental_request.requested_end_date = timezone.now() - timedelta(days=20)
    rental_request.save()
    next_bucket = run_check('rental.return_overdue')[0].dedup_key

    assert first == same_bucket
    assert next_bucket != first


# ---------------------------------------------------------------------------
# licenses
# ---------------------------------------------------------------------------

def test_nextcloud_pending_reports_an_upload_without_a_video(synced, license):
    """An upload nobody downloaded yet is the whole point of this check."""
    from licenses.models import NextcloudVideoFile

    NextcloudVideoFile.objects.create(
        license=license,
        nextcloud_file_id='42',
        filename='beitrag.mp4',
        user_uploaded=True,
        is_deleted=False,
    )

    findings = run_check('licenses.nextcloud_download_pending')

    assert len(findings) == 1
    assert findings[0].payload['filename'] == 'beitrag.mp4'
    assert findings[0].obj.pk == license.pk


def test_nextcloud_pending_ignores_downloaded_uploads(synced, license):
    """Once the video is on a storage location, there is nothing to do."""
    from licenses.models import NextcloudVideoFile
    from media_files.models import StorageLocation
    from media_files.models import VideoFile

    NextcloudVideoFile.objects.create(
        license=license,
        nextcloud_file_id='42',
        filename='beitrag.mp4',
        user_uploaded=True,
        is_deleted=False,
    )
    storage = StorageLocation.objects.create(
        name='Archiv', path='/tmp/archive', storage_type='ARCHIVE')
    VideoFile.objects.create(
        number=license.number,
        filename='beitrag.mp4',
        storage_location=storage,
        file_path='/tmp/archive/beitrag.mp4',
        is_available=True,
    )

    assert run_check('licenses.nextcloud_download_pending') == []


def test_nextcloud_pending_ignores_deleted_uploads(synced, license):
    """A deleted upload is not waiting for anything."""
    from licenses.models import NextcloudVideoFile

    NextcloudVideoFile.objects.create(
        license=license,
        nextcloud_file_id='42',
        filename='beitrag.mp4',
        user_uploaded=True,
        is_deleted=True,
    )

    assert run_check('licenses.nextcloud_download_pending') == []


# ---------------------------------------------------------------------------
# austausch
# ---------------------------------------------------------------------------

def test_exchange_reports_only_new_material(synced, db):
    """Imported material and old finds are not worth reporting."""
    from austausch.models import ExchangeItem

    fresh = ExchangeItem.objects.create(
        contribution_id=1, filename='neu.mp4', file_path='/x/neu.mp4',
        channel='OK Halle', title='Neuer Beitrag', import_status='new')
    ExchangeItem.objects.create(
        contribution_id=2, filename='alt.mp4', file_path='/x/alt.mp4',
        channel='OK Halle', title='Importiert', import_status='imported')
    stale = ExchangeItem.objects.create(
        contribution_id=3, filename='stale.mp4', file_path='/x/stale.mp4',
        channel='OK Halle', title='Zu alt', import_status='new')
    ExchangeItem.objects.filter(pk=stale.pk).update(
        discovered_at=timezone.now() - timedelta(days=90))

    findings = run_check('austausch.new_items')

    assert [item.obj.pk for item in findings] == [fresh.pk]
    # The exchange is worked in the feed, filtered down to the file.
    assert findings[0].payload['url'].startswith('/austausch/feed/?')
    assert 'neu.mp4' in findings[0].payload['url']


# ---------------------------------------------------------------------------
# planung
# ---------------------------------------------------------------------------

def test_plan_missing_reports_empty_and_absent_days(synced, db):
    """Dead air is the most expensive thing this system can catch."""
    from planung.models import TagesPlan

    today = timezone.localdate()
    TagesPlan.objects.create(datum=today + timedelta(days=1), json_plan={
        'items': [{'number': 1, 'start': '18:00', 'duration': 60}]})
    TagesPlan.objects.create(
        datum=today + timedelta(days=2), json_plan={'items': []})

    findings = run_check('planung.plan_missing')

    # Day one has content, day two is empty and therefore reported.
    assert len(findings) == 1
    assert findings[0].payload['date'] == (
        today + timedelta(days=2)).strftime('%d.%m.%Y')
    # Planning is done in the weekly calendar, opened on that day.
    assert findings[0].payload['url'] == (
        '/admin/planung/tagesplan/calendar-weeks/'
        f'?start={(today + timedelta(days=2)).isoformat()}')


def test_plan_missing_video_reports_numbers_without_media(synced, db):
    """A planned entry without a file will not go on air."""
    from media_files.models import StorageLocation
    from media_files.models import VideoFile
    from planung.models import TagesPlan

    today = timezone.localdate()
    TagesPlan.objects.create(datum=today, json_plan={'items': [
        {'number': 111, 'start': '18:00', 'duration': 60, 'title': 'Hat Video'},
        {'number': 222, 'start': '19:00', 'duration': 60, 'title': 'Kein Video'},
    ]})
    storage = StorageLocation.objects.create(
        name='Playout', path='/tmp/playout', storage_type='PLAYOUT')
    VideoFile.objects.create(
        number=111, filename='111.mp4', storage_location=storage,
        file_path='/tmp/playout/111.mp4', is_available=True)

    findings = run_check('planung.plan_missing_video')

    assert len(findings) == 1
    assert findings[0].payload['number'] == 222


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def test_unverified_aging_reports_old_profiles(synced, user):
    """An unverified profile that nobody looked at for weeks."""
    from registration.models import Profile

    Profile.objects.filter(pk=user.profile.pk).update(
        created_at=timezone.now() - timedelta(days=60))

    findings = run_check('registration.unverified_aging')

    assert [item.obj.pk for item in findings] == [user.profile.pk]


def test_unverified_aging_ignores_verified_profiles(synced, user):
    """Verification is exactly what closes this finding."""
    from registration.models import Profile

    Profile.objects.filter(pk=user.profile.pk).update(
        created_at=timezone.now() - timedelta(days=60), verified=True)

    assert run_check('registration.unverified_aging') == []


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------

def test_new_profile_signal_creates_an_event(synced, db, user_dict):
    """Registering raises the verification task by itself."""
    from django.test import TestCase
    from ok_tools.testing import create_user

    with TestCase.captureOnCommitCallbacks(execute=True):
        create_user(user_dict)

    event = NotificationEvent.objects.filter(
        event_type='registration.new_profile').first()
    assert event is not None
    assert user_dict['email'] in event.message


def test_new_video_signal_skips_preview_clips(synced, db):
    """Rendered reels are produced by the system and need no review."""
    from django.test import TestCase
    from media_files.models import StorageLocation
    from media_files.models import VideoFile

    storage = StorageLocation.objects.create(
        name='Playout', path='/tmp/playout', storage_type='PLAYOUT')
    with TestCase.captureOnCommitCallbacks(execute=True):
        VideoFile.objects.create(
            number=1, filename='reel.mp4', storage_location=storage,
            file_path='/tmp/playout/reel.mp4', is_preview=True)
        VideoFile.objects.create(
            number=2, filename='beitrag.mp4', storage_location=storage,
            file_path='/tmp/playout/beitrag.mp4')

    events = NotificationEvent.objects.filter(
        event_type='media_files.new_video')
    assert events.count() == 1
    assert 'beitrag.mp4' in events.first().message


# ---------------------------------------------------------------------------
# the scan as a whole
# ---------------------------------------------------------------------------

def test_scan_stores_facts_but_not_expectations(synced, rental_request):
    """The split between facts and expectations holds for the catalogue."""
    rental_request.status = 'issued'
    rental_request.requested_end_date = timezone.now() - timedelta(days=10)
    rental_request.save()

    run_scan()

    assert NotificationEvent.objects.filter(
        event_type='rental.return_overdue').count() == 1
    assert not NotificationEvent.objects.filter(
        event_type__endswith='_due_today').exists()
