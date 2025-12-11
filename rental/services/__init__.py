"""
Services module for the rental application.

This module contains service classes that encapsulate business logic
for rental operations, separating it from views and models.
"""

# Apply icalendar compatibility patches before any imports that might use caldav
# This fixes compatibility issues between icalendar 6.x and dependent libraries

# Patch 1: InvalidCalendar for recurring-ical-events
try:
    import icalendar
    if not hasattr(icalendar, 'InvalidCalendar'):
        from icalendar.error import InvalidCalendar
        icalendar.InvalidCalendar = InvalidCalendar
except Exception:
    pass

# Patch 2: Component for icalendar-searcher (used by caldav)
try:
    import icalendar
    if not hasattr(icalendar, 'Component'):
        try:
            from icalendar.cal import Component
            icalendar.Component = Component
        except ImportError:
            try:
                from icalendar import Event
                # Component is Event in icalendar 6.x
                icalendar.Component = Event
            except ImportError:
                pass
except Exception:
    pass

from .rental_service import RentalService

# Import NextcloudCalendarService only if needed (it requires caldav library)
try:
    from .nextcloud_calendar_service import NextcloudCalendarService
    __all__ = [
        'RentalService',
        'NextcloudCalendarService',
    ]
except ImportError:
    __all__ = [
        'RentalService',
    ]