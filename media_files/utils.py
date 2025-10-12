"""Utility functions for media files management."""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from django.utils import timezone


logger = logging.getLogger('django')


def extract_number_from_filename(filename: str) -> Optional[int]:
    """
    Extract license number from filename.
    
    Expected format: <number>_<rest_of_filename>.ext
    Example: 12345_my_video.mp4 -> 12345
    
    Args:
        filename: The filename to parse
        
    Returns:
        License number or None if not found
    """
    match = re.match(r'^(\d+)_', filename)
    if match:
        return int(match.group(1))
    return None


def scan_directory(storage_location, supported_formats=None) -> list:
    """
    Scan directory for video files.
    
    Args:
        storage_location: StorageLocation instance
        supported_formats: List of supported file extensions (e.g., ['mp4', 'mov'])
        
    Returns:
        List of tuples: (filename, relative_path, absolute_path)
    """
    if supported_formats is None:
        from django.conf import settings
        supported_formats = getattr(settings, 'VIDEO_SUPPORTED_FORMATS', ['mp4', 'mov', 'mpeg', 'mpg'])
    
    base_path = Path(storage_location.path)
    
    if not base_path.exists():
        logger.error(f"Storage path does not exist: {base_path}")
        return []
    
    found_files = []
    
    # Walk through all directories
    for root, dirs, files in os.walk(base_path):
        for file in files:
            # Check if file has supported extension
            ext = file.rsplit('.', 1)[-1].lower() if '.' in file else ''
            if ext in supported_formats:
                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(base_path)
                found_files.append((file, str(rel_path), str(abs_path)))
    
    logger.info(f"Found {len(found_files)} video files in {storage_location.name}")
    return found_files


