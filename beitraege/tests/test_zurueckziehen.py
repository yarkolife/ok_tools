"""Approvers correct a post from the mail link, hold it back or withdraw it."""

from beitraege import workflow
from beitraege.models import PLATFORM_FACEBOOK
from beitraege.models import PLATFORM_INSTAGRAM
from beitraege.models import PLATFORM_WEBSITE
from beitraege.models import Beitrag
from beitraege.models import BeitragZiel
from beitraege.notify import approval_token
from beitraege.tests.test_beitraege import _edit_data
from beitraege.tests.test_beitraege import _response
from beitraege.tests.test_beitraege import autor  # noqa: F401 (fixtures)
from beitraege.tests.test_beitraege import beitrag  # noqa: F401
from beitraege.tests.test_beitraege import channel  # noqa: F401
from beitraege.tests.test_beitraege import freigeber  # noqa: F401
from beitraege.tests.test_beitraege import thema  # noqa: F401
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from unittest import mock
import pytest


# ---------------------------------------------------------------------------
# correcting from the mail link
# ---------------------------------------------------------------------------

def test_approver_corrects_from_the_mail_link_without_login(client, beitrag, freigeber):
    workflow.submit(beitrag)
    token = approval_token(beitrag, freigeber)
    check = client.get(reverse('beitraege:freigabe', args=[token]))
    edit_url = reverse('beitraege:freigabe_bearbeiten', args=[token])
    assert edit_url.encode() in check.content

    page = client.get(edit_url)
    assert page.status_code == 200 and b'text_instagram' in page.content
    with mock.patch('beitraege.notify._mail') as mail, \
            mock.patch('notifications.services.emit') as emit:
        response = client.post(edit_url, _edit_data(
            beitrag, titel='Workshop im Studio 2', aktion='speichern'))
    assert response.status_code == 302 and response['Location'] == reverse('beitraege:freigabe', args=[token])
    beitrag.refresh_from_db()
    assert beitrag.titel == 'Workshop im Studio 2' and beitrag.status == Beitrag.STATUS_SUBMITTED
    assert emit.call_args.args[0] == 'beitraege.changed'
    assert mail.call_args.args[0] == 'autor@example.org' and mail.call_args.args[1] == 'geaendert'


def test_approver_saves_and_approves_in_one_go(client, beitrag, freigeber):
    workflow.submit(beitrag)
    token = approval_token(beitrag, freigeber)
    with mock.patch('beitraege.notify._mail'), mock.patch('notifications.services.emit'), \
            mock.patch('beitraege.tasks.publish_beitrag.delay'):
        client.post(reverse('beitraege:freigabe_bearbeiten', args=[token]), _edit_data(
            beitrag, text_facebook='Korrigiert', aktion='freigeben'))
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_APPROVED and beitrag.approved_by == freigeber
    assert beitrag.ziele.get(plattform=PLATFORM_FACEBOOK).text == 'Korrigiert'


def test_the_mail_link_of_an_author_does_not_open_the_editor(client, beitrag, autor):
    workflow.submit(beitrag)
    token = approval_token(beitrag, autor)
    assert client.get(reverse('beitraege:freigabe_bearbeiten', args=[token])).status_code == 403
    assert client.get(reverse('beitraege:freigabe_bearbeiten', args=['falsch'])).status_code == 404


# ---------------------------------------------------------------------------
# holding back and withdrawing
# ---------------------------------------------------------------------------

def test_scheduled_post_can_be_held_back(client, beitrag, freigeber):
    beitrag.publish_at = timezone.now() + timedelta(days=1)
    beitrag.save()
    workflow.approve(beitrag, freigeber)
    url = reverse('beitraege:freigabe', args=[approval_token(beitrag, freigeber)])
    assert b'zurueckhalten' in client.get(url).content
    client.post(url, {'aktion': 'zurueckhalten'})
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_SUBMITTED and beitrag.approved_by is None
    assert beitrag not in workflow.due_posts()


