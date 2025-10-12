"""Management command to scan video storage and update database."""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from media_files.models import StorageLocation, VideoFile, FileOperation
from media_files.utils import (
    scan_directory,
    extract_number_from_filename,
    extract_video_metadata,
    calculate_checksum,
    get_file_modified_time,
)


logger = logging.getLogger('django')


class Command(BaseCommand):
    """Scan video storage and update VideoFile records in database."""

    help = 'Scan video storage locations and update database with found files'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--storage-id',
            type=int,
            help='Scan specific storage location by ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Scan all active storage locations',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rescan even if files were recently scanned',
        )
        parser.add_argument(
            '--update-metadata',
            action='store_true',
            help='Update metadata for existing files',
        )
        parser.add_argument(
            '--calculate-checksum',
            action='store_true',
            help='Calculate checksums (slow for large files)',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        storage_id = options.get('storage_id')
        scan_all = options.get('all')
        force = options.get('force')
        update_metadata = options.get('update_metadata')
        calculate_checksums = options.get('calculate_checksum')

        # Determine which storages to scan
        if storage_id:
            storages = StorageLocation.objects.filter(id=storage_id)
            if not storages.exists():
                raise CommandError(f'Storage location with ID {storage_id} not found')
        elif scan_all:
            storages = StorageLocation.objects.filter(is_active=True)
        else:
            raise CommandError('Specify --storage-id or --all')

        total_found = 0
        total_created = 0
        total_updated = 0
        total_errors = 0

        for storage in storages:
            self.stdout.write(f'\nScanning storage: {storage.name} ({storage.path})')
            
            try:
                # Scan directory for video files
                found_files = scan_directory(storage)
                total_found += len(found_files)
                
                self.stdout.write(f'Found {len(found_files)} video files')
                
                # Mark files not found as unavailable
                found_numbers = set()
                for filename, rel_path, abs_path in found_files:
                    number = extract_number_from_filename(filename)
                    if number:
                        found_numbers.add(number)
                
                # Mark missing files as unavailable
                existing_videos = VideoFile.objects.filter(storage_location=storage)
                for video in existing_videos:
                    if video.number not in found_numbers and video.is_available:
                        video.is_available = False
                        video.save(update_fields=['is_available'])
                        self.stdout.write(
                            self.style.WARNING(f'Marked unavailable: {video.number} - {video.filename}')
                        )
                
                for filename, rel_path, abs_path in found_files:
                    try:
                        # Extract number from filename
                        number = extract_number_from_filename(filename)
                        
                        if not number:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Could not extract number from: {filename}'
                                )
                            )
                            continue
                        
                        # Check if VideoFile already exists
                        video_file, created = VideoFile.objects.get_or_create(
                            number=number,
                            defaults={
                                'filename': filename,
                                'storage_location': storage,
                                'file_path': rel_path,
                                'is_available': True,
                            }
                        )
                        
                        if created:
                            total_created += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'Created: {number} - {filename}')
                            )
                        else:
                            # Update existing record - always check availability
                            video_file.filename = filename
                            video_file.storage_location = storage
                            video_file.file_path = rel_path
                            video_file.is_available = True  # File exists, so it's available
                            total_updated += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'Updated: {number} - {filename}')
                            )
                        
                        # Extract and update metadata
                        self.stdout.write(f'Extracting metadata for: {filename}')
                        metadata = extract_video_metadata(abs_path)
                        
                        # Update VideoFile with metadata
                        if 'format' in metadata:
                            video_file.format = metadata['format']
                        if 'file_size' in metadata:
                            video_file.file_size = metadata['file_size']
                        if 'duration' in metadata:
                            video_file.duration = metadata['duration']
                        if 'total_bitrate' in metadata:
                            video_file.total_bitrate = metadata['total_bitrate']
                        
                        # Video metadata
                        video_file.has_video = metadata.get('has_video', False)
                        if video_file.has_video:
                            video_file.video_codec = metadata.get('video_codec', '')
                            video_file.video_codec_long = metadata.get('video_codec_long', '')
                            video_file.video_profile = metadata.get('video_profile', '')
                            video_file.video_bitrate = metadata.get('video_bitrate')
                            video_file.fps = metadata.get('fps')
                            video_file.width = metadata.get('width')
                            video_file.height = metadata.get('height')
                            video_file.aspect_ratio = metadata.get('aspect_ratio', '')
                            video_file.pixel_format = metadata.get('pixel_format', '')
                            video_file.color_space = metadata.get('color_space', '')
                            video_file.color_range = metadata.get('color_range', '')
                            video_file.chroma_subsampling = metadata.get('chroma_subsampling', '')
                        
                        # Audio metadata
                        video_file.has_audio = metadata.get('has_audio', False)
                        if video_file.has_audio:
                            video_file.audio_codec = metadata.get('audio_codec', '')
                            video_file.audio_codec_long = metadata.get('audio_codec_long', '')
                            video_file.audio_bitrate = metadata.get('audio_bitrate')
                            video_file.audio_sample_rate = metadata.get('audio_sample_rate')
                            video_file.audio_channels = metadata.get('audio_channels')
                            video_file.audio_channel_layout = metadata.get('audio_channel_layout', '')
                        
                        # Store full metadata JSON
                        if 'raw_json' in metadata:
                            video_file.metadata_json = metadata['raw_json']
                        
                        # Update timestamps
                        video_file.last_scanned = timezone.now()
                        video_file.last_modified = get_file_modified_time(abs_path)
                        
                        # Calculate checksum if requested
                        if calculate_checksums:
                            self.stdout.write(f'Calculating checksum for: {filename}')
                            video_file.checksum = calculate_checksum(abs_path)
                        
                        video_file.save()
                        
                        # Log operation
                        FileOperation.objects.create(
                            video_file=video_file,
                            operation_type='SCAN',
                            source_location=storage,
                            status='SUCCESS',
                            details={'filename': filename, 'path': rel_path}
                        )
                        
                    except Exception as e:
                        total_errors += 1
                        self.stdout.write(
                            self.style.ERROR(f'Error processing {filename}: {str(e)}')
                        )
                        logger.error(f'Error processing {filename}: {str(e)}', exc_info=True)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error scanning storage {storage.name}: {str(e)}')
                )
                logger.error(f'Error scanning storage {storage.name}: {str(e)}', exc_info=True)
                total_errors += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Scan Complete ==='))
        self.stdout.write(f'Total files found: {total_found}')
        self.stdout.write(f'New records created: {total_created}')
        self.stdout.write(f'Records updated: {total_updated}')
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {total_errors}'))

