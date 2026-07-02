"""Celery tasks for Tools module."""

from .models import AudioNormalizeJob
from .models import SlideshowAudio
from .models import SlideshowMedia
from .models import SlideshowProject
from .models import ToolsConfig
from .services.audio_normalizer import AudioNormalizerError
from .services.audio_normalizer import AudioNormalizerService
from .services.video_generator import VideoGenerator
from .services.video_generator import VideoGeneratorError
from .utils import resolve_tools_file_path
from .utils import resolve_tools_output_path
from celery import shared_task
from datetime import date
from datetime import datetime
from datetime import timedelta
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signing import TimestampSigner
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from pathlib import Path
from urllib.parse import urlencode
import logging


logger = logging.getLogger('django')
REEL_REMINDER_MISSING_URL_ATTEMPTS = 6
REEL_REMINDER_MISSING_URL_RETRIES = REEL_REMINDER_MISSING_URL_ATTEMPTS - 1
REEL_REMINDER_MISSING_URL_RETRY_DELAYS = (300, 600, 900, 900, 900)


def _safe_site_base_url() -> str:
    return (getattr(settings, 'SITE_BASE_URL', '') or '').rstrip('/')


def _absolute_url(path: str) -> str:
    base = _safe_site_base_url()
    if not base:
        return ''
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{base}{path}'


def _reel_public_download_url(filename: str) -> str:
    token = TimestampSigner(salt='tools.reel_public_output').sign(filename)
    path = reverse('tools:reel_public_output_stream', args=[filename])
    return _absolute_url(f'{path}?{urlencode({"token": token})}')


def _reel_reminder_missing_url_countdown(retry_number: int) -> int:
    index = max(0, min(retry_number, len(REEL_REMINDER_MISSING_URL_RETRY_DELAYS) - 1))
    return REEL_REMINDER_MISSING_URL_RETRY_DELAYS[index]


def _time_sort_key(value: str) -> tuple[int, int, int]:
    parts = str(value or '').split(':')
    try:
        hour = int(parts[0]) if len(parts) > 0 and parts[0] != '' else 99
        minute = int(parts[1]) if len(parts) > 1 and parts[1] != '' else 59
        second = int(parts[2]) if len(parts) > 2 and parts[2] != '' else 59
    except (TypeError, ValueError):
        return (99, 59, 59)
    return (hour, minute, second)


def _display_time(value: str) -> str:
    value = str(value or '').strip()
    return value[:5] if len(value) >= 5 else value


def _profile_name(profile) -> str:
    if not profile:
        return ''
    return f'{profile.first_name or ""} {profile.last_name or ""}'.strip()


def _license_tags(license_obj) -> list[str]:
    raw_tags = getattr(license_obj, 'tags', None) if license_obj else None
    if isinstance(raw_tags, list):
        return [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    if isinstance(raw_tags, str):
        return [tag.strip() for tag in raw_tags.split(',') if tag.strip()]
    return []


def _try_refresh_mediathek_url(license_obj) -> str:
    """Try one immediate PeerTube lookup for a missing Mediathek URL."""
    if not license_obj or getattr(license_obj, 'mediathek_url', ''):
        return getattr(license_obj, 'mediathek_url', '') or ''
    try:
        from django.db import transaction
        from licenses.services.peertube_service import \
            find_video_by_number_in_channel
        from licenses.services.peertube_service import peertube_watch_url
        from licenses.services.peertube_service import \
            resolve_peertube_endpoint
        from licenses.tasks import _get_org_channel
        from licenses.tasks import _get_peertube_target_channel

        endpoint = resolve_peertube_endpoint(
            target_channel=_get_peertube_target_channel(license_obj),
            organization_channel=_get_org_channel(),
        )
        video = find_video_by_number_in_channel(
            endpoint.base_url,
            endpoint.channel_handle,
            str(license_obj.number),
        )
        if not video:
            logger.info(
                'Mediathek URL not found during reel reminder lookup for license %s',
                license_obj.number,
            )
            return ''

        watch_url = peertube_watch_url(endpoint.base_url, video)
        with transaction.atomic():
            license_obj.mediathek_url = watch_url
            license_obj.mediathek_url_updated_at = timezone.now()
            license_obj.save(update_fields=['mediathek_url', 'mediathek_url_updated_at'])
        logger.info(
            'Updated mediathek URL during reel reminder lookup for license %s: %s',
            license_obj.number,
            watch_url,
        )
        return watch_url
    except Exception:
        logger.exception(
            'Failed mediathek URL lookup during reel reminder for license %s',
            getattr(license_obj, 'number', None),
        )
        return ''


def _today_plan_matches(target_date: date, numbers: set[int]) -> dict[int, list[dict]]:
    if not (
        getattr(settings, 'PLANUNG_ENABLED', False)
        and apps.is_installed('planung')
    ):
        return {}
    try:
        from planung.models import TagesPlan
    except Exception:
        return {}

    plan = TagesPlan.objects.filter(datum=target_date).first()
    if not plan:
        return {}

    matches: dict[int, list[dict]] = {}
    plan_data = plan.json_plan or {}
    for position, item in enumerate(plan_data.get('items', []) or []):
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get('number'))
        except (TypeError, ValueError):
            continue
        if number not in numbers:
            continue
        entry = item.copy()
        entry['_position'] = position
        matches.setdefault(number, []).append(entry)

    for number, entries in matches.items():
        entries.sort(key=lambda item: (_time_sort_key(item.get('start') or ''), item.get('_position', 0)))
    return matches


