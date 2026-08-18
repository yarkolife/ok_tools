"""
Media types accepted for license uploads.

A screen board (Bildschirmtafel) is a still image, therefore uploads for such
licenses also accept photos. Everything else stays video-only.

User-visible strings must be English and wrapped for translation.
"""

from __future__ import annotations
from django.utils.translation import gettext_lazy as _


VIDEO_EXTENSIONS: tuple[str, ...] = ('mp4', 'mov', 'avi', 'mkv', 'webm')
IMAGE_EXTENSIONS: tuple[str, ...] = ('jpg', 'jpeg', 'png', 'webp')

# Photos are small, so a much tighter limit than the 20 GB used for videos.
MAX_IMAGE_SIZE_MB = 50


def file_extension(filename: str | None) -> str:
    """Return the lowercase extension of ``filename`` without the dot."""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[-1].lower()


def is_image_filename(filename: str | None) -> bool:
    """Whether ``filename`` is one of the supported image formats."""
    return file_extension(filename) in IMAGE_EXTENSIONS


def is_video_filename(filename: str | None) -> bool:
    """Whether ``filename`` is one of the supported video formats."""
    return file_extension(filename) in VIDEO_EXTENSIONS


def allowed_extensions(is_screen_board: bool) -> tuple[str, ...]:
    """Return the extensions a license accepts for its upload."""
    if is_screen_board:
        return IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
    return VIDEO_EXTENSIONS


def is_allowed_filename(filename: str | None, is_screen_board: bool) -> bool:
    """Whether ``filename`` may be uploaded for this kind of license."""
    return file_extension(filename) in allowed_extensions(is_screen_board)


def unsupported_format_message(is_screen_board: bool) -> str:
    """Return the error message listing the accepted formats."""
    return _('Invalid file format. Supported formats: %(formats)s.') % {
        'formats': ', '.join(allowed_extensions(is_screen_board))
    }
