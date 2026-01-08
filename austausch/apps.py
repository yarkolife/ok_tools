"""Django app configuration for austausch module."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AustauschConfig(AppConfig):
    """Configuration for austausch app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'austausch'
    verbose_name = _('Austausch')

