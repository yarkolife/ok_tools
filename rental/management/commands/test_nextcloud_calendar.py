"""Management command to test Nextcloud Calendar integration."""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('django')


class Command(BaseCommand):
    """Command to test Nextcloud Calendar CalDAV integration."""

    help = 'Test Nextcloud Calendar integration: list calendars, create test event, etc.'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--list-calendars',
            action='store_true',
            help='List all available calendars in Nextcloud',
        )
        parser.add_argument(
            '--test-event',
            action='store_true',
            help='Create a test event in the first available calendar',
        )
        parser.add_argument(
            '--test-room-rental',
            type=int,
            metavar='ROOM_RENTAL_ID',
            help='Test sync for a specific room rental ID',
        )
        parser.add_argument(
            '--calendar-name',
            type=str,
            metavar='CALENDAR_NAME',
            help='Specify calendar name for test event',
        )
        parser.add_argument(
            '--cleanup-test-events',
            action='store_true',
            help='Delete all test events from calendars',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        if not getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False):
            self.stdout.write(
                self.style.ERROR(
                    'Nextcloud Calendar integration is disabled. '
                    'Set NEXTCLOUD_CALENDAR_ENABLED=true to enable.'
                )
            )
            return

        try:
            from rental.services.nextcloud_calendar_service import NextcloudCalendarService
            service = NextcloudCalendarService()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to initialize NextcloudCalendarService: {e}')
            )
            return

        if options['list_calendars']:
            self.list_calendars(service)

        if options['test_event']:
            self.create_test_event(service, options.get('calendar_name'))

        if options['test_room_rental']:
            self.test_room_rental_sync(service, options['test_room_rental'])

        if options['cleanup_test_events']:
            self.cleanup_test_events(service)

        if not any([options['list_calendars'], options['test_event'], options['test_room_rental'], options['cleanup_test_events']]):
            # Default: show info and list calendars
            self.stdout.write(self.style.SUCCESS('Nextcloud Calendar integration is enabled'))
            self.stdout.write(f'CalDAV URL: {getattr(settings, "NEXTCLOUD_CALDAV_BASE_URL", "N/A")}')
            self.stdout.write(f'Username: {getattr(settings, "NEXTCLOUD_CALENDAR_USERNAME", "N/A")}')
            self.stdout.write('')
            self.list_calendars(service)

    def list_calendars(self, service):
        """List all available calendars."""
        self.stdout.write(self.style.SUCCESS('Available calendars:'))
        try:
            calendars = service.principal.calendars()
            if not calendars:
                self.stdout.write(self.style.WARNING('  No calendars found'))
                return

            for i, cal in enumerate(calendars, 1):
                try:
                    # Try to get calendar properties
                    cal_name = cal.name
                    cal_url = cal.url
                    self.stdout.write(f'  {i}. {cal_name}')
                    self.stdout.write(f'     URL: {cal_url}')
                except Exception as e:
                    self.stdout.write(f'  {i}. (Error reading calendar: {e})')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error listing calendars: {e}')
            )

    def create_test_event(self, service, calendar_name=None):
        """Create a test event in Nextcloud Calendar."""
        self.stdout.write(self.style.SUCCESS('Creating test event...'))

        try:
            calendars = service.principal.calendars()
            if not calendars:
                self.stdout.write(
                    self.style.ERROR('No calendars available')
                )
                return

            # Find calendar by name or use first one
            calendar = None
            if calendar_name:
                for cal in calendars:
                    if cal.name == calendar_name:
                        calendar = cal
                        break
                if not calendar:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Calendar "{calendar_name}" not found, using first available'
                        )
                    )
                    calendar = calendars[0]
            else:
                calendar = calendars[0]

            self.stdout.write(f'Using calendar: {calendar.name}')

            # Create test event
            from icalendar import Calendar, Event

            cal = Calendar()
            event = Event()

            # Test event details
            now = timezone.now()
            start_time = now + timedelta(hours=1)
            end_time = start_time + timedelta(hours=2)

            event.add('uid', f'test-event-{now.timestamp()}@ok-tools-test')
            event.add('summary', 'OK-Tools Test Event')
            event.add('description', 'This is a test event created by OK-Tools integration test')
            event.add('location', 'Test Location')
            event.add('dtstart', start_time)
            event.add('dtend', end_time)

            cal.add_component(event)
            ical_text = cal.to_ical().decode('utf-8')

            # Save event (support both caldav 2.2.0+ and older versions)
            try:
                # Try new API first (caldav 2.2.0+)
                vevent = calendar.save_event(ical_text)
            except (TypeError, AttributeError):
                # Fallback to old API (caldav < 2.2.0)
                vevent = calendar.add_event(ical_text)
            
            event_url = vevent.url

            self.stdout.write(
                self.style.SUCCESS(
                    f'Test event created successfully!\n'
                    f'  Event URL: {event_url}\n'
                    f'  Start: {start_time}\n'
                    f'  End: {end_time}'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating test event: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

    def test_room_rental_sync(self, service, room_rental_id):
        """Test syncing a specific room rental."""
        self.stdout.write(
            self.style.SUCCESS(f'Testing sync for room rental ID: {room_rental_id}')
        )

        try:
            from rental.models import RoomRental

            try:
                room_rental = RoomRental.objects.get(id=room_rental_id)
            except RoomRental.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Room rental with ID {room_rental_id} not found')
                )
                return

            self.stdout.write(f'Room: {room_rental.room.name}')
            self.stdout.write(f'Project: {room_rental.rental_request.project_name}')
            self.stdout.write(f'Status: {room_rental.rental_request.status}')
            self.stdout.write(f'Start: {room_rental.get_start_date()}')
            self.stdout.write(f'End: {room_rental.get_end_date()}')

            if room_rental.rental_request.status not in ['reserved', 'issued']:
                self.stdout.write(
                    self.style.WARNING(
                        'Room rental status is not "reserved" or "issued". '
                        'Event will not be synced.'
                    )
                )

            # Try to sync
            event_href = service.sync_room_rental_to_calendar(room_rental)

            if event_href:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Sync successful! Event URL: {event_href}'
                    )
                )
                # Update the room rental
                room_rental.nextcloud_event_href = event_href
                room_rental.save(update_fields=['nextcloud_event_href'])
            else:
                self.stdout.write(
                    self.style.ERROR('Sync failed - no event URL returned')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error testing room rental sync: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

    def cleanup_test_events(self, service):
        """Delete all test events from calendars."""
        self.stdout.write(self.style.SUCCESS('Cleaning up test events...'))

        try:
            calendars = service.principal.calendars()
            total_deleted = 0

            for calendar in calendars:
                try:
                    events = calendar.events()
                    deleted_count = 0
                    for event in events:
                        try:
                            # Check if it's a test event
                            event_url = event.url
                            if 'test-event' in event_url.lower() or 'ok-tools-test' in event_url.lower():
                                event.delete()
                                deleted_count += 1
                                self.stdout.write(f'  Deleted test event from {calendar.name}: {event_url}')
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(f'  Error deleting event: {e}')
                            )
                    
                    if deleted_count > 0:
                        total_deleted += deleted_count
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Deleted {deleted_count} test event(s) from calendar "{calendar.name}"'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Error processing calendar {calendar.name}: {e}')
                    )

            if total_deleted > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'\nTotal deleted: {total_deleted} test event(s)')
                )
            else:
                self.stdout.write(self.style.SUCCESS('No test events found'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error cleaning up test events: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

