"""
Start page of the Unfold admin (/admin/).

UNFOLD["DASHBOARD_CALLBACK"] adds the data, the page itself is
ok_tools/unfold_templates/admin/index.html. Blocks:

- "Läuft gerade": Celery tasks that are queued or running, plus the ones
  that finished in the last hours (render, imports, scans ...). The block
  reloads itself every few seconds through ``tasks_fragment``.
- Quick links to the daily work.
- "Heute zu tun": counters (licenses to approve, rentals due/overdue,
  open rental requests, open notifications), each linking to its list.
- "Diese Woche im Programm": fill rate of this and next week (planung).
- "Probleme": contributions of the next days without a usable video,
  storage locations that did not answer, failed exchange imports.
- "Neu im Austausch": exchange items new since the last visit.
- The user's own recent changes (admin log).

Every block checks the module flag and the user's permissions and is left
out when it does not apply.
"""

from __future__ import annotations
from datetime import date
from datetime import datetime
from datetime import timedelta
from django.apps import apps
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from typing import Any


LICENSE_APPROVAL_DAYS = 60      # older unconfirmed licenses are ignored
PROBLEM_DAYS_AHEAD = 3          # contributions without video: look this far ahead
FAILED_IMPORT_DAYS = 7
LAST_VISIT_SESSION_KEY = "ok_dashboard_last_visit"

RUNNING_STATES = ("PENDING", "RECEIVED", "STARTED", "RETRY", "PROGRESS")
RECENT_HOURS = 12

# Celery task function name -> label shown on the dashboard.
TASK_LABELS: dict[str, Any] = {
    "render_video_task": _("Video rendering"),
    "anchor_render_chain": _("Video rendering"),
    "poll_anchor_render_job": _("Video rendering"),
    "okmq_render_reel_task": _("Reel rendering"),
    "okmq_generate_hooks_task": _("Reel hooks"),
    "generate_slideshow_task": _("Slideshow"),
    "normalize_audio_task": _("Audio normalisation"),
    "analyze_audio_normalize_job_task": _("Audio analysis"),
    "transcode_hevc_to_h264": _("Transcoding HEVC → H.264"),
    "export_to_server_task": _("Export to server"),
    "import_exchange_item_task": _("Exchange import"),
    "download_exchange_files_task": _("Exchange download"),
    "sync_exchange_folders_task": _("Exchange folder sync"),
    "copy_videos_for_plan": _("Copy videos for playout"),
    "sync_playout_missing_media": _("Playout media sync"),
    "run_scan_video_storage_task": _("Video storage scan"),
    "run_auto_scan_task": _("Video storage scan"),
    "run_update_video_metadata_task": _("Video metadata update"),
    "run_generate_covers_task": _("Cover generation"),
    "run_find_duplicates_task": _("Duplicate search"),
    "run_backup_db_task": _("Database backup"),
    "download_nextcloud_video_file_to_storage": _("Nextcloud download"),
    "download_pending_nextcloud_videos": _("Nextcloud download"),
}


def _label(task_name: str | None) -> str:
    short = (task_name or "").rsplit(".", 1)[-1]
    label = TASK_LABELS.get(short)
    return str(label) if label else short.replace("_task", "").replace("_", " ").strip().capitalize() or "—"


def _duration(start, end) -> str:
    if not start:
        return ""
    seconds = int(((end or timezone.now()) - start).total_seconds())
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def _url(name: str, *args) -> str | None:
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return None


def task_overview() -> dict[str, Any]:
    """Running and recently finished Celery tasks (django_celery_results)."""
    if not apps.is_installed("django_celery_results"):
        return {"tasks_available": False}
    from django_celery_results.models import TaskResult

    now = timezone.now()
    rows = []
    running = (TaskResult.objects
               .filter(status__in=RUNNING_STATES, date_created__gte=now - timedelta(days=2))
               .order_by("-date_created")[:20])
    recent = (TaskResult.objects
              .exclude(status__in=RUNNING_STATES)
              .filter(date_done__gte=now - timedelta(hours=RECENT_HOURS))
              .order_by("-date_done")[:8])
    for group, queryset in (("running", running), ("recent", recent)):
        for task in queryset:
            start = task.date_started or task.date_created
            rows.append({
                "group": group,
                "label": _label(task.task_name),
                "name": task.periodic_task_name or task.task_name or "",
                "status": task.status,
                "start": start,
                "done": task.date_done,
                "duration": _duration(start, task.date_done if group == "recent" else None),
                "worker": (task.worker or "").split("@")[-1],
                "url": _url("admin:django_celery_results_taskresult_change", task.pk),
            })
    return {
        "tasks_available": True,
        "tasks_running": [r for r in rows if r["group"] == "running"],
        "tasks_recent": [r for r in rows if r["group"] == "recent"],
        "tasks_recent_hours": RECENT_HOURS,
        "tasks_list_url": _url("admin:django_celery_results_taskresult_changelist"),
        "tasks_checked_at": now,
    }


