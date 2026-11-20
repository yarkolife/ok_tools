"""Posts sent by mail to the posts mailbox."""

from PIL import Image
from beitraege import mailin
from beitraege.models import Beitrag
from beitraege.models import BeitragsConfig
from beitraege.models import Thema
from django.contrib.auth.models import Permission
from django.core import mail
from email.message import EmailMessage
from io import BytesIO
from registration.models import OKUser
from unittest import mock
import pytest


def _jpeg() -> bytes:
    output = BytesIO()
    Image.new('RGB', (900, 1200), 'green').save(output, 'JPEG')
    return output.getvalue()


def _mail(sender='reporter@example.org', subject='#okpost Sommerfest im Hof', body='Viele Gäste.',
          photos=1, headers=None) -> bytes:
    message = EmailMessage()
    message['From'] = f'Reporter <{sender}>'
    message['To'] = 'beitrag@example.org'
    message['Subject'] = subject
    message['Message-ID'] = f'<{subject.__hash__()}-{body.__hash__()}@example.org>'
    for key, value in (headers or {}).items():
        message[key] = value
    message.set_content(body)
    for index in range(photos):
        message.add_attachment(_jpeg(), maintype='image', subtype='jpeg', filename=f'IMG_{index}.jpg')
    return message.as_bytes()


@pytest.fixture
def mailbox(db, settings, tmp_path):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.SITE_BASE_URL = 'https://portal.example.org'
    settings.MEDIA_ROOT = str(tmp_path)
    config = BeitragsConfig.get_config()
    config.website_enabled = True
    config.wordpress_url, config.wordpress_user, config.wordpress_app_password = (
        'https://www.example.de', 'okt', 'pw')
    config.mail_enabled = True
    config.imap_host, config.imap_user, config.imap_password = 'imap.example.org', 'beitrag', 'pw'
    config.mail_code = '#okpost'
    config.approval_mail = False
    config.save()
    return config


@pytest.fixture
def reporter(db):
    user = OKUser.objects.create_user('reporter@example.org', password='pw')
    user.user_permissions.add(Permission.objects.get(codename='add_beitrag'))
    return user


def test_mail_with_consent_is_submitted(mailbox, reporter):
    Thema.objects.create(name='Bildung')
    raw = _mail(subject='AW: #okpost Sommerfest im Hof [Bildung]', photos=2,
                body='Viele Gäste kamen.\n\nLink: https://mediathek.example/v/9\nEinverständnis: ja\n\n-- \nMax')
    with mock.patch('notifications.services.emit'):
        beitrag = mailin.import_mail(raw, mailbox)
    assert beitrag.status == Beitrag.STATUS_SUBMITTED
    assert beitrag.titel == 'Sommerfest im Hof'
    assert beitrag.text == 'Viele Gäste kamen.'
    assert beitrag.link == 'https://mediathek.example/v/9'
    assert beitrag.thema.name == 'Bildung' and beitrag.einwilligung
    assert beitrag.fotos.count() == 2 and beitrag.created_by == reporter
    assert mail.outbox[-1].to == ['reporter@example.org']
    assert f'/beitraege/{beitrag.pk}/pruefen/' in mail.outbox[-1].body


def test_photos_without_consent_stay_a_draft_for_the_author(mailbox, reporter):
    beitrag = mailin.import_mail(_mail(), mailbox)
    assert beitrag.status == Beitrag.STATUS_DRAFT
    assert beitrag.thema.name == 'Aktuell'
    assert f'/beitraege/{beitrag.pk}/bearbeiten/' in mail.outbox[-1].body


@pytest.mark.parametrize('kwargs', [
    {'subject': 'Sommerfest ohne Code'},
    {'sender': 'fremd@example.org'},
    {'headers': {'Auto-Submitted': 'auto-replied'}},
])
def test_mails_that_fail_a_check_are_ignored_silently(mailbox, reporter, kwargs):
    OKUser.objects.create_user('fremd@example.org', password='pw')  # no right to add posts
    assert mailin.import_mail(_mail(**kwargs), mailbox) is None
    assert not Beitrag.objects.exists() and mail.outbox == []


def test_a_mail_is_never_imported_twice(mailbox, reporter):
    raw = _mail(photos=0)
    with mock.patch('notifications.services.emit'):
        assert mailin.import_mail(raw, mailbox) is not None
        assert mailin.import_mail(raw, mailbox) is None
    assert Beitrag.objects.count() == 1


def test_fetch_reads_unseen_mails_and_marks_them(mailbox, reporter):
    good, bad = _mail(photos=0), _mail(subject='kein Code', photos=0)
    client = mock.Mock()
    client.search.return_value = ('OK', [b'1 2'])
    client.fetch.side_effect = [('OK', [(b'1 (RFC822)', good), b')']),
                                ('OK', [(b'2 (RFC822)', bad), b')'])]
    with mock.patch('beitraege.mailin.imaplib.IMAP4_SSL', return_value=client) as connect, \
            mock.patch('notifications.services.emit'):
        result = mailin.fetch(mailbox)
    connect.assert_called_once_with('imap.example.org', 993)
    client.login.assert_called_once_with('beitrag', 'pw')
    assert result == {'created': 1, 'ignored': 1}
    assert [c.args for c in client.store.call_args_list] == [(b'1', '+FLAGS', '\\Seen'),
                                                             (b'2', '+FLAGS', '\\Seen')]


def test_mail_is_off_without_a_code(mailbox):
    mailbox.mail_code = ''
    mailbox.save()
    assert not mailbox.is_mail_configured()
    assert mailin.fetch(mailbox) == {'status': 'off'}
