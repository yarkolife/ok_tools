"""Tasks for media files operations."""

import logging
from pathlib import Path

from media_files.models import StorageLocation, VideoFile, FileOperation
from media_files.utils import copy_file_with_progress


logger = logging.getLogger('django')


def get_week_folder_for_date(date):
    """
    Get week folder name in format YYYY_KW_WW for given date.
    
    Args:
        date: Date object
        
    Returns:
        String in format like "2025_KW_41"
    """
    import datetime
    
    # Get ISO week number and year
    iso_year, iso_week, _ = date.isocalendar()
    
    return f"{iso_year}_KW_{iso_week:02d}"


def copy_videos_for_plan(license_numbers, broadcast_date):
    """
    Copy videos from archive to playout for scheduled broadcast.
    
    This function is called when a broadcast plan is saved (not draft).
    It automatically copies the needed videos from archive to playout storage.
    
    Args:
        license_numbers: List of license numbers to copy
        broadcast_date: Date of the broadcast plan
        
    Returns:
        Dict with results: {'copied': int, 'skipped': int, 'errors': int}
    """
    results = {
        'copied': 0,
        'skipped': 0,
        'errors': 0,
        'details': []
    }
    
    # Get destination (playout) storage
    destination = StorageLocation.objects.filter(
        storage_type='PLAYOUT',
        is_active=True
    ).first()
    
    if not destination:
        logger.error('No PLAYOUT storage found for auto-copy')
        return results
    
    logger.info(f'Auto-copying {len(license_numbers)} videos for {broadcast_date}')
    
    for number in license_numbers:
        try:
            # Find video with quality prioritization
            videos = VideoFile.objects.filter(
                number=number,
                is_available=True,
            ).exclude(
                storage_location=destination
            ).select_related('storage_location')
            
            if not videos:
                logger.warning(f'Video {number} not found for auto-copy')
                results['errors'] += 1
                results['details'].append({
                    'number': number,
                    'status': 'error',
                    'message': 'Not found in any storage'
                })
                continue
            
            # Sort by priority: ARCHIVE > PLAYOUT > CUSTOM, then by quality
            storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
            video = max(videos, key=lambda v: (
                storage_priority.get(v.storage_location.storage_type, 0),
                v.total_bitrate or 0,
                v.width or 0
            ))
            
            logger.info(f'Selected video {number} from {video.storage_location.name} '
                       f'(bitrate: {video.total_bitrate}, resolution: {video.width}x{video.height})')
            
            # Check if already exists in playout
            existing = VideoFile.objects.filter(
                number=number,
                storage_location=destination,
                is_available=True
            ).first()
            
            if existing:
                logger.info(f'Video {number} already in playout, skipping')
                results['skipped'] += 1
                results['details'].append({
                    'number': number,
                    'status': 'skipped',
                    'message': 'Already in playout'
                })
                continue
            
            # Determine week folder for playout
            week_folder = get_week_folder_for_date(broadcast_date)
            dest_path = f"{destination.path.rstrip('/')}/{week_folder}/{video.filename}"
            
            logger.info(f'Copying video {number} from archive to playout')
            
            # Create operation record
            operation = FileOperation.objects.create(
                video_file=video,
                operation_type='COPY',
                source_location=video.storage_location,
                destination_location=destination,
                status='IN_PROGRESS',
                details={'broadcast_date': str(broadcast_date)}
            )
            
            # Ensure week folder exists
            week_folder_path = f"{destination.path.rstrip('/')}/{week_folder}"
            Path(week_folder_path).mkdir(parents=True, exist_ok=True)
            
            success, message = copy_file_with_progress(
                source_path,
                dest_path,
                verify_checksum=True
            )
            
            if success:
                # Create new VideoFile record for playout
                new_video, created = VideoFile.objects.get_or_create(
                    number=video.number,
                    storage_location=destination,
                    defaults={
                        'filename': video.filename,
                        'file_path': f"{week_folder}/{video.filename}",
                        'file_size': video.file_size,
                        'duration': video.duration,
                        'format': video.format,
                        'is_available': True,
                        'checksum': video.checksum,
                        # Copy metadata
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
                    new_video.is_available = True
                    new_video.save()
                
                operation.status = 'SUCCESS'
                operation.save()
                
                results['copied'] += 1
                results['details'].append({
                    'number': number,
                    'status': 'success',
                    'message': message
                })
                logger.info(f'Successfully copied video {number} to playout')
            else:
                operation.status = 'FAILED'
                operation.error_message = message
                operation.save()
                
                results['errors'] += 1
                results['details'].append({
                    'number': number,
                    'status': 'error',
                    'message': message
                })
                logger.error(f'Failed to copy video {number}: {message}')
        
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'number': number,
                'status': 'error',
                'message': str(e)
            })
            logger.error(f'Exception copying video {number}: {str(e)}', exc_info=True)
    
    logger.info(
        f'Auto-copy completed: {results["copied"]} copied, '
        f'{results["skipped"]} skipped, {results["errors"]} errors'
    )
    
    return results


