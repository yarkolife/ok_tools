"""Tests for automatic Nextcloud downloads and screen board photo uploads."""

from licenses.media_types import allowed_extensions
from licenses.media_types import is_allowed_filename
from licenses.media_types import is_image_filename
from licenses.models import LicensesConfig
from licenses.models import NextcloudVideoFile
from unittest import mock
import pytest


def test_screen_board_accepts_photos_and_videos():
    """A screen board takes photos, everything else stays video only."""
    assert 'jpg' in allowed_extensions(True)
    assert 'mp4' in allowed_extensions(True)
    assert 'jpg' not in allowed_extensions(False)

    assert is_allowed_filename('board.PNG', True)
    assert not is_allowed_filename('board.png', False)
    assert is_allowed_filename('film.mp4', False)
    assert not is_allowed_filename('notes.txt', True)

    assert is_image_filename('board.jpeg')
    assert not is_image_filename('film.mkv')


@pytest.fixture()
def nextcloud_config(db):
    """Return the licenses config with a usable download path."""
    config = LicensesConfig.get_config()
    config.download_storage_path = '/tmp/nextcloud-downloads/'
    config.auto_download_to_storage = True
    config.save()
    return config


def _create_file(license, **kwargs):
    return NextcloudVideoFile.objects.create(
        license=license,
        nextcloud_file_id='Videos/1_video.mp4',
        filename='1_video.mp4',
        **kwargs,
    )


@pytest.mark.django_db
def test_upload_queues_download_automatically(
        license, nextcloud_config, settings, django_capture_on_commit_callbacks):
    """A new Nextcloud file is fetched to local storage without manual action."""
    settings.NEXTCLOUD_ENABLED = True

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        with django_capture_on_commit_callbacks(execute=True):
            video = _create_file(license)

    delay.assert_called_once_with(video.pk)


@pytest.mark.django_db
def test_no_automatic_download_when_switched_off(
        license, nextcloud_config, settings, django_capture_on_commit_callbacks):
    """Nothing is queued while the config switch is off."""
    settings.NEXTCLOUD_ENABLED = True
    nextcloud_config.auto_download_to_storage = False
    nextcloud_config.save()

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        with django_capture_on_commit_callbacks(execute=True):
            _create_file(license)

    delay.assert_not_called()


@pytest.mark.django_db
def test_no_automatic_download_without_storage_path(
        license, nextcloud_config, settings, django_capture_on_commit_callbacks):
    """Without a download path there is nowhere to put the file."""
    settings.NEXTCLOUD_ENABLED = True
    nextcloud_config.download_storage_path = ''
    nextcloud_config.save()

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        with django_capture_on_commit_callbacks(execute=True):
            _create_file(license)

    delay.assert_not_called()


@pytest.mark.django_db
def test_pending_sweep_queues_only_missing_files(
        license, nextcloud_config, settings, django_capture_on_commit_callbacks):
    """The catch-up sweep skips deleted and already downloaded files."""
    from django.utils import timezone
    from licenses.tasks import download_pending_nextcloud_videos

    settings.NEXTCLOUD_ENABLED = True

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ):
        with django_capture_on_commit_callbacks(execute=True):
            pending = _create_file(license)
            _create_file(license, downloaded_at=timezone.now())
            _create_file(license, is_deleted=True)

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        queued = download_pending_nextcloud_videos()

    assert queued == 1
    delay.assert_called_once_with(pending.pk)


@pytest.mark.django_db
def test_confirm_upload_rejects_unsupported_format(license, client, settings):
    """A file that is neither video nor photo is refused before Nextcloud."""
    settings.NEXTCLOUD_ENABLED = True
    client.force_login(license.profile.okuser)

    response = client.post(
        f'/licenses/{license.pk}/confirm-upload/',
        data='{"filename": "notes.txt"}',
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'Supported formats' in response.json()['error']
    assert not NextcloudVideoFile.objects.filter(license=license).exists()


@pytest.mark.django_db
def test_confirm_upload_accepts_photo_for_screen_board(
        license, client, settings, django_capture_on_commit_callbacks):
    """A screen board may be documented with a photo instead of a video."""
    settings.NEXTCLOUD_ENABLED = True
    license.is_screen_board = True
    license.save()
    client.force_login(license.profile.okuser)

    service = mock.MagicMock()
    service.verify_uploaded_file.return_value = {
        'file_path': 'Videos/board.jpg',
        'file_url': 'https://cloud.example.com/Videos/board.jpg',
        'size': 1234,
    }

    with mock.patch(
        'licenses.services.nextcloud_service.NextcloudService',
        return_value=service,
    ), mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                f'/licenses/{license.pk}/confirm-upload/',
                data='{"filename": "board.jpg"}',
                content_type='application/json',
            )

    assert response.status_code == 200, response.content
    assert response.json()['success'] is True
    uploaded = NextcloudVideoFile.objects.get(license=license)
    assert uploaded.filename == 'board.jpg'
    assert uploaded.is_image