def _published(beitrag):
    beitrag.status = Beitrag.STATUS_PUBLISHED
    beitrag.save()
    ids = {PLATFORM_INSTAGRAM: '1790', PLATFORM_FACEBOOK: '1017_55', PLATFORM_WEBSITE: '77'}
    for ziel in beitrag.ziele.all():
        ziel.status = BeitragZiel.STATUS_PUBLISHED
        ziel.remote_id = ids[ziel.plattform]
        ziel.save()


def test_withdrawing_trashes_the_website_post_and_deletes_on_facebook(client, beitrag, freigeber):
    _published(beitrag)
    url = reverse('beitraege:freigabe_zurueckziehen', args=[approval_token(beitrag, freigeber)])
    check = client.get(reverse('beitraege:freigabe', args=[approval_token(beitrag, freigeber)]))
    assert url.encode() in check.content
    assert client.get(url).status_code == 200

    wp, meta = [], []

    def wordpress(method, url, **kwargs):
        wp.append((method, url, kwargs))
        return _response(200, {'id': 77, 'status': 'trash'})

    def delete(url, params=None, **kwargs):
        meta.append(url)
        return _response(200, {'success': True})

    with mock.patch('beitraege.services.wordpress.requests.request', side_effect=wordpress), \
            mock.patch('requests.get', return_value=_response(200, {'access_token': 'PAGE'})), \
            mock.patch('requests.delete', side_effect=delete), \
            mock.patch('notifications.services.emit') as emit:
        client.post(url, {'p_website': '1', 'p_facebook': '1'})
    assert wp == [('DELETE', 'https://www.example.de/wp-json/wp/v2/posts/77', mock.ANY)]
    assert 'force' not in str(wp[0][2])  # trash, not delete for good
    assert meta == ['https://graph.facebook.com/v27.0/1017_55']
    states = dict(beitrag.ziele.values_list('plattform', 'status'))
    assert states == {PLATFORM_WEBSITE: 'withdrawn', PLATFORM_FACEBOOK: 'withdrawn',
                      PLATFORM_INSTAGRAM: 'published'}
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_PUBLISHED
    assert emit.call_args.args[0] == 'beitraege.withdrawn'


def test_instagram_without_permission_keeps_the_post_and_says_why(beitrag, freigeber):
    _published(beitrag)
    refused = _response(403, {'error': {'message': '(#10) Application does not have permission',
                                        'code': 10}})
    with mock.patch('requests.delete', return_value=refused):
        errors = workflow.withdraw(beitrag, freigeber, platforms=[PLATFORM_INSTAGRAM])
    assert len(errors) == 1 and 'instagram_manage_contents' in errors[0]
    ziel = beitrag.ziele.get(plattform=PLATFORM_INSTAGRAM)
    assert ziel.status == BeitragZiel.STATUS_PUBLISHED and 'instagram_manage_contents' in ziel.error


def test_all_platforms_withdrawn_and_not_published_again(beitrag, freigeber):
    _published(beitrag)
    with mock.patch('beitraege.services.wordpress.requests.request',
                    return_value=_response(200, {})), \
            mock.patch('requests.get', return_value=_response(200, {'access_token': 'PAGE'})), \
            mock.patch('requests.delete', return_value=_response(200, {'success': True})):
        assert workflow.withdraw(beitrag, freigeber) == []
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_WITHDRAWN
    assert not workflow.retry(beitrag)


def test_only_approvers_may_withdraw(client, beitrag, autor):
    _published(beitrag)
    client.force_login(autor)
    assert client.get(reverse('beitraege:zurueckziehen', args=[beitrag.pk])).status_code == 403
    with pytest.raises(Exception):
        workflow.withdraw(beitrag, autor)


def test_approving_from_the_editor_without_changes_tells_the_author_nothing(client, beitrag, freigeber):
    workflow.submit(beitrag)
    token = approval_token(beitrag, freigeber)
    with mock.patch('beitraege.notify._mail') as mail, mock.patch('notifications.services.emit'), \
            mock.patch('beitraege.tasks.publish_beitrag.delay'):
        client.post(reverse('beitraege:freigabe_bearbeiten', args=[token]),
                    _edit_data(beitrag, aktion='freigeben'))
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_APPROVED
    assert not mail.called
