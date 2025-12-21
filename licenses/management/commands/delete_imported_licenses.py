"""
Django management command to delete licenses imported from WordPress.

Usage:
    # Delete licenses created today
    python manage.py delete_imported_licenses --created-today
    
    # Delete licenses by number range
    python manage.py delete_imported_licenses --from-number 1000 --to-number 3820
    
    # Delete licenses by profile
    python manage.py delete_imported_licenses --profile-id 1
    
    # Dry run (show what would be deleted)
    python manage.py delete_imported_licenses --created-today --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from licenses.models import License
from contributions.models import Contribution


class Command(BaseCommand):
    """Command to delete licenses imported from WordPress."""

    help = 'Delete licenses imported from WordPress (by date, number range, or profile)'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--created-today',
            action='store_true',
            help='Delete licenses created today'
        )
        parser.add_argument(
            '--created-since',
            type=str,
            help='Delete licenses created since date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--from-number',
            type=int,
            help='Delete licenses from this number (inclusive)'
        )
        parser.add_argument(
            '--to-number',
            type=int,
            help='Delete licenses up to this number (inclusive)'
        )
        parser.add_argument(
            '--profile-id',
            type=int,
            help='Delete licenses with this profile ID'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        created_today = options['created_today']
        created_since = options.get('created_since')
        from_number = options.get('from_number')
        to_number = options.get('to_number')
        profile_id = options.get('profile_id')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No records will be deleted\n'))

        # Build query
        queryset = License.objects.all()

        # Filter by date
        if created_today:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            queryset = queryset.filter(created_at__gte=today_start)
            self.stdout.write(f'Filtering: created today (since {today_start})\n')
        elif created_since:
            try:
                since_date = datetime.strptime(created_since, '%Y-%m-%d')
                since_date = timezone.make_aware(since_date)
                queryset = queryset.filter(created_at__gte=since_date)
                self.stdout.write(f'Filtering: created since {since_date}\n')
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')

        # Filter by number range
        if from_number is not None:
            queryset = queryset.filter(number__gte=from_number)
            self.stdout.write(f'Filtering: number >= {from_number}\n')
        if to_number is not None:
            queryset = queryset.filter(number__lte=to_number)
            self.stdout.write(f'Filtering: number <= {to_number}\n')

        # Filter by profile
        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
            self.stdout.write(f'Filtering: profile_id = {profile_id}\n')

        # Check if any filters applied
        if not any([created_today, created_since, from_number is not None, to_number is not None, profile_id]):
            raise CommandError(
                'No filter specified. Use --created-today, --created-since, '
                '--from-number/--to-number, or --profile-id'
            )

        # Get count
        count = queryset.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No licenses found matching criteria'))
            return

        self.stdout.write(self.style.WARNING(
            f'\n{"=" * 60}\n'
            f'  Found {count} license(s) to delete\n'
            f'{"=" * 60}\n'
        ))

        # Show sample
        sample = queryset[:10]
        self.stdout.write('Sample licenses to delete:')
        for license in sample:
            self.stdout.write(
                f'  #{license.number}: {license.title} '
                f'(Profile: {license.profile}, Created: {license.created_at})'
            )
        if count > 10:
            self.stdout.write(f'  ... and {count - 10} more\n')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN - No records were actually deleted. Remove --dry-run to delete.'
            ))
            return

        # Confirm deletion
        self.stdout.write(self.style.ERROR(
            '\n⚠️  WARNING: This will permanently delete licenses and their contributions!'
        ))
        confirm = input('Type "DELETE" to confirm: ')
        if confirm != 'DELETE':
            self.stdout.write(self.style.WARNING('Deletion cancelled'))
            return

        # Delete contributions first (they have foreign key to licenses)
        contributions_count = Contribution.objects.filter(
            license__in=queryset
        ).count()

        if contributions_count > 0:
            self.stdout.write(f'Deleting {contributions_count} contribution(s)...')
            with transaction.atomic():
                Contribution.objects.filter(license__in=queryset).delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {contributions_count} contribution(s)'))

        # Delete licenses
        self.stdout.write(f'Deleting {count} license(s)...')
        with transaction.atomic():
            deleted_count, _ = queryset.delete()

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Successfully deleted {deleted_count} license(s) and {contributions_count} contribution(s)'
        ))

