"""Celery tasks for the media_files app."""

import os
from pathlib import Path

from celery import shared_task
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
import logging

from media_files.models import FileOperation, VideoFile
from licenses.models import License

logger = logging.getLogger(__name__)


@shared_task(name="media_files.tasks.run_auto_scan")
def run_auto_scan_task(**kwargs):
    """Run the auto_scan management command."""
    logger.info("Starting auto_scan task...")
    
    args = []
    if kwargs.get("delete_missing"):
        args.append("--delete-missing")
    if kwargs.get("force"):
        args.append("--force")
    if kwargs.get("skip_metadata"):
        args.append("--skip-metadata")
    if kwargs.get("strict_check"):
        args.append("--strict-check")
    if kwargs.get("calculate_checksums"):
        args.append("--calculate-checksums")
    if kwargs.get("storage_type"):
        args.extend(["--storage-type", kwargs["storage_type"]])
    
    call_command("auto_scan", *args)
    logger.info("Finished auto_scan task.")


@shared_task(name="media_files.tasks.run_link_orphan_licenses")
def run_link_orphan_licenses_task():
    """Run the link_orphan_licenses management command."""
    logger.info("Starting link_orphan_licenses task...")
    call_command("link_orphan_licenses")
    logger.info("Finished link_orphan_licenses task.")


@shared_task(name="media_files.tasks.run_sync_licenses_videos")
def run_sync_licenses_videos_task():
    """Run the sync_licenses_videos management command."""
    logger.info("Starting sync_licenses_videos task...")
    call_command("sync_licenses_videos")
    logger.info("Finished sync_licenses_videos task.")


@shared_task(name="media_files.tasks.run_update_video_metadata")
def run_update_video_metadata_task(**kwargs):
    """Run the update_video_metadata management command."""
    logger.info(f"Starting update_video_metadata task with args: {kwargs}")
    args = ["--all"]
    if kwargs.get("missing_only"):
        args.append("--missing-only")
    call_command("update_video_metadata", *args)
    logger.info("Finished update_video_metadata task.")


@shared_task(name="media_files.tasks.run_cleanup_old_file_operations")
def run_cleanup_old_file_operations_task(**kwargs):
    """Run the cleanup_old_file_operations management command."""
    logger.info("Starting cleanup_old_file_operations task...")
    older_than_days = kwargs.get("older_than_days", 30)
    keep_failed = kwargs.get("keep_failed", True)
    
    args = []
    if older_than_days:
        args.extend(["--older-than-days", str(older_than_days)])
    if keep_failed:
        args.append("--keep-failed")
    
    call_command("cleanup_old_file_operations", *args)
    logger.info("Finished cleanup_old_file_operations task.")


@shared_task(name="media_files.tasks.run_cleanup_missing_files")
def run_cleanup_missing_files_task(**kwargs):
    """Run the cleanup_missing_files management command."""
    logger.info("Starting cleanup_missing_files task...")
    
    args = []
    if kwargs.get("all_storages"):
        args.append("--all-storages")
    elif kwargs.get("storage_id"):
        args.extend(["--storage-id", str(kwargs["storage_id"])])
    else:
        # Default: check all storages
        args.append("--all-storages")
    
    if kwargs.get("mark_unavailable"):
        args.append("--mark-unavailable")
    
    call_command("cleanup_missing_files", *args)
    logger.info("Finished cleanup_missing_files task.")


