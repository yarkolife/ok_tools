"""Persisting generated covers to the hand-off directory."""

import logging
import os
import shutil

from PIL import Image, ImageDraw

logger = logging.getLogger('django')


def save_cover(image, number: int, output_dir: str) -> str:
    """Write the cover as ``{number}_cover.jpg`` into ``output_dir``.

    The filename matches the pattern the austausch export looks for
    (``{number}_*.jpg``) so the export picks it up automatically.

    Returns:
        The absolute path of the written file.

    Raises:
        ValueError: if ``output_dir`` is not configured.
    """
    if not output_dir:
        raise ValueError(
            'No cover output directory configured (MediaFilesConfig.cover_output_dir '
            'or austausch thumbnail_storage_path).')

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f'{number}_cover.jpg')
    image.save(path, format='JPEG', quality=88, optimize=True)
    logger.info('Cover: wrote %s', path)
    return path


def candidates_dir(output_dir: str, number: int) -> str:
    """Return (and create) the per-number candidate directory.

    Candidates live in a ``candidates/{number}`` subfolder so the austausch
    export (which scans the top-level output dir for ``{number}_*``) never
    picks them up before an operator has chosen one.
    """
    path = os.path.join(output_dir, 'candidates', str(number))
    os.makedirs(path, exist_ok=True)
    return path


def frames_dir(output_dir: str, number: int) -> str:
    """Return (and create) the per-number extracted-frames directory."""
    path = os.path.join(output_dir, 'candidates', str(number), 'frames')
    os.makedirs(path, exist_ok=True)
    return path


def save_frames(images, number: int, output_dir: str) -> list:
    """Write extracted frames as ``f1.jpg…fN.jpg``; return their paths."""
    target = frames_dir(output_dir, number)
    # Clear stale frames so indices stay consistent across runs.
    for old in os.listdir(target):
        if old.startswith('f') and old.endswith('.jpg'):
            try:
                os.remove(os.path.join(target, old))
            except OSError:
                pass
    paths = []
    for idx, image in enumerate(images, start=1):
        path = os.path.join(target, f'f{idx}.jpg')
        image.convert('RGB').save(path, format='JPEG', quality=85)
        paths.append(path)
    return paths


def save_manifest(number: int, output_dir: str, mapping: dict) -> None:
    """Persist a variant-index -> overlay-name mapping for the gallery."""
    import json
    path = os.path.join(candidates_dir(output_dir, number), 'manifest.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(mapping, fh, ensure_ascii=False)


def load_manifest(number: int, output_dir: str) -> dict:
    """Load the variant-index -> overlay-name mapping (empty if missing)."""
    import json
    path = os.path.join(candidates_dir(output_dir, number), 'manifest.json')
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_variants(images, number: int, output_dir: str) -> list:
    """Write variant images as ``v1.jpg…vN.jpg``; return their paths."""
    target = candidates_dir(output_dir, number)
    paths = []
    for idx, image in enumerate(images, start=1):
        path = os.path.join(target, f'v{idx}.jpg')
        image.save(path, format='JPEG', quality=88, optimize=True)
        paths.append(path)
    logger.info('Cover: wrote %d variants for %s', len(paths), number)
    return paths


def build_contact_sheet(images, number: int, output_dir: str, columns=3) -> str:
    """Build a labelled grid of all variants for quick visual review."""
    target = candidates_dir(output_dir, number)
    cell_w, cell_h, pad, label_h = 400, 225, 12, 26
    count = len(images)
    cols = min(columns, count) or 1
    rows = (count + cols - 1) // cols
    sheet_w = cols * cell_w + (cols + 1) * pad
    sheet_h = rows * (cell_h + label_h) + (rows + 1) * pad
    sheet = Image.new('RGB', (sheet_w, sheet_h), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)

    for idx, image in enumerate(images):
        r, c = divmod(idx, cols)
        x = pad + c * (cell_w + pad)
        y = pad + r * (cell_h + label_h + pad)
        thumb = image.convert('RGB').resize((cell_w, cell_h), Image.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.text((x + 6, y + cell_h + 4), f'v{idx + 1}', fill=(255, 255, 255))

    path = os.path.join(target, 'contact.jpg')
    sheet.save(path, format='JPEG', quality=88)
    logger.info('Cover: wrote contact sheet %s', path)
    return path


def promote_variant(number: int, variant: int, output_dir: str) -> str:
    """Copy candidate ``vN`` to the canonical ``{number}_cover.jpg``.

    Returns the canonical path. Raises FileNotFoundError if the variant is
    missing.
    """
    src = os.path.join(candidates_dir(output_dir, number), f'v{variant}.jpg')
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    os.makedirs(output_dir, exist_ok=True)
    dst = os.path.join(output_dir, f'{number}_cover.jpg')
    shutil.copyfile(src, dst)
    logger.info('Cover: promoted v%d -> %s', variant, dst)
    return dst
