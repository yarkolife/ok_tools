"""Automatic video cover (thumbnail) generation.

Builds a 1280x720 cover image from a video frame plus ``License`` metadata
and channel branding, then writes it to a hand-off directory from which the
existing austausch export uploads it to Nextcloud next to the video.

Public entry point: :func:`media_files.covers.service.generate_cover`.
"""

from media_files.covers.service import (  # noqa: F401
    generate_cover,
    generate_cover_for_license,
)
