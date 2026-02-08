"""Notification side-effects for planning saves."""

from __future__ import annotations

from datetime import date
from licenses.config import get_send_status_emails
from licenses.models import License
from licenses.models import LicenseNotificationEvent
from licenses.models import LicenseNotificationEventType
from licenses.models import NextcloudVideoFile
from licenses.tasks import enqueue_license_notification_email


def send_plan_status_notifications(*, plan_date: date, plan_data: dict) -> None:
    """Send deduplicated draft/planned notifications for relevant licenses."""
    is_draft = bool(plan_data.get("draft"))
    is_planned = bool(plan_data.get("planned"))

    if not get_send_status_emails():
        return

    if not (is_draft or is_planned):
        return

    items = plan_data.get("items", []) or []
    numbers: list[int] = []
    number_to_start: dict[int, str] = {}

    for item in items:
        n = item.get("number")
        if not n:
            continue
        try:
            n_int = int(n)
        except Exception:
            continue
        if n_int not in numbers:
            numbers.append(n_int)
        if n_int not in number_to_start:
            number_to_start[n_int] = (item.get("start") or "")

    if not numbers:
        return

    licenses = License.objects.filter(number__in=numbers).select_related("profile", "profile__okuser")
    plan_date_str = plan_date.isoformat()

    for lic in licenses:
        has_user_uploaded_video = NextcloudVideoFile.objects.filter(
            license=lic,
            is_deleted=False,
            user_uploaded=True,
        ).exists()
        if not has_user_uploaded_video:
            continue

        start_raw = (number_to_start.get(int(lic.number), "") or "").strip()
        start_time = start_raw[:5] if len(start_raw) >= 5 else start_raw
        payload = {"plan_date": plan_date_str, "start_time": start_time}

        if is_draft:
            _, created = LicenseNotificationEvent.objects.get_or_create(
                license_number=int(lic.number),
                event_type=LicenseNotificationEventType.DRAFT_SCHEDULED,
                defaults={"payload": payload},
            )
            if created:
                enqueue_license_notification_email(
                    LicenseNotificationEventType.DRAFT_SCHEDULED,
                    int(lic.number),
                    payload=payload,
                )

        if is_planned:
            _, created = LicenseNotificationEvent.objects.get_or_create(
                license_number=int(lic.number),
                event_type=LicenseNotificationEventType.PLANNED_SCHEDULED,
                defaults={"payload": payload},
            )
            if created:
                enqueue_license_notification_email(
                    LicenseNotificationEventType.PLANNED_SCHEDULED,
                    int(lic.number),
                    payload=payload,
                )

