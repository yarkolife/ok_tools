"""Django app configuration for posts (Beiträge)."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BeitraegeConfig(AppConfig):
    """Posts with photos for Instagram, Facebook and the website."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'beitraege'
    verbose_name = _('Posts')
