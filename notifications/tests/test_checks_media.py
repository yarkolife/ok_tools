"""Tests for the stage 3 checks: format, reels, covers and the rest.

As in ``test_checks.py``, each test builds its own data. The local database
is an old production copy where most of these checks legitimately find
nothing, so it can neither confirm nor refute a query.
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from notifications import config
from notifications import registry
from notifications.models import NotificationEvent
from notifications.models import UserNotification
import pytest


def run_check(code):
    """Run one registered check with its effective parameters."""
    return registry.get_check(code)(config.get_params(code))


@pytest.fixture(scope='function')
def synced(db):
    """Make sure the configuration table mirrors the registry."""
    config.sync_event_type_configs()


@pytest.fixture(scope='function')
def storage(db, tmp_path):
    """Return an active playout storage location on a real directory.

    The disk space check reads the path, so it has to exist.
    """
    from media_files.models import StorageLocation

    return StorageLocation.objects.create(
        name='Playout', path=str(tmp_path), storage_type='PLAYOUT')


@pytest.fixture(scope='function')
def preset(db):
    """Return the encoding preset that defines the expected format."""
    from media_files.models import MediaFilesConfig
    from tools.models import VideoEncodePreset

    preset = VideoEncodePreset.objects.create(
        name='1080p25', display_name='1080p25',
        width=1920, height=1080, fps=25,
        vcodec='libx264', video_bitrate_k=9000,
        acodec='aac', audio_bitrate_k=192,
        audio_sample_rate=48000, audio_channels=2)
    media_config = MediaFilesConfig.get_config()
    media_config.transcode_encode_preset = '1080p25'
    media_config.save()
    return preset


@pytest.fixture(scope='function')
def own_authority(db):
    """Point the organization at a media authority and return it."""
    from registration.models import MediaAuthority
    from registration.models import OrganizationConfig

    authority = MediaAuthority.objects.create(name='OK Test')
    config_obj = OrganizationConfig.get_config()
    config_obj.media_authority = authority
    config_obj.save()
    return authority


# ---------------------------------------------------------------------------
# format
# ---------------------------------------------------------------------------

def test_format_mismatch_reports_wrong_resolution(
        synced, storage, preset, license):
    """A file that is not 1920x1080 has to be converted."""
    from media_files.models import VideoFile

    VideoFile.objects.create(
        number=999999, filename='ok.mp4', storage_location=storage,
        file_path='/tmp/playout/ok.mp4', width=1920, height=1080, fps=25.0)
    VideoFile.objects.create(
        number=license.number, filename='hd.mp4', storage_location=storage,
        file_path='/tmp/playout/hd.mp4', width=1280, height=720, fps=25.0)

    findings = run_check('media_files.format_mismatch')

    assert len(findings) == 1
    assert findings[0].payload['filename'] == 'hd.mp4'
    assert 'resolution' in findings[0].payload['deviation']


def test_format_mismatch_tolerates_ffprobe_rounding(
        synced, storage, preset, license):
    """25.000001 fps is fine; 30 is not."""
    from media_files.models import VideoFile

    rounded = VideoFile.objects.create(
        number=license.number, filename='rounded.mp4', storage_location=storage,
        file_path='/tmp/playout/rounded.mp4',
        width=1920, height=1080, fps=24.999)

    assert run_check('media_files.format_mismatch') == []

    rounded.delete()
    VideoFile.objects.create(
        number=license.number, filename='thirty.mp4', storage_location=storage,
        file_path='/tmp/playout/thirty.mp4',
        width=1920, height=1080, fps=30.0)

    findings = run_check('media_files.format_mismatch')

    assert [item.payload['filename'] for item in findings] == ['thirty.mp4']
    assert 'fps' in findings[0].payload['deviation']


def test_format_mismatch_needs_a_preset(synced, storage, db):
    """Without a configured norm the check reports nothing at all."""
    from media_files.models import VideoFile

    VideoFile.objects.create(
        number=2, filename='hd.mp4', storage_location=storage,
        file_path='/tmp/playout/hd.mp4', width=1280, height=720, fps=25.0)

    assert run_check('media_files.format_mismatch') == []


# ---------------------------------------------------------------------------
# reels and covers
# ---------------------------------------------------------------------------

def _plan_own_license(license_obj, authority, storage, days_ahead=1):
    """Put a confirmed own production with a full video on the plan."""
    from media_files.models import VideoFile
    from planung.models import TagesPlan

    profile = license_obj.profile
    profile.media_authority = authority
    profile.save()
    license_obj.confirmed = True
    license_obj.confirmed_at = timezone.now()
    license_obj.save(update_fields=['confirmed', 'confirmed_at'])
    VideoFile.objects.create(
        number=license_obj.number,
        filename=f'{license_obj.number}.mp4',
        storage_location=storage,
        file_path=f'/tmp/playout/{license_obj.number}.mp4',
        license=license_obj,
    )
    TagesPlan.objects.create(
        datum=timezone.localdate() + timedelta(days=days_ahead),
        json_plan={
            'planned': True,
            'draft': False,
            'items': [{
                'number': license_obj.number, 'start': '18:00',
                'duration': 60, 'title': license_obj.title,
            }],
        })


def test_missing_reel_reports_own_planned_production(synced, license,
                                                     own_authority, storage):
    """An own production going on air soon and no reel rendered."""
    _plan_own_license(license, own_authority, storage)

    findings = run_check('media_files.missing_reel')

    assert len(findings) == 1
    assert findings[0].payload['number'] == license.number


def test_missing_reel_ignores_other_channels(synced, license, own_authority,
                                             storage):
    """Material of another channel is not our reel to make."""
    from registration.models import MediaAuthority

    _plan_own_license(license, own_authority, storage)
    other = MediaAuthority.objects.create(name='OK Other')
    profile = license.profile
    profile.media_authority = other
    profile.save()

    assert run_check('media_files.missing_reel') == []


def test_missing_reel_is_closed_by_an_existing_reel(synced, license,
                                                    own_authority, storage):
    """A rendered reel is registered as a preview clip."""
    from media_files.models import VideoFile

    _plan_own_license(license, own_authority, storage)
    VideoFile.objects.create(
        number=license.number, filename=f'{license.number}_reel.mp4',
        storage_location=storage,
        file_path=f'/tmp/playout/{license.number}_reel.mp4',
        is_preview=True)

    assert run_check('media_files.missing_reel') == []


def _configure_reel_studio(enabled=True):
    """Configure ToolsConfig so the Reel Studio counts as usable."""
    from tools.models import ToolsConfig

    config_obj = ToolsConfig.get_config()
    config_obj.reel_studio_enabled = enabled
    config_obj.reel_render_url = 'http://reel.example:8011'
    config_obj.reel_render_api_key = 'secret-key'
    config_obj.save()
    return config_obj


def _reel_feed_row(client, license_obj, authority, storage, admin_user):
    """Store the reel finding and return its row as the feed page serves it."""
    from notifications import selectors
    from notifications.process_state import refresh_missing_asset_events

    selectors.set_subscriptions(admin_user, ['media_files'], [])
    _plan_own_license(license_obj, authority, storage)
    refresh_missing_asset_events()
    client.force_login(admin_user)

    response = client.get('/admin/notifications/')
    rows = response.context_data['notifications_data']['rows']
    return next(
        row for row in rows
        if row['eventType'] == 'media_files.missing_reel')


def test_missing_reel_hands_over_the_prefilled_reel_studio(
        synced, license, own_authority, storage, client, admin_user):
    """The entry offers the render form; the number alone is not the work."""
    _configure_reel_studio()

    row = _reel_feed_row(client, license, own_authority, storage, admin_user)

    assert row['actionUrl'].startswith('/tools/reel-studio/?')
    assert 'output_name=' in row['actionUrl']
    assert 'video_id=' in row['actionUrl']
    assert row['actionLabel']


def test_missing_reel_offers_no_link_without_a_reel_studio(
        synced, license, own_authority, storage, client, admin_user):
    """An unconfigured renderer must not produce a dead button."""
    _configure_reel_studio(enabled=False)

    row = _reel_feed_row(client, license, own_authority, storage, admin_user)

    assert row['actionUrl'] == ''
    assert row['actionLabel'] == ''


def test_missing_assets_wait_for_confirmation_and_full_video(
        synced, license, own_authority):
    """Cover and reel are not the next step while confirmation/video blocks."""
    from planung.models import TagesPlan

    profile = license.profile
    profile.media_authority = own_authority
    profile.save()
    TagesPlan.objects.create(
        datum=timezone.localdate() + timedelta(days=1),
        json_plan={
            'planned': True,
            'draft': False,
            'items': [{
                'number': license.number,
                'start': '18:00',
                'title': license.title,
            }],
        })

    assert run_check('media_files.missing_reel') == []
    assert run_check('media_files.missing_cover') == []


def test_missing_assets_ignore_live_contributions(
        synced, license, own_authority, storage):
    """A planned stream needs neither a generated cover nor a reel."""
    _plan_own_license(license, own_authority, storage)
    license.__class__.objects.filter(pk=license.pk).update(is_live=True)

    assert run_check('media_files.missing_reel') == []
    assert run_check('media_files.missing_cover') == []


def test_missing_cover_reports_own_planned_production(synced, license,
                                                      own_authority, storage,
                                                      tmp_path):
    """Covers live on disk, so the check looks at the cover directory."""
    from media_files.models import MediaFilesConfig

    _plan_own_license(license, own_authority, storage)
    media_config = MediaFilesConfig.get_config()
    media_config.cover_enabled = True
    media_config.cover_output_dir = str(tmp_path)
    media_config.save()

    findings = run_check('media_files.missing_cover')
    assert len(findings) == 1

    (tmp_path / f'{license.number}_cover.jpg').write_bytes(b'x')
    assert run_check('media_files.missing_cover') == []


def test_missing_asset_checks_need_the_own_authority(synced, license, db):
    """Without the own authority we would report other channels as ours."""
    from registration.models import OrganizationConfig

    config_obj = OrganizationConfig.get_config()
    config_obj.media_authority = None
    config_obj.save()

    assert run_check('media_files.missing_reel') == []
    assert run_check('media_files.missing_cover') == []


# ---------------------------------------------------------------------------
# the rest of the catalogue
# ---------------------------------------------------------------------------

def test_confirmed_without_video_reports_blocked_licenses(synced, license):
    """Staff is alerted only after uploads and indexing had time to finish."""
    license.confirmed = True
    license.confirmed_at = timezone.now() - timedelta(days=4)
    license.save(update_fields=['confirmed', 'confirmed_at'])

    findings = run_check('licenses.confirmed_without_video')

    assert [item.obj.pk for item in findings] == [license.pk]


def test_confirmed_live_license_needs_no_video(synced, license):
    """Confirmation completes the video step for a live stream."""
    license.confirmed = True
    license.confirmed_at = timezone.now()
    license.is_live = True
    license.save(update_fields=['confirmed', 'confirmed_at', 'is_live'])

    assert run_check('licenses.confirmed_without_video') == []


def test_orphan_video_reports_unlinked_files(synced, storage):
    """A file the scan could not link to a license needs a human."""
    from media_files.models import VideoFile
    from notifications.models import NotificationEventTypeConfig

    NotificationEventTypeConfig.objects.filter(
        code='media_files.orphan_video').update(
            params={
                'days': 30,
                'grace_hours': 24,
                'storage_location_ids': [storage.pk],
            })

    orphan = VideoFile.objects.create(
        number=999, filename='orphan.mp4', storage_location=storage,
        file_path='/tmp/playout/orphan.mp4', is_available=True)
    VideoFile.objects.filter(pk=orphan.pk).update(
        created_at=timezone.now() - timedelta(hours=25))

    findings = run_check('media_files.orphan_video')

    assert [item.obj.pk for item in findings] == [orphan.pk]


def test_orphan_video_ignores_unselected_storage(synced, storage):
    """An empty folder selection deliberately disables this notification."""
    from media_files.models import VideoFile

    orphan = VideoFile.objects.create(
        number=999, filename='orphan.mp4', storage_location=storage,
        file_path='/tmp/playout/orphan.mp4', is_available=True)
    VideoFile.objects.filter(pk=orphan.pk).update(
        created_at=timezone.now() - timedelta(hours=25))

    assert run_check('media_files.orphan_video') == []


def test_storage_low_uses_the_threshold(synced, storage):
    """A threshold of 100 percent reports every mounted location."""
    from notifications.models import NotificationEventTypeConfig

    NotificationEventTypeConfig.objects.filter(
        code='media_files.storage_low').update(
            params={'threshold_percent': 100})

    findings = run_check('media_files.storage_low')

    assert [item.obj.pk for item in findings] == [storage.pk]
    assert findings[0].payload['free_percent'] < 100


def test_unmounted_storage_is_a_problem(synced, db, tmp_path):
    """An unreadable NAS must not be mistaken for healthy free space."""
    from media_files.models import StorageLocation

    missing = StorageLocation.objects.create(
        name='Offline NAS',
        path=str(tmp_path / 'not-mounted'),
        storage_type='ARCHIVE',
        is_active=True,
    )

    findings = run_check('media_files.storage_unavailable')

    assert [item.obj.pk for item in findings] == [missing.pk]


def test_ready_reel_requires_manual_posting_today(
        synced, license, own_authority, storage):
    """A prepared reel becomes human work on its contribution's air date."""
    from media_files.models import VideoFile
    from planung.models import TagesPlan

    license.profile.media_authority = own_authority
    license.profile.save()
    license.confirmed = True
    license.confirmed_at = timezone.now()
    license.save(update_fields=['confirmed', 'confirmed_at'])
    VideoFile.objects.create(
        number=license.number,
        filename=f'{license.number}.mp4',
        storage_location=storage,
        file_path=f'{license.number}.mp4',
        license=license,
    )
    VideoFile.objects.create(
        number=license.number,
        filename=f'{license.number}_reel.mp4',
        storage_location=storage,
        file_path=f'{license.number}_reel.mp4',
        is_preview=True,
    )
    TagesPlan.objects.create(
        datum=timezone.localdate(),
        json_plan={
            'planned': True,
            'draft': False,
            'items': [{
                'number': license.number,
                'start': '18:00',
                'title': license.title,
            }],
        },
    )

    findings = run_check('media_files.reel_post_today')

    assert [item.obj.pk for item in findings] == [license.pk]


