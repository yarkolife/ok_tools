from .forms import RangeNumericForm
from .generate_file import generate_license_file
from .models import Category
from .models import License
from .widgets import TagsInputWidget
from admin_auto_filters.filters import AutocompleteFilterFactory
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext as _p
from import_export import resources
from import_export.admin import ExportMixin
from import_export.fields import Field
from ok_tools.datetime import TZ
# from rangefilter.filters import DateTimeRangeFilter
import datetime
import logging


logger = logging.getLogger('django')


class CustomDateTimeRangeFilter(admin.FieldListFilter):
    """Custom filter for date and time range, compatible with Django 5+."""

    template = 'admin/filter_datetime_range.html'
    title = 'Created at'

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.field_path = field_path
        self.parameter_name = field_path
        self.used_parameters = params
        super().__init__(field, request, params, model, model_admin, field_path)

    def choices(self, changelist):
        return ({
            'request': self.request,
            'parameter_name': self.parameter_name,
            'form': self._get_form(),
            'title': self.title,
        }, )

    def _get_form(self):
        """Create a form for the filter."""
        from django import forms

        class DateTimeRangeForm(forms.Form):
            gte_0 = forms.CharField(
                label=_('Date from'),
                required=False,
                widget=forms.TextInput(attrs={'placeholder': _('From'), 'type': 'date'})
            )
            gte_1 = forms.CharField(
                label=_('Time from'),
                required=False,
                widget=forms.TextInput(attrs={'placeholder': _('From'), 'type': 'time'})
            )
            lte_0 = forms.CharField(
                label=_('Date to'),
                required=False,
                widget=forms.TextInput(attrs={'placeholder': _('To'), 'type': 'date'})
            )
            lte_1 = forms.CharField(
                label=_('Time to'),
                required=False,
                widget=forms.TextInput(attrs={'placeholder': _('To'), 'type': 'time'})
            )

        # Create a dictionary with data for the form
        form_data = {}
        for param in self.expected_parameters():
            if param in self.used_parameters:
                form_data[param.replace(f'{self.parameter_name}__', '')] = self.used_parameters[param]

        return DateTimeRangeForm(data=form_data)

    def queryset(self, request, queryset):
        """Apply the filter to the queryset."""
        gte_date = self.used_parameters.get(f'{self.parameter_name}__gte_0')
        gte_time = self.used_parameters.get(f'{self.parameter_name}__gte_1')
        lte_date = self.used_parameters.get(f'{self.parameter_name}__lte_0')
        lte_time = self.used_parameters.get(f'{self.parameter_name}__lte_1')

        # Process the case when the parameter can be a list
        if isinstance(gte_date, list):
            gte_date = gte_date[0] if gte_date else None
        if isinstance(gte_time, list):
            gte_time = gte_time[0] if gte_time else None
        if isinstance(lte_date, list):
            lte_date = lte_date[0] if lte_date else None
        if isinstance(lte_time, list):
            lte_time = lte_time[0] if lte_time else None

        if gte_date:
            try:
                gte_datetime = datetime.datetime.strptime(gte_date, '%Y-%m-%d')
                if gte_time:
                    gte_time_obj = datetime.datetime.strptime(gte_time, '%H:%M').time()
                    gte_datetime = datetime.datetime.combine(gte_datetime.date(), gte_time_obj)
                queryset = queryset.filter(**{f'{self.field_path}__gte': gte_datetime})
            except ValueError:
                pass

        if lte_date:
            try:
                lte_datetime = datetime.datetime.strptime(lte_date, '%Y-%m-%d')
                if lte_time:
                    lte_time_obj = datetime.datetime.strptime(lte_time, '%H:%M').time()
                    lte_datetime = datetime.datetime.combine(lte_datetime.date(), lte_time_obj)
                else:
                    lte_datetime = datetime.datetime.combine(lte_datetime.date(), datetime.time.max)
                queryset = queryset.filter(**{f'{self.field_path}__lte': lte_datetime})
            except ValueError:
                pass

        return queryset

    def expected_parameters(self):
        """Return expected parameters."""
        return [
            f'{self.parameter_name}__gte_0',
            f'{self.parameter_name}__gte_1',
            f'{self.parameter_name}__lte_0',
            f'{self.parameter_name}__lte_1',
        ]


