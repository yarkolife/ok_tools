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


def test_past_pickup_is_not_expected_today(synced, rental_request):
    """A missed appointment is an exception, not today's expectation."""
    rental_request.requested_start_date = (
        timezone.now() - timedelta(days=2))
    rental_request.save(update_fields=['requested_start_date'])

    assert run_check('rental.pickup_due_today') == []
    findings = run_check('rental.pickup_overdue')
    assert [item.obj.pk for item in findings] == [rental_request.pk]


def test_room_booking_is_a_human_expectation(synced, rental_request):
    """Staff sees that somebody has to open a booked room today."""
    from rental.models import Room
    from rental.models import RoomRental

    rental_request.requested_start_date = timezone.now() + timedelta(hours=1)
    rental_request.requested_end_date = timezone.now() + timedelta(hours=2)
    rental_request.save(update_fields=[
        'requested_start_date', 'requested_end_date'])
    room = Room.objects.create(name='Studio', capacity=5)
    booking = RoomRental.objects.create(
        rental_request=rental_request,
        room=room,
        people_count=3,
    )
    rental_request.rental_type = 'room'
    rental_request.save(update_fields=['rental_type'])

    findings = run_check('rental.room_due_today')

    assert [item.obj.pk for item in findings] == [booking.pk]
    assert findings[0].payload['room'] == 'Studio'
    assert run_check('rental.pickup_due_today') == []


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

def test_unconfirmed_aging_ignores_legacy_backlog(synced, license):
    """Ancient abandoned licenses do not flood the daily work queue."""
    license.__class__.objects.filter(pk=license.pk).update(
        created_at=timezone.now() - timedelta(days=365), confirmed=False)

    assert run_check('licenses.unconfirmed_aging') == []

def test_nextcloud_pending_reports_an_upload_without_a_video(synced, license):
    """An upload nobody downloaded yet is the whole point of this check."""
    from licenses.models import NextcloudVideoFile

    license.confirmed = True
    license.confirmed_at = timezone.now()
    license.save(update_fields=['confirmed', 'confirmed_at'])
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