def test_not_aired_reports_missed_broadcasts(synced, db):
    """A scheduled start that never began is a technical problem."""
    from planung.models import AirReport

    missed = AirReport.objects.create(
        external_id='1', media_filename='beitrag.mp4',
        scheduled_start=timezone.now() - timedelta(hours=2))
    AirReport.objects.create(
        external_id='2', media_filename='lief.mp4',
        scheduled_start=timezone.now() - timedelta(hours=2),
        started_at=timezone.now() - timedelta(hours=2))

    findings = run_check('planung.not_aired')

    assert [item.obj.pk for item in findings] == [missed.pk]


def test_task_failures_are_grouped_by_task(synced, db):
    """A broken task fails on every run and must not fill the page."""
    from django_celery_results.models import TaskResult

    for index in range(3):
        TaskResult.objects.create(
            task_id=f'id-{index}', task_name='app.tasks.broken',
            status='FAILURE', date_done=timezone.now())

    findings = run_check('system.task_failures')

    assert len(findings) == 1
    assert findings[0].payload['count'] == 3


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------

def test_committed_plan_emits_missing_asset_events_immediately(
        synced, license, own_authority, storage):
    """A newly committed plan need not wait for tomorrow's digest scan."""
    from media_files.models import VideoFile
    from planung.models import TagesPlan

    profile = license.profile
    profile.media_authority = own_authority
    profile.save()
    with TestCase.captureOnCommitCallbacks(execute=True):
        license.confirmed = True
        license.confirmed_at = timezone.now()
        license.save(update_fields=['confirmed', 'confirmed_at'])
        VideoFile.objects.create(
            number=license.number,
            filename=f'{license.number}.mp4',
            storage_location=storage,
            file_path=f'/tmp/playout/{license.number}.mp4',
            license=license,
        )
        TagesPlan.objects.create(
            datum=timezone.localdate() + timedelta(days=1),
            json_plan={
                'planned': True,
                'draft': False,
                'items': [{
                    'number': license.number,
                    'start': '18:00',
                    'title': license.title,
                }],
            })

    assert set(NotificationEvent.objects.filter(
        object_id=license.pk).values_list('event_type', flat=True)) == {
            'media_files.missing_cover',
            'media_files.missing_reel',
        }


