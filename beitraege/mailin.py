"""Posts sent by mail.

Staff send a mail to the posts mailbox: subject = title, text = text,
attached photos = photos. Every 5 minutes the mailbox is read over IMAP.

Only mails that pass all checks become posts; the others are marked as
read and ignored without an answer (no mail to forged or unknown senders):

- the subject contains the code of the post configuration (a sender address
  alone can be forged),
- the sender is an active user with the right to add posts,
- it is no automatic mail (out of office, bounce).

Optional lines in the text, removed from it:

- ``Thema: Bildung`` (or ``[Bildung]`` in the subject) chooses the topic;
  otherwise "Aktuell", or the first active topic,
- ``Link: https://...``,
- ``Einverständnis: ja`` confirms the consent of the people on the photos.

With photos but without that confirmation the post stays a draft and the
author gets a link to check it, tick the consent and submit it; otherwise
it is submitted to the approvers right away. The author always gets a mail
with the link to the post.
"""

from .models import Beitrag
from .models import BeitragFoto
from .models import BeitragsConfig
from .models import Thema
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from io import BytesIO
import imaplib
import logging
import re


logger = logging.getLogger('django')

MAX_ATTACHMENT = 25 * 1024 * 1024
PHOTO_SUFFIXES = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp')
_CONSENT = re.compile(r'^\s*einverst(?:ä|ae)ndnis\s*:\s*(ja|yes|j|x)\s*$', re.I | re.M)
_LINK = re.compile(r'^\s*link\s*:\s*(https?://\S+)\s*$', re.I | re.M)
_TOPIC_LINE = re.compile(r'^\s*thema\s*:\s*(.+?)\s*$', re.I | re.M)
_TOPIC_TAG = re.compile(r'\[([^\]]+)\]')
_PREFIX = re.compile(r'^\s*((re|aw|fwd?|wg)\s*:\s*)+', re.I)


class Ignored(Exception):
    """The mail is not taken; the message says why (for the log only)."""


def _text_of(message) -> str:
    from django.utils.html import strip_tags

    part = message.get_body(preferencelist=('plain', 'html'))
    if part is None:
        return ''
    content = part.get_content()
    if part.get_content_type() == 'text/html':
        content = strip_tags(re.sub(r'<br\s*/?>|</p>', '\n', content, flags=re.I))
    content = content.replace('\r\n', '\n')
    # Signature: everything after a line "-- ".
    content = re.split(r'^-- ?$', content, maxsplit=1, flags=re.M)[0]
    return content.strip()


def _photos_of(message) -> list:
    from .services import images
    from django.core.files.uploadedfile import SimpleUploadedFile

    photos = []
    for part in message.iter_attachments():
        name = part.get_filename() or ''
        if not (part.get_content_maintype() == 'image' or name.lower().endswith(PHOTO_SUFFIXES)):
            continue
        data = part.get_content()
        if not isinstance(data, bytes) or not data or len(data) > MAX_ATTACHMENT:
            continue
        if not images.is_readable(BytesIO(data)):
            continue
        photos.append(SimpleUploadedFile(name or 'foto.jpg', data))
        if len(photos) == Beitrag.MAX_PHOTOS:
            break
    return photos


def _topic(subject: str, text: str):
    names = [m.strip() for m in _TOPIC_TAG.findall(subject)]
    line = _TOPIC_LINE.search(text)
    if line:
        names.insert(0, line.group(1))
    active = Thema.objects.filter(is_active=True)
    for name in names:
        found = active.filter(name__iexact=name).first() or active.filter(name__icontains=name).first()
        if found:
            return found
    return active.filter(name__iexact='Aktuell').first() or active.first()