def test_nextcloud_pending_waits_for_license_confirmation(synced, license):
    """Confirmation remains the only visible blocker for an unsigned case."""
    from licenses.models import NextcloudVideoFile

    NextcloudVideoFile.objects.create(
        license=license,
        nextcloud_file_id='42',
        filename='beitrag.mp4',
        user_uploaded=True,
        is_deleted=False,
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
        'planned': True,
        'draft': False,
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
    TagesPlan.objects.create(datum=today, json_plan={
        'planned': True,
        'draft': False,
        'items': [
            {'number': 111, 'start': '18:00', 'duration': 60,
             'title': 'Hat Video'},
            {'number': 222, 'start': '19:00', 'duration': 60,
             'title': 'Kein Video'},
        ],
    })
    storage = StorageLocation.objects.create(
        name='Playout', path='/tmp/playout', storage_type='PLAYOUT')
    VideoFile.objects.create(
        number=111, filename='111.mp4', storage_location=storage,
        file_path='/tmp/playout/111.mp4', is_available=True)

    findings = run_check('planung.plan_missing_video')

    assert len(findings) == 1
    assert findings[0].payload['number'] == 222


def test_plan_missing_video_ignores_live_contributions(
        synced, license):
    """A live stream intentionally has no physical video file."""
    from planung.models import TagesPlan

    license.is_live = True
    license.save(update_fields=['is_live'])
    TagesPlan.objects.create(
        datum=timezone.localdate(),
        json_plan={'items': [{
            'number': license.number,
            'start': '18:00',
            'duration': 60,
            'title': license.title,
        }]})

    assert run_check('planung.plan_missing_video') == []


def test_live_contribution_is_expected_today(synced, license):
    """A committed live contribution appears in today's overview."""
    from planung.models import TagesPlan

    license.is_live = True
    license.save(update_fields=['is_live'])
    TagesPlan.objects.create(
        datum=timezone.localdate(),
        json_plan={
            'planned': True,
            'draft': False,
            'items': [{
                'number': license.number,
                'start': '18:00',
                'duration': 60,
                'title': license.title,
                'is_live': True,
            }],
        })

    findings = run_check('planung.live_today')

    assert registry.get('planung.live_today').expectation is True
    assert len(findings) == 1
    assert findings[0].payload['number'] == license.number
    assert findings[0].payload['live'] is True
    assert findings[0].payload['url'].endswith(
        f'?start={timezone.localdate().isoformat()}')


def test_existing_missing_video_action_resolves_when_marked_live(
        synced, license):
    """A previously stored missing-video task disappears after switching live."""
    from notifications.process_state import inactive_event_ids
    from notifications.services import emit
    from planung.models import TagesPlan

    plan = TagesPlan.objects.create(
        datum=timezone.localdate(),
        json_plan={
            'planned': True,
            'draft': False,
            'items': [{
                'number': license.number,
                'start': '18:00',
                'title': license.title,
            }],
        })
    finding = run_check('planung.plan_missing_video')[0]
    event = emit(
        'planung.plan_missing_video',
        obj=plan,
        payload=finding.payload,
        dedup_key=finding.dedup_key,
    )

    license.__class__.objects.filter(pk=license.pk).update(is_live=True)

    assert event.pk in inactive_event_ids([event])


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


def test_unverified_aging_ignores_legacy_backlog(synced, user):
    """The daily queue is not an archive-cleanup list."""
    from registration.models import Profile

    Profile.objects.filter(pk=user.profile.pk).update(
        created_at=timezone.now() - timedelta(days=365), verified=False)

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


def test_new_rental_task_resolves_after_confirmation(synced, user):
    """Confirming a request closes the shared task for every subscriber."""
    from django.test import TestCase
    from notifications.process_state import inactive_event_ids
    from rental.models import RentalRequest

    with TestCase.captureOnCommitCallbacks(execute=True):
        rental = RentalRequest.objects.create(
            user=user,
            created_by=user,
            project_name='Interview',
            purpose='Production',
            requested_start_date=timezone.now() + timedelta(days=1),
            requested_end_date=timezone.now() + timedelta(days=2),
            status='draft',
        )
    event = NotificationEvent.objects.get(event_type='rental.new_request')

    rental.status = 'reserved'
    rental.save(update_fields=['status'])

    assert event.pk in inactive_event_ids([event])


def test_new_video_signal_leaves_normal_indexing_to_automation(synced, db):
    """Finding a file is normal and creates no human attention item."""
    from django.test import TestCase
    from media_files.models import StorageLocation
    from media_files.models import VideoFile
    from notifications.models import NotificationEventTypeConfig

    storage = StorageLocation.objects.create(
        name='Playout', path='/tmp/playout', storage_type='PLAYOUT')
    NotificationEventTypeConfig.objects.filter(
        code='media_files.new_video').update(
            params={'storage_location_ids': [storage.pk]})
    with TestCase.captureOnCommitCallbacks(execute=True):
        VideoFile.objects.create(
            number=1, filename='reel.mp4', storage_location=storage,
            file_path='/tmp/playout/reel.mp4', is_preview=True)
        VideoFile.objects.create(
            number=2, filename='beitrag.mp4', storage_location=storage,
            file_path='/tmp/playout/beitrag.mp4')

    events = NotificationEvent.objects.filter(
        event_type='media_files.new_video')
    assert events.count() == 0


def test_new_video_signal_does_not_report_monitored_locations(synced, db):
    """Even monitored locations stay quiet while automation can proceed."""
    from django.test import TestCase
    from media_files.models import StorageLocation
    from media_files.models import VideoFile
    from notifications.models import NotificationEventTypeConfig

    monitored = StorageLocation.objects.create(
        name='Incoming', path='/tmp/incoming', storage_type='CUSTOM')
    ignored = StorageLocation.objects.create(
        name='Playout', path='/tmp/playout', storage_type='PLAYOUT')
    NotificationEventTypeConfig.objects.filter(
        code='media_files.new_video').update(
            params={'storage_location_ids': [monitored.pk]})

    with TestCase.captureOnCommitCallbacks(execute=True):
        VideoFile.objects.create(
            number=1, filename='incoming.mp4', storage_location=monitored,
            file_path='/tmp/incoming/incoming.mp4')
        VideoFile.objects.create(
            number=2, filename='playout.mp4', storage_location=ignored,
            file_path='/tmp/playout/playout.mp4')

    events = NotificationEvent.objects.filter(
        event_type='media_files.new_video')
    assert not events.exists()


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