def test_failed_operation_creates_a_problem_event(synced, storage):
    """A failed render is reported, a successful one is not."""
    from media_files.models import FileOperation
    from media_files.models import VideoFile

    video = VideoFile.objects.create(
        number=1, filename='beitrag.mp4', storage_location=storage,
        file_path='/tmp/playout/beitrag.mp4')
    with TestCase.captureOnCommitCallbacks(execute=True):
        FileOperation.objects.create(
            video_file=video, operation_type='RENDER', status='SUCCESS')
        FileOperation.objects.create(
            video_file=video, operation_type='RENDER', status='FAILED',
            error_message='ffmpeg exited with 1')

    events = NotificationEvent.objects.filter(
        event_type='media_files.operation_failed')
    assert events.count() == 1


def test_successful_retry_resolves_file_operation_problem(synced, storage):
    """A recovered automatic operation no longer asks for attention."""
    from media_files.models import FileOperation
    from media_files.models import VideoFile
    from notifications.process_state import inactive_event_ids

    video = VideoFile.objects.create(
        number=1, filename='beitrag.mp4', storage_location=storage,
        file_path='/tmp/playout/beitrag.mp4')
    with TestCase.captureOnCommitCallbacks(execute=True):
        FileOperation.objects.create(
            video_file=video, operation_type='RENDER', status='FAILED',
            error_message='ffmpeg exited with 1')
    event = NotificationEvent.objects.get(
        event_type='media_files.operation_failed')
    FileOperation.objects.create(
        video_file=video, operation_type='RENDER', status='SUCCESS')

    assert event.pk in inactive_event_ids([event])


def test_failed_job_goes_to_its_owner_only(synced, db, user_dict):
    """Only a failed render needs its initiator's attention."""
    from notifications import selectors
    from ok_tools.testing import create_user
    from tools.models import SlideshowProject

    owner = create_user(user_dict, is_staff=True)
    other = create_user(
        {**user_dict, 'email': 'other@example.org'}, is_staff=True)
    selectors.set_subscriptions(other, ['tools'], [])

    with TestCase.captureOnCommitCallbacks(execute=True):
        SlideshowProject.objects.create(
            name='Successful show', created_by=owner, status='completed')
        SlideshowProject.objects.create(
            name='Failed show', created_by=owner, status='failed')

    assert UserNotification.objects.filter(
        user=owner, event__event_type='tools.job_failed').count() == 1
    assert not NotificationEvent.objects.filter(
        event_type='tools.job_finished').exists()
    assert UserNotification.objects.filter(user=other).count() == 0
