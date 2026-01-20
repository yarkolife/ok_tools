"""Celery tasks for licenses module."""

import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.urls import reverse
from django.utils import translation

from registration.email import send_mail

from .models import LicensesConfig, License, NextcloudVideoFile
from .services.nextcloud_service import NextcloudService


logger = logging.getLogger('django')


@shared_task(name='licenses.tasks.download_nextcloud_video_file_to_storage', bind=True, max_retries=3)
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
        return str(local_path)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


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
        license_obj = License.objects.select_related("profile", "profile__okuser").get(number=int(license_number))
    except Exception:
        logger.exception("License not found for notification (number=%s, event=%s)", license_number, event_type)
        return

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
        }

        if event_type not in templates:
            logger.warning("Unknown license notification event_type=%s", event_type)
            return

        subject_tpl, body_tpl, html_tpl = templates[event_type]

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "") or ""
        language = getattr(settings, "LANGUAGE_CODE", "de") or "de"

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

