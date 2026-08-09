from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _
import logging


logger = logging.getLogger('django')


def sync_event_types(sender, **kwargs):
    """Mirror the code registry into the configuration table after migrate."""
    from notifications.config import sync_event_type_configs

    try:
        result = sync_event_type_configs()
    except Exception:
        logger.warning('Could not sync notification event types', exc_info=True)
        return
    if result.get('created'):
        logger.info('Added %s notification event types', result['created'])


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = _('Notifications')

    def ready(self):
        # Declarations populate the event registry; checks attach scan
        # callables to it. Both must be imported before any emit() call.
        import notifications.checks  # noqa: F401
        import notifications.event_types  # noqa: F401
        import notifications.signals  # noqa: F401

        post_migrate.connect(sync_event_types, sender=self)
