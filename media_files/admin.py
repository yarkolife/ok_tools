"""Admin interface for media files."""

import logging
import os
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from rangefilter.filters import DateRangeFilter

from .models import StorageLocation, VideoFile, FileOperation, VideoPreset, PresetOverlay, VideoEncodePreset, POSITION_PRESET_CHOICES
from .utils import verify_file_integrity, extract_video_metadata, extract_video_metadata_fast, extract_number_from_filename, calculate_checksum, copy_file_with_progress, copy_video_to_playout
from media_files.management.commands.render_video_preset import _apply_metadata, _ensure_unique_output_relpath
from media_files.rendering.ffmpeg import (
    FfmpegError,
    render_with_intro_outro,
    render_with_overlays_on_main_edges,
    render_preview_overlays_on_main_edges,
)
from media_files.rendering.presets import load_encode_preset, load_style_preset, resolve_preset_asset_path, OverlayLayer
from media_files.rendering.templates import build_template_context


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
                    metadata = extract_video_metadata_fast(file_path)
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
                    metadata = extract_video_metadata_fast(file_path_manual)
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
    classes = ('collapse',)  # Collapsed by default
    
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
    change_list_template = 'admin/media_files/storagelocation/change_list.html'
    
    fieldsets = (
        (None, {
            'fields': ('name', 'storage_type', 'path', 'unc_path', 'is_active')
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
            path(
                '<int:storage_id>/scan-options/',
                self.admin_site.admin_view(self.scan_storage_options_view),
                name='media_files_storagelocation_scan_options',
            ),
        ]
        return custom_urls + urls
    
    def video_count_display(self, obj):
        """Display video count with link and scan button."""
        count = obj.video_count
        scan_url = reverse('admin:media_files_storagelocation_scan_options', args=[obj.id])
        
        if count > 0:
            list_url = reverse('admin:media_files_videofile_changelist') + f'?storage_location__id__exact={obj.id}'
            return format_html(
                '<a href="{}">{}</a> | <button type="button" onclick="openScanModal({}, \'{}\', \'{}\', \'{}\', {})" class="button" style="padding: 3px 10px; margin-left: 5px;">🔍 Scan</button>',
                list_url, count, obj.id, obj.name, obj.path, obj.storage_type, obj.video_count
            )
        return format_html(
            '{} | <button type="button" onclick="openScanModal({}, \'{}\', \'{}\', \'{}\', {})" class="button" style="padding: 3px 10px; margin-left: 5px;">🔍 Scan</button>',
            count, obj.id, obj.name, obj.path, obj.storage_type, obj.video_count
        )
    video_count_display.short_description = _('Videos')
    
    def scan_storage_view(self, request, storage_id):
        """View to scan a single storage location."""
        from django.shortcuts import redirect
        from django.contrib import messages
        from django.core.management import call_command
        from django.http import JsonResponse
        from io import StringIO
        
        try:
            storage = StorageLocation.objects.get(id=storage_id)
            
            # Get scan options from request parameters (both GET and POST)
            scan_options = {}
            if request.GET.get('force') or request.POST.get('force'):
                scan_options['force'] = True
            if request.GET.get('strict_check') or request.POST.get('strict_check'):
                scan_options['strict_check'] = True
            if request.GET.get('skip_metadata') or request.POST.get('skip_metadata'):
                scan_options['skip_metadata'] = True
            if request.GET.get('calculate_checksum') or request.POST.get('calculate_checksum'):
                scan_options['calculate_checksum'] = True
            if request.GET.get('delete_missing') or request.POST.get('delete_missing'):
                scan_options['delete_missing'] = True
            
            # Capture command output
            out = StringIO()
            call_command('scan_video_storage', storage_id=storage_id, stdout=out, **scan_options)
            output = out.getvalue()
            
            # Parse output for statistics
            lines = output.split('\n')
            stats = {'created': 0, 'updated': 0, 'found': 0, 'skipped': 0, 'deleted': 0, 'marked_unavailable': 0}
            for line in lines:
                if 'Created:' in line:
                    stats['created'] += 1
                elif 'Updated:' in line or 'updated' in line.lower():
                    stats['updated'] += 1
                elif 'Skipped:' in line or 'skipped' in line.lower():
                    stats['skipped'] += 1
                elif 'Deleted (file missing):' in line or 'deleted (file missing)' in line.lower():
                    stats['deleted'] += 1
                elif 'Marked unavailable:' in line or 'marked unavailable' in line.lower():
                    stats['marked_unavailable'] += 1
                elif 'Total files found:' in line:
                    try:
                        stats['found'] = int(line.split(':')[1].strip())
                    except:
                        pass
                elif 'Records deleted (files missing):' in line:
                    try:
                        stats['deleted'] = int(line.split(':')[1].strip())
                    except:
                        pass
                elif 'Records marked unavailable:' in line:
                    try:
                        stats['marked_unavailable'] = int(line.split(':')[1].strip())
                    except:
                        pass
            
            success_parts = [
                f'✓ {_("Scanning completed")}: {storage.name}',
                f'{_("Found")}: {stats["found"]} {_("files")}',
                f'{_("Created")}: {stats["created"]} {_("records")}',
                f'{_("Updated")}: {stats["updated"]} {_("records")}',
                f'{_("Skipped")}: {stats["skipped"]} {_("files")} ({_("no changes")})'
            ]
            
            if stats['deleted'] > 0:
                success_parts.append(f'{_("Deleted")}: {stats["deleted"]} {_("records")} ({_("files missing")})')
            if stats['marked_unavailable'] > 0:
                success_parts.append(f'{_("Marked unavailable")}: {stats["marked_unavailable"]} {_("records")}')
            
            success_message = ' | '.join(success_parts)
            
            # If it's an AJAX request, return JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'stats': stats
                })
            
            # Otherwise, redirect with message
            messages.success(request, success_message)
            
        except StorageLocation.DoesNotExist:
            error_message = _('Storage location #{} not found').format(storage_id)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
                return JsonResponse({'success': False, 'message': error_message})
            messages.error(request, error_message)
        except Exception as e:
            error_message = _('Error scanning storage: {}').format(str(e))
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
                return JsonResponse({'success': False, 'message': error_message})
            messages.error(request, error_message)
        
        return redirect('admin:media_files_storagelocation_changelist')
    
    def scan_storage_options_view(self, request, storage_id):
        """View to show scan options for a storage location."""
        from django.shortcuts import render
        from django.contrib import messages
        
        try:
            storage = StorageLocation.objects.get(id=storage_id)
        except StorageLocation.DoesNotExist:
            messages.error(request, _('Storage location #{} not found').format(storage_id))
            return redirect('admin:media_files_storagelocation_changelist')
        
        if request.method == 'POST':
            # Process scan with options
            scan_options = {}
            if request.POST.get('force'):
                scan_options['force'] = True
            if request.POST.get('strict_check'):
                scan_options['strict_check'] = True
            if request.POST.get('skip_metadata'):
                scan_options['skip_metadata'] = True
            if request.POST.get('calculate_checksum'):
                scan_options['calculate_checksum'] = True
            if request.POST.get('delete_missing'):
                scan_options['delete_missing'] = True
            
            # Redirect to scan with options as GET parameters
            from django.urls import reverse
            from urllib.parse import urlencode
            scan_url = reverse('admin:media_files_storagelocation_scan', args=[storage_id])
            if scan_options:
                scan_url += '?' + urlencode(scan_options)
            return redirect(scan_url)
        
        context = {
            'storage': storage,
            'title': _('Scan Options - {}').format(storage.name),
            'site_header': self.admin_site.site_header,
            'site_title': self.admin_site.site_title,
        }
        return render(request, 'admin/media_files/storagelocation/scan_options.html', context)
    
    def scan_storage(self, request, queryset):
        """Action to scan selected storage locations."""
        from django.core.management import call_command
        
        for storage in queryset:
            try:
                call_command('scan_video_storage', storage_id=storage.id)
                self.message_user(request, _('Successfully scanned: {}').format(storage.name))
            except Exception as e:
                self.message_user(request, _('Error scanning {}: {}').format(storage.name, str(e)), level='error')
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
        from django.db.models import Case, When, IntegerField, Max, OuterRef, Subquery, F, Value, Count
        from django.utils import timezone
        from datetime import datetime
        
        if not self.value():
            return queryset
        
        # Find numbers that have duplicates
        duplicated_numbers = VideoFile.objects.values('number').annotate(
            count=Count('number')
        ).filter(count__gt=1).values_list('number', flat=True)
        
        if not duplicated_numbers:
            # No duplicates, so all are primary
            if self.value() == 'primary':
                return queryset
            else:
                return queryset.none()
        
        # Filter to only videos with duplicates
        queryset = queryset.filter(number__in=duplicated_numbers)
        
        # Use Python-based approach for reliability (works correctly with complex queries)
        # Don't use SQL annotations that can cause integer overflow - calculate everything in Python
        # Get all videos with duplicates and determine primary in memory
        try:
            # Load videos without any complex annotations to avoid integer overflow
            videos_list = list(queryset.select_related('storage_location').only(
                'id', 'number', 'total_bitrate', 'created_at', 'last_scanned', 'updated_at',
                'storage_location__storage_type', 'is_manual_primary'
            ))
        except Exception as e:
            logger.error(f'Error loading videos for IsPrimaryVersionFilter: {e}')
            # Fallback: return empty queryset to avoid 500 error
            return queryset.none()
        
        # Group by number and find primary for each group
        by_number = {}
        for video in videos_list:
            if video.number not in by_number:
                by_number[video.number] = []
            by_number[video.number].append(video)
        
        # Determine primary versions
        primary_ids = set()
        duplicate_ids = set()
        
        storage_priority_map = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
        
        for number, video_list in by_number.items():
            try:
                # Check if any version is manually marked as primary
                manual_primary = next((v for v in video_list if getattr(v, 'is_manual_primary', False)), None)
                if manual_primary:
                    primary_ids.add(manual_primary.id)
                    duplicate_ids.update(v.id for v in video_list if v.id != manual_primary.id)
                    continue
                
                # Find best version with safe handling of None values
                def get_sort_key(v):
                    # Safely get storage type
                    storage_type = 'CUSTOM'
                    if v.storage_location and hasattr(v.storage_location, 'storage_type'):
                        storage_type = v.storage_location.storage_type or 'CUSTOM'
                    
                    # Get priority
                    priority = storage_priority_map.get(storage_type, 1)
                    
                    # Get bitrate (default to 0)
                    bitrate = v.total_bitrate if v.total_bitrate is not None else 0
                    
                    # Get date (use earliest possible date if all are None)
                    date = v.created_at or v.last_scanned or v.updated_at
                    if date is None:
                        # Use a very old date as fallback
                        date = datetime(1970, 1, 1, tzinfo=timezone.utc)
                    
                    return (date, bitrate, priority)
                
                best_video = max(video_list, key=get_sort_key)
                primary_ids.add(best_video.id)
                duplicate_ids.update(v.id for v in video_list if v.id != best_video.id)
            except Exception as e:
                logger.error(f'Error determining primary version for number {number}: {e}')
                # If we can't determine, mark all as duplicates (safer than failing)
                duplicate_ids.update(v.id for v in video_list)
        
        # Filter based on selection
        if self.value() == 'primary':
            if primary_ids:
                return queryset.filter(id__in=primary_ids)
            else:
                return queryset.none()
        
        if self.value() == 'duplicate':
            if duplicate_ids:
                return queryset.filter(id__in=duplicate_ids)
            else:
                return queryset.none()
        
        return queryset


