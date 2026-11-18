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
    # Without a hook its line is left out; broadcast day and Mediathek link
    # are filled in when the post is published.
    assert post.caption.startswith('HoMe live\n\nCampus Talk\n\n📺 {sendetermin} im Offenen Kanal')
    assert '▶️ Mediathek: {mediathek}' in post.caption
    assert post.caption.endswith('#Hochschule #CampusTalk')
    # Once per file.
    assert reel_posts.create_draft(FILENAME, 19082) == post
    assert ReelPost.objects.count() == 1


@pytest.mark.django_db
def test_caption_starts_with_the_hook_and_has_the_fixed_hashtags(config, home_license):
    config.instagram_fixed_hashtags = '#OffenerKanal, hochschule #Merseburg'
    config.save()

    post = reel_posts.create_draft(
        FILENAME, 19082, hook={'zeile1': 'Hast du ihn verpasst?', 'zeile2': 'Der Campus Talk'})

    assert post.caption.startswith('Hast du ihn verpasst? Der Campus Talk\n\nHoMe live\n\n')
    # Fixed hashtags after the license tags, "hochschule" only once.
    assert post.caption.endswith('#CampusTalk #OffenerKanal #hochschule #Merseburg')


def test_at_most_five_hashtags_and_the_fixed_ones_always_fit():
    tags = ['Kultur', 'Musik', 'Sport', 'Politik']
    assert reel_posts.hashtags_for(tags, '#OKMQ #Merseburg #Saalekreis') == (
        '#Kultur #Musik #OKMQ #Merseburg #Saalekreis')
    assert reel_posts.hashtags_for(tags) == '#Kultur #Musik #Sport #Politik'
    assert reel_posts.hashtags_for(tags, '#a #b #c #d #e #f') == '#a #b #c #d #e'


@pytest.mark.django_db
def test_author_with_an_instagram_account_is_invited_first(config, home_license):
    home_license.profile.instagram = 'max.muster'
    home_license.profile.save()
    InstagramPartner.objects.create(name='HoMe', keywords='HoMe', usernames='hs_merseburg, Max.Muster')

    assert reel_posts.collaborators_for(home_license) == ['max.muster', 'hs_merseburg']


@pytest.mark.parametrize('text, limit, expected', [
    ('Kurz.', 50, 'Kurz.'),
    ('Erster Satz. Zweiter Satz! Dritter Satz?', 30, 'Erster Satz. Zweiter Satz!'),
    ('Version 2.0 kommt. Ende', 15, 'Version 2.0…'),
    ('Ein langer Satz ohne Ende', 15, 'Ein langer…'),
])
def test_shorten_cuts_at_a_sentence_end(text, limit, expected):
    assert reel_posts.shorten(text, limit) == expected
    assert len(reel_posts.shorten(text, limit)) <= limit


@pytest.mark.django_db
def test_long_description_is_cut_at_a_sentence_end(config, home_license):
    home_license.description = 'Ein ganzer Satz über den Campus. ' * 100
    home_license.save()

    post = reel_posts.create_draft(FILENAME, 19082)

    # Room is kept for the link and the broadcast day filled in later.
    assert len(post.caption) <= ReelPost.CAPTION_MAX_LENGTH - reel_posts.LATE_RESERVE
    assert 'den Campus.\n\n📺 {sendetermin}' in post.caption
    assert post.caption.endswith('#Hochschule #CampusTalk')


@pytest.mark.django_db
def test_broadcast_time_is_taken_from_the_plan_when_publishing(config, home_license):
    post = ReelPost.objects.create(
        filename=FILENAME, license=home_license,
        caption='Hallo\n📺 {sendetermin} im Offenen Kanal\num {uhrzeit}',
        status=ReelPost.STATUS_APPROVED, scheduled_at=timezone.now() - timedelta(minutes=1))

    with mock.patch('tools.reel_posts._plan_entry', return_value={'start': '18:30:00'}), \
            mock.patch('tools.services.instagram.requests.post',
                       return_value=_response(payload={'id': 'C1'})) as post_call:
        assert reel_posts.start_publishing(reel_posts.claim(post.pk))

    assert post_call.call_args.kwargs['data']['caption'] == (
        'Hallo\n📺 Freitag, 13.11.2026, 18:30 Uhr im Offenen Kanal\num 18:30')


@pytest.mark.django_db
def test_render_task_passes_the_hook_to_the_draft(config, home_license):
    from tools.tasks import _create_reel_post_draft

    _create_reel_post_draft({'file': f'/out/{FILENAME}', 'cover_ms': 1220},
                            {'zeile1': 'Wer?', 'zeile2': ''})

    post = ReelPost.objects.get(filename=FILENAME)
    assert post.caption.startswith('Wer?\n\nHoMe live')
    assert post.thumb_offset_ms == 1220


@pytest.mark.django_db
def test_draft_takes_the_cover_frame_from_the_renderer(config, home_license):
    post = reel_posts.create_draft(FILENAME, 19082, cover_ms='1220')
    assert post.thumb_offset_ms == 1220


