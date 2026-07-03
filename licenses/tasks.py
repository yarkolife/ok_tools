"""Celery tasks for licenses module."""

from .models import License
from .models import LicenseNotificationEvent
from .models import LicenseNotificationEventType
from .models import LicensesConfig
from .models import NextcloudVideoFile
from .services.nextcloud_service import NextcloudService
from .services.peertube_service import compute_lookup_eta
from .services.peertube_service import compute_publish_time_for_license
from .services.peertube_service import find_video_by_number_in_channel
from .services.peertube_service import peertube_watch_url
from .services.peertube_service import resolve_peertube_endpoint
from celery import shared_task
from datetime import date
from datetime import datetime
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from pathlib import Path
from registration.email import send_mail
import logging


logger = logging.getLogger('django')


@shared_task(name='licenses.tasks.download_nextcloud_video_file_to_storage', queue='download', bind=True, max_retries=3)
def download_nextcloud_video_file_to_storage(self, nextcloud_video_file_id: int, download_dir: str | None = None) -> str:
    """
    Download a Nextcloud video to local storage.

    Args:
        nextcloud_video_file_id: NextcloudVideoFile PK
        download_dir: Override download directory (optional)

    Returns:
        Local file path as string
    """
    if not settings.NEXTCLOUD_ENABLED:
        raise RuntimeError("NEXTCLOUD_ENABLED is false")

    video = NextcloudVideoFile.objects.select_related('license').get(pk=nextcloud_video_file_id)
    if video.is_deleted:
        raise RuntimeError(f"Nextcloud video is marked deleted (id={video.pk})")

    config = LicensesConfig.get_config()
    storage_path = (download_dir or config.download_storage_path or '').strip()
    if not storage_path:
        raise RuntimeError("download_storage_path is not configured")

    download_path = Path(storage_path)
    download_path.mkdir(parents=True, exist_ok=True)

    service = NextcloudService()
    safe_filename = service._sanitize_filename(video.filename or 'video')

    license_number = getattr(video.license, 'number', None)
    if license_number and not safe_filename.startswith(f"{license_number}_"):
        safe_filename = f"{license_number}_{safe_filename}"

    local_path = download_path / safe_filename

    try:
        ok = service.download_file(video.nextcloud_file_id, str(local_path), resume=True)
        if not ok:
            raise RuntimeError("Download failed")
        logger.info(f"Downloaded Nextcloud video #{video.pk} to {local_path}")

        # Optionally create VideoFile in media_files so it shows as Player immediately
        if getattr(settings, "MEDIA_FILES_ENABLED", False) and getattr(
            config, "create_videofile_on_nextcloud_download", False
        ):
            try:
                _create_videofile_after_download(
                    local_path=local_path,
                    license_number=license_number,
                    filename=video.filename or safe_filename,
                )
            except Exception as e:
                logger.warning(
                    "Could not create VideoFile after Nextcloud download (path=%s): %s",
                    local_path,
                    e,
                    exc_info=True,
                )

        return str(local_path)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


def _create_videofile_after_download(
    *,
    local_path: Path,
    license_number: int | None,
    filename: str,
) -> None:
    """
    Create a VideoFile in media_files when local_path lies under a StorageLocation.

    Used after Nextcloud download so the license list shows Player instead of
    waiting for a storage scan. License linking is done by media_files signals.
    """
    if not license_number:
        return

    from media_files.models import StorageLocation
    from media_files.models import VideoFile

    resolved = Path(local_path).resolve()
    if not resolved.exists():
        return

    # Find StorageLocations whose path contains the file; pick the most specific
    candidates = []
    for s in StorageLocation.objects.filter(is_active=True):
        if not s.path:
            continue
        try:
            base = Path(s.path).resolve()
            resolved.relative_to(base)
            candidates.append((s, len(s.path)))
        except (ValueError, OSError):
            continue
    if not candidates:
        logger.debug(
            "No StorageLocation contains %s, skipping VideoFile creation",
            local_path,
        )
        return

    storage = max(candidates, key=lambda x: x[1])[0]
    base = Path(storage.path).resolve()
    rel_path = str(resolved.relative_to(base)).replace("\\", "/")
    fname = filename or resolved.name

    VideoFile.objects.get_or_create(
        number=license_number,
        storage_location=storage,
        file_path=rel_path,
        defaults={"filename": fname, "is_available": True},
    )


