"""Instagram Graph API client for publishing reels.

Follows the content publishing flow of the Instagram Platform:

1. ``POST /<IG_ID>/media`` with ``media_type=REELS`` creates a container;
   Instagram fetches the video from ``video_url`` (a public URL).
2. ``GET /<CONTAINER_ID>?fields=status_code`` until ``FINISHED``.
3. ``POST /<IG_ID>/media_publish`` with ``creation_id`` publishes it.

Instagram Login tokens (graph.instagram.com) last 60 days and are renewed
with ``GET /refresh_access_token`` once they are at least 24 hours old.
"""

import json
import logging
import requests


logger = logging.getLogger('django')

TIMEOUT = 30


class InstagramError(Exception):
    """A call to the Instagram API failed; the message is readable for staff."""


def _base_url(config) -> str:
    host = config.instagram_api_host or 'graph.instagram.com'
    version = (config.instagram_api_version or '').strip().strip('/')
    return f'https://{host}/{version}' if version else f'https://{host}'


def _call(method: str, url: str, config, params=None) -> dict:
    params = dict(params or {})
    params['access_token'] = config.instagram_access_token
    try:
        if method == 'POST':
            response = requests.post(url, data=params, timeout=TIMEOUT)
        else:
            response = requests.get(url, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise InstagramError(f'Instagram is not reachable: {exc}') from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400 or 'error' in data:
        error = data.get('error') or {}
        message = (
            error.get('error_user_msg') or error.get('message')
            or response.text[:300] or f'HTTP {response.status_code}'
        )
        code = error.get('code')
        raise InstagramError(f'{message} (code {code})' if code else message)
    return data


def create_reel_container(config, *, video_url: str, caption: str = '',
                          collaborators=None, share_to_feed: bool = True,
                          thumb_offset_ms: int = 0) -> str:
    """Create a REELS media container and return its ID."""
    params = {
        'media_type': 'REELS',
        'video_url': video_url,
        'caption': caption or '',
        'share_to_feed': 'true' if share_to_feed else 'false',
    }
    if thumb_offset_ms:
        params['thumb_offset'] = str(int(thumb_offset_ms))
    if collaborators:
        params['collaborators'] = json.dumps(list(collaborators))
    data = _call('POST', f'{_base_url(config)}/{config.instagram_account_id}/media', config, params)
    container_id = str(data.get('id') or '')
    if not container_id:
        raise InstagramError('Instagram returned no container ID.')
    return container_id


def container_status(config, container_id: str) -> tuple[str, str]:
    """Return ``(status_code, status)``; status holds the error text if any."""
    data = _call('GET', f'{_base_url(config)}/{container_id}', config,
                 {'fields': 'status_code,status'})
    return str(data.get('status_code') or ''), str(data.get('status') or '')


def publish_container(config, container_id: str) -> str:
    """Publish a finished container and return the media ID."""
    data = _call('POST', f'{_base_url(config)}/{config.instagram_account_id}/media_publish',
                 config, {'creation_id': container_id})
    media_id = str(data.get('id') or '')
    if not media_id:
        raise InstagramError('Instagram returned no media ID.')
    return media_id


def media_permalink(config, media_id: str) -> str:
    """Return the public link of a published post, or '' if unknown."""
    try:
        data = _call('GET', f'{_base_url(config)}/{media_id}', config, {'fields': 'permalink'})
    except InstagramError:
        logger.warning('Could not read the permalink of Instagram media %s', media_id)
        return ''
    return str(data.get('permalink') or '')


def account_info(config) -> dict:
    """Return username and remaining publishing quota of the account."""
    base = _base_url(config)
    account = _call('GET', f'{base}/{config.instagram_account_id}', config,
                    {'fields': 'username'})
    try:
        limit = _call('GET', f'{base}/{config.instagram_account_id}/content_publishing_limit',
                      config, {'fields': 'quota_usage,config'})
        entry = (limit.get('data') or [{}])[0]
    except InstagramError:
        entry = {}
    return {
        'username': account.get('username', ''),
        'quota_usage': entry.get('quota_usage'),
        'quota_total': (entry.get('config') or {}).get('quota_total'),
    }


def refresh_token(config) -> tuple[str, int]:
    """Renew an Instagram Login token; return ``(token, expires_in_seconds)``."""
    if config.instagram_api_host != 'graph.instagram.com':
        raise InstagramError('Only Instagram Login tokens can be renewed this way.')
    data = _call('GET', 'https://graph.instagram.com/refresh_access_token', config,
                 {'grant_type': 'ig_refresh_token'})
    token = str(data.get('access_token') or '')
    if not token:
        raise InstagramError('Instagram returned no new token.')
    return token, int(data.get('expires_in') or 0)