def _today_reel_videos(target_date: date) -> list:
    if not (
        getattr(settings, 'MEDIA_FILES_ENABLED', False)
        and apps.is_installed('media_files')
    ):
        return []
    try:
        from media_files.models import VideoFile
        from media_files.utils import is_reel_filename
    except Exception:
        return []

    date_marker = target_date.strftime('%y%m%d')
    videos = []
    queryset = (
        VideoFile.objects
        .filter(is_preview=True, is_available=True)
        .select_related('storage_location')
        .order_by('-id')
    )
    seen: set[tuple[int, str]] = set()
    for video in queryset:
        filename = Path(str(video.filename or video.file_path or '')).name
        if not filename or date_marker not in filename:
            continue
        if not (
            is_reel_filename(filename)
            or is_reel_filename(getattr(video, 'file_path', '') or '')
        ):
            continue
        key = (int(video.number), filename)
        if key in seen:
            continue
        seen.add(key)
        videos.append(video)
    return videos


def build_daily_reel_reminder_context(
    target_date: date | None = None,
    *,
    refresh_missing_mediathek: bool = False,
) -> dict:
    """Build the email context for today's sorted reel reminder."""
    target_date = target_date or timezone.localdate()
    videos = _today_reel_videos(target_date)
    numbers = {int(video.number) for video in videos if video.number}
    plan_matches = _today_plan_matches(target_date, numbers)

    licenses_by_number = {}
    if numbers:
        try:
            from licenses.models import License
            licenses = License.objects.filter(number__in=numbers).select_related('profile')
            licenses_by_number = {int(license_obj.number): license_obj for license_obj in licenses}
        except Exception:
            licenses_by_number = {}

    if refresh_missing_mediathek:
        for license_obj in licenses_by_number.values():
            if not getattr(license_obj, 'mediathek_url', ''):
                _try_refresh_mediathek_url(license_obj)

    reels = []
    for video in videos:
        number = int(video.number)
        license_obj = licenses_by_number.get(number)
        matches = plan_matches.get(number, [])
        first_match = matches[0] if matches else {}
        start_time = _display_time(first_match.get('start') or '')
        other_times = [
            _display_time(item.get('start') or '')
            for item in matches[1:]
            if _display_time(item.get('start') or '')
        ]

        sender_responsible = (
            str(first_match.get('sender_responsible') or '').strip()
            or str(first_match.get('author') or '').strip()
            or _profile_name(getattr(license_obj, 'profile', None))
        )
        title = (
            getattr(license_obj, 'title', '') if license_obj else ''
        ) or str(first_match.get('title') or '').strip() or video.filename

        warnings = []
        if not matches:
            warnings.append(
                _('No planning entry was found for this day. Please check the broadcast time or the reel.')
            )
        if other_times:
            warnings.append(
                _('This license has additional broadcast times on this day.')
            )
        if not license_obj:
            warnings.append(_('No license was found for this reel number.'))
        if license_obj and not getattr(license_obj, 'mediathek_url', ''):
            warnings.append(_('No Mediathek URL is available yet. Please check the publication link.'))

        filename = Path(str(video.filename or video.file_path)).name
        reels.append({
            'number': number,
            'filename': filename,
            'title': title,
            'sender_responsible': sender_responsible,
            'start_time': start_time,
            'other_times': other_times,
            'tags': _license_tags(license_obj),
            'mediathek_url': getattr(license_obj, 'mediathek_url', '') or '',
            'download_url': _reel_public_download_url(filename),
            'warnings': warnings,
            'sort_key': (
                0 if start_time else 1,
                _time_sort_key(start_time),
                number,
                filename,
            ),
        })

    reels.sort(key=lambda item: item['sort_key'])
    for item in reels:
        item.pop('sort_key', None)

    return {
        'date': target_date,
        'reels': reels,
        'reel_count': len(reels),
    }