@shared_task(name="media_files.tasks.render_video_task")
def render_video_task(operation_id):
    """
    Render video with overlays asynchronously via Celery.
    
    Args:
        operation_id: FileOperation ID that contains all rendering parameters in details field
    """
    logger.info(f"Starting render_video_task for operation_id={operation_id}")
    
    try:
        # Load operation
        operation = FileOperation.objects.get(id=operation_id)
        
        if operation.status != "IN_PROGRESS":
            logger.warning(f"Operation {operation_id} is not IN_PROGRESS, skipping")
            return
        
        # Extract parameters from operation details
        details = operation.details or {}
        source_video_id = details.get("source_video_id")
        license_number = details.get("license_number")
        encode_name = details.get("encode", "1080p25_9000k")
        is_preview = details.get("preview", False)
        use_intro_outro = details.get("use_intro_outro", False)
        overlay_type = details.get("overlay_type")
        elements = details.get("elements", {})
        styles = details.get("styles", {})
        
        # Get source video
        source_video = VideoFile.objects.get(id=source_video_id)
        new_video = operation.video_file
        
        # Get license
        if license_number:
            license_obj = License.objects.get(number=int(license_number))
        else:
            license_obj = License.objects.get(number=source_video.number)
        
        # Build overlays - import here to avoid circular imports
        from media_files.rendering.presets import (
            load_style_preset_from_db,
            load_style_preset,
            load_encode_preset,
        )
        from media_files.rendering.templates import build_template_context
        from media_files.rendering.ffmpeg import (
            render_with_intro_outro,
            render_with_overlays_on_main_edges,
            render_preview_overlays_on_main_edges,
            FfmpegError,
        )
        from django.conf import settings as django_settings
        from media_files.models import VideoPreset
        from media_files.utils import extract_video_metadata_fast
        
        # Check if this is full intro/outro overlay type (from admin action)
        if overlay_type == "full_intro_outro":
            # Use predefined full overlays (title, subtitle, broadcast_resp, media_authority)
            from media_files.rendering.presets import OverlayLayer
            
            default_font = "fonts/Roboto-Bold.ttf"
            regular_font = "fonts/Roboto-Regular.ttf"
            
            # Intro overlays with full text elements
            intro_overlays = [
                # Title - centered horizontally, positioned below center for combined 4-line block
                OverlayLayer(
                    type="text",
                    template="{license.title_wrapped_short}",
                    x="(W-text_w)/2",  # Proper horizontal centering
                    y="(H/2)+70",  # Slightly above center, accounting for title + subtitle block (max 4 lines total)
                    start=0.0,
                    end=5.0,
                    animation="fade",
                    fade_in=0.6,
                    fade_out=0.6,
                    fontsize=64,
                    fontcolor="white",
                    fontfile=default_font,
                    box=False,
                ),
                # Subtitle - centered horizontally, close below title (max 4 lines total: title + subtitle)
                OverlayLayer(
                    type="text",
                    template="{license.subtitle_wrapped}",
                    x="(W-text_w)/2",  # Proper horizontal centering
                    y="(H/2)+220",  # Close below title, forming a combined centered block
                    start=0.2,
                    end=5.0,
                    animation="fade",
                    fade_in=0.5,
                    fade_out=0.4,
                    fontsize=48,
                    fontcolor="white",
                    fontfile=regular_font,
                    box=False,
                ),
                # Broadcast responsibility - right-aligned, bottom
                OverlayLayer(
                    type="text",
                    template="{labels.broadcast_responsibility}: {profile.display}",
                    x="w-text_w-120",  # More padding from right edge
                    y="882",
                    start=0.2,
                    end=5.0,
                    animation="slide_up",
                    fade_in=0.5,
                    fade_out=0.4,
                    fontsize=50,
                    fontcolor="white",
                    fontfile=regular_font,
                ),
                # Media authority - right-aligned, bottom
                OverlayLayer(
                    type="text",
                    template="{profile.media_authority_full_name}, {license.created_year}",
                    x="w-text_w-120",  # More padding from right edge
                    y="947",
                    start=0.2,
                    end=5.0,
                    animation="slide_left",
                    fade_in=0.6,
                    fade_out=0.4,
                    fontsize=38,
                    fontcolor="white",
                    fontfile=regular_font,
                ),
            ]
            
            # Outro overlays (same structure)
            outro_overlays = [
                # Title - centered horizontally, positioned below center for combined 4-line block
                OverlayLayer(
                    type="text",
                    template="{license.title_wrapped_short}",
                    x="(W-text_w)/2",  # Proper horizontal centering
                    y="(H/2)-20",  # Slightly above center, accounting for title + subtitle block (max 4 lines total)
                    start=0.0,
                    end=5.0,
                    animation="fade",
                    fade_in=0.6,
                    fade_out=0.6,
                    fontsize=64,
                    fontcolor="white",
                    fontfile=default_font,
                    box=False,
                ),
                # Subtitle - centered horizontally, close below title (max 4 lines total: title + subtitle)
                OverlayLayer(
                    type="text",
                    template="{license.subtitle_wrapped}",
                    x="(W-text_w)/2",  # Proper horizontal centering
                    y="(H/2)+140",  # Close below title, forming a combined centered block
                    start=0.2,
                    end=5.0,
                    animation="fade",
                    fade_in=0.5,
                    fade_out=0.4,
                    fontsize=48,
                    fontcolor="white",
                    fontfile=regular_font,
                    box=False,
                ),
                # Broadcast responsibility
                OverlayLayer(
                    type="text",
                    template="{labels.broadcast_responsibility}: {profile.display}",
                    x="w-text_w-120",  # More padding from right edge
                    y="882",
                    start=0.2,
                    end=5.0,
                    animation="slide_up",
                    fade_in=0.5,
                    fade_out=0.4,
                    fontsize=50,
                    fontcolor="white",
                    fontfile=regular_font,
                ),
                # Media authority
                OverlayLayer(
                    type="text",
                    template="{profile.media_authority_full_name}, {license.created_year}",
                    x="w-text_w-120",  # More padding from right edge
                    y="947",
                    start=0.2,
                    end=5.0,
                    animation="slide_left",
                    fade_in=0.6,
                    fade_out=0.4,
                    fontsize=38,
                    fontcolor="white",
                    fontfile=regular_font,
                ),
            ]
            segment_duration = 5.0
            # Get intro/outro paths from details (will search for files if not provided)
            intro_path = details.get("intro_clip")
            outro_path = details.get("outro_clip")
            # use_intro_outro will be set after file search if needed
        else:
            # Build overlays based on selected elements and their styles
            intro_overlays = []
            outro_overlays = []
            segment_duration = 5.0
            intro_path = None
            outro_path = None
            intro_path = None
            outro_path = None
        
        def filter_overlays_by_element(overlays, element_type):
            """Filter overlays to only include text overlays relevant to the specified element type."""
            filtered = []
            excluded_templates = []
            
            # Define templates that should be excluded for each element type
            if element_type == "title":
                excluded_templates = [
                    "{license.subtitle",
                    "{labels.broadcast_responsibility",
                    "{profile.media_authority_full_name",
                    "{license.created_year}",
                ]
            elif element_type == "subtitle":
                excluded_templates = [
                    "{license.title",
                    "{labels.broadcast_responsibility",
                    "{profile.media_authority_full_name",
                    "{license.created_year}",
                ]
            elif element_type == "broadcast_resp":
                excluded_templates = [
                    "{license.title",
                    "{license.title_line_wrapped",
                    "{license.subtitle",
                    "{profile.media_authority_full_name",
                    "{license.created_year}",
                ]
            elif element_type == "media_authority":
                excluded_templates = [
                    "{license.title",
                    "{license.title_line_wrapped",
                    "{license.subtitle",
                    "{labels.broadcast_responsibility",
                    "{profile.display}",
                ]
            
            for overlay in overlays:
                # Skip image overlays (logos) - only include text overlays
                if overlay.type == "image":
                    continue
                elif overlay.type == "text" and overlay.template:
                    template = overlay.template.lower()
                    # Exclude overlays that clearly belong to other elements
                    should_exclude = any(excluded in template for excluded in excluded_templates)
                    if not should_exclude:
                        filtered.append(overlay)
            return filtered
        
        # Process each selected element with its style
        show_title = elements.get("title", False)
        show_subtitle = elements.get("subtitle", False)
        show_broadcast_resp = elements.get("broadcast_resp", False)
        show_media_authority = elements.get("media_authority", False)
        
        style_title = styles.get("title")
        style_subtitle = styles.get("subtitle")
        style_broadcast = styles.get("broadcast")
        style_authority = styles.get("authority")
        
        if show_title and style_title:
            try:
                try:
                    db_preset = VideoPreset.objects.get(name=style_title)
                    style_preset = load_style_preset_from_db(db_preset)
                except VideoPreset.DoesNotExist:
                    style_preset = load_style_preset(style_title)
                
                title_intro = filter_overlays_by_element(style_preset.intro_overlays, "title")
                title_outro = filter_overlays_by_element(style_preset.outro_overlays, "title")
                intro_overlays.extend(title_intro)
                outro_overlays.extend(title_outro)
                segment_duration = max(segment_duration, style_preset.segment_duration)
            except Exception as e:
                logger.warning(f"Failed to load title style {style_title}: {e}")
        
        if show_subtitle and style_subtitle:
            try:
                try:
                    db_preset = VideoPreset.objects.get(name=style_subtitle)
                    style_preset = load_style_preset_from_db(db_preset)
                except VideoPreset.DoesNotExist:
                    style_preset = load_style_preset(style_subtitle)
                
                subtitle_intro = filter_overlays_by_element(style_preset.intro_overlays, "subtitle")
                subtitle_outro = filter_overlays_by_element(style_preset.outro_overlays, "subtitle")
                intro_overlays.extend(subtitle_intro)
                outro_overlays.extend(subtitle_outro)
                segment_duration = max(segment_duration, style_preset.segment_duration)
            except Exception as e:
                logger.warning(f"Failed to load subtitle style {style_subtitle}: {e}")
        
        if show_broadcast_resp and style_broadcast:
            try:
                try:
                    db_preset = VideoPreset.objects.get(name=style_broadcast)
                    style_preset = load_style_preset_from_db(db_preset)
                except VideoPreset.DoesNotExist:
                    style_preset = load_style_preset(style_broadcast)
                
                broadcast_intro = filter_overlays_by_element(style_preset.intro_overlays, "broadcast_resp")
                broadcast_outro = filter_overlays_by_element(style_preset.outro_overlays, "broadcast_resp")
                intro_overlays.extend(broadcast_intro)
                outro_overlays.extend(broadcast_outro)
                segment_duration = max(segment_duration, style_preset.segment_duration)
            except Exception as e:
                logger.warning(f"Failed to load broadcast style {style_broadcast}: {e}")
        
        if show_media_authority and style_authority:
            try:
                try:
                    db_preset = VideoPreset.objects.get(name=style_authority)
                    style_preset = load_style_preset_from_db(db_preset)
                except VideoPreset.DoesNotExist:
                    style_preset = load_style_preset(style_authority)
                
                authority_intro = filter_overlays_by_element(style_preset.intro_overlays, "media_authority")
                authority_outro = filter_overlays_by_element(style_preset.outro_overlays, "media_authority")
                intro_overlays.extend(authority_intro)
                outro_overlays.extend(authority_outro)
                segment_duration = max(segment_duration, style_preset.segment_duration)
            except Exception as e:
                logger.warning(f"Failed to load authority style {style_authority}: {e}")
        
        if overlay_type != "full_intro_outro" and not intro_overlays:
            raise ValueError("No valid presets found for selected elements")
        
        # Load encoding preset
        encode = load_encode_preset(encode_name)
        
        # Get absolute paths
        source_path = Path(source_video.full_path)
        abs_out = Path(new_video.storage_location.path) / new_video.file_path
        
        # Verify source video exists
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"Source video file not found: {source_video.full_path}")
        
        # Ensure output directory exists
        abs_out.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine paths to intro and outro files
        # In production: ./data/media is mounted to /app/media
        # In local dev: docker-local/data/media is mounted to /app/media
        # Files should be placed in: <media_root>/intro_outro/intro.mp4 and outro.mp4
        
        from django.conf import settings as django_settings
        media_root = Path(django_settings.MEDIA_ROOT)
        base_dir = Path(django_settings.BASE_DIR)
        
        intro_path = None
        outro_path = None
        
        # Build list of candidate paths in order of preference
        # 1. MEDIA_ROOT/intro_outro/ (works for both production and local)
        # 2. /app/media/intro_outro/ (Docker path - production and local)
        # 3. BASE_DIR relative paths (for local development)
        
        # Only search for intro/outro files if not already provided in details
        if overlay_type != "full_intro_outro" or not intro_path or not outro_path:
            intro_candidates = [
                # Primary: MEDIA_ROOT (works everywhere)
                media_root / "intro_outro" / "intro.mp4",
                # Docker paths (production: ./data/media -> /app/media, local: docker-local/data/media -> /app/media)
                Path("/app/media/intro_outro/intro.mp4"),
                # Local development paths (relative to BASE_DIR)
                base_dir / "docker-local" / "data" / "media" / "intro_outro" / "intro.mp4",
                base_dir / "media" / "intro_outro" / "intro.mp4",
            ]
            outro_candidates = [
                # Primary: MEDIA_ROOT (works everywhere)
                media_root / "intro_outro" / "outro.mp4",
                # Docker paths (production: ./data/media -> /app/media, local: docker-local/data/media -> /app/media)
                Path("/app/media/intro_outro/outro.mp4"),
                # Local development paths (relative to BASE_DIR)
                base_dir / "docker-local" / "data" / "media" / "intro_outro" / "outro.mp4",
                base_dir / "media" / "intro_outro" / "outro.mp4",
            ]
            
            if not intro_path:
                for candidate in intro_candidates:
                    try:
                        if candidate.exists() and candidate.is_file():
                            intro_path = str(candidate.resolve())
                            logger.info(f"Found intro file at: {intro_path}")
                            break
                    except (OSError, ValueError):
                        continue
            
            if not outro_path:
                for candidate in outro_candidates:
                    try:
                        if candidate.exists() and candidate.is_file():
                            outro_path = str(candidate.resolve())
                            logger.info(f"Found outro file at: {outro_path}")
                            break
                    except (OSError, ValueError):
                        continue
        
        # For full_intro_outro type, ensure use_intro_outro is set correctly
        if overlay_type == "full_intro_outro":
            use_intro_outro = bool(intro_path and outro_path)
            if not use_intro_outro:
                error_msg = "Intro/outro files not found for full_intro_outro overlay type"
                if not intro_path:
                    error_msg += " (intro file missing)"
                if not outro_path:
                    error_msg += " (outro file missing)"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        
        # Render video
        ctx = build_template_context(license_obj)
        
        if is_preview:
            # Preview mode: always use overlay-only mode (no intro/outro clips)
            render_preview_overlays_on_main_edges(
                main_video=str(source_path),
                output_mp4=str(abs_out),
                encode=encode,
                intro_layers=intro_overlays,
                outro_layers=outro_overlays,
                ctx=ctx,
                segment_duration=segment_duration,
            )
        elif use_intro_outro:
            # User explicitly requested intro/outro mode
            if intro_path and outro_path:
                # Use intro/outro clips with overlays
                logger.info(f"Rendering with intro/outro clips: intro={intro_path}, outro={outro_path}")
                render_with_intro_outro(
                    intro_video=intro_path,
                    main_video=str(source_path),
                    outro_video=outro_path,
                    output_mp4=str(abs_out),
                    encode=encode,
                    intro_layers=intro_overlays,
                    outro_layers=outro_overlays,
                    ctx=ctx,
                )
            else:
                # Files not found but user requested intro/outro mode
                error_msg = "Intro/outro mode requested but files not found"
                if not intro_path:
                    error_msg += f" (intro file missing)"
                if not outro_path:
                    error_msg += f" (outro file missing)"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        else:
            # Overlay-only mode (overlays on main video edges) - default behavior
            logger.info("Rendering with overlays on main video edges (no intro/outro clips)")
            render_with_overlays_on_main_edges(
                main_video=str(source_path),
                output_mp4=str(abs_out),
                encode=encode,
                intro_layers=intro_overlays,
                outro_layers=outro_overlays,
                ctx=ctx,
                segment_duration=segment_duration,
            )
        
        # Update metadata
        with transaction.atomic():
            # Before saving, handle OneToOne license constraint:
            # If license already has a linked VideoFile, unlink it first
            # The signal will then link the new VideoFile automatically
            if license_obj.video_file and license_obj.video_file.id != new_video.id:
                old_video = license_obj.video_file
                VideoFile.objects.filter(pk=old_video.pk).update(license=None)
                logger.info(f"Unlinked old VideoFile {old_video.id} from License {license_obj.number} before saving new VideoFile {new_video.id}")
            
            metadata = extract_video_metadata_fast(str(abs_out))
            new_video.format = metadata.get('format', '')
            new_video.duration = metadata.get('duration')
            new_video.file_size = os.path.getsize(str(abs_out))
            new_video.has_video = metadata.get('has_video', False)
            new_video.video_codec = metadata.get('video_codec', '')
            new_video.fps = metadata.get('fps')
            new_video.width = metadata.get('width')
            new_video.height = metadata.get('height')
            new_video.has_audio = metadata.get('has_audio', False)
            new_video.audio_codec = metadata.get('audio_codec', '')
            new_video.audio_channels = metadata.get('audio_channels')
            new_video.total_bitrate = metadata.get('total_bitrate')
            new_video.is_available = True
            new_video.save()
            
            operation.status = "SUCCESS"
            operation.save(update_fields=["status"])
        
        logger.info(f"Successfully rendered video for operation_id={operation_id}, video_id={new_video.id}")
        
    except FileOperation.DoesNotExist:
        logger.error(f"FileOperation {operation_id} not found")
        raise
    except VideoFile.DoesNotExist:
        logger.error(f"VideoFile not found for operation_id={operation_id}")
        with transaction.atomic():
            operation = FileOperation.objects.get(id=operation_id)
            operation.status = "FAILED"
            operation.error_message = "Source video file not found"
            operation.save(update_fields=["status", "error_message"])
        raise
    except License.DoesNotExist:
        logger.error(f"License not found for operation_id={operation_id}")
        with transaction.atomic():
            operation = FileOperation.objects.get(id=operation_id)
            operation.status = "FAILED"
            operation.error_message = "License not found"
            operation.save(update_fields=["status", "error_message"])
        raise
    except FfmpegError as e:
        logger.error(f"FFmpeg error during rendering for operation_id={operation_id}: {e}")
        with transaction.atomic():
            operation = FileOperation.objects.get(id=operation_id)
            new_video = operation.video_file
            new_video.is_available = False
            new_video.save(update_fields=["is_available"])
            operation.status = "FAILED"
            operation.error_message = str(e)
            operation.save(update_fields=["status", "error_message"])
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during rendering for operation_id={operation_id}")
        with transaction.atomic():
            operation = FileOperation.objects.get(id=operation_id)
            new_video = operation.video_file
            new_video.is_available = False
            new_video.save(update_fields=["is_available"])
            operation.status = "FAILED"
            operation.error_message = str(e)
            operation.save(update_fields=["status", "error_message"])
        raise


