"""Mastodon: upload photos, post a status, delete it again.

Uses the REST API of the instance with an access token of the channel's
account (Preferences → Development → New application, scopes
``write:statuses`` and ``write:media``; ``read:accounts`` for the test).
"""

import logging
import re
import requests
import time


logger = logging.getLogger('django')

TIMEOUT = 60
# Mastodon counts every link as 23 characters, whatever its length.
LINK_LENGTH = 23
# Large photos are processed after the upload (HTTP 202); wait for them.
MEDIA_CHECKS = 20
MEDIA_CHECK_PAUSE = 2


class MastodonError(Exception):
    """The instance refused the request or could not be reached."""


def length(text: str) -> int:
    """The length Mastodon counts: links as 23 characters."""
    return len(re.sub(r'https?://\S+', 'x' * LINK_LENGTH, text or ''))


def _url(config, path: str) -> str:
    return config.mastodon_url.rstrip('/') + path


def _request(config, method: str, path: str, ok=(200,), **kwargs):
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = f'Bearer {config.mastodon_token}'
    try:
        response = requests.request(method, _url(config, path), headers=headers,
                                    timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise MastodonError(f'{config.mastodon_url} is not reachable: {exc}') from exc
    if response.status_code not in ok:
        try:
            message = response.json().get('error') or response.text
        except ValueError:
            message = response.text
        raise MastodonError(f'HTTP {response.status_code}: {str(message)[:300]}')
    return response


def check(config) -> dict:
    """The account of the token (``acct``, ``url``)."""
    return _request(config, 'GET', '/api/v1/accounts/verify_credentials').json()


def limits(config) -> tuple[int, int]:
    """Characters per post and photos per post allowed by the instance."""
    data = _request(config, 'GET', '/api/v2/instance').json()
    statuses = (data.get('configuration') or {}).get('statuses') or {}
    return int(statuses.get('max_characters') or 500), int(statuses.get('max_media_attachments') or 4)


def upload_media(config, filename: str, content: bytes, description: str = '') -> str:
    """Upload a photo; return its media id once the instance has processed it."""
    response = _request(config, 'POST', '/api/v2/media', ok=(200, 202),
                        files={'file': (filename, content, 'image/jpeg')},
                        data={'description': description[:1500]})
    media = response.json()
    for _attempt in range(MEDIA_CHECKS):
        if response.status_code == 200 and media.get('url'):
            return str(media['id'])
        time.sleep(MEDIA_CHECK_PAUSE)
        response = _request(config, 'GET', f'/api/v1/media/{media["id"]}', ok=(200, 206))
        media = response.json()
    raise MastodonError('Mastodon is still processing the photos; publish the post again later.')


def post_status(config, text: str, media_ids=(), visibility: str = 'public', key: str = '') -> dict:
    """Publish the status; return ``{'id', 'url'}``.

    ``key`` makes a retry within an hour return the same status instead of
    posting it twice.
    """
    headers = {'Idempotency-Key': key} if key else {}
    data = _request(config, 'POST', '/api/v1/statuses', headers=headers, json={
        'status': text, 'media_ids': list(media_ids), 'visibility': visibility,
    }).json()
    return {'id': str(data['id']), 'url': data.get('url') or ''}


def delete_status(config, status_id: str) -> None:
    """Delete the status; one that is gone already counts as deleted."""
    _request(config, 'DELETE', f'/api/v1/statuses/{status_id}', ok=(200, 404))