def _record_rendered_reel_video(_payload: dict, result: dict) -> None:
    """Register a finished reel as a preview clip in media_files, when available."""
    if not getattr(settings, 'MEDIA_FILES_ENABLED', False):
        return

    filename = Path(str((result or {}).get('file') or '')).name
    if not filename:
        return

    try:
        from media_files.models import StorageLocation
        from media_files.models import VideoFile
        from media_files.utils import extract_number_from_filename
        from media_files.utils import is_reel_filename
    except Exception:
        return

    number = extract_number_from_filename(filename)
    if not number:
        return

    config = ToolsConfig.get_config()
    storage = config.reel_output_storage
    if not storage:
        storage = (
            StorageLocation.objects
            .filter(storage_type='PLAYOUT', is_active=True)
            .order_by('name')
            .first()
        )
    if not storage or not getattr(storage, 'path', None):
        return

    subdir = (config.reel_output_subdir or '').strip('/\\')
    rel_path = str(Path(subdir) / filename) if subdir else filename
    abs_path = Path(storage.path) / rel_path
    file_exists = abs_path.exists() and abs_path.is_file()

    video, _created = VideoFile.objects.get_or_create(
        number=number,
        storage_location=storage,
        file_path=rel_path,
        defaults={
            'filename': filename,
            'is_available': file_exists,
            'is_preview': True,
        },
    )
    video.filename = filename
    video.is_preview = True
    video.is_available = file_exists
    if file_exists:
        video.file_size = abs_path.stat().st_size
    if not is_reel_filename(filename):
        logger.warning("Registered reel output without reel-like filename: %s", filename)
    video.save()


def _media_root_abs() -> Path:
    media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
    if media_root.is_absolute():
        return media_root.resolve()
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return (base_dir / media_root).resolve()


def check_tools_enabled():
    """Check if Tools module is enabled."""
    if not getattr(settings, 'TOOLS_ENABLED', False):
        raise ImproperlyConfigured(
            'Tools module is disabled. Set TOOLS_ENABLED=true to enable.'
        )


