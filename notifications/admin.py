from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from notifications.models import ManualReminder
from notifications.models import NotificationConfig
from notifications.models import NotificationEvent
from notifications.models import NotificationSuppression
from notifications.models import Subscription


@admin.register(NotificationConfig)
class NotificationConfigAdmin(admin.ModelAdmin):
    """Singleton settings of the notification system."""

    list_display = ['__str__', 'enabled', 'digest_time', 'retention_days']

    def has_add_permission(self, request):
        """Only one config instance allowed."""
        return not NotificationConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of config."""
        return False

    def has_view_permission(self, request, obj=None):
        """Configuration is a superuser matter."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Configuration is a superuser matter."""
        return request.user.is_superuser


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    """Read-only view of the raw event stream, for troubleshooting."""

    list_display = ['occurred_at', 'module', 'event_type', 'category',
                    'dedup_key']
    list_filter = ['module', 'category', 'event_type']
    search_fields = ['dedup_key', 'event_type']
    date_hierarchy = 'occurred_at'
    readonly_fields = ['module', 'event_type', 'category', 'occurred_at',
                       'content_type', 'object_id', 'payload', 'dedup_key',
                       'created_at']

    def has_add_permission(self, request):
        """Events are produced by signals and scans only."""
        return False

    def has_view_permission(self, request, obj=None):
        """The raw stream bypasses subscriptions, so restrict it."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Events are immutable."""
        return False


@admin.register(NotificationSuppression)
class NotificationSuppressionAdmin(admin.ModelAdmin):
    """Permanently silenced objects. Deleting a row lets them reappear."""

    list_display = ['label', 'event_type', 'object_id', 'created_by',
                    'created_at']
    list_filter = ['event_type']
    search_fields = ['event_type', 'object_id', 'reason']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        """Suppressions are created from the notification page."""
        return False

    def has_view_permission(self, request, obj=None):
        """Silencing affects everybody, so keep the list for superusers."""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """A suppression is either there or removed, never edited."""
        return False

    def has_module_permission(self, request):
        """Hide the model from the index for non-superusers."""
        return request.user.is_superuser


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Subscriptions are normally managed on the notifications page."""

    list_display = ['user', 'module', 'event_type']
    list_filter = ['module']
    search_fields = ['user__email', 'module', 'event_type']
    autocomplete_fields = ['user']

    def has_view_permission(self, request, obj=None):
        """Other people's subscriptions are a superuser matter."""
        return request.user.is_superuser

    def has_module_permission(self, request):
        """Hide the model from the index for non-superusers."""
        return request.user.is_superuser


@admin.register(ManualReminder)
class ManualReminderAdmin(admin.ModelAdmin):
    """Reminders staff write themselves, for work the data cannot show."""

    list_display = ('title', 'repeat', 'active', 'created_by')
    list_filter = ('active', 'frequency')
    search_fields = ('title', 'message')
    readonly_fields = ('created_by', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'message', 'url', 'active'),
        }),
        (_('When'), {
            'fields': ('frequency', 'run_date', 'weekday', 'day_of_month'),
            'description': _(
                'Fill in only the field belonging to the chosen repeat rule. '
                'Reminders reach everybody subscribed to the "Reminders" '
                'channel on the day they are due.'),
        }),
        (_('Meta'), {
            'fields': ('created_by', 'created_at'),
        }),
    )

    def repeat(self, obj):
        """Return the repeat rule in words."""
        return f'{obj.get_frequency_display()} — {obj.schedule_label()}'
    repeat.short_description = _('Repeat')

    def save_model(self, request, obj, form, change):
        """Record who wrote the reminder."""
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

