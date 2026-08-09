from datetime import time
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from notifications import registry
import json
import logging


logger = logging.getLogger('django')

MAX_STRING_LENGTH = 255


class NotificationEvent(models.Model):
    """A stored fact: something happened that somebody may need to know."""

    module = models.CharField(
        _('Module'),
        max_length=50,
        db_index=True,
    )
    event_type = models.CharField(
        _('Event type'),
        max_length=100,
        db_index=True,
        help_text=_('Code of the event type declared in the registry.'),
    )
    category = models.CharField(
        _('Category'),
        max_length=20,
        choices=registry.CATEGORY_CHOICES,
        default=registry.CATEGORY_INFO,
    )
    occurred_at = models.DateTimeField(
        _('Occurred at'),
        default=timezone.now,
        db_index=True,
    )
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_('Content type'),
    )
    object_id = models.PositiveIntegerField(
        _('Object id'),
        null=True,
        blank=True,
    )
    target = GenericForeignKey('content_type', 'object_id')
    payload = models.JSONField(
        _('Payload'),
        default=dict,
        blank=True,
        help_text=_('Data used to render the message in the reader language.'),
    )
    dedup_key = models.CharField(
        _('Deduplication key'),
        max_length=MAX_STRING_LENGTH,
        unique=True,
        help_text=_('Prevents duplicates when a scan or a signal runs twice.'),
    )
    created_at = models.DateTimeField(
        _('Created at'),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _('Notification event')
        verbose_name_plural = _('Notification events')
        ordering = ['-occurred_at', '-id']
        indexes = [
            models.Index(fields=['module', '-occurred_at'], name='notif_module_occurred_idx'),
            models.Index(fields=['event_type', '-occurred_at'], name='notif_type_occurred_idx'),
        ]

    def __str__(self):
        """Return the event code with its timestamp."""
        return f'{self.event_type} @ {self.occurred_at:%Y-%m-%d %H:%M}'

    @property
    def event_type_spec(self):
        """Return the registry declaration for this event, or None."""
        return registry.get(self.event_type)

    @property
    def label(self):
        """Return the translated title of the event type."""
        spec = self.event_type_spec
        return spec.label if spec else self.event_type

    @property
    def message(self) -> str:
        """Return the rendered line of text in the current language."""
        return registry.render_message(self.event_type, self.payload)

    @property
    def url(self) -> str:
        """Return the admin link stored in the payload, if any."""
        return (self.payload or {}).get('url', '')


class UserNotification(models.Model):
    """Per-user copy of an event that requires an individual action."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('User'),
    )
    event = models.ForeignKey(
        NotificationEvent,
        on_delete=models.CASCADE,
        related_name='user_notifications',
        verbose_name=_('Event'),
    )
    read_at = models.DateTimeField(
        _('Read at'),
        null=True,
        blank=True,
    )
    dismissed_at = models.DateTimeField(
        _('Dismissed at'),
        null=True,
        blank=True,
    )
    snoozed_until = models.DateTimeField(
        _('Snoozed until'),
        null=True,
        blank=True,
        help_text=_('Hidden from the list until this moment.'),
    )

    class Meta:
        verbose_name = _('User notification')
        verbose_name_plural = _('User notifications')
        unique_together = ('user', 'event')
        ordering = ['-event__occurred_at']
        indexes = [
            models.Index(fields=['user', 'dismissed_at'], name='notif_user_dismissed_idx'),
        ]

    def __str__(self):
        """Return user and event codes."""
        return f'{self.user} / {self.event.event_type}'

    @property
    def is_snoozed(self) -> bool:
        """Return whether this item is currently postponed."""
        return bool(self.snoozed_until and self.snoozed_until > timezone.now())


class Subscription(models.Model):
    """A staff member's interest in a module or in a single event type."""

    ALL_TYPES = '*'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_subscriptions',
        verbose_name=_('User'),
    )
    module = models.CharField(
        _('Module'),
        max_length=50,
    )
    event_type = models.CharField(
        _('Event type'),
        max_length=100,
        default=ALL_TYPES,
        help_text=_('Use * to subscribe to the whole module.'),
    )

    class Meta:
        verbose_name = _('Notification subscription')
        verbose_name_plural = _('Notification subscriptions')
        unique_together = ('user', 'module', 'event_type')
        ordering = ['module', 'event_type']

    def __str__(self):
        """Return the subscription in module/type notation."""
        return f'{self.user}: {self.module}/{self.event_type}'


