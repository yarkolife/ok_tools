"""Admin interface for media files."""

import logging
import os
from django import forms
from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from rangefilter.filters import DateRangeFilter

from .models import StorageLocation, VideoFile, FileOperation
from .tasks import copy_video_to_playout
from .utils import verify_file_integrity, extract_video_metadata, extract_number_from_filename, calculate_checksum


logger = logging.getLogger('django')


class VideoFileAdminForm(forms.ModelForm):
    """Form for adding/editing video files with file upload support."""
    
    uploaded_file = forms.FileField(
        required=False,
        label=_('Upload Video File'),
        help_text=_('Upload a video file (mp4, mov, mpeg, mpg). The file will be saved to the selected storage location.')
    )
    
    file_path_manual = forms.CharField(
        required=False,
        label=_('Or specify file path'),
        help_text=_('Full path to existing video file on the server'),
        widget=forms.TextInput(attrs={'size': '80'})
    )
    
    class Meta:
        model = VideoFile
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing file, hide upload fields
        if self.instance and self.instance.pk:
            self.fields['uploaded_file'].widget = forms.HiddenInput()
            self.fields['file_path_manual'].widget = forms.HiddenInput()
            if 'storage_location' in self.fields:
                self.fields['storage_location'].disabled = True
    
    def clean(self):
        cleaned_data = super().clean()
        uploaded_file = cleaned_data.get('uploaded_file')
        file_path_manual = cleaned_data.get('file_path_manual')
        storage_location = cleaned_data.get('storage_location')
        
        # For new files, require either upload or path
        if not self.instance.pk:
            if not uploaded_file and not file_path_manual:
                raise forms.ValidationError(
                    _('Please either upload a file or specify an existing file path.')
                )
            
            if uploaded_file and file_path_manual:
                raise forms.ValidationError(
                    _('Please provide only one: either upload a file OR specify a path.')
                )
            
            if not storage_location:
                raise forms.ValidationError(_('Storage location is required.'))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Only process new files
        if not instance.pk:
            from django.utils import timezone
            
            uploaded_file = self.cleaned_data.get('uploaded_file')
            file_path_manual = self.cleaned_data.get('file_path_manual')
            storage_location = self.cleaned_data.get('storage_location')
            
            if uploaded_file:
                # Handle uploaded file
                filename = uploaded_file.name
                
                # Extract number from filename
                number = extract_number_from_filename(filename)
                if not number:
                    raise forms.ValidationError(
                        _('Filename must start with a number (e.g., 12345_title.mp4)')
                    )
                
                # Save file to storage location
                file_path = os.path.join(storage_location.path, filename)
                
                # Check if file already exists
                if os.path.exists(file_path):
                    raise forms.ValidationError(
                        _('File already exists at: {}').format(file_path)
                    )
                
                # Save uploaded file
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                # Set instance fields
                instance.number = number
                instance.filename = filename
                instance.file_path = filename
                instance.storage_location = storage_location
                instance.is_available = True
                
                # Extract metadata
                try:
                    metadata = extract_video_metadata(file_path)
                    instance.format = metadata.get('format', '')
                    instance.duration = metadata.get('duration')
                    instance.file_size = os.path.getsize(file_path)
                    
                    instance.has_video = metadata.get('has_video', False)
                    if instance.has_video:
                        instance.video_codec = metadata.get('video_codec', '')
                        instance.fps = metadata.get('fps')
                        instance.width = metadata.get('width')
                        instance.height = metadata.get('height')
                    
                    instance.has_audio = metadata.get('has_audio', False)
                    if instance.has_audio:
                        instance.audio_codec = metadata.get('audio_codec', '')
                        instance.audio_channels = metadata.get('audio_channels')
                    
                    instance.total_bitrate = metadata.get('total_bitrate')
                    
                    # Calculate checksum
                    instance.checksum = calculate_checksum(file_path)
                    
                except Exception as e:
                    logger.error(f'Error extracting metadata: {str(e)}')
                    # Continue without metadata
                
                instance.last_scanned = timezone.now()
                
            elif file_path_manual:
                # Handle manual file path
                if not os.path.exists(file_path_manual):
                    raise forms.ValidationError(
                        _('File does not exist: {}').format(file_path_manual)
                    )
                
                if not os.path.isfile(file_path_manual):
                    raise forms.ValidationError(
                        _('Path is not a file: {}').format(file_path_manual)
                    )
                
                filename = os.path.basename(file_path_manual)
                
                # Extract number
                number = extract_number_from_filename(filename)
                if not number:
                    raise forms.ValidationError(
                        _('Filename must start with a number (e.g., 12345_title.mp4)')
                    )
                
                # Calculate relative path
                storage_path = storage_location.path.rstrip('/')
                if not file_path_manual.startswith(storage_path):
                    raise forms.ValidationError(
                        _('File must be within storage location: {}').format(storage_path)
                    )
                
                relative_path = file_path_manual[len(storage_path):].lstrip('/')
                
                # Set instance fields
                instance.number = number
                instance.filename = filename
                instance.file_path = relative_path
                instance.storage_location = storage_location
                instance.is_available = True
                
                # Extract metadata
                try:
                    metadata = extract_video_metadata(file_path_manual)
                    instance.format = metadata.get('format', '')
                    instance.duration = metadata.get('duration')
                    instance.file_size = os.path.getsize(file_path_manual)
                    
                    instance.has_video = metadata.get('has_video', False)
                    if instance.has_video:
                        instance.video_codec = metadata.get('video_codec', '')
                        instance.fps = metadata.get('fps')
                        instance.width = metadata.get('width')
                        instance.height = metadata.get('height')
                    
                    instance.has_audio = metadata.get('has_audio', False)
                    if instance.has_audio:
                        instance.audio_codec = metadata.get('audio_codec', '')
                        instance.audio_channels = metadata.get('audio_channels')
                    
                    instance.total_bitrate = metadata.get('total_bitrate')
                    
                    # Calculate checksum
                    instance.checksum = calculate_checksum(file_path_manual)
                    
                except Exception as e:
                    logger.error(f'Error extracting metadata: {str(e)}')
                
                instance.last_scanned = timezone.now()
        
        if commit:
            instance.save()
        
        return instance


