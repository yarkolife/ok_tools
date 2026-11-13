"""The in-app manual: chapters, version stamp, notes, menu entry."""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.urls import reverse
from handbuch import kapitel as kapitel_module
from handbuch.models import HandbuchNotiz
import pytest
import re


SLUG = 'inventar-und-ausleihe'


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(
        email='staff@example.org', password='x', is_staff=True)


def _menu(rf, user):
    request = rf.get('/admin/')
    request.user = user
    return [m['object_name'] for app in admin.site.get_app_list(request) for m in app['models']]


@pytest.mark.django_db
def test_every_staff_member_finds_the_manual(rf, staff):
    assert 'Handbuch' in _menu(rf, staff)
    assert 'HandbuchNotiz' not in _menu(rf, staff)


@pytest.mark.django_db
def test_index_and_chapter_show_the_version_stamp(client, staff):
    client.force_login(staff)
    index = client.get(reverse('admin:handbuch_index'), secure=True)
    assert index.status_code == 200
    chapter = kapitel_module.get_chapter(SLUG)
    assert f'OK-Tools {chapter.version}' in index.content.decode()

    page = client.get(reverse('admin:handbuch_kapitel', args=[SLUG]), secure=True)
    html = page.content.decode()
    assert page.status_code == 200
    assert f'OK-Tools {chapter.version}' in html
    assert chapter.stand.strftime('%d.%m.%Y') in html
    for anchor in ('inventar', 'etikett', 'ausleihe', 'schnell', 'rueckgabe'):
        assert f'id="{anchor}"' in html


@pytest.mark.django_db
def test_every_screenshot_of_the_chapter_exists(client, staff):
    client.force_login(staff)
    html = client.get(reverse('admin:handbuch_kapitel', args=[SLUG]), secure=True).content.decode()
    images = set(re.findall(r'handbuch/bilder/([\w.-]+)', html))
    assert len(images) >= 20
    missing = [name for name in images if not finders.find(f'handbuch/bilder/{name}')]
    assert missing == []


@pytest.mark.django_db
def test_unknown_chapter_is_404(client, staff):
    client.force_login(staff)
    assert client.get(reverse('admin:handbuch_kapitel', args=['gibt-es-nicht']), secure=True).status_code == 404


@pytest.mark.django_db
def test_chapter_needs_its_modules(monkeypatch):
    real = apps.is_installed
    monkeypatch.setattr(apps, 'is_installed', lambda app: False if app == 'rental' else real(app))
    assert kapitel_module.get_chapter(SLUG) is None


@pytest.mark.django_db
def test_notes_need_the_add_permission(client, staff):
    client.force_login(staff)
    url = reverse('admin:handbuch_kapitel', args=[SLUG])

    client.post(url, {'text': 'Etikettendrucker steht im Büro 2.'}, secure=True)
    assert not HandbuchNotiz.objects.exists()

    staff.user_permissions.add(Permission.objects.get(codename='add_handbuchnotiz'))
    response = client.post(url, {'text': 'Etikettendrucker steht im Büro 2.'}, secure=True)
    assert response.status_code == 302
    note = HandbuchNotiz.objects.get()
    assert (note.kapitel, note.created_by) == (SLUG, staff)
    assert 'Etikettendrucker steht im Büro 2.' in client.get(url, secure=True).content.decode()


def test_chapters_carry_a_version_and_date():
    for chapter in kapitel_module.KAPITEL:
        assert re.fullmatch(r'\d+\.\d+\.\d+', chapter.version)
        assert chapter.stand