class FPSFilter(admin.SimpleListFilter):
    title = _('FPS')
    parameter_name = 'fps'
    
    def lookups(self, request, model_admin):
        return (
            ('25', _('25 fps (Broadcast Standard)')),
            ('not_25', _('Not 25 fps (⚠ Warning)')),
            ('missing', _('FPS not set')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == '25':
            return queryset.filter(fps=25.0)
        elif self.value() == 'not_25':
            return queryset.exclude(fps=25.0).exclude(fps__isnull=True)
        elif self.value() == 'missing':
            return queryset.filter(fps__isnull=True)
        return queryset


@admin.register(VideoFile)
class VideoFileAdmin(admin.ModelAdmin):
    """Admin interface for video files."""

    form = VideoFileAdminForm
    change_form_template = 'admin/media_files/videofile/change_form.html'
    change_list_template = 'admin/media_files/videofile/change_list.html'
    delete_selected_confirmation_template = 'admin/media_files/videofile/delete_selected_confirmation.html'
    
    list_display = [
        'duplicates_indicator', 'filename', 'storage_location', 'number', 'resolution_display',
        'duration_display', 'fps_display', 'file_size_display', 'format',
        'is_available', 'player_link'
    ]
    list_filter = [
        'storage_location', 'format', 'is_available',
        ('created_at', DateRangeFilter),
        'has_video', 'has_audio',
        HasDuplicatesFilter, IsPrimaryVersionFilter, FPSFilter
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
                'video_bitrate', 'video_bitrate_display', 'video_bitrate_mode', 'fps',
                'width', 'height', 'resolution_display', 'aspect_ratio',
                'pixel_format', 'color_space', 'color_range', 'chroma_subsampling',
                'audio_codec', 'audio_codec_long', 'audio_bitrate', 'audio_bitrate_display',
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
                (_('Video Player'), {
                    'fields': ('video_player',)
                }),
                (_('File Properties'), {
                    'fields': (
                        'format', 'file_size_mb', 'duration',
                        'checksum', 'last_modified', 'last_scanned'
                    )
                }),
                (_('Video Properties'), {
                    'fields': (
                        'has_video', 'video_codec', 'video_codec_long', 'video_profile',
                        'video_bitrate_display', 'video_bitrate_mode', 'fps',
                        'width', 'height', 'resolution_display', 'aspect_ratio',
                        'pixel_format', 'color_space', 'color_range', 'chroma_subsampling',
                        'bitrate_mbps'
                    )
                }),
                (_('Audio Properties'), {
                    'fields': (
                        'has_audio', 'audio_codec', 'audio_codec_long', 'audio_bitrate_display',
                        'audio_sample_rate', 'audio_channels', 'audio_channel_layout'
                    )
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
               'mark_as_primary_action', 'delete_duplicates_action', 'move_to_archive_action',
               'cleanup_missing_files_action', 'render_default_preset_action', 'render_preview_default_action',
               'delete_records_without_video_action', 'render_with_intro_outro_full_overlays_action']

    def get_actions(self, request):
        """Hide rendering actions when the feature flag is disabled."""
        actions = super().get_actions(request)
        if not getattr(settings, "VIDEO_OVERLAY_RENDERING_ENABLED", False):
            actions.pop("render_default_preset_action", None)
            actions.pop("render_preview_default_action", None)
        return actions

    @admin.action(description=_('Render video (default presets)'))
    def render_default_preset_action(self, request, queryset):
        """
        Render selected videos using default presets.

        This is intentionally minimal. For full control, use the management command
        `python manage.py render_video_preset ...`.
        """
        if not getattr(settings, "VIDEO_OVERLAY_RENDERING_ENABLED", False):
            self.message_user(
                request,
                _(
                    "Video overlay rendering is disabled. Set VIDEO_OVERLAY_RENDERING_ENABLED=true to enable it."
                ),
                level=messages.ERROR,
            )
            return

        style_name = "overlay_only_center_left_v1"
        encode_name = "1080p25_9000k"

        try:
            style = load_style_preset(style_name)
            encode = load_encode_preset(encode_name)
        except Exception as e:
            self.message_user(
                request,
                _("Failed to load presets: {err}").format(err=str(e)),
                level=messages.ERROR,
            )
            return

        intro_clip = resolve_preset_asset_path(style.intro_clip) if style.intro_clip else None
        outro_clip = resolve_preset_asset_path(style.outro_clip) if style.outro_clip else None

        if intro_clip and not os.path.exists(intro_clip):
            self.message_user(request, _("Intro clip not found: {p}").format(p=intro_clip), level=messages.ERROR)
            return
        if outro_clip and not os.path.exists(outro_clip):
            self.message_user(request, _("Outro clip not found: {p}").format(p=outro_clip), level=messages.ERROR)
            return

        rendered = 0
        failed = 0

        for source in queryset:
            license_obj = source.get_license()
            if not license_obj:
                failed += 1
                continue

            logger.info(
                "Rendering video %s with presets style=%s encode=%s (intro=%s outro=%s)",
                source.full_path,
                style.name,
                encode.name,
                bool(intro_clip),
                bool(outro_clip),
            )

            storage_root = Path(source.storage_location.path)
            rel_dir = Path("rendered") / style.name / encode.name
            src_stem = Path(source.filename).stem
            out_name = f"{src_stem}__rendered__{style.name}__{encode.name}.mp4"
            rel_out = _ensure_unique_output_relpath(source.storage_location, source.number, rel_dir / out_name)
            abs_out = storage_root / rel_out
            abs_out.parent.mkdir(parents=True, exist_ok=True)

            new_video = VideoFile.objects.create(
                number=source.number,
                filename=abs_out.name,
                file_path=str(rel_out).replace("\\", "/"),
                storage_location=source.storage_location,
                is_available=True,
            )

            operation = FileOperation.objects.create(
                video_file=new_video,
                operation_type="RENDER",
                source_location=source.storage_location,
                destination_location=source.storage_location,
                performed_by=request.user,
                status="IN_PROGRESS",
                details={
                    "source_video_id": source.id,
                    "style": style.name,
                    "encode": encode.name,
                    "intro_clip": intro_clip,
                    "outro_clip": outro_clip,
                },
            )

            try:
                ctx = build_template_context(license_obj)
                if intro_clip and outro_clip:
                    render_with_intro_outro(
                        intro_video=intro_clip,
                        main_video=source.full_path,
                        outro_video=outro_clip,
                        output_mp4=str(abs_out),
                        encode=encode,
                        intro_layers=style.intro_overlays,
                        outro_layers=style.outro_overlays,
                        ctx=ctx,
                    )
                else:
                    render_with_overlays_on_main_edges(
                        main_video=source.full_path,
                        output_mp4=str(abs_out),
                        encode=encode,
                        intro_layers=style.intro_overlays,
                        outro_layers=style.outro_overlays,
                        ctx=ctx,
                        segment_duration=style.segment_duration,
                    )
                _apply_metadata(new_video, str(abs_out))
                new_video.save()
                operation.status = "SUCCESS"
                operation.save(update_fields=["status"])
                logger.info("Rendered output: %s (VideoFile id=%s)", str(abs_out), new_video.id)
                rendered += 1
            except FfmpegError as e:
                failed += 1
                new_video.is_available = False
                new_video.save(update_fields=["is_available"])
                operation.status = "FAILED"
                operation.error_message = str(e)
                operation.save(update_fields=["status", "error_message"])
                logger.error("Render failed for %s: %s", source.full_path, str(e))

        if rendered:
            self.message_user(
                request,
                _("Rendered successfully: {n}").format(n=rendered),
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                _("Failed: {n}").format(n=failed),
                level=messages.WARNING,
            )

    @admin.action(description=_('Render preview (10s)'))
    def render_preview_default_action(self, request, queryset):
        """
        Render a fast 10-second preview (5s start + 5s end) using default presets.

        Intended for quick visual verification of overlays.
        """
        if not getattr(settings, "VIDEO_OVERLAY_RENDERING_ENABLED", False):
            self.message_user(
                request,
                _(
                    "Video overlay rendering is disabled. Set VIDEO_OVERLAY_RENDERING_ENABLED=true to enable it."
                ),
                level=messages.ERROR,
            )
            return

        style_name = "overlay_only_center_left_v1"
        encode_name = "1080p25_9000k"
        preview_seconds = 5.0

        try:
            style = load_style_preset(style_name)
            encode = load_encode_preset(encode_name)
        except Exception as e:
            self.message_user(
                request,
                _("Failed to load presets: {err}").format(err=str(e)),
                level=messages.ERROR,
            )
            return

        rendered = 0
        failed = 0

        for source in queryset:
            license_obj = source.get_license()
            if not license_obj:
                failed += 1
                continue

            storage_root = Path(source.storage_location.path)
            rel_dir = Path("rendered") / style.name / encode.name
            src_stem = Path(source.filename).stem
            out_name = f"{src_stem}__preview__{int(preview_seconds)}s__{style.name}__{encode.name}.mp4"
            rel_out = _ensure_unique_output_relpath(source.storage_location, source.number, rel_dir / out_name)
            abs_out = storage_root / rel_out
            abs_out.parent.mkdir(parents=True, exist_ok=True)

            new_video = VideoFile.objects.create(
                number=source.number,
                filename=abs_out.name,
                file_path=str(rel_out).replace("\\", "/"),
                storage_location=source.storage_location,
                is_available=True,
            )

            operation = FileOperation.objects.create(
                video_file=new_video,
                operation_type="RENDER",
                source_location=source.storage_location,
                destination_location=source.storage_location,
                performed_by=request.user,
                status="IN_PROGRESS",
                details={
                    "source_video_id": source.id,
                    "style": style.name,
                    "encode": encode.name,
                    "preview": True,
                    "preview_seconds": preview_seconds,
                },
            )

            try:
                logger.info(
                    "Rendering PREVIEW for %s with presets style=%s encode=%s",
                    source.full_path,
                    style.name,
                    encode.name,
                )
                ctx = build_template_context(license_obj)
                render_preview_overlays_on_main_edges(
                    main_video=source.full_path,
                    output_mp4=str(abs_out),
                    encode=encode,
                    intro_layers=style.intro_overlays,
                    outro_layers=style.outro_overlays,
                    ctx=ctx,
                    segment_duration=preview_seconds,
                )
                _apply_metadata(new_video, str(abs_out))
                new_video.save()
                operation.status = "SUCCESS"
                operation.save(update_fields=["status"])
                logger.info("Rendered preview output: %s (VideoFile id=%s)", str(abs_out), new_video.id)
                rendered += 1
            except FfmpegError as e:
                failed += 1
                new_video.is_available = False
                new_video.save(update_fields=["is_available"])
                operation.status = "FAILED"
                operation.error_message = str(e)
                operation.save(update_fields=["status", "error_message"])
                logger.error("Preview render failed for %s: %s", source.full_path, str(e))

        if rendered:
            self.message_user(
                request,
                _("Rendered successfully: {n}").format(n=rendered),
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                _("Failed: {n}").format(n=failed),
                level=messages.WARNING,
            )
    
    @admin.action(description=_('Delete selected records without video'))
    def delete_records_without_video_action(self, request, queryset):
        """
        Delete VideoFile records for selected entries where the video file does not exist on disk.
        
        Only deletes database records, not physical files. Checks if file exists before deletion.
        """
        from django.db import connection
        
        deleted_count = 0
        found_count = 0
        error_count = 0
        read_only_count = 0
        
        for video in queryset:
            try:
                # Check if file exists on disk (handle read-only storage gracefully)
                file_exists = False
                try:
                    file_exists = os.path.exists(video.full_path)
                    found_count += 1
                except (OSError, PermissionError, IOError) as e:
                    # Storage might be read-only - skip this file
                    read_only_count += 1
                    logger.debug(f'Could not check file existence for {video.full_path}: {e}')
                    continue
                except Exception as e:
                    # Any other error - log and skip
                    read_only_count += 1
                    logger.warning(f'Unexpected error checking file {video.full_path}: {e}')
                    continue
                
                if not file_exists:
                    # Delete related FileOperation objects using raw SQL
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "DELETE FROM media_files_fileoperation WHERE video_file_id = %s",
                                [video.id]
                            )
                    except Exception as e:
                        logger.error(f'Error deleting FileOperation for video {video.id}: {e}')
                        # Continue anyway - will be cascade deleted
                    
                    # Delete the VideoFile
                    video.delete()
                    deleted_count += 1
                    logger.info(f'Deleted VideoFile {video.number} (file missing): {video.filename}')
            
            except Exception as e:
                error_count += 1
                logger.error(f'Error checking/deleting {video.filename}: {str(e)}')
        
        if deleted_count > 0:
            self.message_user(
                request,
                _('Deleted {} record(s) without video files').format(deleted_count),
                level='success',
            )
        if read_only_count > 0:
            self.message_user(
                request,
                _('{} file(s) could not be checked (storage may be read-only)').format(read_only_count),
                level='info',
            )
        if found_count == 0:
            self.message_user(
                request,
                _('No files could be checked'),
                level='info',
            )
        elif deleted_count == 0 and read_only_count == 0:
            self.message_user(
                request,
                _('All checked files exist on disk'),
                level='info',
            )
        if error_count > 0:
            self.message_user(
                request,
                _('{} error(s) occurred').format(error_count),
                level='error',
            )

    @admin.action(description=_('Render with intro/outro and full overlays'))
    def render_with_intro_outro_full_overlays_action(self, request, queryset):
        """
        Render selected videos with intro/outro clips and full text overlays
        (title, subtitle, broadcast responsibility, media authority).
        
        Uses intro.mp4 and outro.mp4 from docker-local/data/media/intro_outro/
        and applies all text overlays to them.
        """
        if not getattr(settings, "VIDEO_OVERLAY_RENDERING_ENABLED", False):
            self.message_user(
                request,
                _(
                    "Video overlay rendering is disabled. Set VIDEO_OVERLAY_RENDERING_ENABLED=true to enable it."
                ),
                level=messages.ERROR,
            )
            return

        encode_name = "1080p25_9000k"

        try:
            encode = load_encode_preset(encode_name)
        except Exception as e:
            self.message_user(
                request,
                _("Failed to load encode preset: {err}").format(err=str(e)),
                level=messages.ERROR,
            )
            return

        # Find intro and outro files
        # In production: ./data/media is mounted to /app/media
        # In local dev: docker-local/data/media is mounted to /app/media
        # Files should be placed in: <media_root>/intro_outro/intro.mp4 and outro.mp4
        
        media_root = Path(settings.MEDIA_ROOT)
        base_dir = Path(settings.BASE_DIR)
        
        # Build list of candidate paths in order of preference
        # 1. MEDIA_ROOT/intro_outro/ (works for both production and local)
        # 2. /app/media/intro_outro/ (Docker path - production and local)
        # 3. BASE_DIR relative paths (for local development)
        
        intro_candidates = [
            # Primary: MEDIA_ROOT (works everywhere)
            media_root / "intro_outro" / "intro.mp4",
            # Docker paths (production: ./data/media -> /app/media, local: docker-local/data/media -> /app/media)
            Path("/app/media/intro_outro/intro.mp4"),
            # Local development paths (relative to BASE_DIR)
            base_dir / "docker-local" / "data" / "media" / "intro_outro" / "intro.mp4",
            base_dir / "media" / "intro_outro" / "intro.mp4",
        ]
        outro_candidates = [
            # Primary: MEDIA_ROOT (works everywhere)
            media_root / "intro_outro" / "outro.mp4",
            # Docker paths (production: ./data/media -> /app/media, local: docker-local/data/media -> /app/media)
            Path("/app/media/intro_outro/outro.mp4"),
            # Local development paths (relative to BASE_DIR)
            base_dir / "docker-local" / "data" / "media" / "intro_outro" / "outro.mp4",
            base_dir / "media" / "intro_outro" / "outro.mp4",
        ]
        
        intro_path = None
        outro_path = None
        
        for candidate in intro_candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    intro_path = str(candidate.resolve())
                    logger.info(f"Found intro file at: {intro_path}")
                    break
            except (OSError, ValueError):
                continue
        
        for candidate in outro_candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    outro_path = str(candidate.resolve())
                    logger.info(f"Found outro file at: {outro_path}")
                    break
            except (OSError, ValueError):
                continue

        if not intro_path or not outro_path:
            missing = []
            if not intro_path:
                missing.append("intro.mp4")
            if not outro_path:
                missing.append("outro.mp4")
            
            # Provide helpful error message with correct paths for production and local
            media_root_str = str(media_root)
            error_msg = _(
                "Intro/outro files not found: {files}.\n\n"
                "Please place the files in one of these locations:\n"
                "- Production: <deployment_dir>/data/media/intro_outro/\n"
                "- Local dev: docker-local/data/media/intro_outro/\n"
                "- Or: {media_root}/intro_outro/\n\n"
                "Files will be accessible at /app/media/intro_outro/ inside the container."
            ).format(
                files=", ".join(missing),
                media_root=media_root_str
            )
            self.message_user(
                request,
                error_msg,
                level=messages.ERROR,
            )
            return

        # Create full overlay layers for intro and outro
        # Requirements:
        # - Title: centered, large font, no box
        # - Subtitle: centered, smaller font, only if title is not too long (not 3+ lines)
        # - Broadcast responsibility: right-aligned, y=882, fontsize=50
        # - Media authority: right-aligned, y=947, fontsize=38
        
        # Default font file (will be resolved by the rendering system)
        default_font = "fonts/Roboto-Bold.ttf"
        regular_font = "fonts/Roboto-Regular.ttf"
        
        # Helper function to create intro/outro overlays dynamically
        # We'll create overlays that check title length at render time
        def create_title_subtitle_overlays():
            """Create title and subtitle overlays with conditional subtitle display."""
            from media_files.rendering.templates import _wrap_text
            
            # We need to check title length, but we don't have context here
            # So we'll use a template that will be evaluated at render time
            # Title overlay - always shown, with proper wrapping
            title_overlay = OverlayLayer(
                type="text",
                template="{license.title_wrapped}",  # Will be created dynamically
                x="(w-text_w)/2",
                y="(h-text_h)/2-60",  # Centered vertically, slightly above center
                start=0.0,
                end=5.0,
                animation="fade",
                fade_in=0.6,
                fade_out=0.6,
                fontsize=64,  # Large font for title
                fontcolor="white",
                fontfile=default_font,
                box=False,  # No box
            )
            
            # Subtitle overlay - will be conditionally shown
            # We'll use a special template that checks title length
            subtitle_overlay = OverlayLayer(
                type="text",
                template="{license.subtitle_conditional}",  # Will check if title is short
                x="(w-text_w)/2",
                y="(h-text_h)/2+40",  # Below title
                start=0.2,
                end=5.0,
                animation="fade",
                fade_in=0.5,
                fade_out=0.4,
                fontsize=48,  # Smaller font for subtitle
                fontcolor="white",
                fontfile=regular_font,
                box=False,
            )
            
            return [title_overlay, subtitle_overlay]
        
        # Intro overlays
        # Position text below logo (approximately 3 lines down from top)
        # For 1080p: logo is typically at y~250, text should start at y~400
        intro_overlays = [
            # Title - centered horizontally and vertically
            OverlayLayer(
                type="text",
                template="{license.title_wrapped_short}",  # Max 3 lines, ~30 chars per line
                x="(W-text_w)/2",  # Proper horizontal centering
                y="(H/2)-72",  # Centered vertically, accounting for 3-line title block
                start=0.0,
                end=5.0,
                animation="fade",
                fade_in=0.6,
                fade_out=0.6,
                fontsize=64,  # Large font for title
                fontcolor="white",
                fontfile=default_font,
                box=False,  # No box
            ),
            # Subtitle - centered horizontally, below title
            OverlayLayer(
                type="text",
                template="{license.subtitle_wrapped}",  # Only shown if title < 3 lines
                x="(W-text_w)/2",  # Proper horizontal centering
                y="(H/2)+180",  # Below title (allows for 3-line title block, ~252px spacing)
                start=0.2,
                end=5.0,
                animation="fade",
                fade_in=0.5,
                fade_out=0.4,
                fontsize=48,  # Smaller font for subtitle
                fontcolor="white",
                fontfile=regular_font,
                box=False,  # No box
            ),
            # Broadcast responsibility - right-aligned, bottom
            OverlayLayer(
                type="text",
                template="{labels.broadcast_responsibility}: {profile.display}",
                x="w-text_w-120",  # More padding from right edge (was 97)
                y="882",
                start=0.2,
                end=5.0,
                animation="slide_up",
                fade_in=0.5,
                fade_out=0.4,
                fontsize=50,
                fontcolor="white",
                fontfile=regular_font,
            ),
            # Media authority - right-aligned, bottom
            OverlayLayer(
                type="text",
                template="{profile.media_authority_full_name}, {license.created_year}",
                x="w-text_w-120",  # More padding from right edge (was 97)
                y="947",
                start=0.2,
                end=5.0,
                animation="slide_left",
                fade_in=0.6,
                fade_out=0.4,
                fontsize=38,
                fontcolor="white",
                fontfile=regular_font,
            ),
        ]
        
        # Outro overlays (same structure as intro)
        outro_overlays = [
            # Title - centered horizontally and vertically
            OverlayLayer(
                type="text",
                template="{license.title_wrapped_short}",  # Max 3 lines, ~30 chars per line
                x="(W-text_w)/2",  # Proper horizontal centering
                y="(H/2)-72",  # Centered vertically, accounting for 3-line title block
                start=0.0,
                end=5.0,
                animation="fade",
                fade_in=0.6,
                fade_out=0.6,
                fontsize=64,  # Large font for title
                fontcolor="white",
                fontfile=default_font,
                box=False,  # No box
            ),
            # Subtitle - centered horizontally, below title
            OverlayLayer(
                type="text",
                template="{license.subtitle_wrapped}",  # Only shown if title < 3 lines
                x="(W-text_w)/2",  # Proper horizontal centering
                y="(H/2)+180",  # Below title (allows for 3-line title block, ~252px spacing)
                start=0.2,
                end=5.0,
                animation="fade",
                fade_in=0.5,
                fade_out=0.4,
                fontsize=48,  # Smaller font for subtitle
                fontcolor="white",
                fontfile=regular_font,
                box=False,  # No box
            ),
            # Broadcast responsibility
            OverlayLayer(
                type="text",
                template="{labels.broadcast_responsibility}: {profile.display}",
                x="w-text_w-120",  # More padding from right edge (was 97)
                y="882",
                start=0.2,
                end=5.0,
                animation="slide_up",
                fade_in=0.5,
                fade_out=0.4,
                fontsize=50,
                fontcolor="white",
                fontfile=regular_font,
            ),
            # Media authority
            OverlayLayer(
                type="text",
                template="{profile.media_authority_full_name}, {license.created_year}",
                x="w-text_w-120",  # More padding from right edge (was 97)
                y="947",
                start=0.2,
                end=5.0,
                animation="slide_left",
                fade_in=0.6,
                fade_out=0.4,
                fontsize=38,
                fontcolor="white",
                fontfile=regular_font,
            ),
        ]

        # Create operations and start async rendering via Celery
        created = 0
        failed = 0

        for source in queryset:
            license_obj = source.get_license()
            if not license_obj:
                failed += 1
                continue

            try:
                storage_root = Path(source.storage_location.path)
                rel_dir = Path("rendered") / "intro_outro_full" / encode.name
                src_stem = Path(source.filename).stem
                out_name = f"{src_stem}__intro_outro_full__{encode.name}.mp4"
                rel_out = _ensure_unique_output_relpath(source.storage_location, source.number, rel_dir / out_name)
                abs_out = storage_root / rel_out
                abs_out.parent.mkdir(parents=True, exist_ok=True)

                new_video = VideoFile.objects.create(
                    number=source.number,
                    filename=abs_out.name,
                    file_path=str(rel_out).replace("\\", "/"),
                    storage_location=source.storage_location,
                    is_available=False,  # Will be set to True after rendering completes
                )

                operation = FileOperation.objects.create(
                    video_file=new_video,
                    operation_type="RENDER",
                    source_location=source.storage_location,
                    destination_location=source.storage_location,
                    performed_by=request.user,
                    status="IN_PROGRESS",
                    details={
                        "source_video_id": source.id,
                        "license_number": license_obj.number,
                        "encode": encode.name,
                        "intro_clip": intro_path,
                        "outro_clip": outro_path,
                        "overlay_type": "full_intro_outro",
                    },
                )

                # Start async rendering task via Celery
                from media_files.tasks import render_video_task
                render_video_task.delay(operation.id)
                
                logger.info(
                    "Started async rendering for video %s with intro/outro and full overlays (operation_id=%s)",
                    source.full_path,
                    operation.id,
                )
                created += 1
            except Exception as e:
                failed += 1
                logger.error("Failed to create operation for %s: %s", source.full_path, str(e))

        if created:
            self.message_user(
                request,
                _("Started rendering with intro/outro and full overlays: {n} video(s). You can track progress in File Operations.").format(n=created),
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                _("Failed to start rendering: {n}").format(n=failed),
                level=messages.WARNING,
            )
    
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
    
    def duration_display(self, obj):
        """Display duration without milliseconds."""
        if obj.duration:
            # Format duration as HH:MM:SS (without microseconds)
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "-"
    duration_display.short_description = _('Duration')
    
    def fps_display(self, obj):
        """Display FPS with warning if not 25."""
        if obj.fps is None:
            return format_html('<span style="color: #999;">—</span>')
        
        fps_value = float(obj.fps)
        fps_formatted = f"{fps_value:.2f}"
        
        if fps_value == 25.0:
            return format_html('<span style="color: #28a745;">{}</span>', fps_formatted)
        else:
            warning_text = _('FPS is not 25 - not suitable for broadcast')
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;" title="{}">⚠️ {}</span>',
                warning_text,
                fps_formatted
            )
    fps_display.short_description = _('FPS')
    
    def video_bitrate_display(self, obj):
        """Display video bitrate in kbps."""
        if obj.video_bitrate:
            kbps = obj.video_bitrate / 1000
            return f"{kbps:,.0f} kbps"
        return "-"
    video_bitrate_display.short_description = _('Video Bitrate (kbps)')
    
    def audio_bitrate_display(self, obj):
        """Display audio bitrate in kbps."""
        if obj.audio_bitrate:
            kbps = obj.audio_bitrate / 1000
            return f"{kbps:,.0f} kbps"
        return "-"
    audio_bitrate_display.short_description = _('Audio Bitrate (kbps)')
    
    def license_link(self, obj):
        """Display link to associated license."""
        license_obj = obj.get_license()
        if license_obj:
            url = reverse('admin:licenses_license_change', args=[license_obj.id])
            return format_html('<a href="{}">{} - {}</a>', url, license_obj.number, license_obj.title)
        return "-"
    license_link.short_description = _('License')
    
    def duplicates_indicator(self, obj):
        """Show duplicate status indicator with version info."""
        if not obj.pk:
            return '—'
        
        # Check for duplicates (same number, any storage)
        all_versions = VideoFile.objects.filter(number=obj.number).exclude(id=obj.id)
        same_storage_versions = all_versions.filter(storage_location=obj.storage_location)
        
        if not all_versions.exists():
            return format_html('<span style="color: #6c757d;" title="{}">—</span>', _('Unique - no duplicates'))
        
        is_primary = obj.is_primary_version()
        total_count = all_versions.count()
        same_storage_count = same_storage_versions.count()
        
        # Build tooltip with version details
        tooltip_parts = []
        if same_storage_count > 0:
            tooltip_parts.append(_('{} version(s) in same storage').format(same_storage_count + 1))
        if total_count > same_storage_count:
            tooltip_parts.append(_('{} version(s) in other storages').format(total_count - same_storage_count))
        
        tooltip = ' | '.join(tooltip_parts)
        
        if is_primary:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;" title="{}">✓ PRIMARY</span><br>'
                '<span style="color: #6c757d; font-size: 0.85em;">({} {})</span>',
                tooltip,
                total_count + 1,
                _('versions total')
            )
        else:
            # Check if this is an old version (lower quality or older date)
            primary_versions = [v for v in obj.get_all_versions() if v.is_primary_version()]
            if primary_versions:
                primary = primary_versions[0]
                is_old = (
                    obj.total_bitrate and primary.total_bitrate and obj.total_bitrate < primary.total_bitrate
                ) or (
                    obj.created_at and primary.created_at and obj.created_at < primary.created_at
                )
                
                if is_old:
                    return format_html(
                        '<span style="color: #dc3545; font-weight: bold;" title="{}">⚠️ OLD VERSION</span><br>'
                        '<span style="color: #6c757d; font-size: 0.85em;">({} {})</span>',
                        tooltip,
                        total_count + 1,
                        _('versions total')
                    )
            
            return format_html(
                '<span style="color: #ffc107; font-weight: bold;" title="{}">⚠️ DUPLICATE</span><br>'
                '<span style="color: #6c757d; font-size: 0.85em;">({} {})</span>',
                tooltip,
                total_count + 1,
                _('versions total')
            )

    duplicates_indicator.short_description = _('Versions')
    
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
        """Show all versions of this video with detailed comparison."""
        if not obj.pk:
            return '-'
        
        # Get all versions (including current)
        all_versions = VideoFile.objects.filter(number=obj.number).order_by(
            '-total_bitrate', '-created_at', '-storage_location__storage_type'
        )
        
        if all_versions.count() <= 1:
            return format_html('<span style="color: #6c757d;">{}</span>', _('No other versions'))
        
        html_parts = []
        primary = None
        
        for v in all_versions:
            is_current = v.id == obj.id
            is_primary = v.is_primary_version()
            if is_primary:
                primary = v
            
            # Determine version status
            if is_primary:
                status = '<span style="color: #28a745; font-weight: bold;">✓ PRIMARY</span>'
            elif is_current:
                status = '<span style="color: #007bff; font-weight: bold;">📍 CURRENT</span>'
            else:
                # Check if old version
                is_old = False
                if primary:
                    is_old = (
                        (v.total_bitrate and primary.total_bitrate and v.total_bitrate < primary.total_bitrate * 0.8)
                        or (v.created_at and primary.created_at and v.created_at < primary.created_at - timedelta(days=30))
                    )
                
                if is_old:
                    status = '<span style="color: #dc3545;">⚠️ OLD</span>'
                else:
                    status = '<span style="color: #ffc107;">⚠️ DUPLICATE</span>'
            
            # Build version info
            format_info = v.format.upper() if v.format else '?'
            resolution = f'{v.width}x{v.height}' if v.width and v.height else '?'
            bitrate = f'{v.bitrate_mbps} Mbps' if v.bitrate_mbps else '?'
            size = f'{v.file_size_mb} MB' if v.file_size_mb else '?'
            date = v.created_at.strftime('%Y-%m-%d') if v.created_at else '?'
            
            info = (
                f'<strong>{v.filename}</strong><br>'
                f'{v.storage_location.name} • {format_info} • {resolution} • {bitrate} • {size}<br>'
                f'<small style="color: #6c757d;">{_("Created")}: {date}</small>'
            )
            
            if is_current:
                html_parts.append(f'<div style="padding: 8px; background: #e7f3ff; border-left: 3px solid #007bff; margin: 5px 0;">{status}<br>{info}</div>')
            else:
                url = reverse('admin:media_files_videofile_change', args=[v.id])
                html_parts.append(
                    f'<div style="padding: 8px; background: #f8f9fa; border-left: 3px solid #dee2e6; margin: 5px 0;">'
                    f'{status}<br><a href="{url}">{info}</a></div>'
                )
        
        return format_html(''.join(html_parts))

    all_versions_display.short_description = _('All Versions')

    def player_link(self, obj):
        """Link to open video stream in modal."""
        if obj.is_available and obj.pk:
            stream_url = reverse('admin:media_files_videofile_stream', args=[obj.id])
            # Prepare additional fields for modal
            number = obj.number or ''
            storage_name = obj.storage_location.name if obj.storage_location else ''
            duration = str(obj.duration) if obj.duration else 'N/A'
            size_display = ''
            try:
                size_display = self.file_size_display(obj) or ''
            except Exception:
                size_display = 'N/A'
            bitrate_display = f"{obj.total_bitrate} bps" if obj.total_bitrate else 'N/A'
            player_text = _("Player")  # Get translated text beforehand

            return format_html(
                '<a href="#" onclick="openVideoModal(\'{}\', \'{}\', \'{}\', \'{}\', \'{}\', \'{}\', \'{}\')" style="color: #417690; text-decoration: none;">🎬 {}</a>',
                stream_url,
                obj.filename or '',
                number,
                storage_name,
                duration,
                size_display,
                bitrate_display,
                player_text,
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
            
            # Get translated strings beforehand
            file_path_linux = _("File path (Linux)")
            file_path_windows = _("File path (Windows UNC)")
            try:
                render_url = reverse('media_files:render_video_admin', args=[obj.id])
            except Exception:
                render_url = f'/media-files/render/video/{obj.id}/'
            
            render_label = _('Render Video with Overlays')
            
            return format_html(
                '''
                <div style="max-width: 640px; margin: 10px 0;">
                    <!-- Plyr CSS -->
                    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
                    
                    <!-- Plyr Player -->
                    <video
                        id="plyr-player-{}"
                        controls
                        preload="metadata"
                        crossorigin="anonymous"
                        width="640"
                        height="360">
                        <source src="{}" type="{}">
                        <p>To view the video, enable JavaScript or use
                            <a href="{}" download>download video</a>
                        </p>
                    </video>
                    
                    <!-- Plyr JavaScript -->
                    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
                    
                    <!-- Render Button -->
                    <div style="margin-top: 15px; text-align: center;">
                        <a href="{}" class="button" style="display: inline-block; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 4px; font-weight: 500;">
                            🎬 {}
                        </a>
                    </div>
                    
                    <!-- Video Info -->
                    <div style="margin-top: 15px; padding: 12px; background: #f8f9fa; border-radius: 4px; border-left: 4px solid #007bff;">
                        <div style="font-size: 12px; color: #333; margin-bottom: 5px;">
                            <strong>📁 {}:</strong>
                        </div>
                        <code style="display: block; padding: 8px; background: white; border-radius: 3px; word-break: break-all; font-size: 11px; color: #495057; border: 1px solid #dee2e6;">{}</code>
                        {}
                    </div>
                    
                    <!-- Initialize Plyr -->
                    <script>
                        document.addEventListener('DOMContentLoaded', function() {{
                            if (typeof Plyr !== 'undefined') {{
                                const player = new Plyr('#plyr-player-{}', {{
                                    controls: [
                                        'play-large', 'restart', 'rewind', 'play', 'fast-forward', 'progress',
                                        'current-time', 'duration', 'mute', 'volume', 'settings', 'fullscreen'
                                    ],
                                    settings: ['quality', 'speed'],
                                    speed: {{ selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2] }},
                                    quality: {{ default: 720, options: [1080, 720, 480, 360] }},
                                    loadSprite: false,  // Disable sprite loading for faster init
                                    clickToPlay: true,  // Enable click to play
                                    hideControls: true, // Hide controls when not interacting
                                    resetOnEnd: false,  // Don't reset on end for better UX
                                    disableContextMenu: false, // Allow right-click menu
                                    keyboard: {{ focused: true, global: false }}, // Keyboard controls
                                    tooltips: {{ controls: true, seek: true }}, // Show tooltips
                                    captions: {{ active: false, language: 'auto', update: false }}, // Disable captions
                                    previewThumbnails: {{ enabled: false }}, // Disable thumbnails for speed
                                    volume: 1, // Default volume
                                    muted: false, // Not muted by default
                                    autoplay: false, // Don't autoplay
                                    loop: {{ active: false }}, // Don't loop
                                    ratio: null // Auto aspect ratio
                                }});
                                console.log('Plyr player ready');
                                
                                // Optimize for fast playback
                                player.on('ready', function() {{
                                    console.log('Modal player ready for fast streaming');
                                    const video = player.media;
                                    if (video) {{
                                        video.addEventListener('loadstart', function() {{
                                            console.log('Modal video buffering started');
                                        }});
                                        
                                        video.addEventListener('seeking', function() {{
                                            console.log('Modal video seeking to:', video.currentTime);
                                        }});
                                        
                                        video.addEventListener('progress', function() {{
                                            if (video.buffered.length > 0) {{
                                                const bufferedEnd = video.buffered.end(video.buffered.length - 1);
                                                const duration = video.duration;
                                                if (duration > 0) {{
                                                    const bufferedPercent = (bufferedEnd / duration) * 100;
                                                    console.log('Modal video buffered:', bufferedPercent.toFixed(1) + '%');
                                                }}
                                            }}
                                        }});
                                    }}
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
                render_url,  # Render button URL
                render_label,  # Render button label
                file_path_linux,  # Use pre-translated string
                obj.full_path,
                f'''
                    <div style="font-size: 12px; color: #333; margin-top: 10px; margin-bottom: 5px;">
                        <strong>💾 {file_path_windows}:</strong>
                    </div>
                    <code style="display: block; padding: 8px; background: white; border-radius: 3px; word-break: break-all; font-size: 11px; color: #495057; border: 1px solid #dee2e6;">{obj.unc_path}</code>
                ''' if obj.unc_path else '',
                obj.id  # video player ID for script
            )
        return _('Video not available')
    
    video_player.short_description = _('Video Player')
    
    def video_player_page(self, request, video_id):
        """Display video player page."""
        try:
            video = VideoFile.objects.get(id=video_id)
            return render(request, 'admin/video_player.html', {'video': video})
        except VideoFile.DoesNotExist:
            return HttpResponse(_('Video not found'), status=404)
        except Exception as e:
            logger.error(f'Error loading video player: {str(e)}', exc_info=True)
            return HttpResponse(_('Error: {}').format(str(e)), status=500)

    @csrf_exempt
    def stream_video(self, request, video_id):
        """Stream video file with range support using django-downloadview."""
        try:
            video = VideoFile.objects.get(id=video_id)
            
            if not video.is_available:
                return HttpResponse(_('Video not available'), status=404)

            file_path = video.full_path

            # Handle read-only storage gracefully
            try:
                if not os.path.exists(file_path):
                    video.is_available = False
                    video.save()
                    return HttpResponse(_('Video file not found'), status=404)
            except (OSError, PermissionError, IOError) as e:
                # Storage might be read-only - try to serve anyway if file path is valid
                logger.debug(f'Could not check file existence for {file_path}: {e}')
                # Continue to try serving - django-downloadview will handle the error
            except Exception as e:
                logger.warning(f'Unexpected error checking file {file_path}: {e}')
                # Continue to try serving
            
            # Determine content type based on file extension, not database format
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
            
            # Use FileResponse with range support for efficient streaming
            from django.http import FileResponse
            import mimetypes
            
            # Get file size for range requests
            file_size = os.path.getsize(file_path)
            
            # Open file in binary mode
            video_file = open(file_path, 'rb')
            
            # Create FileResponse with range support
            response = FileResponse(video_file, content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{video.filename}"'
            response['Accept-Ranges'] = 'bytes'
            response['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
            response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
            
            # Handle Range requests for video streaming
            range_header = request.META.get('HTTP_RANGE')
            if range_header:
                import re
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    
                    # Set partial content response
                    response.status_code = 206
                    response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                    response['Content-Length'] = str(end - start + 1)
                    
                    # Seek to start position
                    video_file.seek(start)
            
            return response
            
        except VideoFile.DoesNotExist:
            return HttpResponse(_('Video not found'), status=404)
        except Exception as e:
            logger.error(f'Error streaming video: {str(e)}', exc_info=True)
            return HttpResponse(_('Error: {}').format(str(e)), status=500)
    
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
            self.message_user(request, _('No PLAYOUT storage configured'), level='error')
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
                
                metadata = extract_video_metadata_fast(video.full_path)
                
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
        """Mark selected videos as primary (manual override)."""
        # Group by number
        by_number = {}
        for video in queryset:
            if video.number not in by_number:
                by_number[video.number] = []
            by_number[video.number].append(video)
        
        marked_count = 0
        
        for number, videos in by_number.items():
            if len(videos) > 1:
                self.message_user(
                    request,
                    _('Multiple videos selected for number {}. Please select only one per number.').format(number),
                    level='error'
                )
                continue
            
            primary = videos[0]
            
            # Clear manual primary flag from all other versions with same number
            VideoFile.objects.filter(number=number).exclude(id=primary.id).update(is_manual_primary=False)
            
            # Set manual primary flag for selected video
            primary.is_manual_primary = True
            primary.save(update_fields=['is_manual_primary'])
            marked_count += 1
            
            all_versions = VideoFile.objects.filter(number=number).exclude(id=primary.id)
            if all_versions.exists():
                logger.info(f'Video #{number} marked as manual primary. Found {all_versions.count()} duplicate(s)')
        
        if marked_count > 0:
            self.message_user(
                request,
                _('Marked {} video(s) as primary version').format(marked_count),
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
            
            # Check if any version is manually marked as primary
            manual_primary = versions.filter(is_manual_primary=True).first()
            if manual_primary:
                primary = manual_primary
            else:
                # Find primary version by quality (date first, then bitrate, then storage)
                storage_priority = {'ARCHIVE': 3, 'PLAYOUT': 2, 'CUSTOM': 1}
                primary = max(versions, key=lambda v: (
                    v.created_at,
                    v.total_bitrate or 0,
                    storage_priority.get(v.storage_location.storage_type, 0)
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
    
    @admin.action(description=_('Cleanup records for files missing from disk'))
    def cleanup_missing_files_action(self, request, queryset):
        """Delete VideoFile records for files that no longer exist on disk.
        
        Works with read-only storage - handles errors gracefully when files cannot be checked.
        """
        import os
        from django.db import connection
        
        deleted_count = 0
        found_count = 0
        error_count = 0
        read_only_count = 0
        
        for video in queryset:
            try:
                if not video.is_available:
                    # Skip files already marked as unavailable
                    continue
                
                # Check if file exists on disk (handle read-only storage gracefully)
                file_exists = False
                try:
                    file_exists = os.path.exists(video.full_path)
                    found_count += 1
                except (OSError, PermissionError, IOError) as e:
                    # Storage might be read-only - skip this file
                    read_only_count += 1
                    logger.debug(f'Could not check file existence for {video.full_path}: {e}')
                    continue
                except Exception as e:
                    # Any other error - log and skip
                    read_only_count += 1
                    logger.warning(f'Unexpected error checking file {video.full_path}: {e}')
                    continue
                
                if not file_exists:
                    # Delete related FileOperation objects using raw SQL
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "DELETE FROM media_files_fileoperation WHERE video_file_id = %s",
                                [video.id]
                            )
                    except Exception as e:
                        logger.error(f'Error deleting FileOperation for video {video.id}: {e}')
                        # Continue anyway - will be cascade deleted
                    
                    # Delete the VideoFile
                    video.delete()
                    deleted_count += 1
                    logger.info(f'Deleted VideoFile {video.number} (file missing): {video.filename}')
            
            except Exception as e:
                error_count += 1
                logger.error(f'Error checking/deleting {video.filename}: {str(e)}')
                self.message_user(
                    request,
                    f'Error processing {video.number}: {str(e)}',
                    level='error'
                )
        
        if deleted_count > 0:
            self.message_user(
                request,
                _('Deleted {} record(s) for files missing from disk').format(deleted_count),
                level='success'
            )
        if read_only_count > 0:
            self.message_user(
                request,
                _('{} file(s) could not be checked (storage may be read-only)').format(read_only_count),
                level='info'
            )
        if found_count == 0:
            self.message_user(
                request,
                _('No files to check (all selected files are already marked as unavailable)'),
                level='info'
            )
        elif deleted_count == 0 and read_only_count == 0:
            self.message_user(
                request,
                _('All checked files exist on disk'),
                level='info'
            )
        if error_count > 0:
            self.message_user(
                request,
                _('{} error(s) occurred').format(error_count),
                level='error'
            )
    
    def has_delete_permission(self, request, obj=None):
        """
        Check if user has permission to delete VideoFile.
        
        By default, uses Django's standard permission system.
        Override this method to add custom permission logic.
        """
        # Use default Django permission checking
        # This checks for 'media_files.delete_videofile' permission
        return super().has_delete_permission(request, obj)
    
    def get_deleted_objects(self, objs, request):
        """
        Override get_deleted_objects to bypass permission checks for FileOperation.
        
        This allows deletion of VideoFile records even when the user doesn't have
        delete permission for FileOperation (which is intentionally disabled).
        """
        from django.contrib.admin.utils import NestedObjects
        
        # Use collector to get all related objects
        collector = NestedObjects(using='default')
        collector.collect(objs)
        
        # Filter out FileOperation from all collections
        file_operation_label = 'media_files.fileoperation'
        
        # Filter model_objs - remove FileOperation
        filtered_model_objs = {}
        for model, instances in collector.model_objs.items():
            if model._meta.label_lower != file_operation_label:
                filtered_model_objs[model] = instances
        
        # Filter protected - remove FileOperation
        filtered_protected = []
        for item in collector.protected:
            if hasattr(item, '_meta') and item._meta.label_lower != file_operation_label:
                filtered_protected.append(item)
            elif not hasattr(item, '_meta'):
                filtered_protected.append(item)
        
        # Build deleted_objects list (format: list of tuples (model, instances))
        deleted_objects = []
        for model, instances in filtered_model_objs.items():
            deleted_objects.append((model, instances))
        
        # Build model_count dict (format: {verbose_name_plural: count})
        model_count = {}
        for model, instances in filtered_model_objs.items():
            model_count[model._meta.verbose_name_plural] = len(instances)
        
        # Build perms_needed set - check permissions for each model (excluding FileOperation)
        perms_needed = set()
        for model, instances in filtered_model_objs.items():
            # Check if user has delete permission for this model
            model_admin = self.admin_site._registry.get(model)
            if model_admin and not model_admin.has_delete_permission(request):
                perms_needed.add(model._meta.verbose_name)
        
        return deleted_objects, model_count, perms_needed, filtered_protected
    
    def delete_model(self, request, obj):
        """
        Override delete_model to bypass permission checks for related FileOperation objects.
        
        This allows deletion of VideoFile records even when the user doesn't have
        delete permission for FileOperation (which is intentionally disabled).
        Also deletes physical files from disk.
        """
        import os
        import traceback
        
        logger.info(f'delete_model called for VideoFile {obj.id} (number: {obj.number})')
        
        try:
            # Check if file exists on disk (handle read-only storage gracefully)
            file_exists = False
            file_check_error = None
            if obj.is_available:
                try:
                    # Safely get full_path - may fail if storage_location is None or path is missing
                    full_path = None
                    try:
                        full_path = obj.full_path
                    except (AttributeError, TypeError) as e:
                        logger.debug(f'Could not get full_path for video {obj.id}: {e}')
                        file_check_error = 'Could not determine file path'
                    
                    if full_path:
                        file_exists = os.path.exists(full_path)
                except (OSError, PermissionError, IOError) as e:
                    # Storage might be read-only or inaccessible - that's OK, we're only deleting DB record
                    file_check_error = str(e)
                    logger.debug(f'Could not check file existence: {e}')
                except Exception as e:
                    # Any other error - log but don't fail
                    file_check_error = str(e)
                    logger.warning(f'Unexpected error checking file: {e}')
            
            # Delete related FileOperation objects using raw SQL to bypass permission checks
            # FileOperationAdmin has delete permission disabled, so we use direct SQL
            from django.db import connection
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM media_files_fileoperation WHERE video_file_id = %s",
                        [obj.id]
                    )
            except Exception as e:
                logger.error(f'Error deleting FileOperation records for video {obj.id}: {e}')
                # Continue anyway - FileOperation will be cascade deleted
            
            # Delete physical file if it exists
            file_deleted = False
            file_delete_error = None
            if file_exists and full_path:
                try:
                    os.remove(full_path)
                    file_deleted = True
                    logger.info(f'Deleted physical file: {full_path}')
                except (OSError, PermissionError, IOError) as e:
                    file_delete_error = str(e)
                    logger.warning(f'Could not delete physical file {full_path}: {e}')
                    # Continue with DB deletion even if file deletion fails
                except Exception as e:
                    file_delete_error = str(e)
                    logger.error(f'Unexpected error deleting file {full_path}: {e}')
                    # Continue with DB deletion even if file deletion fails
            
            # Delete related FileOperation objects using raw SQL to bypass permission checks
            # FileOperationAdmin has delete permission disabled, so we use direct SQL
            from django.db import connection
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM media_files_fileoperation WHERE video_file_id = %s",
                        [obj.id]
                    )
            except Exception as e:
                logger.error(f'Error deleting FileOperation records for video {obj.id}: {e}')
                # Continue anyway - FileOperation will be cascade deleted
            
            # Delete the VideoFile (database record)
            try:
                logger.debug(f'Attempting to delete VideoFile {obj.id}')
                obj.delete()
                logger.info(f'Successfully deleted VideoFile {obj.id}')
            except Exception as e:
                error_traceback = traceback.format_exc()
                logger.error(f'Error in delete_model for VideoFile {obj.id}: {e}')
                logger.error(f'Traceback: {error_traceback}')
                # Re-raise to let Django admin handle it properly
                raise
            
            # Show appropriate message (only if deletion succeeded)
            if file_delete_error:
                self.message_user(
                    request,
                    _('Video record deleted. Could not delete physical file: {error}').format(error=file_delete_error),
                    level='warning'
                )
            elif file_check_error:
                self.message_user(
                    request,
                    _('Video record deleted. Could not check file status (storage may be read-only).'),
                    level='info'
                )
            elif file_deleted:
                self.message_user(
                    request,
                    _('Video record and physical file deleted successfully.'),
                    level='success'
                )
            elif not file_exists:
                self.message_user(
                    request,
                    _('Video record deleted (file was already removed from disk)'),
                    level='success'
                )
            else:
                self.message_user(
                    request,
                    _('Video record deleted.'),
                    level='success'
                )
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f'Unexpected error in delete_model for VideoFile {obj.id}: {e}')
            logger.error(f'Traceback: {error_traceback}')
            raise
    
    def delete_queryset(self, request, queryset):
        """
        Override delete_queryset to bypass permission checks for related FileOperation objects.
        
        This allows bulk deletion of VideoFile records even when the user doesn't have
        delete permission for FileOperation (which is intentionally disabled).
        Also deletes physical files from disk.
        """
        import os
        import traceback
        
        logger.info(f'delete_queryset called with {queryset.count()} objects')
        
        deleted_count = 0
        files_deleted = 0
        files_missing = 0
        files_delete_errors = 0
        read_only_count = 0
        error_count = 0
        
        try:
            for obj in queryset:
                # Check if file exists on disk and delete it
                file_exists = False
                file_deleted = False
                file_check_error = None
                full_path = None
                
                if obj.is_available:
                    try:
                        # Safely get full_path - may fail if storage_location is None or path is missing
                        try:
                            full_path = obj.full_path
                        except (AttributeError, TypeError) as e:
                            logger.debug(f'Could not get full_path for video {obj.id}: {e}')
                            file_check_error = 'Could not determine file path'
                            read_only_count += 1
                        
                        if full_path:
                            file_exists = os.path.exists(full_path)
                            if not file_exists:
                                files_missing += 1
                            elif file_exists:
                                # Try to delete the physical file
                                try:
                                    os.remove(full_path)
                                    file_deleted = True
                                    files_deleted += 1
                                    logger.info(f'Deleted physical file: {full_path}')
                                except (OSError, PermissionError, IOError) as e:
                                    files_delete_errors += 1
                                    logger.warning(f'Could not delete physical file {full_path}: {e}')
                                    # Continue with DB deletion even if file deletion fails
                                except Exception as e:
                                    files_delete_errors += 1
                                    logger.error(f'Unexpected error deleting file {full_path}: {e}')
                                    # Continue with DB deletion even if file deletion fails
                    except (OSError, PermissionError, IOError) as e:
                        # Storage might be read-only or inaccessible
                        file_check_error = str(e)
                        read_only_count += 1
                        logger.debug(f'Could not check file existence: {e}')
                    except Exception as e:
                        # Any other error - log but don't fail
                        file_check_error = str(e)
                        read_only_count += 1
                        logger.warning(f'Unexpected error checking file: {e}')
                
                # Delete related FileOperation objects using raw SQL to bypass permission checks
                # Do this AFTER getting all info but BEFORE calling obj.delete() to avoid signal conflicts
                from django.db import connection
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM media_files_fileoperation WHERE video_file_id = %s",
                            [obj.id]
                        )
                except Exception as e:
                    logger.error(f'Error deleting FileOperation records for video {obj.id}: {e}')
                    # Continue anyway - FileOperation will be cascade deleted
                
                # Delete the VideoFile (database record)
                # Wrap in try-except to catch any errors during deletion
                try:
                    logger.debug(f'Attempting to delete VideoFile {obj.id} (number: {obj.number})')
                    obj.delete()
                    deleted_count += 1
                    logger.debug(f'Successfully deleted VideoFile {obj.id}')
                except Exception as e:
                    error_count += 1
                    error_traceback = traceback.format_exc()
                    logger.error(f'Error deleting VideoFile {obj.id}: {e}')
                    logger.error(f'Traceback: {error_traceback}')
                    # Log error but continue with other deletions
                    self.message_user(
                        request,
                        _('Error deleting video {}: {}').format(obj.number or obj.id, str(e)),
                        level='error'
                    )
        
        except Exception as e:
            # Catch any unexpected errors in the loop
            error_traceback = traceback.format_exc()
            logger.error(f'Unexpected error in delete_queryset loop: {e}')
            logger.error(f'Traceback: {error_traceback}')
            self.message_user(
                request,
                _('Unexpected error during deletion: {}').format(str(e)),
                level='error'
            )
        
        # Show appropriate message
        if files_delete_errors > 0:
            self.message_user(
                request,
                _('{} video record(s) deleted. {} file(s) deleted from disk. {} file(s) could not be deleted from disk.').format(
                    deleted_count, files_deleted, files_delete_errors
                ),
                level='warning'
            )
        elif read_only_count > 0:
            self.message_user(
                request,
                _('{} video record(s) deleted. {} file(s) deleted from disk. {} file(s) could not be checked (storage may be read-only).').format(
                    deleted_count, files_deleted, read_only_count
                ),
                level='info'
            )
        elif files_missing == deleted_count:
            self.message_user(
                request,
                _('{} video record(s) deleted (files were already removed from disk)').format(deleted_count),
                level='success'
            )
        elif files_deleted > 0:
            self.message_user(
                request,
                _('{} video record(s) and {} physical file(s) deleted successfully.').format(deleted_count, files_deleted),
                level='success'
            )
        else:
            self.message_user(
                request,
                _('{} video record(s) deleted.').format(deleted_count),
                level='success'
            )
        
        if error_count > 0:
            logger.warning(f'delete_queryset completed with {error_count} error(s), {deleted_count} successful deletion(s)')
        else:
            logger.info(f'delete_queryset completed successfully: {deleted_count} deletion(s), {files_deleted} file(s) deleted')

    class Media:
        css = {
            'all': ('css/admin/custom_admin.css',)
        }


@admin.register(FileOperation)
class FileOperationAdmin(admin.ModelAdmin):
    """Admin interface for file operations (read-only)."""

    change_list_template = 'admin/media_files/fileoperation/change_list.html'
    
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


class PresetOverlayInline(admin.TabularInline):
    """Inline admin for preset overlays."""

    model = PresetOverlay
    extra = 0
    fields = [
        'segment', 'order', 'overlay_type', 'text_template', 'image_path',
        'position_preset', 'animation', 'start_time', 'end_time'
    ]
    ordering = ['segment', 'order']


@admin.register(VideoPreset)
class VideoPresetAdmin(admin.ModelAdmin):
    """Admin interface for video presets."""

    change_form_template = 'admin/media_files/videopreset/change_form.html'
    change_list_template = 'admin/media_files/videopreset/change_list.html'
    
    list_display = [
        'display_name', 'name', 'is_template', 'is_public',
        'created_by', 'overlay_count', 'updated_at', 'edit_in_ui'
    ]
    list_filter = ['is_template', 'is_public']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'overlay_count']
    inlines = [PresetOverlayInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'description')
        }),
        (_('Settings'), {
            'fields': (
                'segment_duration', 'intro_clip_path', 'outro_clip_path',
                'is_template', 'is_public', 'based_on'
            )
        }),
        (_('Ownership'), {
            'fields': ('created_by',)
        }),
        (_('Information'), {
            'fields': ('overlay_count', 'created_at', 'updated_at')
        }),
    )
    
    def get_urls(self):
        """Add custom URLs for preset editor and import."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/edit-preset/',
                self.admin_site.admin_view(self.preset_editor_view),
                name='media_files_videopreset_edit_preset',
            ),
            path(
                '<int:object_id>/preset-load/',
                self.admin_site.admin_view(self.preset_load_view),
                name='media_files_videopreset_preset_load',
            ),
            path(
                '<int:object_id>/preset-save/',
                self.admin_site.admin_view(self.preset_save_view),
                name='media_files_videopreset_preset_save',
            ),
            path(
                'import-all/',
                self.admin_site.admin_view(self.import_all_presets_view),
                name='media_files_videopreset_import_all',
            ),
            path(
                'import-single/<str:preset_name>/',
                self.admin_site.admin_view(self.import_single_preset_view),
                name='media_files_videopreset_import_single',
            ),
        ]
        return custom_urls + urls
    
    def preset_editor_view(self, request, object_id):
        """Visual preset editor view in admin."""
        from django.shortcuts import get_object_or_404
        from licenses.models import License
        
        preset = get_object_or_404(VideoPreset, id=object_id)
        
        # Check permissions
        if not request.user.is_superuser and preset.created_by != request.user and not preset.is_public:
            messages.error(request, _('You do not have permission to edit this preset.'))
            return redirect('admin:media_files_videopreset_changelist')
        
        # Get a sample license for preview
        sample_license = License.objects.filter(title__isnull=False).first()
        
        context = {
            **self.admin_site.each_context(request),
            'title': _('Edit Preset'),
            'preset': preset,
            'sample_license': sample_license,
            'position_presets': POSITION_PRESET_CHOICES,
            'animation_choices': PresetOverlay._meta.get_field('animation').choices,
            'font_choices': [
                ('fonts/Roboto-Regular.ttf', 'Roboto Regular'),
                ('fonts/Roboto-Bold.ttf', 'Roboto Bold'),
            ],
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request, preset),
            'has_change_permission': self.has_change_permission(request, preset),
        }
        return render(request, 'admin/media_files/preset_editor.html', context)
    
    def preset_load_view(self, request, object_id):
        """Load preset data via AJAX."""
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        
        preset = get_object_or_404(VideoPreset, id=object_id)
        
        overlays = []
        for overlay in preset.overlays.all().order_by('segment', 'order'):
            overlays.append({
                'id': overlay.id,
                'type': overlay.overlay_type,
                'segment': overlay.segment,
                'order': overlay.order,
                'text_template': overlay.text_template,
                'image_path': overlay.image_path,
                'image_width': overlay.image_width,
                'image_height': overlay.image_height,
                'position_preset': overlay.position_preset,
                'x_position': overlay.x_position,
                'y_position': overlay.y_position,
                'start_time': overlay.start_time,
                'end_time': overlay.end_time,
                'animation': overlay.animation,
                'fade_in_duration': overlay.fade_in_duration,
                'fade_out_duration': overlay.fade_out_duration,
                'font_file': overlay.font_file,
                'font_size': overlay.font_size,
                'font_color': overlay.font_color,
                'has_box': overlay.has_box,
                'box_color': overlay.box_color,
                'box_border_width': overlay.box_border_width,
            })
        
        return JsonResponse({
            'success': True,
            'preset': {
                'id': preset.id,
                'name': preset.name,
                'display_name': preset.display_name,
                'description': preset.description,
                'segment_duration': preset.segment_duration,
                'intro_clip_path': preset.intro_clip_path,
                'outro_clip_path': preset.outro_clip_path,
                'is_public': preset.is_public,
                'overlays': overlays,
            }
        })
    
    def preset_save_view(self, request, object_id):
        """Save preset via AJAX."""
        import json
        import logging
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        from django.views.decorators.http import require_http_methods
        
        logger = logging.getLogger('django')
        
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
        try:
            data = json.loads(request.body)
            preset = get_object_or_404(VideoPreset, id=object_id)
            
            # Check permissions
            if not request.user.is_superuser and preset.created_by != request.user:
                return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
            
            # Update preset fields
            preset.name = data.get('name', preset.name)
            preset.display_name = data.get('display_name', preset.display_name)
            preset.description = data.get('description', preset.description)
            preset.segment_duration = float(data.get('segment_duration', preset.segment_duration))
            preset.intro_clip_path = data.get('intro_clip_path', preset.intro_clip_path)
            preset.outro_clip_path = data.get('outro_clip_path', preset.outro_clip_path)
            preset.is_public = data.get('is_public', preset.is_public)
            preset.save()
            
            # Delete existing overlays
            preset.overlays.all().delete()
            
            # Create new overlays
            for overlay_data in data.get('overlays', []):
                overlay = PresetOverlay(
                    preset=preset,
                    overlay_type=overlay_data.get('type', 'text'),
                    segment=overlay_data.get('segment', 'intro'),
                    order=overlay_data.get('order', 0),
                    text_template=overlay_data.get('text_template', ''),
                    image_path=overlay_data.get('image_path', ''),
                    image_width=overlay_data.get('image_width'),
                    image_height=overlay_data.get('image_height'),
                    position_preset=overlay_data.get('position_preset', 'custom'),
                    x_position=overlay_data.get('x_position', '(w-text_w)/2'),
                    y_position=overlay_data.get('y_position', '(h-text_h)/2'),
                    start_time=float(overlay_data.get('start_time', 0.0)),
                    end_time=float(overlay_data.get('end_time', 5.0)),
                    animation=overlay_data.get('animation', 'fade'),
                    fade_in_duration=float(overlay_data.get('fade_in_duration', 0.4)),
                    fade_out_duration=float(overlay_data.get('fade_out_duration', 0.4)),
                    font_file=overlay_data.get('font_file', 'fonts/Roboto-Regular.ttf'),
                    font_size=int(overlay_data.get('font_size', 48)),
                    font_color=overlay_data.get('font_color', 'white'),
                    has_box=overlay_data.get('has_box', False),
                    box_color=overlay_data.get('box_color', 'black@0.5'),
                    box_border_width=int(overlay_data.get('box_border_width', 12)),
                )
                overlay.save()
            
            return JsonResponse({
                'success': True,
                'preset_id': preset.id,
                'message': _('Preset saved successfully')
            })
            
        except Exception as e:
            logger.exception("Error saving preset")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    def overlay_count(self, obj):
        """Display count of overlays."""
        if obj.pk:
            return obj.overlays.count()
        return 0
    overlay_count.short_description = _('Overlays')
    
    def edit_in_ui(self, obj):
        """Link to visual editor."""
        if obj.pk:
            url = reverse('admin:media_files_videopreset_edit_preset', args=[obj.id])
            return format_html(
                '<a href="{}" class="button">🎨 {}</a>',
                url,
                _('Visual Editor')
            )
        return '-'
    edit_in_ui.short_description = _('Editor')
    
    def save_model(self, request, obj, form, change):
        """Set created_by on new presets."""
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def changelist_view(self, request, extra_context=None):
        """Add available JSON presets to changelist context."""
        extra_context = extra_context or {}
        from media_files.rendering.presets import list_style_presets
        extra_context['available_json_presets'] = list_style_presets()
        return super().changelist_view(request, extra_context=extra_context)
    
    def import_all_presets_view(self, request):
        """Import all JSON presets from video_presets/style directory."""
        from django.core.management import call_command
        from django.contrib import messages
        from django.shortcuts import redirect
        
        try:
            call_command('import_json_presets')
            messages.success(request, _('All presets imported successfully'))
        except Exception as e:
            messages.error(request, _('Error importing presets: %s') % str(e))
        
        return redirect('admin:media_files_videopreset_changelist')
    
    def import_single_preset_view(self, request, preset_name):
        """Import a single JSON preset by name."""
        from django.core.management import call_command
        from django.contrib import messages
        from django.shortcuts import redirect
        
        try:
            call_command('import_json_presets', preset_name=preset_name)
            messages.success(request, _('Preset "%s" imported successfully') % preset_name)
        except Exception as e:
            messages.error(request, _('Error importing preset "%s": %s') % (preset_name, str(e)))
        
        return redirect('admin:media_files_videopreset_changelist')


@admin.register(VideoEncodePreset)
class VideoEncodePresetAdmin(admin.ModelAdmin):
    """Admin interface for video encode presets."""

    list_display = [
        'display_name', 'name', 'width', 'height', 'fps', 
        'video_bitrate_k', 'audio_bitrate_k', 'updated_at'
    ]
    list_filter = ['vcodec', 'acodec', 'x264_preset', 'x264_profile']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'description')
        }),
        (_('Video Settings'), {
            'fields': (
                'width', 'height', 'fps', 'vcodec', 'video_bitrate_k',
                'pix_fmt', 'x264_preset', 'x264_profile'
            )
        }),
        (_('Audio Settings'), {
            'fields': (
                'acodec', 'audio_bitrate_k', 'audio_sample_rate', 'audio_channels'
            )
        }),
        (_('Information'), {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-generate display_name if not provided and save to JSON file."""
        if not obj.display_name:
            obj.display_name = f"{obj.height}p ({obj.video_bitrate_k}k)"
        super().save_model(request, obj, form, change)
        
        # Export to JSON file after saving
        try:
            import json
            from pathlib import Path
            from django.conf import settings
            
            encode_dir = Path(settings.BASE_DIR) / 'media_files' / 'video_presets' / 'encode'
            encode_dir.mkdir(parents=True, exist_ok=True)
            
            json_file = encode_dir / f"{obj.name}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(obj.to_json(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save encode preset to JSON: {e}")


@admin.register(PresetOverlay)
class PresetOverlayAdmin(admin.ModelAdmin):
    """Admin interface for preset overlays."""

    list_display = [
        'preset', 'segment', 'order', 'overlay_type',
        'preview_text', 'animation', 'timing'
    ]
    list_filter = ['preset', 'segment', 'overlay_type', 'animation']
    search_fields = ['preset__name', 'text_template', 'image_path']
    
    fieldsets = (
        (None, {
            'fields': ('preset', 'segment', 'order', 'overlay_type')
        }),
        (_('Content'), {
            'fields': ('text_template', 'image_path', 'image_width', 'image_height')
        }),
        (_('Position'), {
            'fields': ('position_preset', 'x_position', 'y_position')
        }),
        (_('Timing & Animation'), {
            'fields': (
                'start_time', 'end_time', 'animation',
                'fade_in_duration', 'fade_out_duration'
            )
        }),
        (_('Text Styling'), {
            'fields': (
                'font_file', 'font_size', 'font_color',
                'has_box', 'box_color', 'box_border_width'
            )
        }),
    )
    
    def preview_text(self, obj):
        """Show preview of text or image path."""
        if obj.overlay_type == 'text':
            text = obj.text_template[:50]
            if len(obj.text_template) > 50:
                text += '...'
            return text
        else:
            return obj.image_path
    preview_text.short_description = _('Content')
    
    def timing(self, obj):
        """Show timing info."""
        return f"{obj.start_time}s - {obj.end_time}s"
    timing.short_description = _('Timing')
