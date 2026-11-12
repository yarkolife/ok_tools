"""Instagram posts for rendered reels: drafts, collab partners, publishing."""

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from licenses.models import License
from licenses.models import default_category
from tools import reel_posts
from tools.models import InstagramPartner
from tools.models import ReelPost
from tools.models import ToolsConfig
from tools.services import instagram
from unittest import mock
import json
import pytest


FILENAME = '19082_Programmvorschau_Reel_261113.mp4'


@pytest.fixture
def config(tmp_path, settings):
    from media_files.models import StorageLocation

    settings.TOOLS_ENABLED = True
    settings.SITE_BASE_URL = 'https://portal.example.org'
    storage = StorageLocation.objects.create(
        name='Reel Output', storage_type='PLAYOUT', path=str(tmp_path), is_active=True)
    (tmp_path / 'reels').mkdir()
    (tmp_path / 'reels' / FILENAME).write_bytes(b'mp4')
    cfg = ToolsConfig.get_config()
    cfg.reel_studio_enabled = True
    cfg.reel_render_url = 'http://reel.example:8011'
    cfg.reel_render_api_key = 'key'
    cfg.reel_output_storage = storage
    cfg.reel_output_subdir = 'reels'
    cfg.instagram_enabled = True
    cfg.instagram_account_id = '1789'
    cfg.instagram_access_token = 'TOKEN'
    cfg.reel_reminder_time = time(9, 0)
    cfg.save()
    return cfg


@pytest.fixture
def home_license(user):
    lic = License.objects.create(
        profile=user.profile, category=default_category(), number=19082,
        title='HoMe live', subtitle='Wissen schafft Zukunft',
        description='Campus Talk', duration=timedelta(minutes=30), further_persons='',
        suggested_date=None, repetitions_allowed=True, media_authority_exchange_allowed=True,
        youth_protection_necessary=False, store_in_ok_media_library=True,
        tags=['Hochschule', 'Campus Talk'], mediathek_url='https://mediathek.example/v/1')
    return lic


def _response(status=200, payload=None):
    response = mock.Mock(status_code=status)
    response.json.return_value = payload or {}
    response.text = json.dumps(payload or {})
    return response


def test_reel_date_comes_from_the_file_name():
    assert reel_posts.reel_date_from_filename(FILENAME) == date(2026, 11, 13)
    assert reel_posts.reel_date_from_filename('19082_Reel.mp4') is None


def test_caption_drops_lines_with_only_empty_placeholders():
    text = reel_posts.render_caption(
        '{titel}\n\n▶️ Mediathek: {mediathek}\n{hashtags}',
        {'titel': 'HoMe live', 'mediathek': '', 'hashtags': '#Campus'})
    assert text == 'HoMe live\n\n#Campus'


@pytest.mark.django_db
def test_partner_keywords_match_whole_words(home_license):
    InstagramPartner.objects.create(name='HoMe', keywords='HoMe', usernames='hs_merseburg')
    InstagramPartner.objects.create(name='MDR', keywords='MDR', usernames='@mdr_sachsenanhalt')
    InstagramPartner.objects.create(name='Off', keywords='HoMe', usernames='old', is_active=False)
    assert reel_posts.collaborators_for(home_license) == ['hs_merseburg']

    home_license.title = 'Homezone'
    assert reel_posts.collaborators_for(home_license) == []


@pytest.mark.django_db
def test_rendered_reel_becomes_a_draft(config, home_license):
    InstagramPartner.objects.create(name='HoMe', keywords='HoMe', usernames='hs_merseburg')

    post = reel_posts.create_draft(FILENAME, 19082)

    assert post.status == ReelPost.STATUS_DRAFT
    assert post.license == home_license
    assert post.collaborators == 'hs_merseburg'
    # Posted in the morning of the broadcast day, with the reminder mail.
    assert timezone.localtime(post.scheduled_at) == timezone.make_aware(datetime(2026, 11, 13, 9, 0))
    assert post.caption.startswith('HoMe live\n\nCampus Talk\n\n📺 Freitag, 13.11.2026 im Offenen Kanal')
    # The Mediathek link is filled in when the post is published.
    assert '▶️ Mediathek: {mediathek}' in post.caption
    assert post.caption.endswith('#Hochschule #CampusTalk')
    # Once per file.
    assert reel_posts.create_draft(FILENAME, 19082) == post
    assert ReelPost.objects.count() == 1