@pytest.mark.django_db
def test_draft_from_the_folder_scan_gets_the_cover_later(config, home_license):
    post = reel_posts.create_draft(FILENAME, 19082)
    assert post.thumb_offset_ms == 0

    from tools.tasks import _create_reel_post_draft
    _create_reel_post_draft({'status': 'done', 'file': FILENAME, 'cover_ms': 1220})
    post.refresh_from_db()
    assert post.thumb_offset_ms == 1220

    # A cover chosen by hand stays.
    post.thumb_offset_ms = 3000
    post.save()
    reel_posts.create_draft(FILENAME, 19082, cover_ms=1220)
    post.refresh_from_db()
    assert post.thumb_offset_ms == 3000


@pytest.mark.django_db
def test_no_draft_while_posting_is_off(config):
    config.instagram_enabled = False
    config.save()
    assert reel_posts.create_draft(FILENAME, 19082) is None


@pytest.mark.django_db
def test_limits_are_checked():
    post = ReelPost(filename='x.mp4', caption='#a ' * 6, collaborators='a, b, c, d')
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


@pytest.mark.django_db
def test_morning_mail_shows_the_post_and_an_approval_link(config, home_license):
    post = ReelPost.objects.create(filename=FILENAME, license=home_license, caption='Hallo')
    info = reel_posts.reminder_info(FILENAME, 19082)
    assert info['status'] == ReelPost.STATUS_DRAFT
    assert info['approve_url'].startswith('https://portal.example.org/tools/reel-posts/freigeben/')

    post.status = ReelPost.STATUS_PUBLISHED
    post.permalink = 'https://www.instagram.com/reel/abc/'
    post.save()
    info = reel_posts.reminder_info(FILENAME, 19082)
    assert (info['approve_url'], info['permalink']) == ('', 'https://www.instagram.com/reel/abc/')


@pytest.mark.django_db
def test_morning_mail_creates_missing_drafts(config, home_license):
    assert reel_posts.reminder_info(FILENAME, 19082)['status'] == ReelPost.STATUS_DRAFT
    assert ReelPost.objects.filter(filename=FILENAME).exists()


@pytest.mark.django_db
def test_finished_reels_get_drafts_from_their_broadcast_day_on(config, home_license, tmp_path):
    folder = tmp_path / 'reels'
    (folder / '19082_Programmvorschau_Reel_261112.mp4').write_bytes(b'mp4')  # broadcast over
    (folder / '19082_Programmvorschau_Reel_261120.mp4').write_bytes(b'mp4')
    (folder / '19082_Reel_ohne_Datum.mp4').write_bytes(b'mp4')
    (folder / 'notes_261120.txt').write_text('x')
    (folder / '19100_Programmvorschau_261119.mp4').write_bytes(b'mp4')  # full preview, no reel
    ReelPost.objects.create(filename='19082_Programmvorschau_Reel_261120.mp4')

    created = reel_posts.drafts_for_existing_reels(today=date(2026, 11, 13))

    # FILENAME is broadcast on the 13th; the one on the 20th already has a post.
    assert [p.filename for p in created] == [FILENAME]
    assert created[0].license == home_license
    assert created[0].caption.startswith('HoMe live')
    assert ReelPost.objects.count() == 2
    assert reel_posts.drafts_for_existing_reels(today=date(2026, 11, 13)) == []


@pytest.mark.django_db
def test_no_drafts_for_existing_reels_while_posting_is_off(config):
    config.instagram_enabled = False
    config.save()
    assert reel_posts.drafts_for_existing_reels(today=date(2026, 11, 13)) == []


@pytest.mark.django_db
@override_settings(TOOLS_ENABLED=True)
def test_drafts_button_creates_drafts_on_post_only(client, config, home_license):
    admin_user = get_user_model().objects.create_superuser(email='boss@example.org', password='x')
    client.force_login(admin_user)
    url = reverse('admin:tools_reelpost_create_drafts')

    with mock.patch.object(reel_posts.timezone, 'localdate', return_value=date(2026, 11, 13)):
        assert client.get(url, secure=True).status_code == 405
        assert not ReelPost.objects.exists()
        response = client.post(url, secure=True)

    assert response.status_code == 302
    assert ReelPost.objects.filter(filename=FILENAME).exists()
    changelist = client.get(reverse('admin:tools_reelpost_changelist'), secure=True).content.decode()
    assert url in changelist
    # Inside the object-tools list in both admin modes, so it gets the button style.
    tools = changelist[changelist.index('<ul class="object-tools">'):]
    assert tools.index(url) < tools.index('</ul>')


