"""Render a new video version using intro/outro clips and presets."""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.translation import gettext as _

from licenses.models import License
from media_files.models import FileOperation, VideoFile
from media_files.rendering.ffmpeg import (
    FfmpegError,
    render_with_intro_outro,
    render_with_overlays_on_main_edges,
    render_preview_overlays_on_main_edges,
)
from tools.rendering.presets import (
    PresetError,
    load_encode_preset,
    load_style_preset,
    resolve_preset_asset_path,
)
from media_files.rendering.templates import build_template_context
from media_files.utils import extract_video_metadata


def _pick_source_video_by_number(number: int) -> VideoFile:
    # Best-effort pick: prefer higher bitrate and newer records among available files.
    return (
        VideoFile.objects.filter(number=number, is_available=True)
        .order_by("-total_bitrate", "-created_at")
        .first()
    )


def _apply_metadata(video: VideoFile, abs_path: str) -> None:
    md = extract_video_metadata(abs_path, fast_mode=False)

    if "format" in md:
        video.format = md["format"]
    if "file_size" in md:
        video.file_size = md["file_size"]
    if "duration" in md:
        video.duration = md["duration"]
    if "total_bitrate" in md:
        video.total_bitrate = md["total_bitrate"]

    video.has_video = md.get("has_video", False)
    if video.has_video:
        video.video_codec = md.get("video_codec", "")
        video.video_codec_long = md.get("video_codec_long", "")
        video.video_profile = md.get("video_profile", "")
        video.video_bitrate = md.get("video_bitrate")
        video.fps = md.get("fps")
        video.width = md.get("width")
        video.height = md.get("height")
        video.aspect_ratio = md.get("aspect_ratio", "")
        video.pixel_format = md.get("pixel_format", "")
        video.color_space = md.get("color_space", "")
        video.color_range = md.get("color_range", "")
        video.chroma_subsampling = md.get("chroma_subsampling", "")

    video.has_audio = md.get("has_audio", False)
    if video.has_audio:
        video.audio_codec = md.get("audio_codec", "")
        video.audio_codec_long = md.get("audio_codec_long", "")
        video.audio_bitrate = md.get("audio_bitrate")
        video.audio_sample_rate = md.get("audio_sample_rate")
        video.audio_channels = md.get("audio_channels")
        video.audio_channel_layout = md.get("audio_channel_layout", "")

    if "raw_json" in md:
        video.metadata_json = md["raw_json"]

    video.last_scanned = timezone.now()


def _ensure_unique_output_relpath(storage_location, number: int, rel_path: Path) -> Path:
    """
    Ensure a unique output path for the (number, storage_location, file_path) constraint.

    We must consider both:
    - the filesystem (file exists)
    - the database (VideoFile row already exists even if the file is missing)
    """
    storage_root = Path(storage_location.path)

    def taken(candidate_rel: Path) -> bool:
        cand_str = str(candidate_rel).replace("\\", "/")
        if (storage_root / candidate_rel).exists():
            return True
        return VideoFile.objects.filter(
            number=number,
            storage_location=storage_location,
            file_path=cand_str,
        ).exists()

    if not taken(rel_path):
        return rel_path

    stem = rel_path.stem
    suffix = rel_path.suffix
    parent = rel_path.parent
    for i in range(2, 1000):
        candidate = parent / f"{stem}__v{i}{suffix}"
        if not taken(candidate):
            return candidate

    raise CommandError(_("Could not find a free output filename (too many collisions)."))


def _ensure_unique_output_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    for i in range(2, 1000):
        candidate = parent / f"{stem}__v{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise CommandError(_("Could not find a free output filename (too many collisions)."))