@pytest.mark.django_db
def test_no_draft_while_posting_is_off(config):
    config.instagram_enabled = False
    config.save()
    assert reel_posts.create_draft(FILENAME, 19082) is None


@pytest.mark.django_db
def test_limits_are_checked():
    post = ReelPost(filename='x.mp4', caption='#a ' * 31, collaborators='a, b, c, d')
    with pytest.raises(ValidationError) as exc:
        post.full_clean()
    assert set(exc.value.message_dict) == {'caption', 'collaborators'}


@pytest.mark.django_db
def test_publish_flow(config, home_license):
    post = ReelPost.objects.create(
        filename=FILENAME, license=home_license, caption='Hallo\nMediathek: {mediathek}',
        collaborators='hs_merseburg', status=ReelPost.STATUS_APPROVED,
        scheduled_at=timezone.now() - timedelta(minutes=1))
    assert list(reel_posts.due_posts()) == [post]

    with mock.patch('tools.services.instagram.requests.post',
                    return_value=_response(payload={'id': 'C1'})) as post_call:
        claimed = reel_posts.claim(post.pk)
        assert reel_posts.start_publishing(claimed)
    sent = post_call.call_args.kwargs['data']
    assert post_call.call_args.args[0] == 'https://graph.instagram.com/v27.0/1789/media'
    assert sent['media_type'] == 'REELS'
    assert sent['video_url'].startswith('https://portal.example.org/')
    assert json.loads(sent['collaborators']) == ['hs_merseburg']
    assert sent['access_token'] == 'TOKEN'
    assert sent['caption'] == 'Hallo\nMediathek: https://mediathek.example/v/1'
    # A second claim does nothing: the post is already being published.
    assert reel_posts.claim(post.pk) is None

    claimed.refresh_from_db()
    with mock.patch('tools.services.instagram.requests.get',
                    return_value=_response(payload={'status_code': 'IN_PROGRESS'})):
        assert reel_posts.check_and_publish(claimed) == 'wait'

    with mock.patch('tools.services.instagram.requests.get', side_effect=[
            _response(payload={'status_code': 'FINISHED'}),
            _response(payload={'permalink': 'https://www.instagram.com/reel/abc/'})]), \
            mock.patch('tools.services.instagram.requests.post',
                       return_value=_response(payload={'id': 'M1'})) as publish_call:
        assert reel_posts.check_and_publish(claimed) == 'published'
    assert publish_call.call_args.kwargs['data']['creation_id'] == 'C1'
    post.refresh_from_db()
    assert (post.status, post.media_id) == (ReelPost.STATUS_PUBLISHED, 'M1')
    assert post.permalink == 'https://www.instagram.com/reel/abc/'


@pytest.mark.django_db
def test_instagram_error_marks_the_post_failed_and_notifies(config):
    post = ReelPost.objects.create(filename=FILENAME, status=ReelPost.STATUS_APPROVED,
                                   scheduled_at=timezone.now())
    error = {'error': {'message': 'Invalid parameter', 'code': 100}}
    with mock.patch('tools.services.instagram.requests.post',
                    return_value=_response(400, error)), \
            mock.patch('notifications.services.emit') as emit:
        assert not reel_posts.start_publishing(reel_posts.claim(post.pk))
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_FAILED
    assert post.error_message == 'Invalid parameter (code 100)'
    assert emit.call_args.args[0] == 'tools.instagram_post_failed'


@pytest.mark.django_db
def test_processing_too_long_fails_but_keeps_the_upload(config):
    post = ReelPost.objects.create(
        filename=FILENAME, status=ReelPost.STATUS_PUBLISHING, container_id='C1',
        container_created_at=timezone.now(), status_checks=reel_posts.STATUS_CHECK_LIMIT - 1)
    with mock.patch('tools.services.instagram.requests.get',
                    return_value=_response(payload={'status_code': 'IN_PROGRESS'})):
        assert reel_posts.check_and_publish(post) == 'failed'
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_FAILED and post.container_id == 'C1'


