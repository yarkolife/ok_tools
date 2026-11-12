"""Weekly programme e-mail for newspapers and partners.

Builds the subject and the plain-text body of the "TV Programm" mail for a
period, from one of two sources:

* ``plan``: the day plans (Sendeplan). Every planned item is listed; the
  plan already holds exactly what the user wants to announce.
* ``contributions``: the Beiträge. Only premieres are listed: a license
  whose very first broadcast falls into the period, at that time.

The text around the programme (intro, closing words, subject) comes from
``PlanungConfig`` and may use the placeholders ``{von}``, ``{bis}`` and
``{name}`` (the sending staff member).
"""

from __future__ import annotations
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from django.utils import timezone


SOURCE_PLAN = "plan"
SOURCE_CONTRIBUTIONS = "contributions"
SOURCE_AUTO = "auto"

WEEKDAYS_DE = (
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag",
)
DAY_HEADING_PREFIX = "Programm für "
MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
    "September", "Oktober", "November", "Dezember",
)

# Title of the programme preview licenses (anchor_render_service._license_title).
PREVIEW_TITLE_PREFIX = "Programmvorschau vom "

DEFAULT_SUBJECT ="TV Programm vom {von} bis {bis}"
DEFAULT_CHANGE_PREFIX = "ÄNDERUNG: "
DEFAULT_INTRO = (
    "Hallo,\n\n"
    "anbei das Fernsehprogramm vom {von} bis {bis}. Bei Fragen können Sie sich "
    "gerne an mich wenden.\n\n"
    "Programm vom {von} bis {bis}"
)
DEFAULT_CHANGE_INTRO = (
    "Hallo,\n\n"
    "es gibt eine Änderung im Fernsehprogramm vom {von} bis {bis}. "
    "Bitte nutzen Sie das folgende Programm.\n\n"
    "Programm vom {von} bis {bis}"
)
DEFAULT_OUTRO = (
    "Kurzfristige Programmänderungen können vorkommen.\n\n"
    "Für Rückfragen stehen wir gern zur Verfügung.\n\n"
    "Viele Grüße\n"
    "{name}"
)


@dataclass
class ProgramEntry:
    """One announced broadcast."""

    start: str  # "HH:MM"
    title: str
    subtitle: str = ""
    author: str = ""

    def as_text(self) -> str:
        """Return "18:00 Uhr Title - Subtitle" plus "(Author)" below."""
        line = f"{self.start} Uhr {self.title}".rstrip()
        if self.subtitle:
            line += f" - {self.subtitle}"
        if self.author:
            line += f"\n({self.author})"
        return line


@dataclass
class ProgramDay:
    """All announced broadcasts of one day."""

    day: date
    entries: list[ProgramEntry] = field(default_factory=list)
    draft: bool = False


@dataclass
class Program:
    """The programme of a period, with hints for the person sending it."""

    start: date
    end: date
    source: str
    days: list[ProgramDay] = field(default_factory=list)
    # Days of the period without any entry.
    empty_days: list[date] = field(default_factory=list)
    # Days whose plan is still a draft (plan source only).
    draft_days: list[date] = field(default_factory=list)

    @property
    def entry_count(self) -> int:
        """Return the number of announced broadcasts."""
        return sum(len(d.entries) for d in self.days)


def default_period(today: date | None = None) -> tuple[date, date]:
    """Return the seven days starting tomorrow."""
    today = today or timezone.localdate()
    start = today + timedelta(days=1)
    return start, start + timedelta(days=6)


def format_date(value: date) -> str:
    """Return 13.11.2026."""
    return value.strftime("%d.%m.%Y")


def format_long_date(value: date) -> str:
    """Return "Freitag, 13. November 2026" independent of the active locale."""
    return (
        f"{WEEKDAYS_DE[value.weekday()]}, {value.day}. "
        f"{MONTHS_DE[value.month - 1]} {value.year}"
    )


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _profile_name(profile) -> str:
    if not profile:
        return ""
    return f"{profile.first_name or ''} {profile.last_name or ''}".strip()


def _start_key(entry: ProgramEntry) -> str:
    return entry.start.zfill(5)


