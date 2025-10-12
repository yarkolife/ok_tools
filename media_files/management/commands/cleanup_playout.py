"""Management command to cleanup playout storage."""

import logging
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from media_files.models import StorageLocation, VideoFile
from media_files.utils import (
    has_system_attributes,
    is_file_in_use,
    move_video_to_archive,
    verify_file_integrity
)


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Cleanup playout storage - move videos to archive when no longer in use."""

    help = 'Move videos from playout to archive when they are no longer in use'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--check-attributes',
            action='store_true',
            help='Check file system attributes to determine if files are in use'
        )
        parser.add_argument(
            '--check-locks',
            action='store_true',
            help='Check if files are locked by other processes'
        )
        parser.add_argument(
            '--older-than',
            type=int,
            default=7,
            help='Only process videos older than N days (default: 7)'
        )
        parser.add_argument(
            '--storage-id',
            type=int,
            help='Cleanup specific playout storage by ID'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        check_attributes = options['check_attributes']
        check_locks = options['check_locks']
        older_than_days = options['older_than']
        storage_id = options.get('storage_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get playout storage locations
        if storage_id:
            playout_storages = StorageLocation.objects.filter(
                id=storage_id,
                storage_type='PLAYOUT',
                is_active=True
            )
        else:
            playout_storages = StorageLocation.objects.filter(
                storage_type='PLAYOUT',
                is_active=True
            )
        
        if not playout_storages.exists():
            self.stdout.write(self.style.ERROR('No PLAYOUT storage locations found'))
            return
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=older_than_days)
        
        stats = {
            'checked': 0,
            'moved': 0,
            'skipped_in_use': 0,
            'skipped_recent': 0,
            'errors': 0
        }
        
        for storage in playout_storages:
            self.stdout.write(f'Processing playout storage: {storage.name}')
            
            # Get videos in this storage
            videos = VideoFile.objects.filter(
                storage_location=storage,
                is_available=True
            )
            
            self.stdout.write(f'Found {videos.count()} videos in {storage.name}')
            
            for video in videos:
                stats['checked'] += 1
                
                # Check if video is recent
                if video.created_at and video.created_at > cutoff_date:
                    self.stdout.write(f'#{video.number}: Skipped (recent: {video.created_at.date()})')
                    stats['skipped_recent'] += 1
                    continue
                
                # Check if file exists
                if not video.full_path or not os.path.exists(video.full_path):
                    self.stdout.write(f'#{video.number}: File not found - marking unavailable')
                    video.is_available = False
                    video.save(update_fields=['is_available'])
                    continue
                
                # Check if file is in use (system attributes)
                if check_attributes and has_system_attributes(video.full_path):
                    self.stdout.write(f'#{video.number}: Has system attributes - still in use')
                    stats['skipped_in_use'] += 1
                    continue
                
                # Check if file is locked
                if check_locks and is_file_in_use(video.full_path):
                    self.stdout.write(f'#{video.number}: File is locked - still in use')
                    stats['skipped_in_use'] += 1
                    continue
                
                # Verify file integrity before moving
                is_valid, integrity_msg = verify_file_integrity(video)
                if not is_valid:
                    self.stdout.write(
                        self.style.WARNING(f'#{video.number}: Integrity check failed - {integrity_msg}')
                    )
                    continue
                
                # Move to archive
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'#{video.number}: Would move to archive')
                    )
                else:
                    success, message = move_video_to_archive(video)
                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f'#{video.number}: Moved to archive')
                        )
                        stats['moved'] += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'#{video.number}: Failed to move - {message}')
                        )
                        stats['errors'] += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Cleanup Complete ==='))
        self.stdout.write(f'Videos checked: {stats["checked"]}')
        self.stdout.write(f'Videos moved: {stats["moved"]}')
        self.stdout.write(f'Skipped (in use): {stats["skipped_in_use"]}')
        self.stdout.write(f'Skipped (recent): {stats["skipped_recent"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {stats["errors"]}'))

