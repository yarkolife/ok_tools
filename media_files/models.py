"""Models for media files management."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
import logging


logger = logging.getLogger('django')


ANIMATION_CHOICES = [
    ('none', _('None')),
    ('fade', _('Fade')),
    ('slide_up', _('Slide Up')),
    ('slide_left', _('Slide Left')),
    ('slide_right', _('Slide Right')),
    ('slide_down', _('Slide Down')),
    ('zoom_in', _('Zoom In')),
    ('zoom_out', _('Zoom Out')),
]

OVERLAY_TYPE_CHOICES = [
    ('text', _('Text')),
    ('image', _('Image')),
]

POSITION_PRESET_CHOICES = [
    ('custom', _('Custom')),
    ('center', _('Center')),
    ('top_left', _('Top Left')),
    ('top_center', _('Top Center')),
    ('top_right', _('Top Right')),
    ('bottom_left', _('Bottom Left')),
    ('bottom_center', _('Bottom Center')),
    ('bottom_right', _('Bottom Right')),
    ('lower_third_left', _('Lower Third Left')),
    ('lower_third_right', _('Lower Third Right')),
]


class StorageLocation(models.Model):
    """Model representing a storage location for video files."""

    STORAGE_TYPE_CHOICES = [
        ('ARCHIVE', _('Archive')),
        ('PLAYOUT', _('Playout')),
        ('CUSTOM', _('Custom')),
    ]

    name = models.CharField(
        max_length=255,
        verbose_name=_('Name'),
        help_text=_('Display name for this storage location')
    )
    storage_type = models.CharField(
        max_length=20,
        choices=STORAGE_TYPE_CHOICES,
        default='CUSTOM',
        verbose_name=_('Storage Type'),
    )
    path = models.CharField(
        max_length=500,
        verbose_name=_('Path'),
        help_text=_('Absolute path to the storage directory (e.g., /mnt/archive/)'),
    )
    unc_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('UNC Path'),
        help_text=_('Windows UNC path (e.g., \\\\192.168.88.2\\Share) - optional'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this storage location is currently active'),
    )
    scan_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Scan Enabled'),
        help_text=_('Enable automatic scanning of this location'),
    )
    scan_schedule = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Scan Schedule'),
        help_text=_('Cron-style schedule for automatic scanning (optional)'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )

    class Meta:
        """Meta options for StorageLocation."""

        verbose_name = _('Storage Location')
        verbose_name_plural = _('Storage Locations')
        ordering = ['storage_type', 'name']

    def __str__(self):
        """Return string representation."""
        return f"{self.name} ({self.get_storage_type_display()})"

    def clean(self):
        """Validate the model."""
        if not self.path:
            raise ValidationError({'path': _('Path cannot be empty')})
        
        # Normalize path for comparison (remove trailing slashes, lowercase)
        normalized_path = self.path.rstrip('/').lower()
        
        # Check for duplicate paths (case-insensitive, ignoring trailing slashes)
        # Compare normalized paths
        existing = StorageLocation.objects.exclude(pk=self.pk if self.pk else None)
        for existing_storage in existing:
            existing_normalized = existing_storage.path.rstrip('/').lower()
            if existing_normalized == normalized_path:
                raise ValidationError({
                    'path': _(
                        'A storage location with this path already exists: "{name}" (ID {id}). '
                        'Please use the existing storage location or choose a different path.'
                    ).format(name=existing_storage.name, id=existing_storage.id)
                })

    @property
    def video_count(self):
        """Return count of videos in this storage."""
        return self.videofile_set.count()


class VideoFile(models.Model):
    """Model representing a video file with comprehensive metadata."""

    # Basic information
    number = models.IntegerField(
        verbose_name=_('Number'),
        db_index=True,
        help_text=_('Identification number matching License number (unique per storage location)'),
    )
    filename = models.CharField(
        max_length=500,
        verbose_name=_('Filename'),
    )
    storage_location = models.ForeignKey(
        StorageLocation,
        on_delete=models.PROTECT,
        verbose_name=_('Storage Location'),
    )
    file_path = models.CharField(
        max_length=1000,
        verbose_name=_('File Path'),
        help_text=_('Relative path within the storage location'),
    )
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('File Size (bytes)'),
    )
    duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_('Duration'),
    )
    format = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Format'),
        help_text=_('Container format (mp4, mov, mxf, etc.)'),
    )
    is_available = models.BooleanField(
        default=True,
        verbose_name=_('Available'),
        help_text=_('Whether the file is physically accessible'),
    )
    is_manual_primary = models.BooleanField(
        default=False,
        verbose_name=_('Manual Primary'),
        help_text=_('Manually marked as primary version (overrides automatic selection)'),
    )
    is_preview = models.BooleanField(
        default=False,
        verbose_name=_('Preview version'),
        help_text=_('Short preview clip (e.g. 10s); not a full version, not linked to license'),
    )

    # Relationship with License
    license = models.OneToOneField(
        'licenses.License',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_file',
        verbose_name=_('License'),
    )

    # Tracking
    last_scanned = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Scanned'),
    )
    last_modified = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Modified'),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Checksum (SHA256)'),
    )

    # Video metadata (from ffprobe)
    video_codec = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Video Codec'),
    )
    video_codec_long = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Video Codec (Long)'),
    )
    video_profile = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Video Profile'),
    )
    video_bitrate = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Video Bitrate (bps)'),
    )
    video_bitrate_mode = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('Bitrate Mode'),
    )
    fps = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('FPS'),
    )
    width = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Width'),
    )
    height = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Height'),
    )
    aspect_ratio = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Aspect Ratio'),
    )
    pixel_format = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Pixel Format'),
    )
    color_space = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Color Space'),
    )
    color_range = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Color Range'),
    )
    chroma_subsampling = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Chroma Subsampling'),
    )

    # Audio metadata
    audio_codec = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Audio Codec'),
    )
    audio_codec_long = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Audio Codec (Long)'),
    )
    audio_bitrate = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Audio Bitrate (bps)'),
    )
    audio_sample_rate = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Audio Sample Rate (Hz)'),
    )
    audio_channels = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Audio Channels'),
    )
    audio_channel_layout = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Audio Channel Layout'),
    )

    # Additional fields
    has_video = models.BooleanField(
        default=True,
        verbose_name=_('Has Video'),
    )
    has_audio = models.BooleanField(
        default=True,
        verbose_name=_('Has Audio'),
    )
    total_bitrate = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Total Bitrate (bps)'),
    )
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Full Metadata (JSON)'),
        help_text=_('Complete ffprobe output for extensibility'),
    )
    thumbnail = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Thumbnail Path'),
        help_text=_('Path to preview image'),
    )

    created_at = models.DateTimeField(
        _('Created at'),
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for VideoFile."""

        verbose_name = _('Video File')
        verbose_name_plural = _('Video Files')
        ordering = ['-created_at']
        # Allow multiple files with same number in same storage (different paths/versions)
        # Uniqueness is ensured by (number, storage_location, file_path)
        unique_together = [('number', 'storage_location', 'file_path')]
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['storage_location', 'is_available']),
            models.Index(fields=['number', 'storage_location']),  # For duplicate detection
        ]

    def __str__(self):
        """Return string representation."""
        return f"{self.number} - {self.filename}"

    @property
    def full_path(self):
        """Return absolute file path."""
        from pathlib import Path
        return str(Path(self.storage_location.path) / self.file_path)

    @property
    def unc_path(self):
        """Return Windows UNC path if configured."""
        if self.storage_location.unc_path:
            # Replace forward slashes with backslashes for Windows
            relative_path = self.file_path.replace('/', '\\')
            # Combine UNC base with relative path
            return f"{self.storage_location.unc_path}\\{relative_path}"
        return None

    @property
    def resolution_display(self):
        """Return formatted resolution string."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "-"

    @property
    def file_size_mb(self):
        """Return file size in MB."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None

    @property
    def bitrate_mbps(self):
        """Return total bitrate in Mbps."""
        if self.total_bitrate:
            return round(self.total_bitrate / 1_000_000, 2)
        return None

    def get_license(self):
        """Get associated license if exists."""
        from licenses.models import License
        if self.license:
            return self.license
        try:
            return License.objects.get(number=self.number)
        except License.DoesNotExist:
            return None

    def _versions_queryset(self):
        """Base queryset for versioning: same number, exclude preview clips."""
        return VideoFile.objects.filter(number=self.number).exclude(is_preview=True)

    @property
    def has_duplicates(self):
        """Check if there are other (non-preview) versions with same number."""
        return self._versions_queryset().exclude(id=self.id).exists()

    @property
    def duplicate_count(self):
        """Count of other (non-preview) versions."""
        return self._versions_queryset().exclude(id=self.id).count()

    def get_all_versions(self):
        """Get all full versions of this video (including self); excludes preview clips."""
        return self._versions_queryset().order_by('-total_bitrate', '-created_at')

    def is_primary_version(self):
        """Check if this is the primary (best quality) version."""
        versions = self.get_all_versions()
        if not versions:
            return True
        
        # Check if any version is manually marked as primary
        manual_primary = versions.filter(is_manual_primary=True).first()
        if manual_primary:
            return manual_primary.id == self.id
        
        # Priority: availability > quality (bitrate + storage) > recency
        # For CUSTOM storage: prefer newer versions if bitrate is not significantly lower
        # (re-rendered versions should become primary)
        
        # Pre-compute values needed for all versions to avoid redundant queries
        all_versions_list = list(versions)
        all_custom = all(
            v.storage_location and v.storage_location.storage_type == 'CUSTOM'
            for v in all_versions_list
        )
        max_bitrate = max((v.total_bitrate or 0 for v in all_versions_list), default=0)
        
        def get_sort_key(v):
            # Always return a tuple of the same structure with comparable types
            # Structure: (is_available: bool, primary_metric_1: int, primary_metric_2: int, created_ts: float)
            
            is_available = bool(v.is_available)
            
            # Determine which metric to use based on storage types
            if all_custom:
                v_bitrate = v.total_bitrate or 0
                if max_bitrate > 0 and v_bitrate >= max_bitrate * 0.8:
                    # For CUSTOM: prefer newer if bitrate is >= 80% of max
                    # primary_metric_1 = recency (higher is newer)
                    # primary_metric_2 = quality as tie-breaker
                    created_ts = self._get_created_timestamp(v)
                    return (
                        is_available,
                        created_ts,  # Recency first for CUSTOM with acceptable quality
                        v_bitrate,   # Quality as tie-breaker
                    )
            
            # Default: quality first, then recency
            # primary_metric_1 = quality score (higher is better)
            # primary_metric_2 = recency (higher is newer)
            quality_score = int(v.get_quality_score() or 0)
            created_ts = self._get_created_timestamp(v)
            return (
                is_available,
                quality_score,
                created_ts,
            )
        
        best = max(all_versions_list, key=get_sort_key)
        
        return best.id == self.id
    
    def _get_created_timestamp(self, v):
        """Get creation timestamp as float for safe comparison."""
        from datetime import datetime, timezone
        created = v.created_at or v.last_scanned or v.updated_at
        if created is None:
            # Use epoch timestamp for null dates
            return 0.0
        # Convert to epoch seconds (timezone-aware datetime assumed)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created.timestamp()

    def get_quality_score(self):
        """Calculate quality score for comparison."""
        storage_priority = {'ARCHIVE': 1000000000, 'PLAYOUT': 500000000, 'CUSTOM': 0}
        return (
            storage_priority.get(self.storage_location.storage_type, 0) +
            (self.total_bitrate or 0)
        )

    # Codecs not supported by most browsers (Chrome, Firefox, Edge without extensions)
    BROWSER_INCOMPATIBLE_VIDEO_CODECS = ['hevc', 'h265', 'hev1', 'hvc1', 'av1']
    # Codecs supported by all modern browsers
    BROWSER_COMPATIBLE_VIDEO_CODECS = ['h264', 'avc1', 'avc', 'vp8', 'vp9']

    @property
    def is_browser_compatible(self):
        """
        Check if video codec is supported by most browsers.
        
        HEVC/H.265 is NOT supported by Chrome, Firefox, and Edge (without extension).
        Only Safari has native HEVC support.
        
        Returns:
            bool: True if codec is supported by most browsers
        """
        if not self.video_codec:
            return True  # Assume compatible if unknown
        
        codec_lower = self.video_codec.lower()
        
        # Check for incompatible codecs
        for incompatible in self.BROWSER_INCOMPATIBLE_VIDEO_CODECS:
            if incompatible in codec_lower:
                return False
        
        return True

    @property
    def browser_compatibility_message(self):
        """
        Return a user-friendly message about browser compatibility.
        
        Returns:
            str or None: Warning message if incompatible, None if compatible
        """
        if self.is_browser_compatible:
            return None
        
        codec_display = self.video_codec_long or self.video_codec or 'Unknown'
        
        if 'hevc' in self.video_codec.lower() or 'h265' in self.video_codec.lower():
            return _(
                'This video uses H.265/HEVC codec which is not supported by Chrome, Firefox, '
                'and Edge. Only audio will play. Use Safari, or transcode to H.264.'
            )
        
        return _(
            f'This video uses {codec_display} codec which may not be supported by your browser. '
            'Consider transcoding to H.264 for better compatibility.'
        )


