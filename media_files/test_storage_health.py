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


def test_probe_directory_skips_hidden_files():
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, '.DS_Store'), 'wb') as handle:
            handle.write(b'x' * 1024)
        assert probe_directory(root, timeout=10) == EMPTY
