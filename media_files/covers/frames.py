"""Smart background-frame selection from a local video file (on NAS).

Builds on :func:`media_files.utils.generate_thumbnail` (local ffmpeg capture):
samples several frames across the video and picks the most "interesting" one
(well-exposed, good contrast), then cover-fits it to the target size.
"""

import logging
import os
import tempfile

from PIL import Image, ImageStat

from media_files.utils import generate_thumbnail

logger = logging.getLogger('django')

# Where in the video to sample candidate frames (fraction of duration).
SAMPLE_FRACTIONS = (0.10, 0.35, 0.60, 0.85)
# If duration is unknown, probe these fixed timestamps (seconds) instead.
FALLBACK_TIMESTAMPS = (5, 20, 45, 90)


def _seconds_to_ts(seconds: float) -> str:
    """Format seconds as ffmpeg HH:MM:SS timestamp."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def _sample_timestamps(duration_seconds) -> list:
    """Return a list of HH:MM:SS timestamps to sample."""
    if duration_seconds and duration_seconds > 1:
        return [_seconds_to_ts(duration_seconds * f) for f in SAMPLE_FRACTIONS]
    return [_seconds_to_ts(t) for t in FALLBACK_TIMESTAMPS]


def _score_frame(image: Image.Image) -> float:
    """Score a frame: prefer mid-range brightness with high contrast.

    Penalizes near-black / blown-out frames (intros, fades), rewards detail.
    """
    gray = image.convert('L')
    stat = ImageStat.Stat(gray)
    mean = stat.mean[0]
    stddev = stat.stddev[0]
    # Brightness sweet spot around 110 (0..255); fall off towards extremes.
    brightness_score = max(0.0, 1.0 - abs(mean - 110) / 110.0)
    # Contrast: more variation is better, normalized.
    contrast_score = min(stddev / 60.0, 1.0)
    return brightness_score * 0.5 + contrast_score * 0.5


def _cover_fit(image: Image.Image, size) -> Image.Image:
    """Scale to cover the target size, then center-crop (no distortion)."""
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def extract_background(video_path: str, duration_seconds=None, size=(1280, 720)):
    """Extract the best background frame from a local video file.

    Args:
        video_path: Absolute path to the video file (NAS/local).
        duration_seconds: Video duration in seconds (for sampling); optional.
        size: Target (width, height).

    Returns:
        A cover-fitted ``PIL.Image`` in RGB, or ``None`` if extraction failed
        (e.g. the file is not accessible).
    """
    if not video_path or not os.path.isfile(video_path):
        logger.warning('Cover: video not accessible for frame extraction: %s', video_path)
        return None

    timestamps = _sample_timestamps(duration_seconds)
    best_image = None
    best_score = -1.0

    with tempfile.TemporaryDirectory(prefix='cover_frames_') as tmpdir:
        for idx, ts in enumerate(timestamps):
            # PNG (not JPG): ffmpeg's mjpeg encoder rejects full-range YUV
            # ("Non full-range YUV is non-standard"); png handles any frame.
            out_path = os.path.join(tmpdir, f'frame_{idx}.png')
            if not generate_thumbnail(video_path, out_path, timestamp=ts):
                continue
            try:
                with Image.open(out_path) as img:
                    img = img.convert('RGB')
                    score = _score_frame(img)
                    if score > best_score:
                        best_score = score
                        best_image = img.copy()
            except Exception:
                logger.exception('Cover: failed to read sampled frame %s', out_path)

    if best_image is None:
        logger.warning('Cover: no usable frame extracted from %s', video_path)
        return None

    return _cover_fit(best_image, size)


def extract_frames(video_path, duration_seconds=None, count=6, size=(1280, 720)):
    """Extract ``count`` evenly spaced, cover-fitted frames across the video.

    Returns a list of RGB ``PIL.Image`` (may be shorter than ``count`` if some
    extractions fail); empty if the file is inaccessible.
    """
    if not video_path or not os.path.isfile(video_path):
        return []

    if duration_seconds and duration_seconds > 1:
        timestamps = [_seconds_to_ts(duration_seconds * ((i + 0.5) / count))
                      for i in range(count)]
    else:
        timestamps = [_seconds_to_ts(5 + i * 15) for i in range(count)]

    images = []
    with tempfile.TemporaryDirectory(prefix='cover_strip_') as tmpdir:
        for idx, ts in enumerate(timestamps):
            out_path = os.path.join(tmpdir, f'f{idx}.png')
            if not generate_thumbnail(video_path, out_path, timestamp=ts):
                continue
            try:
                with Image.open(out_path) as img:
                    images.append(_cover_fit(img.convert('RGB'), size))
            except Exception:
                logger.exception('Cover: failed to read strip frame %s', out_path)
    return images


def best_frame(images):
    """Pick the highest-scoring frame from a list (brightness + contrast)."""
    if not images:
        return None
    return max(images, key=_score_frame)


def extract_frame_at(video_path, seconds, size=(1280, 720)):
    """Extract a single cover-fitted frame at an exact timestamp (seconds)."""
    if not video_path or not os.path.isfile(video_path):
        return None
    with tempfile.TemporaryDirectory(prefix='cover_tc_') as tmpdir:
        out_path = os.path.join(tmpdir, 'f.png')
        if not generate_thumbnail(video_path, out_path, timestamp=_seconds_to_ts(seconds)):
            return None
        try:
            with Image.open(out_path) as img:
                return _cover_fit(img.convert('RGB'), size)
        except Exception:
            logger.exception('Cover: failed to read frame at %ss', seconds)
            return None
