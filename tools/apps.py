"""Django app configuration for tools module."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ToolsConfig(AppConfig):
    """Configuration for tools app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools'
    verbose_name = _('Tools')
