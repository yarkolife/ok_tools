from datetime import datetime
from django.conf import settings
from django.http import FileResponse
from django.utils.translation import gettext as _
from icalendar import Calendar
from icalendar import Event
from zoneinfo import ZoneInfo
import io
import logging


logger = logging.getLogger('django')


def ics_export(queryset) -> FileResponse:
    """Export the dates form the given projects."""
    c = Calendar()

    for project in queryset:
        begin_date: datetime = project.begin_date.astimezone(
            tz=ZoneInfo(settings.TIME_ZONE)) if project.begin_date else None

        end_date: datetime = project.end_date.astimezone(
            tz=ZoneInfo(settings.TIME_ZONE)) if project.end_date else None

        e = Event()
        e.add('summary', project.title)
        e.add('description', project.topic)
        e.add('dtstart', begin_date)
        e.add('dtend', end_date)
        c.add_component(e)

    ics_stream = io.BytesIO()
    ics_stream.write(c.to_ical())
    ics_stream.seek(0)
    return FileResponse(ics_stream, filename=_('projects.ics'))
