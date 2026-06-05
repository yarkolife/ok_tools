from django.conf import settings
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


class PlanungConfig(models.Model):
    """Configuration for planning module integrations (singleton)."""

    PLAYOUT_MISSING_TASK_NAME = "planung.tasks.sync_playout_missing_media"

    playout_import_url = models.URLField(
        blank=True,
        verbose_name=_("Playout import URL"),
        help_text=_("External playout endpoint, e.g. http://192.168.88.50/api/media/import"),
    )
    playout_import_api_key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Playout import API key"),
        help_text=_("API key sent as X-API-Key when planned media metadata is exported."),
    )
    playout_import_timeout = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Playout import timeout (seconds)"),
        help_text=_("HTTP timeout for playout metadata import requests."),
    )
    playout_missing_url = models.URLField(
        blank=True,
        verbose_name=_("Playout missing metadata URL"),
        help_text=_(
            "Endpoint for files without metadata, e.g. "
            "http://192.168.88.50/api/media/import/missing. "
            "If empty, /missing is appended to the import URL."
        ),
    )
    playout_missing_sync_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Enable periodic missing metadata check"),
        help_text=_("Periodically query playout for files that still need metadata."),
    )
    playout_missing_sync_interval_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name=_("Missing metadata check interval (minutes)"),
        help_text=_("How often Celery Beat should query playout for missing metadata."),
    )
    playout_missing_page_size = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Missing metadata page size"),
        help_text=_("Number of missing playout files requested per page."),
    )
    playout_schedule_url = models.URLField(
        blank=True,
        verbose_name=_("Playout schedule URL"),
        help_text=_(
            "External playout schedule endpoint, e.g. "
            "http://192.168.88.50/api/schedule/import/oktools"
        ),
    )
    anchor_render_url = models.URLField(
        blank=True,
        verbose_name=_("Anchor render URL"),
        help_text=_("External anchor render endpoint, e.g. http://192.168.88.50:8011/api/anchor"),
    )
    anchor_render_api_key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Anchor render API key"),
        help_text=_("API key sent as X-API-Key when the programme preview video is rendered."),
    )
    anchor_render_timeout = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Anchor render timeout (seconds)"),
        help_text=_("HTTP timeout for anchor render requests."),
    )
    anchor_render_wait = models.BooleanField(
        default=True,
        verbose_name=_("Wait for render result"),
        help_text=_("Append wait=1 to the render request and wait for the synchronous response."),
    )
    anchor_output_filename_pattern = models.CharField(
        max_length=255,
        blank=True,
        default="{number}_Programmvorschau_{date:%y%m%d}.mp4",
        verbose_name=_("Anchor output filename pattern"),
        help_text=_("Python format string with {number} and {date}, e.g. {number}_Programmvorschau_{date:%y%m%d}.mp4."),
    )
    anchor_playout_path_prefix = models.CharField(
        max_length=255,
        blank=True,
        default="playout",
        verbose_name=_("Anchor playout path prefix"),
        help_text=_("NAS-relative prefix sent for videos copied to playout."),
    )
    anchor_default_placeholder_video = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Anchor default placeholder video"),
        help_text=_("NAS-relative fallback video path, e.g. playout/placeholder/default.mp4."),
    )
    anchor_placeholder_rules = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Anchor placeholder rules"),
        help_text=_(
            "List of rules. Supported match values: live, title_prefix. "
            "Each rule needs a video path; title_prefix rules also need prefix."
        ),
    )
    webhook_hmac_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Webhook HMAC secret"),
        help_text=_("Shared secret for HMAC-SHA256 verification of incoming webhooks."),
    )

    class Meta:
        verbose_name = _("Planning Configuration")
        verbose_name_plural = _("Planning Configuration")

    def __str__(self):
        """Return string representation."""
        return str(_("Planning Configuration"))

    def save(self, *args, **kwargs):
        """Ensure only one config instance exists."""
        self.pk = 1
        super().save(*args, **kwargs)
        self.sync_playout_missing_periodic_task()

    @classmethod
    def get_config(cls):
        """Get the singleton config instance, creating it if needed."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def is_playout_import_configured(self) -> bool:
        """Return whether outbound playout import can be used."""
        return bool(self.playout_import_url and self.playout_import_api_key)

    def get_playout_missing_url(self) -> str:
        """Return explicit or import-derived playout missing metadata URL."""
        if self.playout_missing_url:
            return self.playout_missing_url
        if self.playout_import_url:
            return f"{self.playout_import_url.rstrip('/')}/missing"
        return ""

    def is_playout_missing_configured(self) -> bool:
        """Return whether missing metadata checks can be used."""
        return bool(self.get_playout_missing_url() and self.playout_import_api_key)

    def is_playout_schedule_configured(self) -> bool:
        """Return whether outbound playout schedule can be used."""
        return bool(self.playout_schedule_url and self.playout_import_api_key)

    def is_anchor_render_configured(self) -> bool:
        """Return whether the anchor render service can be used."""
        return bool(self.anchor_render_url and self.anchor_render_api_key)

    def sync_playout_missing_periodic_task(self) -> None:
        """Create/update the Celery Beat task controlled by this config."""
        try:
            from django_celery_beat.models import IntervalSchedule
            from django_celery_beat.models import PeriodicTask
            import json

            if not self.playout_missing_sync_enabled or not self.is_playout_missing_configured():
                PeriodicTask.objects.filter(task=self.PLAYOUT_MISSING_TASK_NAME).update(enabled=False)
                return

            schedule, created = IntervalSchedule.objects.get_or_create(
                every=max(1, int(self.playout_missing_sync_interval_minutes or 60)),
                period=IntervalSchedule.MINUTES,
            )
            PeriodicTask.objects.update_or_create(
                name="Planning: sync playout files missing metadata",
                defaults={
                    "task": self.PLAYOUT_MISSING_TASK_NAME,
                    "interval": schedule,
                    "enabled": True,
                    "kwargs": json.dumps({"page_size": self.playout_missing_page_size}),
                },
            )
        except Exception:
            # Configuration must remain saveable even if django-celery-beat tables
            # are unavailable during setup or migrations.
            return

    def is_playout_api_configured(self) -> bool:
        """Return whether the incoming playout API is usable."""
        return bool(self.playout_import_api_key)

    def is_webhook_hmac_configured(self) -> bool:
        """Return whether HMAC webhook verification can be used."""
        return bool(self.webhook_hmac_secret)


class AirReport(models.Model):
    """Incoming air report from an external playout system."""

    DIRECTION_INBOUND_MEDIA = "inbound_media"
    DIRECTION_INBOUND_SCHEDULE = "inbound_schedule"
    DIRECTION_OUTBOUND_AIR_REPORT = "outbound_air_report"

    DIRECTION_CHOICES = (
        (DIRECTION_INBOUND_MEDIA, _("Inbound media")),
        (DIRECTION_INBOUND_SCHEDULE, _("Inbound schedule")),
        (DIRECTION_OUTBOUND_AIR_REPORT, _("Outbound air report")),
    )

    external_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("External ID"),
    )
    media_filename = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Media filename"),
    )
    scheduled_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Scheduled start"),
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Started at"),
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Ended at"),
    )
    used_fallback = models.BooleanField(
        default=False,
        verbose_name=_("Used fallback"),
    )
    direction = models.CharField(
        max_length=30,
        choices=DIRECTION_CHOICES,
        default=DIRECTION_OUTBOUND_AIR_REPORT,
        verbose_name=_("Direction"),
    )
    raw_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Raw payload"),
    )
    processed = models.BooleanField(
        default=False,
        verbose_name=_("Processed"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created at"),
    )

    class Meta:
        verbose_name = _("Air report")
        verbose_name_plural = _("Air reports")
        ordering = ("-created_at",)

def __str__(self):
        return f"AirReport {self.pk} ({self.external_id or 'new'})"


class IncomingWebhookLog(models.Model):
    """Log entry for incoming webhooks from external integrations."""

    DIRECTION_INBOUND_MEDIA = AirReport.DIRECTION_INBOUND_MEDIA
    DIRECTION_INBOUND_SCHEDULE = AirReport.DIRECTION_INBOUND_SCHEDULE
    DIRECTION_OUTBOUND_AIR_REPORT = AirReport.DIRECTION_OUTBOUND_AIR_REPORT

    DIRECTION_CHOICES = (
        (DIRECTION_INBOUND_MEDIA, _("Inbound media")),
        (DIRECTION_INBOUND_SCHEDULE, _("Inbound schedule")),
        (DIRECTION_OUTBOUND_AIR_REPORT, _("Outbound air report")),
    )

    connector_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Connector ID"),
    )
    direction = models.CharField(
        max_length=30,
        choices=DIRECTION_CHOICES,
        verbose_name=_("Direction"),
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Payload"),
    )
    processed = models.BooleanField(
        default=False,
        verbose_name=_("Processed"),
        help_text=_("Whether the webhook payload has been processed."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created at"),
    )

    class Meta:
        verbose_name = _("Incoming webhook log")
        verbose_name_plural = _("Incoming webhook logs")
        ordering = ("-created_at",)

    def __str__(self):
        return f"Webhook {self.pk} ({self.direction})"