@shared_task(name='tools.tasks.generate_slideshow', queue='render', bind=True, max_retries=2)
def generate_slideshow_task(self, project_id):
    """
    Generate slideshow video asynchronously.
    
    Args:
        project_id: SlideshowProject ID
        
    Returns:
        dict: Status and result information
    """
    check_tools_enabled()
    
    logger.info(f"Starting slideshow generation task for project {project_id}")
    
    try:
        project = SlideshowProject.objects.get(id=project_id)
    except SlideshowProject.DoesNotExist:
        logger.error(f"SlideshowProject {project_id} not found")
        raise
    
    # Update status to processing
    project.status = 'processing'
    project.error_message = ''
    project.save(update_fields=['status', 'error_message'])
    
    try:
        # Initialize generator
        generator = VideoGenerator(project)
        
        # Validate inputs
        generator.validate_media()
        
        # Generate video
        def progress_callback(message):
            """Log progress updates."""
            logger.debug(f"Project {project_id}: {message}")
        
        output_path = generator.generate(progress_callback=progress_callback)
        
        # Save output file to project
        # Check if output is in mounted path
        config = ToolsConfig.get_config()
        output_path_config = config.get_effective_output_path()
        
        # If file is in mounted path, just set the path directly without saving through Django storage
        if output_path_config:
            output_base = Path(output_path_config).resolve()
            try:
                # Check if output_path is under output_base
                rel_path = output_path.relative_to(output_base)
                # File is in mounted path, set path directly
                rel_path_str = str(rel_path).replace("\\", "/")
                project.output_file.name = rel_path_str
                project.save(update_fields=['output_file'])
            except ValueError:
                # File is not under output_base, use default behavior
                from django.core.files import File
                with open(output_path, 'rb') as f:
                    project.output_file.save(
                        output_path.name,
                        File(f),
                        save=True
                    )
        else:
            # No mounted path configured, use default behavior
            from django.core.files import File
            with open(output_path, 'rb') as f:
                project.output_file.save(
                    output_path.name,
                    File(f),
                    save=True
                )
        
        # Update status to completed
        project.status = 'completed'
        project.completed_at = timezone.now()
        project.error_message = ''
        project.save(update_fields=['status', 'completed_at', 'error_message', 'output_file'])
        
        logger.info(
            f"Slideshow generation completed successfully for project {project_id}, "
            f"output: {output_path}"
        )
        
        return {
            'status': 'success',
            'project_id': project_id,
            'output_path': str(output_path)
        }
        
    except VideoGeneratorError as e:
        error_msg = str(e)
        logger.error(
            f"Video generation failed for project {project_id}: {error_msg}",
            exc_info=True
        )
        
        # Update status to failed
        project.status = 'failed'
        project.error_message = error_msg
        project.save(update_fields=['status', 'error_message'])
        
        # Don't retry on VideoGeneratorError (validation errors, etc.)
        return {
            'status': 'failed',
            'project_id': project_id,
            'error': error_msg
        }
        
    except Exception as e:
        error_msg = f"Unexpected error during video generation: {str(e)}"
        logger.error(
            f"Unexpected error in slideshow generation for project {project_id}: {e}",
            exc_info=True
        )
        
        # Update status to failed
        project.status = 'failed'
        project.error_message = error_msg
        project.save(update_fields=['status', 'error_message'])
        
        # Retry on unexpected errors
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(name='tools.tasks.cleanup_old_projects_task', queue='render')
def cleanup_old_projects_task(older_than_days=30, keep_failed=False):
    """
    Clean up old slideshow projects and their files.
    
    Args:
        older_than_days: Delete projects older than this many days (default: 30)
        keep_failed: If True, keep failed projects (default: False)
        
    Returns:
        dict: Summary of cleanup operation
    """
    check_tools_enabled()
    
    logger.info(f"Starting cleanup of old slideshow projects (older than {older_than_days} days)")
    
    cutoff_date = timezone.now() - timedelta(days=older_than_days)
    
    # Find old projects
    queryset = SlideshowProject.objects.filter(created_at__lt=cutoff_date)
    
    if keep_failed:
        queryset = queryset.exclude(status='failed')
    
    old_projects = list(queryset)
    deleted_count = 0
    files_deleted = 0
    
    for project in old_projects:
        try:
            # Delete media files (only if not used by library or other projects)
            for media in project.media_files.all():
                if media.file:
                    try:
                        media_path = resolve_tools_file_path(media.file)
                    except Exception:
                        media_path = None
                else:
                    media_path = None

                if media_path and media_path.exists():
                    # Check if file is used by library or other projects
                    other_uses = SlideshowMedia.objects.filter(
                        file=media.file
                    ).exclude(id=media.id).exists()
                    
                    if not other_uses:
                        try:
                            media_path.unlink()
                            files_deleted += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete media file {media_path}: {e}")
                    else:
                        logger.debug(f"Skipping media file {media_path} - used by library or other projects")
            
            # Delete audio files (only if not used by library or other projects)
            for audio in project.audio_files.all():
                if audio.file:
                    try:
                        audio_path = resolve_tools_file_path(audio.file)
                    except Exception:
                        audio_path = None
                else:
                    audio_path = None

                if audio_path and audio_path.exists():
                    # Check if file is used by library or other projects
                    other_uses = SlideshowAudio.objects.filter(
                        file=audio.file
                    ).exclude(id=audio.id).exists()
                    
                    if not other_uses:
                        try:
                            audio_path.unlink()
                            files_deleted += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete audio file {audio_path}: {e}")
                    else:
                        logger.debug(f"Skipping audio file {audio_path} - used by library or other projects")
            
            # Delete output file
            if project.output_file:
                try:
                    output_path = resolve_tools_output_path(project.output_file)
                except Exception:
                    output_path = None
                if output_path and output_path.exists():
                    try:
                        output_path.unlink()
                        files_deleted += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete output file {output_path}: {e}")
            
            # Delete project (cascades to related objects)
            project_id = project.id
            project.delete()
            deleted_count += 1
            
            logger.debug(f"Deleted old project {project_id}")
            
        except Exception as e:
            logger.error(f"Error deleting project {project.id}: {e}", exc_info=True)
    
    result = {
        'status': 'completed',
        'projects_deleted': deleted_count,
        'files_deleted': files_deleted,
        'cutoff_date': cutoff_date.isoformat()
    }
    
    logger.info(
        f"Cleanup completed: {deleted_count} projects deleted, {files_deleted} files removed"
    )
    
    return result


