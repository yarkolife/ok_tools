"""Drafts on the phone and deleting a post that is not approved yet."""

from beitraege.models import PLATFORM_WEBSITE
from beitraege.models import Beitrag
from beitraege.tests.test_beitraege import _jpeg
from beitraege.tests.test_beitraege import autor  # noqa: F401 (fixtures)
from beitraege.tests.test_beitraege import beitrag  # noqa: F401
from beitraege.tests.test_beitraege import channel  # noqa: F401
from beitraege.tests.test_beitraege import freigeber  # noqa: F401
from beitraege.tests.test_beitraege import thema  # noqa: F401
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from pathlib import Path
from unittest import mock


def test_a_draft_needs_only_a_title_and_tells_nobody(client, channel, thema, autor, freigeber):
    client.force_login(autor)
    with mock.patch('notifications.services.emit') as emit:
        response = client.post(reverse('beitraege:neu'), {
            'aktion': 'entwurf', 'thema': thema.pk, 'titel': 'Halb fertig', 'text': '',
            'fotos': [SimpleUploadedFile('a.jpg', _jpeg())]})
    assert response.status_code == 302 and response['Location'] == reverse('beitraege:meine')
    post = Beitrag.objects.get(titel='Halb fertig')
    assert post.status == Beitrag.STATUS_DRAFT and post.fotos.count() == 1
    emit.assert_not_called()
    page = client.get(reverse('beitraege:meine')).content.decode()
    assert 'Halb fertig' in page and reverse('beitraege:bearbeiten', args=[post.pk]) in page


def test_a_draft_still_needs_a_title(client, channel, thema, autor):
    client.force_login(autor)
    response = client.post(reverse('beitraege:neu'), {'aktion': 'entwurf', 'thema': thema.pk, 'titel': ''})
    assert response.status_code == 200 and not Beitrag.objects.exists()


def test_a_draft_is_saved_again_or_submitted_from_the_edit_page(client, beitrag, autor, freigeber):
    url = reverse('beitraege:bearbeiten', args=[beitrag.pk])
    client.force_login(autor)
    form = {'thema': beitrag.thema.pk, 'titel': 'Neuer Titel', 'text': '', 'plattformen': [PLATFORM_WEBSITE]}
    assert client.post(url, dict(form, aktion='entwurf')).status_code == 302
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_DRAFT and beitrag.titel == 'Neuer Titel'
    # submitting checks everything: the text is missing, the consent for the photos too
    assert client.post(url, dict(form, aktion='einreichen')).status_code == 200
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_DRAFT
    with mock.patch('notifications.services.emit'):
        response = client.post(url, dict(form, aktion='einreichen', text='Fertig.', einwilligung='on'))
    assert response.status_code == 302
    beitrag.refresh_from_db()
    assert beitrag.status == Beitrag.STATUS_SUBMITTED


def test_the_author_deletes_a_post_with_its_photo_files(client, beitrag, autor,
                                                        django_capture_on_commit_callbacks):
    files = [Path(foto.bild.path) for foto in beitrag.fotos.all()]
    assert all(f.exists() for f in files)
    url = reverse('beitraege:loeschen', args=[beitrag.pk])
    client.force_login(autor)
    assert 'Workshop im Studio' in client.get(url).content.decode()  # asks first
    assert Beitrag.objects.filter(pk=beitrag.pk).exists()
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url)
    assert response.status_code == 302
    assert not Beitrag.objects.filter(pk=beitrag.pk).exists()
    assert not any(f.exists() for f in files)


def test_only_the_author_deletes_and_only_before_the_approval(client, beitrag, autor, freigeber):
    url = reverse('beitraege:loeschen', args=[beitrag.pk])
    client.force_login(freigeber)
    assert client.post(url).status_code == 403
    beitrag.status = Beitrag.STATUS_APPROVED
    beitrag.save()
    client.force_login(autor)
    assert client.post(url).status_code == 403
    assert Beitrag.objects.filter(pk=beitrag.pk).exists()
