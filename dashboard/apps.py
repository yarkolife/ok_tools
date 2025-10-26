from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'
    verbose_name = _('Dashboard')

    def ready(self):
        import dashboard.signals
        # Import cache invalidation signals to register them
        import dashboard.cache_invalidation
