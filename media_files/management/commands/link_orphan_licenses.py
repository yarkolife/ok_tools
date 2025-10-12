"""Management command to find and link videos for licenses without video files."""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from licenses.models import License
from media_files.models import VideoFile


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Find and link videos for licenses that don't have associated video files."""

    help = 'Search for videos matching licenses without video files and link them'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--scan-first',
            action='store_true',
            help='Scan all storages before searching for matches'
        )
        parser.add_argument(
            '--number',
            type=int,
            help='Link specific license number only'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        scan_first = options['scan_first']
        specific_number = options.get('number')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Scan storages first if requested
        if scan_first:
            self.stdout.write('Scanning all active storage locations first...')
            from django.core.management import call_command
            try:
                call_command('auto_scan')
                self.stdout.write(self.style.SUCCESS('✓ Scanning completed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Scanning failed: {str(e)}'))
                return
        
        # Find orphan licenses (licenses without video files)
        if specific_number:
            orphan_licenses = License.objects.filter(number=specific_number)
        else:
            # Get all licenses that don't have linked videos
            all_license_numbers = set(License.objects.values_list('number', flat=True))
            linked_video_numbers = set(
                VideoFile.objects.filter(license__isnull=False).values_list('number', flat=True)
            )
            orphan_numbers = all_license_numbers - linked_video_numbers
            orphan_licenses = License.objects.filter(number__in=orphan_numbers)
        
        if not orphan_licenses.exists():
            self.stdout.write(self.style.SUCCESS('No orphan licenses found - all licenses have videos!'))
            return
        
        self.stdout.write(f'Found {orphan_licenses.count()} license(s) without video files')
        
        stats = {
            'checked': 0,
            'found': 0,
            'linked': 0,
            'not_found': 0,
            'duration_synced': 0,
            'errors': 0
        }
        
        for license in orphan_licenses:
            stats['checked'] += 1
            
            try:
                # Search for video with same number
                videos = VideoFile.objects.filter(
                    number=license.number,
                    is_available=True
                )
                
                if not videos.exists():
                    self.stdout.write(f'#{license.number}: No video found in storage')
                    stats['not_found'] += 1
                    continue
                
                # If multiple videos, select best quality
                if videos.count() > 1:
                    storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
                    video = max(videos, key=lambda v: (
                        storage_priority.get(v.storage_location.storage_type, 0),
                        v.total_bitrate or 0,
                        v.created_at
                    ))
                    self.stdout.write(
                        f'#{license.number}: Found {videos.count()} videos, '
                        f'selected best quality from {video.storage_location.name}'
                    )
                else:
                    video = videos.first()
                    self.stdout.write(
                        f'#{license.number}: Found video in {video.storage_location.name}'
                    )
                
                stats['found'] += 1
                
                # Link video to license
                if not dry_run:
                    video.license = license
                    video.save(update_fields=['license'])
                    
                    # Sync duration from video to license
                    if video.duration:
                        from datetime import timedelta
                        video_seconds = int(video.duration.total_seconds())
                        rounded_duration = timedelta(seconds=video_seconds)
                        
                        if license.duration:
                            license_seconds = int(license.duration.total_seconds())
                            duration_diff = abs(video_seconds - license_seconds)
                            
                            if duration_diff >= 1:
                                license.duration = rounded_duration
                                license.save(update_fields=['duration'])
                                self.stdout.write(
                                    f'  → Duration synced: {rounded_duration} (diff: {duration_diff}s)'
                                )
                                stats['duration_synced'] += 1
                        else:
                            license.duration = rounded_duration
                            license.save(update_fields=['duration'])
                            self.stdout.write(f'  → Duration synced: {rounded_duration}')
                            stats['duration_synced'] += 1
                
                stats['linked'] += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'#{license.number}: Error - {str(e)}')
                )
                stats['errors'] += 1
                logger.error(f'Error linking license #{license.number}: {str(e)}', exc_info=True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Link Orphan Licenses Complete ==='))
        self.stdout.write(f'Licenses checked: {stats["checked"]}')
        self.stdout.write(f'Videos found: {stats["found"]}')
        self.stdout.write(f'Videos linked: {stats["linked"]}')
        self.stdout.write(f'Duration synced: {stats["duration_synced"]}')
        self.stdout.write(f'Not found: {stats["not_found"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {stats["errors"]}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
