"""Models for the Tools module."""

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from pathlib import Path
import uuid


ANIMATION_CHOICES = [
    ("none", _("None")),
    ("fade", _("Fade")),
    ("slide_up", _("Slide Up")),
    ("slide_left", _("Slide Left")),
    ("slide_right", _("Slide Right")),
    ("slide_down", _("Slide Down")),
    ("zoom_in", _("Zoom In")),
    ("zoom_out", _("Zoom Out")),
]

OVERLAY_TYPE_CHOICES = [
    ("text", _("Text")),
    ("image", _("Image")),
]

POSITION_PRESET_CHOICES = [
    ("custom", _("Custom")),
    ("center", _("Center")),
    ("top_left", _("Top Left")),
    ("top_center", _("Top Center")),
    ("top_right", _("Top Right")),
    ("bottom_left", _("Bottom Left")),
    ("bottom_center", _("Bottom Center")),
    ("bottom_right", _("Bottom Right")),
    ("lower_third_left", _("Lower Third Left")),
    ("lower_third_right", _("Lower Third Right")),
]


def slideshow_media_upload_path(instance, filename):
    """Generate upload path for slideshow media files."""
    if instance.project:
        return f"tools/slideshow/{instance.project.id}/media/{filename}"
    return f"tools/library/media/{filename}"


def slideshow_audio_upload_path(instance, filename):
    """Generate upload path for slideshow audio files."""
    if instance.project:
        return f"tools/slideshow/{instance.project.id}/audio/{filename}"
    return f"tools/library/audio/{filename}"


def slideshow_output_path(instance, filename):
    """Generate output path for generated slideshow videos."""
    return f"tools/slideshow/{instance.id}/output/{filename}"


def audio_normalize_input_upload_path(instance, filename):
    """Generate upload path for audio normalize input files."""
    # Keep original filename. Avoid prefixes; use a _vN suffix only if needed.
    # This is best-effort and assumes local FileSystemStorage under MEDIA_ROOT.
    filename = Path(filename).name
    ext = Path(filename).suffix
    safe_stem = Path(filename).stem
    rel_dir = Path("tools/audio_normalize/input")

    media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
    if media_root.is_absolute():
        media_root_abs = media_root
    else:
        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        media_root_abs = base_dir / media_root

    base = media_root_abs / rel_dir
    candidate = rel_dir / f"{safe_stem}{ext}"
    if not (base / f"{safe_stem}{ext}").exists():
        return str(candidate).replace("\\", "/")

    for i in range(1, 100):
        name = f"{safe_stem}_v{i}{ext}"
        if not (base / name).exists():
            return str(rel_dir / name).replace("\\", "/")

    token = uuid.uuid4().hex[:8]
    return str(rel_dir / f"{safe_stem}_v{token}{ext}").replace("\\", "/")


def audio_normalize_output_upload_path(instance, filename):
    """Generate upload path for audio normalize output files."""
    return f"tools/audio_normalize/{instance.id}/output/{filename}"


