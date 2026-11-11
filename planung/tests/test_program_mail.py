"""Weekly programme mail: text, sources, sending."""

from contributions.models import Contribution
from datetime import date
from datetime import datetime
from datetime import timedelta
from django.contrib.auth.models import Permission
from django.core import mail as django_mail
from django.urls import reverse
from django.utils import timezone
from licenses.models import License
from licenses.models import default_category
from planung.models import PlanungConfig
from planung.models import ProgramMailLog
from planung.models import TagesPlan
from planung.services import program_mail_service as pm
import pytest


START = date(2026, 11, 13)   # Friday
END = date(2026, 11, 19)     # Thursday


def _license(profile, title, subtitle=""):
    return License.objects.create(
        profile=profile,
        category=default_category(),
        title=title,
        subtitle=subtitle,
        description="",
        duration=timedelta(minutes=20),
        further_persons="",
        suggested_date=None,
        repetitions_allowed=True,
        media_authority_exchange_allowed=True,
        youth_protection_necessary=False,
        store_in_ok_media_library=True,
    )


def _broadcast(lic, day, hour, minute=0):
    when = timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))
    return Contribution.objects.create(license=lic, broadcast_date=when, live=False)


@pytest.fixture
def staff_user(user):
    """Staff member allowed to see the plan."""
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    user.user_permissions.add(Permission.objects.get(codename="view_tagesplan"))
    return user


@pytest.fixture
def plan_week(db):
    """Two planned days, one of them a draft, items out of order."""
    TagesPlan.objects.create(datum=START, json_plan={"draft": False, "items": [
        {"start": "18:05:00", "title": "Voll im Fokus",
         "subtitle": "Eine Sendung des Jungeakadamiemedien 2026",
         "number": 1, "sender_responsible": "Johana Alkhouri"},
        {"start": "18:00:00", "title": "Mein Lieblingsort",
         "subtitle": "Waldgeister Manga Café Magdeburg",
         "number": 2, "sender_responsible": "Lotta Lange"},
    ]})
    TagesPlan.objects.create(datum=START + timedelta(days=3), json_plan={"draft": True, "items": [
        {"start": "14:00:00", "title": "Jugendgottesdienst", "number": 3,
         "sender_responsible": "Michael Germann"},
    ]})


def test_long_date_is_german_whatever_the_locale():
    assert pm.format_long_date(date(2026, 11, 13)) == "Freitag, 13. November 2026"
    assert pm.format_long_date(date(2026, 3, 1)) == "Sonntag, 1. März 2026"


def test_default_period_is_seven_days_from_tomorrow():
    assert pm.default_period(date(2026, 11, 12)) == (START, END)


@pytest.mark.django_db
def test_plan_mail_matches_the_newspaper_format(plan_week):
    program = pm.collect_program(START, END)
    assert program.source == pm.SOURCE_PLAN
    assert [d.day for d in program.days] == [START, START + timedelta(days=3)]
    assert program.draft_days == [START + timedelta(days=3)]
    assert len(program.empty_days) == 5

    subject, body = pm.render_mail(program)

    assert subject == "TV Programm vom 13.11.2026 bis 19.11.2026"
    assert body.startswith(
        "Hallo,\n\nanbei das Fernsehprogramm vom 13.11.2026 bis 19.11.2026.")
    assert (
        "Programm vom 13.11.2026 bis 19.11.2026\n\n"
        "Programm für Freitag, 13. November 2026\n\n"
        "18:00 Uhr Mein Lieblingsort - Waldgeister Manga Café Magdeburg\n"
        "(Lotta Lange)\n\n"
        "18:05 Uhr Voll im Fokus - Eine Sendung des Jungeakadamiemedien 2026\n"
        "(Johana Alkhouri)\n\n"
        "Programm für Montag, 16. November 2026\n\n"
        "14:00 Uhr Jugendgottesdienst\n"
        "(Michael Germann)\n\n"
        "Kurzfristige"
    ) in body


@pytest.mark.django_db
def test_configured_texts_and_change_prefix(plan_week, staff_user):
    config = PlanungConfig.get_config()
    config.program_mail_subject = "TV Programm des Offenen Kanals MQ vom {von} bis {bis}"
    config.program_mail_change_prefix = "ÄNDERUNG – "
    config.program_mail_change_intro = "Hallo,\n\nkorrigiert ({von}–{bis}):"
    config.program_mail_outro = "Viele Grüße\n{name}\nIhr OK-Team {unbekannt}"
    config.save()

    subject, body = pm.render_mail(
        pm.collect_program(START, END), config=config, user=staff_user, change=True)

    assert subject == "ÄNDERUNG – TV Programm des Offenen Kanals MQ vom 13.11.2026 bis 19.11.2026"
    assert body.startswith("Hallo,\n\nkorrigiert (13.11.2026–19.11.2026):\n\nProgramm für Freitag")
    # Unknown placeholders stay as typed instead of breaking the mail.
    assert body.endswith("Viele Grüße\njohn doe\nIhr OK-Team {unbekannt}\n")


