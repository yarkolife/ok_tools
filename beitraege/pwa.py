"""The post pages as an app on the phone (PWA).

- ``manifest.webmanifest``: name, icon, colours; start page "Meine Beiträge",
  scope ``/beitraege/`` (the app never shows other OK-Tools pages as its own).
  On Android it also registers OK-Tools as a share target: photos shared
  from the gallery open "Neuer Beitrag" with the photos filled in.
- ``sw.js``: the service worker. It caches nothing private: only the
  offline page and the icon. A share from the gallery (POST to ``teilen/``)
  is kept in the browser's cache until "Neuer Beitrag" takes it.
- ``icon-<size>.png``: the small logo of the organisation on white, or its
  initials on the brand colour.
- ``teilen/``: answers a share that reached the server because the service
  worker was not active yet; it only redirects to "Neuer Beitrag".
"""

from django.conf import settings
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from io import BytesIO
import logging


logger = logging.getLogger('django')

ICON_SIZES = (180, 192, 512)
SW_VERSION = '1'
_ICONS: dict = {}


def _organization():
    from registration.models import OrganizationConfig

    try:
        return OrganizationConfig.get_config()
    except Exception:  # pragma: no cover - table missing during setup
        return None


def _app_name() -> str:
    org = _organization()
    short = (getattr(org, 'short_name', '') or 'OK-Tools').strip()
    return f'{_("Posts")} – {short}'


@cache_control(max_age=3600)
def manifest(request):
    """Web app manifest; Android needs it to install, iOS reads name and icon."""
    icons = [{'src': reverse('beitraege:icon', args=[size]), 'sizes': f'{size}x{size}',
              'type': 'image/png', 'purpose': 'any'} for size in (192, 512)]
    icons.append({'src': reverse('beitraege:icon', args=[512]), 'sizes': '512x512',
                  'type': 'image/png', 'purpose': 'maskable'})
    data = {
        'id': reverse('beitraege:meine'),
        'name': _app_name(),
        'short_name': _('Posts'),
        'description': _('Write posts with photos and approve them on the phone.'),
        'lang': 'de',
        'start_url': reverse('beitraege:meine') + '?app=1',
        'scope': reverse('beitraege:meine'),
        'display': 'standalone',
        'background_color': '#f4f6f8',
        'theme_color': '#1d5d7a',  # the --brand colour of the post pages
        'icons': icons,
        'shortcuts': [{'name': _('New post'), 'url': reverse('beitraege:neu')}],
        'share_target': {
            'action': reverse('beitraege:teilen'),
            'method': 'POST',
            'enctype': 'multipart/form-data',
            'params': {'title': 'title', 'text': 'text', 'url': 'url',
                       'files': [{'name': 'fotos', 'accept': ['image/*', '.heic', '.heif']}]},
        },
    }
    return JsonResponse(data, content_type='application/manifest+json',
                        json_dumps_params={'ensure_ascii': False})


def service_worker(request):
    response = render(request, 'beitraege/sw.js', {
        'version': SW_VERSION,
        'offline_url': reverse('beitraege:offline'),
        'share_url': reverse('beitraege:teilen'),
        'new_url': reverse('beitraege:neu'),
        'icon_url': reverse('beitraege:icon', args=[192]),
    }, content_type='text/javascript; charset=utf-8')
    # Served below /beitraege/, so its scope is /beitraege/ without extra headers.
    response['Cache-Control'] = 'no-cache'
    return response


def offline(request):
    """Shown by the service worker when the phone has no connection."""
    return render(request, 'beitraege/offline.html', {'title': _('No connection'), 'state': 'invalid'})


@csrf_exempt
def teilen(request):
    """A share the service worker did not catch: nothing is stored, go to the form."""
    return redirect('beitraege:neu')


def _initials(name: str) -> str:
    """"OK Merseburg" → "OK", "Offener Kanal Magdeburg" → "OK"."""
    words = [w for w in name.replace('-', ' ').split() if w[:1].isalnum()]
    if words and len(words[0]) <= 3 and words[0].isupper():
        return words[0]
    letters = ''.join(w[0] for w in words[:2]).upper()
    return letters or 'OK'


def _render_icon(size: int) -> bytes:
    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageFont

    org = _organization()
    logo = getattr(org, 'logo_small', None)
    canvas = None
    if logo:
        try:
            with logo.open('rb') as handle:
                picture = Image.open(handle)
                picture.load()
            picture = picture.convert('RGBA')
            canvas = Image.new('RGBA', (size, size), 'white')
            # Maskable icons are cut to a circle: keep the logo inside 70 %.
            inner = int(size * 0.7)
            picture.thumbnail((inner, inner), Image.LANCZOS)
            canvas.alpha_composite(picture, ((size - picture.width) // 2, (size - picture.height) // 2))
        except Exception:  # SVG or broken file: fall back to the initials
            logger.info('Small logo cannot be used as app icon', exc_info=True)
            canvas = None
    if canvas is None:
        canvas = Image.new('RGBA', (size, size), settings.BRAND_COLOR or '#1d5d7a')
        draw = ImageDraw.Draw(canvas)
        text = _initials(getattr(org, 'short_name', '') or 'OK')
        try:
            font = ImageFont.load_default(size=int(size * 0.38))
        except TypeError:  # pragma: no cover - Pillow < 10.1
            font = ImageFont.load_default()
        draw.text((size / 2, size / 2), text, fill='white', font=font, anchor='mm')
    output = BytesIO()
    canvas.convert('RGB').save(output, 'PNG', optimize=True)
    return output.getvalue()


@cache_control(max_age=86400)
def icon(request, size):
    if size not in ICON_SIZES:
        size = 192
    org = _organization()
    key = (size, str(getattr(getattr(org, 'logo_small', None), 'name', '') or ''),
           getattr(org, 'short_name', ''), settings.BRAND_COLOR)
    if key not in _ICONS:
        _ICONS[key] = _render_icon(size)
    return HttpResponse(_ICONS[key], content_type='image/png')