@shared_task(name='tools.tasks.cleanup_old_video_render_operations_task', queue='render')
def cleanup_old_video_render_operations_task(older_than_days=30, keep_failed=True):
    """
    Clean up old FileOperation records created by the Tools video-render UI.

    IMPORTANT: This task deletes only database records (FileOperation). It does NOT delete
    any VideoFile records or physical files from disk.
    """
    check_tools_enabled()

    if not getattr(settings, "MEDIA_FILES_ENABLED", False) or "media_files" not in getattr(settings, "INSTALLED_APPS", []):
        logger.info("Skipping cleanup_old_video_render_operations_task: media_files is not available")
        return {"status": "skipped", "reason": "media_files not available"}

    from media_files.models import FileOperation  # type: ignore

    cutoff_date = timezone.now() - timedelta(days=int(older_than_days))

    qs = FileOperation.objects.filter(
        operation_type="RENDER",
        performed_at__lt=cutoff_date,
        details__source="tools_video_render",
    )
    if keep_failed:
        qs = qs.exclude(status="FAILED")

    deleted = qs.delete()[0]
    logger.info(
        "cleanup_old_video_render_operations_task completed: deleted=%s (older_than_days=%s, keep_failed=%s)",
        deleted,
        older_than_days,
        keep_failed,
    )
    return {
        "status": "completed",
        "deleted": deleted,
        "cutoff_date": cutoff_date.isoformat(),
    }


