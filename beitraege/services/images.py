"""Photos of posts: open anything a phone sends, publish clean JPEGs.

Phones send HEIC (iPhone), JPEG with an EXIF rotation and location data.
Every rendition is turned upright, converted to RGB, stripped of all metadata
(no GPS on the internet) and saved as JPEG:

- ``instagram``: 4:5 crop (1080 x 1350), the crop moved by ``fokus_y``;
  Instagram rejects ratios taller than 4:5 and only takes JPEG.
- ``web``: at most 2048 px on the long side, used for Facebook and the
  website.
"""

from PIL import Image
from PIL import ImageOps
from io import BytesIO
import logging


logger = logging.getLogger('django')

INSTAGRAM_SIZE = (1080, 1350)
WEB_LONG_SIDE = 2048
QUALITY = 88
VARIANTS = ('instagram', 'web')

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - only without the optional package
    logger.warning('pillow-heif is not installed; HEIC photos cannot be read')


def open_upright(source) -> Image.Image:
    """Open a photo (path or file), rotate it as the camera meant, RGB."""
    image = Image.open(source)
    image = ImageOps.exif_transpose(image)
    if image.mode != 'RGB':
        background = Image.new('RGB', image.size, 'white')
        if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
            rgba = image.convert('RGBA')
            background.paste(rgba, mask=rgba.split()[-1])
            image = background
        else:
            image = image.convert('RGB')
    return image


def crop_4_5(image: Image.Image, fokus_y: int = 50) -> Image.Image:
    """Cut the image to 4:5; ``fokus_y`` (0-100) moves a vertical crop."""
    width, height = image.size
    target = 4 / 5
    if width / height > target:
        # Too wide: cut the sides, centred.
        new_width = round(height * target)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = round(width / target)
    room = height - new_height
    top = round(room * max(0, min(100, fokus_y)) / 100)
    return image.crop((0, top, width, top + new_height))


def rendition(source, variant: str, fokus_y: int = 50) -> bytes:
    """JPEG bytes of a photo for ``instagram`` or ``web``, without metadata."""
    image = open_upright(source)
    if variant == 'instagram':
        image = crop_4_5(image, fokus_y).resize(INSTAGRAM_SIZE, Image.Resampling.LANCZOS)
    elif variant == 'web':
        image.thumbnail((WEB_LONG_SIDE, WEB_LONG_SIDE), Image.Resampling.LANCZOS)
    else:
        raise ValueError(f'Unknown photo variant: {variant}')
    output = BytesIO()
    # A fresh image carries no EXIF, GPS or ICC data of the original.
    clean = Image.new('RGB', image.size)
    clean.paste(image)
    clean.save(output, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
    return output.getvalue()


ORIGINAL_LONG_SIDE = 4096


def clean_original(source) -> bytes:
    """The upload as it is kept: upright JPEG without any metadata.

    Uploads land below MEDIA_ROOT, which the web server may serve; a photo
    from a phone must never sit there with its GPS position.
    """
    image = open_upright(source)
    image.thumbnail((ORIGINAL_LONG_SIDE, ORIGINAL_LONG_SIDE), Image.Resampling.LANCZOS)
    output = BytesIO()
    clean = Image.new('RGB', image.size)
    clean.paste(image)
    clean.save(output, 'JPEG', quality=94, optimize=True)
    return output.getvalue()


def is_readable(source) -> bool:
    """True if the upload is a photo Pillow can open (JPEG, PNG, HEIC, ...)."""
    try:
        with Image.open(source) as image:
            image.verify()
        return True
    except Exception:
        return False
    finally:
        if hasattr(source, 'seek'):
            source.seek(0)
