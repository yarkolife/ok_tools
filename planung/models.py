from django.db import models
from django.utils.translation import gettext_lazy as _


class TagesPlan(models.Model):
    """Model for storing daily broadcast plans.

    Each plan represents a single day with planned items, draft/planned
    status, and optional comments.
    """

    datum = models.DateField(unique=True)
    json_plan = models.JSONField(default=dict, blank=True)
    kommentar = models.TextField(blank=True)

    def __str__(self):
        """Return a formatted date string representing this plan."""
        return self.datum.strftime("%d.%m.%Y")


class CalendarWeeksProxy(TagesPlan):
    """Virtual model just to show a menu entry that opens the calendar view."""

    class Meta:
        """Meta options for the CalendarWeeksProxy class."""

        verbose_name = _('Calendar weeks')
        verbose_name_plural = _('Calendar weeks')
        proxy = True