def copy_video_to_playout(video_file, destination_storage=None, user=None, broadcast_date=None):
    """
    Copy a single video file to playout storage.
    
    Args:
        video_file: VideoFile instance to copy
        destination_storage: Destination StorageLocation (optional, defaults to PLAYOUT)
        user: User performing the operation (optional)
        broadcast_date: Date for week folder determination (optional, defaults to today)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not destination_storage:
        destination_storage = StorageLocation.objects.filter(
            storage_type='PLAYOUT',
            is_active=True
        ).first()
        
        if not destination_storage:
            return False, 'No PLAYOUT storage configured'
    
    # Check if already exists
    existing = VideoFile.objects.filter(
        number=video_file.number,
        storage_location=destination_storage,
        is_available=True
    ).first()
    
    if existing:
        return False, 'Video already exists in playout'
    
    # Determine week folder for playout
    if broadcast_date:
        week_folder = get_week_folder_for_date(broadcast_date)
    else:
        # Use current date if no broadcast_date provided
        from datetime import date
        week_folder = get_week_folder_for_date(date.today())
    
    try:
        source_path = video_file.full_path
        dest_path = f"{destination_storage.path.rstrip('/')}/{week_folder}/{video_file.filename}"
        
        # Ensure week folder exists
        week_folder_path = f"{destination_storage.path.rstrip('/')}/{week_folder}"
        Path(week_folder_path).mkdir(parents=True, exist_ok=True)
        
        # Create operation record
        operation = FileOperation.objects.create(
            video_file=video_file,
            operation_type='COPY',
            source_location=video_file.storage_location,
            destination_location=destination_storage,
            performed_by=user,
            status='IN_PROGRESS',
        )
        
        success, message = copy_file_with_progress(source_path, dest_path)
        
        if success:
            # Create new VideoFile record
            new_video, _ = VideoFile.objects.get_or_create(
                number=video_file.number,
                storage_location=destination_storage,
                defaults={
                    'filename': video_file.filename,
                    'file_path': f"{week_folder}/{video_file.filename}",
                    'file_size': video_file.file_size,
                    'duration': video_file.duration,
                    'format': video_file.format,
                    'is_available': True,
                    'checksum': video_file.checksum,
                    # Copy all metadata fields
                    'video_codec': video_file.video_codec,
                    'video_codec_long': video_file.video_codec_long,
                    'video_profile': video_file.video_profile,
                    'video_bitrate': video_file.video_bitrate,
                    'fps': video_file.fps,
                    'width': video_file.width,
                    'height': video_file.height,
                    'aspect_ratio': video_file.aspect_ratio,
                    'pixel_format': video_file.pixel_format,
                    'color_space': video_file.color_space,
                    'color_range': video_file.color_range,
                    'chroma_subsampling': video_file.chroma_subsampling,
                    'audio_codec': video_file.audio_codec,
                    'audio_codec_long': video_file.audio_codec_long,
                    'audio_bitrate': video_file.audio_bitrate,
                    'audio_sample_rate': video_file.audio_sample_rate,
                    'audio_channels': video_file.audio_channels,
                    'audio_channel_layout': video_file.audio_channel_layout,
                    'has_video': video_file.has_video,
                    'has_audio': video_file.has_audio,
                    'total_bitrate': video_file.total_bitrate,
                    'metadata_json': video_file.metadata_json,
                }
            )
            
            operation.status = 'SUCCESS'
            operation.save()
            
            return True, 'Video copied successfully'
        else:
            operation.status = 'FAILED'
            operation.error_message = message
            operation.save()
            
            return False, message
            
    except Exception as e:
        logger.error(f'Error copying video to playout: {str(e)}', exc_info=True)
        return False, str(e)

