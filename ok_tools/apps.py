from django.apps import AppConfig
from django.core.signals import setting_changed
from django.dispatch import receiver


class OkToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ok_tools'
    
    def ready(self):
        """Called when Django starts."""
        # Register custom admin after all apps are loaded
        self._register_custom_admin()
    
    def _register_custom_admin(self):
        """Register custom admin configurations."""
        try:
            from .admin_imports import register_custom_admin
            register_custom_admin()
        except Exception as e:
            # Log error but don't crash the app
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to register custom admin: {e}")
