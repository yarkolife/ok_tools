"""Form fields of the projects admin."""

from django import forms
from django.utils.translation import gettext_lazy as _
import datetime
import re


_HOURS_MINUTES = re.compile(r'^\s*(\d{1,3})\s*(?::\s*(\d{1,2}))?\s*(?::\s*(\d{1,2}))?\s*$')


class HoursMinutesDurationField(forms.DurationField):
    """Project duration entered as hours and minutes.

    "2:30" is 2 hours 30 minutes (Django's DurationField reads it as
    2 minutes 30 seconds), "3" is 3 hours. "h:mm:ss" is still accepted, so
    older values with seconds survive a save unchanged.
    """

    default_error_messages = {
        'invalid': _('Enter the duration as hours:minutes, e.g. 2:30.'),
    }

    def prepare_value(self, value):
        if isinstance(value, datetime.timedelta):
            seconds = int(value.total_seconds())
            hours, rest = divmod(seconds, 3600)
            minutes, secs = divmod(rest, 60)
            if secs:
                return f'{hours}:{minutes:02d}:{secs:02d}'
            return f'{hours}:{minutes:02d}'
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.timedelta):
            return value
        match = _HOURS_MINUTES.match(str(value))
        if not match:
            raise forms.ValidationError(self.error_messages['invalid'], code='invalid')
        hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
        if minutes > 59 or seconds > 59:
            raise forms.ValidationError(self.error_messages['invalid'], code='invalid')
        return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)