class LicenseResource(resources.ModelResource):
    """Define the export for License."""

    def _f(field, name=None):
        """Shortcut for field creation."""
        return Field(attribute=field, column_name=name)

    number = _f('number', _('Number'))
    title = _f('title', _('Title'))
    subtitle = _f('subtitle', _('Subtitle'))
    description = _f('description', _('Description'))
    profile = _f('profile', _('Profile'))
    profile_id = _f('profile__id', _('Profile ID'))
    further_persons = _f('further_persons', _('Further involved persons'))
    duration = _f('duration', _('Duration'))
    category = _f('category__name', _('Category'))
    suggested_date = _f('suggested_date__date', _('Suggested broadcast date'))
    suggested_time = _f('suggested_date__time', _('Suggested broadcast time'))
    repetition_allowed = _f('repetitions_allowed', _('Repetitions allowed'))
    exchange = _f(
        'media_authority_exchange_allowed',
        _('Media Authority exchange allowed')
    )
    youth_protection = _f(
        'youth_protection_necessary', _('Youth protection necessary'))
    media_library = _f(
        'store_in_ok_media_library', _('Store in OK media library'))
    screen_board = _f('is_screen_board', _('Screen Board'))
    created_at = _f('created_at', _('created at'))

    def dehydrate_suggested_date(self, license: License):
        """Return the suggested date in the current time zone."""
        if (date := license.suggested_date):
            return date.astimezone(TZ).date()
        else:
            return None

    def dehydrate_suggested_time(self, license: License):
        """Return the suggested time in the current time zone."""
        if (date := license.suggested_date):
            return date.astimezone(TZ).time()
        else:
            return None

    def dehydrate_created_at(self, license: License):
        """Return the created_at datetime in the current time zone."""
        tz_datetime = license.created_at.astimezone(TZ)
        return f'{tz_datetime.date()} {tz_datetime.time()}'

    class Meta:
        """Define meta properties for the License export."""

        model = License
        fields = []


class YearFilter(admin.SimpleListFilter):
    """Filter after this or last year."""

    title = _('Creation year')

    parameter_name = 'created_at'

    def lookups(self, request, model_admin):
        """Define labels to filter after this or last year."""
        return (
            ('this', _('This year')),
            ('last', _('Last year')),
        )

    def queryset(self, request, queryset):
        """Filter after creation date for this or last year."""
        match self.value():
            case None:
                return
            case 'this':
                return queryset.filter(
                    created_at__year=datetime.datetime.now().year)
            case 'last':
                return queryset.filter(
                    created_at__year=datetime.datetime.now().year-1)
            case _:
                msg = f'Invalid value {self.value()}.'
                logger.error(msg)
                raise ValueError(msg)


class WithoutContributionFilter(admin.SimpleListFilter):
    """All Licenses with or without any contributions."""

    title = _('without contributions')
    parameter_name = 'without_contribution'

    def lookups(self, request, model_admin):
        """Yes or no labels."""
        return (
            ('y', _('Yes')),
            ('n', _('No')),
        )

    def queryset(self, request, queryset):
        """All licenses with or without contributions."""
        match self.value():
            case None:
                return
            case 'y':
                return (queryset
                        .annotate(num_contr=Count('contribution'))
                        .filter(num_contr=0))
            case 'n':
                return (queryset
                        .annotate(num_contr=Count('contribution'))
                        .filter(num_contr__gt=0))
            case _:
                msg = f'Invalid value {self.value()}.'
                logger.error(msg)
                raise ValueError(msg)


class LicenseAdminForm(forms.ModelForm):
    """Override the clean method for the forms used on the admin site."""

    class Meta:
        model = License
        fields = '__all__'
        widgets = {
            'tags': TagsInputWidget(),
        }

    def clean(self):
        """Raise an error if the LR of an unverified user gets confirmed."""
        profile = self.cleaned_data.get('profile')
        if self.cleaned_data.get('confirmed') and (not profile or not getattr(profile, 'verified', False)):
            raise forms.ValidationError(
                {'confirmed': _('The corresponding profile is not verified.'
                                ' The License can not be confirmed until the'
                                ' profile is verified.')}
            )

        return super().clean()
    
    def clean_tags(self):
        """
        Validate tags field.
        
        Ensures:
        - Maximum 4 tags
        - No empty tags
        - Proper formatting
        
        Returns:
            List of cleaned tags
            
        Raises:
            ValidationError: If validation fails
        """
        tags = self.cleaned_data.get('tags', [])
        
        if not tags:
            return []
        
        # Ensure tags is a list
        if not isinstance(tags, list):
            tags = [tags]
        
        # Clean and filter tags
        cleaned_tags = []
        for tag in tags:
            tag = str(tag).strip()
            if tag and tag not in cleaned_tags:  # Avoid duplicates
                cleaned_tags.append(tag)
        
        # Check maximum limit
        if len(cleaned_tags) > 4:
            raise forms.ValidationError(
                _('Maximum 4 tags allowed. You provided %(count)d tags.') % {
                    'count': len(cleaned_tags)
                }
            )
        
        # Check for empty tags
        if any(not tag for tag in cleaned_tags):
            raise forms.ValidationError(_('Empty tags are not allowed.'))
        
        return cleaned_tags
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add help text for tags field
        if 'tags' in self.fields:
            self.fields['tags'].help_text = _(
                'Enter tags separated by commas. Maximum 4 tags allowed. '
                'Example: documentary, local, culture, news'
            )


