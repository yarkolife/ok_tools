"""Models for the Austausch (content exchange) module."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class ExchangeItem(models.Model):
    """Represents an item found in Nextcloud exchange folders."""
    
    # Identification
    contribution_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_('Contribution ID'),
        help_text=_('Numeric ID from filename (if OK-Tools managed)')
    )
    filename = models.CharField(
        max_length=500,
        verbose_name=_('Filename')
    )
    file_path = models.CharField(
        max_length=1000,
        verbose_name=_('File Path'),
        help_text=_('Full Nextcloud path to video file')
    )
    pdf_path = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name=_('PDF Path'),
        help_text=_('Full Nextcloud path to PDF file (if part of package)')
    )
    thumbnail_path = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name=_('Thumbnail Path'),
        help_text=_('Full Nextcloud path to thumbnail image (jpg, png, etc.)')
    )
    channel = models.CharField(
        max_length=100,
        verbose_name=_('Channel'),
        help_text=_('Source channel name')
    )
    
    # File info
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('File Size (bytes)')
    )
    file_type = models.CharField(
        max_length=50,
        verbose_name=_('File Type'),
        help_text=_("'video' or 'pdf'")
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Checksum'),
        help_text=_('SHA256 checksum')
    )
    
    # Metadata (enriched from OK-Tools if contribution_id exists)
    title = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Title')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_('Duration')
    )
    sendeverantwortung = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Sender Responsible')
    )
    
    # Status
    is_oktools_managed = models.BooleanField(
        default=False,
        verbose_name=_('OK-Tools Managed'),
        help_text=_('Item is managed by OK-Tools (has contribution_id)')
    )
    is_legacy = models.BooleanField(
        default=False,
        verbose_name=_('Legacy'),
        help_text=_('Item without numeric ID prefix')
    )
    import_status = models.CharField(
        max_length=20,
        choices=[
            ('new', _('New')),
            ('imported', _('Imported')),
            ('failed', _('Failed')),
        ],
        default='new',
        db_index=True,
        verbose_name=_('Import Status')
    )
    
    # Timestamps
    discovered_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('Discovered At')
    )
    last_seen_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Seen At')
    )
    imported_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Imported At')
    )
    
    # Relationships
    imported_license = models.ForeignKey(
        'licenses.License',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='exchange_items',
        verbose_name=_('Imported License')
    )
    
    class Meta:
        verbose_name = _('Exchange Item')
        verbose_name_plural = _('Exchange Items')
        unique_together = [('file_path', 'channel')]
        indexes = [
            models.Index(fields=['contribution_id']),
            models.Index(fields=['channel', 'discovered_at']),
            models.Index(fields=['import_status']),
        ]
        ordering = ['-discovered_at']
    
    def __str__(self):
        """Return string representation."""
        if self.contribution_id:
            return f"{self.contribution_id} - {self.filename} ({self.channel})"
        return f"{self.filename} ({self.channel})"


class ExchangeImport(models.Model):
    """Tracks import operations from exchange folders."""
    
    exchange_item = models.ForeignKey(
        ExchangeItem,
        on_delete=models.CASCADE,
        related_name='imports',
        verbose_name=_('Exchange Item')
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Imported By')
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('pending_download', _('Pending Download')),
            ('downloading', _('Downloading')),
            ('processing', _('Processing')),
            ('completed', _('Completed')),
            ('failed', _('Failed')),
        ],
        default='pending',
        db_index=True,
        verbose_name=_('Status')
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_('Created At')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At')
    )
    
    # Imported resources
    license = models.ForeignKey(
        'licenses.License',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='exchange_import_records',
        verbose_name=_('License')
    )
    video_file = models.ForeignKey(
        'media_files.VideoFile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='exchange_imports',
        verbose_name=_('Video File')
    )
    
    class Meta:
        verbose_name = _('Exchange Import')
        verbose_name_plural = _('Exchange Imports')
        ordering = ['-created_at']
    
    def __str__(self):
        """Return string representation."""
        return f"Import {self.id} - {self.exchange_item.filename} ({self.get_status_display()})"


class ExchangeConfig(models.Model):
    """Configuration for exchange module (singleton)."""
    
    # Nextcloud settings
    nextcloud_base_url = models.URLField(
        verbose_name=_('Nextcloud Base URL'),
        help_text=_('Base URL of Nextcloud server (e.g., https://cloud.example.com)')
    )
    nextcloud_username = models.CharField(
        max_length=255,
        verbose_name=_('Nextcloud Username'),
        help_text=_('Service account username for WebDAV access')
    )
    nextcloud_password = models.CharField(
        max_length=255,
        verbose_name=_('Nextcloud Password'),
        help_text=_('App password or service account password')
    )
    
    # Folder patterns
    channel_folder_pattern = models.CharField(
        max_length=255,
        default="{channel}",
        verbose_name=_('Channel Folder Pattern'),
        help_text=_('Pattern for channel folders: {channel} will be replaced')
    )
    exchange_folder_pattern = models.CharField(
        max_length=255,
        default="{channel}_austausch",
        verbose_name=_('Exchange Folder Pattern'),
        help_text=_('Pattern for exchange folders: {channel} will be replaced')
    )
    
    # Sync settings
    sync_lookback_days = models.IntegerField(
        default=7,
        verbose_name=_('Sync Lookback Days'),
        help_text=_('How many days back to check for new items (for file age filtering). Only files modified within this period will be processed.')
    )
    sync_date_folders_days = models.IntegerField(
        default=2,
        verbose_name=_('Sync Date Folders Days'),
        help_text=_('How many recent date folders to scan (e.g., 2 = today and yesterday). Files are organized in date-named folders like "2026_01_07".')
    )
    
    # Storage settings
    storage_location = models.ForeignKey(
        'media_files.StorageLocation',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Storage Location'),
        help_text=_('Select existing storage location for imported files. If not set, a new storage will be created automatically.')
    )
    download_storage_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Download Storage Path'),
        help_text=_('Local path for downloaded files before import (used if storage location is not set)')
    )
    
    # Auto-import settings
    auto_import_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Auto-Import Enabled'),
        help_text=_('Automatically enqueue PeerTube upload after import')
    )
    
    # Channel list (comma-separated or JSON)
    channels_list = models.TextField(
        blank=True,
        verbose_name=_('Channels List'),
        help_text=_('Comma-separated list of channel names to sync (optional, can be auto-discovered)')
    )
    
    # Export to server settings
    upload_server_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Upload Server Path'),
        help_text=_('WebDAV path on Nextcloud for upload (e.g. GroupFolders/Mediathek-Upload/OK_MQ). Distinct from download/sync paths.')
    )
    default_media_authority = models.ForeignKey(
        'registration.MediaAuthority',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Default Media Authority'),
        help_text=_('Optional "Offener Kanal" preselected for export.')
    )
    local_pdf_fallback_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Local PDF Fallback Path'),
        help_text=_('First local directory for unsigned licenses; PDFs searched by pattern {number}_*.pdf.')
    )
    local_pdf_fallback_path_2 = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Local PDF Fallback Path (2)'),
        help_text=_('Second local directory for unsigned licenses; searched if not found in first path.')
    )
    upload_thumbnail_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Upload Thumbnail Enabled'),
        help_text=_('If enabled, upload video cover/thumbnail images from a local directory when exporting to server.')
    )
    thumbnail_storage_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Thumbnail Storage Path'),
        help_text=_('Local directory where cover images are stored. Used when "Upload Thumbnail Enabled" is on. Matching by number at start of filename (e.g. 12345_cover.jpg). Supported: .jpg, .jpeg, .png, .webp.')
    )
    
    class Meta:
        verbose_name = _('Exchange Configuration')
        verbose_name_plural = _('Exchange Configuration')
    
    def __str__(self):
        """Return string representation."""
        return f"Exchange Config - {self.nextcloud_base_url}"
    
    def clean(self):
        """Validate the model."""
        # Either storage_location or download_storage_path must be set
        if not self.storage_location and not self.download_storage_path:
            raise ValidationError({
                'storage_location': _('Either storage location or download storage path must be set.'),
                'download_storage_path': _('Either storage location or download storage path must be set.'),
            })
    
    def save(self, *args, **kwargs):
        """Ensure only one config instance exists."""
        self.full_clean()  # Run validation before saving
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class ExportToServerRun(models.Model):
    """Result of an export-to-server (Celery) run for user-visible report."""

    started_at = models.DateTimeField(
        verbose_name=_('Started at'),
        auto_now_add=True,
        db_index=True,
    )
    completed_at = models.DateTimeField(
        verbose_name=_('Completed at'),
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('User'),
    )
    mode = models.CharField(
        max_length=20,
        choices=[('contributions', _('By contributions')), ('licenses', _('By license numbers'))],
        verbose_name=_('Mode'),
    )
    total_count = models.PositiveIntegerField(verbose_name=_('Total selected'), default=0)
    success_count = models.PositiveIntegerField(verbose_name=_('Uploaded'), default=0)
    failure_count = models.PositiveIntegerField(verbose_name=_('Failed'), default=0)
    skipped_no_pdf_count = models.PositiveIntegerField(
        verbose_name=_('Skipped (no PDF)'),
        default=0,
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Details'),
        help_text=_('success_ids, failed (id, reason), skipped_no_pdf'),
    )

    class Meta:
        ordering = ['-started_at']
        verbose_name = _('Export to server run')
        verbose_name_plural = _('Export to server runs')

    def __str__(self):
        return f"Export {self.started_at} ({self.success_count}/{self.total_count})"