def _copy_video_to_storage(source_video, destination_storage, user, destination_subfolder=None):
    """
    Helper function to copy video to storage location.
    
    Args:
        source_video: VideoFile instance to copy
        destination_storage: Destination StorageLocation
        user: User performing operation (optional)
        destination_subfolder: Optional subfolder (e.g., "2025_KW_41")
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    from media_files.models import VideoFile, FileOperation
    from media_files.utils import (
        copy_file_with_progress,
        check_duplicate_before_copy,
    )
    from pathlib import Path
    import os
    
    try:
        # Check for duplicates
        is_dup, existing, dup_msg = check_duplicate_before_copy(
            source_video, destination_storage
        )
        
        if is_dup and existing:
            # Check if it's the same file (same checksum) or different
            if source_video.checksum and existing.checksum:
                if source_video.checksum == existing.checksum:
                    # Identical file - just update file_path if needed
                    if destination_subfolder and not existing.file_path.startswith(destination_subfolder):
                        # Move to correct weekly folder
                        old_path = Path(destination_storage.path) / existing.file_path
                        new_path = Path(destination_storage.path) / destination_subfolder / source_video.filename
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        if old_path.exists():
                            os.rename(str(old_path), str(new_path))
                        existing.file_path = f"{destination_subfolder}/{source_video.filename}"
                        existing.save(update_fields=['file_path'])
                    return True, f"Video already exists (identical file)"
                else:
                    # Different file with same number - skip to avoid overwrite
                    return False, f"Different file with same number exists: {dup_msg}"
            else:
                # No checksum - compare by size
                if source_video.file_size == existing.file_size:
                    return True, f"Video already exists (same size)"
                else:
                    return False, f"Different file with same number exists: {dup_msg}"
        
        # Build destination path
        if destination_subfolder:
            dest_path = Path(destination_storage.path) / destination_subfolder / source_video.filename
            file_path = f"{destination_subfolder}/{source_video.filename}"
        else:
            dest_path = Path(destination_storage.path) / source_video.filename
            file_path = source_video.filename
        
        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create operation record
        operation = FileOperation.objects.create(
            video_file=source_video,
            operation_type='COPY',
            source_location=source_video.storage_location,
            destination_location=destination_storage,
            performed_by=user,
            status='IN_PROGRESS',
        )
        
        # Copy the file
        success, message = copy_file_with_progress(
            str(source_video.full_path), 
            str(dest_path),
            verify_checksum=True
        )
        
        if not success:
            operation.status = 'FAILED'
            operation.error_message = message
            operation.save()
            return False, message
        
        # Create new VideoFile record with all metadata
        new_video = VideoFile.objects.create(
            number=source_video.number,
            filename=source_video.filename,
            file_path=file_path,
            storage_location=destination_storage,
            is_available=True,
            format=source_video.format,
            file_size=source_video.file_size,
            duration=source_video.duration,
            checksum=source_video.checksum,
            has_video=source_video.has_video,
            has_audio=source_video.has_audio,
            video_codec=source_video.video_codec,
            video_codec_long=source_video.video_codec_long,
            video_profile=source_video.video_profile,
            video_bitrate=source_video.video_bitrate,
            video_bitrate_mode=source_video.video_bitrate_mode,
            audio_codec=source_video.audio_codec,
            audio_codec_long=source_video.audio_codec_long,
            audio_bitrate=source_video.audio_bitrate,
            audio_sample_rate=source_video.audio_sample_rate,
            audio_channels=source_video.audio_channels,
            width=source_video.width,
            height=source_video.height,
            fps=source_video.fps,
            aspect_ratio=source_video.aspect_ratio,
            pixel_format=source_video.pixel_format,
            color_space=source_video.color_space,
            color_range=source_video.color_range,
            chroma_subsampling=source_video.chroma_subsampling,
            total_bitrate=source_video.total_bitrate,
            last_scanned=timezone.now(),
        )
        
        # Update operation with new video reference
        operation.video_file = new_video
        operation.status = 'SUCCESS'
        operation.save()
        
        logger.info(f"Created VideoFile record {new_video.id} for video {new_video.number} in {destination_storage.name}")
        return True, f"Video copied successfully"
        
    except Exception as e:
        error_msg = f'Error copying video: {str(e)}'
        logger.error(error_msg, exc_info=True)
        
        if 'operation' in locals():
            operation.status = 'FAILED'
            operation.error_message = error_msg
            operation.save()
        
        return False, error_msg


def _delete_source_from_custom(source_video, user):
    """
    Delete video file and VideoFile record from CUSTOM storage after successful copy.
    
    Args:
        source_video: VideoFile instance from CUSTOM storage
        user: User performing operation (optional)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    from media_files.models import FileOperation
    from pathlib import Path
    import os
    
    try:
        # Only delete if source is CUSTOM storage
        if source_video.storage_location.storage_type != 'CUSTOM':
            return False, "Source is not CUSTOM storage"
        
        # Check if file exists
        full_path = Path(source_video.full_path)
        file_exists = full_path.exists()
        
        if not file_exists:
            logger.warning(f"Source file does not exist: {full_path}")
            # Delete record anyway if file is missing
            video_id = source_video.id
            video_number = source_video.number
            source_video.delete()
            logger.info(f"Deleted source video record {video_number} (ID: {video_id}) - file was already missing")
            return True, "Source file already missing, deleted record"
        
        # Create operation record
        operation = FileOperation.objects.create(
            video_file=source_video,
            operation_type='DELETE',
            source_location=source_video.storage_location,
            destination_location=None,
            performed_by=user,
            status='IN_PROGRESS',
        )
        
        # Delete physical file
        try:
            os.remove(str(full_path))
            logger.info(f"Deleted source file: {full_path}")
        except Exception as e:
            logger.error(f"Error deleting source file {full_path}: {e}")
            operation.status = 'FAILED'
            operation.error_message = f"Error deleting file: {str(e)}"
            operation.save()
            return False, f"Error deleting file: {str(e)}"
        
        # Delete VideoFile record (this will cascade delete related FileOperations)
        video_id = source_video.id
        video_number = source_video.number
        storage_name = source_video.storage_location.name
        
        # Delete the record
        source_video.delete()
        
        # Update operation status
        operation.status = 'SUCCESS'
        operation.save()
        
        logger.info(
            f"Deleted source video {video_number} (ID: {video_id}) from CUSTOM storage "
            f"({storage_name}) - file and database record removed"
        )
        return True, "Source deleted successfully"
        
    except Exception as e:
        error_msg = f'Error deleting source: {str(e)}'
        logger.error(error_msg, exc_info=True)
        
        if 'operation' in locals():
            operation.status = 'FAILED'
            operation.error_message = error_msg
            operation.save()
        
        return False, error_msg


