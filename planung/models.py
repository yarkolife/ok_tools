from django.db import models
from django.conf import settings
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


class PlanTemplate(models.Model):
    """Reusable template with predefined items for one broadcast day."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    json_plan = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Plan template")
        verbose_name_plural = _("Plan templates")
        ordering = ("name",)

    def __str__(self):
        """Return template name."""
        return self.name


class PlanChangeLog(models.Model):
    """Audit log for create/update/delete actions of daily plans."""

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"

    ACTION_CHOICES = (
        (ACTION_CREATE, _("Create")),
        (ACTION_UPDATE, _("Update")),
        (ACTION_DELETE, _("Delete")),
    )

    plan_date = models.DateField(db_index=True)
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    old_payload = models.JSONField(default=dict, blank=True)
    new_payload = models.JSONField(default=dict, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planung_change_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Plan change log")
        verbose_name_plural = _("Plan change logs")
        ordering = ("-created_at",)

    def __str__(self):
        """Return compact, human-readable log summary."""
        return f"{self.plan_date.isoformat()} • {self.action}"
