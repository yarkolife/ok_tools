"""Management command to cleanup duplicate video files."""

import logging
from django.core.management.base import BaseCommand
from django.db.models import Count
from media_files.models import VideoFile, StorageLocation


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Cleanup duplicate video files by keeping the best quality version."""

    help = 'Remove duplicate video files, keeping the best quality version'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes'
        )
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Filter by storage type (ARCHIVE, PLAYOUT, CUSTOM)'
        )
        parser.add_argument(
            '--number',
            type=int,
            help='Cleanup duplicates for specific video number only'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options['dry_run']
        storage_type = options.get('storage_type')
        specific_number = options.get('number')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be deleted'))
        
        # Build queryset for videos with duplicates
        videos = VideoFile.objects.annotate(
            duplicate_count=Count('number')
        ).filter(duplicate_count__gt=1)
        
        if storage_type:
            videos = videos.filter(storage_location__storage_type=storage_type)
        
        if specific_number:
            videos = videos.filter(number=specific_number)
        
        # Group by number
        by_number = {}
        for video in videos:
            if video.number not in by_number:
                by_number[video.number] = []
            by_number[video.number].append(video)
        
        if not by_number:
            self.stdout.write('No duplicates found')
            return
        
        deleted_count = 0
        kept_count = 0
        
        for number, video_list in by_number.items():
            self.stdout.write(f'\nProcessing video #{number} ({len(video_list)} versions):')
            
            # Sort by quality (storage priority, bitrate, creation date)
            storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
            
            def quality_score(video):
                return (
                    storage_priority.get(video.storage_location.storage_type, 0),
                    video.total_bitrate or 0,
                    video.created_at or video.last_scanned
                )
            
            # Keep the best quality version
            best_video = max(video_list, key=quality_score)
            duplicates = [v for v in video_list if v.id != best_video.id]
            
            self.stdout.write(f'  Keeping: {best_video.filename} ({best_video.storage_location.name})')
            
            for duplicate in duplicates:
                self.stdout.write(f'  {"Would delete" if dry_run else "Deleting"}: {duplicate.filename} ({duplicate.storage_location.name})')
                
                if not dry_run:
                    # Log before deletion
                    logger.info(f'Deleting duplicate video {duplicate.number} from {duplicate.storage_location.name}')
                    duplicate.delete()
                    deleted_count += 1
                else:
                    deleted_count += 1
            
            kept_count += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Cleanup Complete ==='))
        self.stdout.write(f'Videos processed: {len(by_number)}')
        self.stdout.write(f'Versions kept: {kept_count}')
        self.stdout.write(f'{"Would delete" if dry_run else "Deleted"}: {deleted_count} duplicates')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a dry run. Use without --dry-run to actually delete files.'))
