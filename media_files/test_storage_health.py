"""Health check of storage locations that hold no known video."""

from media_files.models import StorageLocation
from media_files.storage_health import EMPTY
from media_files.storage_health import measure_storage_health
from media_files.storage_health import probe_directory
from media_files.storage_health import record_read_speed
import os
import pytest
import tempfile


def _location(path):
    return StorageLocation.objects.create(
        name='Fotos', storage_type='ARCHIVE', path=path, is_active=True)


@pytest.mark.django_db
def test_location_with_photos_only_gets_a_speed():
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, 'sub'))
        with open(os.path.join(root, 'sub', 'OK-000001.jpg'), 'wb') as handle:
            handle.write(os.urandom(64 * 1024))
        location = _location(root)
        record_read_speed(location, None)   # the old false alarm

        speed = measure_storage_health(location, timeout=10)

        location.refresh_from_db()
        assert speed and speed > 0
        assert location.last_read_mbps == speed
        assert location.last_health_check is not None


@pytest.mark.django_db
def test_empty_reachable_location_is_unknown_not_silent():
    with tempfile.TemporaryDirectory() as root:
        location = _location(root)
        record_read_speed(location, None)

        assert measure_storage_health(location, timeout=10) is None

        location.refresh_from_db()
        assert location.last_read_mbps is None
        assert location.last_health_check is None


@pytest.mark.django_db
def test_missing_location_did_not_answer():
    location = _location('/nonexistent/oktools-share')

    assert measure_storage_health(location, timeout=10) is None

    location.refresh_from_db()
    assert location.last_read_mbps is None
    assert location.last_health_check is not None


def test_probe_directory_states():
    with tempfile.TemporaryDirectory() as root:
        assert probe_directory(root, timeout=10) == EMPTY
        with open(os.path.join(root, 'a.jpg'), 'wb') as handle:
            handle.write(b'x' * 1024)
        assert probe_directory(root, timeout=10) > 0
    assert probe_directory('/nonexistent/oktools-share', timeout=10) is None


@pytest.fixture
def daemonic_process():
    """Run the test as if inside a Celery prefork worker (daemonic process)."""
    import multiprocessing
    config = multiprocessing.current_process()._config
    before = config.get('daemon')
    config['daemon'] = True
    yield
    if before is None:
        config.pop('daemon', None)
    else:
        config['daemon'] = before


def test_probes_work_inside_a_daemonic_worker(daemonic_process):
    """Celery pool workers are daemonic; the probe must still start its child.

    Without that the folder probe reported "did not answer" for every share
    without known videos (case 11.11.2026, Fotos Inventar).
    """
    from media_files.storage_health import probe_read_speed
    with tempfile.TemporaryDirectory() as root:
        path = os.path.join(root, 'a.jpg')
        with open(path, 'wb') as handle:
            handle.write(b'x' * 1024)
        assert probe_directory(root, timeout=10) > 0
        assert probe_read_speed(path, timeout=10) > 0


def test_probe_directory_skips_hidden_and_cache_files():
    with tempfile.TemporaryDirectory() as root:
        for name in ('.DS_Store', 'Thumbs.db', 'desktop.ini'):
            with open(os.path.join(root, name), 'wb') as handle:
                handle.write(b'x' * 1024)
        assert probe_directory(root, timeout=10) == EMPTY


def test_sample_is_the_largest_file():
    """A tiny file measures latency, not speed (Thumbs.db case, 11.11.2026)."""
    from media_files.storage_health import _find_sample_in_dir
    with tempfile.TemporaryDirectory() as root:
        os.mkdir(os.path.join(root, '483'))
        for rel, size in (('small.jpg', 10), ('483/big.jpg', 5000), ('mid.jpg', 100)):
            with open(os.path.join(root, rel), 'wb') as handle:
                handle.write(b'x' * size)
        assert _find_sample_in_dir(root).endswith('big.jpg')


def _video(location, name, scanned):
    from media_files.models import VideoFile
    return VideoFile.objects.create(
        number=int(name.split('_')[0]), filename=name, storage_location=location,
        file_path=name, is_available=True, last_scanned=scanned)


@pytest.mark.django_db
def test_one_unopenable_file_does_not_make_the_storage_silent():
    """Case 24.11.2026: the newest record named a file that would not open."""
    from django.utils import timezone
    import datetime
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, '100_good.mp4'), 'wb') as handle:
            handle.write(os.urandom(256 * 1024))
        location = _location(root)
        now = timezone.now()
        _video(location, '100_good.mp4', now - datetime.timedelta(hours=1))
        _video(location, '101_gone.mp4', now)

        speed = measure_storage_health(location, timeout=10)

        location.refresh_from_db()
        assert speed and speed > 0
        assert location.last_read_mbps == speed


@pytest.mark.django_db
def test_never_scanned_records_are_sampled_last():
    from django.utils import timezone
    from media_files.storage_health import _sample_files
    location = _location('/srv/share')
    _video(location, '200_unscanned.mp4', None)
    _video(location, '201_scanned.mp4', timezone.now())

    assert [os.path.basename(p) for p in _sample_files(location)] == [
        '201_scanned.mp4', '200_unscanned.mp4']


def test_probe_file_tells_a_bad_file_from_a_silent_storage():
    from media_files.storage_health import UNREADABLE
    from media_files.storage_health import probe_file
    assert probe_file('/nonexistent/file.mp4', timeout=10) == UNREADABLE
    with tempfile.TemporaryDirectory() as root:
        path = os.path.join(root, 'empty.mp4')
        open(path, 'wb').close()
        assert probe_file(path, timeout=10) == UNREADABLE


def test_probe_directory_skips_a_file_that_does_not_open(monkeypatch):
    from media_files import storage_health
    real_read = storage_health._read_sample

    def read(path, sample_bytes):
        if path.endswith('big.mp4'):
            raise FileNotFoundError(path)
        return real_read(path, sample_bytes)

    monkeypatch.setattr(storage_health, '_read_sample', read)
    with tempfile.TemporaryDirectory() as root:
        for name, size in (('big.mp4', 8000), ('small.mp4', 1000)):
            with open(os.path.join(root, name), 'wb') as handle:
                handle.write(b'x' * size)
        assert probe_directory(root, timeout=10) > 0


@pytest.mark.django_db
def test_scan_gives_no_available_record_to_a_file_that_does_not_open(monkeypatch):
    from django.core.management import call_command
    from media_files.management.commands import scan_video_storage
    from media_files.models import VideoFile
    import io

    monkeypatch.setattr(
        scan_video_storage, 'unreadable_reason',
        lambda path: 'No such file or directory' if '301_' in str(path) else '')
    with tempfile.TemporaryDirectory() as root:
        for name in ('300_ok.mp4', '301_stuck.mp4'):
            with open(os.path.join(root, name), 'wb') as handle:
                handle.write(b'x' * 1024)
        location = _location(root)
        _video(location, '301_stuck.mp4', None)

        out = io.StringIO()
        call_command('scan_video_storage', storage_id=location.pk,
                     skip_metadata=True, stdout=out)

        assert VideoFile.objects.get(file_path='300_ok.mp4').is_available
        assert not VideoFile.objects.get(file_path='301_stuck.mp4').is_available
        assert 'Cannot open, skipped: 301_stuck.mp4' in out.getvalue()
