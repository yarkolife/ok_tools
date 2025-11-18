"""Management command to export mediathek import report."""

import csv
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db.models import Min, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from contributions.models import Contribution
from licenses.models import License
from media_files.models import VideoFile
from ok_tools.datetime import TZ


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Export mediathek import report with primary contributions."""

    help = 'Export mediathek import report with primary contributions filtered by period and criteria'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--date-from',
            type=str,
            required=True,
            help='Start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--date-to',
            type=str,
            required=True,
            help='End date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='mediathek_report.csv',
            help='Output CSV file path (default: mediathek_report.csv)'
        )
        parser.add_argument(
            '--media-authority',
            type=int,
            help='Filter by Media Authority ID'
        )
        parser.add_argument(
            '--global-producer',
            action='store_true',
            help='Filter by Global Producer (Yes only)'
        )
        parser.add_argument(
            '--no-global-producer',
            action='store_true',
            help='Filter by Global Producer (No only)'
        )
        parser.add_argument(
            '--store-in-mediathek',
            action='store_true',
            help='Filter by Store in OK media library (Yes only)'
        )
        parser.add_argument(
            '--no-store-in-mediathek',
            action='store_true',
            help='Filter by Store in OK media library (No only)'
        )
        parser.add_argument(
            '--has-video',
            action='store_true',
            help='Filter by Has video (Yes only)'
        )
        parser.add_argument(
            '--no-video',
            action='store_true',
            help='Filter by Has video (No only)'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        date_from_str = options['date_from']
        date_to_str = options['date_to']
        output_path = options['output']
        
        # Parse dates
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Invalid date format: {e}'))
            self.stdout.write('Use format: YYYY-MM-DD')
            return
        
        # Convert to datetime with timezone for filtering
        date_from_dt = timezone.make_aware(
            datetime.combine(date_from, datetime.min.time())
        )
        date_to_dt = timezone.make_aware(
            datetime.combine(date_to, datetime.max.time())
        )
        
        self.stdout.write(f'Exporting mediathek report from {date_from} to {date_to}')
        
        # Start with all contributions in the period
        queryset = Contribution.objects.filter(
            broadcast_date__gte=date_from_dt,
            broadcast_date__lte=date_to_dt
        ).select_related(
            'license',
            'license__profile',
            'license__profile__media_authority',
            'license__video_file',
            'license__video_file__storage_location'
        )
        
        # Apply filters
        if options.get('media_authority'):
            queryset = queryset.filter(
                license__profile__media_authority_id=options['media_authority']
            )
            self.stdout.write(f'Filtered by Media Authority ID: {options["media_authority"]}')
        
        if options.get('global_producer'):
            queryset = queryset.filter(license__profile__global_producer=True)
            self.stdout.write('Filtered by Global Producer: Yes')
        elif options.get('no_global_producer'):
            queryset = queryset.filter(license__profile__global_producer=False)
            self.stdout.write('Filtered by Global Producer: No')
        
        if options.get('store_in_mediathek'):
            queryset = queryset.filter(license__store_in_ok_media_library=True)
            self.stdout.write('Filtered by Store in OK media library: Yes')
        elif options.get('no_store_in_mediathek'):
            queryset = queryset.filter(license__store_in_ok_media_library=False)
            self.stdout.write('Filtered by Store in OK media library: No')
        
        if options.get('has_video'):
            queryset = queryset.filter(license__video_file__isnull=False)
            self.stdout.write('Filtered by Has video: Yes')
        elif options.get('no_video'):
            queryset = queryset.filter(license__video_file__isnull=True)
            self.stdout.write('Filtered by Has video: No')
        
        # Get all license IDs from filtered contributions
        license_ids = queryset.values_list('license_id', flat=True).distinct()
        
        if not license_ids:
            self.stdout.write(self.style.WARNING('No contributions found matching criteria'))
            return
        
        # Get primary dates for all licenses
        primary_dates = Contribution.objects.filter(
            license_id__in=license_ids
        ).values('license_id').annotate(
            min_date=Min('broadcast_date')
        )
        
        # Create dictionary for O(1) lookup
        license_primary_dates = {
            item['license_id']: item['min_date']
            for item in primary_dates
        }
        
        # Filter to only primary contributions
        primary_contributions = []
        for contribution in queryset:
            if license_primary_dates.get(contribution.license_id) == contribution.broadcast_date:
                primary_contributions.append(contribution)
        
        self.stdout.write(f'Found {len(primary_contributions)} primary contributions')
        
        # Prepare data for export
        rows = []
        for contribution in primary_contributions:
            license = contribution.license
            profile = license.profile
            video_file = license.get_video_file()
            
            # Get primary broadcast date and time in timezone
            broadcast_dt = contribution.broadcast_date.astimezone(TZ)
            broadcast_datetime = broadcast_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Get Windows path to video
            video_path = ''
            if video_file:
                # Use UNC path if available, otherwise use full_path converted to Windows format
                if video_file.unc_path:
                    video_path = video_file.unc_path
                elif video_file.full_path:
                    # Convert Unix path to Windows format
                    video_path = video_file.full_path.replace('/', '\\')
            
            rows.append({
                'license_number': license.number,
                'title': license.title or '',
                'subtitle': license.subtitle or '',
                'profile': str(profile),
                'broadcast_datetime': broadcast_datetime,
                'video_path': video_path,
            })
        
        # Write to CSV
        if rows:
            fieldnames = [
                'license_number',
                'title',
                'subtitle',
                'profile',
                'broadcast_datetime',
                'video_path',
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Report exported successfully to {output_path}'
                )
            )
            self.stdout.write(f'Total rows: {len(rows)}')
        else:
            self.stdout.write(self.style.WARNING('No data to export'))

