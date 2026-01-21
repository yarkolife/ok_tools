"""Management command to merge duplicate storage locations with the same path."""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from media_files.models import StorageLocation, VideoFile

logger = logging.getLogger('django')


class Command(BaseCommand):
    """Merge duplicate storage locations that point to the same path."""

    help = 'Find and merge duplicate storage locations with identical paths'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be merged without actually merging'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force merge even if storage locations have different names'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        force = options['force']
        
        # Find all storage locations and group by normalized path
        all_storages = StorageLocation.objects.all().order_by('id')
        path_groups = {}
        
        for storage in all_storages:
            # Normalize path (remove trailing slashes, lowercase for comparison)
            normalized_path = storage.path.rstrip('/').lower()
            
            if normalized_path not in path_groups:
                path_groups[normalized_path] = []
            path_groups[normalized_path].append(storage)
        
        # Find duplicates (groups with more than one storage)
        duplicates = {path: storages for path, storages in path_groups.items() 
                     if len(storages) > 1}
        
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicate storage locations found.'))
            return
        
        self.stdout.write(f'Found {len(duplicates)} duplicate path(s):\n')
        
        total_merged = 0
        total_videos_moved = 0
        
        for normalized_path, storages in duplicates.items():
            self.stdout.write(f'\nPath: {storages[0].path}')
            self.stdout.write(f'  Found {len(storages)} storage location(s):')
            
            for storage in storages:
                video_count = storage.videofile_set.count()
                self.stdout.write(
                    f'    - ID {storage.id}: "{storage.name}" '
                    f'({storage.get_storage_type_display()}, '
                    f'scan_enabled={storage.scan_enabled}, '
                    f'active={storage.is_active}, '
                    f'videos={video_count})'
                )
            
            # Choose primary storage:
            # 1. Prefer storage with scan_enabled=True
            # 2. Prefer active storage
            # 3. Prefer newer storage (higher ID)
            primary = None
            for storage in sorted(storages, key=lambda s: (
                not s.scan_enabled,  # False first (scan_enabled=True preferred)
                not s.is_active,     # False first (active=True preferred)
                -s.id               # Higher ID preferred (newer)
            )):
                primary = storage
                break
            
            if not primary:
                self.stdout.write(self.style.ERROR(f'  Could not determine primary storage'))
                continue
            
            self.stdout.write(f'  → Primary: ID {primary.id} "{primary.name}"')
            
            # Check if merge is safe
            secondary_storages = [s for s in storages if s.id != primary.id]
            
            if not force:
                # Check if any secondary has different name and videos
                for secondary in secondary_storages:
                    if secondary.videofile_set.exists() and secondary.name != primary.name:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠️  Secondary storage "{secondary.name}" has videos. '
                                f'Use --force to merge anyway.'
                            )
                        )
                        continue
            
            if dry_run:
                self.stdout.write(self.style.WARNING('  [DRY RUN] Would merge:'))
                for secondary in secondary_storages:
                    video_count = secondary.videofile_set.count()
                    self.stdout.write(
                        f'    - Move {video_count} video(s) from "{secondary.name}" '
                        f'(ID {secondary.id}) to "{primary.name}" (ID {primary.id})'
                    )
                    if video_count > 0:
                        total_videos_moved += video_count
                total_merged += len(secondary_storages)
            else:
                # Perform merge
                with transaction.atomic():
                    for secondary in secondary_storages:
                        video_count = secondary.videofile_set.count()
                        
                        if video_count > 0:
                            # Move all VideoFile records to primary storage
                            moved = VideoFile.objects.filter(
                                storage_location=secondary
                            ).update(storage_location=primary)
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Moved {moved} video(s) from "{secondary.name}" '
                                    f'to "{primary.name}"'
                                )
                            )
                            total_videos_moved += moved
                        
                        # Delete secondary storage
                        secondary_name = secondary.name
                        secondary.delete()
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Deleted storage "{secondary_name}" (ID {secondary.id})')
                        )
                        total_merged += 1
        
        # Summary
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN SUMMARY ==='))
            self.stdout.write(f'Would merge {total_merged} storage location(s)')
            self.stdout.write(f'Would move {total_videos_moved} video file(s)')
            self.stdout.write(self.style.WARNING('\nRun without --dry-run to perform merge.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n=== MERGE COMPLETE ==='))
            self.stdout.write(f'Merged {total_merged} storage location(s)')
            self.stdout.write(f'Moved {total_videos_moved} video file(s)')
            logger.info(
                f'Merged {total_merged} duplicate storage locations, '
                f'moved {total_videos_moved} video files'
            )
