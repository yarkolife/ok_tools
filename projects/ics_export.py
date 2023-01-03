from django.http import FileResponse
from django.utils.translation import gettext as _
from icalendar import Calendar
from icalendar import Event
import io
import logging


logger = logging.getLogger('django')


def ics_export(queryset) -> FileResponse:
    """Export the dates form the given projects."""
    c = Calendar()

    for project in queryset:
        topic = project.topic or ""
        description = (
            topic
            + '\n\n'
            + _('Dauer: %(duration)s')
            % {'duration': project.duration}
        )

        e = Event()
        e.add('summary', project.title)
        e.add('description', description)
        e.add('dtstart', project.date)
        c.add_component(e)

    ics_stream = io.BytesIO()
    ics_stream.write(c.to_ical())
    ics_stream.seek(0)
    return FileResponse(ics_stream, filename=_('projects.ics'))