class SlideshowProject(models.Model):
    """Model representing a slideshow project."""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]
    
    TRANSITION_CHOICES = [
        ('fade', _('Fade')),
        ('fadeblack', _('Fade to Black')),
        ('fadewhite', _('Fade to White')),
        ('wipeleft', _('Wipe Left')),
        ('wiperight', _('Wipe Right')),
        ('wipeup', _('Wipe Up')),
        ('wipedown', _('Wipe Down')),
        ('slideleft', _('Slide Left')),
        ('slideright', _('Slide Right')),
        ('slideup', _('Slide Up')),
        ('slidedown', _('Slide Down')),
        ('smoothleft', _('Smooth Left')),
        ('smoothright', _('Smooth Right')),
        ('circleopen', _('Circle Open')),
        ('circleclose', _('Circle Close')),
        ('radial', _('Radial')),
        ('random', _('Random')),
    ]
    
    # Basic info
    name = models.CharField(
        max_length=255,
        verbose_name=_('Project Name'),
        help_text=_('Name of the slideshow project')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='slideshow_projects',
        verbose_name=_('Created By')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        verbose_name=_('Status')
    )
    
    # Video settings
    slide_duration = models.FloatField(
        default=20.0,
        verbose_name=_('Slide Duration (seconds)'),
        help_text=_('Duration of each slide in seconds')
    )
    fps = models.IntegerField(
        default=25,
        verbose_name=_('FPS'),
        help_text=_('Frames per second')
    )
    width = models.IntegerField(
        default=1920,
        verbose_name=_('Width'),
        help_text=_('Video width in pixels')
    )
    height = models.IntegerField(
        default=1080,
        verbose_name=_('Height'),
        help_text=_('Video height in pixels')
    )
    
    # Transition settings
    use_transitions = models.BooleanField(
        default=True,
        verbose_name=_('Use Transitions'),
        help_text=_('Enable transitions between slides')
    )
    transition_type = models.CharField(
        max_length=20,
        choices=TRANSITION_CHOICES,
        default='random',
        verbose_name=_('Transition Type')
    )
    transition_duration = models.FloatField(
        default=2.0,
        verbose_name=_('Transition Duration (seconds)'),
        help_text=_('Duration of transitions in seconds')
    )
    
    # Encoding settings
    video_bitrate = models.CharField(
        max_length=20,
        default='5M',
        verbose_name=_('Video Bitrate'),
        help_text=_('Video bitrate (e.g., 5M, 10M)')
    )
    audio_bitrate = models.CharField(
        max_length=20,
        default='256k',
        verbose_name=_('Audio Bitrate'),
        help_text=_('Audio bitrate (e.g., 128k, 256k)')
    )
    video_codec = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Video Codec'),
        help_text=_('Video codec (auto-detect if empty)')
    )
    
    # Output
    output_file = models.FileField(
        upload_to=slideshow_output_path,
        null=True,
        blank=True,
        verbose_name=_('Output Video File')
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message'),
        help_text=_('Error message if generation failed')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At')
    )
    
    class Meta:
        verbose_name = _('Slideshow Project')
        verbose_name_plural = _('Slideshow Projects')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        """Return string representation."""
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def media_count(self):
        """Return count of media files."""
        return self.media_files.count()
    
    @property
    def has_audio(self):
        """Check if project has audio file."""
        return self.audio_files.filter(project=self).exists()


class SlideshowMedia(models.Model):
    """Model representing media files (images/videos) for slideshow."""
    
    MEDIA_TYPE_CHOICES = [
        ('image', _('Image')),
        ('video', _('Video')),
    ]
    
    project = models.ForeignKey(
        SlideshowProject,
        on_delete=models.CASCADE,
        related_name='media_files',
        null=True,
        blank=True,
        verbose_name=_('Project'),
        help_text=_('Project this media belongs to (null for library files)')
    )
    file = models.FileField(
        upload_to=slideshow_media_upload_path,
        verbose_name=_('Media File'),
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'm4v']
            )
        ]
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Name'),
        help_text=_('Name of the media file')
    )
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPE_CHOICES,
        verbose_name=_('Media Type')
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Order in slideshow sequence')
    )
    duration_override = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Duration Override (seconds)'),
        help_text=_('Override default slide duration for this file')
    )
    is_library = models.BooleanField(
        default=False,
        verbose_name=_('Library File'),
        help_text=_('Is this a library media file available to all projects?')
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Uploaded At')
    )
    
    class Meta:
        verbose_name = _('Slideshow Media')
        verbose_name_plural = _('Slideshow Media')
        ordering = ['project', 'order', 'uploaded_at']
        indexes = [
            models.Index(fields=['project', 'order']),
            models.Index(fields=['is_library', 'media_type']),
        ]
    
    def __str__(self):
        """Return string representation."""
        if self.project:
            return f"{self.project.name} - {Path(self.file.name).name} ({self.order})"
        return f"{self.name or Path(self.file.name).name} (Library)"
    
    def save(self, *args, **kwargs):
        """Auto-detect media type on save and set default name."""
        if not self.media_type:
            ext = Path(self.file.name).suffix.lower()
            if ext in ['.jpg', '.jpeg', '.png']:
                self.media_type = 'image'
            elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']:
                self.media_type = 'video'
        
        # Set default name if not provided
        if not self.name and self.file:
            self.name = Path(self.file.name).stem
        
        super().save(*args, **kwargs)