class FileOperationInline(admin.TabularInline):
    """Inline admin for file operations history."""

    model = FileOperation
    extra = 0
    can_delete = False
    readonly_fields = [
        'operation_type', 'source_location', 'destination_location',
        'performed_by', 'performed_at', 'status', 'error_message'
    ]
    fields = readonly_fields
    
    def has_add_permission(self, request, obj=None):
        """Disable add permission."""
        return False


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    """Admin interface for storage locations."""

    list_display = [
        'name', 'storage_type', 'path', 'is_active',
        'scan_enabled', 'video_count_display', 'updated_at'
    ]
    list_filter = ['storage_type', 'is_active', 'scan_enabled']
    search_fields = ['name', 'path']
    readonly_fields = ['created_at', 'updated_at', 'video_count']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'storage_type', 'path', 'is_active')
        }),
        (_('Scanning'), {
            'fields': ('scan_enabled', 'scan_schedule')
        }),
        (_('Information'), {
            'fields': ('video_count', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['scan_storage', 'test_connection']
    
    def get_urls(self):
        """Add custom URLs for storage management."""
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path(
                '<int:storage_id>/scan/',
                self.admin_site.admin_view(self.scan_storage_view),
                name='media_files_storagelocation_scan',
            ),
        ]
        return custom_urls + urls
    
    def video_count_display(self, obj):
        """Display video count with link and scan button."""
        count = obj.video_count
        scan_url = reverse('admin:media_files_storagelocation_scan', args=[obj.id])
        
        if count > 0:
            list_url = reverse('admin:media_files_videofile_changelist') + f'?storage_location__id__exact={obj.id}'
            return format_html(
                '<a href="{}">{}</a> | <a href="{}" class="button" style="padding: 3px 10px; margin-left: 5px;">🔍 Scan</a>',
                list_url, count, scan_url
            )
        return format_html(
            '{} | <a href="{}" class="button" style="padding: 3px 10px; margin-left: 5px;">🔍 Scan</a>',
            count, scan_url
        )
    video_count_display.short_description = _('Videos')
    
    def scan_storage_view(self, request, storage_id):
        """View to scan a single storage location."""
        from django.shortcuts import redirect
        from django.contrib import messages
        from django.core.management import call_command
        from io import StringIO
        
        try:
            storage = StorageLocation.objects.get(id=storage_id)
            
            # Capture command output
            out = StringIO()
            call_command('scan_video_storage', storage_id=storage_id, stdout=out)
            output = out.getvalue()
            
            # Parse output for statistics
            lines = output.split('\n')
            stats = {'created': 0, 'updated': 0, 'found': 0}
            for line in lines:
                if 'Created:' in line:
                    stats['created'] += 1
                elif 'Updated:' in line or 'updated' in line.lower():
                    stats['updated'] += 1
                elif 'Total files found:' in line:
                    try:
                        stats['found'] = int(line.split(':')[1].strip())
                    except:
                        pass
            
            messages.success(
                request,
                f'✓ Сканирование завершено: {storage.name}\n'
                f'Найдено: {stats["found"]} файлов | '
                f'Создано: {stats["created"]} записей | '
                f'Обновлено: {stats["updated"]} записей'
            )
            
        except StorageLocation.DoesNotExist:
            messages.error(request, f'Storage location #{storage_id} not found')
        except Exception as e:
            messages.error(request, f'Error scanning storage: {str(e)}')
        
        return redirect('admin:media_files_storagelocation_changelist')
    
    def scan_storage(self, request, queryset):
        """Action to scan selected storage locations."""
        from django.core.management import call_command
        
        for storage in queryset:
            try:
                call_command('scan_video_storage', storage_id=storage.id)
                self.message_user(request, f'Successfully scanned: {storage.name}')
            except Exception as e:
                self.message_user(request, f'Error scanning {storage.name}: {str(e)}', level='error')
    scan_storage.short_description = _('Scan selected storage locations')
    
    def test_connection(self, request, queryset):
        """Action to test connection to storage."""
        import os
        
        for storage in queryset:
            if os.path.exists(storage.path) and os.path.isdir(storage.path):
                self.message_user(request, f'✓ {storage.name}: Connection OK')
            else:
                self.message_user(
                    request,
                    f'✗ {storage.name}: Cannot access path',
                    level='error'
                )
    test_connection.short_description = _('Test connection to storage')


class HasDuplicatesFilter(admin.SimpleListFilter):
    title = _('Has Duplicates')
    parameter_name = 'has_duplicates'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes - has duplicates')),
            ('no', _('No - unique')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            # Videos that have other versions with same number
            from django.db.models import Count
            duplicated_numbers = VideoFile.objects.values('number').annotate(
                count=Count('number')
            ).filter(count__gt=1).values_list('number', flat=True)
            return queryset.filter(number__in=duplicated_numbers)
        
        if self.value() == 'no':
            # Videos that are unique (no other versions)
            from django.db.models import Count
            unique_numbers = VideoFile.objects.values('number').annotate(
                count=Count('number')
            ).filter(count=1).values_list('number', flat=True)
            return queryset.filter(number__in=unique_numbers)


class IsPrimaryVersionFilter(admin.SimpleListFilter):
    title = _('Version Type')
    parameter_name = 'is_primary'
    
    def lookups(self, request, model_admin):
        return (
            ('primary', _('Primary versions')),
            ('duplicate', _('Duplicate versions')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'primary':
            # Complex filter - need to evaluate is_primary_version() for each
            primary_ids = [v.id for v in queryset if v.is_primary_version()]
            return queryset.filter(id__in=primary_ids)
        
        if self.value() == 'duplicate':
            primary_ids = [v.id for v in queryset if v.is_primary_version()]
            return queryset.exclude(id__in=primary_ids)


@admin.register(VideoFile)
class VideoFileAdmin(admin.ModelAdmin):
    """Admin interface for video files."""

    form = VideoFileAdminForm
    
    list_display = [
        'number', 'filename', 'storage_location', 'resolution_display',
        'duration', 'file_size_display', 'format', 'is_available',
        'duplicates_indicator', 'view_video_link', 'player_link'
    ]
    list_filter = [
        'storage_location', 'format', 'is_available',
        ('created_at', DateRangeFilter),
        'has_video', 'has_audio',
        HasDuplicatesFilter, IsPrimaryVersionFilter
    ]
    search_fields = ['number', 'filename', 'video_codec', 'audio_codec']
    def get_readonly_fields(self, request, obj=None):
        """Make fields editable when adding new video."""
        if obj:  # Editing existing object
            return [
                'number', 'filename', 'storage_location', 'file_path',
                'file_size', 'file_size_mb', 'duration', 'format',
                'last_scanned', 'last_modified', 'checksum',
                'video_codec', 'video_codec_long', 'video_profile',
                'video_bitrate', 'video_bitrate_mode', 'fps',
                'width', 'height', 'resolution_display', 'aspect_ratio',
                'pixel_format', 'color_space', 'color_range', 'chroma_subsampling',
                'audio_codec', 'audio_codec_long', 'audio_bitrate',
                'audio_sample_rate', 'audio_channels', 'audio_channel_layout',
                'has_video', 'has_audio', 'total_bitrate', 'bitrate_mbps',
                'license_link', 'video_player', 'duplicate_status_display', 'all_versions_display', 'created_at', 'updated_at'
            ]
        else:  # Adding new object
            return []
    
    def get_fieldsets(self, request, obj=None):
        """Show different fields when adding vs editing."""
        if obj:  # Editing existing object
            return (
                (_('Basic Information'), {
                    'fields': (
                        'number', 'filename', 'storage_location', 'file_path',
                        'license_link', 'is_available'
                    )
                }),
                (_('File Properties'), {
                    'fields': (
                        'format', 'file_size', 'file_size_mb', 'duration',
                        'checksum', 'last_modified', 'last_scanned'
                    )
                }),
                (_('Video Properties'), {
                    'fields': (
                        'has_video', 'video_codec', 'video_codec_long', 'video_profile',
                        'video_bitrate', 'video_bitrate_mode', 'fps',
                        'width', 'height', 'resolution_display', 'aspect_ratio',
                        'pixel_format', 'color_space', 'color_range', 'chroma_subsampling'
                    )
                }),
                (_('Audio Properties'), {
                    'fields': (
                        'has_audio', 'audio_codec', 'audio_codec_long', 'audio_bitrate',
                        'audio_sample_rate', 'audio_channels', 'audio_channel_layout'
                    )
                }),
                (_('Overall'), {
                    'fields': ('total_bitrate', 'bitrate_mbps')
                }),
                (_('Video Player'), {
                    'fields': ('video_player',),
                    'classes': ('wide',)
                }),
                (_('Duplicate Management'), {
                    'fields': ('duplicate_status_display', 'all_versions_display'),
                    'classes': ('collapse',),
                }),
                (_('Timestamps'), {
                    'fields': ('created_at', 'updated_at'),
                    'classes': ('collapse',)
                }),
            )
        else:  # Adding new object
            return (
                (_('Add Video File'), {
                    'fields': ('storage_location', 'uploaded_file', 'file_path_manual', 'is_available'),
                    'description': _(
                        'Choose a storage location, then either:<br>'
                        '• <strong>Upload a file</strong> - File will be saved to the storage location<br>'
                        '• <strong>Specify a path</strong> - Reference an existing file on the server<br><br>'
                        '<strong>Important:</strong> Filename must start with a number (e.g., 12345_title.mp4)'
                    )
                }),
            )
    
    inlines = [FileOperationInline]
    actions = ['copy_to_playout_action', 'update_metadata_action', 'verify_integrity_action', 
               'mark_as_primary_action', 'delete_duplicates_action', 'move_to_archive_action']
    
    def get_urls(self):
        """Add custom URLs."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:video_id>/stream/',
                self.admin_site.admin_view(self.stream_video),
                name='media_files_videofile_stream',
            ),
            path(
                '<int:video_id>/player/',
                self.admin_site.admin_view(self.video_player_page),
                name='media_files_videofile_player',
            ),
            path(
                'system-management/',
                self.admin_site.admin_view(system_management_view),
                name='media_files_system_management',
            ),
        ]
        return custom_urls + urls
    
    def file_size_display(self, obj):
        """Display file size in MB."""
        if obj.file_size_mb:
            return f"{obj.file_size_mb} MB"
        return "-"
    file_size_display.short_description = _('Size')
    
    def license_link(self, obj):
        """Display link to associated license."""
        license_obj = obj.get_license()
        if license_obj:
            url = reverse('admin:licenses_license_change', args=[license_obj.id])
            return format_html('<a href="{}">{} - {}</a>', url, license_obj.number, license_obj.title)
        return "-"
    license_link.short_description = _('License')
    
    def duplicates_indicator(self, obj):
        """Show duplicate status indicator."""
        if not obj.has_duplicates:
            return '—'
        
        count = obj.duplicate_count
        is_primary = obj.is_primary_version()
        
        if is_primary:
            return format_html(
                '<span style="color: #28a745;" title="Primary version, {} duplicate(s) exist">✓ PRIMARY ({})</span>',
                count, count
            )
        else:
            return format_html(
                '<span style="color: #ffc107;" title="Duplicate version, primary exists">⚠️ DUPLICATE</span>'
            )

    duplicates_indicator.short_description = _('Duplicate Status')
    
    def duplicate_status_display(self, obj):
        """Show detailed duplicate status."""
        if not obj.pk:
            return '-'
        
        if not obj.has_duplicates:
            return format_html('<span style="color: #28a745;">✓ Unique (no duplicates)</span>')
        
        is_primary = obj.is_primary_version()
        count = obj.duplicate_count
        
        if is_primary:
            return format_html(
                '<span style="color: #28a745;">✓ PRIMARY VERSION</span><br>'
                '<span style="color: #666;">This is the best quality version. {} duplicate(s) exist.</span>',
                count
            )
        else:
            primary = [v for v in obj.get_all_versions() if v.is_primary_version()][0]
            return format_html(
                '<span style="color: #ffc107;">⚠️ DUPLICATE VERSION</span><br>'
                '<span style="color: #666;">Primary version is in: <a href="{}">{}</a></span>',
                reverse('admin:media_files_videofile_change', args=[primary.id]),
                primary.storage_location.name
            )

    duplicate_status_display.short_description = _('Duplicate Status')

    def all_versions_display(self, obj):
        """Show all versions of this video."""
        if not obj.pk or not obj.has_duplicates:
            return '-'
        
        versions = obj.get_all_versions()
        html_parts = []
        
        for v in versions:
            is_current = v.id == obj.id
            is_primary = v.is_primary_version()
            
            status = ''
            if is_primary:
                status = '<span style="color: #28a745;">✓ PRIMARY</span>'
            elif is_current:
                status = '<span style="color: #ffc107;">⚠️ CURRENT</span>'
            else:
                status = '<span style="color: #999;">DUPLICATE</span>'
            
            info = f'{v.storage_location.name} • {v.total_bitrate or 0} bps • {v.width}x{v.height} • {v.file_size_mb} MB'
            
            if is_current:
                html_parts.append(f'<strong>{status} • {info}</strong>')
            else:
                url = reverse('admin:media_files_videofile_change', args=[v.id])
                html_parts.append(f'{status} • <a href="{url}">{info}</a>')
        
        return format_html('<br>'.join(html_parts))

    all_versions_display.short_description = _('All Versions')
    
    def view_video_link(self, obj):
        """Display link to view video."""
        if obj.is_available:
            return format_html(
                '<a href="#" onclick="window.open(\'{}\', \'video\', \'width=800,height=600\'); return false;">▶️ {}</a>',
                reverse('admin:media_files_videofile_stream', args=[obj.id]),
                _('Play')
            )
        return "-"
    view_video_link.short_description = _('View')
    
    def player_link(self, obj):
        """Link to dedicated video player page."""
        if obj.is_available and obj.pk:
            player_url = reverse('admin:media_files_videofile_player', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank" style="color: #417690; text-decoration: none;">🎬 Плеер</a>',
                player_url
            )
        return "-"
    player_link.short_description = _('Player')
    
    def video_player(self, obj):
        """Embed Video.js player in admin."""
        if obj.is_available and obj.pk:
            stream_url = reverse('admin:media_files_videofile_stream', args=[obj.id])
            
            # Get correct MIME type based on file extension
            import os
            file_extension = os.path.splitext(obj.filename)[1].lower()
            content_types = {
                '.mp4': 'video/mp4',
                '.mov': 'video/quicktime',
                '.mpeg': 'video/mpeg',
                '.mpg': 'video/mpeg',
                '.avi': 'video/x-msvideo',
                '.mkv': 'video/x-matroska',
                '.webm': 'video/webm',
            }
            mime_type = content_types.get(file_extension, 'video/mp4')
            
            # Generate UNC path for VLC
            vlc_path = self._get_vlc_path(obj)
            
            return format_html(
                '''
                <div style="max-width: 640px; margin: 10px 0;">
                    <!-- Video.js CSS -->
                    <link href="https://vjs.zencdn.net/8.6.1/video-js.css" rel="stylesheet">
                    
                    <!-- Video.js Player -->
                    <video
                        id="video-player-{}"
                        class="video-js vjs-default-skin"
                        controls
                        preload="auto"
                        width="640"
                        height="360"
                        data-setup='{{"fluid": true, "responsive": true, "playbackRates": [0.5, 1, 1.25, 1.5, 2]}}'>
                        <source src="{}" type="{}">
                        <p class="vjs-no-js">
                            Для просмотра видео включите JavaScript или используйте 
                            <a href="{}" download>скачать видео</a>
                        </p>
                    </video>
                    
                    <!-- Video.js JavaScript -->
                    <script src="https://vjs.zencdn.net/8.6.1/video.min.js"></script>
                    
                    <!-- VLC Integration -->
                    <div style="margin-top: 10px; text-align: center;">
                        <a href="vlc://{}" style="background: #ff8800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">
                            🎬 Открыть в VLC
                        </a>
                    </div>
                    
                    <!-- File Info -->
                    <div style="font-size: 11px; color: #666; margin-top: 10px; background: #f8f8f8; padding: 8px; border-radius: 4px;">
                        <strong>Путь к файлу для VLC:</strong><br>
                        <code style="word-break: break-all;">{}</code><br>
                        <em>Скопируйте путь для открытия в VLC → Медиа → Открыть файл</em>
                    </div>
                    
                    <!-- Initialize Video.js -->
                    <script>
                        document.addEventListener('DOMContentLoaded', function() {{
                            if (typeof videojs !== 'undefined') {{
                                var player = videojs('video-player-{}');
                                player.ready(function() {{
                                    console.log('Video.js player ready');
                                }});
                            }}
                        }});
                    </script>
                </div>
                ''',
                obj.id,  # video player ID
                stream_url,
                mime_type,
                stream_url,
                vlc_path,
                vlc_path,
                obj.id  # video player ID for script
            )
        return _('Video not available')
    
    def _get_vlc_path(self, obj):
        """Generate UNC path for VLC based on storage location."""
        # Map storage locations to NAS UNC paths
        nas_mapping = {
            'ARCHIVE': '\\\\192.168.88.101\\FilmArchiv',
            'PLAYOUT': '\\\\192.168.88.2\\Playout',
        }
        
        if obj.storage_location and obj.storage_location.storage_type in nas_mapping:
            nas_base = nas_mapping[obj.storage_location.storage_type]
            # Convert Unix path to Windows UNC path
            vlc_path = f"{nas_base}\\{obj.file_path.replace('/', '\\')}"
        else:
            # Fallback to original path
            vlc_path = obj.file_path
            
        return vlc_path
    video_player.short_description = _('Video Player')
    
    def video_player_page(self, request, video_id):
        """Display video player page."""
        try:
            video = VideoFile.objects.get(id=video_id)
            # Add VLC path to video object
            video.vlc_path = self._get_vlc_path(video)
            return render(request, 'admin/video_player.html', {'video': video})
        except VideoFile.DoesNotExist:
            return HttpResponse('Video not found', status=404)
        except Exception as e:
            logger.error(f'Error loading video player: {str(e)}', exc_info=True)
            return HttpResponse(f'Error: {str(e)}', status=500)

    def stream_video(self, request, video_id):
        """Stream video file with range support."""
        import os
        from django.http import FileResponse
        
        try:
            video = VideoFile.objects.get(id=video_id)
            
            if not video.is_available:
                return HttpResponse('Video not available', status=404)
            
            file_path = video.full_path
            
            if not os.path.exists(file_path):
                video.is_available = False
                video.save()
                return HttpResponse('Video file not found', status=404)
            
            # Determine content type based on file extension, not database format
            import os
            file_extension = os.path.splitext(video.filename)[1].lower()
            content_types = {
                '.mp4': 'video/mp4',
                '.mov': 'video/quicktime',
                '.mpeg': 'video/mpeg',
                '.mpg': 'video/mpeg',
                '.avi': 'video/x-msvideo',
                '.mkv': 'video/x-matroska',
                '.webm': 'video/webm',
            }
            content_type = content_types.get(file_extension, 'video/mp4')
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Handle range requests for video seeking
            range_header = request.META.get('HTTP_RANGE', '').strip()
            
            if range_header:
                import re
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                
                if range_match:
                    first_byte = int(range_match.group(1))
                    last_byte = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    length = last_byte - first_byte + 1
                    
                    file_handle = open(file_path, 'rb')
                    file_handle.seek(first_byte)
                    
                    response = HttpResponse(
                        file_handle.read(length),
                        status=206,
                        content_type=content_type
                    )
                    response['Content-Length'] = str(length)
                    response['Content-Range'] = f'bytes {first_byte}-{last_byte}/{file_size}'
                    response['Accept-Ranges'] = 'bytes'
                    response['Content-Disposition'] = 'inline'
                    
                    file_handle.close()
                    return response
            
            # Full file response
            file_handle = open(file_path, 'rb')
            response = FileResponse(file_handle, content_type=content_type)
            response['Content-Length'] = str(file_size)
            response['Accept-Ranges'] = 'bytes'
            response['Content-Disposition'] = 'inline'
            response['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
            response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
            
            return response
            
        except VideoFile.DoesNotExist:
            return HttpResponse('Video not found', status=404)
        except Exception as e:
            logger.error(f'Error streaming video: {str(e)}', exc_info=True)
            return HttpResponse(f'Error: {str(e)}', status=500)
    
    def copy_to_playout_action(self, request, queryset):
        """Action to copy selected videos to playout."""
        from .utils import check_duplicate_before_copy
        
        success_count = 0
        error_count = 0
        
        # Get destination storage
        destination = StorageLocation.objects.filter(
            storage_type='PLAYOUT',
            is_active=True
        ).first()
        
        if not destination:
            self.message_user(request, 'No PLAYOUT storage configured', level='error')
            return
        
        for video in queryset:
            # Check for duplicates if copying to ARCHIVE
            if destination.storage_type == 'ARCHIVE':
                is_dup, existing, msg = check_duplicate_before_copy(video, destination)
                if is_dup:
                    self.message_user(
                        request,
                        f'{video.number}: Cannot copy - {msg}',
                        level='error'
                    )
                    error_count += 1
                    continue
            
            success, message = copy_video_to_playout(video, destination, user=request.user)
            if success:
                success_count += 1
            else:
                error_count += 1
                if 'already exists' not in message.lower():
                    self.message_user(request, f'{video.number}: {message}', level='warning')
        
        if success_count > 0:
            self.message_user(request, f'Successfully copied {success_count} video(s) to playout')
        if error_count > 0:
            self.message_user(
                request,
                f'{error_count} video(s) failed or already in playout',
                level='warning'
            )
    copy_to_playout_action.short_description = _('Copy to playout storage')
    
    def update_metadata_action(self, request, queryset):
        """Action to update metadata for selected videos."""
        from django.utils import timezone
        
        success_count = 0
        error_count = 0
        
        for video in queryset:
            try:
                if not video.is_available:
                    continue
                
                metadata = extract_video_metadata(video.full_path)
                
                # Update fields
                if 'format' in metadata:
                    video.format = metadata['format']
                if 'duration' in metadata:
                    video.duration = metadata['duration']
                if 'total_bitrate' in metadata:
                    video.total_bitrate = metadata['total_bitrate']
                
                video.has_video = metadata.get('has_video', False)
                if video.has_video:
                    video.video_codec = metadata.get('video_codec', '')
                    video.fps = metadata.get('fps')
                    video.width = metadata.get('width')
                    video.height = metadata.get('height')
                
                video.has_audio = metadata.get('has_audio', False)
                if video.has_audio:
                    video.audio_codec = metadata.get('audio_codec', '')
                    video.audio_channels = metadata.get('audio_channels')
                
                video.last_scanned = timezone.now()
                video.save()
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f'Error updating metadata for {video.number}: {str(e)}')
        
        if success_count > 0:
            self.message_user(request, f'Updated metadata for {success_count} video(s)')
        if error_count > 0:
            self.message_user(request, f'{error_count} error(s) occurred', level='error')
    update_metadata_action.short_description = _('Update metadata')
    
    def verify_integrity_action(self, request, queryset):
        """Action to verify file integrity."""
        success_count = 0
        error_count = 0
        
        for video in queryset:
            if not video.checksum:
                self.message_user(
                    request,
                    f'{video.number}: No checksum stored',
                    level='warning'
                )
                continue
            
            is_valid, message = verify_file_integrity(video)
            if is_valid:
                success_count += 1
            else:
                error_count += 1
                self.message_user(
                    request,
                    f'{video.number}: {message}',
                    level='error'
                )
        
        if success_count > 0:
            self.message_user(request, f'{success_count} video(s) verified successfully')
        if error_count > 0:
            self.message_user(request, f'{error_count} video(s) failed verification', level='error')
    verify_integrity_action.short_description = _('Verify file integrity')
    
    @admin.action(description=_('Mark selected as primary version'))
    def mark_as_primary_action(self, request, queryset):
        """Mark selected videos as primary (keep), find and report duplicates."""
        # Group by number
        by_number = {}
        for video in queryset:
            if video.number not in by_number:
                by_number[video.number] = []
            by_number[video.number].append(video)
        
        for number, videos in by_number.items():
            if len(videos) > 1:
                self.message_user(
                    request,
                    f'Multiple videos selected for number {number}. Please select only one per number.',
                    level='error'
                )
                continue
            
            primary = videos[0]
            all_versions = VideoFile.objects.filter(number=number).exclude(id=primary.id)
            
            if all_versions.exists():
                self.message_user(
                    request,
                    f'Video #{number} marked as primary. Found {all_versions.count()} duplicate(s) in: {", ".join([v.storage_location.name for v in all_versions])}',
                    level='success'
                )
    
    @admin.action(description=_('Delete duplicate versions (keep best quality)'))
    def delete_duplicates_action(self, request, queryset):
        """Delete duplicate versions, keeping the best quality one."""
        # Get unique numbers from selection
        numbers = set(queryset.values_list('number', flat=True))
        
        deleted_count = 0
        kept_count = 0
        
        for number in numbers:
            versions = VideoFile.objects.filter(number=number).select_related('storage_location')
            if versions.count() <= 1:
                continue
            
            # Find primary version
            storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
            primary = max(versions, key=lambda v: (
                storage_priority.get(v.storage_location.storage_type, 0),
                v.total_bitrate or 0,
                v.created_at
            ))
            
            # Delete others
            duplicates = versions.exclude(id=primary.id)
            for dup in duplicates:
                # Log before deletion
                logger.info(f'Deleting duplicate video {dup.number} from {dup.storage_location.name}')
                dup.delete()
                deleted_count += 1
            
            kept_count += 1
        
        self.message_user(
            request,
            f'Deleted {deleted_count} duplicate(s), kept {kept_count} primary version(s)',
            level='success'
        )
    
    @admin.action(description=_('Move to archive storage'))
    def move_to_archive_action(self, request, queryset):
        """Move selected videos to archive storage."""
        from .utils import move_video_to_archive, has_system_attributes, is_file_in_use
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for video in queryset:
            # Only process playout videos
            if video.storage_location.storage_type != 'PLAYOUT':
                self.message_user(
                    request,
                    f'{video.number}: Not in playout storage, skipping',
                    level='warning'
                )
                skipped_count += 1
                continue
            
            # Check if file is still in use
            if has_system_attributes(video.full_path):
                self.message_user(
                    request,
                    f'{video.number}: Has system attributes - still in use by playout system',
                    level='warning'
                )
                skipped_count += 1
                continue
            
            if is_file_in_use(video.full_path):
                self.message_user(
                    request,
                    f'{video.number}: File is locked - still in use',
                    level='warning'
                )
                skipped_count += 1
                continue
            
            success, message = move_video_to_archive(video, user=request.user)
            if success:
                success_count += 1
            else:
                error_count += 1
                self.message_user(request, f'{video.number}: {message}', level='error')
        
        if success_count > 0:
            self.message_user(request, f'Successfully moved {success_count} video(s) to archive')
        if skipped_count > 0:
            self.message_user(request, f'{skipped_count} video(s) skipped (still in use)', level='warning')
        if error_count > 0:
            self.message_user(request, f'{error_count} video(s) failed to move', level='error')


@admin.register(FileOperation)
class FileOperationAdmin(admin.ModelAdmin):
    """Admin interface for file operations (read-only)."""

    list_display = [
        'video_file', 'operation_type', 'status',
        'source_location', 'destination_location',
        'performed_by', 'performed_at'
    ]
    list_filter = [
        'operation_type', 'status',
        ('performed_at', DateRangeFilter),
        'source_location', 'destination_location'
    ]
    search_fields = ['video_file__number', 'video_file__filename', 'error_message']
    readonly_fields = [
        'video_file', 'operation_type', 'source_location', 'destination_location',
        'performed_by', 'performed_at', 'status', 'error_message', 'details'
    ]
    
    fieldsets = (
        (None, {
            'fields': (
                'video_file', 'operation_type', 'status',
                'source_location', 'destination_location'
            )
        }),
        (_('Execution'), {
            'fields': ('performed_by', 'performed_at')
        }),
        (_('Details'), {
            'fields': ('error_message', 'details'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable add permission."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable delete permission."""
        return False


# Add System Management as a proxy model like in planung
from .admin_commands import system_management_view
from django.http import HttpResponseRedirect
from django.urls import reverse


class SystemManagementProxy(VideoFile):
    """Proxy model to show System Management in admin menu."""
    
    class Meta:
        verbose_name = _('🎛️ System Management')
        verbose_name_plural = _('🎛️ System Management')
        proxy = True


@admin.register(SystemManagementProxy)
class SystemManagementProxyAdmin(admin.ModelAdmin):
    """Admin for System Management proxy model."""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_staff
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to System Management page."""
        url = reverse('admin:media_files_system_management')
        return HttpResponseRedirect(url)