class FileOperation(models.Model):
    """Model representing file operations history."""

    OPERATION_TYPE_CHOICES = [
        ('SCAN', _('Scan')),
        ('COPY', _('Copy')),
        ('MOVE', _('Move')),
        ('DELETE', _('Delete')),
        ('METADATA_UPDATE', _('Metadata Update')),
        ('VERIFY', _('Verify Integrity')),
        ('RENDER', _('Render')),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', _('Success')),
        ('FAILED', _('Failed')),
        ('IN_PROGRESS', _('In Progress')),
    ]

    video_file = models.ForeignKey(
        VideoFile,
        on_delete=models.CASCADE,
        related_name='operations',
        verbose_name=_('Video File'),
    )
    operation_type = models.CharField(
        max_length=20,
        choices=OPERATION_TYPE_CHOICES,
        verbose_name=_('Operation Type'),
    )
    source_location = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_operations',
        verbose_name=_('Source Location'),
    )
    destination_location = models.ForeignKey(
        StorageLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='destination_operations',
        verbose_name=_('Destination Location'),
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Performed By'),
    )
    performed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Performed At'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='IN_PROGRESS',
        verbose_name=_('Status'),
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message'),
    )
    details = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Details'),
        help_text=_('Additional operation details'),
    )

    class Meta:
        """Meta options for FileOperation."""

        verbose_name = _('File Operation')
        verbose_name_plural = _('File Operations')
        ordering = ['-performed_at']

    def __str__(self):
        """Return string representation."""
        return f"{self.get_operation_type_display()} - {self.video_file} ({self.get_status_display()})"


