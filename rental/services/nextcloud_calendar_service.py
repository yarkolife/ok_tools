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
            # Instead of creating an event for each room rental, create one event for all rooms in the rental request
            return self._sync_rental_request_to_calendar(room_rental.rental_request)

        except Exception as e:
            logger.error(f'Error syncing room rental {room_rental.id} to Nextcloud: {e}', exc_info=True)
            return None

    def _sync_rental_request_to_calendar(self, rental_request) -> Optional[str]:
        """Create or update a single calendar event for all rooms in a rental request.
        
        Args:
            rental_request: RentalRequest model instance
            
        Returns:
            Event URL (href) if successful, None otherwise
        """
        from rental.models import RoomRental
        
        # Get all room rentals for this request
        room_rentals = list(rental_request.room_rentals.all())
        
        if not room_rentals:
            logger.debug(f'No room rentals found for rental request {rental_request.id}')
            return None

        # Check if all room rentals have the same start/end dates
        start_dates = set()
        end_dates = set()
        for rr in room_rentals:
            start_date = rr.get_start_date()
            end_date = rr.get_end_date()
            if start_date:
                start_dates.add(start_date)
            if end_date:
                end_dates.add(end_date)
        
        if len(start_dates) > 1 or len(end_dates) > 1:
            logger.warning(f'Rental request {rental_request.id} has rooms with different dates, using first room dates')
        
        # Use the first room's dates (or request dates if no rooms have custom dates)
        primary_room_rental = room_rentals[0]
        start_date = primary_room_rental.get_start_date()
        end_date = primary_room_rental.get_end_date()

        if not start_date or not end_date:
            logger.error(f'Missing dates for rental request {rental_request.id}')
            return None

        # Get the calendar for the first room (we'll use this for all rooms in the request)
        calendar = self._get_calendar_for_room(primary_room_rental.room)
        
        if not calendar:
            logger.error(f'No calendar found for rooms in rental request {rental_request.id}')
            return None

        # Get user display name (first_name + last_name from Profile)
        user = rental_request.user
        user_display_name = user.email  # Default to email
        try:
            profile = user.profile
            if profile.first_name and profile.last_name:
                user_display_name = f"{profile.first_name} {profile.last_name}"
            elif profile.first_name:
                user_display_name = profile.first_name
            elif profile.last_name:
                user_display_name = profile.last_name
        except AttributeError:
            # Profile doesn't exist, try get_full_name as fallback
            user_display_name = user.get_full_name() or user.email

        # Ensure timezone-aware and convert to configured timezone
        # Get timezone from settings or default to Europe/Berlin
        tz_name = getattr(settings, 'TIME_ZONE', 'Europe/Berlin')
        tz = pytz.timezone(tz_name)
        
        # Ensure dates are timezone-aware
        if timezone.is_naive(start_date):
            # If naive, assume it's in the configured timezone
            start_date = tz.localize(start_date)
        else:
            # Convert to configured timezone
            start_date = start_date.astimezone(tz)
        
        if timezone.is_naive(end_date):
            end_date = tz.localize(end_date)
        else:
            end_date = end_date.astimezone(tz)

        # Create iCal event
        cal = Calendar()
        event = Event()

        # UID - use rental request ID to identify the event (since it covers all rooms in the request)
        uid = f"ok-tools-booking-{rental_request.id}@ok-tools"
        event.add("uid", uid)

        # Summary: User name - All Room names - Project name
        room_names = [rr.room.name for rr in room_rentals]
        rooms_str = ", ".join(room_names)
        summary = f"{user_display_name} – {rooms_str} – {rental_request.project_name}"
        event.add("summary", summary)

        # Location: All room names combined
        event.add("location", rooms_str)

        # Add dates with timezone
        # icalendar will automatically add TZID parameter when datetime is timezone-aware
        event.add("dtstart", start_date)
        event.add("dtend", end_date)

        # Description: Booking details
        # Ensure translations use the correct language (from Django settings)
        from django.utils.translation import get_language, activate
        current_language = get_language()
        # Activate default language if not set (should be 'de' based on settings)
        if not current_language:
            activate(getattr(settings, 'LANGUAGE_CODE', 'de'))
        
        user_name = user_display_name
        description_parts = [
            gettext("OK-Tools Booking #{booking_id}").format(booking_id=rental_request.id),
            gettext("User: {user_name} ({email})").format(user_name=user_name, email=user.email),
            gettext("Project: {project}").format(project=rental_request.project_name),
            gettext("Purpose: {purpose}").format(purpose=rental_request.purpose),
        ]
        
        # Add information about all rooms
        room_details = []
        for rr in room_rentals:
            room_details.append(f"- {rr.room.name} ({rr.people_count} people)")
        if room_details:
            description_parts.append(gettext("Rooms and People:") + "\n" + "\n".join(room_details))
        
        if rental_request.notes:
            description_parts.append(f"\n{gettext('Request Notes:')}\n{rental_request.notes}")

        event.add("description", "\n".join(description_parts))

        # Add to calendar
        cal.add_component(event)

        # Convert to iCal string
        ical_text = cal.to_ical().decode("utf-8")

        # Find the main event href for this rental request (using the first room rental that has an event)
        main_event_href = None
        for rr in room_rentals:
            if rr.nextcloud_event_href:
                main_event_href = rr.nextcloud_event_href
                break

        # Create or update event
        if main_event_href:
            # Update existing event
            try:
                vevent = calendar.event_by_url(main_event_href)
                vevent.data = ical_text
                vevent.save()
                logger.info(
                    f'Updated Nextcloud event for rental request {rental_request.id} '
                    f'at {main_event_href}'
                )
                # Update all room rentals in this request to use the same href
                for rr in room_rentals:
                    if rr.nextcloud_event_href != main_event_href:
                        rr.nextcloud_event_href = main_event_href
                        RoomRental.objects.filter(pk=rr.pk).update(nextcloud_event_href=main_event_href)
                return main_event_href
            except self.caldav.error.NotFoundError:
                # Event was deleted, create new one
                logger.warning(
                    f'Event {main_event_href} not found, creating new event'
                )
                main_event_href = None
            except Exception as e:
                logger.error(f'Error updating Nextcloud event: {e}')
                return None
        
        # Create new event (either first time or after NotFoundError)
        if not main_event_href:
            try:
                # Use save_event with iCal string (caldav 2.2.0+)
                # save_event can accept iCal string or parameters
                try:
                    # Try new API first (caldav 2.2.0+)
                    vevent = calendar.save_event(ical_text)
                except (TypeError, AttributeError) as api_error:
                    # Fallback to old API (caldav < 2.2.0)
                    vevent = calendar.add_event(ical_text)
                
                event_href = vevent.url
                logger.info(
                    f'Created Nextcloud event for rental request {rental_request.id} at {event_href}'
                )
                
                # Update all room rentals in this request to use the same href
                for rr in room_rentals:
                    rr.nextcloud_event_href = event_href
                    RoomRental.objects.filter(pk=rr.pk).update(nextcloud_event_href=event_href)
                return event_href
            except Exception as e:
                logger.error(f'Error creating Nextcloud event: {e}')
                return None

    def delete_room_rental_event(self, room_rental) -> bool:
        """Delete a room rental event from Nextcloud Calendar.
        
        Args:
            room_rental: RoomRental model instance with nextcloud_event_href
            
        Returns:
            True if successful, False otherwise
        """
        # Instead of deleting individual events, we need to delete the shared event for the entire rental request
        return self._delete_rental_request_event(room_rental.rental_request)

    def _delete_rental_request_event(self, rental_request) -> bool:
        """Delete the shared calendar event for all rooms in a rental request.
        
        Args:
            rental_request: RentalRequest model instance
            
        Returns:
            True if successful, False otherwise
        """
        from rental.models import RoomRental
        
        # Get all room rentals for this request
        room_rentals = list(rental_request.room_rentals.all())
        
        if not room_rentals:
            logger.debug(f'No room rentals found for rental request {rental_request.id}')
            return True

        # Find the main event href for this rental request (using the first room rental that has an event)
        main_event_href = None
        for rr in room_rentals:
            if rr.nextcloud_event_href:
                main_event_href = rr.nextcloud_event_href
                break

        if not main_event_href:
            # No event to delete
            return True

        try:
            # Use the calendar of the first room rental for deletion
            calendar = self._get_calendar_for_room(room_rentals[0].room)
            
            if not calendar:
                logger.warning(f'No calendar found for rooms in rental request {rental_request.id}, cannot delete event')
                return False

            try:
                vevent = calendar.event_by_url(main_event_href)
                vevent.delete()
                logger.info(
                    f'Deleted Nextcloud event for rental request {rental_request.id} '
                    f'at {main_event_href}'
                )
                
                # Clear the event href for all room rentals in this request
                for rr in room_rentals:
                    if rr.nextcloud_event_href == main_event_href:
                        RoomRental.objects.filter(pk=rr.pk).update(nextcloud_event_href=None)
                return True
            except self.caldav.error.NotFoundError:
                # Event already deleted, that's fine
                logger.info(f'Event {main_event_href} already deleted')
                
                # Clear the event href for all room rentals in this request
                for rr in room_rentals:
                    if rr.nextcloud_event_href == main_event_href:
                        RoomRental.objects.filter(pk=rr.pk).update(nextcloud_event_href=None)
                return True
            except Exception as e:
                logger.error(f'Error deleting Nextcloud event: {e}')
                return False

        except Exception as e:
            logger.error(f'Error deleting rental request {rental_request.id} from Nextcloud: {e}', exc_info=True)
            return False


