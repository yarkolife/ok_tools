"""Thumbnail generation and caching for inventory item photos.

Source photos live in a mounted folder and may be large (multi-megabyte camera
shots). To keep the admin gallery fast and visually uniform we generate small
cached JPEG thumbnails and serve those in the gallery, while the full-size
original stays one click away.

Where thumbnails are stored is configurable (``InventoryImageConfig``):

* ``MEDIA_ROOT/inventory_thumbnails/`` -- an app-owned cache that never touches
  the source and works even with a read-only mount (default).
* ``<base>/<inventory_number>/.thumbnails/`` -- next to the originals, so they
  travel with the photos. Requires a writable mount; falls back to the
  MEDIA_ROOT cache when the beside-location cannot be written.
"""

from django.conf import settings
from pathlib import Path
import hashlib
import logging


logger = logging.getLogger('django')

# Longest edge of a generated thumbnail (px). 400 keeps ~150px tiles crisp on
# high-DPI screens while staying tiny in bytes.
THUMBNAIL_MAX_SIZE = (400, 400)
MEDIA_THUMBNAIL_SUBDIR = 'inventory_thumbnails'
BESIDE_THUMBNAIL_SUBDIR = '.thumbnails'


def media_thumbnail_root() -> Path:
    """Return the absolute app-owned thumbnail cache directory."""
    root = Path(settings.MEDIA_ROOT)
    if not root.is_absolute():
        root = Path(settings.BASE_DIR) / root
    return root / MEDIA_THUMBNAIL_SUBDIR


def _media_thumbnail_path(image) -> Path:
    """Return the MEDIA_ROOT cache path for ``image`` (globally unique)."""
    digest = hashlib.md5(image.relative_path.encode('utf-8')).hexdigest()
    return media_thumbnail_root() / f'{image.item_id}_{digest}.jpg'


def _beside_thumbnail_path(image, base_dir: Path) -> Path:
    """Return the beside-originals thumbnail path for ``image``."""
    rel = Path(image.relative_path)
    digest = hashlib.md5(rel.name.encode('utf-8')).hexdigest()
    return base_dir / rel.parent / BESIDE_THUMBNAIL_SUBDIR / f'{digest}.jpg'


def _candidate_paths(image):
    """Yield every location a thumbnail for ``image`` might live in.

    Used for cleanup so we never leave orphans behind regardless of which mode
    produced the thumbnail.
    """
    from .models import InventoryImageConfig
    config = InventoryImageConfig.get_config()
    base_dir = config.get_base_dir()
    if base_dir is not None:
        yield _beside_thumbnail_path(image, base_dir)
    yield _media_thumbnail_path(image)


def generate_thumbnail(source: Path, target: Path) -> bool:
    """Generate a JPEG thumbnail from ``source`` into ``target``.

    Returns ``True`` on success. Fails softly (returns ``False``) if Pillow is
    unavailable, the target is not writable, or the image cannot be processed.
    """
    try:
        from PIL import Image
        from PIL import ImageOps
    except ImportError:
        logger.warning('Pillow is not installed; cannot generate thumbnails.')
        return False

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            # Respect EXIF orientation, then flatten to RGB for JPEG output.
            img = ImageOps.exif_transpose(img)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img.thumbnail(THUMBNAIL_MAX_SIZE)
            img.save(target, format='JPEG', quality=85, optimize=True)
        return True
    except Exception as exc:
        logger.warning('Failed to build thumbnail for %s: %s', source, exc)
        return False


def _is_fresh(target: Path, source: Path) -> bool:
    """Return True if ``target`` exists and is at least as new as ``source``."""
    try:
        return (
            target.is_file()
            and target.stat().st_mtime >= source.stat().st_mtime
        )
    except OSError:
        return False


def ensure_thumbnail(image) -> Path | None:
    """Return an up-to-date thumbnail path for ``image`` or ``None``.

    Honours the configured storage mode, regenerates when missing or stale,
    and falls back to the MEDIA_ROOT cache if the beside-originals location is
    not writable. Returns ``None`` when the source is unavailable or all
    generation attempts fail.
    """
    from .models import InventoryImageConfig
    config = InventoryImageConfig.get_config()

    source = image.abs_path()
    if source is None or not source.is_file():
        return None

    base_dir = config.get_base_dir()
    targets = []
    if getattr(config, 'thumbnails_beside_originals', False) and base_dir:
        targets.append(_beside_thumbnail_path(image, base_dir))
    targets.append(_media_thumbnail_path(image))

    for target in targets:
        if _is_fresh(target, source):
            return target
        if generate_thumbnail(source, target):
            return target
    return None


def delete_thumbnail(image) -> None:
    """Remove any cached thumbnails for ``image`` (both possible locations)."""
    for path in _candidate_paths(image):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