def quick_links(request) -> list[dict[str, Any]]:
    """Shortcuts to the daily work; only those the user may open."""
    candidates = [
        (_("Projects"), "school", "admin:projects_project_changelist", "projects.view_project"),
        (_("Licenses"), "verified", "admin:licenses_license_changelist", "licenses.view_license"),
        (_("Calendar weeks"), "calendar_month", "admin:calendar_weeks_view", "planung.view_tagesplan"),
        (_("New rental"), "shopping_cart", "rental:admin_rental_process", "rental.view_rentalrequest"),
        (_("Exchange feed"), "swap_horiz", "austausch:feed", "austausch.view_exchangeitem"),
        (_("DISA import"), "upload_file", "admin:contributions_disaimport_add", "contributions.add_disaimport"),
        (_("Video files"), "movie", "admin:media_files_videofile_changelist", "media_files.view_videofile"),
        (_("Statistics"), "monitoring", "dashboard:main", None),
    ]
    links = []
    for title, icon, url_name, perm in candidates:
        url = _url(url_name)
        if url and (perm is None or request.user.has_perm(perm)):
            links.append({"title": title, "icon": icon, "url": url})
    return links


def recent_actions(request, limit: int = 8) -> list[LogEntry]:
    return list(LogEntry.objects
                .filter(user=request.user)
                .select_related("content_type")
                .order_by("-action_time")[:limit])


def _enabled(flag: str, default: bool = False) -> bool:
    return bool(getattr(settings, flag, default))


def _qs(url: str | None, query: str) -> str | None:
    return f"{url}?{query}" if url else None


def todo_counters(request) -> list[dict[str, Any]]:
    """Counters for "Heute zu tun". Zero counters are shown muted."""
    user = request.user
    now = timezone.now()
    items = []

    if _enabled("LICENSES_ENABLED", True) and user.has_perm("licenses.view_license"):
        from licenses.models import License
        since = (now - timedelta(days=LICENSE_APPROVAL_DAYS)).date()
        count = License.objects.filter(confirmed=False, created_at__date__gte=since).count()
        items.append({
            "title": _("Licenses to approve"),
            "hint": _("created in the last %(days)s days") % {"days": LICENSE_APPROVAL_DAYS},
            "count": count, "tone": "warning", "icon": "verified",
            "url": _qs(_url("admin:licenses_license_changelist"),
                       f"confirmed__exact=0&created_at__date__gte={since.isoformat()}"),
        })

    if _enabled("RENTAL_ENABLED") and user.has_perm("rental.view_rentalrequest"):
        from rental.models import RentalRequest
        rentals = RentalRequest.objects.all()
        rental_list = _url("rental:list")
        items += [
            {"title": _("Rentals overdue"), "icon": "assignment_late", "tone": "danger",
             "count": rentals.filter(status="issued", requested_end_date__lt=now).count(),
             "url": _qs(rental_list, "status=overdue")},
            {"title": _("Rentals due today"), "icon": "event_upcoming", "tone": "warning",
             "count": rentals.filter(status="issued",
                                     requested_end_date__date=timezone.localdate()).count(),
             "url": _qs(rental_list, "status=issued")},
            {"title": _("Rental requests waiting"), "icon": "pending_actions", "tone": "info",
             "count": rentals.filter(status="draft").count(),
             "url": _qs(rental_list, "status=draft")},
        ]

    if apps.is_installed("notifications") and user.is_staff:
        try:
            from notifications import selectors
            count = selectors.action_count(user, request)
        except Exception:
            count = None
        if count is not None:
            items.append({"title": _("Open notifications"), "icon": "notifications",
                          "tone": "info", "count": count,
                          "url": _url("admin:notifications_feed")})
    return items


def week_program(request) -> list[dict[str, Any]]:
    """Fill rate of this and the next broadcast week."""
    if not _enabled("PLANUNG_ENABLED") or not request.user.has_perm("planung.view_tagesplan"):
        return []
    try:
        from planung.views import compute_week_stats
        today = timezone.localdate()
        rows = compute_week_stats(today - timedelta(days=today.weekday()), 2)
    except Exception:
        return []
    calendar = _url("admin:calendar_weeks_view")
    weeks = []
    for label, row in zip([_("This week"), _("Next week")], rows):
        start = date.fromisoformat(row["week_start"])
        end = date.fromisoformat(row["week_end"])
        rate = row["fill_rate"]
        if rate > 100:
            tone = "danger"
        elif rate >= 80:
            tone = "success"
        elif rate >= 40:
            tone = "warning"
        else:
            tone = "muted"
        weeks.append({
            "label": label,
            "kw": start.isocalendar()[1],
            "range": f"{start:%d.%m.} – {end:%d.%m.}",
            "rate": rate,
            "bar": min(rate, 100),
            "tone": tone,
            "planned_days": row["planned_days"],
            "licenses": row["licenses_count"],
            "url": _qs(calendar, f"start={start.isoformat()}"),
        })
    return weeks