def collect_from_plan(start: date, end: date) -> Program:
    """Return every item of the day plans between ``start`` and ``end``."""
    from licenses.models import License
    from planung.models import TagesPlan

    plans = {p.datum: p for p in TagesPlan.objects.filter(datum__range=(start, end))}
    numbers = {
        item.get("number")
        for plan in plans.values()
        for item in plan.json_plan.get("items", [])
        if item.get("number")
    }
    licenses = {
        lic.number: lic
        for lic in License.objects.filter(number__in=numbers).select_related("profile")
    }

    program = Program(start=start, end=end, source=SOURCE_PLAN)
    for day in _days(start, end):
        plan = plans.get(day)
        items = plan.json_plan.get("items", []) if plan else []
        entries = []
        for item in items:
            lic = licenses.get(item.get("number"))
            title = str(item.get("title") or getattr(lic, "title", "") or "").strip()
            if not title:
                continue
            subtitle = str(item.get("subtitle") or getattr(lic, "subtitle", "") or "").strip()
            author = (
                str(item.get("sender_responsible") or item.get("author") or "").strip()
                or _profile_name(getattr(lic, "profile", None))
            )
            entries.append(ProgramEntry(
                start=str(item.get("start") or "")[:5],
                title=title,
                subtitle=subtitle,
                author=author,
            ))
        if not entries:
            program.empty_days.append(day)
            continue
        entries.sort(key=_start_key)
        draft = bool(plan.json_plan.get("draft", False))
        if draft:
            program.draft_days.append(day)
        program.days.append(ProgramDay(day=day, entries=entries, draft=draft))
    return program


def collect_from_contributions(start: date, end: date) -> Program:
    """Return the premieres (first broadcast of a license) in the period."""
    from contributions.models import Contribution

    tz = timezone.get_current_timezone()
    range_start = timezone.make_aware(datetime.combine(start, time.min), tz)
    range_end = timezone.make_aware(datetime.combine(end, time.max), tz)
    contributions = (
        Contribution.objects
        .filter(broadcast_date__range=(range_start, range_end))
        .select_related("license", "license__profile")
        .order_by("broadcast_date")
    )

    # A premiere is the license's very first broadcast; repetitions of
    # earlier weeks (the night loop) and later repetitions are left out.
    from django.db.models import Min
    first = dict(
        Contribution.objects
        .filter(license_id__in=contributions.values("license_id"))
        .values("license_id")
        .annotate(first=Min("broadcast_date"))
        .values_list("license_id", "first")
    )
    by_day: dict[date, list[ProgramEntry]] = {}
    for contribution in contributions:
        if contribution.broadcast_date != first.get(contribution.license_id):
            continue
        lic = contribution.license
        if (lic.title or "").startswith(PREVIEW_TITLE_PREFIX):
            continue  # the rendered programme preview, not a broadcast
        local = timezone.localtime(contribution.broadcast_date)
        by_day.setdefault(local.date(), []).append(ProgramEntry(
            start=local.strftime("%H:%M"),
            title=(lic.title or "").strip(),
            subtitle=(lic.subtitle or "").strip(),
            author=_profile_name(lic.profile),
        ))

    program = Program(start=start, end=end, source=SOURCE_CONTRIBUTIONS)
    for day in _days(start, end):
        entries = by_day.get(day)
        if entries:
            program.days.append(ProgramDay(day=day, entries=entries))
        else:
            program.empty_days.append(day)
    return program


def plan_has_items(start: date, end: date) -> bool:
    """Return whether any day plan in the period holds an item."""
    from planung.models import TagesPlan

    return any(
        plan.json_plan.get("items")
        for plan in TagesPlan.objects.filter(datum__range=(start, end)).only("json_plan")
    )


def collect_program(start: date, end: date, source: str = SOURCE_AUTO) -> Program:
    """Collect the programme; ``auto`` prefers the plan when it is filled."""
    if source == SOURCE_AUTO:
        source = SOURCE_PLAN if plan_has_items(start, end) else SOURCE_CONTRIBUTIONS
    if source == SOURCE_CONTRIBUTIONS:
        return collect_from_contributions(start, end)
    return collect_from_plan(start, end)


def _fill(template: str, values: dict[str, str]) -> str:
    """Replace the known placeholders only; other braces stay as typed."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def sender_name(user) -> str:
    """Return the staff member's name for the signature."""
    if user is None:
        return ""
    name = user.get_full_name().strip() if hasattr(user, "get_full_name") else ""
    if not name:
        name = _profile_name(getattr(user, "profile", None))
    return name or (getattr(user, "email", "") or "")


