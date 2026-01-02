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
        
        # Check if any version is manually marked as primary
        manual_primary = versions.filter(is_manual_primary=True).first()
        if manual_primary:
            return manual_primary.id == self.id
        
        # Priority: date > bitrate > storage (ARCHIVE > PLAYOUT > CUSTOM)
        storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
        
        best = max(versions, key=lambda v: (
            v.created_at,
            v.total_bitrate or 0,
            storage_priority.get(v.storage_location.storage_type, 0)
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


class VideoPreset(models.Model):
    """Model representing a custom video rendering preset."""

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Preset Name'),
        help_text=_('Unique name for this preset (e.g., "my_custom_lower_third")'),
    )
    display_name = models.CharField(
        max_length=255,
        verbose_name=_('Display Name'),
        help_text=_('Human-readable name shown in UI'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Optional description of this preset'),
    )
    
    # Preset type
    is_template = models.BooleanField(
        default=False,
        verbose_name=_('Is Template'),
        help_text=_('If true, this preset serves as a starting template for new presets'),
    )
    
    # Based on existing preset
    based_on = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Based On'),
        help_text=_('Original preset this was copied from'),
    )
    
    # Rendering settings
    segment_duration = models.FloatField(
        default=5.0,
        verbose_name=_('Segment Duration (seconds)'),
        help_text=_('Duration for intro/outro overlay segments'),
    )
    intro_clip_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Intro Clip Path'),
        help_text=_('Optional path to intro video clip'),
    )
    outro_clip_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Outro Clip Path'),
        help_text=_('Optional path to outro video clip'),
    )
    
    # Ownership
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_presets',
        verbose_name=_('Created By'),
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_('Public'),
        help_text=_('If true, this preset is available to all users'),
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for VideoPreset."""

        verbose_name = _('Video Preset')
        verbose_name_plural = _('Video Presets')
        ordering = ['display_name']

    def __str__(self):
        """Return string representation."""
        return self.display_name

    def to_json_preset(self):
        """Export preset to JSON format compatible with rendering system."""
        intro_overlays = []
        outro_overlays = []
        
        for overlay in self.overlays.filter(segment='intro').order_by('order'):
            intro_overlays.append(overlay.to_dict())
        
        for overlay in self.overlays.filter(segment='outro').order_by('order'):
            outro_overlays.append(overlay.to_dict())
        
        return {
            'name': self.name,
            'intro_clip': self.intro_clip_path or None,
            'outro_clip': self.outro_clip_path or None,
            'segment_duration': self.segment_duration,
            'overlays': {
                'intro': intro_overlays,
                'outro': outro_overlays,
            }
        }


class PresetOverlay(models.Model):
    """Model representing an individual overlay element in a preset."""

    SEGMENT_CHOICES = [
        ('intro', _('Intro')),
        ('outro', _('Outro')),
    ]

    preset = models.ForeignKey(
        VideoPreset,
        on_delete=models.CASCADE,
        related_name='overlays',
        verbose_name=_('Preset'),
    )
    
    # Overlay type and content
    overlay_type = models.CharField(
        max_length=20,
        choices=OVERLAY_TYPE_CHOICES,
        default='text',
        verbose_name=_('Type'),
    )
    segment = models.CharField(
        max_length=10,
        choices=SEGMENT_CHOICES,
        default='intro',
        verbose_name=_('Segment'),
        help_text=_('Apply this overlay to intro or outro segment'),
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Rendering order (lower number = rendered first/bottom layer)'),
    )
    
    # Text overlay settings
    text_template = models.TextField(
        blank=True,
        verbose_name=_('Text Template'),
        help_text=_('Template with variables like {license.title}, {profile.display}'),
    )
    
    # Image overlay settings
    image_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Image Path'),
        help_text=_('Path to image file (relative to assets/ or absolute)'),
    )
    image_width = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Image Width'),
    )
    image_height = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Image Height'),
    )
    
    # Position
    position_preset = models.CharField(
        max_length=30,
        choices=POSITION_PRESET_CHOICES,
        default='custom',
        verbose_name=_('Position Preset'),
    )
    x_position = models.CharField(
        max_length=100,
        default='(w-text_w)/2',
        verbose_name=_('X Position'),
        help_text=_('X coordinate or expression (e.g., "(w-text_w)/2", "40")'),
    )
    y_position = models.CharField(
        max_length=100,
        default='(h-text_h)/2',
        verbose_name=_('Y Position'),
        help_text=_('Y coordinate or expression (e.g., "h-140", "(h-text_h)/2")'),
    )
    
    # Timing
    start_time = models.FloatField(
        default=0.0,
        verbose_name=_('Start Time (seconds)'),
        help_text=_('When to show this overlay (relative to segment start)'),
    )
    end_time = models.FloatField(
        default=5.0,
        verbose_name=_('End Time (seconds)'),
        help_text=_('When to hide this overlay (relative to segment start)'),
    )
    
    # Animation
    animation = models.CharField(
        max_length=20,
        choices=ANIMATION_CHOICES,
        default='fade',
        verbose_name=_('Animation'),
    )
    fade_in_duration = models.FloatField(
        default=0.4,
        verbose_name=_('Fade In Duration (seconds)'),
    )
    fade_out_duration = models.FloatField(
        default=0.4,
        verbose_name=_('Fade Out Duration (seconds)'),
    )
    
    # Text styling
    font_file = models.CharField(
        max_length=500,
        default='fonts/Roboto-Regular.ttf',
        verbose_name=_('Font File'),
        help_text=_('Path relative to assets/ (e.g., "fonts/Roboto-Bold.ttf")'),
    )
    font_size = models.IntegerField(
        default=48,
        verbose_name=_('Font Size'),
    )
    font_color = models.CharField(
        max_length=50,
        default='white',
        verbose_name=_('Font Color'),
        help_text=_('Color name or hex (e.g., "white", "#FFFFFF")'),
    )
    
    # Text box
    has_box = models.BooleanField(
        default=False,
        verbose_name=_('Has Background Box'),
    )
    box_color = models.CharField(
        max_length=50,
        default='black@0.5',
        verbose_name=_('Box Color'),
        help_text=_('Color with opacity (e.g., "black@0.5")'),
    )
    box_border_width = models.IntegerField(
        default=12,
        verbose_name=_('Box Border Width'),
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for PresetOverlay."""

        verbose_name = _('Preset Overlay')
        verbose_name_plural = _('Preset Overlays')
        ordering = ['preset', 'segment', 'order']

    def __str__(self):
        """Return string representation."""
        if self.overlay_type == 'text':
            preview = self.text_template[:50] + '...' if len(self.text_template) > 50 else self.text_template
            return f"{self.get_segment_display()} - Text: {preview}"
        else:
            return f"{self.get_segment_display()} - Image: {self.image_path}"

    def to_dict(self):
        """Export overlay to dictionary format for JSON preset."""
        if self.overlay_type == 'text':
            data = {
                'type': 'text',
                'template': self.text_template,
                'x': self.x_position,
                'y': self.y_position,
                'start': self.start_time,
                'end': self.end_time,
                'animation': self.animation,
                'fade_in': self.fade_in_duration,
                'fade_out': self.fade_out_duration,
                'fontfile': self.font_file,
                'fontsize': self.font_size,
                'fontcolor': self.font_color,
            }
            if self.has_box:
                data['box'] = True
                data['boxcolor'] = self.box_color
                data['boxborderw'] = self.box_border_width
            return data
        else:
            return {
                'type': 'image',
                'path': self.image_path,
                'x': self.x_position,
                'y': self.y_position,
                'start': self.start_time,
                'end': self.end_time,
                'animation': self.animation,
                'fade_in': self.fade_in_duration,
                'fade_out': self.fade_out_duration,
                'scale_w': self.image_width,
                'scale_h': self.image_height,
            }

    def apply_position_preset(self):
        """Apply predefined position based on position_preset."""
        presets = {
            'center': ('(w-text_w)/2', '(h-text_h)/2'),
            'top_left': ('40', '40'),
            'top_center': ('(w-text_w)/2', '40'),
            'top_right': ('w-text_w-40', '40'),
            'bottom_left': ('40', 'h-text_h-40'),
            'bottom_center': ('(w-text_w)/2', 'h-text_h-40'),
            'bottom_right': ('w-text_w-40', 'h-text_h-40'),
            'lower_third_left': ('40', 'h-140'),
            'lower_third_right': ('w-text_w-40', 'h-140'),
        }
        
        if self.position_preset in presets:
            self.x_position, self.y_position = presets[self.position_preset]