class SlideshowAudio(models.Model):
    """Model representing audio files for slideshow background music."""
    
    project = models.ForeignKey(
        SlideshowProject,
        on_delete=models.CASCADE,
        related_name='audio_files',
        null=True,
        blank=True,
        verbose_name=_('Project'),
        help_text=_('Project this audio belongs to (null for library files)')
    )
    file = models.FileField(
        upload_to=slideshow_audio_upload_path,
        verbose_name=_('Audio File'),
        validators=[
            FileExtensionValidator(
                allowed_extensions=['mp3', 'wav', 'm4a', 'flac', 'ogg']
            )
        ]
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Name'),
        help_text=_('Name of the audio track')
    )
    duration = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Duration (seconds)'),
        help_text=_('Duration of audio in seconds')
    )
    is_library = models.BooleanField(
        default=False,
        verbose_name=_('Library File'),
        help_text=_('Is this a library audio file available to all projects?')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    class Meta:
        verbose_name = _('Slideshow Audio')
        verbose_name_plural = _('Slideshow Audio')
        ordering = ['name']
        indexes = [
            models.Index(fields=['project', 'is_library']),
        ]
    
    def __str__(self):
        """Return string representation."""
        if self.project:
            return f"{self.project.name} - {self.name}"
        return f"{self.name} (Library)"


class VideoPreset(models.Model):
    """
    Video overlay style preset.

    This model was moved from `media_files` to `tools`, but keeps the original table
    (`media_files_videopreset`) for backward compatibility and data retention.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Preset Name"),
        help_text=_('Unique name for this preset (e.g., "my_custom_lower_third")'),
    )
    display_name = models.CharField(
        max_length=255,
        verbose_name=_("Display Name"),
        help_text=_("Human-readable name shown in UI"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of this preset"),
    )

    is_template = models.BooleanField(
        default=False,
        verbose_name=_("Is Template"),
        help_text=_("If true, this preset serves as a starting template for new presets"),
    )

    based_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Based On"),
        help_text=_("Original preset this was copied from"),
    )

    segment_duration = models.FloatField(
        default=5.0,
        verbose_name=_("Segment Duration (seconds)"),
        help_text=_("Duration for intro/outro overlay segments"),
    )
    intro_clip_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Intro Clip Path"),
        help_text=_("Optional path to intro video clip"),
    )
    outro_clip_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Outro Clip Path"),
        help_text=_("Optional path to outro video clip"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_presets",
        verbose_name=_("Created By"),
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_("Public"),
        help_text=_("If true, this preset is available to all users"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Video Preset")
        verbose_name_plural = _("Video Presets")
        ordering = ["display_name"]
        db_table = "media_files_videopreset"

    def __str__(self):
        return self.display_name


class PresetOverlay(models.Model):
    """
    Single overlay layer used by a VideoPreset.

    Moved from `media_files` to `tools`, table kept as `media_files_presetoverlay`.
    """

    SEGMENT_CHOICES = [
        ("intro", _("Intro")),
        ("outro", _("Outro")),
    ]

    preset = models.ForeignKey(
        VideoPreset,
        on_delete=models.CASCADE,
        related_name="overlays",
        verbose_name=_("Preset"),
    )

    overlay_type = models.CharField(
        max_length=20,
        choices=OVERLAY_TYPE_CHOICES,
        default="text",
        verbose_name=_("Type"),
    )
    segment = models.CharField(
        max_length=10,
        choices=SEGMENT_CHOICES,
        default="intro",
        verbose_name=_("Segment"),
        help_text=_("Apply this overlay to intro or outro segment"),
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_("Order"),
        help_text=_("Rendering order (lower number = rendered first/bottom layer)"),
    )

    text_template = models.TextField(
        blank=True,
        verbose_name=_("Text Template"),
        help_text=_("Template with variables like {license.title}, {profile.display}"),
    )

    image_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Image Path"),
        help_text=_("Path to image file (relative to assets/ or absolute)"),
    )
    image_width = models.IntegerField(null=True, blank=True, verbose_name=_("Image Width"))
    image_height = models.IntegerField(null=True, blank=True, verbose_name=_("Image Height"))

    position_preset = models.CharField(
        max_length=30,
        choices=POSITION_PRESET_CHOICES,
        default="custom",
        verbose_name=_("Position Preset"),
    )
    x_position = models.CharField(
        max_length=100,
        default="(w-text_w)/2",
        verbose_name=_("X Position"),
        help_text=_('X coordinate or expression (e.g., "(w-text_w)/2", "40")'),
    )
    y_position = models.CharField(
        max_length=100,
        default="(h-text_h)/2",
        verbose_name=_("Y Position"),
        help_text=_('Y coordinate or expression (e.g., "h-140", "(h-text_h)/2")'),
    )

    start_time = models.FloatField(
        default=0.0,
        verbose_name=_("Start Time (seconds)"),
        help_text=_("When to show this overlay (relative to segment start)"),
    )
    end_time = models.FloatField(
        default=5.0,
        verbose_name=_("End Time (seconds)"),
        help_text=_("When to hide this overlay (relative to segment start)"),
    )

    animation = models.CharField(
        max_length=20,
        choices=ANIMATION_CHOICES,
        default="fade",
        verbose_name=_("Animation"),
    )
    fade_in_duration = models.FloatField(default=0.4, verbose_name=_("Fade In Duration (seconds)"))
    fade_out_duration = models.FloatField(default=0.4, verbose_name=_("Fade Out Duration (seconds)"))

    font_file = models.CharField(
        max_length=500,
        default="fonts/Roboto-Regular.ttf",
        verbose_name=_("Font File"),
        help_text=_('Path relative to assets/ (e.g., "fonts/Roboto-Bold.ttf")'),
    )
    font_size = models.IntegerField(default=48, verbose_name=_("Font Size"))
    font_color = models.CharField(
        max_length=50,
        default="white",
        verbose_name=_("Font Color"),
        help_text=_('Color name or hex (e.g., "white", "#FFFFFF")'),
    )

    has_box = models.BooleanField(default=False, verbose_name=_("Has Background Box"))
    box_color = models.CharField(
        max_length=50,
        default="black@0.5",
        verbose_name=_("Box Color"),
        help_text=_('Color with opacity (e.g., "black@0.5")'),
    )
    box_border_width = models.IntegerField(default=12, verbose_name=_("Box Border Width"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Preset Overlay")
        verbose_name_plural = _("Preset Overlays")
        ordering = ["preset", "segment", "order"]
        db_table = "media_files_presetoverlay"

    def __str__(self):
        if self.overlay_type == "text":
            preview = self.text_template[:50] + "..." if len(self.text_template) > 50 else self.text_template
            return f"{self.get_segment_display()} - Text: {preview}"
        return f"{self.get_segment_display()} - Image: {self.image_path}"


class VideoEncodePreset(models.Model):
    """
    Video encoding preset (resolution/codec/bitrate).

    Moved from `media_files` to `tools`, table kept as `media_files_videoencodepreset`.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Preset Name"),
        help_text=_('Unique name for this encoding preset (e.g., "1080p25_9000k")'),
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Display Name"),
        help_text=_("Human-readable name shown in UI (auto-generated if empty)"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of this encoding preset"),
    )

    width = models.IntegerField(verbose_name=_("Width"), help_text=_("Video width in pixels"))
    height = models.IntegerField(verbose_name=_("Height"), help_text=_("Video height in pixels"))
    fps = models.IntegerField(verbose_name=_("FPS"), help_text=_("Frames per second"))

    vcodec = models.CharField(
        max_length=50,
        default="libx264",
        verbose_name=_("Video Codec"),
        help_text=_('Video codec (e.g., "libx264")'),
    )
    video_bitrate_k = models.IntegerField(
        default=9000,
        verbose_name=_("Video Bitrate (kbps)"),
        help_text=_("Video bitrate in kilobits per second"),
    )

    acodec = models.CharField(
        max_length=50,
        default="aac",
        verbose_name=_("Audio Codec"),
        help_text=_('Audio codec (e.g., "aac")'),
    )
    audio_bitrate_k = models.IntegerField(
        default=192,
        verbose_name=_("Audio Bitrate (kbps)"),
        help_text=_("Audio bitrate in kilobits per second"),
    )
    audio_sample_rate = models.IntegerField(
        default=48000,
        verbose_name=_("Audio Sample Rate (Hz)"),
        help_text=_("Audio sample rate in Hz"),
    )
    audio_channels = models.IntegerField(
        default=2,
        verbose_name=_("Audio Channels"),
        help_text=_("Number of audio channels"),
    )

    pix_fmt = models.CharField(
        max_length=50,
        default="yuv420p",
        verbose_name=_("Pixel Format"),
        help_text=_('Pixel format (e.g., "yuv420p")'),
    )
    x264_preset = models.CharField(
        max_length=50,
        default="veryfast",
        verbose_name=_("x264 Preset"),
        help_text=_('x264 encoding preset (e.g., "veryfast", "medium", "slow")'),
    )
    x264_profile = models.CharField(
        max_length=50,
        default="high",
        verbose_name=_("x264 Profile"),
        help_text=_('x264 profile (e.g., "baseline", "main", "high")'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Video Encode Preset")
        verbose_name_plural = _("Video Encode Presets")
        ordering = ["name"]
        db_table = "media_files_videoencodepreset"

    def __str__(self):
        if self.display_name:
            return self.display_name
        return f"{self.height}p ({self.video_bitrate_k}k)"

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = f"{self.height}p ({self.video_bitrate_k}k)"
        super().save(*args, **kwargs)

    def to_json(self) -> dict:
        """Export preset to JSON format compatible with the rendering system."""
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "vcodec": self.vcodec,
            "acodec": self.acodec,
            "video_bitrate_k": self.video_bitrate_k,
            "audio_bitrate_k": self.audio_bitrate_k,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "pix_fmt": self.pix_fmt,
            "x264_preset": self.x264_preset,
            "x264_profile": self.x264_profile,
        }


class ToolsConfig(models.Model):
    """Configuration for tools module (singleton)."""
    
    # Storage paths
    storage_path_storage = models.ForeignKey(
        'media_files.StorageLocation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Storage Path (Storage Location)'),
        help_text=_('Optional. Storage location for uploads. Overrides the path below when set.'),
    )
    storage_path = models.CharField(
        max_length=500,
        verbose_name=_('Storage Path'),
        help_text=_('Required when no Storage Location is selected. Base path for storing uploaded media files.')
    )
    output_path_storage = models.ForeignKey(
        'media_files.StorageLocation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Output Path (Storage Location)'),
        help_text=_('Optional. Storage location for generated videos. Overrides the path below when set.'),
    )
    output_path = models.CharField(
        max_length=500,
        verbose_name=_('Output Path'),
        help_text=_('Required when no Storage Location is selected. Base path for storing generated videos.')
    )
    
    # Upload limits
    max_upload_size = models.IntegerField(
        default=500,
        verbose_name=_('Max Upload Size (MB)'),
        help_text=_('Maximum file upload size in megabytes')
    )
    
    # Allowed formats
    allowed_image_formats = models.CharField(
        max_length=100,
        default='jpg,jpeg,png',
        verbose_name=_('Allowed Image Formats'),
        help_text=_('Comma-separated list of allowed image extensions')
    )
    allowed_video_formats = models.CharField(
        max_length=200,
        default='mp4,mov,avi,mkv,webm,flv,wmv,m4v',
        verbose_name=_('Allowed Video Formats'),
        help_text=_('Comma-separated list of allowed video extensions')
    )
    allowed_audio_formats = models.CharField(
        max_length=100,
        default='mp3,wav,m4a,flac,ogg',
        verbose_name=_('Allowed Audio Formats'),
        help_text=_('Comma-separated list of allowed audio extensions')
    )
    
    # FFmpeg paths
    ffmpeg_path = models.CharField(
        max_length=500,
        default='ffmpeg',
        verbose_name=_('FFmpeg Path'),
        help_text=_('Path to ffmpeg executable')
    )
    ffprobe_path = models.CharField(
        max_length=500,
        default='ffprobe',
        verbose_name=_('FFprobe Path'),
        help_text=_('Path to ffprobe executable')
    )

    # Audio normalize settings
    audio_normalize_input_storage = models.ForeignKey(
        'media_files.StorageLocation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Audio Normalize Input Storage'),
        help_text=_('Optional. Storage location for input base path. Overrides the path below when set.'),
    )
    audio_normalize_input_path = models.CharField(
        max_length=500,
        default='',
        blank=True,
        verbose_name=_('Audio Normalize Input Path'),
        help_text=_('Base path when no storage is selected. Used for upload dedup and similar. Can be empty.')
    )
    audio_normalize_output_storage = models.ForeignKey(
        'media_files.StorageLocation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Audio Normalize Output Storage'),
        help_text=_('Optional. Storage location for output directory. Overrides the path below when set.'),
    )
    audio_normalize_output_path = models.CharField(
        max_length=500,
        default='',
        blank=True,
        verbose_name=_('Audio Normalize Output Path'),
        help_text=_(
            'Base path when no storage is selected. Empty = next to input. '
            'Can be left empty. If storage is set, output can be outside MEDIA_ROOT.'
        )
    )
    audio_normalize_default_preset = models.CharField(
        max_length=50,
        default='tv_natural',
        verbose_name=_('Audio Normalize Default Preset'),
        help_text=_('Default audio normalize preset ID')
    )
    audio_normalize_default_bitrate = models.CharField(
        max_length=20,
        default='192k',
        verbose_name=_('Audio Normalize Default Bitrate'),
        help_text=_('Default audio bitrate for normalized files (e.g., 192k)')
    )
    
    class Meta:
        verbose_name = _('Tools Configuration')
        verbose_name_plural = _('Tools Configuration')
    
    def __str__(self):
        """Return string representation."""
        return "Tools Configuration"
    
    def save(self, *args, **kwargs):
        """Ensure only one config instance exists."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def get_effective_storage_path(self) -> str:
        """Return storage_path_storage.path if set, else storage_path."""
        s = getattr(self, 'storage_path_storage', None)
        if s and getattr(s, 'path', None):
            return (s.path or '').rstrip('/\\')
        return (self.storage_path or '').strip().rstrip('/\\')

    def get_effective_output_path(self) -> str:
        """Return output_path_storage.path if set, else output_path."""
        s = getattr(self, 'output_path_storage', None)
        if s and getattr(s, 'path', None):
            return (s.path or '').rstrip('/\\')
        return (self.output_path or '').strip().rstrip('/\\')


class AudioNormalizeJob(models.Model):
    """Audio normalization job using EBU R128 loudness normalization."""

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('analyzing', _('Analyzing')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]

    TARGET_CHOICES = [
        ('tv', _('TV (R128)')),
        ('web', _('Web')),
    ]

    BITRATE_CHOICES = [
        ('192k', _('192 kbps')),
        ('256k', _('256 kbps')),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audio_normalize_jobs',
        verbose_name=_('Created By'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name=_('Status'),
    )

    preset_id = models.CharField(
        max_length=50,
        default='tv_natural',
        verbose_name=_('Preset'),
        help_text=_('Audio normalize preset ID'),
    )
    target = models.CharField(
        max_length=10,
        choices=TARGET_CHOICES,
        default='tv',
        verbose_name=_('Target'),
        help_text=_('Target loudness profile'),
    )

    input_file = models.FileField(
        upload_to=audio_normalize_input_upload_path,
        verbose_name=_('Input File'),
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['mp4', 'mov', 'mkv', 'avi', 'webm', 'm4v', 'mp3', 'wav', 'm4a', 'flac', 'ogg']
            )
        ],
    )
    input_path_external = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name=_('Input path (external)'),
        help_text=_('Absolute path when input is outside MEDIA_ROOT (e.g. from a storage location).'),
    )
    input_media_file_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Input media file ID'),
        help_text=_('media_files.VideoFile ID when input was chosen by media number (for stream URL).'),
    )
    output_file = models.FileField(
        upload_to=audio_normalize_output_upload_path,
        null=True,
        blank=True,
        verbose_name=_('Output File'),
    )
    output_path_external = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name=_('Output Path (external)'),
        help_text=_('Absolute path when output was written outside MEDIA_ROOT (e.g. to a storage location).'),
    )

    output_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Output Filename'),
        help_text=_('If empty, will default to <input>_R128.mp4'),
    )

    audio_bitrate = models.CharField(
        max_length=20,
        choices=BITRATE_CHOICES,
        default='192k',
        verbose_name=_('Audio Bitrate'),
    )
    sample_rate = models.IntegerField(
        default=48000,
        verbose_name=_('Sample Rate'),
    )
    force_stereo = models.BooleanField(
        default=False,
        verbose_name=_('Force Stereo'),
        help_text=_('If enabled, audio will be forced to 2 channels'),
    )

    input_metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Input Metadata'),
        help_text=_('ffprobe JSON output'),
    )
    analysis_before = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Analysis Before'),
        help_text=_('loudnorm analysis JSON from pass 1'),
    )
    analysis_after = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Analysis After'),
        help_text=_('loudnorm analysis JSON from after-processing verification pass'),
    )

    progress = models.IntegerField(
        default=0,
        verbose_name=_('Progress (%)'),
        help_text=_('Processing progress 0..100'),
    )

    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message'),
    )
    ffmpeg_log = models.TextField(
        blank=True,
        verbose_name=_('FFmpeg Log'),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('Created At'),
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Started At'),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At'),
    )

    class Meta:
        verbose_name = _('Audio Normalize Job')
        verbose_name_plural = _('Audio Normalize Jobs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"AudioNormalizeJob #{self.id} ({self.get_status_display()})"

    def mark_started(self):
        self.started_at = timezone.now()
        self.save(update_fields=['started_at'])

    def mark_completed(self):
        self.completed_at = timezone.now()
        self.save(update_fields=['completed_at'])