class Command(BaseCommand):
    """Render a new VideoFile version using presets."""

    help = "Render a new video version using intro/outro clips and overlay presets."

    def add_arguments(self, parser):
        parser.add_argument("--video-id", type=int, help=_("Source VideoFile ID to render"))
        parser.add_argument(
            "--license-number",
            type=int,
            help=_("License number (will pick the best available VideoFile by that number)"),
        )
        parser.add_argument("--style", required=True, help=_("Style preset name"))
        parser.add_argument("--encode", required=True, help=_("Encoding preset name"))
        parser.add_argument(
            "--preview",
            action="store_true",
            help=_("Render a fast preview: first N seconds + last N seconds only (no full-length transcode)"),
        )
        parser.add_argument(
            "--preview-seconds",
            type=float,
            default=5.0,
            help=_("Preview seconds for start and end (default: 5.0)"),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Print what would be done without rendering or writing anything"),
        )
        parser.add_argument(
            "--intro-clip",
            type=str,
            help=_("Path to intro clip (overrides preset intro_clip)"),
        )
        parser.add_argument(
            "--outro-clip",
            type=str,
            help=_("Path to outro clip (overrides preset outro_clip)"),
        )

    def handle(self, *args, **options):
        from media_files.config import get_video_overlay_rendering_enabled
        if not get_video_overlay_rendering_enabled():
            raise CommandError(
                _(
                    "Video overlay rendering is disabled. Enable it in Media Files Configuration."
                )
            )

        video_id = options.get("video_id")
        license_number = options.get("license_number")
        style_name = options["style"]
        encode_name = options["encode"]
        dry_run = bool(options.get("dry_run"))
        preview = bool(options.get("preview"))
        preview_seconds = float(options.get("preview_seconds") or 5.0)

        if not video_id and not license_number:
            raise CommandError(_("Specify --video-id or --license-number."))
        if video_id and license_number:
            raise CommandError(_("Provide only one: --video-id OR --license-number."))

        if video_id:
            try:
                source = VideoFile.objects.get(pk=video_id)
            except VideoFile.DoesNotExist as e:
                raise CommandError(_("VideoFile with id {id} not found.").format(id=video_id)) from e
        else:
            source = _pick_source_video_by_number(int(license_number))
            if not source:
                raise CommandError(
                    _("No available VideoFile found for license number {n}.").format(n=license_number)
                )

        license_obj = source.get_license()
        if not license_obj:
            raise CommandError(
                _("No License found for video number {n}.").format(n=source.number)
            )

        try:
            style = load_style_preset(style_name)
            encode = load_encode_preset(encode_name)
        except PresetError as e:
            raise CommandError(str(e)) from e

        # Allow command-line override of intro/outro clips
        intro_clip_override = options.get("intro_clip")
        outro_clip_override = options.get("outro_clip")
        
        if intro_clip_override:
            intro_clip = intro_clip_override
        else:
            intro_clip = resolve_preset_asset_path(style.intro_clip) if style.intro_clip else None
        
        if outro_clip_override:
            outro_clip = outro_clip_override
        else:
            outro_clip = resolve_preset_asset_path(style.outro_clip) if style.outro_clip else None

        if intro_clip and not os.path.exists(intro_clip):
            raise CommandError(_("Intro clip not found: {p}").format(p=intro_clip))
        if outro_clip and not os.path.exists(outro_clip):
            raise CommandError(_("Outro clip not found: {p}").format(p=outro_clip))

        storage_root = Path(source.storage_location.path)
        rel_dir = Path("rendered") / style.name / encode.name

        src_stem = Path(source.filename).stem
        if preview:
            out_name = f"{src_stem}__preview__{int(preview_seconds)}s__{style.name}__{encode.name}.mp4"
        else:
            out_name = f"{src_stem}__rendered__{style.name}__{encode.name}.mp4"

        rel_out = _ensure_unique_output_relpath(source.storage_location, source.number, rel_dir / out_name)
        abs_out = storage_root / rel_out
        abs_out.parent.mkdir(parents=True, exist_ok=True)

        self.stdout.write(
            _("Source: {src}").format(src=source.full_path)
        )
        self.stdout.write(
            _("Output: {dst}").format(dst=str(abs_out))
        )

        if dry_run:
            self.stdout.write(self.style.WARNING(_("Dry-run: nothing was rendered.")))
            return

        ctx = build_template_context(license_obj)

        operation = None
        new_video = None
        try:
            new_video = VideoFile.objects.create(
                number=source.number,
                filename=abs_out.name,
                file_path=str(rel_out).replace("\\", "/"),
                storage_location=source.storage_location,
                is_available=True,
                is_preview=preview,
                # Do NOT set `license` here: VideoFile.license is OneToOneField.
            )

            operation = FileOperation.objects.create(
                video_file=new_video,
                operation_type="RENDER",
                source_location=source.storage_location,
                destination_location=source.storage_location,
                status="IN_PROGRESS",
                details={
                    "source_video_id": source.id,
                    "style": style.name,
                    "encode": encode.name,
                    "intro_clip": intro_clip,
                    "outro_clip": outro_clip,
                },
            )

            if preview:
                render_preview_overlays_on_main_edges(
                    main_video=source.full_path,
                    output_mp4=str(abs_out),
                    encode=encode,
                    intro_layers=style.intro_overlays,
                    outro_layers=style.outro_overlays,
                    ctx=ctx,
                    segment_duration=preview_seconds,
                )
            elif intro_clip and outro_clip:
                render_with_intro_outro(
                    intro_video=intro_clip,
                    main_video=source.full_path,
                    outro_video=outro_clip,
                    output_mp4=str(abs_out),
                    encode=encode,
                    intro_layers=style.intro_overlays,
                    outro_layers=style.outro_overlays,
                    ctx=ctx,
                )
            else:
                render_with_overlays_on_main_edges(
                    main_video=source.full_path,
                    output_mp4=str(abs_out),
                    encode=encode,
                    intro_layers=style.intro_overlays,
                    outro_layers=style.outro_overlays,
                    ctx=ctx,
                    segment_duration=style.segment_duration,
                )

            _apply_metadata(new_video, str(abs_out))
            new_video.save()

            operation.status = "SUCCESS"
            operation.save(update_fields=["status"])

            self.stdout.write(self.style.SUCCESS(_("Rendered successfully.")))
            self.stdout.write(_("New VideoFile id: {id}").format(id=new_video.id))

        except FfmpegError as e:
            if operation:
                operation.status = "FAILED"
                operation.error_message = str(e)
                operation.save(update_fields=["status", "error_message"])
            if new_video:
                new_video.is_available = False
                new_video.save(update_fields=["is_available"])
            raise CommandError(str(e)) from e
        except Exception as e:
            if operation:
                operation.status = "FAILED"
                operation.error_message = str(e)
                operation.save(update_fields=["status", "error_message"])
            if new_video:
                new_video.is_available = False
                new_video.save(update_fields=["is_available"])
            raise


