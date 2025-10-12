"""Management command to sync licenses and videos."""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import timedelta

from media_files.models import VideoFile
from licenses.models import License


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Sync licenses and videos - link them and sync durations."""

    help = 'Sync licenses and videos - find matches by number and link them'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--force-sync-duration',
            action='store_true',
            help='Force sync duration even if difference is < 1 second'
        )
        parser.add_argument(
            '--number',
            type=int,
            help='Sync specific license/video number only'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        force_sync = options['force_sync_duration']
        specific_number = options.get('number')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        stats = {
            'licenses_found': 0,
            'videos_found': 0,
            'linked': 0,
            'duration_synced': 0,
            'errors': 0
        }
        
        with transaction.atomic():
            if specific_number:
                # Sync specific number only
                self.stdout.write(f'Syncing license/video #{specific_number}...')
                stats = self._sync_specific_number(specific_number, dry_run, force_sync, stats)
            else:
                # Sync all
                self.stdout.write('Syncing all licenses and videos...')
                
                # Get all numbers that have both license and video
                license_numbers = set(License.objects.values_list('number', flat=True))
                video_numbers = set(VideoFile.objects.values_list('number', flat=True))
                common_numbers = license_numbers & video_numbers
                
                self.stdout.write(f'Found {len(license_numbers)} licenses, {len(video_numbers)} videos')
                self.stdout.write(f'Common numbers to sync: {len(common_numbers)}')
                
                for number in sorted(common_numbers):
                    stats = self._sync_specific_number(number, dry_run, force_sync, stats)
            
            if dry_run:
                # Rollback transaction in dry run mode
                transaction.set_rollback(True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Sync Complete ==='))
        self.stdout.write(f'Licenses found: {stats["licenses_found"]}')
        self.stdout.write(f'Videos found: {stats["videos_found"]}')
        self.stdout.write(f'Linked: {stats["linked"]}')
        self.stdout.write(f'Duration synced: {stats["duration_synced"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {stats["errors"]}'))

    def _sync_specific_number(self, number, dry_run, force_sync, stats):
        """Sync specific license/video number."""
        try:
            # Get license and video
            try:
                license = License.objects.get(number=number)
                stats['licenses_found'] += 1
            except License.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'License #{number} not found'))
                return stats
            
            try:
                video = VideoFile.objects.get(number=number)
                stats['videos_found'] += 1
            except VideoFile.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Video #{number} not found'))
                return stats
            
            # Check if already linked
            if license == video.license:
                self.stdout.write(f'#{number}: Already linked')
            else:
                if not dry_run:
                    video.license = license
                    video.save(update_fields=['license'])
                self.stdout.write(self.style.SUCCESS(f'#{number}: Linked license to video'))
                stats['linked'] += 1
            
            # Sync duration if needed
            if video.duration and license.duration:
                video_seconds = int(video.duration.total_seconds())
                license_seconds = int(license.duration.total_seconds())
                duration_diff = abs(video_seconds - license_seconds)
                
                if force_sync or duration_diff >= 1:
                    if not dry_run:
                        rounded_duration = timedelta(seconds=video_seconds)
                        license.duration = rounded_duration
                        license.save(update_fields=['duration'])
                    
                    self.stdout.write(f'#{number}: Duration synced (diff: {duration_diff}s)')
                    stats['duration_synced'] += 1
                else:
                    self.stdout.write(f'#{number}: Duration difference < 1s, no sync needed')
            
            elif video.duration and not license.duration:
                if not dry_run:
                    rounded_duration = timedelta(seconds=int(video.duration.total_seconds()))
                    license.duration = rounded_duration
                    license.save(update_fields=['duration'])
                
                self.stdout.write(f'#{number}: Duration synced from video to license')
                stats['duration_synced'] += 1
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error syncing #{number}: {str(e)}'))
            stats['errors'] += 1
            logger.error(f'Error syncing #{number}: {str(e)}', exc_info=True)
        
        return stats
