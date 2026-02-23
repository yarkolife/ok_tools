"""ffmpeg rendering pipeline: intro/main/outro + concat."""

from __future__ import annotations

import logging
import math
import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from django.utils.translation import gettext as _

from media_files.utils import extract_video_metadata

from .presets import EncodePreset, OverlayLayer, resolve_preset_asset_path
from .templates import TemplateContext, render_text_template

logger = logging.getLogger(__name__)

_DEFAULT_RENDER_TIMEOUT_SECONDS = 21600
_DEFAULT_RENDER_TIMEOUT_FACTOR = 3.0


class FfmpegError(RuntimeError):
    """Raised when ffmpeg execution fails."""


@dataclass(frozen=True)
class RenderArtifacts:
    """Paths produced by a render run."""

    output_mp4: str


def _get_env_int(name: str, default: int) -> int:
    """Read integer value from environment with safe fallback."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except (TypeError, ValueError):
        logger.warning("Invalid env %s=%r, using default %s", name, raw, default)
        return default


def _get_env_float(name: str, default: float) -> float:
    """Read float value from environment with safe fallback."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
        return value if value > 0 else default
    except (TypeError, ValueError):
        logger.warning("Invalid env %s=%r, using default %s", name, raw, default)
        return default


def _render_timeout(duration_seconds: Optional[float] = None) -> int:
    """Calculate render timeout from env and optional segment duration."""
    base_timeout = _get_env_int("OKTOOLS_RENDER_TIMEOUT_SECONDS", _DEFAULT_RENDER_TIMEOUT_SECONDS)
    factor = _get_env_float("OKTOOLS_RENDER_TIMEOUT_FACTOR", _DEFAULT_RENDER_TIMEOUT_FACTOR)

    if duration_seconds is None or duration_seconds <= 0:
        return base_timeout

    dynamic_timeout = int(math.ceil(duration_seconds * factor))
    return max(base_timeout, dynamic_timeout)


def _run(cmd: List[str], timeout: Optional[int] = None) -> None:
    """Run a subprocess and raise a detailed error on failure."""
    effective_timeout = int(timeout) if timeout is not None else _render_timeout()
    started_at = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=effective_timeout)
    elapsed = time.monotonic() - started_at
    logger.info(
        "Command finished: executable=%s timeout=%ss elapsed=%.1fs returncode=%s",
        cmd[0] if cmd else "unknown",
        effective_timeout,
        elapsed,
        result.returncode,
    )
    if result.returncode != 0:
        joined = " ".join(shlex.quote(c) for c in cmd)
        raise FfmpegError(
            _("ffmpeg failed (exit {code}). Command: {cmd}\n\nstderr:\n{stderr}").format(
                code=result.returncode,
                cmd=joined,
                stderr=(result.stderr or "").strip(),
            )
        )


def _has_audio(path: str) -> bool:
    md = extract_video_metadata(path, fast_mode=False)
    return bool(md.get("has_audio"))

def _duration_seconds(path: str) -> float:
    md = extract_video_metadata(path, fast_mode=False)
    dur = md.get("duration")
    if not dur:
        return 0.0
    return float(dur.total_seconds())


def _source_fps(path: str) -> Optional[float]:
    """Return the source video framerate as a float, or None if undetectable."""
    md = extract_video_metadata(path, fast_mode=False)
    fps = md.get("fps")
    if fps is None:
        return None
    try:
        return float(fps)
    except (TypeError, ValueError):
        return None


