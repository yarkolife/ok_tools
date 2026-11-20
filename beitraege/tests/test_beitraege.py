"""Posts: texts per platform, approval by link, publishing on three platforms."""

from PIL import Image
from beitraege import workflow
from beitraege.models import PLATFORM_FACEBOOK
from beitraege.models import PLATFORM_INSTAGRAM
from beitraege.models import PLATFORM_WEBSITE
from beitraege.models import Beitrag
from beitraege.models import BeitragFoto
from beitraege.models import BeitragZiel
from beitraege.models import BeitragsConfig
from beitraege.models import Thema
from beitraege.services import images
from datetime import timedelta
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from io import BytesIO
from registration.models import OKUser
from unittest import mock
import json
import pytest


def _jpeg(size=(1200, 1600), colour='red', exif_gps=False) -> bytes:
    image = Image.new('RGB', size, colour)
    output = BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: 'N', 2: (51.0, 21.0, 0.0)}  # GPSInfo
        exif[0x0112] = 1
        image.save(output, 'JPEG', exif=exif)
    else:
        image.save(output, 'JPEG')
    return output.getvalue()


def _response(status=200, payload=None):
    response = mock.Mock(status_code=status)
    response.json.return_value = payload if payload is not None else {}
    response.text = json.dumps(payload or {})
    return response


@pytest.fixture
def channel(db, settings, tmp_path):
    settings.SITE_BASE_URL = 'https://portal.example.org'
    settings.MEDIA_ROOT = str(tmp_path)
    from tools.models import ToolsConfig

    meta = ToolsConfig.get_config()
    meta.instagram_api_host = 'graph.facebook.com'
    meta.instagram_account_id = '1789'
    meta.instagram_access_token = 'TOKEN'
    meta.facebook_page_id = '1017'
    meta.save()
    config = BeitragsConfig.get_config()
    config.instagram_enabled = True
    config.facebook_enabled = True
    config.website_enabled = True
    config.wordpress_url = 'https://www.example.de/'
    config.wordpress_user = 'okt'
    config.wordpress_app_password = 'abcd efgh'
    config.save()
    return config


@pytest.fixture
def thema(db):
    return Thema.objects.create(
        name='Medienpädagogik', hashtags='Medienbildung, #Merseburg',
        signatur_instagram='Mehr im Link in Bio', signatur_facebook='OK Merseburg',
        signatur_website='Ihr Offener Kanal', wordpress_categories='Medienpädagogik',
        wordpress_tags='Workshop')


@pytest.fixture
def autor(db):
    user = OKUser.objects.create_user('autor@example.org', password='pw')
    user.is_staff = True
    user.user_permissions.add(Permission.objects.get(codename='add_beitrag'))
    user.save()
    return user


@pytest.fixture
def freigeber(db, thema):
    user = OKUser.objects.create_user('freigabe@example.org', password='pw')
    user.is_staff = True
    user.save()
    thema.freigeber.add(user)
    return user


@pytest.fixture
def beitrag(channel, thema, autor):
    post = Beitrag.objects.create(
        titel='Workshop im Studio', text='Zehn Jugendliche drehen ihren ersten Film.',
        link='https://mediathek.example/v/1', thema=thema, einwilligung=True, created_by=autor)
    for position in range(2):
        BeitragFoto.objects.create(beitrag=post, position=position,
                                   bild=SimpleUploadedFile(f'f{position}.jpg', _jpeg()))
    workflow.ensure_ziele(post)
    return post


# ---------------------------------------------------------------------------
# texts and checks
# ---------------------------------------------------------------------------

def test_hashtags_are_normalised():
    assert workflow.hashtags('Medienbildung, #Merseburg medienbildung') == '#Medienbildung #Merseburg'


def test_every_platform_gets_its_own_text(beitrag):
    texts = {z.plattform: z.text for z in beitrag.ziele.all()}
    assert texts[PLATFORM_INSTAGRAM] == (
        'Workshop im Studio\n\nZehn Jugendliche drehen ihren ersten Film.\n\n'
        'Mehr im Link in Bio\n\n#Medienbildung #Merseburg')
    assert 'https://mediathek.example/v/1' not in texts[PLATFORM_INSTAGRAM]
    assert 'https://mediathek.example/v/1' in texts[PLATFORM_FACEBOOK]
    assert texts[PLATFORM_WEBSITE] == 'Zehn Jugendliche drehen ihren ersten Film.\n\nIhr Offener Kanal'


