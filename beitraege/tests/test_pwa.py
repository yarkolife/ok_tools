"""The post pages as an app (manifest, service worker, icon, share target)."""

from PIL import Image
from django.contrib.auth.models import Permission
from django.urls import reverse
from io import BytesIO
from registration.models import OKUser
import pytest


def test_manifest_installs_the_post_pages(client, db):
    response = client.get(reverse('beitraege:manifest'))
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/manifest+json'
    data = response.json()
    assert data['scope'] == '/beitraege/' and data['start_url'].startswith('/beitraege/')
    assert data['display'] == 'standalone'
    assert {icon['sizes'] for icon in data['icons']} == {'192x192', '512x512'}
    share = data['share_target']
    assert share['action'] == '/beitraege/teilen/' and share['method'] == 'POST'
    assert share['params']['files'][0]['name'] == 'fotos'


def test_service_worker_has_the_scope_of_the_post_pages(client, db):
    response = client.get(reverse('beitraege:sw'))
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/javascript')
    assert response['Cache-Control'] == 'no-cache'
    body = response.content.decode()
    assert "const SHARE = '/beitraege/teilen/'" in body
    assert "const OFFLINE = '/beitraege/offline/'" in body


@pytest.mark.parametrize('size', [180, 192, 512])
def test_icon_is_a_square_png(client, db, size):
    response = client.get(reverse('beitraege:icon', args=[size]))
    assert response['Content-Type'] == 'image/png'
    assert Image.open(BytesIO(response.content)).size == (size, size)


def test_share_without_service_worker_only_redirects(client, db):
    response = client.post(reverse('beitraege:teilen'), {'title': 'x'})
    assert response.status_code == 302 and response['Location'] == reverse('beitraege:neu')


def test_offline_page_needs_no_login(client, db):
    assert client.get(reverse('beitraege:offline')).status_code == 200


def test_post_pages_link_the_manifest_and_offer_the_app(client, db):
    user = OKUser.objects.create_user('autor@example.org', password='pw')
    user.user_permissions.add(Permission.objects.get(codename='add_beitrag'))
    client.force_login(user)
    page = client.get(reverse('beitraege:neu')).content.decode()
    assert 'rel="manifest" href="/beitraege/manifest.webmanifest"' in page
    assert 'apple-touch-icon' in page and 'id="install"' in page
    assert "register('/beitraege/sw.js'" in page
    assert "beitraege-geteilt" in page


@pytest.mark.parametrize('name, letters', [
    ('OK Merseburg', 'OK'), ('Offener Kanal Magdeburg', 'OK'), ('Bürgerradio', 'B'), ('', 'OK')])
def test_icon_letters(name, letters):
    from beitraege.pwa import _initials

    assert _initials(name) == letters