def _safe_site_base_url() -> str:
    base = getattr(settings, "SITE_BASE_URL", "") or ""
    return base.rstrip("/")


def _absolute_url(path: str) -> str:
    base = _safe_site_base_url()
    if not base:
        return ""
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _get_contact_email() -> str:
    try:
        from registration import organization_config
        email = (organization_config.get_organization_email() or "").strip()
        if email:
            return email
    except Exception:
        pass

    return (
        (getattr(settings, "OK_EMAIL", None) or "").strip()
        or (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
        or (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
        or ""
    )


def _get_ok_name() -> str:
    try:
        from registration import organization_config
        name = (organization_config.get_organization_name() or "").strip()
        if name:
            return name
    except Exception:
        pass
    return (getattr(settings, "OK_NAME", "") or "").strip()


def _enqueue(task, *args, **kwargs) -> None:
    """
    Enqueue a Celery task if available; otherwise run synchronously.

    This mirrors other parts of the codebase where Celery may be optional.
    """
    try:
        task.delay(*args, **kwargs)
    except AttributeError:
        task(*args, **kwargs)


@shared_task(name="licenses.tasks.send_license_notification_email")
def send_license_notification_email(event_type: str, license_number: int, payload: dict | None = None) -> None:
    """
    Send a user notification email for a license event.

    Args:
        event_type: string matching LicenseNotificationEventType values
        license_number: License.number
        payload: optional dict with event details (schedule time, filenames, etc.)
    """
    payload = payload or {}

    try:
        from .config import get_send_status_emails
        if not get_send_status_emails():
            return
    except Exception:
        pass

    try:
        license_obj = License.objects.select_related(
            "profile", "profile__okuser", "profile__media_authority"
        ).get(number=int(license_number))
    except Exception:
        logger.exception("License not found for notification (number=%s, event=%s)", license_number, event_type)
        return

    try:
        from .config import should_send_notification_for_license
        if not should_send_notification_for_license(license_obj):
            return
    except Exception:
        pass

    profile = getattr(license_obj, "profile", None)
    user = getattr(profile, "okuser", None) if profile else None
    to_email = (getattr(user, "email", None) or "").strip()
    if not to_email:
        return

    try:
        license_url = ""
        try:
            license_url = _absolute_url(reverse("licenses:details", kwargs={"pk": license_obj.pk}))
        except Exception:
            license_url = ""

        contributions_url = ""
        try:
            contributions_url = _absolute_url(reverse("contributions:contributions"))
        except Exception:
            contributions_url = ""

        context = {
            "ok_name": _get_ok_name(),
            "contact_email": _get_contact_email(),
            "first_name": getattr(profile, "first_name", "") if profile else "",
            "license_number": int(license_obj.number),
            "license_title": license_obj.title or str(license_obj),
            "license_url": license_url,
            "contributions_url": contributions_url,
            "tz": getattr(settings, "TIME_ZONE", ""),
            **payload,
        }

        templates = {
            "video_uploaded": (
                "email/license_video_uploaded_subject.txt",
                "email/license_video_uploaded_body.txt",
                "email/license_video_uploaded_body.html",
            ),
            "draft_scheduled": (
                "email/license_draft_scheduled_subject.txt",
                "email/license_draft_scheduled_body.txt",
                "email/license_draft_scheduled_body.html",
            ),
            "planned_scheduled": (
                "email/license_planned_scheduled_subject.txt",
                "email/license_planned_scheduled_body.txt",
                "email/license_planned_scheduled_body.html",
            ),
            "contributions_available": (
                "email/license_contributions_available_subject.txt",
                "email/license_contributions_available_body.txt",
                "email/license_contributions_available_body.html",
            ),
            "mediathek_published": (
                "email/license_mediathek_published_subject.txt",
                "email/license_mediathek_published_body.txt",
                "email/license_mediathek_published_body.html",
            ),
        }

        if event_type not in templates:
            logger.warning("Unknown license notification event_type=%s", event_type)
            return

        subject_tpl, body_tpl, html_tpl = templates[event_type]

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or ""

        # Use organization default language for isolated rendering in worker processes
        language = (getattr(settings, "LANGUAGE_CODE", "de") or "de").split("-")[0]
        with translation.override(language):
            send_mail(
                subject_template_name=subject_tpl,
                email_template_name=body_tpl,
                html_email_template_name=html_tpl,
                context=context,
                from_email=from_email,
                to_email=to_email,
            )
    except Exception:
        logger.exception("Failed to send license notification email (number=%s, event=%s)", license_number, event_type)


def enqueue_license_notification_email(event_type: str, license_number: int, payload: dict | None = None) -> None:
    """Public helper for other modules to queue a notification email."""
    _enqueue(send_license_notification_email, event_type, int(license_number), payload or None)


def _get_peertube_target_channel(license_obj: License) -> str | None:
    """Get target channel from license media authority if configured."""
    profile = getattr(license_obj, 'profile', None)
    media_authority = getattr(profile, 'media_authority', None) if profile else None
    return (getattr(media_authority, 'target_channel', None) or '').strip() or None


def _get_org_channel() -> str | None:
    """Get OrganizationConfig peertube_channel if available."""
    try:
        from registration.models import OrganizationConfig

        config = OrganizationConfig.get_config()
        return (config.peertube_channel or '').strip() or None
    except Exception:
        return None


def _send_mediathek_published_email(license_obj: License, mediathek_url: str) -> None:
    """
    Send email when video is first published to mediathek.

    Uses LicenseNotificationEvent for deduplication - email is sent only once
    per license when mediathek_url is first set.
    """
    event_type = LicenseNotificationEventType.MEDIATHEK_PUBLISHED
    license_number = license_obj.number

    # Check if already sent (deduplication)
    if LicenseNotificationEvent.objects.filter(
        license_number=license_number,
        event_type=event_type,
    ).exists():
        logger.debug(
            'Mediathek published email already sent for license %s, skipping',
            license_number,
        )
        return

    # Create event for deduplication
    try:
        LicenseNotificationEvent.objects.create(
            license_number=license_number,
            event_type=event_type,
            payload={"mediathek_url": mediathek_url},
        )
    except Exception:
        logger.warning(
            'Failed to create LicenseNotificationEvent for license %s, '
            'email may be sent again on retry',
            license_number,
        )

    # Send the email
    enqueue_license_notification_email(
        event_type=event_type,
        license_number=license_number,
        payload={"mediathek_url": mediathek_url},
    )
    logger.info('Queued mediathek published email for license %s', license_number)


@shared_task(
    name='licenses.tasks.refresh_license_mediathek_url',
    bind=True,
    max_retries=8,
)
def refresh_license_mediathek_url(
    self,
    license_number: int,
    force: bool = False,
    send_notification_email: bool = True,
    retry_not_found: bool = True,
) -> dict:
    """Refresh mediathek watch URL for one license by PeerTube videoNumber."""
    try:
        license_obj = License.objects.select_related('profile__media_authority').get(
            number=int(license_number)
        )
    except License.DoesNotExist:
        logger.warning('License not found for mediathek refresh: %s', license_number)
        return {
            'license_number': int(license_number),
            'updated': False,
            'reason': 'license_not_found',
        }

    if not force and license_obj.mediathek_url:
        return {
            'license_number': int(license_number),
            'updated': False,
            'reason': 'already_set',
            'mediathek_url': license_obj.mediathek_url,
        }

    target_channel = _get_peertube_target_channel(license_obj)
    org_channel = _get_org_channel()

    try:
        endpoint = resolve_peertube_endpoint(
            target_channel=target_channel,
            organization_channel=org_channel,
        )
    except ValueError as exc:
        logger.warning(
            'Cannot resolve PeerTube endpoint for license %s: %s',
            license_obj.number,
            exc,
        )
        return {
            'license_number': int(license_obj.number),
            'updated': False,
            'reason': 'endpoint_not_configured',
        }

    try:
        video = find_video_by_number_in_channel(
            endpoint.base_url,
            endpoint.channel_handle,
            str(license_obj.number),
        )
    except Exception as exc:
        countdown = min(3600, 120 * (2 ** self.request.retries))
        raise self.retry(exc=exc, countdown=countdown)

    if not video:
        if retry_not_found and self.request.retries < self.max_retries:
            countdown = min(7200, 300 * (2 ** self.request.retries))
            raise self.retry(exc=RuntimeError('PeerTube video not found yet'), countdown=countdown)
        return {
            'license_number': int(license_obj.number),
            'updated': False,
            'reason': 'not_found',
        }

    watch_url = peertube_watch_url(endpoint.base_url, video)

    # Check if this is the first time mediathek_url is being set
    was_empty = not license_obj.mediathek_url

    with transaction.atomic():
        license_obj.mediathek_url = watch_url
        license_obj.mediathek_url_updated_at = timezone.now()
        license_obj.save(update_fields=['mediathek_url', 'mediathek_url_updated_at'])

    logger.info('Updated mediathek URL for license %s: %s', license_obj.number, watch_url)

    # Send email notification only on first publish when notifications are enabled
    if was_empty and send_notification_email:
        _send_mediathek_published_email(license_obj, watch_url)

    return {
        'license_number': int(license_obj.number),
        'updated': True,
        'mediathek_url': watch_url,
    }


def _parse_iso_date(value: str) -> date | None:
    """Parse YYYY-MM-DD date safely."""
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _collect_license_numbers_from_planung(start_date: date, end_date: date) -> set[int]:
    """Collect license numbers from TagesPlan items for date range."""
    try:
        from planung.models import TagesPlan
    except (ImportError, RuntimeError, ModuleNotFoundError):
        return set()

    numbers: set[int] = set()
    plans = TagesPlan.objects.filter(datum__gte=start_date, datum__lte=end_date)
    for plan in plans:
        for item in (plan.json_plan or {}).get('items', []):
            number = item.get('number')
            if number is None:
                continue
            try:
                numbers.add(int(number))
            except (TypeError, ValueError):
                continue
    return numbers


def _collect_license_numbers_from_contributions(start_date: date, end_date: date) -> set[int]:
    """Collect license numbers from Contribution broadcast dates for date range."""
    try:
        from contributions.models import Contribution
    except (ImportError, RuntimeError, ModuleNotFoundError):
        return set()

    contribution_numbers = Contribution.objects.filter(
        broadcast_date__date__gte=start_date,
        broadcast_date__date__lte=end_date,
    ).values_list('license__number', flat=True)
    return {int(number) for number in contribution_numbers if number is not None}


def _queue_mediathek_refreshes_for_numbers(
    *,
    numbers: set[int],
    start_date: date,
    end_date: date,
    source: str,
    only_store_in_ok_media_library: bool = True,
    missing_only: bool = False,
    requested_by_user_id: int | None = None,
) -> dict:
    """Queue per-license mediathek URL refresh tasks for collected license numbers."""
    if not numbers:
        logger.info(
            'Mediathek %s rescan: no license numbers found for %s..%s',
            source,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        return {
            'queued_count': 0,
            'source': source,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'only_store_in_ok_media_library': bool(only_store_in_ok_media_library),
            'missing_only': bool(missing_only),
            'requested_by_user_id': requested_by_user_id,
        }

    filters = Q(number__in=list(numbers))
    if only_store_in_ok_media_library:
        filters &= Q(store_in_ok_media_library=True)
    if missing_only:
        filters &= Q(mediathek_url__isnull=True) | Q(mediathek_url='')

    license_numbers = list(
        License.objects.filter(filters).values_list('number', flat=True)
    )

    queued_count = 0
    for license_number in license_numbers:
        license_obj = License.objects.filter(number=int(license_number)).first()
        eta = timezone.now()
        if license_obj:
            publish_time = compute_publish_time_for_license(license_obj)
            eta = compute_lookup_eta(publish_time)
        refresh_license_mediathek_url.apply_async(
            args=[int(license_number)],
            kwargs={
                'force': True,
                'send_notification_email': False,
                'retry_not_found': False,
            },
            eta=eta,
        )
        queued_count += 1

    logger.info(
        'Mediathek %s rescan queued: %s licenses, range=%s..%s, requested_by=%s',
        source,
        queued_count,
        start_date.isoformat(),
        end_date.isoformat(),
        requested_by_user_id,
    )

    return {
        'queued_count': queued_count,
        'source': source,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'only_store_in_ok_media_library': bool(only_store_in_ok_media_library),
        'missing_only': bool(missing_only),
        'requested_by_user_id': requested_by_user_id,
    }


@shared_task(name='licenses.tasks.rescan_mediathek_links_for_period')
def rescan_mediathek_links_for_period(
    start_date_iso: str,
    end_date_iso: str,
    only_store_in_ok_media_library: bool = True,
    requested_by_user_id: int | None = None,
) -> dict:
    """Queue per-license mediathek URL refresh tasks for selected period."""
    start_date = _parse_iso_date(start_date_iso)
    end_date = _parse_iso_date(end_date_iso)
    if not start_date or not end_date or start_date > end_date:
        raise ValueError('Invalid date range')

    numbers = _collect_license_numbers_from_contributions(start_date, end_date)
    numbers.update(_collect_license_numbers_from_planung(start_date, end_date))

    return _queue_mediathek_refreshes_for_numbers(
        numbers=numbers,
        start_date=start_date,
        end_date=end_date,
        source='period',
        only_store_in_ok_media_library=only_store_in_ok_media_library,
        missing_only=False,
        requested_by_user_id=requested_by_user_id,
    )


@shared_task(name='licenses.tasks.rescan_mediathek_links_from_planung')
def rescan_mediathek_links_from_planung(
    days_back: int = 2,
    days_forward: int = 0,
    only_store_in_ok_media_library: bool = True,
) -> dict:
    """Queue mediathek URL refreshes for planned broadcasts without a stored URL."""
    today = timezone.localdate()
    start_date = today - timedelta(days=max(0, int(days_back)))
    end_date = today + timedelta(days=max(0, int(days_forward)))
    numbers = _collect_license_numbers_from_planung(start_date, end_date)
    return _queue_mediathek_refreshes_for_numbers(
        numbers=numbers,
        start_date=start_date,
        end_date=end_date,
        source='planung',
        only_store_in_ok_media_library=only_store_in_ok_media_library,
        missing_only=True,
    )


@shared_task(name='licenses.tasks.rescan_mediathek_links_from_contributions')
def rescan_mediathek_links_from_contributions(
    days_back: int = 14,
    days_forward: int = 0,
    only_store_in_ok_media_library: bool = True,
) -> dict:
    """Queue mediathek URL refreshes for Contribution broadcasts without a stored URL."""
    today = timezone.localdate()
    start_date = today - timedelta(days=max(0, int(days_back)))
    end_date = today + timedelta(days=max(0, int(days_forward)))
    numbers = _collect_license_numbers_from_contributions(start_date, end_date)
    return _queue_mediathek_refreshes_for_numbers(
        numbers=numbers,
        start_date=start_date,
        end_date=end_date,
        source='contributions',
        only_store_in_ok_media_library=only_store_in_ok_media_library,
        missing_only=True,
    )
