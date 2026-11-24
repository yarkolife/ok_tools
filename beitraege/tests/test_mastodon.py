"""Posts on Mastodon: text, limits, publishing with photos, withdrawing."""

from beitraege import workflow
from beitraege.models import PLATFORM_MASTODON
from beitraege.models import Beitrag
from beitraege.models import BeitragsConfig
from beitraege.models import BeitragZiel
from beitraege.services import mastodon
from beitraege.tests.test_beitraege import _response
from beitraege.tests.test_beitraege import autor  # noqa: F401 (fixtures)
from beitraege.tests.test_beitraege import beitrag  # noqa: F401
from beitraege.tests.test_beitraege import channel  # noqa: F401
from beitraege.tests.test_beitraege import freigeber  # noqa: F401
from beitraege.tests.test_beitraege import thema  # noqa: F401
from django.urls import reverse
from unittest import mock
import pytest


@pytest.fixture
def toot(channel, thema):
    channel.mastodon_enabled = True
    channel.mastodon_url = 'https://social.example/'
    channel.mastodon_token = 'MTOKEN'
    channel.mastodon_max_photos = 1
    channel.save()
    thema.signatur_mastodon = 'OK Merseburg'
    thema.save()
    return channel


@pytest.fixture
def post(toot, beitrag):
    workflow.ensure_ziele(beitrag)
    return beitrag


def test_mastodon_is_a_platform_once_set_up(beitrag, toot):
    assert not beitrag.ziele.filter(plattform=PLATFORM_MASTODON).exists()
    assert PLATFORM_MASTODON in toot.configured_platforms()
    workflow.ensure_ziele(beitrag)
    ziel = beitrag.ziele.get(plattform=PLATFORM_MASTODON)
    assert ziel.aktiv
    assert ziel.text == ('Workshop im Studio\n\nZehn Jugendliche drehen ihren ersten Film.\n\n'
                         'https://mediathek.example/v/1\n\nOK Merseburg\n\n#Medienbildung #Merseburg')


def test_links_count_as_23_characters():
    assert mastodon.length('a https://example.de/' + 'x' * 100) == 2 + 23


def test_too_long_text_stops_the_approval(post):
    ziel = post.ziele.get(plattform=PLATFORM_MASTODON)
    ziel.text = 'x' * 470 + ' https://example.de/' + 'y' * 200
    ziel.save()
    assert not any('Mastodon' in p for p in workflow.problems(post))
    ziel.text = 'x' * 490 + ' https://example.de/'
    ziel.save()
    assert any('Mastodon' in p and '514' in p for p in workflow.problems(post))


def test_publishing_uploads_photos_up_to_the_limit_and_posts(post):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith('/api/v2/media'):
            return _response(200, {'id': '501', 'url': 'https://files.example/1.jpg'})
        return _response(200, {'id': '1129', 'url': 'https://social.example/@okmq/1129'})

    ziele = list(post.ziele.exclude(plattform=PLATFORM_MASTODON))
    for ziel in ziele:
        ziel.aktiv = False
        ziel.save()
    with mock.patch('beitraege.services.mastodon.requests.request', side_effect=request):
        workflow.publish(post)
    assert [c[1] for c in calls] == ['https://social.example/api/v2/media',
                                     'https://social.example/api/v1/statuses']
    status = calls[1][2]
    assert status['headers']['Authorization'] == 'Bearer MTOKEN'
    assert status['headers']['Idempotency-Key'].startswith('oktools-beitrag-')
    assert status['json']['media_ids'] == ['501'] and status['json']['visibility'] == 'public'
    assert 'https://mediathek.example/v/1' in status['json']['status']
    ziel = post.ziele.get(plattform=PLATFORM_MASTODON)
    assert ziel.status == BeitragZiel.STATUS_PUBLISHED and ziel.remote_id == '1129'
    assert ziel.permalink == 'https://social.example/@okmq/1129'


def test_photos_still_processing_are_waited_for(toot):
    answers = [_response(202, {'id': '7', 'url': None}), _response(206, {'id': '7', 'url': None}),
               _response(200, {'id': '7', 'url': 'https://files.example/7.jpg'})]
    with mock.patch('beitraege.services.mastodon.requests.request', side_effect=answers), \
            mock.patch('beitraege.services.mastodon.time.sleep'):
        assert mastodon.upload_media(toot, 'a.jpg', b'jpeg') == '7'


def test_a_refusal_stays_with_the_platform(post):
    refused = _response(422, {'error': 'Validation failed: Text character limit of 500 exceeded'})
    with mock.patch('beitraege.services.mastodon.requests.request', return_value=refused), \
            mock.patch('beitraege.workflow._publish_instagram', return_value=('1', '')), \
            mock.patch('beitraege.workflow._publish_facebook', return_value=('2', '')), \
            mock.patch('beitraege.workflow._publish_website', return_value=('3', '')):
        assert workflow.publish(post) == Beitrag.STATUS_PARTIAL
    ziel = post.ziele.get(plattform=PLATFORM_MASTODON)
    assert ziel.status == BeitragZiel.STATUS_FAILED and 'character limit' in ziel.error


def test_withdrawing_deletes_the_status(post, freigeber):
    ziel = post.ziele.get(plattform=PLATFORM_MASTODON)
    ziel.status, ziel.remote_id = BeitragZiel.STATUS_PUBLISHED, '1129'
    ziel.save()
    with mock.patch('beitraege.services.mastodon.requests.request',
                    return_value=_response(200, {})) as request:
        assert workflow.withdraw(post, freigeber, platforms=[PLATFORM_MASTODON]) == []
    assert request.call_args.args == ('DELETE', 'https://social.example/api/v1/statuses/1129')
    ziel.refresh_from_db()
    assert ziel.status == BeitragZiel.STATUS_WITHDRAWN


def test_connection_test_reads_the_limits(admin_client, toot):
    def request(method, url, **kwargs):  # Mastodon and WordPress share requests.request
        if url.endswith('/api/v1/accounts/verify_credentials'):
            return _response(200, {'acct': 'okmq'})
        if url.endswith('/api/v2/instance'):
            return _response(200, {'configuration': {'statuses': {
                'max_characters': 1000, 'max_media_attachments': 8}}})
        return _response(200, {'name': 'okt', 'roles': ['editor']})

    with mock.patch('requests.request', side_effect=request), \
            mock.patch('tools.services.instagram.account_info', return_value={'username': 'x'}), \
            mock.patch('tools.services.facebook.page_info', return_value={'name': 'x'}):
        response = admin_client.get(reverse('admin:beitraege_beitragsconfig_test'))
    assert response.status_code == 302, response.status_code
    config = BeitragsConfig.get_config()
    assert (config.mastodon_max_characters, config.mastodon_max_photos) == (1000, 8)


def test_check_page_says_when_photos_are_left_out(client, post, freigeber):
    from beitraege.notify import approval_token

    page = client.get(reverse('beitraege:freigabe', args=[approval_token(post, freigeber)]))
    assert b'Mastodon' in page.content
    assert 'nur die ersten 1 Fotos'.encode() in page.content or b'only the first 1 photos' in page.content