def test_edited_text_is_kept_when_the_post_changes(beitrag):
    ziel = beitrag.ziele.get(plattform=PLATFORM_FACEBOOK)
    ziel.text = 'Von Hand geschrieben'
    workflow.mark_edited(ziel)
    ziel.save()
    beitrag.text = 'Neuer Text'
    beitrag.save()
    workflow.ensure_ziele(beitrag)
    assert beitrag.ziele.get(plattform=PLATFORM_FACEBOOK).text == 'Von Hand geschrieben'
    assert 'Neuer Text' in beitrag.ziele.get(plattform=PLATFORM_INSTAGRAM).text


def test_platforms_not_set_up_are_left_out(channel, thema, autor):
    channel.website_enabled = False
    channel.save()
    post = Beitrag.objects.create(titel='T', text='x', thema=thema, created_by=autor)
    workflow.ensure_ziele(post)
    assert set(post.ziele.values_list('plattform', flat=True)) == {PLATFORM_INSTAGRAM, PLATFORM_FACEBOOK}


def test_problems_before_approval(channel, thema, autor):
    post = Beitrag.objects.create(titel='T', text='x', thema=thema, created_by=autor)
    workflow.ensure_ziele(post)
    assert any('Instagram' in p for p in workflow.problems(post))
    BeitragFoto.objects.create(beitrag=post, bild=SimpleUploadedFile('a.jpg', _jpeg()))
    assert any('agreed' in p for p in workflow.problems(post))
    post.einwilligung = True
    post.save()
    ziel = post.ziele.get(plattform=PLATFORM_INSTAGRAM)
    ziel.text = '#a #b #c #d #e #f'
    ziel.save()
    assert any('hashtags' in p for p in workflow.problems(post))


# ---------------------------------------------------------------------------
# photos
# ---------------------------------------------------------------------------

def test_instagram_rendition_is_4_5_without_gps():
    data = images.rendition(BytesIO(_jpeg((3000, 2000), exif_gps=True)), 'instagram')
    image = Image.open(BytesIO(data))
    assert image.size == images.INSTAGRAM_SIZE
    assert image.format == 'JPEG'
    assert not image.getexif()


def test_web_rendition_is_limited_and_heic_is_read():
    import pillow_heif  # noqa: F401  (registers the HEIC opener)

    source = BytesIO()
    Image.new('RGB', (4000, 3000), 'blue').save(source, 'HEIF')
    source.seek(0)
    assert images.is_readable(source)
    image = Image.open(BytesIO(images.rendition(source, 'web')))
    assert max(image.size) == images.WEB_LONG_SIDE


def test_crop_follows_the_focus():
    tall = Image.new('RGB', (100, 300))
    assert images.crop_4_5(tall, 0).size == (100, 125)
    top = images.crop_4_5(tall, 0).getbbox()
    assert top is None or top[1] == 0


def test_photo_previews_need_a_signature_until_approval(client, beitrag, freigeber):
    from beitraege.links import preview_url

    foto = beitrag.fotos.first()
    plain = reverse('beitraege:foto', args=[foto.token, 'instagram'])
    assert client.get(plain).status_code == 404
    response = client.get(preview_url(foto, 'instagram'))
    assert response.status_code == 200 and response['Content-Type'] == 'image/jpeg'
    assert client.get(plain + '?s=forged').status_code == 404
    # From the approval on, Instagram and Facebook fetch them with the token alone.
    with mock.patch('beitraege.tasks.publish_beitrag.delay'):
        workflow.approve(beitrag, freigeber)
    assert client.get(plain).status_code == 200
    assert client.get(reverse('beitraege:foto', args=['nope', 'web'])).status_code == 404


def test_upload_is_kept_without_gps_and_outside_the_public_media(channel, beitrag):
    foto = BeitragFoto.objects.create(
        beitrag=beitrag, bild=SimpleUploadedFile('phone.jpg', _jpeg((800, 600), exif_gps=True)))
    assert foto.bild.name.startswith('.beitraege/') and foto.bild.name.endswith('.jpg')
    with foto.bild.open('rb') as handle:
        stored = Image.open(BytesIO(handle.read()))
    assert stored.format == 'JPEG' and not stored.getexif()


