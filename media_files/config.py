"""Configuration helpers for media_files module with env fallbacks."""

import os
from django.conf import settings


def get_video_overlay_rendering_enabled():
    """Get whether video overlay rendering is enabled."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.overlay_rendering_enabled
    except Exception:
        # Fallback to env variable for backward compatibility
        value = os.getenv('VIDEO_OVERLAY_RENDERING_ENABLED', 'false')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_auto_copy_on_schedule():
    """Get whether to auto-copy videos on schedule."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.auto_copy_on_schedule
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_AUTO_COPY_ON_SCHEDULE', 'false')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_auto_copy_to_archive():
    """Get whether to auto-copy videos to archive."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.auto_copy_to_archive
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_AUTO_COPY_TO_ARCHIVE', 'false')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_auto_copy_to_playout():
    """Get whether to auto-copy videos to playout."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.auto_copy_to_playout
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_AUTO_COPY_TO_PLAYOUT', 'false')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_use_weekly_folders():
    """Get whether to use weekly folders in playout storage."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.use_weekly_folders
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_USE_WEEKLY_FOLDERS', 'true')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_archive_protected():
    """Get whether archive storage is protected."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.archive_protected
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_ARCHIVE_PROTECTED', 'true')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_source_preference_custom_days():
    """Get number of days to consider CUSTOM storage files as recent."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.source_preference_custom_days
    except Exception:
        # Fallback to env variable
        try:
            return int(os.getenv('VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS', '7'))
        except ValueError:
            return 7


def get_video_default_playout_storage_name():
    """Get default playout storage name."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        if config.default_playout_storage_name:
            return config.default_playout_storage_name
    except Exception:
        pass
    
    # Fallback to env variable
    return os.getenv('VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME', '')


def get_video_default_playout_storage_path():
    """Get default playout storage path."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        if config.default_playout_storage_path:
            return config.default_playout_storage_path
    except Exception:
        pass
    
    # Fallback to env variable
    return os.getenv('VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH', '')


def get_video_auto_delete_from_custom():
    """Get whether to auto-delete from CUSTOM storage after copy."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.auto_delete_from_custom
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_AUTO_DELETE_FROM_CUSTOM', 'true')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_copy_verify_checksum():
    """Get whether to verify checksum during copy."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.copy_verify_checksum
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_COPY_VERIFY_CHECKSUM', 'true')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_copy_use_md5_for_archive():
    """Get whether to use MD5 checksum for ARCHIVE sources."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.copy_use_md5_for_archive
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_COPY_USE_MD5_FOR_ARCHIVE', 'true')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_video_supported_formats():
    """Get list of supported video formats."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        formats_str = config.supported_formats
        if formats_str:
            return [fmt.strip() for fmt in formats_str.split(',') if fmt.strip()]
    except Exception:
        pass
    
    # Fallback to env variable
    env_value = os.getenv('VIDEO_SUPPORTED_FORMATS', 'mp4,mov,mpeg,mpg')
    return [fmt.strip() for fmt in env_value.split(',') if fmt.strip()]


def get_auto_transcode_hevc():
    """Get whether to auto-transcode HEVC videos to H.264."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        return config.auto_transcode_hevc
    except Exception:
        # Fallback to env variable
        value = os.getenv('VIDEO_AUTO_TRANSCODE_HEVC', 'false')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_transcode_encode_preset():
    """Get default encoding preset for transcoding."""
    try:
        from .models import MediaFilesConfig
        config = MediaFilesConfig.get_config()
        if config.transcode_encode_preset:
            return config.transcode_encode_preset
    except Exception:
        pass
    
    # Fallback to env variable
    return os.getenv('VIDEO_TRANSCODE_ENCODE_PRESET', '1080p25_9000k')
