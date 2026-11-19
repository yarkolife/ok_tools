"""Facebook Pages client for publishing a reel on the channel's page.

The Instagram API cannot share a reel to Facebook (the app's "also share to
Facebook" switch does not apply to API posts), so the reel is published a
second time through the Reels Publishing API of the page:

1. ``POST /<PAGE_ID>/video_reels`` with ``upload_phase=start`` returns a
   video ID.
2. ``POST https://rupload.facebook.com/video-upload/<version>/<VIDEO_ID>``
   with the header ``file_url``: Facebook downloads the video itself.
3. ``POST /<PAGE_ID>/video_reels`` with ``upload_phase=finish`` and
   ``video_state=PUBLISHED`` publishes it with the description.
4. ``GET /<VIDEO_ID>?fields=status,permalink_url`` until it is published.

Every call uses the page access token, which is read from the system user
token stored for Instagram (it needs ``pages_manage_posts``).
"""

from .instagram import InstagramError
import logging
import requests


logger = logging.getLogger('django')

TIMEOUT = 30
# The upload call only answers after Facebook has downloaded the reel from
# our server; that takes longer than an ordinary API call.
UPLOAD_TIMEOUT = 300
GRAPH_HOST = 'graph.facebook.com'
UPLOAD_HOST = 'rupload.facebook.com'


class FacebookError(InstagramError):
    """A call to the Facebook API failed; the message is readable for staff."""


def _version(config) -> str:
    return (config.instagram_api_version or '').strip().strip('/') or 'v27.0'


def _graph(config) -> str:
    return f'https://{GRAPH_HOST}/{_version(config)}'


def _result(response) -> dict:
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400 or (isinstance(data, dict) and 'error' in data):
        error = (data.get('error') if isinstance(data, dict) else None) or {}
        if isinstance(error, str):
            error = {'message': error}
        message = (
            error.get('error_user_msg') or error.get('message')
            or response.text[:300] or f'HTTP {response.status_code}'
        )
        code = error.get('code')
        raise FacebookError(f'{message} (code {code})' if code else message)
    return data if isinstance(data, dict) else {}


def _request(method: str, url: str, *, params=None, headers=None, files=None,
             timeout=TIMEOUT) -> dict:
    try:
        if method == 'POST':
            response = requests.post(url, data=params or {}, headers=headers, files=files,
                                     timeout=timeout)
        else:
            response = requests.get(url, params=params or {}, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise FacebookError(f'Facebook is not reachable: {exc}') from exc
    return _result(response)


def page_token(config) -> str:
    """Return the access token of the page, read with the stored token."""
    data = _request('GET', f'{_graph(config)}/{config.facebook_page_id}', params={
        'fields': 'access_token', 'access_token': config.instagram_access_token})
    token = str(data.get('access_token') or '')
    if not token:
        raise FacebookError(
            'No access to the Facebook page: the token needs pages_manage_posts '
            'and the page must be assigned to it.')
    return token


def page_info(config) -> dict:
    """Return name and link of the page, to test the connection."""
    token = page_token(config)
    data = _request('GET', f'{_graph(config)}/{config.facebook_page_id}', params={
        'fields': 'name,link', 'access_token': token})
    return {'name': data.get('name', ''), 'link': data.get('link', '')}


def publish_reel(config, *, video_url: str, description: str = '', started=None) -> str:
    """Upload a reel from its public URL and publish it; return the video ID.

    ``started(video_id)`` is called as soon as Facebook has assigned the ID,
    so a later failure can still be traced to that video.
    """
    token = page_token(config)
    reels = f'{_graph(config)}/{config.facebook_page_id}/video_reels'
    session = _request('POST', reels, params={'upload_phase': 'start', 'access_token': token})
    video_id = str(session.get('video_id') or '')
    if not video_id:
        raise FacebookError('Facebook returned no video ID.')
    if started is not None:
        started(video_id)
    uploaded = _request(
        'POST', f'https://{UPLOAD_HOST}/video-upload/{_version(config)}/{video_id}',
        headers={'Authorization': f'OAuth {token}', 'file_url': video_url},
        timeout=UPLOAD_TIMEOUT)
    if not uploaded.get('success'):
        raise FacebookError('Facebook did not accept the video upload.')
    finished = _request('POST', reels, params={
        'upload_phase': 'finish',
        'video_id': video_id,
        'video_state': 'PUBLISHED',
        'description': description or '',
        'access_token': token,
    })
    if not finished.get('success', True):
        raise FacebookError('Facebook did not publish the reel.')
    return video_id


def set_cover(config, video_id: str, image: bytes) -> None:
    """Upload a JPEG as the preferred cover of a published reel."""
    token = page_token(config)
    data = _request('POST', f'{_graph(config)}/{video_id}/thumbnails',
                    params={'is_preferred': 'true', 'access_token': token},
                    files={'source': ('cover.jpg', image, 'image/jpeg')})
    if not data.get('success', True):
        raise FacebookError('Facebook did not accept the cover.')


def reel_status(config, video_id: str) -> tuple[str, str]:
    """Return ``(state, permalink)``; state is ``published``, ``error`` or ``processing``.

    ``permalink`` is the full public link once Facebook knows it.
    """
    token = page_token(config)
    data = _request('GET', f'{_graph(config)}/{video_id}', params={
        'fields': 'status,permalink_url', 'access_token': token})
    status = data.get('status') or {}
    phases = [status.get(name) or {} for name in
              ('uploading_phase', 'processing_phase', 'publishing_phase')]
    if status.get('video_status') == 'error' or any(p.get('status') == 'error' for p in phases):
        errors = [e.get('message', '') for p in phases for e in (p.get('errors') or [])]
        return 'error', '; '.join(filter(None, errors))
    link = str(data.get('permalink_url') or '')
    if link.startswith('/'):
        link = f'https://www.facebook.com{link}'
    publishing = status.get('publishing_phase') or {}
    if publishing.get('status') == 'complete' or status.get('video_status') == 'ready':
        return 'published', link
    return 'processing', link