@pytest.mark.django_db
def test_missing_public_address_fails_clearly(config, settings):
    settings.SITE_BASE_URL = ''
    post = ReelPost.objects.create(filename=FILENAME, status=ReelPost.STATUS_APPROVED,
                                   scheduled_at=timezone.now())
    with mock.patch('notifications.services.emit'):
        assert not reel_posts.start_publishing(reel_posts.claim(post.pk))
    post.refresh_from_db()
    assert 'SITE_BASE_URL' in post.error_message


@pytest.mark.django_db
def test_token_is_renewed_once_a_week(config):
    config.instagram_token_refreshed_at = timezone.now() - timedelta(days=8)
    config.save()
    with mock.patch('tools.services.instagram.requests.get', return_value=_response(
            payload={'access_token': 'NEW', 'token_type': 'bearer', 'expires_in': 5183944})) as call:
        assert reel_posts.renew_token()
    assert call.call_args.args[0] == 'https://graph.instagram.com/refresh_access_token'
    config.refresh_from_db()
    assert config.instagram_access_token == 'NEW'
    assert not reel_posts.renew_token()


@pytest.mark.django_db
@override_settings(TOOLS_ENABLED=True)
def test_approval_needs_the_publish_permission(client, config):
    user = get_user_model().objects.create_user(email='staff@example.org', password='x', is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(
        content_type__app_label='tools', codename__in=['view_reelpost', 'change_reelpost']))
    post = ReelPost.objects.create(filename=FILENAME, scheduled_at=timezone.now() + timedelta(hours=2))
    client.force_login(user)
    url = reverse('admin:tools_reelpost_changelist')
    data = {'action': 'approve_action', '_selected_action': [post.pk]}

    client.post(url, data, secure=True)
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_DRAFT

    user.user_permissions.add(Permission.objects.get(codename='publish_reelpost'))
    user = get_user_model().objects.get(pk=user.pk)
    client.force_login(user)
    client.post(url, data, secure=True)
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_APPROVED
    assert post.approved_by == user


@pytest.mark.django_db
def test_post_waits_up_to_an_hour_for_the_mediathek_link(config, home_license):
    home_license.mediathek_url = ''
    home_license.save()
    post = ReelPost.objects.create(
        filename=FILENAME, license=home_license, caption='Hallo\nMediathek: {mediathek}',
        status=ReelPost.STATUS_APPROVED, scheduled_at=timezone.now() - timedelta(minutes=10),
        approved_at=timezone.now() - timedelta(days=1))

    with mock.patch('tools.tasks._try_refresh_mediathek_url', return_value=''), \
            mock.patch('tools.services.instagram.requests.post') as post_call:
        assert not reel_posts.start_publishing(reel_posts.claim(post.pk))
    post_call.assert_not_called()
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_APPROVED  # tried again on the next run

    # After an hour it is published without the line.
    ReelPost.objects.filter(pk=post.pk).update(scheduled_at=timezone.now() - timedelta(minutes=61))
    with mock.patch('tools.tasks._try_refresh_mediathek_url', return_value=''), \
            mock.patch('tools.services.instagram.requests.post',
                       return_value=_response(payload={'id': 'C1'})) as post_call:
        assert reel_posts.start_publishing(reel_posts.claim(post.pk))
    assert post_call.call_args.kwargs['data']['caption'] == 'Hallo'


@pytest.mark.django_db
def test_publish_now_does_not_wait_for_the_link(config, home_license, user):
    home_license.mediathek_url = ''
    home_license.save()
    post = ReelPost.objects.create(filename=FILENAME, license=home_license,
                                   caption='Hallo\nMediathek: {mediathek}')
    reel_posts.approve(post, user, now=True)
    with mock.patch('tools.tasks._try_refresh_mediathek_url', return_value=''), \
            mock.patch('tools.services.instagram.requests.post',
                       return_value=_response(payload={'id': 'C1'})):
        assert reel_posts.start_publishing(reel_posts.claim(post.pk))