def extract_video_metadata(file_path: str) -> Dict:
    """
    Extract comprehensive video metadata using ffprobe.
    
    Args:
        file_path: Absolute path to the video file
        
    Returns:
        Dictionary with extracted metadata
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    metadata = {
        'has_video': False,
        'has_audio': False,
    }
    
    try:
        # Run ffprobe to get JSON output
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"ffprobe failed for {file_path}: {result.stderr}")
            return metadata
        
        data = json.loads(result.stdout)
        metadata['raw_json'] = data
        
        # Extract format information
        if 'format' in data:
            fmt = data['format']
            # Get format from ffprobe
            ffprobe_format = fmt.get('format_name', '').split(',')[0]
            
            # Determine format based on file extension, not ffprobe
            file_extension = os.path.splitext(file_path)[1].lower()
            extension_formats = {
                '.mp4': 'mp4',
                '.mov': 'mov', 
                '.mpeg': 'mpeg',
                '.mpg': 'mpeg',
                '.avi': 'avi',
                '.mkv': 'mkv',
                '.webm': 'webm',
            }
            
            # Use file extension format if available, otherwise use ffprobe format
            metadata['format'] = extension_formats.get(file_extension, ffprobe_format)
            metadata['file_size'] = int(fmt.get('size', 0))
            metadata['total_bitrate'] = int(fmt.get('bit_rate', 0))
            
            # Duration
            duration_seconds = float(fmt.get('duration', 0))
            if duration_seconds > 0:
                metadata['duration'] = timedelta(seconds=duration_seconds)
        
        # Extract stream information
        if 'streams' in data:
            for stream in data['streams']:
                codec_type = stream.get('codec_type')
                
                if codec_type == 'video':
                    metadata['has_video'] = True
                    metadata['video_codec'] = stream.get('codec_name', '')
                    metadata['video_codec_long'] = stream.get('codec_long_name', '')
                    metadata['video_profile'] = stream.get('profile', '')
                    metadata['video_bitrate'] = int(stream.get('bit_rate', 0))
                    metadata['width'] = stream.get('width')
                    metadata['height'] = stream.get('height')
                    metadata['pixel_format'] = stream.get('pix_fmt', '')
                    metadata['color_space'] = stream.get('color_space', '')
                    metadata['color_range'] = stream.get('color_range', '')
                    
                    # FPS calculation
                    if 'r_frame_rate' in stream:
                        try:
                            num, den = map(int, stream['r_frame_rate'].split('/'))
                            if den != 0:
                                metadata['fps'] = round(num / den, 2)
                        except (ValueError, ZeroDivisionError):
                            pass
                    
                    # Aspect ratio
                    if 'display_aspect_ratio' in stream:
                        metadata['aspect_ratio'] = stream['display_aspect_ratio']
                    elif metadata['width'] and metadata['height']:
                        from math import gcd
                        g = gcd(metadata['width'], metadata['height'])
                        metadata['aspect_ratio'] = f"{metadata['width']//g}:{metadata['height']//g}"
                    
                    # Chroma subsampling from pixel format
                    pix_fmt = metadata['pixel_format']
                    if 'yuv420' in pix_fmt:
                        metadata['chroma_subsampling'] = '4:2:0'
                    elif 'yuv422' in pix_fmt:
                        metadata['chroma_subsampling'] = '4:2:2'
                    elif 'yuv444' in pix_fmt:
                        metadata['chroma_subsampling'] = '4:4:4'
                
                elif codec_type == 'audio':
                    metadata['has_audio'] = True
                    metadata['audio_codec'] = stream.get('codec_name', '')
                    metadata['audio_codec_long'] = stream.get('codec_long_name', '')
                    metadata['audio_bitrate'] = int(stream.get('bit_rate', 0))
                    metadata['audio_sample_rate'] = stream.get('sample_rate')
                    metadata['audio_channels'] = stream.get('channels')
                    metadata['audio_channel_layout'] = stream.get('channel_layout', '')
        
        logger.debug(f"Successfully extracted metadata for {file_path}")
        
    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe timeout for {file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ffprobe output for {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error extracting metadata for {file_path}: {e}")
    
    return metadata


def calculate_checksum(file_path: str, algorithm='sha256') -> str:
    """
    Calculate file checksum.
    
    Args:
        file_path: Absolute path to the file
        algorithm: Hash algorithm ('sha256' or 'md5')
        
    Returns:
        Hexadecimal checksum string
    """
    if algorithm == 'sha256':
        hasher = hashlib.sha256()
    elif algorithm == 'md5':
        hasher = hashlib.md5()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    try:
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating checksum for {file_path}: {e}")
        return ''


def copy_file_with_progress(source: str, destination: str, verify_checksum=True) -> Tuple[bool, str]:
    """
    Copy file with progress logging and optional integrity verification.
    
    Args:
        source: Source file path
        destination: Destination file path
        verify_checksum: Whether to verify checksum after copy
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Ensure destination directory exists
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get file size for progress reporting
        file_size = os.path.getsize(source)
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"Copying {source} to {destination} ({file_size_mb:.2f} MB)")
        
        # Calculate source checksum if verification is enabled
        source_checksum = None
        if verify_checksum:
            logger.debug("Calculating source checksum...")
            source_checksum = calculate_checksum(source)
        
        # Copy the file
        shutil.copy2(source, destination)
        
        # Verify checksum
        if verify_checksum and source_checksum:
            logger.debug("Verifying destination checksum...")
            dest_checksum = calculate_checksum(destination)
            if source_checksum != dest_checksum:
                os.remove(destination)
                error_msg = "Checksum mismatch - file may be corrupted"
                logger.error(error_msg)
                return False, error_msg
        
        logger.info(f"Successfully copied file to {destination}")
        return True, "File copied successfully"
        
    except Exception as e:
        error_msg = f"Error copying file: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def verify_file_integrity(video_file) -> Tuple[bool, str]:
    """
    Verify file integrity by comparing stored checksum with current file.
    
    Args:
        video_file: VideoFile model instance
        
    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    if not video_file.checksum:
        return False, "No checksum stored for comparison"
    
    full_path = video_file.full_path
    
    if not os.path.exists(full_path):
        return False, "File not found"
    
    try:
        current_checksum = calculate_checksum(full_path)
        
        if current_checksum == video_file.checksum:
            return True, "File integrity verified"
        else:
            return False, "Checksum mismatch - file may be corrupted"
            
    except Exception as e:
        return False, f"Error verifying integrity: {str(e)}"


def generate_thumbnail(file_path: str, output_path: str, timestamp='00:00:05') -> bool:
    """
    Generate thumbnail image from video.
    
    Args:
        file_path: Path to video file
        output_path: Path for output thumbnail
        timestamp: Time position for thumbnail (format: HH:MM:SS)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-ss', timestamp,
            '-i', file_path,
            '-vframes', '1',
            '-q:v', '2',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"Generated thumbnail: {output_path}")
            return True
        else:
            logger.error(f"Failed to generate thumbnail: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        return False


def get_file_modified_time(file_path: str) -> Optional[datetime]:
    """
    Get file modification time as timezone-aware datetime.
    
    Args:
        file_path: Path to file
        
    Returns:
        Datetime object or None
    """
    try:
        mtime = os.path.getmtime(file_path)
        return timezone.make_aware(datetime.fromtimestamp(mtime))
    except Exception as e:
        logger.error(f"Error getting file mtime: {e}")
        return None


def check_duplicate_before_copy(source_video, destination_storage):
    """
    Check if copying would create a duplicate.
    
    Args:
        source_video: VideoFile instance to copy
        destination_storage: StorageLocation where to copy
        
    Returns:
        Tuple of (is_duplicate: bool, existing_video: VideoFile or None, message: str)
    """
    from .models import VideoFile
    
    existing = VideoFile.objects.filter(
        number=source_video.number,
        storage_location=destination_storage,
        is_available=True
    ).first()
    
    if not existing:
        return False, None, "No duplicate"
    
    # Check if files are identical by checksum
    if source_video.checksum and existing.checksum:
        if source_video.checksum == existing.checksum:
            return True, existing, "Identical file already exists (same checksum)"
        else:
            return True, existing, "Different file with same number exists (different checksum)"
    
    # Compare by size if no checksum
    if source_video.file_size == existing.file_size:
        return True, existing, "File with same size already exists"
    
    return True, existing, "File with same number but different characteristics exists"


def has_system_attributes(file_path):
    """
    Check if file has hidden/system attributes (Windows) or special permissions (Linux).
    
    Args:
        file_path: Path to file
        
    Returns:
        bool: True if file has system attributes, False otherwise
    """
    import stat
    
    try:
        if os.name == 'nt':  # Windows
            # On Windows, check for hidden/system attributes
            attrs = os.stat(file_path).st_file_attributes
            return bool(attrs & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))
        else:  # Linux/Unix
            # On Linux, check for special permissions or attributes
            file_stat = os.stat(file_path)
            # Check if file has special permissions (e.g., +x, setuid, setgid)
            mode = file_stat.st_mode
            # Check for system files (owned by root, etc.)
            return bool(mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX))
    except (OSError, AttributeError):
        # If we can't determine attributes, assume no special attributes
        return False


