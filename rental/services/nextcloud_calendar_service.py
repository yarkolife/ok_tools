"""Service for syncing room rentals to Nextcloud Calendar via CalDAV."""

import logging
from typing import Optional
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
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
        # #region agent log
        import json
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rental/services/nextcloud_calendar_service.py:62","message":"_get_calendar_for_room called","data":{"room_name":room.name if hasattr(room, 'name') else None,"default_calendar_name":self.default_calendar_name},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        try:
            calendars = self.principal.calendars()
            # #region agent log
            try:
                with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rental/services/nextcloud_calendar_service.py:72","message":"Available calendars","data":{"count":len(calendars),"names":[c.name for c in calendars]},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            # Priority 1: Use default calendar if configured
            if self.default_calendar_name:
                for cal in calendars:
                    if cal.name == self.default_calendar_name:
                        # #region agent log
                        try:
                            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rental/services/nextcloud_calendar_service.py:77","message":"Found default calendar","data":{"calendar_name":cal.name},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                        except: pass
                        # #endregion
                        return cal
                logger.warning(
                    f'Default calendar "{self.default_calendar_name}" not found. '
                    f'Available calendars: {[c.name for c in calendars]}'
                )
                # #region agent log
                try:
                    with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rental/services/nextcloud_calendar_service.py:85","message":"Default calendar not found, using fallback","data":{"default_calendar_name":self.default_calendar_name,"fallback_calendar":calendars[0].name if calendars else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
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
        # #region agent log
        import json
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rental/services/nextcloud_calendar_service.py:121","message":"sync_room_rental_to_calendar called","data":{"room_rental_id":room_rental.id if hasattr(room_rental, 'id') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        from rental.models import RoomRental
        
        if not isinstance(room_rental, RoomRental):
            logger.error(f'Invalid room_rental type: {type(room_rental)}')
            return None

        # Only sync if rental request is confirmed (reserved or issued)
        status = room_rental.rental_request.status if hasattr(room_rental, 'rental_request') else None
        # #region agent log
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"rental/services/nextcloud_calendar_service.py:137","message":"Status check in sync_room_rental_to_calendar","data":{"status":status,"should_sync":status in ['reserved', 'issued']},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        if status not in ['reserved', 'issued']:
            logger.debug(
                f'Skipping sync for room rental {room_rental.id}: '
                f'status is {status}'
            )
            return None

        try:
            calendar = self._get_calendar_for_room(room_rental.room)
            # #region agent log
            try:
                with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rental/services/nextcloud_calendar_service.py:145","message":"Calendar lookup result","data":{"calendar_found":calendar is not None,"calendar_name":calendar.name if calendar else None,"room_name":room_rental.room.name if hasattr(room_rental, 'room') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            if not calendar:
                logger.error(f'No calendar found for room {room_rental.room.name}')
                return None

            # Get start and end dates
            start_date = room_rental.get_start_date()
            end_date = room_rental.get_end_date()

            if not start_date or not end_date:
                logger.error(f'Missing dates for room rental {room_rental.id}')
                return None

            # Get user display name (first_name + last_name from Profile)
            user = room_rental.rental_request.user
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

            # UID - use rental ID to identify the event
            uid = f"ok-tools-booking-{room_rental.id}@ok-tools"
            event.add("uid", uid)

            # Summary: User name - Room name - Project name
            summary = f"{user_display_name} – {room_rental.room.name} – {room_rental.rental_request.project_name}"
            event.add("summary", summary)

            # Location: Room name
            event.add("location", room_rental.room.name)

            # Add dates with timezone
            # icalendar will automatically add TZID parameter when datetime is timezone-aware
            event.add("dtstart", start_date)
            event.add("dtend", end_date)

            # Description: Booking details
            user_name = user_display_name
            description_parts = [
                f"OK-Tools Booking #{room_rental.rental_request.id}",
                f"User: {user_name} ({user.email})",
                f"Project: {room_rental.rental_request.project_name}",
                f"Purpose: {room_rental.rental_request.purpose}",
                f"People: {room_rental.people_count}",
            ]
            
            if room_rental.notes:
                description_parts.append(f"\nNotes:\n{room_rental.notes}")
            
            if room_rental.rental_request.notes:
                description_parts.append(f"\nRequest Notes:\n{room_rental.rental_request.notes}")

            event.add("description", "\n".join(description_parts))

            # Add to calendar
            cal.add_component(event)

            # Convert to iCal string
            ical_text = cal.to_ical().decode("utf-8")

            # Create or update event
            if room_rental.nextcloud_event_href:
                # Update existing event
                try:
                    vevent = calendar.event_by_url(room_rental.nextcloud_event_href)
                    vevent.data = ical_text
                    vevent.save()
                    logger.info(
                        f'Updated Nextcloud event for room rental {room_rental.id} '
                        f'at {room_rental.nextcloud_event_href}'
                    )
                    return room_rental.nextcloud_event_href
                except self.caldav.error.NotFoundError:
                    # Event was deleted, create new one
                    logger.warning(
                        f'Event {room_rental.nextcloud_event_href} not found, creating new event'
                    )
                    room_rental.nextcloud_event_href = None
                except Exception as e:
                    logger.error(f'Error updating Nextcloud event: {e}')
                    return None
            
            # Create new event (either first time or after NotFoundError)
            if not room_rental.nextcloud_event_href:
                try:
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rental/services/nextcloud_calendar_service.py:230","message":"Creating new event in CalDAV","data":{"room_rental_id":room_rental.id,"ical_length":len(ical_text)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    # Use save_event with iCal string (caldav 2.2.0+)
                    # save_event can accept iCal string or parameters
                    try:
                        # Try new API first (caldav 2.2.0+)
                        vevent = calendar.save_event(ical_text)
                    except (TypeError, AttributeError) as api_error:
                        # #region agent log
                        try:
                            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rental/services/nextcloud_calendar_service.py:214","message":"New API failed, trying old API","data":{"error":str(api_error)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                        except: pass
                        # #endregion
                        # Fallback to old API (caldav < 2.2.0)
                        vevent = calendar.add_event(ical_text)
                    
                    event_href = vevent.url
                    logger.info(
                        f'Created Nextcloud event for room rental {room_rental.id} at {event_href}'
                    )
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rental/services/nextcloud_calendar_service.py:221","message":"Event created successfully","data":{"event_href":event_href,"room_rental_id":room_rental.id},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    return event_href
                except Exception as e:
                    logger.error(f'Error creating Nextcloud event: {e}')
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rental/services/nextcloud_calendar_service.py:224","message":"Exception creating event","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    return None

        except Exception as e:
            logger.error(f'Error syncing room rental {room_rental.id} to Nextcloud: {e}', exc_info=True)
            return None

    def delete_room_rental_event(self, room_rental) -> bool:
        """Delete a room rental event from Nextcloud Calendar.
        
        Args:
            room_rental: RoomRental model instance with nextcloud_event_href
            
        Returns:
            True if successful, False otherwise
        """
        # #region agent log
        import json
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:230","message":"delete_room_rental_event called","data":{"room_rental_id":room_rental.id if hasattr(room_rental, 'id') else None,"event_href":room_rental.nextcloud_event_href if hasattr(room_rental, 'nextcloud_event_href') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        if not room_rental.nextcloud_event_href:
            # #region agent log
            try:
                with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:240","message":"No event href to delete","data":{"room_rental_id":room_rental.id if hasattr(room_rental, 'id') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            return True  # Nothing to delete

        try:
            calendar = self._get_calendar_for_room(room_rental.room)
            # #region agent log
            try:
                with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:247","message":"Calendar lookup for delete","data":{"calendar_found":calendar is not None,"room_name":room_rental.room.name if hasattr(room_rental, 'room') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            if not calendar:
                logger.warning(f'No calendar found for room {room_rental.room.name}, cannot delete event')
                return False

            try:
                vevent = calendar.event_by_url(room_rental.nextcloud_event_href)
                vevent.delete()
                logger.info(
                    f'Deleted Nextcloud event for room rental {room_rental.id} '
                    f'at {room_rental.nextcloud_event_href}'
                )
                # #region agent log
                try:
                    with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:260","message":"Event deleted successfully","data":{"room_rental_id":room_rental.id,"event_href":room_rental.nextcloud_event_href},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                return True
            except self.caldav.error.NotFoundError:
                # Event already deleted, that's fine
                logger.info(f'Event {room_rental.nextcloud_event_href} already deleted')
                # #region agent log
                try:
                    with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:268","message":"Event already deleted (NotFoundError)","data":{"room_rental_id":room_rental.id,"event_href":room_rental.nextcloud_event_href},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                return True
            except Exception as e:
                logger.error(f'Error deleting Nextcloud event: {e}')
                # #region agent log
                try:
                    with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:275","message":"Exception deleting event","data":{"error":str(e),"error_type":type(e).__name__,"room_rental_id":room_rental.id},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                return False

        except Exception as e:
            logger.error(f'Error deleting room rental {room_rental.id} from Nextcloud: {e}', exc_info=True)
            # #region agent log
            try:
                with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/services/nextcloud_calendar_service.py:283","message":"Exception in delete_room_rental_event","data":{"error":str(e),"room_rental_id":room_rental.id if hasattr(room_rental, 'id') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            return False