def parse(raw: bytes, config: BeitragsConfig) -> dict:
    """Check a mail and read what a post needs; raise :class:`Ignored` if not taken."""
    from django.contrib.auth import get_user_model

    message = BytesParser(policy=policy.default).parsebytes(raw)
    if (message.get('Auto-Submitted', 'no') or 'no').lower() != 'no' or message.get('X-Autoreply'):
        raise Ignored('automatic mail')
    subject = str(message.get('Subject', '') or '')
    code = (config.mail_code or '').strip()
    if not code or code.lower() not in subject.lower():
        raise Ignored('code missing in the subject')
    sender = parseaddr(str(message.get('From', '')))[1].strip().lower()
    user = get_user_model().objects.filter(email__iexact=sender, is_active=True).first()
    if user is None or not user.has_perm('beitraege.add_beitrag'):
        raise Ignored(f'sender {sender!r} may not add posts')

    text = _text_of(message)
    title = re.sub(re.escape(code), '', subject, flags=re.I)
    title = _TOPIC_TAG.sub('', _PREFIX.sub('', title)).strip(' -:') or 'Beitrag per E-Mail'
    thema = _topic(subject, text)
    if thema is None:
        raise Ignored('no active topic')
    link = _LINK.search(text)
    consent = bool(_CONSENT.search(text))
    for pattern in (_LINK, _CONSENT, _TOPIC_LINE):
        text = pattern.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return {
        'user': user,
        'titel': title[:200],
        'text': text or title,
        'link': link.group(1) if link else '',
        'thema': thema,
        'einwilligung': consent,
        'fotos': _photos_of(message),
        'message_id': str(message.get('Message-ID', '') or '').strip()[:255],
    }


def import_mail(raw: bytes, config: BeitragsConfig | None = None) -> Beitrag | None:
    """Turn one mail into a post; None if it is ignored."""
    from . import workflow
    from django.db import transaction

    config = config or BeitragsConfig.get_config()
    try:
        data = parse(raw, config)
    except Ignored as reason:
        logger.info('Mail for posts ignored: %s', reason)
        return None
    if data['message_id'] and Beitrag.objects.filter(mail_message_id=data['message_id']).exists():
        logger.info('Mail %s was imported before', data['message_id'])
        return None
    with transaction.atomic():
        beitrag = Beitrag.objects.create(
            titel=data['titel'], text=data['text'], link=data['link'], thema=data['thema'],
            einwilligung=data['einwilligung'], created_by=data['user'],
            mail_message_id=data['message_id'])
        for position, upload in enumerate(data['fotos']):
            BeitragFoto.objects.create(beitrag=beitrag, bild=upload, position=position)
        workflow.ensure_ziele(beitrag)
        submitted = not data['fotos'] or data['einwilligung']
        if submitted:
            workflow.submit(beitrag)
    from .notify import tell_author_received
    tell_author_received(beitrag, submitted)
    return beitrag


def fetch(config: BeitragsConfig | None = None) -> dict:
    """Read unseen mails from the mailbox; every mail is marked as read."""
    config = config or BeitragsConfig.get_config()
    if not config.is_mail_configured():
        return {'status': 'off'}
    created = ignored = 0
    client = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    try:
        client.login(config.imap_user, config.imap_password)
        client.select(config.imap_folder or 'INBOX')
        _status, data = client.search(None, 'UNSEEN')
        for number in (data[0] or b'').split():
            _status, parts = client.fetch(number, '(RFC822)')
            raw = next((p[1] for p in parts if isinstance(p, tuple)), b'')
            try:
                beitrag = import_mail(raw, config)
            except Exception:
                logger.exception('Mail %s for posts could not be imported', number)
                beitrag = None
            client.store(number, '+FLAGS', '\\Seen')
            if beitrag is None:
                ignored += 1
            else:
                created += 1
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return {'created': created, 'ignored': ignored}


def check(config: BeitragsConfig) -> int:
    """Log in and return the number of unseen mails, to test the settings."""
    client = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    try:
        client.login(config.imap_user, config.imap_password)
        client.select(config.imap_folder or 'INBOX', readonly=True)
        _status, data = client.search(None, 'UNSEEN')
        return len((data[0] or b'').split())
    finally:
        try:
            client.logout()
        except Exception:
            pass