class MediaFilesConfig(models.Model):
    """Configuration for media files module (singleton)."""
    
    # Enable optional video rendering features (ffmpeg presets)
    # Includes a video editor for adding text overlays at the beginning and end of videos:
    # Title, subtitle, author, channel, year
    overlay_rendering_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Overlay Rendering Enabled'),
        help_text=_('Enable video overlay rendering features (text overlays)')
    )
    
    # Auto-copy configuration for planning module
    auto_copy_on_schedule = models.BooleanField(
        default=False,
        verbose_name=_('Auto Copy on Schedule'),
        help_text=_('Automatically copy videos when saving broadcast plans')
    )
    
    auto_copy_to_archive = models.BooleanField(
        default=False,
        verbose_name=_('Auto Copy to Archive'),
        help_text=_('Automatically copy videos to archive storage when planning')
    )
    
    auto_copy_to_playout = models.BooleanField(
        default=False,
        verbose_name=_('Auto Copy to Playout'),
        help_text=_('Automatically copy videos to playout storage when planning')
    )
    
    # Use weekly folders (YYYY_KW_WW format) in playout storage
    use_weekly_folders = models.BooleanField(
        default=True,
        verbose_name=_('Use Weekly Folders'),
        help_text=_('Use weekly folders (YYYY_KW_WW format) in playout storage')
    )
    
    # Protect ARCHIVE storage from deletion
    archive_protected = models.BooleanField(
        default=True,
        verbose_name=_('Archive Protected'),
        help_text=_('Protect ARCHIVE storage from deletion (read-only access)')
    )
    
    # Number of days to consider CUSTOM storage files as "recent"
    # Recent CUSTOM files are preferred over ARCHIVE when selecting source
    source_preference_custom_days = models.IntegerField(
        default=7,
        verbose_name=_('Source Preference Custom Days'),
        help_text=_('Number of days to consider CUSTOM storage files as "recent"')
    )
    
    # Default playout storage for main broadcasts
    # If not set, auto-detects storage containing "000_Sendungen" in path or "Sendungen" in name
    default_playout_storage_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Default Playout Storage Name'),
        help_text=_('Default playout storage name (auto-detected if empty)')
    )
    
    default_playout_storage_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Default Playout Storage Path'),
        help_text=_('Default playout storage path (auto-detected if empty)')
    )
    
    # Auto-delete videos from CUSTOM storage after successful copy to archive and playout
    auto_delete_from_custom = models.BooleanField(
        default=True,
        verbose_name=_('Auto Delete from Custom'),
        help_text=_('Auto-delete videos from CUSTOM storage after successful copy')
    )
    
    # Verify checksum during video copy operations
    copy_verify_checksum = models.BooleanField(
        default=True,
        verbose_name=_('Copy Verify Checksum'),
        help_text=_('Verify checksum during video copy operations (SHA256)')
    )
    
    # Use faster MD5 checksum for ARCHIVE sources instead of SHA256
    copy_use_md5_for_archive = models.BooleanField(
        default=True,
        verbose_name=_('Copy Use MD5 for Archive'),
        help_text=_('Use faster MD5 checksum for ARCHIVE sources instead of SHA256')
    )
    
    # Supported video formats for file scanning
    supported_formats = models.CharField(
        max_length=200,
        default='mp4,mov,mpeg,mpg',
        verbose_name=_('Supported Video Formats'),
        help_text=_('Comma-separated list of supported video file extensions (e.g., mp4,mov,mpeg,mpg)')
    )
    
    # Auto-transcode HEVC/H.265 videos to H.264 for browser compatibility
    auto_transcode_hevc = models.BooleanField(
        default=False,
        verbose_name=_('Auto Transcode HEVC'),
        help_text=_('Automatically transcode HEVC/H.265 videos to H.264 for browser playback compatibility')
    )
    
    # Default encoding preset for transcoding (e.g., "1080p25_9000k")
    transcode_encode_preset = models.CharField(
        max_length=100,
        default='1080p25_9000k',
        blank=True,
        verbose_name=_('Transcode Encoding Preset'),
        help_text=_('Default encoding preset for transcoding (e.g., "1080p25_9000k")')
    )
    
    class Meta:
        verbose_name = _('Media Files Configuration')
        verbose_name_plural = _('Media Files Configuration')
    
    def __str__(self):
        """Return string representation."""
        return str(_("Media Files Configuration"))
    
    def save(self, *args, **kwargs):
        """Ensure only one config instance exists."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