class NotificationSuppression(models.Model):
    """A permanent "never report this again" mark on one object.

    Dismissing an action item is personal and only covers that one event.
    Some findings are simply never going to be acted on -- an old license
    that will never be confirmed -- and a periodic check would raise them
    again in the next period, for everybody. A suppression stops the event
    from being created at all, for the whole channel.
    """

    event_type = models.CharField(
        _('Event type'),
        max_length=100,
        db_index=True,
    )
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_('Content type'),
    )
    object_id = models.PositiveIntegerField(
        _('Object id'),
        null=True,
        blank=True,
    )
    target = GenericForeignKey('content_type', 'object_id')
    reason = models.CharField(
        _('Reason'),
        max_length=MAX_STRING_LENGTH,
        blank=True,
        default='',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notification_suppressions',
        verbose_name=_('Created by'),
    )
    created_at = models.DateTimeField(
        _('Created at'),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _('Notification suppression')
        verbose_name_plural = _('Notification suppressions')
        unique_together = ('event_type', 'content_type', 'object_id')
        ordering = ['-created_at']

    def __str__(self):
        """Return the suppressed event type and object."""
        return f'{self.event_type} #{self.object_id}'

    @property
    def label(self):
        """Return the translated title of the suppressed event type."""
        spec = registry.get(self.event_type)
        return spec.label if spec else self.event_type


class NotificationEventTypeConfig(models.Model):
    """Channel level switch and parameters for one event type.

    Rows are synchronised from the code registry; they are never created by
    hand. Disabling a row stops the corresponding check from running at all.
    """

    code = models.CharField(
        _('Event type'),
        max_length=100,
        unique=True,
    )
    enabled = models.BooleanField(
        _('Enabled'),
        default=True,
        help_text=_('When off, the check is not executed and nobody sees it.'),
    )
    params = models.JSONField(
        _('Parameters'),
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = _('Notification event type')
        verbose_name_plural = _('Notification event types')
        ordering = ['code']

    def __str__(self):
        """Return the event type code."""
        return self.code

    @property
    def spec(self):
        """Return the registry declaration for this row, or None."""
        return registry.get(self.code)


class NotificationConfig(models.Model):
    """Singleton settings of the notification system."""

    DIGEST_TASK_NAME = 'notifications.tasks.build_daily_digest'

    enabled = models.BooleanField(
        _('Enabled'),
        default=True,
        help_text=_('Master switch for the whole notification system.'),
    )
    digest_time = models.TimeField(
        _('Daily summary time'),
        default=time(10, 0),
        help_text=_('When the day marker is built. Nothing is sent by email.'),
    )
    retention_days = models.PositiveIntegerField(
        _('Retention (days)'),
        default=90,
        help_text=_('Events older than this are deleted by the cleanup task.'),
    )

    class Meta:
        verbose_name = _('Notification Configuration')
        verbose_name_plural = _('Notification Configuration')

    def __str__(self):
        """Return string representation."""
        return str(_('Notification Configuration'))

    def save(self, *args, **kwargs):
        """Ensure only one config instance exists and keep Beat in sync."""
        self.pk = 1
        super().save(*args, **kwargs)
        self.sync_digest_periodic_task()

    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist."""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def sync_digest_periodic_task(self) -> None:
        """Create/update the Celery Beat task controlled by these settings."""
        try:
            from django_celery_beat.models import CrontabSchedule
            from django_celery_beat.models import PeriodicTask

            if not self.enabled:
                PeriodicTask.objects.filter(
                    task=self.DIGEST_TASK_NAME).update(enabled=False)
                return

            digest_time = self.digest_time or time(10, 0)
            schedule, _created = CrontabSchedule.objects.get_or_create(
                minute=str(digest_time.minute),
                hour=str(digest_time.hour),
                day_of_month='*',
                month_of_year='*',
                day_of_week='*',
                timezone=getattr(settings, 'TIME_ZONE', 'UTC'),
            )
            PeriodicTask.objects.update_or_create(
                name=str(_('Notifications: build daily summary')),
                defaults={
                    'task': self.DIGEST_TASK_NAME,
                    'crontab': schedule,
                    'enabled': True,
                    'kwargs': json.dumps({}),
                },
            )
        except Exception:
            # Configuration must remain saveable during setup and migrations.
            logger.warning(
                'Could not sync the notification digest schedule',
                exc_info=True,
            )


class UserNotificationState(models.Model):
    """Read marker: everything newer than last_seen_at counts as new."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_state',
        verbose_name=_('User'),
    )
    last_seen_at = models.DateTimeField(
        _('Last seen at'),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _('Notification read state')
        verbose_name_plural = _('Notification read states')

    def __str__(self):
        """Return the owner of this marker."""
        return str(self.user)
