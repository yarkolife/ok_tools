"""
Reconstruct and print the subject/body of a license notification email.

Use this to view the exact text that was (or would be) sent, e.g. from a
TaskResult in django_celery_results. The text is not stored in TaskResult;
it is re-rendered from the same templates and context the task uses.

Example:
  python manage.py render_license_notification_email --task-result-id 12345
  python manage.py render_license_notification_email --event-type video_uploaded --license-number 18084 --payload '{"filename":"x.mp4"}'
"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template import loader
from django.urls import reverse
from django.utils import translation

from licenses.models import License


# Same names as in licenses.tasks.send_license_notification_email
# (resolved from licenses/templates/email/...)
TEMPLATES = {
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


class Command(BaseCommand):
    help = (
        "Rerender a license notification email from TaskResult or from "
        "event_type+license_number+payload and print subject, body text and HTML."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--task-result-id",
            type=int,
            help="ID of django_celery_results.models.TaskResult for send_license_notification_email",
        )
        parser.add_argument("--event-type", type=str, help="e.g. video_uploaded, draft_scheduled")
        parser.add_argument("--license-number", type=int, help="License.number")
        parser.add_argument(
            "--payload",
            type=str,
            default="{}",
            help='JSON object merged into context, e.g. \'{"filename":"x.mp4"}\'',
        )

    def handle(self, *args, **options):
        event_type, license_number, payload = self._resolve_input(options)
        if event_type is None:
            return

        if event_type not in TEMPLATES:
            self.stderr.write(self.style.ERROR(f"Unknown event_type: {event_type}"))
            return

        try:
            license_obj = License.objects.select_related("profile", "profile__okuser").get(
                number=int(license_number)
            )
        except License.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"License with number={license_number} not found"))
            return

        profile = getattr(license_obj, "profile", None)
        user = getattr(profile, "okuser", None) if profile else None
        to_email = (getattr(user, "email", None) or "").strip()
        if not to_email:
            self.stderr.write(self.style.ERROR(f"No email for license {license_number} (profile/okuser)"))
            return

        from licenses.tasks import _absolute_url, _get_contact_email, _get_ok_name

        license_url = ""
        try:
            license_url = _absolute_url(reverse("licenses:details", kwargs={"pk": license_obj.pk}))
        except Exception:
            pass
        contributions_url = ""
        try:
            contributions_url = _absolute_url(reverse("contributions:contributions"))
        except Exception:
            pass

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

        subject_tpl, body_tpl, html_tpl = TEMPLATES[event_type]
        
        # Activate German language for email rendering
        translation.activate('de')
        try:
            subject = loader.render_to_string(subject_tpl, context)
            subject = "".join(subject.splitlines())
            body = loader.render_to_string(body_tpl, context)
            html = loader.render_to_string(html_tpl, context)
        finally:
            translation.deactivate()

        self.stdout.write("--- To")
        self.stdout.write(to_email)
        self.stdout.write("--- Subject")
        self.stdout.write(subject)
        self.stdout.write("--- Body (text)")
        self.stdout.write(body)
        self.stdout.write("--- Body (HTML)")
        self.stdout.write(html)

    def _resolve_input(self, options):
        tid = options.get("task_result_id")
        if tid is not None:
            try:
                from django_celery_results.models import TaskResult

                r = TaskResult.objects.get(pk=tid)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"TaskResult id={tid} not found: {e}"))
                self.stderr.write(
                    "Tip: use --event-type and --license-number (and --payload), or find IDs in "
                    "Admin: Django Celery Results → Task results, or via shell."
                )
                return None, None, None
            if r.task_name != "licenses.tasks.send_license_notification_email":
                self.stderr.write(
                    self.style.ERROR(f"TaskResult {tid} is not send_license_notification_email: {r.task_name}")
                )
                return None, None, None
            raw = r.task_args
            arr = json.loads(raw) if isinstance(raw, str) else (raw or [])
            ev = arr[0] if len(arr) > 0 else None
            num = int(arr[1]) if len(arr) > 1 else None
            pl = (arr[2] if len(arr) > 2 else None) or {}
            if not isinstance(pl, dict):
                pl = {}
            return ev, num, pl

        ev = options.get("event_type")
        num = options.get("license_number")
        if not ev or num is None:
            self.stderr.write(
                self.style.ERROR("Use --task-result-id ID or both --event-type and --license-number")
            )
            return None, None, None
        try:
            pl = json.loads(options.get("payload") or "{}")
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"Invalid --payload JSON: {e}"))
            return None, None, None
        if not isinstance(pl, dict):
            pl = {}
        return ev, num, pl
