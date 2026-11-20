"""WordPress REST API: upload photos and publish a post.

Authentication is HTTP Basic with an application password (WordPress 5.6+,
Users -> Profile -> Application passwords). Categories and tags are given by
name and created on the website when they do not exist yet.
"""

from html import escape
import logging
import requests


logger = logging.getLogger('django')

TIMEOUT = 60


class WordPressError(Exception):
    """A call to the WordPress REST API failed; the message is readable for staff."""


def _api(config) -> str:
    return config.wordpress_url.rstrip('/') + '/wp-json/wp/v2'


def _auth(config):
    # WordPress shows application passwords with spaces; it accepts them as they are.
    return (config.wordpress_user, config.wordpress_app_password)


def _request(config, method, path, **kwargs) -> dict | list:
    try:
        response = requests.request(method, f'{_api(config)}/{path}', auth=_auth(config),
                                    timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise WordPressError(f'The website is not reachable: {exc}') from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400:
        message = (data.get('message') if isinstance(data, dict) else '') or response.text[:300]
        raise WordPressError(f'{message} (HTTP {response.status_code})')
    return data


def check(config) -> dict:
    """Return the WordPress user, to test address and password."""
    data = _request(config, 'GET', 'users/me', params={'context': 'edit'})
    return {'name': data.get('name', ''), 'roles': data.get('roles', [])}


def upload_media(config, filename: str, content: bytes, alt: str = '') -> dict:
    """Upload a JPEG to the media library; return ``{'id', 'url'}``."""
    data = _request(config, 'POST', 'media', data=content, headers={
        'Content-Type': 'image/jpeg',
        'Content-Disposition': f'attachment; filename="{filename}"',
    })
    media_id = data.get('id')
    if not media_id:
        raise WordPressError('The website returned no media ID.')
    if alt:
        try:
            _request(config, 'POST', f'media/{media_id}', json={'alt_text': alt})
        except WordPressError:
            logger.warning('Could not set the alt text of WordPress media %s', media_id)
    return {'id': media_id, 'url': data.get('source_url', '')}


def term_ids(config, taxonomy: str, names) -> list[int]:
    """IDs of categories or tags by name; missing ones are created."""
    ids = []
    for name in [n.strip() for n in names if n and n.strip()]:
        found = _request(config, 'GET', taxonomy, params={'search': name, 'per_page': 100})
        match = next((t for t in found if str(t.get('name', '')).strip().lower() == name.lower()), None)
        if match is None:
            match = _request(config, 'POST', taxonomy, json={'name': name})
        if match.get('id'):
            ids.append(int(match['id']))
    return ids


def paragraphs(text: str) -> str:
    """Plain text to HTML paragraphs; single line breaks stay line breaks."""
    blocks = [block.strip() for block in (text or '').replace('\r\n', '\n').split('\n\n')]
    return '\n'.join(
        '<p>' + escape(block).replace('\n', '<br>') + '</p>' for block in blocks if block)


def gallery_block(media: list[dict]) -> str:
    """A core gallery block (WordPress block editor) for the uploaded photos."""
    if not media:
        return ''
    items = '\n'.join(
        f'<!-- wp:image {{"id":{m["id"]},"sizeSlug":"large","linkDestination":"media"}} -->\n'
        f'<figure class="wp-block-image size-large"><a href="{escape(m["url"])}">'
        f'<img src="{escape(m["url"])}" alt="" class="wp-image-{m["id"]}"/></a></figure>\n'
        f'<!-- /wp:image -->'
        for m in media)
    return ('<!-- wp:gallery {"linkTo":"media"} -->\n'
            '<figure class="wp-block-gallery has-nested-images columns-default is-cropped">\n'
            f'{items}\n</figure>\n<!-- /wp:gallery -->')


def create_post(config, *, title: str, content: str, featured_media: int | None = None,
                categories=(), tags=(), status: str = 'publish') -> dict:
    """Create the post; return ``{'id', 'link'}``."""
    payload = {'title': title, 'content': content, 'status': status}
    if featured_media:
        payload['featured_media'] = featured_media
    if categories:
        payload['categories'] = list(categories)
    if tags:
        payload['tags'] = list(tags)
    data = _request(config, 'POST', 'posts', json=payload)
    if not data.get('id'):
        raise WordPressError('The website returned no post ID.')
    return {'id': data['id'], 'link': data.get('link', '')}
