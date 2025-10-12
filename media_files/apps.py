"""Media files app configuration."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MediaFilesConfig(AppConfig):
    """Configuration for media files application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'media_files'
    verbose_name = _('Media Files')

    def ready(self):
        """Import signals when app is ready."""
        import media_files.signals  # noqa