def problems(request) -> list[dict[str, Any]]:
    """Things that need a look soon (empty list: all fine)."""
    user = request.user
    now = timezone.now()
    found = []

    if (_enabled("LICENSES_ENABLED", True) and _enabled("MEDIA_FILES_ENABLED")
            and user.has_perm("contributions.view_contribution")):
        from contributions.models import Contribution
        from django.db.models import Q
        soon = (Contribution.objects
                .filter(broadcast_date__gte=now,
                        broadcast_date__lt=now + timedelta(days=PROBLEM_DAYS_AHEAD))
                .filter(Q(license__video_file__isnull=True)
                        | Q(license__video_file__is_available=False))
                .select_related("license")
                .order_by("broadcast_date"))
        shown = list(soon[:6])
        for contribution in shown:
            when = timezone.localtime(contribution.broadcast_date).strftime("%d.%m. %H:%M")
            found.append({
                "icon": "videocam_off", "tone": "danger",
                "title": contribution.license.title if contribution.license_id else str(contribution),
                "meta": _("on air %(when)s, no usable video") % {"when": when},
                "url": _url("admin:licenses_license_change", contribution.license_id),
            })
        rest = soon.count() - len(shown)
        if rest > 0:
            found.append({"icon": "more_horiz", "tone": "muted",
                          "title": _("%(n)s more contributions without video") % {"n": rest},
                          "meta": "", "url": _url("admin:calendar_weeks_view")})

    if _enabled("MEDIA_FILES_ENABLED") and user.has_perm("media_files.view_storagelocation"):
        from media_files.models import StorageLocation
        for location in StorageLocation.objects.filter(
                is_active=True, last_health_check__isnull=False, last_read_mbps__isnull=True):
            when = timezone.localtime(location.last_health_check).strftime("%d.%m. %H:%M")
            found.append({
                "icon": "hard_drive", "tone": "danger", "title": location.name,
                "meta": _("did not answer (checked %(when)s)") % {"when": when},
                "url": _url("admin:media_files_storagelocation_change", location.pk),
            })

    if _enabled("AUSTAUSCH_ENABLED") and user.has_perm("austausch.view_exchangeimport"):
        from austausch.models import ExchangeImport
        count = ExchangeImport.objects.filter(
            status="failed",
            created_at__gte=now - timedelta(days=FAILED_IMPORT_DAYS)).count()
        if count:
            found.append({
                "icon": "sync_problem", "tone": "warning",
                "title": _("%(n)s failed exchange imports") % {"n": count},
                "meta": _("last %(days)s days") % {"days": FAILED_IMPORT_DAYS},
                "url": _qs(_url("admin:austausch_exchangeimport_changelist"),
                           "status__exact=failed"),
            })
    return found


def exchange_news(request) -> dict[str, Any] | None:
    """Exchange items that arrived since the user's previous visit of /admin/."""
    if not _enabled("AUSTAUSCH_ENABLED") or not request.user.has_perm("austausch.view_exchangeitem"):
        return None
    from austausch.models import ExchangeItem

    previous = request.session.get(LAST_VISIT_SESSION_KEY)
    request.session[LAST_VISIT_SESSION_KEY] = timezone.now().isoformat()
    since = None
    if previous:
        try:
            since = datetime.fromisoformat(previous)
        except ValueError:
            since = None
    if since is None:
        since = timezone.now() - timedelta(days=1)

    new_items = ExchangeItem.objects.filter(import_status="new")
    arrived = new_items.filter(discovered_at__gt=since)
    return {
        "since": since,
        "arrived": arrived.count(),
        "waiting": new_items.count(),
        "latest": list(arrived.order_by("-discovered_at")[:5]),
        "url": _qs(_url("austausch:feed"), "status=new"),
    }


def dashboard_callback(request, context: dict[str, Any]) -> dict[str, Any]:
    context.update(task_overview())
    context["quick_links"] = quick_links(request)
    context["todo_counters"] = todo_counters(request)
    context["week_program"] = week_program(request)
    context["problems"] = problems(request)
    context["exchange_news"] = exchange_news(request)
    context["recent_actions"] = recent_actions(request)
    return context


@staff_member_required
def tasks_fragment(request):
    """The "Läuft gerade" block alone, reloaded by htmx on the start page."""
    return TemplateResponse(request, "admin/_ok_tasks.html", task_overview())