class DurationRangeFilter(admin.FieldListFilter):
    """Filter the duration using the given range of minutes."""

    request = None
    parameter_name = 'duration'
    template = 'admin/filter_numeric_range.html'

    def queryset(self, request, queryset):
        """Filter the licenses after their duration."""
        value_from = self.used_parameters.get(
            self.parameter_name + '_from', None)
        # Process the case when the parameter can be a list
        if isinstance(value_from, list):
            value_from = value_from[0] if value_from else None

        if value_from is not None and value_from != '':
            try:
                time_from = datetime.timedelta(minutes=int(value_from))
                queryset = queryset.filter(duration__gte=time_from)
            except (ValueError, TypeError):
                pass

        value_to = self.used_parameters.get(self.parameter_name + '_to', None)
        # Process the case when the parameter can be a list
        if isinstance(value_to, list):
            value_to = value_to[0] if value_to else None

        if value_to is not None and value_to != '':
            try:
                time_to = datetime.timedelta(minutes=int(value_to))
                queryset = queryset.filter(duration__lte=time_to)
            except (ValueError, TypeError):
                pass

        return queryset

    def expected_parameters(self):
        """Define expected parameters."""
        return [
            '{}_from'.format(self.parameter_name),
            '{}_to'.format(self.parameter_name),
        ]

    def choices(self, changelist):
        """Set the form."""
        # Get the parameter values, processing lists
        from_value = self.used_parameters.get(self.parameter_name + '_from', None)
        to_value = self.used_parameters.get(self.parameter_name + '_to', None)

        # Process the case when the parameter can be a list
        if isinstance(from_value, list):
            from_value = from_value[0] if from_value else None
        if isinstance(to_value, list):
            to_value = to_value[0] if to_value else None

        return ({
            'request': self.request,
            'parameter_name': self.parameter_name,
            'form': RangeNumericForm(name=self.parameter_name, data={
                self.parameter_name + '_from': from_value,
                self.parameter_name + '_to': to_value,
            }),
        }, )