@shared_task(name='tools.tasks.cleanup_old_audio_normalize_jobs_task', queue='render')
def cleanup_old_audio_normalize_jobs_task(older_than_days=30, delete_if_missing_files=True, delete_media_files=False):
    """
    Clean up old audio normalize jobs and related files.

    Rules:
    - Delete jobs older than `older_than_days` (except actively running ones).
    - If `delete_if_missing_files` is True, also delete jobs whose input/output files
      referenced by the DB are missing on disk (especially missing output for completed jobs).
    - If `delete_media_files` is True, also delete input/output media files on disk.
      Default is False to avoid removing user media.
    """
    check_tools_enabled()

    logger.info("Starting cleanup of audio normalize jobs (older than %s days)", older_than_days)

    cutoff_date = timezone.now() - timedelta(days=older_than_days)

    deleted_jobs = 0
    files_deleted = 0  # counts deleted files/caches (mp4 deletion is disabled by default)
    skipped_running = 0
    deleted_missing = 0

    def _path_exists(p: str) -> bool:
        try:
            return bool(p) and Path(p).exists()
        except Exception:
            return False

    def _unlink(path_str: str) -> bool:
        try:
            p = Path(path_str)
            if p.exists():
                p.unlink()
                return True
        except Exception as e:
            logger.warning("Failed to delete file %s: %s", path_str, e)
        return False

    def _cleanup_job_folder(job_id: int) -> int:
        """
        Remove cached waveform JSONs (and empty dirs) under MEDIA_ROOT/tools/audio_normalize/<job_id>/...
        Returns number of files removed (best effort).
        """
        removed = 0
        base = Path(settings.MEDIA_ROOT) / f"tools/audio_normalize/{job_id}"
        if not base.exists():
            return 0
        try:
            # Remove known waveform cache files first
            wf_dir = base / "waveform"
            for f in (wf_dir / "before.json", wf_dir / "after.json"):
                if f.exists():
                    try:
                        f.unlink()
                        removed += 1
                    except Exception as e:
                        logger.warning("Failed to delete waveform cache %s: %s", f, e)
            # Remove empty dirs (waveform and base) if possible
            for d in (wf_dir, base):
                try:
                    if d.exists() and d.is_dir() and not any(d.iterdir()):
                        d.rmdir()
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Failed to cleanup job folder %s: %s", base, e)
        return removed

    def _should_delete_missing(job: AudioNormalizeJob) -> bool:
        if not delete_if_missing_files:
            return False
        ext = (getattr(job, "input_path_external", "") or "").strip()
        input_missing = (
            (bool(job.input_file) and (job.input_file.name or "").strip() and not _path_exists(getattr(job.input_file, "path", "")))
            or (bool(ext) and not _path_exists(ext))
        )
        output_missing = (
            (bool(job.output_file) and not _path_exists(getattr(job.output_file, "path", "")))
            or (bool(getattr(job, "output_path_external", "")) and not _path_exists(job.output_path_external))
        )

        if input_missing:
            return True
        if job.status == "completed" and output_missing:
            return True
        return False

    def _delete_job(job: AudioNormalizeJob, missing_trigger: bool) -> None:
        nonlocal deleted_jobs, deleted_missing, files_deleted

        # Only our copy under MEDIA_ROOT is deleted; input_path_external references external storage and must not be unlinked.
        input_path = getattr(job.input_file, "path", "") if (job.input_file and (job.input_file.name or "").strip()) else ""
        output_path = getattr(job.output_file, "path", "") if job.output_file else ""
        output_path_external = getattr(job, "output_path_external", "") or ""

        # Delete media files only if explicitly enabled.
        if delete_media_files:
            if output_path and _unlink(output_path):
                files_deleted += 1
            if output_path_external and _unlink(output_path_external):
                files_deleted += 1
            # Delete input file
            if input_path and _unlink(input_path):
                files_deleted += 1
        # Cleanup per-job cache folder (waveform + legacy outputs)
        files_deleted += _cleanup_job_folder(job.id)

        job_id = job.id
        job.delete()
        deleted_jobs += 1
        if missing_trigger:
            deleted_missing += 1

        logger.debug("Deleted audio normalize job %s", job_id)

    # First pass: delete broken rows with missing files regardless of age
    deleted_ids: set[int] = set()
    if delete_if_missing_files:
        for job in AudioNormalizeJob.objects.exclude(status__in=("processing", "analyzing")).order_by("id").iterator():
            try:
                if _should_delete_missing(job):
                    _delete_job(job, missing_trigger=True)
                    deleted_ids.add(job.id)
            except Exception as e:
                logger.error("Error deleting audio normalize job %s (missing-files pass): %s", job.id, e, exc_info=True)

    # Second pass: age-based cleanup
    old_qs = AudioNormalizeJob.objects.filter(created_at__lt=cutoff_date).order_by("id")
    for job in old_qs.iterator():
        if job.status in ("processing", "analyzing"):
            skipped_running += 1
            continue

        try:
            if job.id in deleted_ids:
                continue
            missing_trigger = _should_delete_missing(job)
            _delete_job(job, missing_trigger=missing_trigger)
        except Exception as e:
            logger.error("Error deleting audio normalize job %s: %s", job.id, e, exc_info=True)

    result = {
        "status": "completed",
        "jobs_deleted": deleted_jobs,
        "jobs_deleted_missing_files": deleted_missing,
        "files_deleted": files_deleted,
        "skipped_running": skipped_running,
        "cutoff_date": cutoff_date.isoformat(),
    }

    logger.info(
        "Audio normalize cleanup completed: %s jobs deleted (%s missing-file), %s files removed",
        deleted_jobs,
        deleted_missing,
        files_deleted,
    )
    return result