@pytest.mark.django_db
def test_contributions_list_only_premieres(user):
    profile = user.profile
    old = _license(profile, "Schon gesendet")
    a = _license(profile, "Red Devils-TV")
    b = _license(profile, "Magazinsendung", "Ergebnisse des Seminars")
    _broadcast(old, START - timedelta(days=1), 18)   # premiere last week
    _broadcast(old, START + timedelta(days=1), 0)    # night repetition: dropped
    _broadcast(a, START + timedelta(days=1), 18, 10) # premiere
    _broadcast(a, START + timedelta(days=2), 12)     # repetition: dropped
    _broadcast(b, END, 18, 15)
    _broadcast(_license(profile, "Programmvorschau vom 14.11.2026"), START, 19, 40)

    program = pm.collect_program(START, END, pm.SOURCE_CONTRIBUTIONS)
    _, body = pm.render_mail(program)

    assert program.entry_count == 2
    assert "Schon gesendet" not in body
    assert "Programm für Samstag, 14. November 2026\n\n18:10 Uhr Red Devils-TV\n(john doe)" in body
    assert "Programm für Donnerstag, 19. November 2026\n\n" \
           "18:15 Uhr Magazinsendung - Ergebnisse des Seminars" in body
    assert "Sonntag, 15. November" not in body


@pytest.mark.django_db
def test_auto_falls_back_to_contributions_without_a_plan(user):
    _broadcast(_license(user.profile, "Nur Beitrag"), START, 18)
    program = pm.collect_program(START, END)
    assert program.source == pm.SOURCE_CONTRIBUTIONS
    assert program.entry_count == 1


def test_html_version_sets_day_headings_in_bold():
    html = pm.text_to_html(
        "Hallo <Team>,\n\nProgramm für Freitag, 13. November 2026\n\n"
        "18:00 Uhr Programm für Kinder\n(A & B)\n")
    assert "<strong>Programm für Freitag, 13. November 2026</strong>" in html
    assert "Hallo &lt;Team&gt;,<br>" in html
    # Only real day headings: a title starting with the same words stays plain.
    assert "18:00 Uhr Programm für Kinder<br>" in html
    assert "(A &amp; B)" in html


@pytest.mark.django_db
def test_page_builds_the_mail(client, staff_user, plan_week):
    client.force_login(staff_user)
    response = client.get(
        reverse("admin:planung_program_mail"),
        {"von": START.isoformat(), "bis": END.isoformat()},
        secure=True,
    )
    assert response.status_code == 200
    assert response.context["subject"] == "TV Programm vom 13.11.2026 bis 19.11.2026"
    assert "18:00 Uhr Mein Lieblingsort" in response.context["body"]


@pytest.mark.django_db
def test_page_needs_permission(client, user):
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client.force_login(user)
    response = client.get(reverse("admin:planung_program_mail"), secure=True)
    assert response.status_code == 403


@pytest.mark.django_db
def test_send_uses_the_edited_text_and_logs_it(client, staff_user, plan_week, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    config = PlanungConfig.get_config()
    config.program_mail_to = "redaktion@example.org"
    config.program_mail_bcc = "a@example.org, b@example.org\nc@example.org"
    config.save()
    client.force_login(staff_user)

    response = client.post(reverse("admin:planung_program_mail"), {
        "action": "send",
        "von": START.isoformat(),
        "bis": END.isoformat(),
        "quelle": "auto",
        "aenderung": "1",
        "subject": "ÄNDERUNG: TV Programm",
        "body": "Hallo,\n\nhand edited\n",
    }, secure=True)

    assert response.status_code == 302
    assert len(django_mail.outbox) == 1
    sent = django_mail.outbox[0]
    assert sent.subject == "ÄNDERUNG: TV Programm"
    assert sent.body == "Hallo,\n\nhand edited\n"
    assert sent.to == ["redaktion@example.org"]
    assert sent.bcc == ["a@example.org", "b@example.org", "c@example.org"]
    assert sent.reply_to == [staff_user.email]
    html, mimetype = sent.alternatives[0]
    assert mimetype == "text/html"
    assert "Hallo,<br>" in html
    log = ProgramMailLog.objects.get()
    assert (log.period_start, log.period_end, log.source, log.is_change) == (START, END, "plan", True)
    assert log.sent_by == staff_user


@pytest.mark.django_db
def test_send_without_recipients_sends_nothing(client, staff_user, plan_week, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    client.force_login(staff_user)
    response = client.post(reverse("admin:planung_program_mail"), {
        "action": "send", "von": START.isoformat(), "bis": END.isoformat(),
        "subject": "x", "body": "y",
    }, secure=True)
    assert response.status_code == 200
    assert django_mail.outbox == []
    assert not ProgramMailLog.objects.exists()