# ---------------------------------------------------------------------------
# submission and approval
# ---------------------------------------------------------------------------

def test_new_post_from_the_phone_is_submitted(client, channel, thema, autor, freigeber, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    client.force_login(autor)
    with mock.patch('notifications.services.emit') as emit:
        response = client.post(reverse('beitraege:neu'), {
            'thema': thema.pk, 'titel': 'Vor Ort', 'text': 'Es läuft.',
            'fotos': [SimpleUploadedFile('a.jpg', _jpeg()), SimpleUploadedFile('b.jpg', _jpeg())],
            'einwilligung': 'on', 'plattformen': [PLATFORM_INSTAGRAM, PLATFORM_WEBSITE],
        })
    post = Beitrag.objects.get(titel='Vor Ort')
    assert response.status_code == 302
    assert post.status == Beitrag.STATUS_SUBMITTED and post.created_by == autor
    assert post.fotos.count() == 2
    assert dict(post.ziele.values_list('plattform', 'aktiv')) == {
        PLATFORM_INSTAGRAM: True, PLATFORM_FACEBOOK: False, PLATFORM_WEBSITE: True}
    assert emit.call_args.args[0] == 'beitraege.submitted'
    assert list(emit.call_args.kwargs['recipients']) == [freigeber]
    assert [m.to for m in mail.outbox] == [['freigabe@example.org']]
    assert '/beitraege/freigabe/' in mail.outbox[0].body


def test_new_post_needs_consent_for_photos(client, channel, thema, autor):
    client.force_login(autor)
    response = client.post(reverse('beitraege:neu'), {
        'thema': thema.pk, 'titel': 'X', 'text': 'Y',
        'fotos': [SimpleUploadedFile('a.jpg', _jpeg())], 'plattformen': [PLATFORM_INSTAGRAM]})
    assert response.status_code == 200
    assert not Beitrag.objects.exists()


def test_only_permitted_staff_may_write(client, channel, db):
    nobody = OKUser.objects.create_user('nobody@example.org', password='pw')
    client.force_login(nobody)
    assert client.get(reverse('beitraege:neu')).status_code == 403


def test_one_approval_from_the_mail_link_publishes(client, beitrag, freigeber):
    from beitraege.notify import approval_url

    workflow.submit(beitrag)
    url = approval_url(beitrag, freigeber).replace('https://portal.example.org', '')
    page = client.get(url)
    assert page.status_code == 200 and b'Workshop im Studio' in page.content
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_SUBMITTED  # opening alone does nothing

    with mock.patch('beitraege.tasks.publish_beitrag.delay') as publish, \
            mock.patch('django.db.transaction.on_commit', side_effect=lambda f: f()):
        client.post(url, {'aktion': 'freigeben'})
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_APPROVED and beitrag.approved_by == freigeber
    publish.assert_called_once_with(beitrag.pk)


def test_scheduled_post_waits_for_its_time(beitrag, freigeber):
    beitrag.publish_at = timezone.now() + timedelta(hours=2)
    beitrag.save()
    with mock.patch('beitraege.tasks.publish_beitrag.delay') as publish:
        workflow.approve(beitrag, freigeber)
    publish.assert_not_called()
    assert list(workflow.due_posts()) == []
    Beitrag.objects.filter(pk=beitrag.pk).update(publish_at=timezone.now() - timedelta(minutes=1))
    assert list(workflow.due_posts()) == [beitrag]


def test_approver_of_another_topic_may_not_approve(client, beitrag, db):
    other = OKUser.objects.create_user('andere@example.org', password='pw')
    Thema.objects.create(name='Bildung').freigeber.add(other)
    from beitraege.notify import approval_token

    response = client.get(reverse('beitraege:freigabe', args=[approval_token(beitrag, other)]))
    assert response.status_code == 403


def test_approve_all_permission_covers_every_topic(beitrag, db):
    boss = OKUser.objects.create_user('chef@example.org', password='pw')
    boss.user_permissions.add(Permission.objects.get(codename='freigeben_alle'))
    boss = OKUser.objects.get(pk=boss.pk)
    assert beitrag.may_approve(boss)
    assert boss in beitrag.approvers()


def test_sending_back_tells_the_author(client, beitrag, freigeber, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    from beitraege.notify import approval_token

    workflow.submit(beitrag)
    mail.outbox.clear()
    client.post(reverse('beitraege:freigabe', args=[approval_token(beitrag, freigeber)]),
                {'aktion': 'ablehnen', 'grund': 'Bitte ein anderes Foto'})
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_REJECTED
    assert beitrag.rejection_note == 'Bitte ein anderes Foto'
    assert mail.outbox[0].to == ['autor@example.org']


def test_expired_or_wrong_link_is_refused(client, db):
    assert client.get(reverse('beitraege:freigabe', args=['falsch'])).status_code == 400


# ---------------------------------------------------------------------------
# publishing
# ---------------------------------------------------------------------------

def _approved(beitrag, freigeber):
    with mock.patch('beitraege.tasks.publish_beitrag.delay'):
        workflow.approve(beitrag, freigeber)
    return workflow.claim(beitrag.pk)


class FakeMeta:
    """Answers Instagram and Facebook calls by URL; both share ``requests``."""

    def __init__(self, facebook_error=None):
        self.calls = []
        self.facebook_error = facebook_error
        self.counter = 0

    def _next(self, prefix):
        self.counter += 1
        return f'{prefix}{self.counter}'

    def post(self, url, data=None, **kwargs):
        self.calls.append(('POST', url, data or {}))
        if '/1789/media_publish' in url:
            return _response(payload={'id': 'M1'})
        if '/1789/media' in url:
            return _response(payload={'id': self._next('C')})
        if self.facebook_error and '/1017/' in url:
            return self.facebook_error
        if '/1017/photos' in url:
            return _response(payload={'id': self._next('P')})
        if '/1017/feed' in url:
            return _response(payload={'id': '1017_55'})
        raise AssertionError(f'unexpected POST {url}')

    def get(self, url, params=None, **kwargs):
        self.calls.append(('GET', url, params or {}))
        fields = (params or {}).get('fields', '')
        if fields == 'access_token':
            return self.facebook_error or _response(payload={'access_token': 'PAGE'})
        if fields == 'status_code,status':
            return _response(payload={'status_code': 'FINISHED'})
        if fields == 'permalink':
            return _response(payload={'permalink': 'https://www.instagram.com/p/abc/'})
        if fields == 'permalink_url':
            return _response(payload={'permalink_url': 'https://www.facebook.com/x/posts/1'})
        raise AssertionError(f'unexpected GET {url}')


def _fake_wordpress(calls):
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith('/media'):
            media_id = 10 + sum(1 for c in calls if c[1].endswith('/media'))
            return _response(201, {'id': media_id, 'source_url': f'https://www.example.de/{media_id}.jpg'})
        if '/media/' in url:
            return _response(200, {})
        if url.endswith('/categories') and method == 'GET':
            return _response(200, [{'id': 5, 'name': 'Medienpädagogik'}])
        if url.endswith('/tags') and method == 'GET':
            return _response(200, [])
        if url.endswith('/tags') and method == 'POST':
            return _response(201, {'id': 9, 'name': 'Workshop'})
        if url.endswith('/posts'):
            return _response(201, {'id': 77, 'link': 'https://www.example.de/workshop/'})
        raise AssertionError(f'unexpected {method} {url}')
    return request


def test_publishing_on_all_three_platforms(beitrag, freigeber):
    post = _approved(beitrag, freigeber)
    meta, wp_calls = FakeMeta(), []
    with mock.patch('requests.post', side_effect=meta.post), \
            mock.patch('requests.get', side_effect=meta.get), \
            mock.patch('beitraege.services.wordpress.requests.request',
                       side_effect=_fake_wordpress(wp_calls)):
        assert workflow.publish(post) == Beitrag.STATUS_PUBLISHED

    posts = [c for c in meta.calls if c[0] == 'POST']
    items = [c for c in posts if c[2].get('is_carousel_item') == 'true']
    assert len(items) == 2
    assert items[0][2]['image_url'].startswith('https://portal.example.org/beitraege/foto/')
    carousel = next(c for c in posts if c[2].get('media_type') == 'CAROUSEL')
    children = carousel[2]['children'].split(',')
    assert len(children) == 2 and all(c.startswith('C') for c in children)
    assert carousel[2]['caption'].startswith('Workshop im Studio')
    photos = [c for c in posts if c[1].endswith('/1017/photos')]
    assert [p[2]['published'] for p in photos] == ['false', 'false']
    feed = next(c for c in posts if c[1].endswith('/1017/feed'))
    assert {'attached_media[0]', 'attached_media[1]'} <= set(feed[2])
    created = wp_calls[-1]
    body = created[2]['json']
    assert body['title'] == 'Workshop im Studio' and body['status'] == 'publish'
    assert body['featured_media'] == 11 and body['categories'] == [5] and body['tags'] == [9]
    assert 'wp:gallery' in body['content'] and 'https://mediathek.example/v/1' in body['content']
    links = dict(post.ziele.values_list('plattform', 'permalink'))
    assert links == {PLATFORM_INSTAGRAM: 'https://www.instagram.com/p/abc/',
                     PLATFORM_FACEBOOK: 'https://www.facebook.com/x/posts/1',
                     PLATFORM_WEBSITE: 'https://www.example.de/workshop/'}


def test_one_failing_platform_does_not_stop_the_others(beitrag, freigeber):
    BeitragZiel.objects.filter(beitrag=beitrag, plattform=PLATFORM_INSTAGRAM).update(aktiv=False)
    post = _approved(beitrag, freigeber)
    broken = FakeMeta(facebook_error=_response(403, {'error': {'message': 'Permissions error',
                                                                'code': 200}}))
    with mock.patch('requests.post', side_effect=broken.post), \
            mock.patch('requests.get', side_effect=broken.get), \
            mock.patch('beitraege.services.wordpress.requests.request', side_effect=_fake_wordpress([])), \
            mock.patch('notifications.services.emit') as emit:
        assert workflow.publish(post) == Beitrag.STATUS_PARTIAL
    statuses = dict(post.ziele.filter(aktiv=True).values_list('plattform', 'status'))
    assert statuses == {PLATFORM_FACEBOOK: BeitragZiel.STATUS_FAILED,
                        PLATFORM_WEBSITE: BeitragZiel.STATUS_PUBLISHED}
    assert 'Permissions error' in post.ziele.get(plattform=PLATFORM_FACEBOOK).error
    assert emit.call_args.args[0] == 'beitraege.failed'

    # Publishing again only retries Facebook.
    with mock.patch('beitraege.tasks.publish_beitrag.delay'), \
            mock.patch('django.db.transaction.on_commit', side_effect=lambda f: f()):
        assert workflow.retry(post)
    post = workflow.claim(post.pk)
    meta = FakeMeta()
    with mock.patch('requests.post', side_effect=meta.post), \
            mock.patch('requests.get', side_effect=meta.get), \
            mock.patch('beitraege.services.wordpress.requests.request') as wp_again:
        assert workflow.publish(post) == Beitrag.STATUS_PUBLISHED
    wp_again.assert_not_called()


# ---------------------------------------------------------------------------
# names, order, "my posts"
# ---------------------------------------------------------------------------

def test_person_name_uses_the_profile(db, user, autor):
    from beitraege.models import person_name

    profile = user.profile
    profile.first_name, profile.last_name = 'Max', 'Mustermann'
    profile.save()
    assert person_name(user) == 'Max Mustermann'
    assert person_name(autor) == 'autor@example.org'  # no profile: the mail address
    assert person_name(None) == '-'


def test_check_page_lists_instagram_facebook_website_and_the_4_5_crop(client, beitrag, freigeber):
    workflow.submit(beitrag)
    client.force_login(freigeber)
    page = client.get(reverse('beitraege:pruefen', args=[beitrag.pk])).content.decode()
    assert page.index('<h2>Instagram') < page.index('<h2>Facebook') < page.index('<h2>Website')
    assert '/instagram.jpg' in page


def test_my_posts_shows_own_posts_and_those_waiting_for_me(client, beitrag, autor, freigeber):
    workflow.submit(beitrag)
    client.force_login(autor)
    page = client.get(reverse('beitraege:meine')).content.decode()
    assert 'Workshop im Studio' in page

    client.force_login(freigeber)
    page = client.get(reverse('beitraege:meine')).content.decode()
    assert 'Workshop im Studio' in page and reverse('beitraege:pruefen', args=[beitrag.pk]) in page


def test_author_sees_the_own_post_but_cannot_approve(client, beitrag, autor):
    workflow.submit(beitrag)
    client.force_login(autor)
    response = client.get(reverse('beitraege:pruefen', args=[beitrag.pk]))
    assert response.status_code == 200
    assert b'name="aktion"' not in response.content
    with mock.patch('beitraege.tasks.publish_beitrag.delay') as publish:
        client.post(reverse('beitraege:pruefen', args=[beitrag.pk]), {'aktion': 'freigeben'})
    publish.assert_not_called()
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_SUBMITTED


def test_others_may_not_see_a_post(client, beitrag, db):
    stranger = OKUser.objects.create_user('fremd@example.org', password='pw')
    client.force_login(stranger)
    assert client.get(reverse('beitraege:pruefen', args=[beitrag.pk])).status_code == 403


# ---------------------------------------------------------------------------
# editing on the phone, access
# ---------------------------------------------------------------------------

def _edit_data(beitrag, **changes):
    data = {
        'thema': beitrag.thema.pk, 'titel': beitrag.titel, 'text': beitrag.text,
        'link': beitrag.link, 'einwilligung': 'on' if beitrag.einwilligung else '',
        'plattformen': [z.plattform for z in beitrag.ziele.filter(aktiv=True)],
    }
    data.update(changes)
    return data


def test_author_fixes_a_returned_post_and_submits_it_again(client, beitrag, autor, freigeber):
    workflow.submit(beitrag)
    with mock.patch('beitraege.notify._mail'):
        workflow.reject(beitrag, freigeber, 'Anderes Foto bitte')
    first, second = beitrag.fotos.all()
    client.force_login(autor)
    page = client.get(reverse('beitraege:bearbeiten', args=[beitrag.pk]))
    assert page.status_code == 200 and b'text_instagram' not in page.content  # authors: no platform texts
    with mock.patch('notifications.services.emit') as emit:
        response = client.post(reverse('beitraege:bearbeiten', args=[beitrag.pk]), _edit_data(
            beitrag, text='Neuer Text', **{f'entfernen_{first.pk}': '1', f'fokus_{second.pk}': '0'}))
    assert response.status_code == 302
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_SUBMITTED and beitrag.text == 'Neuer Text'
    assert list(beitrag.fotos.values_list('pk', 'fokus_y')) == [(second.pk, 0)]
    assert 'Neuer Text' in beitrag.ziele.get(plattform=PLATFORM_INSTAGRAM).text
    assert emit.call_args.args[0] == 'beitraege.submitted'


def test_approver_changes_the_text_of_one_platform(client, beitrag, freigeber):
    workflow.submit(beitrag)
    client.force_login(freigeber)
    client.post(reverse('beitraege:bearbeiten', args=[beitrag.pk]), _edit_data(
        beitrag, text_facebook='Nur für Facebook'))
    ziel = beitrag.ziele.get(plattform=PLATFORM_FACEBOOK)
    assert ziel.text == 'Nur für Facebook' and ziel.text_bearbeitet
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_SUBMITTED


def test_approved_posts_and_strangers_cannot_edit(client, beitrag, autor, freigeber, db):
    stranger = OKUser.objects.create_user('fremd2@example.org', password='pw')
    client.force_login(stranger)
    assert client.get(reverse('beitraege:bearbeiten', args=[beitrag.pk])).status_code == 403
    with mock.patch('beitraege.tasks.publish_beitrag.delay'):
        workflow.approve(beitrag, freigeber)
    client.force_login(autor)
    assert client.get(reverse('beitraege:bearbeiten', args=[beitrag.pk])).status_code == 403


def test_my_posts_is_only_for_staff_working_with_posts(client, channel, db):
    member = OKUser.objects.create_user('mitglied@example.org', password='pw')
    client.force_login(member)
    assert client.get(reverse('beitraege:meine')).status_code == 403


def test_returned_post_mail_links_to_the_phone_page(beitrag, freigeber, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    workflow.submit(beitrag)
    mail.outbox.clear()
    workflow.reject(beitrag, freigeber, 'Bitte kürzen')
    body = mail.outbox[0].body
    assert f'/beitraege/{beitrag.pk}/bearbeiten/' in body and '/admin/' not in body