def _source_is_vfr(path: str) -> bool:
    """
    Return True when the source video has variable frame rate (VFR).

    VFR is detected by comparing r_frame_rate (peak/nominal) with avg_frame_rate
    (actual average measured over the file).  When they differ by more than 5 %
    the stream is considered variable and the fps filter must be kept.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,avg_frame_rate",
        "-of", "default=nw=1",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            # On failure assume VFR to stay safe
            logger.warning("ffprobe VFR check failed for %s, assuming VFR", path)
            return True

        def _parse_rate(line: str) -> Optional[float]:
            line = line.strip()
            if "=" in line:
                line = line.split("=", 1)[1]
            if "/" in line:
                parts = line.split("/")
                try:
                    num, den = float(parts[0]), float(parts[1])
                    return num / den if den != 0 else None
                except (ValueError, IndexError):
                    return None
            try:
                return float(line)
            except ValueError:
                return None

        r_rate: Optional[float] = None
        avg_rate: Optional[float] = None
        for raw_line in result.stdout.splitlines():
            if raw_line.startswith("r_frame_rate="):
                r_rate = _parse_rate(raw_line)
            elif raw_line.startswith("avg_frame_rate="):
                avg_rate = _parse_rate(raw_line)

        if r_rate is None or avg_rate is None:
            return False

        return not math.isclose(r_rate, avg_rate, rel_tol=0.01, abs_tol=0.01)

    except subprocess.TimeoutExpired:
        logger.warning("ffprobe VFR check timed out for %s, assuming VFR", path)
        return True
    except Exception as exc:
        logger.warning("ffprobe VFR check error for %s: %s, assuming VFR", path, exc)
        return True


def _is_still_image(path: str) -> bool:
    """
    Return True for still image files that should be looped as a video stream.

    FFmpeg treats single-image inputs (e.g. PNG) as a single frame unless `-loop 1`
    is used on the input. For time-based overlays (`enable=between(t,...)`) we need
    the image stream to be available for the whole segment duration.
    """
    suffix = Path(path).suffix.lower()
    return suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
    }


def _base_video_filters(
    p: EncodePreset,
    source_fps: Optional[float] = None,
    is_vfr: bool = False,
) -> str:
    """
    Build the base video filter chain for scale + letterbox + fps + pixel format.

    The fps filter is skipped when the source already matches the target framerate
    AND the stream is not variable frame rate (VFR).  This avoids expensive frame
    interpolation/dropping when it is not needed, reducing CPU load significantly.
    The output fps is still enforced via ``-r`` in the encode arguments.
    """
    skip_fps = (
        source_fps is not None
        and not is_vfr
        and abs(source_fps - p.fps) < 0.1
    )
    if skip_fps:
        logger.info(
            "Skipping fps filter: source fps %.2f matches target %d",
            source_fps,
            p.fps,
        )
        fps_filter = ""
    else:
        fps_filter = f"fps={p.fps},"

    return (
        "setpts=PTS-STARTPTS,"
        f"scale={p.width}:{p.height}:force_original_aspect_ratio=decrease,"
        f"pad={p.width}:{p.height}:(ow-iw)/2:(oh-ih)/2,"
        f"{fps_filter}format={p.pix_fmt}"
    )


def _alpha_expr(layer: OverlayLayer) -> str:
    if layer.animation in {"none"}:
        return "1"

    # Clamp times to avoid division by zero.
    fade_in = max(float(layer.fade_in), 0.001)
    fade_out = max(float(layer.fade_out), 0.001)

    start = float(layer.start)
    end = float(layer.end)

    # Fade in from [start..start+fade_in], hold, then fade out at [end-fade_out..end].
    # Remove spaces to avoid parsing issues in FFmpeg filters
    return (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{start}+{fade_in}),(t-{start})/{fade_in},"
        f"if(gt(t,{end}-{fade_out}),({end}-t)/{fade_out},1)"
        f"))"
    )


def _animated_xy(layer: OverlayLayer, axis: str, base_expr: str) -> str:
    """
    Apply a simple slide animation on x/y.

    For text layers, the expressions may refer to text_w/text_h.
    For image layers, they may refer to overlay_w/overlay_h.
    """
    if layer.animation == "slide_up" and axis == "y":
        # Start slightly lower and slide into place during fade-in window.
        dy = 60
        start = float(layer.start)
        dur = max(float(layer.fade_in), 0.001)
        return (
            f"if(lt(t,{start}),({base_expr})+{dy},"
            f" if(lt(t,{start}+{dur}),({base_expr})+{dy}*(1-(t-{start})/{dur}),"
            f"  {base_expr}"
            f" ))"
        )

    if layer.animation == "slide_down" and axis == "y":
        # Start slightly higher and slide into place during fade-in window.
        dy = 60
        start = float(layer.start)
        dur = max(float(layer.fade_in), 0.001)
        return (
            f"if(lt(t,{start}),({base_expr})-{dy},"
            f" if(lt(t,{start}+{dur}),({base_expr})-{dy}*(1-(t-{start})/{dur}),"
            f"  {base_expr}"
            f" ))"
        )

    if layer.animation == "slide_left" and axis == "x":
        dx = 80
        start = float(layer.start)
        dur = max(float(layer.fade_in), 0.001)
        return (
            f"if(lt(t,{start}),({base_expr})-{dx},"
            f" if(lt(t,{start}+{dur}),({base_expr})-{dx}*(1-(t-{start})/{dur}),"
            f"  {base_expr}"
            f" ))"
        )

    if layer.animation == "slide_right" and axis == "x":
        dx = 80
        start = float(layer.start)
        dur = max(float(layer.fade_in), 0.001)
        return (
            f"if(lt(t,{start}),({base_expr})+{dx},"
            f" if(lt(t,{start}+{dur}),({base_expr})+{dx}*(1-(t-{start})/{dur}),"
            f"  {base_expr}"
            f" ))"
        )

    return base_expr


def _animated_size(layer: OverlayLayer, base_size: int) -> str:
    """
    Apply zoom animation by changing size dynamically.
    
    For text layers, returns fontsize expression.
    For image layers, returns scale expression (as multiplier, e.g., 1.5 for 150%).
    """
    if layer.animation == "zoom_in":
        # Start smaller and zoom to full size during fade-in
        scale_start = 0.3  # Start at 30% size
        scale_end = 1.0    # End at 100% size
        start = float(layer.start)
        dur = max(float(layer.fade_in), 0.001)
        # Linear interpolation: start_size + (end_size - start_size) * progress
        return (
            f"if(lt(t,{start}),{base_size}*{scale_start},"
            f" if(lt(t,{start}+{dur}),{base_size}*({scale_start}+({scale_end}-{scale_start})*((t-{start})/{dur})),"
            f"  {base_size}"
            f" ))"
        )
    
    if layer.animation == "zoom_out":
        # Start at full size and zoom out (smaller) during fade-in
        scale_start = 1.0  # Start at 100% size
        scale_end = 0.7    # End at 70% size (or could be smaller)
        start = float(layer.start)
        dur = max(float(layer.fade_in), 0.001)
        return (
            f"if(lt(t,{start}),{base_size}*{scale_start},"
            f" if(lt(t,{start}+{dur}),{base_size}*({scale_start}+({scale_end}-{scale_start})*((t-{start})/{dur})),"
            f"  {base_size}*{scale_end}"
            f" ))"
        )
    
    return str(base_size)


def _segment_filter_complex(
    encode: EncodePreset,
    layers: List[OverlayLayer],
    ctx: TemplateContext,
    work_dir: Path,
    source_fps: Optional[float] = None,
    is_vfr: bool = False,
) -> Tuple[str, List[str]]:
    """
    Build filter_complex and return (filter_complex, extra_inputs).

    The main segment input is always index 0. Any image layers add extra `-i` inputs.
    """
    extra_inputs: List[str] = []
    img_inputs: List[Tuple[int, OverlayLayer]] = []

    for layer in layers:
        if layer.type == "image":
            if not layer.path:
                raise FfmpegError(_("Image overlay layer missing 'path'."))
            img_path = resolve_preset_asset_path(layer.path)
            # Check if file exists
            if not Path(img_path).exists():
                raise FfmpegError(
                    _("Image asset file not found: {path}").format(path=img_path)
                )
            extra_inputs.append(img_path)
            img_inputs.append((len(extra_inputs), layer))  # 1-based relative to extra_inputs

    steps: List[str] = []
    steps.append(f"[0:v]{_base_video_filters(encode, source_fps=source_fps, is_vfr=is_vfr)}[base]")

    current = "base"
    # Add image overlays first.
    for idx, layer in img_inputs:
        # ffmpeg input index for this image is 1 + (idx-1)
        input_idx = idx
        img_label = f"img{input_idx}"
        scaled_label = f"{img_label}s"
        out_label = f"v{input_idx}"

        scale_parts: List[str] = []
        # Handle zoom animation for images
        # Note: For static images, full zoom animation is limited because scale filter
        # doesn't support time-based expressions on image inputs. We scale to final size.
        if layer.animation in {"zoom_in", "zoom_out"}:
            if layer.animation == "zoom_in":
                # Zoom in: scale to full size (100%)
                scale_end = 1.0
            else:  # zoom_out
                # Zoom out: scale to smaller size (70%)
                scale_end = 0.7
            if layer.scale_w and layer.scale_h:
                w_final = int(layer.scale_w * scale_end)
                h_final = int(layer.scale_h * scale_end)
                scale_parts.append(f"scale={w_final}:{h_final}")
            else:
                # Use expressions if base size is not specified
                scale_parts.append(f"scale='iw*{scale_end}':'ih*{scale_end}'")
        elif layer.scale_w or layer.scale_h:
            w = layer.scale_w if layer.scale_w else -1
            h = layer.scale_h if layer.scale_h else -1
            scale_parts.append(f"scale={w}:{h}")
        else:
            scale_parts.append("scale=iw:ih")

        # Scale and format the image to RGBA
        # Note: For image overlays, we rely on the image's built-in alpha channel
        # Fade-in/fade-out animation is handled via enable parameter timing
        scale_parts.append("format=rgba")
        steps.append(f"[{input_idx}:v]{','.join(scale_parts)}[{scaled_label}]")

        # Convert text expressions to image expressions for image overlays
        # text_w -> overlay_w, text_h -> overlay_h
        img_x = layer.x.replace("text_w", "overlay_w").replace("text_h", "overlay_h")
        img_y = layer.y.replace("text_w", "overlay_w").replace("text_h", "overlay_h")
        
        x_expr = _animated_xy(layer, "x", img_x)
        y_expr = _animated_xy(layer, "y", img_y)

        # `enable` gates overlay evaluation, keeping it cheap outside [start..end]
        # Image overlays use their built-in alpha channel; fade animation via timing
        enable = f"between(t,{layer.start},{layer.end})"
        steps.append(
            f"[{current}][{scaled_label}]overlay="
            f"x='{x_expr}':y='{y_expr}':enable='{enable}'"
            f"[{out_label}]"
        )
        current = out_label

    # Add text overlays via drawtext on the current stream.
    # Track title line count to enforce rule: if title is 3+ lines, skip subtitle
    title_lines_count = None
    for i, layer in enumerate([l for l in layers if l.type == "text"], start=1):
        if not layer.template:
            raise FfmpegError(_("Text overlay layer missing 'template'."))

        def _wrap_line_by_pixels(
            line: str,
            *,
            max_width_px: int,
            font_path: str,
            font_size_px: int,
        ) -> List[str]:
            """
            Wrap a single line by measured pixel width, breaking only on spaces.
            This avoids last-glyph clipping when a line is a few pixels too wide.
            """
            line = (line or "").strip()
            if not line:
                return []

            # Import locally to avoid importing Pillow on cold paths.
            from PIL import ImageFont

            font = None
            try:
                font = ImageFont.truetype(font_path, font_size_px)
            except Exception:
                # Try fallback fonts (same as in _render_text_png)
                fallback_candidates = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                ]
                for cand in fallback_candidates:
                    try:
                        if Path(cand).exists():
                            font = ImageFont.truetype(cand, font_size_px)
                            break
                    except Exception:
                        continue
                # If no font could be loaded, return original line
                if font is None:
                    return [line]

            def _measure(text: str) -> float:
                try:
                    return float(font.getlength(text))
                except Exception:
                    bbox = font.getbbox(text)
                    return float(bbox[2] - bbox[0]) if bbox else float(len(text) * font_size_px)

            words = [w for w in line.split(" ") if w]
            if not words:
                return []

            out: List[str] = []
            cur = words[0]
            for w in words[1:]:
                candidate = f"{cur} {w}"
                if _measure(candidate) <= max_width_px:
                    cur = candidate
                    continue
                out.append(cur)
                cur = w
            out.append(cur)
            return out

        def _split_into_3_lines_with_font_adjustment(
            text: str,
            *,
            font_path: str,
            initial_fontsize: int,
            max_width_px: int,
            min_fontsize: int = 48,
        ) -> Tuple[List[str], int]:
            """
            Split text into exactly 3 lines by finding spaces near target positions.
            If text doesn't fit, dynamically reduce fontsize and retry.
            
            Returns:
                Tuple of (list of 3 lines, final fontsize)
            """
            text = (text or "").strip()
            if not text:
                return ["", "", ""], initial_fontsize

            # Import locally
            from PIL import ImageFont

            words = [w for w in text.split(" ") if w]
            if not words:
                return ["", "", ""], initial_fontsize

            # Try with decreasing fontsize until it fits
            fontsize = initial_fontsize
            while fontsize >= min_fontsize:
                try:
                    font = ImageFont.truetype(font_path, fontsize)
                except Exception:
                    # Fallback: simple split by character count
                    return _simple_split_into_3(text), fontsize

                def _measure(text: str) -> float:
                    try:
                        return float(font.getlength(text))
                    except Exception:
                        bbox = font.getbbox(text)
                        return float(bbox[2] - bbox[0]) if bbox else float(len(text) * fontsize)

                # Try to split into 3 lines
                # Strategy: find split points by measuring pixel width, not character count
                # Find the best split points that keep lines roughly equal in width
                
                def find_best_split_points() -> Tuple[int, int]:
                    """Find best split points to create 3 roughly equal-width lines."""
                    # Start with approximate positions: 1/3 and 2/3 of word count
                    target_idx_1 = len(words) // 3
                    target_idx_2 = (len(words) * 2) // 3
                    
                    # Ensure at least 1 word per line
                    target_idx_1 = max(1, min(target_idx_1, len(words) - 2))
                    target_idx_2 = max(target_idx_1 + 1, min(target_idx_2, len(words) - 1))
                    
                    # Try to optimize split points by checking widths
                    best_idx_1 = target_idx_1
                    best_idx_2 = target_idx_2
                    best_balance = float('inf')
                    
                    # Try different split points around target positions
                    for idx1 in range(max(1, target_idx_1 - 2), min(len(words) - 1, target_idx_1 + 3)):
                        for idx2 in range(max(idx1 + 1, target_idx_2 - 2), min(len(words), target_idx_2 + 3)):
                            if idx1 >= idx2 or idx2 >= len(words):
                                continue
                            
                            line1_test = " ".join(words[:idx1])
                            line2_test = " ".join(words[idx1:idx2])
                            line3_test = " ".join(words[idx2:])
                            
                            w1 = _measure(line1_test) if line1_test else 0
                            w2 = _measure(line2_test) if line2_test else 0
                            w3 = _measure(line3_test) if line3_test else 0
                            
                            # Check if all fit
                            if w1 <= max_width_px and w2 <= max_width_px and w3 <= max_width_px:
                                # Calculate balance (difference between max and min width)
                                balance = max(w1, w2, w3) - min(w1, w2, w3)
                                if balance < best_balance:
                                    best_balance = balance
                                    best_idx_1 = idx1
                                    best_idx_2 = idx2
                    
                    return best_idx_1, best_idx_2
                
                split_idx_1, split_idx_2 = find_best_split_points()

                # Build 3 lines
                line1 = " ".join(words[:split_idx_1])
                line2 = " ".join(words[split_idx_1:split_idx_2])
                line3 = " ".join(words[split_idx_2:])

                # Check if all lines fit
                width1 = _measure(line1) if line1 else 0
                width2 = _measure(line2) if line2 else 0
                width3 = _measure(line3) if line3 else 0

                if width1 <= max_width_px and width2 <= max_width_px and width3 <= max_width_px:
                    return [line1, line2, line3], fontsize

                # If any line is too wide, try with smaller fontsize
                fontsize -= 2
                if fontsize < min_fontsize:
                    # Last resort: force split even if it doesn't fit perfectly
                    return [line1, line2, line3], min_fontsize

            # Fallback: simple character-based split
            return _simple_split_into_3(text), min_fontsize

        def _simple_split_into_3(text: str) -> List[str]:
            """Simple fallback: split by character count."""
            words = text.split()
            if len(words) <= 3:
                lines = [" ".join(words[:1]), " ".join(words[1:2]), " ".join(words[2:])]
                return [l if l else "" for l in lines]
            
            third = len(words) // 3
            return [
                " ".join(words[:third]),
                " ".join(words[third:third*2]),
                " ".join(words[third*2:])
            ]

        def _render_text_png(
            *,
            text: str,
            font_path: str,
            font_size_px: int,
            font_color: str,
            out_path: Path,
            padding_px: int = 12,
        ) -> Tuple[int, int]:
            """
            Render a single line of text into an RGBA PNG with padding.
            Using an image overlay avoids FFmpeg drawtext last-glyph clipping.
            Returns (width, height) of the generated PNG.
            """
            from PIL import Image, ImageColor, ImageDraw, ImageFont

            # Parse color like "white" or "white@0.8" or "#RRGGBB"
            color_spec = (font_color or "white").split("@", 1)[0].strip()
            try:
                rgb = ImageColor.getrgb(color_spec)
            except Exception:
                rgb = (255, 255, 255)

            # Load font. The FFmpeg drawtext backend (freetype) may support fonts
            # that Pillow cannot load (e.g. WOFF/WOFF2). For PNG rendering we need
            # a TrueType/OpenType font that Pillow can parse, so we fall back to a
            # known system TTF if the configured font can't be loaded.
            font: ImageFont.FreeTypeFont
            used_font_path = font_path
            try:
                font = ImageFont.truetype(font_path, font_size_px)
            except Exception as e:
                fallback_candidates = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                ]
                loaded = False
                for cand in fallback_candidates:
                    try:
                        if Path(cand).exists():
                            font = ImageFont.truetype(cand, font_size_px)
                            used_font_path = cand
                            loaded = True
                            break
                    except Exception:
                        continue
                if not loaded:
                    raise FfmpegError(
                        _("Failed to load font for PNG text rendering. Tried '{primary}' and fallbacks. Error: {err}").format(
                            primary=font_path, err=str(e)
                        )
                    )
                logger.warning(
                    "Pillow failed to load font '%s' (%s). Falling back to '%s' for PNG title rendering.",
                    font_path,
                    str(e),
                    used_font_path,
                )

            # Measure tight bbox
            bbox = font.getbbox(text)
            text_w = max(1, int(bbox[2] - bbox[0]))
            text_h = max(1, int(bbox[3] - bbox[1]))

            # Add generous padding to avoid edge clipping
            img_w = text_w + padding_px * 2
            img_h = text_h + padding_px * 2

            img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # Draw at padding, adjusting for bbox origin
            draw_x = padding_px - bbox[0]
            draw_y = padding_px - bbox[1]
            draw.text((draw_x, draw_y), text, font=font, fill=(rgb[0], rgb[1], rgb[2], 255))

            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path, format="PNG")
            return img_w, img_h

        # Render template and split into lines
        rendered_text = render_text_template(layer.template, ctx)
        
        # Apply uppercase transformation if requested
        if layer.uppercase:
            rendered_text = rendered_text.upper()
        
        # DEBUG: Log raw rendered text with code points (using INFO level to ensure visibility)
        logger.info(
            f"[TEXT DEBUG] Layer {i} template='{layer.template}' "
            f"rendered_text={repr(rendered_text)} "
            f"len={len(rendered_text)} "
            f"code_points={[ord(c) for c in rendered_text[:100]]}"
        )
        
        import re
        # Clean and split into lines.
        # IMPORTANT: Do not aggressively strip "unknown" characters here, as it can
        # delete valid letters at line ends. We only remove control / zero-width chars.
        lines = rendered_text.splitlines()
        cleaned_lines = []
        for line_idx, line in enumerate(lines):
            original_line = line
            line = line.strip()
            if not line:
                continue
            # Remove control chars and zero-width characters anywhere in the line.
            # This keeps user-visible letters intact.
            line_before_clean = line
            
            # Special check for "und" - look for invisible characters BEFORE cleaning
            if 'und' in line.lower() or 'un' in line.lower():
                und_pos = line.lower().find('und')
                if und_pos < 0:
                    und_pos = line.lower().find('un')
                if und_pos >= 0:
                    start = max(0, und_pos - 3)
                    end = min(len(line), und_pos + 6)
                    section = line[start:end]
                    logger.info(
                        f"[TEXT DEBUG] Layer {i} line {line_idx} BEFORE CLEAN - section around un/und: "
                        f"{repr(section)} "
                        f"code_points={[ord(c) for c in section]} "
                        f"hex={[hex(ord(c)) for c in section]}"
                    )
            
            line = re.sub(r'[\x00-\x1F\x7F-\x9F\u200B-\u200D\uFEFF]', '', line)
            line = line.strip()
            
            # Check again after cleaning
            if 'und' in line.lower() or 'un' in line.lower():
                und_pos = line.lower().find('und')
                if und_pos < 0:
                    und_pos = line.lower().find('un')
                if und_pos >= 0:
                    start = max(0, und_pos - 3)
                    end = min(len(line), und_pos + 6)
                    section = line[start:end]
                    logger.info(
                        f"[TEXT DEBUG] Layer {i} line {line_idx} AFTER CLEAN - section around un/und: "
                        f"{repr(section)} "
                        f"code_points={[ord(c) for c in section]} "
                        f"hex={[hex(ord(c)) for c in section]}"
                    )
            
            # DEBUG: Log each line with code points (using INFO level to ensure visibility)
            if line:
                logger.info(
                    f"[TEXT DEBUG] Layer {i} line {line_idx}: "
                    f"original={repr(original_line)} "
                    f"before_clean={repr(line_before_clean)} "
                    f"after_clean={repr(line)} "
                    f"len={len(line)} "
                    f"code_points={[ord(c) for c in line]} "
                    f"contains_und={'und' in line.lower()} "
                    f"contains_un={'un' in line.lower() and 'und' not in line.lower()}"
                )
                cleaned_lines.append(line)
        
        if not cleaned_lines:
            # Skip empty text layers (e.g., conditional subtitle that was empty)
            continue

        fontfile = ""
        if layer.fontfile:
            fontfile = resolve_preset_asset_path(layer.fontfile)
            # Check if font file exists
            if not Path(fontfile).exists():
                raise FfmpegError(
                    _("Font file not found: {path}").format(path=fontfile)
                )

        # Determine if this is a title layer (we treat title specially)
        is_title_layer = bool(layer.template and "title" in layer.template.lower())
        # Determine if this is a subtitle layer
        is_subtitle_layer = bool(layer.template and "subtitle" in layer.template.lower())

        # Rule: if title is 3+ lines, skip subtitle
        if is_subtitle_layer and title_lines_count is not None and title_lines_count >= 3:
            logger.info(
                f"[TEXT DEBUG] Layer {i} (subtitle) skipped because title has {title_lines_count} lines "
                f"(rule: max 4 lines total, skip subtitle if title >= 3 lines)"
            )
            continue

        # Pixel-based wrapping pass (prevents last-letter clipping on near-max lines).
        # For title layers: first try standard wrapping, only split into 3 lines if needed
        adjusted_fontsize = layer.fontsize  # Will be updated if fontsize is adjusted
        
        if fontfile and is_title_layer:
            # For title: join all lines back into single text for pixel-based wrapping
            # This handles cases where title might come pre-split from template
            max_width_px = int(encode.width * 0.85)  # 85% of screen width
            original_text = " ".join(cleaned_lines)
            
            # Try with initial fontsize, then reduce if needed
            current_fontsize = int(layer.fontsize)
            min_fontsize = 48
            fontsize_step = 2
            
            best_result = None
            best_fontsize = current_fontsize
            
            # Try to fit text in 1-3 lines by adjusting fontsize
            while current_fontsize >= min_fontsize:
                # Try pixel-based wrapping with current fontsize
                wrapped = _wrap_line_by_pixels(
                    original_text,
                    max_width_px=max_width_px,
                    font_path=fontfile,
                    font_size_px=current_fontsize,
                )
                
                # Check if single line is too wide (more than 80% of max_width)
                # If so, force split into 2 lines for better readability
                force_split_success = False
                single_line_too_wide = False
                
                if len(wrapped) == 1:
                    from PIL import ImageFont
                    font = None
                    used_font_path = fontfile
                    try:
                        font = ImageFont.truetype(fontfile, current_fontsize)
                    except Exception as e:
                        # Try fallback fonts (same as in _render_text_png)
                        fallback_candidates = [
                            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
                            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                        ]
                        for cand in fallback_candidates:
                            try:
                                if Path(cand).exists():
                                    font = ImageFont.truetype(cand, current_fontsize)
                                    used_font_path = cand
                                    logger.warning(
                                        f"[TEXT DEBUG] Layer {i} font '{fontfile}' failed to load, using fallback '{cand}' for width measurement"
                                    )
                                    break
                            except Exception:
                                continue
                    
                    if font is not None:
                        def _measure(text: str) -> float:
                            try:
                                return float(font.getlength(text))
                            except Exception:
                                bbox = font.getbbox(text)
                                return float(bbox[2] - bbox[0]) if bbox else float(len(text) * current_fontsize)
                        
                        line_width = _measure(wrapped[0])
                        # If line width is more than 80% of max_width, force split into 2 lines
                        if line_width > max_width_px * 0.80:
                            single_line_too_wide = True
                            # Try to split into 2 lines
                            words = original_text.split(" ")
                            if len(words) > 1:
                                # Find best split point (middle of text)
                                mid_point = len(words) // 2
                                # Try to find a good split point near the middle
                                best_split = None
                                best_balance = float('inf')
                                
                                # Search for split points around the middle
                                for split_idx in range(max(1, mid_point - 3), min(len(words), mid_point + 4)):
                                    line1_test = " ".join(words[:split_idx])
                                    line2_test = " ".join(words[split_idx:])
                                    w1 = _measure(line1_test)
                                    w2 = _measure(line2_test)
                                    # Check if both lines fit
                                    if w1 <= max_width_px and w2 <= max_width_px:
                                        # Calculate balance (difference between line widths)
                                        balance = abs(w1 - w2)
                                        # Prefer split that makes lines more balanced
                                        if balance < best_balance:
                                            best_balance = balance
                                            best_split = split_idx
                                
                                # If we found a valid split point, use it
                                if best_split is not None:
                                    line1 = " ".join(words[:best_split])
                                    line2 = " ".join(words[best_split:])
                                    wrapped = [line1, line2]
                                    force_split_success = True
                                    logger.info(
                                        f"[TEXT DEBUG] Layer {i} single line too wide ({line_width:.0f}px > {max_width_px * 0.80:.0f}px), "
                                        f"forced split into 2 lines at word {best_split}"
                                    )
                                else:
                                    # No valid split point found - will try with smaller fontsize
                                    logger.info(
                                        f"[TEXT DEBUG] Layer {i} single line too wide ({line_width:.0f}px > {max_width_px * 0.80:.0f}px), "
                                        f"but no valid split point found, will try smaller fontsize"
                                    )
                    else:
                        # If font loading completely failed, log warning but continue
                        logger.warning(f"[TEXT DEBUG] Layer {i} font measurement failed: could not load font or fallback")
                
                # If text fits in 1-3 lines AND (it's not a single wide line OR we successfully split it), use this result
                if len(wrapped) <= 3:
                    if len(wrapped) == 1 and single_line_too_wide and not force_split_success:
                        # Single line is too wide and we couldn't split it - try with smaller fontsize
                        current_fontsize -= fontsize_step
                        continue
                    else:
                        # Use this result (either multiple lines, or single line that's not too wide, or successfully split)
                        best_result = wrapped
                        best_fontsize = current_fontsize
                        break
                
                # If text doesn't fit (more than 3 lines), try with smaller fontsize
                current_fontsize -= fontsize_step
            
            # If we found a result that fits, use it
            if best_result is not None:
                cleaned_lines = best_result
                adjusted_fontsize = best_fontsize
                title_lines_count = len(cleaned_lines)
                if adjusted_fontsize != layer.fontsize:
                    logger.info(
                        f"[TEXT DEBUG] Layer {i} fontsize adjusted from {layer.fontsize} to {adjusted_fontsize} "
                        f"to fit title in {len(cleaned_lines)} line(s)"
                    )
                else:
                    logger.info(
                        f"[TEXT DEBUG] Layer {i} title fits in {len(cleaned_lines)} line(s) with original fontsize"
                    )
            else:
                # Last resort: use result with min_fontsize even if it's more than 3 lines
                wrapped = _wrap_line_by_pixels(
                    original_text,
                    max_width_px=max_width_px,
                    font_path=fontfile,
                    font_size_px=min_fontsize,
                )
                cleaned_lines = wrapped
                adjusted_fontsize = min_fontsize
                title_lines_count = len(cleaned_lines)
                logger.warning(
                    f"[TEXT DEBUG] Layer {i} title requires {len(cleaned_lines)} lines even at min fontsize {min_fontsize}"
                )
        elif fontfile:
            # For non-title layers: use standard pixel-based wrapping
            # For subtitle: use same width as title (85%) for consistency
            # For other layers: use 80% width for large fonts (64px) to prevent last-letter clipping
            if is_subtitle_layer:
                max_width_px = int(encode.width * 0.85)  # Same as title for consistency
            else:
                max_width_px = int(encode.width * 0.80) if layer.fontsize >= 60 else int(encode.width * 0.90)
            wrapped: List[str] = []
            for ln in cleaned_lines:
                wrapped.extend(
                    _wrap_line_by_pixels(
                        ln,
                        max_width_px=max_width_px,
                        font_path=fontfile,
                        font_size_px=int(layer.fontsize),
                    )
                )
            cleaned_lines = [x for x in wrapped if x]
            
            # Store title line count if this is a title layer (after wrapping)
            if is_title_layer:
                title_lines_count = len(cleaned_lines)
            
            # DEBUG: Log after pixel-based wrapping (using INFO level to ensure visibility)
            logger.info(
                f"[TEXT DEBUG] Layer {i} after pixel-based wrapping: "
                f"lines={[repr(l) for l in cleaned_lines]} "
                f"line_lengths={[len(l) for l in cleaned_lines]}"
            )

        # If this is a title layer and we have a font, render each line to a PNG and overlay as an image.
        # This avoids FFmpeg drawtext glyph clipping (e.g. "und" -> "un").
        if is_title_layer and fontfile and cleaned_lines:
            # Ensure title_lines_count is set (in case title wasn't wrapped above)
            if title_lines_count is None:
                title_lines_count = len(cleaned_lines)
            # Calculate line height from adjusted fontsize
            line_height = int(adjusted_fontsize * 1.2)

            # Base expressions for image overlay (convert text_* to overlay_*)
            img_x_base = layer.x.replace("text_w", "overlay_w").replace("text_h", "overlay_h")
            img_y_base = layer.y.replace("text_w", "overlay_w").replace("text_h", "overlay_h")

            for line_idx, line_text in enumerate(cleaned_lines[:3]):
                # Render PNG for this line
                png_path = work_dir / f"text_layer_{i}_{line_idx}.png"
                _render_text_png(
                    text=line_text,
                    font_path=fontfile,
                    font_size_px=int(adjusted_fontsize),
                    font_color=layer.fontcolor,
                    out_path=png_path,
                    padding_px=16,
                )

                # Add as extra ffmpeg input
                extra_inputs.append(str(png_path))
                input_idx = len(extra_inputs)  # 1-based index for ffmpeg inputs beyond main video
                img_label = f"timg{input_idx}"
                fmt_label = f"{img_label}f"
                out_label = f"v_t{input_idx}"

                # Prepare image stream (format + fade if requested)
                img_filters: List[str] = ["format=rgba"]
                if layer.animation == "fade":
                    fade_in = max(float(layer.fade_in), 0.0)
                    fade_out = max(float(layer.fade_out), 0.0)
                    if fade_in > 0:
                        img_filters.append(f"fade=t=in:st={layer.start}:d={fade_in}:alpha=1")
                    if fade_out > 0:
                        st_out = max(float(layer.end) - fade_out, float(layer.start))
                        img_filters.append(f"fade=t=out:st={st_out}:d={fade_out}:alpha=1")

                steps.append(f"[{input_idx}:v]{','.join(img_filters)}[{fmt_label}]")

                # Y position for this line (stacked)
                line_y = f"({img_y_base})+{line_idx * line_height}"
                x_expr = _animated_xy(layer, "x", img_x_base)
                y_expr = _animated_xy(layer, "y", line_y)
                enable = f"between(t,{layer.start},{layer.end})"

                steps.append(
                    f"[{current}][{fmt_label}]overlay="
                    f"x='{x_expr}':y='{y_expr}':enable='{enable}'"
                    f"[{out_label}]"
                )
                current = out_label

            # Done handling title via image overlays; skip drawtext path for this layer
            continue

        alpha = _alpha_expr(layer)
        # Check if original x expression indicates centering (before animation)
        # Support both (w-text_w)/2 and w/2 for centering
        is_centered = "(w-text_w)/2" in layer.x or layer.x.strip() == "w/2" or layer.x.strip().startswith("w/2")
        base_x_expr = _animated_xy(layer, "x", layer.x)
        base_y_expr = _animated_xy(layer, "y", layer.y)
        enable = f"between(t,{layer.start},{layer.end})"

        # For multi-line text, create separate drawtext for each line
        # Each line will be centered/aligned independently
        if len(cleaned_lines) > 1:
            # Calculate line height (use adjusted_fontsize if it was modified)
            line_height = int(adjusted_fontsize * 1.3)
            
            # Create a separate drawtext for each line
            for line_idx, line_text in enumerate(cleaned_lines):
                # DEBUG: Log final text that goes to FFmpeg (using INFO level to ensure visibility)
                escaped_preview = line_text.replace("\\", "\\\\").replace("'", "\\'")[:50]
                logger.info(
                    f"[TEXT DEBUG] Layer {i} final line {line_idx} for FFmpeg drawtext: "
                    f"text={repr(line_text)} "
                    f"len={len(line_text)} "
                    f"code_points={[ord(c) for c in line_text]} "
                    f"escaped_preview={escaped_preview}"
                )
                
                # Escape text for FFmpeg
                escaped_text = line_text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
                
                # Calculate Y position for this line
                line_y_offset = line_idx * line_height
                line_y = f"({base_y_expr})+{line_y_offset}"
                
                # Apply zoom animation to fontsize if needed
                # Use adjusted_fontsize if it was modified (for title layers with 3-line split)
                fontsize_expr = _animated_size(layer, adjusted_fontsize)
                parts = [
                    f"drawtext=text='{escaped_text}'",
                ]
                
                if is_centered:
                    # Each line centered independently.
                    # For first line (line_idx == 0), add extra left offset to prevent last-letter clipping
                    # This is needed because FFmpeg can clip the last glyph on the first line
                    if line_idx == 0:
                        # Add 3px left offset for first line to prevent 'd' in 'und' from being clipped
                        parts.append("x='floor((w-text_w)/2)-3'")
                    else:
                        parts.append("x='floor((w-text_w)/2)'")
                    # fix_bounds=1 prevents glyph clipping at the edges of the frame
                    parts.append("fix_bounds=1")
                else:
                    # Left alignment
                    parts.append(f"x='{base_x_expr}'")
                
                parts.extend([
                    f"y='{line_y}'",
                    f"fontsize='{fontsize_expr}'",
                    f"fontcolor={layer.fontcolor}",
                    f"alpha='{alpha}'",
                    f"enable='{enable}'",
                ])
                if fontfile:
                    parts.append(f"fontfile='{fontfile}'")
                if layer.box:
                    parts.append("box=1")
                    parts.append(f"boxcolor={layer.boxcolor}")
                    parts.append(f"boxborderw={layer.boxborderw}")

                out_label = f"t{i}_l{line_idx}"
                steps.append(f"[{current}]{':'.join(parts)}[{out_label}]")
                current = out_label
        else:
            # Single line - use direct text
            escaped_text = cleaned_lines[0].replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
            parts = [
                f"drawtext=text='{escaped_text}'",
            ]
            
            if is_centered:
                # Keep true centering but avoid last-glyph clipping:
                # - floor() avoids rounding up
                # - fix_bounds=1 prevents edge clipping
                parts.append("fix_bounds=1")
                parts.append("x='floor((w-text_w)/2)'")
            else:
                parts.append(f"x='{base_x_expr}'")
            # Apply zoom animation to fontsize if needed
            # Use adjusted_fontsize if it was modified (for title layers with 3-line split)
            fontsize_expr = _animated_size(layer, adjusted_fontsize)
            parts.extend([
                f"y='{base_y_expr}'",
                f"fontsize='{fontsize_expr}'",
                f"fontcolor={layer.fontcolor}",
                f"alpha='{alpha}'",
                f"enable='{enable}'",
            ])
            if fontfile:
                parts.append(f"fontfile='{fontfile}'")
            if layer.box:
                parts.append("box=1")
                parts.append(f"boxcolor={layer.boxcolor}")
                parts.append(f"boxborderw={layer.boxborderw}")

            out_label = f"t{i}"
            steps.append(f"[{current}]{':'.join(parts)}[{out_label}]")
            current = out_label

    filter_complex = ";".join(steps)
    return filter_complex, extra_inputs


def _encode_args(p: EncodePreset) -> List[str]:
    return [
        "-c:v",
        p.vcodec,
        "-preset",
        p.x264_preset,
        "-profile:v",
        p.x264_profile,
        "-pix_fmt",
        p.pix_fmt,
        "-b:v",
        f"{p.video_bitrate_k}k",
        "-maxrate",
        f"{p.video_bitrate_k}k",
        "-bufsize",
        f"{p.video_bitrate_k * 2}k",
        "-r",
        str(p.fps),
        "-c:a",
        p.acodec,
        "-b:a",
        f"{p.audio_bitrate_k}k",
        "-ar",
        str(p.audio_sample_rate),
        "-ac",
        str(p.audio_channels),
    ]


def _render_segment_to_ts(
    input_video: str,
    output_ts: str,
    encode: EncodePreset,
    layers: List[OverlayLayer],
    ctx: TemplateContext,
    *,
    ss: Optional[float] = None,
    t: Optional[float] = None,
    source_fps: Optional[float] = None,
    is_vfr: bool = False,
) -> None:
    work_dir = Path(output_ts).parent
    work_dir.mkdir(parents=True, exist_ok=True)
    filter_complex, extra_inputs = _segment_filter_complex(
        encode, layers, ctx, work_dir, source_fps=source_fps, is_vfr=is_vfr
    )

    cmd: List[str] = ["ffmpeg", "-y"]
    # IMPORTANT: -ss/-t must be input options here so filter time (t) starts from 0.
    if ss is not None:
        cmd.extend(["-ss", str(max(ss, 0.0))])
    if t is not None:
        cmd.extend(["-t", str(max(t, 0.0))])
    cmd.extend(["-i", input_video])
    for extra in extra_inputs:
        if _is_still_image(extra):
            # Loop still images to keep them available for the full segment duration.
            # Use the target FPS so overlay timing aligns with the base segment.
            cmd.extend(["-framerate", str(encode.fps), "-loop", "1", "-i", extra])
        else:
            cmd.extend(["-i", extra])

    has_audio = _has_audio(input_video)
    if not has_audio:
        # Provide silent audio to keep concat consistent.
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={encode.audio_sample_rate}",
            ]
        )

    cmd.extend(["-filter_complex", filter_complex])
    cmd.extend(["-map", f"[{_final_video_label(filter_complex)}]"])

    if has_audio:
        cmd.extend(["-map", "0:a?"])
    else:
        # Silent audio is the last input.
        cmd.extend(["-map", f"{1 + len(extra_inputs)}:a"])

    cmd.extend(_encode_args(encode))
    cmd.extend(["-shortest", "-f", "mpegts", output_ts])
    segment_duration = float(t) if t is not None and t > 0 else _duration_seconds(input_video)
    _run(cmd, timeout=_render_timeout(segment_duration))


def _final_video_label(filter_complex: str) -> str:
    # The last filter step ends with [label]. We need that label for mapping.
    # We keep this simple by parsing the last [...] token.
    tail = filter_complex.split(";")[-1]
    if "[" not in tail or "]" not in tail:
        return "base"
    return tail.split("[")[-1].split("]")[0]


def _render_main_to_ts(
    input_video: str,
    output_ts: str,
    encode: EncodePreset,
    source_fps: Optional[float] = None,
    is_vfr: bool = False,
) -> None:
    if source_fps is None:
        source_fps = _source_fps(input_video)
    if not is_vfr:
        is_vfr = _source_is_vfr(input_video)
        if is_vfr:
            logger.info("VFR detected for %s, keeping fps filter", input_video)

    vf = _base_video_filters(encode, source_fps=source_fps, is_vfr=is_vfr)
    cmd: List[str] = ["ffmpeg", "-y", "-i", input_video]

    has_audio = _has_audio(input_video)
    if not has_audio:
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={encode.audio_sample_rate}",
            ]
        )

    cmd.extend(["-vf", vf])
    cmd.extend(["-map", "0:v:0"])
    if has_audio:
        cmd.extend(["-map", "0:a?"])
    else:
        cmd.extend(["-map", "1:a"])

    cmd.extend(_encode_args(encode))
    cmd.extend(["-shortest", "-f", "mpegts", output_ts])
    _run(cmd, timeout=_render_timeout(_duration_seconds(input_video)))


def render_with_intro_outro(
    *,
    intro_video: str,
    main_video: str,
    outro_video: str,
    output_mp4: str,
    encode: EncodePreset,
    intro_layers: List[OverlayLayer],
    outro_layers: List[OverlayLayer],
    ctx: TemplateContext,
) -> RenderArtifacts:
    """
    Render intro/main/outro segments and concat them into a single MP4 output.
    """
    out_path = Path(output_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="oktools_render_") as tmp:
        intro_ts = str(Path(tmp) / "intro.ts")
        main_ts = str(Path(tmp) / "main.ts")
        outro_ts = str(Path(tmp) / "outro.ts")

        # Compute source fps once per input file to skip the fps filter when
        # the source already matches the target.  VFR streams always keep the filter.
        intro_fps = _source_fps(intro_video)
        intro_vfr = _source_is_vfr(intro_video)
        if intro_vfr:
            logger.info("VFR detected for %s, keeping fps filter", intro_video)
        main_fps = _source_fps(main_video)
        main_vfr = _source_is_vfr(main_video)
        if main_vfr:
            logger.info("VFR detected for %s, keeping fps filter", main_video)
        outro_fps = _source_fps(outro_video)
        outro_vfr = _source_is_vfr(outro_video)
        if outro_vfr:
            logger.info("VFR detected for %s, keeping fps filter", outro_video)

        _render_segment_to_ts(
            intro_video, intro_ts, encode, intro_layers, ctx,
            source_fps=intro_fps, is_vfr=intro_vfr,
        )
        _render_main_to_ts(
            main_video, main_ts, encode,
            source_fps=main_fps, is_vfr=main_vfr,
        )
        _render_segment_to_ts(
            outro_video, outro_ts, encode, outro_layers, ctx,
            source_fps=outro_fps, is_vfr=outro_vfr,
        )

        concat_input = f"concat:{intro_ts}|{main_ts}|{outro_ts}"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            concat_input,
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            str(out_path),
        ]
        _run(cmd)

        return RenderArtifacts(output_mp4=str(out_path))


def render_with_overlays_on_main_edges(
    *,
    main_video: str,
    output_mp4: str,
    encode: EncodePreset,
    intro_layers: List[OverlayLayer],
    outro_layers: List[OverlayLayer],
    ctx: TemplateContext,
    segment_duration: float = 5.0,
) -> RenderArtifacts:
    """
    Render overlays on the first/last N seconds of the *main* video, without intro/outro clips.
    """
    out_path = Path(output_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dur = _duration_seconds(main_video)
    if dur <= 0:
        raise FfmpegError(_("Could not determine video duration for edge overlays."))

    seg = max(0.1, float(segment_duration))
    seg = min(seg, max(dur / 2.0, 0.1))
    mid = max(dur - 2.0 * seg, 0.0)

    with tempfile.TemporaryDirectory(prefix="oktools_render_") as tmp:
        intro_ts = str(Path(tmp) / "intro.ts")
        main_ts = str(Path(tmp) / "main.ts")
        outro_ts = str(Path(tmp) / "outro.ts")

        # Compute source fps once; all segments come from the same main_video.
        main_fps = _source_fps(main_video)
        main_vfr = _source_is_vfr(main_video)
        if main_vfr:
            logger.info("VFR detected for %s, keeping fps filter", main_video)

        _render_segment_to_ts(
            main_video, intro_ts, encode, intro_layers, ctx,
            ss=0.0, t=seg,
            source_fps=main_fps, is_vfr=main_vfr,
        )
        if mid > 0.01:
            # Middle part: no overlay.
            # We render it as a segment with ss/t so concat timings align.
            cmd = ["ffmpeg", "-y", "-ss", str(seg), "-t", str(mid), "-i", main_video]
            has_audio = _has_audio(main_video)
            if not has_audio:
                cmd.extend(
                    [
                        "-f",
                        "lavfi",
                        "-i",
                        f"anullsrc=channel_layout=stereo:sample_rate={encode.audio_sample_rate}",
                    ]
                )
            cmd.extend(["-vf", _base_video_filters(encode, source_fps=main_fps, is_vfr=main_vfr)])
            cmd.extend(["-map", "0:v:0"])
            if has_audio:
                cmd.extend(["-map", "0:a?"])
            else:
                cmd.extend(["-map", "1:a"])
            cmd.extend(_encode_args(encode))
            cmd.extend(["-shortest", "-f", "mpegts", main_ts])
            _run(cmd, timeout=_render_timeout(mid))
        else:
            # If the video is very short, just skip the middle.
            Path(main_ts).write_bytes(b"")

        _render_segment_to_ts(
            main_video,
            outro_ts,
            encode,
            outro_layers,
            ctx,
            ss=max(dur - seg, 0.0),
            t=seg,
            source_fps=main_fps,
            is_vfr=main_vfr,
        )

        concat_input = f"concat:{intro_ts}|{main_ts}|{outro_ts}" if mid > 0.01 else f"concat:{intro_ts}|{outro_ts}"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            concat_input,
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            str(out_path),
        ]
        _run(cmd)

        return RenderArtifacts(output_mp4=str(out_path))


def render_preview_overlays_on_main_edges(
    *,
    main_video: str,
    output_mp4: str,
    encode: EncodePreset,
    intro_layers: List[OverlayLayer],
    outro_layers: List[OverlayLayer],
    ctx: TemplateContext,
    segment_duration: float = 5.0,
) -> RenderArtifacts:
    """
    Preview mode: render only N seconds from the start and N seconds from the end of the main video.

    This is intended for fast visual verification of overlays.
    """
    out_path = Path(output_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dur = _duration_seconds(main_video)
    if dur <= 0:
        raise FfmpegError(_("Could not determine video duration for preview rendering."))

    seg = max(0.1, float(segment_duration))
    seg = min(seg, max(dur / 2.0, 0.1))

    with tempfile.TemporaryDirectory(prefix="oktools_render_preview_") as tmp:
        intro_ts = str(Path(tmp) / "intro.ts")
        outro_ts = str(Path(tmp) / "outro.ts")

        # Compute source fps once; both segments come from the same main_video.
        main_fps = _source_fps(main_video)
        main_vfr = _source_is_vfr(main_video)
        if main_vfr:
            logger.info("VFR detected for %s, keeping fps filter", main_video)

        _render_segment_to_ts(
            main_video, intro_ts, encode, intro_layers, ctx,
            ss=0.0, t=seg,
            source_fps=main_fps, is_vfr=main_vfr,
        )
        _render_segment_to_ts(
            main_video,
            outro_ts,
            encode,
            outro_layers,
            ctx,
            ss=max(dur - seg, 0.0),
            t=seg,
            source_fps=main_fps,
            is_vfr=main_vfr,
        )

        concat_input = f"concat:{intro_ts}|{outro_ts}"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            concat_input,
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            str(out_path),
        ]
        _run(cmd)

        return RenderArtifacts(output_mp4=str(out_path))
