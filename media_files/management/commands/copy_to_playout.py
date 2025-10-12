"""Management command to copy video files to playout storage."""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from media_files.models import StorageLocation, VideoFile, FileOperation
from media_files.utils import copy_file_with_progress


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Copy video files from archive to playout storage."""

    help = 'Copy video files to playout storage for broadcast'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--number',
            type=int,
            nargs='+',
            help='Video number(s) to copy',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Copy videos for specific date plan (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--destination-id',
            type=int,
            help='Destination storage location ID',
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            default=True,
            help='Verify file integrity after copy (default: True)',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip if file already exists in destination',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        numbers = options.get('number')
        date_str = options.get('date')
        destination_id = options.get('destination_id')
        verify = options.get('verify')
        skip_existing = options.get('skip_existing')

        # Determine video numbers to copy
        if date_str:
            # Get videos from TagesPlan for specific date
            try:
                from planung.models import TagesPlan
                plan_date = parse_date(date_str)
                if not plan_date:
                    raise CommandError(f'Invalid date format: {date_str}')
                
                try:
                    plan = TagesPlan.objects.get(datum=plan_date)
                    numbers = [item.get('number') for item in plan.json_plan.get('items', [])]
                    
                    if not numbers:
                        self.stdout.write(
                            self.style.WARNING(f'No videos in plan for {date_str}')
                        )
                        return
                    
                    self.stdout.write(f'Found {len(numbers)} videos in plan for {date_str}')
                    
                except TagesPlan.DoesNotExist:
                    raise CommandError(f'No plan found for date: {date_str}')
                    
            except ImportError:
                raise CommandError('Planung module not available')
        
        elif not numbers:
            raise CommandError('Specify --number or --date')

        # Get destination storage
        if destination_id:
            try:
                destination = StorageLocation.objects.get(id=destination_id)
            except StorageLocation.DoesNotExist:
                raise CommandError(f'Storage location {destination_id} not found')
        else:
            # Try to find PLAYOUT storage
            destination = StorageLocation.objects.filter(
                storage_type='PLAYOUT',
                is_active=True
            ).first()
            
            if not destination:
                raise CommandError(
                    'No PLAYOUT storage found. Specify --destination-id or create PLAYOUT storage.'
                )

        self.stdout.write(f'Destination: {destination.name} ({destination.path})')
        
        total_copied = 0
        total_skipped = 0
        total_errors = 0

        for number in numbers:
            try:
                # Find video in archive
                video = VideoFile.objects.filter(
                    number=number,
                    is_available=True,
                ).exclude(
                    storage_location=destination
                ).first()
                
                if not video:
                    self.stdout.write(
                        self.style.WARNING(f'Video {number} not found in archive')
                    )
                    total_errors += 1
                    continue
                
                # Check if already exists in destination
                existing = VideoFile.objects.filter(
                    number=number,
                    storage_location=destination,
                    is_available=True
                ).first()
                
                if existing and skip_existing:
                    self.stdout.write(
                        self.style.WARNING(f'Video {number} already exists in destination, skipping')
                    )
                    total_skipped += 1
                    continue
                
                # Copy file
                source_path = video.full_path
                dest_path = f"{destination.path.rstrip('/')}/{video.filename}"
                
                self.stdout.write(f'\nCopying: {number} - {video.filename}')
                self.stdout.write(f'From: {source_path}')
                self.stdout.write(f'To: {dest_path}')
                
                # Create operation record
                operation = FileOperation.objects.create(
                    video_file=video,
                    operation_type='COPY',
                    source_location=video.storage_location,
                    destination_location=destination,
                    status='IN_PROGRESS',
                )
                
                # Perform copy
                success, message = copy_file_with_progress(
                    source_path,
                    dest_path,
                    verify_checksum=verify
                )
                
                if success:
                    # Create new VideoFile record for destination
                    new_video, created = VideoFile.objects.get_or_create(
                        number=video.number,
                        storage_location=destination,
                        defaults={
                            'filename': video.filename,
                            'file_path': video.filename,
                            'file_size': video.file_size,
                            'duration': video.duration,
                            'format': video.format,
                            'is_available': True,
                            'checksum': video.checksum,
                            # Copy all metadata
                            'video_codec': video.video_codec,
                            'video_codec_long': video.video_codec_long,
                            'video_profile': video.video_profile,
                            'video_bitrate': video.video_bitrate,
                            'fps': video.fps,
                            'width': video.width,
                            'height': video.height,
                            'aspect_ratio': video.aspect_ratio,
                            'pixel_format': video.pixel_format,
                            'color_space': video.color_space,
                            'color_range': video.color_range,
                            'chroma_subsampling': video.chroma_subsampling,
                            'audio_codec': video.audio_codec,
                            'audio_codec_long': video.audio_codec_long,
                            'audio_bitrate': video.audio_bitrate,
                            'audio_sample_rate': video.audio_sample_rate,
                            'audio_channels': video.audio_channels,
                            'audio_channel_layout': video.audio_channel_layout,
                            'has_video': video.has_video,
                            'has_audio': video.has_audio,
                            'total_bitrate': video.total_bitrate,
                            'metadata_json': video.metadata_json,
                        }
                    )
                    
                    if not created:
                        # Update existing record
                        new_video.is_available = True
                        new_video.save()
                    
                    operation.status = 'SUCCESS'
                    operation.save()
                    
                    total_copied += 1
                    self.stdout.write(self.style.SUCCESS(f'Copied successfully: {message}'))
                else:
                    operation.status = 'FAILED'
                    operation.error_message = message
                    operation.save()
                    
                    total_errors += 1
                    self.stdout.write(self.style.ERROR(f'Copy failed: {message}'))
                
            except Exception as e:
                total_errors += 1
                self.stdout.write(
                    self.style.ERROR(f'Error copying video {number}: {str(e)}')
                )
                logger.error(f'Error copying video {number}: {str(e)}', exc_info=True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Copy Complete ==='))
        self.stdout.write(f'Total copied: {total_copied}')
        self.stdout.write(f'Skipped: {total_skipped}')
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {total_errors}'))

