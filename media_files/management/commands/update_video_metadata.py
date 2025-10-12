"""Management command to update video metadata."""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from media_files.models import VideoFile, FileOperation
from media_files.utils import extract_video_metadata, calculate_checksum


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Update metadata for existing video files."""

    help = 'Update metadata for video files in database'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--number',
            type=int,
            help='Update specific video by number',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all video files',
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Update only files with missing metadata',
        )
        parser.add_argument(
            '--calculate-checksum',
            action='store_true',
            help='Recalculate checksums',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        number = options.get('number')
        update_all = options.get('all')
        missing_only = options.get('missing_only')
        calculate_checksums = options.get('calculate_checksum')

        # Determine which files to update
        if number:
            videos = VideoFile.objects.filter(number=number)
            if not videos.exists():
                raise CommandError(f'Video file with number {number} not found')
        elif update_all:
            videos = VideoFile.objects.filter(is_available=True)
            if missing_only:
                videos = videos.filter(duration__isnull=True)
        else:
            raise CommandError('Specify --number or --all')

        total_updated = 0
        total_errors = 0

        for video in videos:
            try:
                self.stdout.write(f'\nUpdating: {video.number} - {video.filename}')
                
                abs_path = video.full_path
                
                # Extract metadata
                metadata = extract_video_metadata(abs_path)
                
                # Update VideoFile with metadata
                if 'format' in metadata:
                    video.format = metadata['format']
                if 'file_size' in metadata:
                    video.file_size = metadata['file_size']
                if 'duration' in metadata:
                    video.duration = metadata['duration']
                if 'total_bitrate' in metadata:
                    video.total_bitrate = metadata['total_bitrate']
                
                # Video metadata
                video.has_video = metadata.get('has_video', False)
                if video.has_video:
                    video.video_codec = metadata.get('video_codec', '')
                    video.video_codec_long = metadata.get('video_codec_long', '')
                    video.video_profile = metadata.get('video_profile', '')
                    video.video_bitrate = metadata.get('video_bitrate')
                    video.fps = metadata.get('fps')
                    video.width = metadata.get('width')
                    video.height = metadata.get('height')
                    video.aspect_ratio = metadata.get('aspect_ratio', '')
                    video.pixel_format = metadata.get('pixel_format', '')
                    video.color_space = metadata.get('color_space', '')
                    video.color_range = metadata.get('color_range', '')
                    video.chroma_subsampling = metadata.get('chroma_subsampling', '')
                
                # Audio metadata
                video.has_audio = metadata.get('has_audio', False)
                if video.has_audio:
                    video.audio_codec = metadata.get('audio_codec', '')
                    video.audio_codec_long = metadata.get('audio_codec_long', '')
                    video.audio_bitrate = metadata.get('audio_bitrate')
                    video.audio_sample_rate = metadata.get('audio_sample_rate')
                    video.audio_channels = metadata.get('audio_channels')
                    video.audio_channel_layout = metadata.get('audio_channel_layout', '')
                
                # Store full metadata JSON
                if 'raw_json' in metadata:
                    video.metadata_json = metadata['raw_json']
                
                # Update timestamp
                video.last_scanned = timezone.now()
                
                # Calculate checksum if requested
                if calculate_checksums:
                    self.stdout.write(f'Calculating checksum...')
                    video.checksum = calculate_checksum(abs_path)
                
                video.save()
                
                # Log operation
                FileOperation.objects.create(
                    video_file=video,
                    operation_type='METADATA_UPDATE',
                    status='SUCCESS',
                )
                
                total_updated += 1
                self.stdout.write(self.style.SUCCESS(f'Updated successfully'))
                
            except FileNotFoundError:
                video.is_available = False
                video.save()
                self.stdout.write(
                    self.style.WARNING(f'File not found, marked as unavailable')
                )
            except Exception as e:
                total_errors += 1
                self.stdout.write(
                    self.style.ERROR(f'Error: {str(e)}')
                )
                logger.error(f'Error updating video {video.number}: {str(e)}', exc_info=True)
                
                # Log failed operation
                FileOperation.objects.create(
                    video_file=video,
                    operation_type='METADATA_UPDATE',
                    status='FAILED',
                    error_message=str(e),
                )
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Update Complete ==='))
        self.stdout.write(f'Total updated: {total_updated}')
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {total_errors}'))

