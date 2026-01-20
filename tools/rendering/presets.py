"""Preset loading and validation for video rendering (Tools module)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.apps import apps
from django.conf import settings


class PresetError(ValueError):
    """Raised when a preset cannot be loaded or validated."""


@dataclass(frozen=True)
class EncodePreset:
    """Encoding preset (video+audio normalization)."""

    name: str
    width: int
    height: int
    fps: int
    vcodec: str = "libx264"
    acodec: str = "aac"
    video_bitrate_k: int = 9000
    audio_bitrate_k: int = 192
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    pix_fmt: str = "yuv420p"
    x264_preset: str = "veryfast"
    x264_profile: str = "high"


@dataclass(frozen=True)
class OverlayLayer:
    """Single overlay layer for a segment (intro/outro)."""

    type: str  # "text" or "image"
    template: Optional[str] = None  # for text
    path: Optional[str] = None  # for image
    x: str = "(w-text_w)/2"
    y: str = "(h-text_h)/2"
    start: float = 0.0
    end: float = 5.0
    animation: str = "fade"  # "fade", "slide_up", "slide_left", "none"
    fade_in: float = 0.4
    fade_out: float = 0.4
    fontsize: int = 48
    fontcolor: str = "white"
    fontfile: Optional[str] = None
    box: bool = False
    boxcolor: str = "black@0.5"
    boxborderw: int = 20
    scale_w: Optional[int] = None  # for image
    scale_h: Optional[int] = None  # for image
    uppercase: bool = False  # convert text to uppercase


@dataclass(frozen=True)
class StylePreset:
    """Style preset: intro/outro clips and overlay layers."""

    name: str
    intro_clip: Optional[str]
    outro_clip: Optional[str]
    intro_overlays: List[OverlayLayer]
    outro_overlays: List[OverlayLayer]
    segment_duration: float = 5.0


def _preset_dir(kind: str) -> Path:
    """
    Return preset directory.

    NOTE: Preset assets (fonts/logo) currently live under `media_files/video_presets/`.
    We keep this path to avoid duplicating binary assets in the repo.
    """
    return Path(settings.BASE_DIR) / "media_files" / "video_presets" / kind


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise PresetError(f"Preset not found: {path}") from e
    except json.JSONDecodeError as e:
        raise PresetError(f"Invalid JSON preset: {path}: {e}") from e


def _require(obj: Dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise PresetError(f"Missing required preset field: {key}")
    return obj[key]


def load_encode_preset(name: str) -> EncodePreset:
    """
    Load an encoding preset by name.

    First tries to load from database (tools.VideoEncodePreset model).
    If not found, falls back to JSON file in media_files/video_presets/encode.
    """
    try:
        VideoEncodePreset = apps.get_model("tools", "VideoEncodePreset")
        preset = VideoEncodePreset.objects.filter(name=name).first()
        if preset:
            return EncodePreset(
                name=preset.name,
                width=preset.width,
                height=preset.height,
                fps=preset.fps,
                vcodec=preset.vcodec,
                acodec=preset.acodec,
                video_bitrate_k=preset.video_bitrate_k,
                audio_bitrate_k=preset.audio_bitrate_k,
                audio_sample_rate=preset.audio_sample_rate,
                audio_channels=preset.audio_channels,
                pix_fmt=preset.pix_fmt,
                x264_preset=preset.x264_preset,
                x264_profile=preset.x264_profile,
            )
    except Exception:
        pass

    path = _preset_dir("encode") / f"{name}.json"
    data = _load_json(path)
    return EncodePreset(
        name=_require(data, "name"),
        width=int(_require(data, "width")),
        height=int(_require(data, "height")),
        fps=int(_require(data, "fps")),
        vcodec=str(data.get("vcodec", "libx264")),
        acodec=str(data.get("acodec", "aac")),
        video_bitrate_k=int(data.get("video_bitrate_k", 9000)),
        audio_bitrate_k=int(data.get("audio_bitrate_k", 192)),
        audio_sample_rate=int(data.get("audio_sample_rate", 48000)),
        audio_channels=int(data.get("audio_channels", 2)),
        pix_fmt=str(data.get("pix_fmt", "yuv420p")),
        x264_preset=str(data.get("x264_preset", "veryfast")),
        x264_profile=str(data.get("x264_profile", "high")),
    )


def list_encode_presets() -> List[Dict[str, str]]:
    """List all available encoding presets from media_files/video_presets/encode directory."""
    encode_dir = _preset_dir("encode")
    if not encode_dir.exists():
        return []

    presets: List[Dict[str, str]] = []
    for json_file in sorted(encode_dir.glob("*.json")):
        try:
            data = _load_json(json_file)
            preset_name = _require(data, "name")
            width = int(_require(data, "width"))
            height = int(_require(data, "height"))
            fps = int(_require(data, "fps"))
            video_bitrate_k = int(data.get("video_bitrate_k", 9000))

            display_name = f"{height}p ({video_bitrate_k}k)"
            description = f"{width}x{height}, {fps}fps"

            presets.append({"id": preset_name, "name": display_name, "description": description})
        except Exception:
            continue

    return presets


def list_style_presets() -> List[Dict[str, Any]]:
    """List all available style presets from media_files/video_presets/style directory (JSON files)."""
    style_dir = _preset_dir("style")
    if not style_dir.exists():
        return []

    presets: List[Dict[str, Any]] = []
    for json_file in sorted(style_dir.glob("*.json")):
        try:
            data = _load_json(json_file)
            preset_name = _require(data, "name")
            display_name = preset_name.replace("_", " ").title()

            overlays = data.get("overlays", {})
            intro_overlays = overlays.get("intro", [])
            outro_overlays = overlays.get("outro", [])
            has_intro = len(intro_overlays) > 0
            has_outro = len(outro_overlays) > 0

            if has_intro and has_outro:
                description = f"Imported from {json_file.name}"
            elif has_intro:
                description = f"Intro overlays only - Imported from {json_file.name}"
            elif has_outro:
                description = f"Outro overlays only - Imported from {json_file.name}"
            else:
                description = f"Imported from {json_file.name}"

            presets.append(
                {"id": preset_name, "name": display_name, "description": description, "is_json_preset": True, "json_file": str(json_file.name)}
            )
        except Exception:
            continue

    return presets


def _parse_layer(raw: Dict[str, Any]) -> OverlayLayer:
    layer_type = str(_require(raw, "type"))
    if layer_type not in {"text", "image"}:
        raise PresetError(f"Unsupported overlay layer type: {layer_type}")

    return OverlayLayer(
        type=layer_type,
        template=raw.get("template"),
        path=raw.get("path"),
        x=str(raw.get("x", "(w-text_w)/2")),
        y=str(raw.get("y", "(h-text_h)/2")),
        start=float(raw.get("start", 0.0)),
        end=float(raw.get("end", 5.0)),
        animation=str(raw.get("animation", "fade")),
        fade_in=float(raw.get("fade_in", 0.4)),
        fade_out=float(raw.get("fade_out", 0.4)),
        fontsize=int(raw.get("fontsize", 48)),
        fontcolor=str(raw.get("fontcolor", "white")),
        fontfile=raw.get("fontfile"),
        box=bool(raw.get("box", False)),
        boxcolor=str(raw.get("boxcolor", "black@0.5")),
        boxborderw=int(raw.get("boxborderw", 20)),
        scale_w=raw.get("scale_w"),
        scale_h=raw.get("scale_h"),
        uppercase=bool(raw.get("uppercase", False)),
    )


def load_style_preset(name: str) -> StylePreset:
    """
    Load a style preset by name.

    First tries to load from database (tools.VideoPreset model).
    If not found, falls back to JSON file in media_files/video_presets/style.
    """
    try:
        VideoPreset = apps.get_model("tools", "VideoPreset")
        preset = VideoPreset.objects.filter(name=name).first()
        if preset:
            return load_style_preset_from_db(preset)
    except Exception:
        pass

    path = _preset_dir("style") / f"{name}.json"
    data = _load_json(path)

    overlays = data.get("overlays") or {}
    intro_layers = overlays.get("intro") or []
    outro_layers = overlays.get("outro") or []

    return StylePreset(
        name=_require(data, "name"),
        intro_clip=data.get("intro_clip"),
        outro_clip=data.get("outro_clip"),
        intro_overlays=[_parse_layer(x) for x in intro_layers],
        outro_overlays=[_parse_layer(x) for x in outro_layers],
        segment_duration=float(data.get("segment_duration", 5.0)),
    )


def load_style_preset_from_db(preset) -> StylePreset:
    """Load a style preset from tools.VideoPreset database model."""
    intro_layers = []
    outro_layers = []

    for overlay in preset.overlays.filter(segment="intro").order_by("order"):
        intro_layers.append(_parse_layer_from_model(overlay))

    for overlay in preset.overlays.filter(segment="outro").order_by("order"):
        outro_layers.append(_parse_layer_from_model(overlay))

    return StylePreset(
        name=preset.name,
        intro_clip=preset.intro_clip_path or None,
        outro_clip=preset.outro_clip_path or None,
        intro_overlays=intro_layers,
        outro_overlays=outro_layers,
        segment_duration=preset.segment_duration,
    )


def _parse_layer_from_model(overlay) -> OverlayLayer:
    """Convert PresetOverlay model instance to OverlayLayer dataclass."""
    if overlay.overlay_type == "text":
        return OverlayLayer(
            type="text",
            template=overlay.text_template,
            x=overlay.x_position,
            y=overlay.y_position,
            start=overlay.start_time,
            end=overlay.end_time,
            animation=overlay.animation,
            fade_in=overlay.fade_in_duration,
            fade_out=overlay.fade_out_duration,
            fontsize=overlay.font_size,
            fontcolor=overlay.font_color,
            fontfile=overlay.font_file,
            box=overlay.has_box,
            boxcolor=overlay.box_color,
            boxborderw=overlay.box_border_width,
            uppercase=getattr(overlay, "uppercase", False),
        )

    return OverlayLayer(
        type="image",
        path=overlay.image_path,
        x=overlay.x_position,
        y=overlay.y_position,
        start=overlay.start_time,
        end=overlay.end_time,
        animation=overlay.animation,
        fade_in=overlay.fade_in_duration,
        fade_out=overlay.fade_out_duration,
        scale_w=overlay.image_width,
        scale_h=overlay.image_height,
    )


def resolve_preset_asset_path(path_str: str) -> str:
    """
    Resolve a preset asset path.

    - Absolute paths are returned as-is.
    - Relative paths are resolved against `media_files/video_presets/assets/`.
    """
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    assets_base = Path(settings.BASE_DIR) / "media_files" / "video_presets" / "assets"
    return str(assets_base / p)

