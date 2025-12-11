from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RentalConfig(AppConfig):
    """Django app configuration for the rental app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "rental"
    verbose_name = _("Rental")

    def ready(self):
        """Register signal handlers on app ready."""
        # Apply icalendar compatibility patches before importing signals
        # This fixes compatibility issues between icalendar 6.x and dependent libraries
        
        # Patch 1: InvalidCalendar for recurring-ical-events
        try:
            import icalendar
            if not hasattr(icalendar, 'InvalidCalendar'):
                from icalendar.error import InvalidCalendar
                icalendar.InvalidCalendar = InvalidCalendar
        except Exception:
            pass  # If patch fails, continue anyway
        
        # Patch 2: Component for icalendar-searcher (used by caldav)
        try:
            import icalendar
            if not hasattr(icalendar, 'Component'):
                try:
                    from icalendar.cal import Component
                    icalendar.Component = Component
                except ImportError:
                    # Try alternative import path
                    try:
                        from icalendar import Event, Calendar
                        # Component is Event in icalendar 6.x
                        icalendar.Component = Event
                    except ImportError:
                        pass
        except Exception:
            pass  # If patch fails, continue anyway
        
        from . import signals  # noqa: F401
