"""In-app manual: chapters shipped with the code, notes kept by the staff."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class HandbuchConfig(AppConfig):
    """Configuration of the manual."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'handbuch'
    verbose_name = _('Manual')
