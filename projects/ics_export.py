from django.conf import settings
from django.http import FileResponse
from django.utils.translation import gettext as _
from ics import Calendar
from ics import Event
from zoneinfo import ZoneInfo
import io


def ics_export(queryset) -> FileResponse:
    """Export the dates form the given projects."""
    c = Calendar()

    for project in queryset:
        begin_date = project.begin_date.astimezone(
            tz=ZoneInfo(settings.TIME_ZONE)) if project.begin_date else None

        end_date = project.end_date.astimezone(
            tz=ZoneInfo(settings.TIME_ZONE)) if project.end_date else None

        e = Event()
        e.name = project.title
        e.description = project.topic
        e.begin = begin_date
        e.end = end_date
        e.duration = project.duration
        c.events.add(e)

    ics_stream = io.BytesIO()
    ics_stream.write(c.serialize().encode('utf-8'))
    ics_stream.seek(0)
    return FileResponse(ics_stream, filename=_('projects.ics'))
