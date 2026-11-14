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


@pytest.mark.django_db
def test_admin_shows_the_installed_version(client, staff, monkeypatch):
    from ok_tools import version
    monkeypatch.setattr(version, 'commit', lambda: 'abc1234')
    client.force_login(staff)
    html = client.get(reverse('admin:index')).content.decode()
    assert f'OK-Tools {version.VERSION}' in html
    assert 'abc1234' in html


def test_chapter_for_an_older_minor_version_says_so(monkeypatch):
    chapter = kapitel_module.get_chapter(SLUG)
    monkeypatch.setattr(kapitel_module, 'VERSION', chapter.version)
    assert not chapter.older_than_installed
    major, minor, _ = (int(p) for p in chapter.version.split('.'))
    monkeypatch.setattr(kapitel_module, 'VERSION', f'{major}.{minor}.5')
    assert not chapter.older_than_installed
    monkeypatch.setattr(kapitel_module, 'VERSION', f'{major}.{minor + 1}.0')
    assert chapter.older_than_installed


def test_version_tuple():
    from ok_tools.version import version_tuple
    assert version_tuple('4.72.0') == (4, 72, 0)
    assert version_tuple('4.72') == (4, 72, 0)
    assert version_tuple('') == (0, 0, 0)
    assert version_tuple('4.x.1') == (4, 0, 1)


def test_freshness_script_reads_the_same_chapters():
    from handbuch import aktualitaet
    read = {c['slug']: c for c in aktualitaet.read_chapters()}
    for chapter in kapitel_module.KAPITEL:
        assert read[chapter.slug]['stand'] == chapter.stand
        assert read[chapter.slug]['pfade'] == chapter.pfade


def test_watched_paths_exist():
    from handbuch.aktualitaet import REPO
    for chapter in kapitel_module.KAPITEL:
        assert chapter.pfade, f'{chapter.slug}: no pfade'
        for entry in chapter.pfade:
            path = REPO / entry
            assert path.is_dir() if entry.endswith('/') else path.is_file(), entry


def test_staged_pages_without_chapter_give_a_reminder():
    from handbuch.aktualitaet import matches
    from handbuch.aktualitaet import staged_reminders
    chapter = {'slug': 's', 'title': 'T', 'stand': None,
               'pfade': ('rental/views.py', 'rental/templates/rental/')}
    assert matches('rental/templates/rental/list.html', chapter['pfade'])
    assert not matches('rental/views_api.py', chapter['pfade'])
    assert staged_reminders([chapter], ['rental/views.py']) == {'T': ['rental/views.py']}
    assert staged_reminders([chapter], ['rental/views.py', 'handbuch/inhalt/s.md']) == {}
    assert staged_reminders([chapter], ['rental/views.py', 'handbuch/kapitel.py']) == {}
    assert staged_reminders([chapter], ['ok_tools/admin.py']) == {}