@pytest.mark.django_db
def test_license_list_offers_photo_upload_for_screen_board(license, client, settings):
    """The overview opens the upload dialog in photo mode for screen boards."""
    settings.NEXTCLOUD_ENABLED = True
    license.is_screen_board = True
    license.save()
    client.force_login(license.profile.okuser)

    content = client.get('/licenses/').content.decode()

    assert f"openVideoUploadModal('{license.pk}'" in content
    assert ', true)' in content


@pytest.mark.django_db
def test_update_page_accepts_images_for_screen_board(license, client, settings):
    """The upload card of a screen board accepts image files."""
    settings.NEXTCLOUD_ENABLED = True
    license.is_screen_board = True
    license.save()
    client.force_login(license.profile.okuser)

    content = client.get(f'/licenses/{license.pk}/update/').content.decode()

    assert 'accept="image/*,video/*"' in content


@pytest.mark.django_db
def test_no_download_when_file_is_already_in_storage(
        license, nextcloud_config, settings, tmp_path,
        django_capture_on_commit_callbacks):
    """A copy known to media_files is not fetched from Nextcloud again."""
    from media_files.models import StorageLocation
    from media_files.models import VideoFile

    settings.NEXTCLOUD_ENABLED = True
    settings.MEDIA_FILES_ENABLED = True

    storage = StorageLocation.objects.create(
        name='Test storage',
        path=str(tmp_path),
        is_active=True,
    )
    local_file = tmp_path / '1_video.mp4'
    local_file.write_bytes(b'data')
    VideoFile.objects.create(
        number=license.number,
        storage_location=storage,
        file_path='1_video.mp4',
        filename='1_video.mp4',
        is_available=True,
    )

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        with django_capture_on_commit_callbacks(execute=True):
            video = _create_file(license)

    delay.assert_not_called()
    video.refresh_from_db()
    assert video.downloaded_at is not None
    assert video.local_path == str(local_file)


@pytest.mark.django_db
def test_download_still_runs_for_a_different_file(
        license, nextcloud_config, settings, tmp_path,
        django_capture_on_commit_callbacks):
    """Another file of the same license does not block a new download."""
    from media_files.models import StorageLocation
    from media_files.models import VideoFile

    settings.NEXTCLOUD_ENABLED = True
    settings.MEDIA_FILES_ENABLED = True

    storage = StorageLocation.objects.create(
        name='Test storage 2',
        path=str(tmp_path),
        is_active=True,
    )
    (tmp_path / 'old_version.mp4').write_bytes(b'data')
    VideoFile.objects.create(
        number=license.number,
        storage_location=storage,
        file_path='old_version.mp4',
        filename='old_version.mp4',
        is_available=True,
    )

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        with django_capture_on_commit_callbacks(execute=True):
            video = _create_file(license)

    delay.assert_called_once_with(video.pk)


@pytest.mark.django_db
def test_downloaded_file_is_never_fetched_again(
        license, nextcloud_config, settings, django_capture_on_commit_callbacks):
    """A moved or deleted local copy does not trigger a second download."""
    from django.utils import timezone
    from licenses.tasks import download_nextcloud_video_file_to_storage
    from licenses.tasks import download_pending_nextcloud_videos

    settings.NEXTCLOUD_ENABLED = True

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ):
        with django_capture_on_commit_callbacks(execute=True):
            video = _create_file(license)

    # First download succeeded, the copy was removed from storage afterwards.
    NextcloudVideoFile.objects.filter(pk=video.pk).update(
        downloaded_at=timezone.now(),
        local_path='/tmp/nextcloud-downloads/1_video.mp4',
    )

    with mock.patch('licenses.tasks.NextcloudService') as service:
        result = download_nextcloud_video_file_to_storage(video.pk)

    service.assert_not_called()
    assert result == '/tmp/nextcloud-downloads/1_video.mp4'

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ) as delay:
        assert download_pending_nextcloud_videos() == 0
    delay.assert_not_called()


@pytest.mark.django_db
def test_admin_download_button_forces_a_new_download(
        license, nextcloud_config, settings, tmp_path,
        django_capture_on_commit_callbacks):
    """The manual Download button fetches the file again on purpose."""
    from django.utils import timezone
    from licenses.tasks import download_nextcloud_video_file_to_storage

    settings.NEXTCLOUD_ENABLED = True
    nextcloud_config.download_storage_path = str(tmp_path)
    nextcloud_config.save()

    with mock.patch(
        'licenses.tasks.download_nextcloud_video_file_to_storage.delay'
    ):
        with django_capture_on_commit_callbacks(execute=True):
            video = _create_file(license)
    NextcloudVideoFile.objects.filter(pk=video.pk).update(downloaded_at=timezone.now())

    service = mock.MagicMock()
    service._sanitize_filename.return_value = 'video.mp4'
    service.download_file.return_value = True

    with mock.patch('licenses.tasks.NextcloudService', return_value=service):
        result = download_nextcloud_video_file_to_storage(video.pk, force=True)

    service.download_file.assert_called_once()
    assert result == str(tmp_path / f'{license.number}_video.mp4')