def render_mail(program: Program, config=None, user=None, change: bool = False) -> tuple[str, str]:
    """Return ``(subject, body)`` of the programme mail."""
    values = {
        "von": format_date(program.start),
        "bis": format_date(program.end),
        "name": sender_name(user),
    }
    subject_tpl = getattr(config, "program_mail_subject", "") or DEFAULT_SUBJECT
    if change:
        intro_tpl = getattr(config, "program_mail_change_intro", "") or DEFAULT_CHANGE_INTRO
    else:
        intro_tpl = getattr(config, "program_mail_intro", "") or DEFAULT_INTRO
    outro_tpl = getattr(config, "program_mail_outro", "") or DEFAULT_OUTRO

    subject = _fill(subject_tpl, values).strip()
    if change:
        change_tpl = getattr(config, "program_mail_change_prefix", None)
        change_tpl = DEFAULT_CHANGE_PREFIX if change_tpl is None else change_tpl
        if any("{" + key + "}" in change_tpl for key in (*values, "betreff")):
            # A whole subject of its own; {betreff} inserts the normal subject.
            subject = _fill(change_tpl, {**values, "betreff": subject}).strip()
        else:
            # Plain text such as "ÄNDERUNG: " goes in front of the normal subject.
            subject = f"{change_tpl}{subject}"

    # Texts typed in the admin arrive with Windows line ends.
    intro_tpl, outro_tpl = (t.replace("\r\n", "\n").replace("\r", "\n") for t in (intro_tpl, outro_tpl))
    blocks = [_fill(intro_tpl, values).strip()]
    for day in program.days:
        blocks.append(f"{DAY_HEADING_PREFIX}{format_long_date(day.day)}")
        blocks.extend(entry.as_text() for entry in day.entries)
    blocks.append(_fill(outro_tpl, values).strip())
    body = "\n\n".join(b for b in blocks if b) + "\n"
    return subject, body


def is_day_heading(line: str) -> bool:
    """Return whether ``line`` is a day heading such as "Programm für Freitag, …"."""
    return line.startswith(DAY_HEADING_PREFIX) and line[len(DAY_HEADING_PREFIX):].split(",")[0] in WEEKDAYS_DE


def text_to_html(text: str) -> str:
    """Return the HTML version of the (possibly hand edited) mail text.

    The text stays the source: line breaks are kept and the day headings are
    set in bold. Same rule as ``textToHtml`` in program_mail.html.
    """
    from django.utils.html import escape

    lines = []
    for line in text.rstrip("\n").split("\n"):
        line = line.rstrip("\r")
        html = escape(line)
        if is_day_heading(line.strip()):
            html = f"<strong>{html}</strong>"
        lines.append(html)
    return (
        '<div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px;">'
        + "<br>\n".join(lines)
        + "</div>"
    )


def split_addresses(value: str) -> list[str]:
    """Split a recipient field on new lines, commas and semicolons.

    Accepts ``a@b.de``, ``<a@b.de>`` and ``Name <a@b.de>`` (also with a
    quoted name); a name stays with its address.
    """
    from email.utils import getaddresses
    import re

    parts = [p for p in re.split(r"[\r\n;]+", value or "") if p.strip()]
    result = []
    for name, address in getaddresses(parts):
        address, name = address.strip(), name.strip()
        if not address:
            continue
        if not name:
            result.append(address)
        elif any(c in name for c in ',;:"()<>@[]\\'):
            escaped = name.replace("\\", "\\\\").replace('"', '\\"')
            result.append(f'"{escaped}" <{address}>')
        else:
            result.append(f"{name} <{address}>")
    return result


def invalid_addresses(value: str) -> list[str]:
    """Return the entries of a recipient field that are no e-mail address."""
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    from email.utils import parseaddr

    bad = []
    for entry in split_addresses(value):
        try:
            validate_email(parseaddr(entry)[1])
        except ValidationError:
            bad.append(entry)
    return bad


def send_program_mail(*, subject: str, body: str, config, user) -> list[str]:
    """Send the mail to the configured recipients; return everyone it went to.

    ``To`` holds the configured recipients; when only BCC is configured the
    mail goes to the sender itself so that the recipients stay hidden.
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    to = split_addresses(config.program_mail_to)
    bcc = split_addresses(config.program_mail_bcc)
    if not to and not bcc:
        raise ValueError("no recipients configured")
    from_email = (config.program_mail_from or "").strip() or settings.DEFAULT_FROM_EMAIL
    reply_to = split_addresses(config.program_mail_reply_to)
    if not reply_to and getattr(user, "email", ""):
        reply_to = [user.email]
    message = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=from_email,
        to=to or [from_email],
        bcc=bcc,
        reply_to=reply_to,
    )
    # Day headings in bold; mail programs without HTML show the text part.
    message.attach_alternative(text_to_html(body), "text/html")
    message.send(fail_silently=False)
    return to + bcc
