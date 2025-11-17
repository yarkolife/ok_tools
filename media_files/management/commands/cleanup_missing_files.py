"""Management command to cleanup VideoFile records for files that no longer exist on disk."""

import logging
import os
from django.core.management.base import BaseCommand
from django.db import connection
from media_files.models import VideoFile, StorageLocation


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Cleanup VideoFile records for files that no longer exist on disk."""

    help = 'Remove VideoFile records for files that have been deleted from disk'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes'
        )
        parser.add_argument(
            '--storage-id',
            type=int,
            help='Check specific storage location by ID'
        )
        parser.add_argument(
            '--all-storages',
            action='store_true',
            help='Check all active storage locations'
        )
        parser.add_argument(
            '--mark-unavailable',
            action='store_true',
            help='Mark files as unavailable instead of deleting records'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        storage_id = options.get('storage_id')
        all_storages = options.get('all_storages')
        mark_unavailable = options.get('mark_unavailable')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Determine which storages to check
        if storage_id:
            storages = StorageLocation.objects.filter(id=storage_id)
            if not storages.exists():
                self.stdout.write(self.style.ERROR(f'Storage location with ID {storage_id} not found'))
                return
        elif all_storages:
            storages = StorageLocation.objects.filter(is_active=True)
        else:
            # Default: check all active storages
            storages = StorageLocation.objects.filter(is_active=True)
        
        if not storages.exists():
            self.stdout.write('No storage locations to check')
            return
        
        total_checked = 0
        total_missing = 0
        total_deleted = 0
        total_marked = 0
        
        for storage in storages:
            self.stdout.write(f'\nChecking storage: {storage.name} ({storage.path})')
            
            # Get all videos for this storage
            videos = VideoFile.objects.filter(
                storage_location=storage,
                is_available=True  # Only check files marked as available
            ).select_related('storage_location')
            
            storage_checked = 0
            storage_missing = 0
            storage_deleted = 0
            storage_marked = 0
            
            for video in videos:
                storage_checked += 1
                total_checked += 1
                
                try:
                    file_path = video.full_path
                    file_exists = os.path.exists(file_path)
                    
                    if not file_exists:
                        storage_missing += 1
                        total_missing += 1
                        
                        if mark_unavailable:
                            if not dry_run:
                                video.is_available = False
                                video.save(update_fields=['is_available'])
                                logger.info(f'Marked VideoFile {video.number} as unavailable: {video.filename}')
                            self.stdout.write(
                                f'  {"Would mark" if dry_run else "Marked"} as unavailable: '
                                f'{video.number} - {video.filename}'
                            )
                            storage_marked += 1
                            total_marked += 1
                        else:
                            if not dry_run:
                                # Delete related FileOperation objects using raw SQL
                                with connection.cursor() as cursor:
                                    cursor.execute(
                                        "DELETE FROM media_files_fileoperation WHERE video_file_id = %s",
                                        [video.id]
                                    )
                                
                                # Delete the VideoFile
                                logger.info(f'Deleting VideoFile {video.number} (file missing): {video.filename}')
                                video.delete()
                            
                            self.stdout.write(
                                f'  {"Would delete" if dry_run else "Deleted"}: '
                                f'{video.number} - {video.filename}'
                            )
                            storage_deleted += 1
                            total_deleted += 1
                
                except Exception as e:
                    logger.error(f'Error checking file {video.filename}: {str(e)}')
                    self.stdout.write(
                        self.style.ERROR(f'  Error checking {video.number} - {video.filename}: {str(e)}')
                    )
            
            # Storage summary
            if storage_missing > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Storage summary: {storage_checked} checked, '
                        f'{storage_missing} missing, '
                        f'{storage_deleted if not mark_unavailable else storage_marked} '
                        f'{"deleted" if not mark_unavailable else "marked"}'
                    )
                )
            else:
                self.stdout.write(f'  Storage summary: {storage_checked} checked, all files exist')
        
        # Overall summary
        self.stdout.write(self.style.SUCCESS('\n=== Cleanup Complete ==='))
        self.stdout.write(f'Total files checked: {total_checked}')
        self.stdout.write(f'Total files missing: {total_missing}')
        
        if mark_unavailable:
            self.stdout.write(f'Total records {"would be marked" if dry_run else "marked"} as unavailable: {total_marked}')
        else:
            self.stdout.write(f'Total records {"would be deleted" if dry_run else "deleted"}: {total_deleted}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a dry run. Use without --dry-run to actually make changes.'))

