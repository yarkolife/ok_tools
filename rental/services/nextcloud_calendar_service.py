"""Service for syncing room rentals to Nextcloud Calendar via CalDAV."""

import logging
from typing import Optional
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _, gettext
from django.utils import timezone
from icalendar import Calendar, Event
from datetime import datetime
import pytz

logger = logging.getLogger('django')


class NextcloudCalendarService:
    """Service class for Nextcloud Calendar CalDAV operations."""

    def __init__(self):
        """Initialize Nextcloud Calendar service."""
        if not getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False):
            raise ImproperlyConfigured(
                _('Nextcloud Calendar integration is disabled. Set NEXTCLOUD_CALENDAR_ENABLED=true to enable.')
            )

        # Fix for icalendar 6.x compatibility with dependent libraries
        # Apply patches BEFORE importing caldav to ensure they're available when caldav imports dependencies
        try:
            import icalendar
            
            # Patch 1: InvalidCalendar for recurring-ical-events
            if not hasattr(icalendar, 'InvalidCalendar'):
                try:
                    from icalendar.error import InvalidCalendar
                    icalendar.InvalidCalendar = InvalidCalendar
                except ImportError:
                    pass
            
            # Patch 2: Component for icalendar-searcher (used by caldav)
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
            pass  # If patch fails, continue anyway

        try:
            import caldav
            self.caldav = caldav
        except ImportError:
            raise ImproperlyConfigured(
                _('caldav library is required for Nextcloud Calendar integration. Install it with: pip install caldav')
            )
        except AttributeError as e:
            # Handle the InvalidCalendar AttributeError specifically
            if 'InvalidCalendar' in str(e):
                try:
                    import icalendar
                    from icalendar.error import InvalidCalendar
                    icalendar.InvalidCalendar = InvalidCalendar
                    # Retry import after patch
                    import caldav
                    self.caldav = caldav
                except Exception as retry_error:
                    raise ImproperlyConfigured(
                        _('Failed to import caldav library due to icalendar compatibility issue: {error}').format(error=str(retry_error))
                    )
            else:
                raise

        self.base_url = getattr(settings, 'NEXTCLOUD_CALDAV_BASE_URL', '').rstrip('/')
        self.username = getattr(settings, 'NEXTCLOUD_CALENDAR_USERNAME', '')
        self.password = getattr(settings, 'NEXTCLOUD_CALENDAR_PASSWORD', '')
        self.default_calendar_name = getattr(settings, 'NEXTCLOUD_DEFAULT_CALENDAR_NAME', None)
        self.room_calendars = getattr(settings, 'NEXTCLOUD_ROOM_CALENDARS', {})

        if not self.base_url:
            raise ImproperlyConfigured(
                _('NEXTCLOUD_CALDAV_BASE_URL is required for Calendar integration')
            )
        if not self.username or not self.password:
            raise ImproperlyConfigured(
                _('NEXTCLOUD_CALENDAR_USERNAME and NEXTCLOUD_CALENDAR_PASSWORD are required')
            )

        # Initialize CalDAV client
        try:
            self.client = self.caldav.DAVClient(
                url=self.base_url,
                username=self.username,
                password=self.password
            )
            self.principal = self.client.principal()
        except Exception as e:
            logger.error(f'Failed to initialize CalDAV client: {e}')
            raise ImproperlyConfigured(
                _('Failed to connect to Nextcloud CalDAV server: {error}').format(error=str(e))
            )

    def _get_calendar_for_room(self, room) -> Optional[object]:
        """Get the calendar object for a specific room.
        
        Args:
            room: Room model instance
            
        Returns:
            Calendar object or None if not found
        """
        try:
            calendars = self.principal.calendars()
            
            # Priority 1: Use default calendar if configured
            if self.default_calendar_name:
                for cal in calendars:
                    if cal.name == self.default_calendar_name:
                        return cal
                logger.warning(
                    f'Default calendar "{self.default_calendar_name}" not found. '
                    f'Available calendars: {[c.name for c in calendars]}'
                )
                # Fallback to first calendar if default not found
                if calendars:
                    return calendars[0]
                return None
            
            # Priority 2: Try to get calendar name from room mapping
            room_slug = getattr(room, 'slug', None) or str(room.id)
            calendar_name = self.room_calendars.get(room_slug) or self.room_calendars.get(room.name)
            
            if calendar_name:
                for cal in calendars:
                    if cal.name == calendar_name:
                        return cal
                logger.warning(
                    f'Calendar "{calendar_name}" from mapping not found for room "{room.name}". '
                    f'Available calendars: {[c.name for c in calendars]}'
                )
            
            # Priority 3: Try to find calendar by room name
            if not calendar_name:
                calendar_name = room.name
                for cal in calendars:
                    if cal.name == calendar_name:
                        return cal
            
            # Fallback: use first available calendar
            if calendars:
                logger.info(
                    f'Using first available calendar "{calendars[0].name}" for room "{room.name}"'
                )
                return calendars[0]
            
            return None
            
        except Exception as e:
            logger.error(f'Error getting calendar for room {room.name}: {e}')
            return None

    def sync_room_rental_to_calendar(self, room_rental) -> Optional[str]:
        """Create or update a room rental event in Nextcloud Calendar.
        
        Args:
            room_rental: RoomRental model instance
            
        Returns:
            Event URL (href) if successful, None otherwise
        """
        from rental.models import RoomRental
        
        if not isinstance(room_rental, RoomRental):
            logger.error(f'Invalid room_rental type: {type(room_rental)}')
            return None

        # Only sync if rental request is confirmed (reserved or issued)
        status = room_rental.rental_request.status if hasattr(room_rental, 'rental_request') else None
        
        if status not in ['reserved', 'issued']:
            logger.debug(
                f'Skipping sync for room rental {room_rental.id}: '
                f'status is {status}'
            )
            return None

        try:
            return self._sync_rental_request_to_calendar(room_rental.rental_request)

        except Exception as e:
            logger.error(f'Error syncing room rental {room_rental.id} to Nextcloud: {e}', exc_info=True)
            return None

    def _sync_rental_request_to_calendar(self, rental_request) -> Optional[str]:
        """Create or update separate calendar events for each room in a rental request.

        Each room rental gets its own event with its own dates and calendar.
        This supports per-room date variations within a single rental request.

        Args:
            rental_request: RentalRequest model instance

        Returns:
            Event URL (href) of the first successfully synced room, None if all failed
        """
        from rental.models import RoomRental

        room_rentals = list(rental_request.room_rentals.all())

        if not room_rentals:
            logger.debug(f'No room rentals found for rental request {rental_request.id}')
            return None

        first_href = None

        for rr in room_rentals:
            href = self._sync_single_room_event_to_calendar(rr)
            if href and not first_href:
                first_href = href

        return first_href

    def _sync_single_room_event_to_calendar(self, room_rental) -> Optional[str]:
        """Create or update a single room rental event in Nextcloud Calendar.

        Args:
            room_rental: RoomRental model instance

        Returns:
            Event URL (href) if successful, None otherwise
        """
        from rental.models import RoomRental

        start_date = room_rental.get_start_date()
        end_date = room_rental.get_end_date()

        if not start_date or not end_date:
            logger.error(f'Missing dates for room rental {room_rental.id}')
            return None

        calendar = self._get_calendar_for_room(room_rental.room)
        if not calendar:
            logger.error(f'No calendar found for room {room_rental.room.name}')
            return None

        rental_request = room_rental.rental_request
        user = rental_request.user

        user_display_name = user.email
        try:
            profile = user.profile
            if profile.first_name and profile.last_name:
                user_display_name = f"{profile.first_name} {profile.last_name}"
            elif profile.first_name:
                user_display_name = profile.first_name
            elif profile.last_name:
                user_display_name = profile.last_name
        except AttributeError:
            user_display_name = user.get_full_name() or user.email

        tz_name = getattr(settings, 'TIME_ZONE', 'Europe/Berlin')
        tz = pytz.timezone(tz_name)

        if timezone.is_naive(start_date):
            start_date = tz.localize(start_date)
        else:
            start_date = start_date.astimezone(tz)

        if timezone.is_naive(end_date):
            end_date = tz.localize(end_date)
        else:
            end_date = end_date.astimezone(tz)

        cal = Calendar()
        event = Event()
        uid = f"ok-tools-room-booking-{room_rental.id}@ok-tools"
        event.add("uid", uid)
        summary = f"{user_display_name} – {room_rental.room.name} – {rental_request.project_name}"
        event.add("summary", summary)
        event.add("location", room_rental.room.name)
        event.add("dtstart", start_date)
        event.add("dtend", end_date)

        # Description
        from django.utils.translation import get_language, activate
        current_language = get_language()
        if not current_language:
            activate(getattr(settings, 'LANGUAGE_CODE', 'de'))

        description_parts = [
            gettext("OK-Tools Booking #{booking_id}").format(booking_id=rental_request.id),
            gettext("User: {user_name} ({email})").format(
                user_name=user_display_name, email=user.email,
            ),
            gettext("Project: {project}").format(project=rental_request.project_name),
            gettext("Purpose: {purpose}").format(purpose=rental_request.purpose),
            gettext("Room: {room} ({people_count} people)").format(
                room=room_rental.room.name,
                people_count=room_rental.people_count,
            ),
        ]

        if rental_request.notes:
            description_parts.append(
                f"\n{gettext('Request Notes:')}\n{rental_request.notes}"
            )

        event.add("description", "\n".join(description_parts))

        cal.add_component(event)
        ical_text = cal.to_ical().decode("utf-8")

        existing_href = room_rental.nextcloud_event_href

        if existing_href:
            try:
                vevent = calendar.event_by_url(existing_href)
                vevent.data = ical_text
                vevent.save()
                logger.info(
                    f'Updated Nextcloud event for room rental {room_rental.id} '
                    f'(room: {room_rental.room.name}) at {existing_href}'
                )
                return existing_href
            except self.caldav.error.NotFoundError:
                logger.warning(
                    f'Event {existing_href} not found for room rental '
                    f'{room_rental.id}, creating new event'
                )
                existing_href = None
            except Exception as e:
                logger.error(
                    f'Error updating Nextcloud event for room rental '
                    f'{room_rental.id}: {e}'
                )
                return None

        # Create new event
        try:
            try:
                vevent = calendar.save_event(ical_text)
            except (TypeError, AttributeError):
                vevent = calendar.add_event(ical_text)

            event_href = vevent.url
            logger.info(
                f'Created Nextcloud event for room rental {room_rental.id} '
                f'(room: {room_rental.room.name}) at {event_href}'
            )

            RoomRental.objects.filter(pk=room_rental.pk).update(
                nextcloud_event_href=event_href,
            )
            return event_href
        except Exception as e:
            logger.error(
                f'Error creating Nextcloud event for room rental '
                f'{room_rental.id}: {e}'
            )
            return None

    def delete_room_rental_event(self, room_rental) -> bool:
        """Delete a room rental event from Nextcloud Calendar.
        
        Args:
            room_rental: RoomRental model instance with nextcloud_event_href
            
        Returns:
            True if successful, False otherwise
        """
        return self._delete_rental_request_event(room_rental.rental_request)

    def _delete_rental_request_event(self, rental_request) -> bool:
        """Delete all calendar events for rooms in a rental request.

        Each room rental may have its own event — all are deleted individually.

        Args:
            rental_request: RentalRequest model instance

        Returns:
            True if all deletions succeeded, False if any failed
        """
        from rental.models import RoomRental

        room_rentals = list(rental_request.room_rentals.all())

        if not room_rentals:
            logger.debug(f'No room rentals found for rental request {rental_request.id}')
            return True

        all_success = True

        for rr in room_rentals:
            if not rr.nextcloud_event_href:
                continue

            calendar = self._get_calendar_for_room(rr.room)
            if not calendar:
                logger.warning(
                    f'No calendar found for room {rr.room.name}, '
                    f'skipping event deletion for room rental {rr.id}'
                )
                continue

            try:
                vevent = calendar.event_by_url(rr.nextcloud_event_href)
                vevent.delete()
                logger.info(
                    f'Deleted Nextcloud event for room rental {rr.id} '
                    f'(room: {rr.room.name}) at {rr.nextcloud_event_href}'
                )
                RoomRental.objects.filter(pk=rr.pk).update(nextcloud_event_href=None)
            except self.caldav.error.NotFoundError:
                logger.info(
                    f'Event {rr.nextcloud_event_href} already deleted '
                    f'(room rental {rr.id})'
                )
                RoomRental.objects.filter(pk=rr.pk).update(nextcloud_event_href=None)
            except Exception as e:
                logger.error(
                    f'Error deleting Nextcloud event {rr.nextcloud_event_href} '
                    f'for room rental {rr.id}: {e}'
                )
                all_success = False

        return all_success