class VideoEncodePreset(models.Model):
    """Model representing a video encoding preset."""

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Preset Name'),
        help_text=_('Unique name for this encoding preset (e.g., "1080p25_9000k")'),
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Display Name'),
        help_text=_('Human-readable name shown in UI (auto-generated if empty)'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Optional description of this encoding preset'),
    )
    
    # Video encoding settings
    width = models.IntegerField(
        verbose_name=_('Width'),
        help_text=_('Video width in pixels'),
    )
    height = models.IntegerField(
        verbose_name=_('Height'),
        help_text=_('Video height in pixels'),
    )
    fps = models.IntegerField(
        verbose_name=_('FPS'),
        help_text=_('Frames per second'),
    )
    vcodec = models.CharField(
        max_length=50,
        default='libx264',
        verbose_name=_('Video Codec'),
        help_text=_('Video codec (e.g., "libx264")'),
    )
    video_bitrate_k = models.IntegerField(
        default=9000,
        verbose_name=_('Video Bitrate (kbps)'),
        help_text=_('Video bitrate in kilobits per second'),
    )
    
    # Audio encoding settings
    acodec = models.CharField(
        max_length=50,
        default='aac',
        verbose_name=_('Audio Codec'),
        help_text=_('Audio codec (e.g., "aac")'),
    )
    audio_bitrate_k = models.IntegerField(
        default=192,
        verbose_name=_('Audio Bitrate (kbps)'),
        help_text=_('Audio bitrate in kilobits per second'),
    )
    audio_sample_rate = models.IntegerField(
        default=48000,
        verbose_name=_('Audio Sample Rate (Hz)'),
        help_text=_('Audio sample rate in Hz'),
    )
    audio_channels = models.IntegerField(
        default=2,
        verbose_name=_('Audio Channels'),
        help_text=_('Number of audio channels'),
    )
    
    # Advanced settings
    pix_fmt = models.CharField(
        max_length=50,
        default='yuv420p',
        verbose_name=_('Pixel Format'),
        help_text=_('Pixel format (e.g., "yuv420p")'),
    )
    x264_preset = models.CharField(
        max_length=50,
        default='veryfast',
        verbose_name=_('x264 Preset'),
        help_text=_('x264 encoding preset (e.g., "veryfast", "medium", "slow")'),
    )
    x264_profile = models.CharField(
        max_length=50,
        default='high',
        verbose_name=_('x264 Profile'),
        help_text=_('x264 profile (e.g., "baseline", "main", "high")'),
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for VideoEncodePreset."""

        verbose_name = _('Video Encode Preset')
        verbose_name_plural = _('Video Encode Presets')
        ordering = ['name']

    def __str__(self):
        """Return string representation."""
        if self.display_name:
            return self.display_name
        return f"{self.height}p ({self.video_bitrate_k}k)"

    def save(self, *args, **kwargs):
        """Auto-generate display_name if not provided."""
        if not self.display_name:
            self.display_name = f"{self.height}p ({self.video_bitrate_k}k)"
        super().save(*args, **kwargs)

    def to_json(self) -> dict:
        """Export preset to JSON format compatible with rendering system."""
        return {
            'name': self.name,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'vcodec': self.vcodec,
            'acodec': self.acodec,
            'video_bitrate_k': self.video_bitrate_k,
            'audio_bitrate_k': self.audio_bitrate_k,
            'audio_sample_rate': self.audio_sample_rate,
            'audio_channels': self.audio_channels,
            'pix_fmt': self.pix_fmt,
            'x264_preset': self.x264_preset,
            'x264_profile': self.x264_profile,
        }

