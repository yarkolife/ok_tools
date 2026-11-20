"""Addresses of photo renditions.

Instagram and Facebook download the photos of an approved post from our
server, so from the approval on a rendition is served to anybody with its
unguessable token. Before that, previews (check page, edit page, admin) carry
an extra signature that expires, so a forwarded preview link stops working.
"""

from django.core import signing
from django.urls import reverse


PREVIEW_SALT = 'beitraege.foto.preview'
PREVIEW_MAX_AGE = 7 * 24 * 60 * 60


def preview_url(foto, variant: str) -> str:
    """Relative URL of a rendition for previews (signed, expires)."""
    signature = signing.TimestampSigner(salt=PREVIEW_SALT).sign(foto.token)
    return f"{reverse('beitraege:foto', args=[foto.token, variant])}?s={signature}"


def preview_allowed(foto, signature: str) -> bool:
    try:
        value = signing.TimestampSigner(salt=PREVIEW_SALT).unsign(signature or '', max_age=PREVIEW_MAX_AGE)
    except signing.BadSignature:
        return False
    return value == foto.token


def previews(fotos) -> list[dict]:
    """``{'foto', 'web', 'instagram'}`` preview URLs for templates."""
    return [{'foto': f, 'web': preview_url(f, 'web'), 'instagram': preview_url(f, 'instagram')}
            for f in fotos]