class LicenseAdmin(ExportMixin, admin.ModelAdmin):
    """How should the Licenses be shown on the admin site."""

    form = LicenseAdminForm
    resource_classes = [LicenseResource]

    change_form_template = 'admin/licenses_change_form_edit.html'
    list_display = (
        'title',
        'subtitle',
        'profile',
        'number',
        'duration',
        'created_at',
        'confirmed',
        'video_status',
    )
    autocomplete_fields = ['profile']

    ordering = ['-created_at']
    
    actions = ['search_videos_for_licenses']

    search_fields = [
        'title',
        'subtitle',
        'number',
        'description',
        'further_persons',
    ]
    search_help_text = _(
        'title, subtitle, number, description, further persons')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'subtitle', 'description', 'further_persons', 'tags')
        }),
        (_('Content Details'), {
            'fields': ('category', 'profile', 'duration', 'suggested_date')
        }),
        (_('Broadcasting Permissions'), {
            'fields': (
                'repetitions_allowed',
                'media_authority_exchange_allowed',
                'media_authority_exchange_allowed_other_states',
            ),
            'classes': ('collapse',),
        }),
        (_('Youth Protection'), {
            'fields': ('youth_protection_necessary', 'youth_protection_category'),
            'classes': ('collapse',),
        }),
        (_('Media Library & Special Formats'), {
            'fields': ('store_in_ok_media_library', 'is_screen_board', 'infoblock'),
            'classes': ('collapse',),
        }),
        (_('Status & Metadata'), {
            'fields': ('number', 'confirmed', 'created_at', 'video_file_info'),
            'classes': ('collapse',),
            'description': _('Number is auto-generated but can be manually changed if needed.')
        }),
    )
    readonly_fields = ('created_at', 'video_file_info')
    
    def video_file_info(self, obj):
        """Display video file information if exists."""
        from django.urls import reverse
        from django.utils.html import format_html
        
        if not obj.pk:
            return '-'
        
        try:
            video_file = obj.get_video_file()
            if video_file:
                
                url = reverse('admin:media_files_videofile_change', args=[video_file.id])
                
                # Icon based on availability
                icon = '🎬' if video_file.is_available else '⚠️'
                
                # Build info string
                info_parts = []
                if video_file.duration:
                    info_parts.append(f'{video_file.duration}')
                if video_file.resolution_display:
                    info_parts.append(video_file.resolution_display)
                if video_file.file_size_mb:
                    info_parts.append(f'{video_file.file_size_mb} MB')
                
                info = ' • '.join(info_parts) if info_parts else ''
                
                # Status
                status_text = _('Available') if video_file.is_available else _('Not available')
                status_class = 'success' if video_file.is_available else 'warning'
                
                # Check if duration needs sync (only if difference >= 1 second)
                duration_warning = ''
                if video_file.duration and obj.duration:
                    # Calculate difference in seconds
                    video_seconds = int(video_file.duration.total_seconds())
                    license_seconds = int(obj.duration.total_seconds())
                    duration_diff = abs(video_seconds - license_seconds)
                    
                    # Only show warning if difference is 1 second or more
                    if duration_diff >= 1:
                        duration_warning = format_html(
                            '<br><span style="color: #ff9800; font-weight: bold;">⚠️ {}: {} ({})</span>'
                            '<br><button type="submit" name="_sync_duration_from_video" '
                            'style="margin-top: 5px; padding: 5px 10px; background: #417690; color: white; '
                            'border: none; border-radius: 4px; cursor: pointer;">'
                            '🔄 {}</button>',
                            _('Duration mismatch'),
                            _('License'),
                            obj.duration,
                            _('Sync from Video')
                        )
                
                return format_html(
                    '{} <a href="{}">{}</a><br>'
                    '<span style="color: #666;">{}</span><br>'
                    '<span class="badge badge-{}">{}</span> • <span style="color: #666;">{}</span>'
                    '{}',
                    icon,
                    url,
                    video_file.filename,
                    info,
                    status_class,
                    status_text,
                    video_file.storage_location.name if video_file.storage_location else '-',
                    duration_warning
                )
            else:
                search_url = reverse('admin:licenses_license_search_video', args=[obj.id])
                return format_html(
                    '<span style="color: #999;">❌ {}</span><br>'
                    '<a href="{}" class="button" style="padding: 5px 10px; background: #417690; color: white; '
                    'text-decoration: none; border-radius: 4px; margin-top: 5px; display: inline-block;">'
                    '🔍 {}</a>',
                    _('No video file found'),
                    search_url,
                    _('Search for Video')
                )
        except Exception as e:
            return format_html('<span style="color: #999;">-</span>')
    
    video_file_info.short_description = _('Video File')
    
    def video_status(self, obj):
        """Display video status and play link in list view."""
        from django.urls import reverse
        from django.utils.html import format_html
        
        if not obj.pk:
            return '-'
        
        try:
            video_file = obj.get_video_file()
            if video_file:
                
                # Check if video is available
                if video_file.is_available:
                    # Create link to Video.js player page
                    player_url = reverse('admin:media_files_videofile_player', args=[video_file.id])
                    
                    return format_html(
                        '<span style="color: #28a745;">🎬 {}</span><br>'
                        '<a href="{}" target="_blank" style="color: #007bff; text-decoration: none;">'
                        '▶️ Плеер</a>',
                        _('Available'),
                        player_url
                    )
                else:
                    return format_html(
                        '<span style="color: #ffc107;">⚠️ {}</span>',
                        _('Not available')
                    )
            else:
                return format_html(
                    '<span style="color: #999;">❌ {}</span>',
                    _('No video')
                )
        except Exception as e:
            return format_html('<span style="color: #999;">-</span>')
    
    video_status.short_description = _('Video')
    
    
    # PERFORMANCE OPTIMIZATION: Reduce N+1 queries in list view
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        return super().get_queryset(request).select_related(
            'profile',
            'profile__okuser', 
            'profile__media_authority', 
            'category',
            'video_file',  # OneToOneField to VideoFile
            'video_file__storage_location'
        )  # tags is JSONField, not ManyToMany - no prefetch needed
    
    def get_fieldsets(self, request, obj=None):
        """Remove 'number' field from fieldsets when adding new license."""
        fieldsets = super().get_fieldsets(request, obj)
        
        # If creating new object, remove 'number' from Status & Metadata fieldset
        if obj is None:
            fieldsets = list(fieldsets)
            status_metadata_idx = 5  # Index of 'Status & Metadata' fieldset
            
            # Make a mutable copy of the fieldset
            status_metadata = list(fieldsets[status_metadata_idx])
            status_metadata_fields = dict(status_metadata[1])
            
            # Remove 'number' from fields
            status_metadata_fields['fields'] = tuple(
                f for f in status_metadata_fields['fields'] if f != 'number'
            )
            
            # Rebuild the fieldset
            status_metadata[1] = status_metadata_fields
            fieldsets[status_metadata_idx] = tuple(status_metadata)
            
            return tuple(fieldsets)
        
        return fieldsets

    actions = ['confirm', 'unconfirm', 'duplicate_license']

    list_filter = [
        AutocompleteFilterFactory(_('Profile'), 'profile'),
        ('created_at', CustomDateTimeRangeFilter),
        YearFilter,
        ('duration', DurationRangeFilter),
        AutocompleteFilterFactory(
            _('Media Authority'), 'profile__media_authority'),
        AutocompleteFilterFactory(_('Category'), 'category'),
        'store_in_ok_media_library',
        WithoutContributionFilter,
    ]

    def get_rangefilter_created_at_title(self, request, field_path):
        """Set a custom filter name for created_at DateTimeRangeFilter."""
        return _('Created at')

    @admin.action(description=_('Confirm selected Licenses'))
    def confirm(self, request, queryset):
        """Confirm all selected profiles."""
        updated = self._set_confirmed(request, queryset, True)
        self.message_user(request, _p(
            '%d License was successfully confirmed.',
            '%d Licenses were successfully confirmed.',
            updated
        ) % updated, messages.SUCCESS)

    @admin.action(description=_('Unconfirm selected Licenses'))
    def unconfirm(self, request, queryset):
        """Unconfirm all selected profiles."""
        updated = self._set_confirmed(request, queryset, False)
        self.message_user(request, _p(
            '%d License was successfully unconfirmed.',
            '%d Licenses were successfully unconfirmed.',
            updated
        ) % updated, messages.SUCCESS)

    @admin.action(description=_('Create a copy of selected licenses'))
    def duplicate_license(self, request, queryset):
        """Create a copy of selected licenses."""
        from .models import License
        for obj in queryset:
            obj.pk = None  # reset id
            # Generate a new unique number
            max_number = License.objects.order_by('-number').first()
            obj.number = (max_number.number + 1) if max_number else 1
            obj.confirmed = False  # the copy is not confirmed
            obj.save()
        self.message_user(request, _('License copies created successfully.'), messages.SUCCESS)

    def _set_confirmed(self, request, queryset, value: bool):
        """
        Set the 'confirmed' attribute.

        Return the amount of updated objects.
        """
        updated = 0
        for obj in queryset:
            if obj.confirmed == value:
                continue

            if value and not obj.profile.verified:
                # do not confirm LR of unverified users
                self.message_user(
                    request,
                    _('The corresponding profile of %(obj)s is not verified.'
                      ' The License can not be confirmed until the'
                      ' profile is verified.') % {'obj': obj},
                    messages.ERROR
                )
                continue

            obj.confirmed = value
            # in case we need to do further actions when a license is
            # confirmed later
            obj.save(update_fields=['confirmed'])
            updated += 1

        return updated

    def change_view(
            self, request, object_id, form_url="", extra_context=None):
        """Don't show the save buttons if LR is confirmed."""
        license = get_object_or_404(License, pk=object_id)
        extra_context = extra_context or {}

        extra_context['object'] = license

        if license.confirmed:
            extra_context['show_save_and_continue'] = False
            extra_context['show_save'] = False
            extra_context['show_save_and_add_another'] = False

        return super().changeform_view(
            request, object_id, form_url, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        """Exclude the number field."""
        self.exclude = ['number']
        result = super().add_view(request, form_url, extra_context)
        # Because exclude is also used by change_view
        self.exclude = None

        return result

    def response_change(self, request, obj: License):
        """Add Print license and Sync duration buttons to change view."""
        if '_print_license' in request.POST:
            return generate_license_file(obj)
        
        if '_sync_duration_from_video' in request.POST:
            # Get associated video file
            video_file = obj.get_video_file()
            if video_file and video_file.duration:
                from datetime import timedelta
                old_duration = obj.duration
                # Round to seconds (hh:mm:ss format)
                rounded_duration = timedelta(seconds=int(video_file.duration.total_seconds()))
                obj.duration = rounded_duration
                obj.save(update_fields=['duration'])
                self.message_user(
                    request,
                    _('Duration synced from video: {} → {}').format(old_duration, rounded_duration),
                    messages.SUCCESS
                )
            elif not video_file:
                self.message_user(
                    request,
                    _('No video file found for this license.'),
                    messages.WARNING
                )
            else:
                self.message_user(
                    request,
                    _('Video file has no duration information.'),
                    messages.WARNING
                )
            return HttpResponseRedirect(request.path)
        
        return super().response_change(request, obj)
    
    def get_urls(self):
        """Add custom URLs for license management."""
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path(
                '<int:license_id>/search-video/',
                self.admin_site.admin_view(self.search_video_view),
                name='licenses_license_search_video',
            ),
        ]
        return custom_urls + urls
    
    def search_video_view(self, request, license_id):
        """Search for video matching this license number."""
        from django.shortcuts import redirect
        from django.contrib import messages
        from django.core.management import call_command
        from io import StringIO
        
        try:
            license_obj = License.objects.get(id=license_id)
            
            # First, scan all storages to find latest videos
            self.message_user(
                request,
                f'Сканирование хранилищ для поиска видео #{license_obj.number}...',
                messages.INFO
            )
            
            # Capture command output
            out = StringIO()
            call_command('link_orphan_licenses', number=license_obj.number, stdout=out)
            output = out.getvalue()
            
            # Check if video was found
            if 'Found video' in output or 'Videos found:' in output:
                messages.success(
                    request,
                    f'✓ Видео найдено и связано с лицензией #{license_obj.number}!'
                )
            elif 'No video found' in output:
                messages.warning(
                    request,
                    f'⚠️ Видео с номером {license_obj.number} не найдено в хранилищах. '
                    f'Убедитесь, что файл существует и начинается с номера.'
                )
            else:
                messages.info(request, f'Поиск завершен. Проверьте результаты.')
            
        except License.DoesNotExist:
            messages.error(request, f'License #{license_id} not found')
        except Exception as e:
            messages.error(request, f'Error searching for video: {str(e)}')
            logger.error(f'Error in search_video_view for license {license_id}: {str(e)}', exc_info=True)
        
        return redirect('admin:licenses_license_change', license_id)
    
    @admin.action(description=_('Search for videos in storage'))
    def search_videos_for_licenses(self, request, queryset):
        """Search for videos matching selected licenses."""
        from django.core.management import call_command
        from io import StringIO
        
        found_count = 0
        not_found_count = 0
        error_count = 0
        
        for license_obj in queryset:
            try:
                # Search for video with this number
                out = StringIO()
                call_command('link_orphan_licenses', number=license_obj.number, stdout=out)
                output = out.getvalue()
                
                if 'Found video' in output or 'Videos found:' in output:
                    found_count += 1
                elif 'No video found' in output:
                    not_found_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(f'Error searching for video for license {license_obj.number}: {str(e)}')
        
        # Summary messages
        if found_count > 0:
            self.message_user(
                request,
                f'✓ Найдено и связано видео для {found_count} лицензий',
                messages.SUCCESS
            )
        if not_found_count > 0:
            self.message_user(
                request,
                f'⚠️ Не найдено видео для {not_found_count} лицензий',
                messages.WARNING
            )
        if error_count > 0:
            self.message_user(
                request,
                f'❌ Ошибки при поиске: {error_count}',
                messages.ERROR
            )


admin.site.register(License, LicenseAdmin)


class CategoryAdmin(admin.ModelAdmin):
    """Define search_fields for AutocompleteFilterFactory."""

    search_fields = ['name']


admin.site.register(Category, CategoryAdmin)
