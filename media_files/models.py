"""Models for media files management."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
import logging


logger = logging.getLogger('django')


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    @property
    def video_count(self):
        """Return count of videos in this storage."""
        return self.videofile_set.count()


class VideoFile(models.Model):
    """Model representing a video file with comprehensive metadata."""

    # Basic information
    number = models.IntegerField(
        verbose_name=_('Number'),
        unique=True,
        db_index=True,
        help_text=_('Unique identification number matching License number'),
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for VideoFile."""

        verbose_name = _('Video File')
        verbose_name_plural = _('Video Files')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['storage_location', 'is_available']),
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

    @property
    def has_duplicates(self):
        """Check if there are other versions with same number."""
        return VideoFile.objects.filter(number=self.number).exclude(id=self.id).exists()

    @property
    def duplicate_count(self):
        """Count of other versions."""
        return VideoFile.objects.filter(number=self.number).exclude(id=self.id).count()

    def get_all_versions(self):
        """Get all versions of this video (including self)."""
        return VideoFile.objects.filter(number=self.number).order_by('-total_bitrate', '-created_at')

    def is_primary_version(self):
        """Check if this is the primary (best quality) version."""
        versions = self.get_all_versions()
        if not versions:
            return True
        
        # Priority: ARCHIVE > PLAYOUT > CUSTOM
        storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
        
        best = max(versions, key=lambda v: (
            storage_priority.get(v.storage_location.storage_type, 0),
            v.total_bitrate or 0,
            v.created_at
        ))
        
        return best.id == self.id

    def get_quality_score(self):
        """Calculate quality score for comparison."""
        storage_priority = {'ARCHIVE': 1000000000, 'PLAYOUT': 500000000, 'CUSTOM': 0}
        return (
            storage_priority.get(self.storage_location.storage_type, 0) +
            (self.total_bitrate or 0)
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

