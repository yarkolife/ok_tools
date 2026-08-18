"""
Signals for the licenses app.

User-visible strings must be English and wrapped for translation.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .config import get_send_status_emails
from .models import LicenseNotificationEvent, LicenseNotificationEventType, NextcloudVideoFile
from .tasks import enqueue_license_notification_email
from .tasks import enqueue_nextcloud_download


logger = logging.getLogger("django")


@receiver(post_save, sender=NextcloudVideoFile)
def download_nextcloud_file_automatically(sender, instance: NextcloudVideoFile, created: bool, **kwargs) -> None:
    """Fetch a freshly uploaded Nextcloud file into local storage without manual action."""
    if not created:
        return

    if getattr(instance, "is_deleted", False) or instance.downloaded_at:
        return

    def _enqueue_download() -> None:
        try:
            enqueue_nextcloud_download(instance)
        except Exception:
            logger.exception(
                "Failed to queue automatic download for Nextcloud file %s", instance.pk
            )

    transaction.on_commit(_enqueue_download)


@receiver(post_save, sender=NextcloudVideoFile)
def notify_on_nextcloud_video_uploaded(sender, instance: NextcloudVideoFile, created: bool, **kwargs) -> None:
    """Notify user when a video upload to Nextcloud was recorded."""
    if not created:
        return

    if not get_send_status_emails():
        return

    if getattr(instance, "is_deleted", False):
        return

    license_obj = getattr(instance, "license", None)
    license_number = getattr(license_obj, "number", None)
    if not license_number:
        return

    try:
        event, was_created = LicenseNotificationEvent.objects.get_or_create(
            license_number=int(license_number),
            event_type=LicenseNotificationEventType.VIDEO_UPLOADED,
            defaults={
                "payload": {
                    "filename": getattr(instance, "filename", "") or "",
                    "nextcloud_url": getattr(instance, "nextcloud_url", "") or "",
                }
            },
        )
    except Exception:
        logger.exception("Failed to create notification event (license=%s, type=%s)", license_number, "video_uploaded")
        return

    if not was_created:
        return

    payload = event.payload or {}
    enqueue_license_notification_email(
        LicenseNotificationEventType.VIDEO_UPLOADED,
        int(license_number),
        payload=payload,
    )

