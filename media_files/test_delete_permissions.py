"""Staff without the right to delete videos cannot delete them by other ways."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from unittest.mock import patch
import pytest


DELETING_ACTIONS = {
    'delete_records_without_video_action',
    'delete_duplicates_action',
    'delete_archive_duplicates_action',
    'delete_archive_duplicates_keep_newest_action',
    'delete_archive_duplicates_keep_largest_action',
    'force_delete_archive_duplicates_keep_best_action',
    'force_delete_archive_duplicates_keep_newest_action',
    'force_delete_archive_duplicates_keep_largest_action',
    'cleanup_missing_files_action',
}


def _staff(*codenames):
    user = get_user_model().objects.create_user(
        email=f'staff{len(codenames)}@example.org', password='x', is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(
        content_type__app_label='media_files', codename__in=codenames))
    return user


def _actions(user):
    from django.contrib import admin
    from django.test import RequestFactory
    from media_files.models import VideoFile

    request = RequestFactory().get('/')
    request.user = user
    return set(admin.site._registry[VideoFile].get_actions(request))


@pytest.mark.django_db
def test_deleting_actions_need_the_delete_right():
    without = _actions(_staff('view_videofile', 'change_videofile'))
    assert not (without & DELETING_ACTIONS)

    with_right = _actions(_staff('view_videofile', 'change_videofile', 'delete_videofile'))
    assert DELETING_ACTIONS <= with_right


@pytest.mark.django_db
@pytest.mark.parametrize('post, allowed', [
    ({'command': 'cleanup_duplicates'}, False),
    ({'command': 'cleanup_playout'}, False),
    ({'command': 'scan_video_storage', 'delete_missing': '1'}, False),
    ({'command': 'cleanup_duplicates', 'dry_run': '1'}, True),
    ({'command': 'scan_video_storage'}, True),
])
def test_system_management_refuses_deleting_commands(client, post, allowed):
    client.force_login(_staff('view_videofile', 'change_videofile'))
    with patch('media_files.admin_commands.run_cleanup_duplicates_task') as dup, \
            patch('media_files.admin_commands.run_cleanup_playout_task') as playout, \
            patch('media_files.admin_commands.run_scan_video_storage_task') as scan:
        client.post(reverse('admin:media_files_system_management'), post, secure=True)
    queued = dup.delay.called or playout.delay.called or scan.delay.called
    assert queued is allowed
