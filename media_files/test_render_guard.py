"""A second click on a render action must not encode the same video twice."""

from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from media_files.admin import render_running
from media_files.models import FileOperation
from media_files.models import StorageLocation
from media_files.models import VideoFile
from types import SimpleNamespace
from unittest import mock
import pytest


@pytest.fixture
def source(db, tmp_path):
    storage = StorageLocation.objects.create(
        name='Planung', storage_type='PLAYOUT', path=str(tmp_path), is_active=True)
    (tmp_path / '19125_WIgeFA.mov').write_bytes(b'mov')
    return VideoFile.objects.create(
        number=19125, filename='19125_WIgeFA.mov', file_path='19125_WIgeFA.mov',
        storage_location=storage, is_available=True)


def _operation(source, **details):
    return FileOperation.objects.create(
        video_file=source, operation_type='RENDER', status='IN_PROGRESS',
        source_location=source.storage_location, destination_location=source.storage_location,
        details={'source_video_id': source.id, **details})


def test_render_running_matches_source_and_kind(source):
    operation = _operation(source, plain_encode=True)
    assert render_running(source, plain_encode=True)
    assert not render_running(source, preview=True)

    operation.status = 'SUCCESS'
    operation.save()
    assert not render_running(source, plain_encode=True)


def test_operation_left_behind_by_a_dead_worker_does_not_block(source):
    operation = _operation(source, plain_encode=True)
    FileOperation.objects.filter(pk=operation.pk).update(
        performed_at=timezone.now() - timedelta(hours=13))
    assert not render_running(source, plain_encode=True)


def test_second_click_on_plain_encoding_queues_nothing(client, admin_user, source, settings):
    settings.TOOLS_ENABLED = True
    client.force_login(admin_user)
    url = reverse('admin:media_files_videofile_changelist')
    data = {'action': 'render_default_preset_action', '_selected_action': [source.pk]}
    with mock.patch('media_files.config.get_video_overlay_rendering_enabled', return_value=True), \
            mock.patch('media_files.admin.load_encode_preset',
                    return_value=SimpleNamespace(name='1080p25_12000k')), \
            mock.patch('media_files.tasks.render_video_task.delay') as queued:
        client.post(url, data)
        second = client.post(url, data, follow=True)

    assert queued.call_count == 1
    assert VideoFile.objects.filter(number=19125).count() == 2
    assert 'already being rendered' in second.content.decode()