@shared_task(name='tools.tasks.analyze_audio_normalize_job', queue='render', bind=True, max_retries=1)
def analyze_audio_normalize_job_task(self, job_id):
    """Run analysis-only (ffprobe + loudnorm analyze) for AudioNormalizeJob."""
    check_tools_enabled()

    job = AudioNormalizeJob.objects.get(id=job_id)
    job.status = 'analyzing'
    job.progress = 0
    job.error_message = ''
    job.ffmpeg_log = ''
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'progress', 'error_message', 'ffmpeg_log', 'started_at'])

    try:
        service = AudioNormalizerService(job)
        ext = (getattr(job, 'input_path_external', '') or '').strip()
        if ext:
            input_path = Path(ext)
        elif job.input_file and (job.input_file.name or '').strip():
            input_path = Path(job.input_file.path)
        else:
            raise AudioNormalizerError("Job has no input file.")

        import time
        start_time = time.time()
        
        meta, _probe = service.probe(input_path)
        probe_time = time.time() - start_time
        
        # Single-pass analysis: loudnorm + noise analysis combined
        analysis_start = time.time()
        before, noise_analysis = service.analyze_all(input_path, _probe.duration_sec)
        analysis_time = time.time() - analysis_start
        
        recs_start = time.time()
        recs = service.get_recommendations(before, noise_analysis)
        recs_time = time.time() - recs_start
        
        total_time = time.time() - start_time
        logger.info(
            "Audio analyze completed for job %s: total=%.2fs (probe=%.2fs, analysis=%.2fs, recommendations=%.2fs)",
            job_id, total_time, probe_time, analysis_time, recs_time
        )

        job.input_metadata = meta
        job.analysis_before = before
        job.analysis_after = None
        # Store noise analysis in input_metadata for now (or add separate field later)
        if noise_analysis and isinstance(job.input_metadata, dict):
            job.input_metadata = {**(job.input_metadata or {}), "noise_analysis": noise_analysis}
        job.progress = 100
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=['input_metadata', 'analysis_before', 'analysis_after', 'progress', 'status', 'completed_at'])

        return {'status': 'success', 'job_id': job_id, 'recommendations': recs}

    except AudioNormalizerError as e:
        msg = str(e)
        logger.error("Audio analyze failed for job %s: %s", job_id, msg, exc_info=True)
        job.status = 'failed'
        job.error_message = msg
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at'])
        return {'status': 'failed', 'job_id': job_id, 'error': msg}

    except Exception as e:
        logger.error("Unexpected error in audio analyze for job %s: %s", job_id, e, exc_info=True)
        raise self.retry(exc=e, countdown=30)


@shared_task(name='tools.tasks.normalize_audio', queue='render', bind=True, max_retries=1)
def normalize_audio_task(self, job_id):
    """Run full R128 normalization pipeline for AudioNormalizeJob."""
    check_tools_enabled()

    job = AudioNormalizeJob.objects.get(id=job_id)
    job.status = 'processing'
    job.progress = 0
    job.error_message = ''
    job.ffmpeg_log = ''
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'progress', 'error_message', 'ffmpeg_log', 'started_at'])

    try:
        service = AudioNormalizerService(job)
        result = service.run_full_pipeline()

        input_metadata = result.get('input_metadata')
        if input_metadata is None or not isinstance(input_metadata, dict):
            input_metadata = {}
        # Persist loudnorm mode diagnostics for UI/API guardrails.
        input_metadata = {
            **input_metadata,
            'normalization_type': result.get('normalization_type'),
            'normalization_warning': result.get('normalization_warning'),
        }

        job.input_metadata = input_metadata
        job.analysis_before = result.get('analysis_before')
        job.analysis_after = result.get('analysis_after')
        job.ffmpeg_log = result.get('ffmpeg_log', '') or ''

        output_path_external = result.get('output_path_external')
        if output_path_external:
            job.output_path_external = output_path_external
            job.output_file = None
        else:
            job.output_path_external = ''
            rel_name = result.get('output_relpath')
            if not rel_name:
                rel_name = str(Path(result['output_path']).resolve().relative_to(_media_root_abs()))
            job.output_file.name = rel_name.replace("\\", "/")

        job.progress = 100
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=[
            'input_metadata',
            'analysis_before',
            'analysis_after',
            'ffmpeg_log',
            'output_file',
            'output_path_external',
            'progress',
            'status',
            'completed_at',
        ])

        elapsed = (job.completed_at - job.started_at).total_seconds() if job.started_at else 0
        output_path = job.output_path_external or (job.output_file.name if job.output_file else 'N/A')
        logger.info(
            "Audio normalize completed for job %s: elapsed=%.2fs, preset=%s, output=%s",
            job_id, elapsed, job.preset_id, output_path
        )

        out_url = job.output_file.url if job.output_file else None
        return {'status': 'success', 'job_id': job_id, 'output_file': out_url, 'output_path_external': job.output_path_external or None}

    except AudioNormalizerError as e:
        msg = str(e)
        logger.error("Audio normalize failed for job %s: %s", job_id, msg, exc_info=True)
        job.status = 'failed'
        job.error_message = msg
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at'])
        return {'status': 'failed', 'job_id': job_id, 'error': msg}

    except ValueError as e:
        msg = str(e)
        logger.error("Audio normalize failed for job %s (path error): %s", job_id, msg, exc_info=True)
        job.status = 'failed'
        job.error_message = msg
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at'])
        return {'status': 'failed', 'job_id': job_id, 'error': msg}

    except Exception as e:
        logger.error("Unexpected error in audio normalize for job %s: %s", job_id, e, exc_info=True)
        raise self.retry(exc=e, countdown=30)


