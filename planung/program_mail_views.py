"""Admin page that builds, copies and sends the weekly programme mail."""

from .models import PlanungConfig
from .models import ProgramMailLog
from datetime import date
from datetime import timedelta
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from planung.services import program_mail_service as mail
import json
import logging


logger = logging.getLogger("planung")

# A programme mail covers a week or two; this only catches typos in a date.
MAX_PERIOD_DAYS = 62


def can_use_program_mail(user) -> bool:
    """Staff who may see the plan or the contributions may use the page."""
    return user.is_active and user.is_staff and (
        user.has_perm("planung.view_tagesplan")
        or user.has_perm("contributions.view_contribution")
    )


def program_mail_url(start: date | None = None, end: date | None = None, source: str = "") -> str:
    """Return the page URL, optionally preset to a period and a source."""
    url = reverse("admin:planung_program_mail")
    params = {}
    if start:
        params["von"] = start.isoformat()
    if end:
        params["bis"] = end.isoformat()
    if source:
        params["quelle"] = source
    return f"{url}?{urlencode(params)}" if params else url


def _period(data) -> tuple[date, date, str]:
    """Return (start, end, error) from the request data."""
    default_start, default_end = mail.default_period()
    start = parse_date(data.get("von") or "") or default_start
    end = parse_date(data.get("bis") or "") or (start + timedelta(days=6))
    if end < start:
        start, end = end, start
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        end = start + timedelta(days=MAX_PERIOD_DAYS - 1)
        return start, end, _("The period was shortened to %(days)s days.") % {"days": MAX_PERIOD_DAYS}
    return start, end, ""


def _source(data) -> str:
    value = data.get("quelle") or mail.SOURCE_AUTO
    if value not in (mail.SOURCE_AUTO, mail.SOURCE_PLAN, mail.SOURCE_CONTRIBUTIONS):
        return mail.SOURCE_AUTO
    return value


def _config_url() -> str:
    try:
        if PlanungConfig.objects.filter(pk=1).exists():
            return reverse("admin:planung_planungconfig_change", args=[1])
        return reverse("admin:planung_planungconfig_add")
    except NoReverseMatch:
        return ""


def program_mail_view(request, admin_site):
    """Show the mail for a period; send it on POST."""
    if not can_use_program_mail(request.user):
        raise PermissionDenied

    data = request.POST if request.method == "POST" else request.GET
    start, end, period_note = _period(data)
    source = _source(data)
    change = data.get("aenderung") in ("1", "on", "true")
    config = PlanungConfig.get_config()
    program = mail.collect_program(start, end, source)
    subject, body = mail.render_mail(program, config=config, user=request.user, change=change)

    to = mail.split_addresses(config.program_mail_to)
    bcc = mail.split_addresses(config.program_mail_bcc)

    if request.method == "POST" and request.POST.get("action") == "send":
        subject = (request.POST.get("subject") or "").strip()
        body = request.POST.get("body") or ""
        if not subject or not body.strip():
            messages.error(request, _("Subject and text must not be empty."))
        elif not (to or bcc):
            messages.error(request, _("No recipients are configured for the programme mail."))
        else:
            try:
                sent_to = mail.send_program_mail(
                    subject=subject, body=body, config=config, user=request.user)
            except Exception as exc:  # SMTP errors come in many types
                logger.exception("Programme mail could not be sent")
                messages.error(request, _("The mail could not be sent: %(error)s") % {"error": exc})
            else:
                ProgramMailLog.objects.create(
                    sent_by=request.user,
                    period_start=start,
                    period_end=end,
                    source=program.source,
                    is_change=change,
                    recipients="\n".join(sent_to),
                    subject=subject,
                    body=body,
                )
                messages.success(
                    request,
                    _("The programme mail was sent to %(count)s recipients.") % {"count": len(sent_to)},
                )
                params = {"von": start.isoformat(), "bis": end.isoformat(), "quelle": source}
                if change:
                    params["aenderung"] = "1"
                return HttpResponseRedirect(
                    f"{reverse('admin:planung_program_mail')}?{urlencode(params)}")

    last_sent = ProgramMailLog.objects.filter(
        period_start__lte=end, period_end__gte=start).select_related("sent_by").first()

    context = {
        **admin_site.each_context(request),
        "title": _("Programme mail"),
        "start": start,
        "end": end,
        "source": source,
        "change": change,
        "program": program,
        "subject": subject,
        "body": body,
        "period_note": period_note,
        "recipients_to": to,
        "recipients_bcc": bcc,
        "config_url": _config_url() if request.user.has_perm("planung.change_planungconfig") else "",
        "last_sent": last_sent,
        "log_url": _log_url(request.user),
        "calendar_url": reverse("admin:calendar_weeks_view"),
        "source_choices": (
            (mail.SOURCE_AUTO, _("Automatic (day plans if filled)")),
            (mail.SOURCE_PLAN, _("Day plans")),
            (mail.SOURCE_CONTRIBUTIONS, _("Contributions (premieres)")),
        ),
        "weekdays_json": json.dumps(mail.WEEKDAYS_DE),
        "day_heading_prefix": mail.DAY_HEADING_PREFIX,
        "prev_week":(start - timedelta(days=7), end - timedelta(days=7)),
        "next_week": (start + timedelta(days=7), end + timedelta(days=7)),
    }
    return TemplateResponse(request, "admin/planung/program_mail.html", context)


def _log_url(user) -> str:
    if not user.has_perm("planung.view_programmaillog"):
        return ""
    try:
        return reverse("admin:planung_programmaillog_changelist")
    except NoReverseMatch:
        return ""