@pytest.mark.django_db
def test_mail_link_shows_the_post_and_publishes_only_on_the_button(client, config, home_license):
    post = ReelPost.objects.create(filename=FILENAME, license=home_license, caption='Hallo Welt')
    url = reverse('tools:reel_post_approve', args=[reel_posts.approval_token(post)])

    page = client.get(url, secure=True)
    assert page.status_code == 200
    assert 'Hallo Welt' in page.content.decode()
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_DRAFT  # opening the link changes nothing

    with mock.patch('tools.tasks.publish_due_reel_posts.delay') as publish:
        client.post(url, secure=True)
    post.refresh_from_db()
    assert post.status == ReelPost.STATUS_APPROVED
    assert post.approved_by is None
    publish.assert_called_once()

    # A second click does nothing.
    assert 'Hallo Welt' not in client.post(url, secure=True).content.decode()


@pytest.mark.django_db
def test_mail_link_with_a_wrong_token_is_refused(client, config):
    response = client.get(reverse('tools:reel_post_approve', args=['nonsense']), secure=True)
    assert response.status_code == 400


@pytest.mark.django_db
def test_story_reminder_half_an_hour_after_publishing(config, home_license, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    from django.core import mail
    config.reel_reminder_recipient_email = 'social@example.org'
    config.save()
    post = ReelPost.objects.create(
        filename=FILENAME, license=home_license, status=ReelPost.STATUS_PUBLISHING,
        container_id='C1', container_created_at=timezone.now())

    from tools.tasks import check_reel_post
    with mock.patch('tools.services.instagram.requests.get', side_effect=[
            _response(payload={'status_code': 'FINISHED'}),
            _response(payload={'permalink': 'https://www.instagram.com/reel/abc/'})]), \
            mock.patch('tools.services.instagram.requests.post',
                       return_value=_response(payload={'id': 'M1'})), \
            mock.patch('tools.tasks.send_reel_story_reminder.apply_async') as later:
        check_reel_post(post.pk)
    assert later.call_args.kwargs == {'args': [post.pk], 'countdown': 30 * 60}

    from tools.tasks import send_reel_story_reminder
    with mock.patch('notifications.services.emit') as emit:
        send_reel_story_reminder(post.pk)
    assert emit.call_args.args[0] == 'tools.instagram_story_reminder'
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['social@example.org']
    assert 'https://mediathek.example/v/1' in mail.outbox[0].body
    assert 'https://www.instagram.com/reel/abc/' in mail.outbox[0].body


@pytest.mark.parametrize('ig, expected, absent', [
    ({'status': 'draft', 'approve_url': 'https://x/approve'},
     ['Approve and publish now: https://x/approve'], ['Reel download']),
    ({'status': 'published', 'permalink': 'https://www.instagram.com/reel/abc/'},
     ['Instagram: published - https://www.instagram.com/reel/abc/'], ['Approve']),
    (None, ['Reel download: https://x/file.mp4'], ['Instagram']),
])
def test_morning_mail_text(ig, expected, absent):
    from django.template.loader import render_to_string
    from django.utils import translation

    reel = {'number': 19082, 'title': 'HoMe live', 'instagram': ig,
            'download_url': '' if ig else 'https://x/file.mp4',
            'mediathek_url': 'https://mediathek.example/v/1'}
    with translation.override('en'):
        text = render_to_string('email/daily_reel_reminder_body.txt',
                                {'date': date(2026, 11, 13), 'reels': [reel]})
    for part in expected:
        assert part in text
    for part in absent:
        assert part not in text
    assert 'Mediathek: https://mediathek.example/v/1' in text


@pytest.mark.django_db
def test_without_reel_studio_nothing_of_it_exists(client, config, admin_user):
    from notifications import config as notification_config

    config.reel_studio_enabled = False
    config.save()
    client.force_login(admin_user)

    assert not config.is_instagram_configured()
    assert reel_posts.create_draft(FILENAME, 19082) is None
    assert client.get(reverse('admin:tools_reelpost_changelist'), secure=True).status_code == 403
    assert client.get(reverse('admin:tools_instagrampartner_changelist'), secure=True).status_code == 403
    page = client.get(reverse('admin:tools_toolsconfig_change', args=[config.pk]), secure=True)
    assert 'id_instagram_enabled' not in page.content.decode()
    for code in ('media_files.missing_reel', 'media_files.reel_post_today',
                 'tools.instagram_post_failed', 'tools.instagram_story_reminder'):
        assert not notification_config.is_enabled(code), code

    config.reel_studio_enabled = True
    config.save()
    assert client.get(reverse('admin:tools_reelpost_changelist'), secure=True).status_code == 200
    assert notification_config.is_enabled('media_files.missing_reel')
    assert notification_config.is_enabled('tools.instagram_story_reminder')


@pytest.mark.django_db
def test_instagram_off_hides_posts_but_keeps_reel_features(client, config, admin_user):
    from notifications import config as notification_config

    config.instagram_enabled = False
    config.save()
    client.force_login(admin_user)
    assert client.get(reverse('admin:tools_reelpost_changelist'), secure=True).status_code == 403
    page = client.get(reverse('admin:tools_toolsconfig_change', args=[config.pk]), secure=True)
    assert 'id_instagram_enabled' in page.content.decode()  # the switch stays reachable
    assert notification_config.is_enabled('media_files.missing_reel')
    assert not notification_config.is_enabled('tools.instagram_story_reminder')