# ---- Reel Studio (external OKMQ reel renderer) ----------------------------
@shared_task(name='tools.tasks.okmq_generate_hooks', bind=True)
def okmq_generate_hooks_task(self, *, title, hook_type, description=None,
                             category=None, location=None, date=None, n=5):
    """Generate hook candidates (result lands in the Celery result backend)."""
    from .services import okmq_reel
    return okmq_reel.generate_hooks(
        title, hook_type=hook_type, description=description, category=category,
        location=location, date=date, n=n,
    )


@shared_task(name='tools.tasks.okmq_render_reel', bind=True)
def okmq_render_reel_task(self, *, payload):
    """Render a reel (start + poll) and return the final status dict.

    On render error/timeout the client raises -> task = FAILURE.
    """
    from .services import okmq_reel
    result = okmq_reel.render_reel_blocking(**payload)
    _record_rendered_reel_video(payload, result)
    return result


@shared_task(
    name='tools.tasks.send_daily_reel_reminder',
    bind=True,
    max_retries=REEL_REMINDER_MISSING_URL_RETRIES,
)
def send_daily_reel_reminder(self, target_date_iso=None):
    """Send one daily email with today's Reel Studio output links."""
    check_tools_enabled()

    config = ToolsConfig.get_config()
    if not (
        config.is_reel_configured()
        and config.reel_reminder_enabled
        and config.reel_reminder_recipient_email
    ):
        return {'status': 'skipped', 'reason': 'not_configured'}

    if target_date_iso:
        try:
            target_date = datetime.strptime(str(target_date_iso), '%Y-%m-%d').date()
        except ValueError:
            return {'status': 'error', 'reason': 'invalid_date'}
    else:
        target_date = timezone.localdate()

    context = build_daily_reel_reminder_context(
        target_date,
        refresh_missing_mediathek=True,
    )
    if not context['reels']:
        return {'status': 'skipped', 'reason': 'no_reels', 'date': target_date.isoformat()}

    missing_mediathek_numbers = [
        reel['number']
        for reel in context['reels']
        if not reel.get('mediathek_url')
    ]
    if missing_mediathek_numbers:
        if self.request.retries >= self.max_retries:
            logger.error(
                'Daily reel reminder sent for %s although Mediathek URLs are still missing for licenses: %s',
                target_date,
                missing_mediathek_numbers,
            )
        else:
            countdown = _reel_reminder_missing_url_countdown(self.request.retries)
            logger.info(
                'Daily reel reminder delayed for %s; missing Mediathek URLs for licenses %s. Retrying in %s seconds.',
                target_date,
                missing_mediathek_numbers,
                countdown,
            )
            raise self.retry(
                exc=RuntimeError('Mediathek URL missing for daily reel reminder'),
                countdown=countdown,
            )

    try:
        from registration.email import send_mail

        from_email = (
            getattr(settings, 'DEFAULT_FROM_EMAIL', '')
            or getattr(settings, 'EMAIL_HOST_USER', '')
            or ''
        )
        language = (getattr(settings, 'LANGUAGE_CODE', 'de') or 'de').split('-')[0]
        with translation.override(language):
            send_mail(
                subject_template_name='email/daily_reel_reminder_subject.txt',
                email_template_name='email/daily_reel_reminder_body.txt',
                html_email_template_name='email/daily_reel_reminder_body.html',
                context=context,
                from_email=from_email,
                to_email=config.reel_reminder_recipient_email,
            )
    except Exception:
        logger.exception('Failed to send daily reel reminder for %s', target_date)
        return {'status': 'error', 'reason': 'send_failed', 'date': target_date.isoformat()}

    return {
        'status': 'sent',
        'date': target_date.isoformat(),
        'reel_count': context['reel_count'],
        'missing_mediathek_numbers': missing_mediathek_numbers,
    }