def is_file_in_use(file_path):
    """
    Check if file is currently in use (locked by another process).
    
    Args:
        file_path: Path to file
        
    Returns:
        bool: True if file is in use, False otherwise
    """
    try:
        if os.name == 'nt':  # Windows
            # Try to open file in exclusive mode
            with open(file_path, 'r+b') as f:
                pass
            return False
        else:  # Linux/Unix
            # Use lsof to check if file is open
            import subprocess
            result = subprocess.run(
                ['lsof', file_path], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # If we can't determine, assume file is not in use
        return False


def move_video_to_archive(video_file, archive_storage=None, user=None):
    """
    Move video from playout to archive storage.
    
    Args:
        video_file: VideoFile instance to move
        archive_storage: Archive StorageLocation (optional, auto-detect if None)
        user: User performing the operation (optional)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    from .models import StorageLocation, FileOperation
    
    if not archive_storage:
        archive_storage = StorageLocation.objects.filter(
            storage_type='ARCHIVE',
            is_active=True
        ).first()
        
        if not archive_storage:
            return False, 'No ARCHIVE storage configured'
    
    # Check if file has system attributes (still in use)
    if has_system_attributes(video_file.full_path):
        return False, 'File has system attributes - still in use by playout system'
    
    # Check if file is locked
    if is_file_in_use(video_file.full_path):
        return False, 'File is currently in use - cannot move'
    
    try:
        source_path = video_file.full_path
        dest_path = f"{archive_storage.path.rstrip('/')}/{video_file.filename}"
        
        # Create operation record
        operation = FileOperation.objects.create(
            video_file=video_file,
            operation_type='MOVE',
            source_location=video_file.storage_location,
            destination_location=archive_storage,
            performed_by=user,
            status='IN_PROGRESS',
        )
        
        # Ensure destination directory exists
        dest_dir = os.path.dirname(dest_path)
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        
        # Move the file
        shutil.move(source_path, dest_path)
        
        # Update VideoFile record
        video_file.storage_location = archive_storage
        video_file.file_path = video_file.filename
        video_file.save(update_fields=['storage_location', 'file_path'])
        
        operation.status = 'SUCCESS'
        operation.save()
        
        logger.info(f'Moved video {video_file.number} from playout to archive')
        return True, 'Video moved to archive successfully'
        
    except Exception as e:
        error_msg = f'Error moving video to archive: {str(e)}'
        logger.error(error_msg, exc_info=True)
        
        if 'operation' in locals():
            operation.status = 'FAILED'
            operation.error_message = error_msg
            operation.save()
        
        return False, error_msg