@shared_task(name="media_files.tasks.copy_videos_for_plan")
def copy_videos_for_plan(video_numbers, plan_date, user_id=None):
    """
    Automatically copy videos to archive and playout storage when planning.
    
    Uses smart source selection: prefers CUSTOM if recent, otherwise ARCHIVE.
    
    Args:
        video_numbers: List of video numbers (license numbers)
        plan_date: Date object from planning
        user_id: Optional user ID for operation tracking
        
    Returns:
        Dictionary with operation results
    """
    from datetime import date
    from pathlib import Path
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from django.conf import settings
    from media_files.models import StorageLocation, VideoFile, FileOperation
    from media_files.utils import select_best_source_video
    
    User = get_user_model()
    user = User.objects.get(id=user_id) if user_id else None
    
    logger.info(f"[AUTO-COPY] Starting auto-copy for plan date {plan_date}, {len(video_numbers)} videos")
    
    # Get storage locations
    archive_storage = None
    if getattr(settings, 'VIDEO_AUTO_COPY_TO_ARCHIVE', False):
        archive_storage = StorageLocation.objects.filter(
            storage_type='ARCHIVE',
            is_active=True
        ).first()
        if not archive_storage:
            logger.warning("VIDEO_AUTO_COPY_TO_ARCHIVE enabled but no ARCHIVE storage found")
    
    playout_storage = None
    if getattr(settings, 'VIDEO_AUTO_COPY_TO_PLAYOUT', False):
        # Try to find default playout storage (000_Sendungen for main broadcasts)
        default_playout_name = getattr(settings, 'VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME', None)
        default_playout_path = getattr(settings, 'VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH', None)
        
        playout_query = StorageLocation.objects.filter(
            storage_type='PLAYOUT',
            is_active=True
        )
        
        # Priority 1: Use configured name
        if default_playout_name and default_playout_name.strip():
            playout_storage = playout_query.filter(name__icontains=default_playout_name).first()
            if playout_storage:
                logger.info(f"Using playout storage by name '{default_playout_name}': {playout_storage.name}")
        
        # Priority 2: Use configured path
        if not playout_storage and default_playout_path and default_playout_path.strip():
            playout_storage = playout_query.filter(path__icontains=default_playout_path).first()
            if playout_storage:
                logger.info(f"Using playout storage by path '{default_playout_path}': {playout_storage.name}")
        
        # Priority 3: Auto-detect by path (000_Sendungen)
        if not playout_storage:
            playout_storage = playout_query.filter(path__icontains='000_Sendungen').first()
            if playout_storage:
                logger.info(f"Auto-detected playout storage by path '000_Sendungen': {playout_storage.name}")
        
        # Priority 4: Auto-detect by name (Sendungen)
        if not playout_storage:
            playout_storage = playout_query.filter(name__icontains='Sendungen').first()
            if playout_storage:
                logger.info(f"Auto-detected playout storage by name 'Sendungen': {playout_storage.name}")
        
        # Priority 5: Fallback to first available
        if not playout_storage:
            playout_storage = playout_query.first()
            if playout_storage:
                logger.warning(f"Using first available playout storage (fallback): {playout_storage.name}")
        
        if not playout_storage:
            logger.warning("VIDEO_AUTO_COPY_TO_PLAYOUT enabled but no PLAYOUT storage found")
    
    if not archive_storage and not playout_storage:
        logger.warning("No target storages configured for auto-copy")
        return {
            'copied_to_archive': 0,
            'copied_to_playout': 0,
            'skipped': 0,
            'errors': len(video_numbers),
        }
    
    # Calculate calendar week folder name
    use_weekly_folders = getattr(settings, 'VIDEO_USE_WEEKLY_FOLDERS', True)
    if use_weekly_folders and playout_storage:
        year, week, _ = plan_date.isocalendar()
        week_folder = f"{year}_KW_{week:02d}"
    else:
        week_folder = None
    
    copied_to_archive = 0
    copied_to_playout = 0
    skipped = 0
    errors = 0
    operation_details = {'errors': []}
    
    for number in video_numbers:
        try:
            # Use smart source selection
            source_video, selection_reason = select_best_source_video(number)
            
            if not source_video:
                logger.warning(f"Video {number}: Not found in source storages (CUSTOM/ARCHIVE)")
                errors += 1
                operation_details['errors'].append({
                    'number': number,
                    'message': 'Not found in CUSTOM or ARCHIVE storage'
                })
                continue
            
            logger.info(
                f"Video {number}: Selected source from {source_video.storage_location.name} "
                f"({source_video.storage_location.storage_type}) - {selection_reason}"
            )
            
            # Save original source info for potential deletion from CUSTOM
            original_source_type = source_video.storage_location.storage_type
            original_source_id = source_video.id
            should_delete_from_custom = False
            
            # Step 1: Copy to archive if needed
            archive_copy_success = False
            if archive_storage:
                archive_exists = VideoFile.objects.filter(
                    number=number,
                    storage_location=archive_storage,
                    is_available=True
                ).exists()
                
                if not archive_exists:
                    # Copy to archive
                    success, msg = _copy_video_to_storage(
                        source_video, archive_storage, user, 
                        destination_subfolder=None
                    )
                    if success:
                        copied_to_archive += 1
                        archive_copy_success = True
                        logger.info(f"Video {number}: ✓ Copied to archive")
                        # Update source_video to use archive version for next copy
                        source_video = VideoFile.objects.get(
                            number=number,
                            storage_location=archive_storage,
                            is_available=True
                        )
                    else:
                        logger.error(f"Video {number}: ✗ Failed to copy to archive: {msg}")
                        errors += 1
                        operation_details['errors'].append({
                            'number': number,
                            'message': f'Archive copy failed: {msg}'
                        })
                else:
                    archive_copy_success = True  # Already exists, consider as success
                    logger.debug(f"Video {number}: Already in archive, skipping")
            else:
                archive_copy_success = True  # Archive copy not required
            
            # Step 2: Copy to playout in weekly folder
            playout_copy_success = False
            if playout_storage:
                # Check if already exists in this week folder (or root if no weekly folders)
                if week_folder:
                    playout_exists = VideoFile.objects.filter(
                        number=number,
                        storage_location=playout_storage,
                        file_path__startswith=week_folder,
                        is_available=True
                    ).exists()
                else:
                    playout_exists = VideoFile.objects.filter(
                        number=number,
                        storage_location=playout_storage,
                        is_available=True
                    ).exists()
                
                if not playout_exists:
                    success, msg = _copy_video_to_storage(
                        source_video, playout_storage, user,
                        destination_subfolder=week_folder
                    )
                    if success:
                        copied_to_playout += 1
                        playout_copy_success = True
                        logger.info(f"Video {number}: ✓ Copied to playout/{week_folder or 'root'}")
                    else:
                        logger.error(f"Video {number}: ✗ Failed to copy to playout: {msg}")
                        errors += 1
                        operation_details['errors'].append({
                            'number': number,
                            'message': f'Playout copy failed: {msg}'
                        })
                else:
                    playout_copy_success = True  # Already exists, consider as success
                    logger.debug(f"Video {number}: Already in playout/{week_folder or 'root'}, skipping")
                    skipped += 1
            else:
                playout_copy_success = True  # Playout copy not required
                skipped += 1
            
            # Step 3: Delete from CUSTOM if source was CUSTOM and all copies succeeded
            auto_delete_enabled = getattr(settings, 'VIDEO_AUTO_DELETE_FROM_CUSTOM', True)
            if (auto_delete_enabled 
                and original_source_type == 'CUSTOM'
                and archive_copy_success 
                and playout_copy_success):
                
                # Find CUSTOM source video (may have been updated, so reload)
                try:
                    custom_source = VideoFile.objects.filter(
                        id=original_source_id,
                        storage_location__storage_type='CUSTOM',
                        is_available=True
                    ).first()
                    
                    if custom_source:
                        delete_success, delete_msg = _delete_source_from_custom(custom_source, user)
                        if delete_success:
                            logger.info(f"Video {number}: ✓ Deleted from CUSTOM storage (moved to archive/playout)")
                        else:
                            logger.warning(f"Video {number}: ⚠ Failed to delete from CUSTOM: {delete_msg}")
                    else:
                        logger.debug(f"Video {number}: CUSTOM source already deleted or not found")
                except Exception as e:
                    logger.error(f"Video {number}: Error deleting from CUSTOM: {str(e)}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Video {number}: ERROR - {str(e)}", exc_info=True)
            errors += 1
            operation_details['errors'].append({
                'number': number,
                'message': str(e)
            })
    
    logger.info(
        f"[AUTO-COPY] Completed: archive={copied_to_archive}, "
        f"playout={copied_to_playout}, skipped={skipped}, errors={errors}"
    )
    
    return {
        'copied_to_archive': copied_to_archive,
        'copied_to_playout': copied_to_playout,
        'skipped': skipped,
        'errors': errors,
        'details': operation_details
    }
