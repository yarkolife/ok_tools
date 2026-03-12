from .forms import ImportJSONForm
from .forms import RangeNumericForm
from .generate_file import generate_license_file
from .models import Category
from .models import License
from .models import LicensesConfig
from .models import NextcloudVideoFile
from .widgets import TagsInputWidget
from admin_auto_filters.filters import AutocompleteFilterFactory
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext as _p
from import_export import resources
from import_export.admin import ExportMixin
from import_export.fields import Field
from ok_tools.datetime import TZ
from registration.models import MediaAuthority
from registration.models import Profile
from rangefilter.filters import DateTimeRangeFilter


try:
    from .forms import MediathekRescanPeriodForm
except ImportError:
    class MediathekRescanPeriodForm(forms.Form):
        """Fallback admin form for mediathek rescan period."""

        date_from = forms.DateField(
            label=_('Date from'),
            required=True,
            widget=forms.DateInput(attrs={'type': 'date'}),
        )
        date_to = forms.DateField(
            label=_('Date to'),
            required=True,
            widget=forms.DateInput(attrs={'type': 'date'}),
        )
        only_store_in_ok_media_library = forms.BooleanField(
            label=_('Only licenses stored in OK media library'),
            required=False,
            initial=True,
            help_text=_('If enabled, include only licenses with “Store in OK media library” set to Yes.'),
        )

        def clean(self):
            """Validate period boundaries."""
            cleaned_data = super().clean()
            date_from = cleaned_data.get('date_from')
            date_to = cleaned_data.get('date_to')

            if date_from and date_to and date_from > date_to:
                raise forms.ValidationError(
                    _('Date from must be earlier than or equal to Date to.')
                )

            return cleaned_data


class TranslatedDateTimeRangeFilter(DateTimeRangeFilter):
    """DateTimeRangeFilter with translated title."""

    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)
        self.title = "Erstellt am"


import datetime
import json
import logging
from difflib import SequenceMatcher


logger = logging.getLogger('django')


def get_category_by_id(category_id):
    """Get Category by numeric ID."""
    try:
        category = Category.objects.get(numeric_id=category_id)
        return category
    except Category.DoesNotExist:
        logger.warning(f'Unknown category ID: {category_id}')
        return None


def get_category_by_name(category_name):
    """Get Category by name."""
    try:
        category = Category.objects.get(name=category_name)
        return category
    except Category.DoesNotExist:
        logger.warning(f'Unknown category name: {category_name}')
        return None


def get_profile_by_name(name):
    """Get Profile by full name (e.g., 'Bernd Krüger')."""
    if not name:
        return None
    
    # Split name into first and last name
    name_parts = name.strip().split(maxsplit=1)
    if len(name_parts) == 1:
        # Only one name part - try as first_name or last_name
        first_name = name_parts[0]
        last_name = None
    else:
        first_name = name_parts[0]
        last_name = name_parts[1]
    
    # Try exact match first
    if last_name:
        profile = Profile.objects.filter(
            first_name=first_name,
            last_name=last_name
        ).first()
    else:
        # Try as first_name only
        profile = Profile.objects.filter(
            first_name=first_name
        ).first()
        if not profile:
            # Try as last_name only
            profile = Profile.objects.filter(
                last_name=first_name
            ).first()
    
    if not profile and last_name:
        # Try case-insensitive match
        profile = Profile.objects.filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name
        ).first()
    
    return profile


def create_profile_by_name(name, media_authority=None):
    """Create a new Profile by name with optional media_authority."""
    if not name:
        return None
    
    # Split name into first and last name
    name_parts = name.strip().split(maxsplit=1)
    if len(name_parts) == 1:
        first_name = name_parts[0]
        last_name = None
    else:
        first_name = name_parts[0]
        last_name = name_parts[1]
    
    # Get or use default media_authority
    if not media_authority:
        from django.conf import settings
        media_authority, _created = MediaAuthority.objects.get_or_create(
            name=settings.OK_NAME_SHORT
        )
    
    # Create profile
    profile = Profile.objects.create(
        first_name=first_name,
        last_name=last_name,
        media_authority=media_authority,
        verified=False,
        member=False,
    )
    
    logger.info(f'Created new profile: {first_name} {last_name or ""} (ID: {profile.id})')
    return profile


def get_profile_by_target_channel(target_channel):
    """Get Profile by targetChannel."""
    try:
        media_authority = MediaAuthority.objects.get(target_channel=target_channel)
    except MediaAuthority.DoesNotExist:
        logger.warning(f'Unknown targetChannel: {target_channel}')
        return None
    
    # Try to find a profile with this media_authority
    # Prefer verified profiles, then members, then any profile
    profile = Profile.objects.filter(
        media_authority=media_authority,
        verified=True
    ).first()
    
    if not profile:
        profile = Profile.objects.filter(
            media_authority=media_authority,
            member=True
        ).first()
    
    if not profile:
        profile = Profile.objects.filter(
            media_authority=media_authority
        ).first()
    
    return profile


def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings (0.0 to 1.0)."""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower().strip(), str2.lower().strip()).ratio()


def find_potential_duplicates(title, profile, threshold=0.8):
    """
    Find potential duplicate licenses by title and profile.
    
    Args:
        title: License title to check
        profile: Profile object to check
        threshold: Similarity threshold (default 0.8 = 80%)
    
    Returns:
        QuerySet of potential duplicate licenses
    """
    if not title or not profile:
        return License.objects.none()
    
    # Get all licenses for this profile
    profile_licenses = License.objects.filter(profile=profile)
    
    # Find licenses with similar titles
    potential_duplicates = []
    for license_obj in profile_licenses:
        similarity = similarity_ratio(title, license_obj.title)
        if similarity >= threshold:
            potential_duplicates.append(license_obj)
    
    # Return as QuerySet
    if potential_duplicates:
        return License.objects.filter(
            id__in=[dup.id for dup in potential_duplicates]
        ).order_by('-created_at')
    
    return License.objects.none()


class CustomDateTimeRangeFilter(admin.FieldListFilter):
    """Custom filter for date and time range, compatible with Django 5+."""

    template = 'admin/filter_datetime_range.html'
    title = _('Created at')

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
    created_at = _f('created_at', _('Created at'))

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
                msg = _('Invalid value %(value)s.') % {'value': self.value()}
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
                msg = _('Invalid value %(value)s.') % {'value': self.value()}
                logger.error(msg)
                raise ValueError(msg)


class GlobalProducerFilter(admin.SimpleListFilter):
    """Filter licenses by global_producer status from Profile."""

    title = _('Global Producer')
    parameter_name = 'profile__global_producer'

    def lookups(self, request, model_admin):
        """Define filter options."""
        return (
            ('1', _('Yes')),
            ('0', _('No')),
        )

    def queryset(self, request, queryset):
        """Filter licenses by global_producer status."""
        if self.value() == '1':
            return queryset.filter(profile__global_producer=True)
        elif self.value() == '0':
            return queryset.filter(profile__global_producer=False)
        return queryset


class HasMediathekUrlFilter(admin.SimpleListFilter):
    """Filter licenses by mediathek URL presence."""

    title = _('Has Mediathek URL')
    parameter_name = 'has_mediathek_url'

    def lookups(self, request, model_admin):
        """Define filter options."""
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )

    def queryset(self, request, queryset):
        """Filter licenses by mediathek URL presence."""
        if self.value() == 'yes':
            return queryset.filter(mediathek_url__isnull=False).exclude(mediathek_url='')
        elif self.value() == 'no':
            return queryset.filter(mediathek_url__isnull=True) | queryset.filter(mediathek_url='')
        return queryset


class HasVideoFilter(admin.SimpleListFilter):
    """Filter licenses by video file presence and availability."""

    title = _('Has video')
    parameter_name = 'has_video'

    def lookups(self, request, model_admin):
        """Define filter options."""
        return (
            ('available', _('Available')),
            ('not_available', _('Not available')),
            ('no_video', _('No video')),
        )

    def queryset(self, request, queryset):
        """Filter licenses by video file presence and availability."""
        from django.conf import settings
        
        # Skip filtering if media_files module is disabled
        if not getattr(settings, 'MEDIA_FILES_ENABLED', False):
            return queryset
        
        if self.value() == 'available':
            return queryset.filter(video_file__isnull=False, video_file__is_available=True)
        elif self.value() == 'not_available':
            return queryset.filter(video_file__isnull=False, video_file__is_available=False)
        elif self.value() == 'no_video':
            return queryset.filter(video_file__isnull=True)
        return queryset


class LicenseAdminForm(forms.ModelForm):
    """Override the clean method for the forms used on the admin site."""

    class Meta:
        model = License
        fields = '__all__'
        widgets = {
            'tags': TagsInputWidget(),
            'youth_protection_necessary': forms.NullBooleanSelect(),
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
    change_list_template = 'admin/licenses/license/change_list.html'
    list_display = (
        'title',
        'subtitle',
        'profile',
        'number',
        'duration',
        'created_at',
        'confirmed',
        'has_signature',
        'video_status',
    )
    autocomplete_fields = ['profile']

    ordering = ['-created_at']
    
    def delete_queryset(self, request, queryset):
        """Clear dashboard UserJourney references before delete to satisfy FK constraint."""
        try:
            from dashboard.models import UserJourney
            license_ids = list(queryset.values_list('id', flat=True))
            if license_ids:
                UserJourney.objects.filter(license_id__in=license_ids).update(license_id=None)
        except Exception:
            pass
        super().delete_queryset(request, queryset)

    def changelist_view(self, request, extra_context=None):
        """Add import JSON URL to changelist context."""
        extra_context = extra_context or {}
        from django.urls import reverse
        extra_context['import_json_url'] = reverse('admin:licenses_license_import_json')
        return super().changelist_view(request, extra_context=extra_context)

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
                'is_live',
                'repetitions_allowed',
                'media_authority_exchange_allowed',
                'media_authority_exchange_allowed_other_states',
            ),
        }),
        (_('Youth Protection'), {
            'fields': ('youth_protection_necessary', 'youth_protection_category'),
        }),
        (_('Media Library & Special Formats'), {
            'fields': ('store_in_ok_media_library', 'is_screen_board', 'infoblock'),
        }),
        (_('Status & Metadata'), {
            'fields': (
                'number',
                'confirmed',
                'created_at',
                'has_signature_display',
                'video_file_info',
                'mediathek_url_display',
                'mediathek_url_updated_at',
            ),
            'description': _('Number is auto-generated but can be manually changed if needed.')
        }),
    )
    readonly_fields = (
        'created_at',
        'has_signature_display',
        'video_file_info',
        'mediathek_url_display',
        'mediathek_url_updated_at',
    )
    
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
                # Icon based on availability (film icon / warning triangle)
                _film_svg = (
                    '<svg class="icon-svg" viewBox="0 0 24 24" fill="none"'
                    ' stroke="currentColor" stroke-width="2" width="16" height="16"'
                    ' stroke-linecap="round" stroke-linejoin="round"'
                    ' style="vertical-align: text-bottom;">'
                    '<rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect>'
                    '<line x1="7" y1="2" x2="7" y2="22"></line>'
                    '<line x1="17" y1="2" x2="17" y2="22"></line>'
                    '<line x1="2" y1="12" x2="22" y2="12"></line>'
                    '<line x1="2" y1="7" x2="7" y2="7"></line>'
                    '<line x1="2" y1="17" x2="7" y2="17"></line>'
                    '<line x1="17" y1="17" x2="22" y2="17"></line>'
                    '<line x1="17" y1="7" x2="22" y2="7"></line>'
                    '</svg>'
                )
                _warn_svg = (
                    '<svg class="icon-svg" viewBox="0 0 24 24" fill="none"'
                    ' stroke="currentColor" stroke-width="2.5" width="16" height="16"'
                    ' stroke-linecap="round" stroke-linejoin="round"'
                    ' style="vertical-align: text-bottom;">'
                    '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94'
                    'a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>'
                    '<line x1="12" y1="9" x2="12" y2="13"></line>'
                    '<line x1="12" y1="17" x2="12.01" y2="17"></line>'
                    '</svg>'
                )
                icon = mark_safe(_film_svg if video_file.is_available else _warn_svg)
                
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
                            '<br><span style="color: #ff9800; font-weight: bold;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> {}: {} ({})</span>'
                            '<br><button type="submit" name="_sync_duration_from_video" '
                            'style="margin-top: 5px; padding: 5px 10px; background: #417690; color: white; '
                            'border: none; border-radius: 4px; cursor: pointer;">'
                            '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> {}</button>',
                            _('Duration mismatch'),
                            _('License'),
                            obj.duration,
                            _('Sync from Video')
                        )
                
                # Render button if video is available
                render_button = ''
                if video_file.is_available:
                    render_url = reverse('media_files:render_video_admin', args=[video_file.id])
                    render_button = format_html(
                        '<br><a href="{}" class="button" style="padding: 8px 16px; background: #28a745; color: white; '
                        'text-decoration: none; border-radius: 4px; margin-top: 5px; display: inline-block;">'
                        '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg> {}</a>',
                        render_url,
                        _('Render Video with Overlays')
                    )
                
                return format_html(
                    '{} <a href="{}">{}</a><br>'
                    '<span style="color: #666;">{}</span><br>'
                    '<span class="badge badge-{}">{}</span> • <span style="color: #666;">{}</span>'
                    '{}{}',
                    icon,
                    url,
                    video_file.filename,
                    info,
                    status_class,
                    status_text,
                    video_file.storage_location.name if video_file.storage_location else '-',
                    duration_warning,
                    render_button
                )
            else:
                search_url = reverse('admin:licenses_license_search_video', args=[obj.id])
                return format_html(
                    '<span style="color: #999;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg> {}</span><br>'
                    '<a href="{}" class="button" style="padding: 5px 10px; background: #417690; color: white; '
                    'text-decoration: none; border-radius: 4px; margin-top: 5px; display: inline-block;">'
                    '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> {}</a>',
                    _('No video file found'),
                    search_url,
                    _('Search for Video')
                )
        except Exception as e:
            return format_html('<span style="color: #999;">-</span>')
    
    video_file_info.short_description = _('Video File')

    def mediathek_url_display(self, obj):
        """Display mediathek watch URL with quick actions."""
        if not obj or not obj.pk:
            return '-'

        refresh_url = reverse('admin:licenses_license_refresh_mediathek', args=[obj.id])
        clear_url = reverse('admin:licenses_license_clear_mediathek', args=[obj.id])

        if obj.mediathek_url:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">{}</a><br>'
                '<div style="margin-top: 6px;">'
                '<a class="button" href="{}" style="margin-right: 6px;">{}</a> '
                '<a class="button" href="{}">{}</a>'
                '</div>',
                obj.mediathek_url,
                obj.mediathek_url,
                refresh_url,
                _('Refresh URL'),
                clear_url,
                _('Clear URL'),
            )

        return format_html(
            '<span style="color: #999;">{}</span><br>'
            '<div style="margin-top: 6px;">'
            '<a class="button" href="{}">{}</a>'
            '</div>',
            _('No mediathek URL set'),
            refresh_url,
            _('Refresh URL'),
        )

    mediathek_url_display.short_description = _('Mediathek URL')
    
    def video_status(self, obj):
        """Display video status with modal player link in list view.

        Priority: 1) Local VideoFile (Player) if available — e.g. after Nextcloud
        download; 2) NextcloudVideoFile (☁️) if no local; 3) No video. This avoids
        showing the NC icon when the video is already in media_files and playable.
        """
        from django.urls import reverse
        from django.utils.html import format_html
        from django.conf import settings

        if not obj.pk:
            return '-'

        # 1) Prefer local VideoFile (media_files): after NC download it exists and is playable
        try:
            video_file = obj.get_video_file()
            if video_file:
                # Check if video is available
                if video_file.is_available:
                    stream_url = reverse('admin:media_files_videofile_stream', args=[video_file.id])
                    
                    # Prepare additional fields for modal
                    number = video_file.number or ''
                    storage_name = video_file.storage_location.name if video_file.storage_location else ''
                    duration = str(video_file.duration) if video_file.duration else 'N/A'
                    size_display = f"{video_file.file_size_mb} MB" if video_file.file_size_mb else 'N/A'
                    bitrate_display = f"{video_file.total_bitrate} bps" if video_file.total_bitrate else 'N/A'
                    
                    # Return clickable link with modal attributes (Bootstrap 5)
                    return format_html(
                        '<span style="color: #28a745;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg> {}</span><br>'
                        '<a href="javascript:void(0);" '
                        'data-bs-toggle="modal" '
                        'data-bs-target="#videoPlayerModal" '
                        'data-url="{}" '
                        'data-filename="{}" '
                        'data-number="{}" '
                        'data-storage="{}" '
                        'data-duration="{}" '
                        'data-size="{}" '
                        'data-bitrate="{}" '
                        'style="color: #007bff; text-decoration: none; cursor: pointer;">'
                        '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> {}</a>',
                        _('Available'),
                        stream_url,
                        video_file.filename or '',
                        number,
                        storage_name,
                        duration,
                        size_display,
                        bitrate_display,
                        _('Player')
                    )
                else:
                    return format_html(
                        '<span style="color: #ffc107;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> {}</span>',
                        _('Not available')
                    )

            # 2) No local VideoFile — show Nextcloud if present
            if settings.NEXTCLOUD_ENABLED:
                if hasattr(obj, 'active_nextcloud_videos') and obj.active_nextcloud_videos:
                    nextcloud_video = obj.active_nextcloud_videos[0]
                else:
                    nextcloud_video = NextcloudVideoFile.objects.filter(
                        license=obj,
                        is_deleted=False
                    ).first()
                if nextcloud_video:
                    return format_html(
                        '<span style="color: #17a2b8;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path></svg> {}</span>',
                        _('Nextcloud Video')
                    )

            return format_html(
                '<span style="color: #999;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg> {}</span>',
                _('No video')
            )
        except Exception:
            return format_html('<span style="color: #999;">-</span>')

    video_status.short_description = _('Video')
    
    def has_signature(self, obj):
        """Display signature status in list view."""
        if not obj.pk:
            return '-'
        
        if obj.has_any_signature():
            return format_html(
                '<span style="color: #28a745;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="20 6 9 17 4 12"></polyline></svg> {}</span>',
                _('Yes')
            )
        else:
            return format_html(
                '<span style="color: #999;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg> {}</span>',
                _('No')
            )
    
    has_signature.short_description = _('Signature')
    has_signature.admin_order_field = 'signature'
    
    def has_signature_display(self, obj):
        """Display signature status in change form."""
        if not obj.pk:
            return '-'
        
        if obj.has_any_signature():
            return format_html(
                '<span style="color: #28a745; font-weight: bold;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="20 6 9 17 4 12"></polyline></svg> {}</span>',
                _('Digital signature is present')
            )
        else:
            return format_html(
                '<span style="color: #999;"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg> {}</span>',
                _('No digital signature')
            )
    
    has_signature_display.short_description = _('Digital Signature')
    
    
    # PERFORMANCE OPTIMIZATION: Reduce N+1 queries in list view
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        from django.conf import settings
        from django.db.models import Prefetch
        
        queryset = super().get_queryset(request).select_related(
            'profile',
            'profile__okuser',
            'profile__media_authority',
            'category'
        )
        
        # Prefetch video_file only if media_files module is enabled
        if getattr(settings, 'MEDIA_FILES_ENABLED', False):
            try:
                queryset = queryset.prefetch_related(
                    'video_file',  # OneToOneField from VideoFile to License
                    'video_file__storage_location'
                )
            except (AttributeError, Exception):
                # If video_file relation doesn't exist (module disabled), skip prefetch
                pass
        
        # Prefetch Nextcloud videos if enabled
        if settings.NEXTCLOUD_ENABLED:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'nextcloud_videos',
                    queryset=NextcloudVideoFile.objects.filter(is_deleted=False),
                    to_attr='active_nextcloud_videos'
                )
            )
        
        return queryset
    
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

    actions = [
        'confirm',
        'unconfirm',
        'duplicate_license',
        'search_videos_for_licenses',
        'clear_mediathek_url_action',
        'refresh_mediathek_url_action',
    ]

    list_filter = [
        AutocompleteFilterFactory(_('Profile'), 'profile'),
        'created_at',
        YearFilter,
        ('duration', DurationRangeFilter),
        AutocompleteFilterFactory(
            _('Media Authority'), 'profile__media_authority'),
        AutocompleteFilterFactory(_('Category'), 'category'),
        'is_live',
        'store_in_ok_media_library',
        GlobalProducerFilter,
        HasVideoFilter,
        HasMediathekUrlFilter,
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
        
        if '_download_pdf' in request.POST:
            from .generate_file import normalize_filename
            # Generate filename: Nummer_Titel.pdf
            title_normalized = normalize_filename(obj.title) if obj.title else 'Untitled'
            filename = f"{obj.number}_{title_normalized}.pdf"
            return generate_license_file(obj, filename=filename, as_attachment=True)
        
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
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                'rescan-mediathek/',
                self.admin_site.admin_view(self.rescan_mediathek_view),
                name='licenses_license_rescan_mediathek',
            ),
            path(
                'import-json/',
                self.admin_site.admin_view(self.import_json_view),
                name='licenses_license_import_json',
            ),
            path(
                '<int:license_id>/search-video/',
                self.admin_site.admin_view(self.search_video_view),
                name='licenses_license_search_video',
            ),
            path(
                '<int:license_id>/refresh-mediathek/',
                self.admin_site.admin_view(self.refresh_mediathek_view),
                name='licenses_license_refresh_mediathek',
            ),
            path(
                '<int:license_id>/clear-mediathek/',
                self.admin_site.admin_view(self.clear_mediathek_view),
                name='licenses_license_clear_mediathek',
            ),
        ]
        return custom_urls + urls

    def refresh_mediathek_view(self, request, license_id):
        """Queue mediathek URL refresh for one license from admin change view."""
        from django.shortcuts import redirect

        from .tasks import refresh_license_mediathek_url

        license_obj = get_object_or_404(License, pk=license_id)
        refresh_license_mediathek_url.delay(
            int(license_obj.number),
            force=True,
            send_notification_email=False,
        )
        self.message_user(
            request,
            _('Mediathek URL refresh queued for license #%(number)s.') % {
                'number': license_obj.number,
            },
            messages.SUCCESS,
        )
        return redirect('admin:licenses_license_change', license_id)

    def clear_mediathek_view(self, request, license_id):
        """Clear mediathek URL for one license from admin change view."""
        from django.shortcuts import redirect

        license_obj = get_object_or_404(License, pk=license_id)
        license_obj.mediathek_url = None
        license_obj.mediathek_url_updated_at = timezone.now()
        license_obj.save(update_fields=['mediathek_url', 'mediathek_url_updated_at'])
        self.message_user(
            request,
            _('Mediathek URL cleared for license #%(number)s.') % {
                'number': license_obj.number,
            },
            messages.SUCCESS,
        )
        return redirect('admin:licenses_license_change', license_id)

    def rescan_mediathek_view(self, request):
        """Render and process admin form to trigger mediathek rescan by period."""
        from datetime import date
        from django.shortcuts import redirect
        from django.shortcuts import render
        from django.utils import timezone

        from .tasks import rescan_mediathek_links_for_period

        if request.method == 'POST':
            form = MediathekRescanPeriodForm(request.POST)
            if form.is_valid():
                date_from = form.cleaned_data['date_from']
                date_to = form.cleaned_data['date_to']
                only_store = form.cleaned_data['only_store_in_ok_media_library']

                rescan_mediathek_links_for_period.delay(
                    start_date_iso=date_from.isoformat(),
                    end_date_iso=date_to.isoformat(),
                    only_store_in_ok_media_library=bool(only_store),
                    requested_by_user_id=request.user.pk if request.user and request.user.is_authenticated else None,
                )

                self.message_user(
                    request,
                    _('Mediathek rescan has been queued in the background.'),
                    messages.SUCCESS,
                )
                return redirect('admin:licenses_license_changelist')
        else:
            form = MediathekRescanPeriodForm(
                initial={
                    'date_from': date(2025, 1, 1),
                    'date_to': timezone.localdate(),
                    'only_store_in_ok_media_library': True,
                }
            )

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': _('Rescan mediathek links'),
            'form': form,
        }
        return render(request, 'admin/licenses/rescan_mediathek.html', context)
    
    def search_video_view(self, request, license_id):
        """Search for video matching this license number."""
        from django.shortcuts import redirect
        from django.contrib import messages
        from django.core.management import call_command
        from io import StringIO
        from media_files.models import VideoFile
        
        try:
            license_obj = License.objects.get(id=license_id)
            
            # First, scan all storages to find latest videos
            self.message_user(
                request,
                f'{_("Scanning storages for video")} #{license_obj.number}...',
                messages.INFO
            )
            
            # Capture command output
            out = StringIO()
            call_command('link_orphan_licenses', number=license_obj.number, stdout=out)
            output = out.getvalue()
            
            # Refresh license from DB to check if video was actually linked
            license_obj.refresh_from_db()
            
            # Check if video is now linked (via OneToOne relation or by number)
            video_linked = False
            try:
                # First check via OneToOne relation (reverse lookup)
                if hasattr(license_obj, 'video_file') and license_obj.video_file:
                    video_linked = True
                else:
                    # Fallback: check by number
                    video_linked = VideoFile.objects.filter(
                        number=license_obj.number,
                        is_available=True
                    ).exists()
            except VideoFile.DoesNotExist:
                pass
            
            # Show appropriate message based on actual result
            if video_linked:
                messages.success(
                    request,
                    _('Video found and linked to license') + f' #{license_obj.number}!'
                )
            elif 'No video found' in output or 'not found' in output.lower():
                messages.warning(
                    request,
                    f'{_("Video with number")} {license_obj.number} {_("not found in storages")}. '
                    f'{_("Make sure the file exists and starts with the number")}.'
                )
            elif 'Error' in output:
                # Extract error message from output
                messages.error(
                    request,
                    f'{_("Error linking video")}: {output}'
                )
            else:
                messages.info(request, f'{_("Search completed. Check the results")}.')
            
        except License.DoesNotExist:
            messages.error(request, _('License #%(id)s not found') % {'id': license_id})
        except Exception as e:
            messages.error(request, _('Error searching for video: %(error)s') % {'error': str(e)})
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
                _('Videos found and linked for') + f' {found_count} ' + (_('licenses') if found_count != 1 else _('license')),
                messages.SUCCESS
            )
        if not_found_count > 0:
            self.message_user(
                request,
                f'{_("No videos found for")} {not_found_count} {_("licenses") if not_found_count != 1 else _("license")}',
                messages.WARNING
            )
        if error_count > 0:
            self.message_user(
                request,
                f'{_("Search errors")}: {error_count}',
                messages.ERROR
            )

    @admin.action(description=_('Clear mediathek URL for selected licenses'))
    def clear_mediathek_url_action(self, request, queryset):
        """Admin action to clear mediathek URL for selected licenses."""
        updated = 0
        for obj in queryset:
            obj.mediathek_url = None
            obj.mediathek_url_updated_at = timezone.now()
            obj.save(update_fields=['mediathek_url', 'mediathek_url_updated_at'])
            updated += 1

        self.message_user(
            request,
            _p(
                '%d license mediathek URL was cleared.',
                '%d license mediathek URLs were cleared.',
                updated,
            ) % updated,
            messages.SUCCESS,
        )

    @admin.action(description=_('Refresh mediathek URL for selected licenses'))
    def refresh_mediathek_url_action(self, request, queryset):
        """Admin action to queue mediathek URL refresh for selected licenses."""
        from .tasks import refresh_license_mediathek_url

        queued = 0
        for obj in queryset:
            refresh_license_mediathek_url.delay(
                int(obj.number),
                force=True,
                send_notification_email=False,
            )
            queued += 1

        self.message_user(
            request,
            _p(
                '%d mediathek refresh task was queued.',
                '%d mediathek refresh tasks were queued.',
                queued,
            ) % queued,
            messages.SUCCESS,
        )
    
    def import_json_view(self, request):
        """Import License from JSON file."""
        from django.template.response import TemplateResponse
        from django.shortcuts import redirect
        
        # Handle duplicate confirmation
        if request.method == 'POST' and '_confirm_import' in request.POST:
            # Get license data from session
            license_data_json = request.session.get('pending_license_data')
            if not license_data_json:
                self.message_user(
                    request,
                    _('Session expired. Please try importing again.'),
                    messages.ERROR
                )
                return redirect('admin:licenses_license_import_json')
            
            try:
                license_data_dict = json.loads(license_data_json)
                
                # Restore model instances from IDs
                license_data = {}
                license_data['title'] = license_data_dict.get('title', '')
                license_data['description'] = license_data_dict.get('description', '')
                license_data['profile'] = Profile.objects.get(id=license_data_dict['profile'])
                license_data['category'] = Category.objects.get(id=license_data_dict['category'])
                license_data['media_authority_exchange_allowed'] = license_data_dict.get('media_authority_exchange_allowed', False)
                license_data['store_in_ok_media_library'] = license_data_dict.get('store_in_ok_media_library', False)
                license_data['repetitions_allowed'] = license_data_dict.get('repetitions_allowed', False)
                license_data['media_authority_exchange_allowed_other_states'] = license_data_dict.get('media_authority_exchange_allowed_other_states', False)
                license_data['youth_protection_necessary'] = license_data_dict.get('youth_protection_necessary', False)
                license_data['youth_protection_category'] = license_data_dict.get('youth_protection_category', 'none')
                license_data['is_screen_board'] = license_data_dict.get('is_screen_board', False)
                license_data['infoblock'] = license_data_dict.get('infoblock', False)
                license_data['confirmed'] = license_data_dict.get('confirmed', False)
                # Parse duration string back to timedelta
                duration_str = license_data_dict.get('duration', '0:00:00')
                parts = duration_str.split(':')
                if len(parts) == 3:
                    license_data['duration'] = datetime.timedelta(
                        hours=int(parts[0]),
                        minutes=int(parts[1]),
                        seconds=int(parts[2])
                    )
                else:
                    license_data['duration'] = datetime.timedelta(seconds=0)
                
                # Create License
                license_obj = License.objects.create(**license_data)
                
                # Clear session
                del request.session['pending_license_data']
                del request.session['pending_duplicates']
                
                self.message_user(
                    request,
                    _('License "%(title)s" successfully imported.') % {
                        'title': license_obj.title
                    },
                    messages.SUCCESS
                )
                
                # Redirect to the created license
                from django.urls import reverse
                return redirect(
                    reverse('admin:licenses_license_change', args=[license_obj.id])
                )
            except Exception as e:
                logger.error(f'Error creating license after confirmation: {str(e)}', exc_info=True)
                self.message_user(
                    request,
                    _('Error creating license: {}').format(str(e)),
                    messages.ERROR
                )
                return redirect('admin:licenses_license_import_json')
        
        # Handle cancel duplicate confirmation
        if request.method == 'POST' and '_cancel_import' in request.POST:
            # Clear session
            del request.session['pending_license_data']
            del request.session['pending_duplicates']
            
            self.message_user(
                request,
                _('Import cancelled.'),
                messages.INFO
            )
            return redirect('admin:licenses_license_import_json')
        
        # Handle initial JSON import
        if request.method == 'POST':
            form = ImportJSONForm(request.POST, request.FILES)
            if form.is_valid():
                json_file = request.FILES['json_file']
                try:
                    # Read and parse JSON
                    json_data = json.loads(json_file.read().decode('utf-8'))
                    
                    # Map JSON fields to License model
                    license_data = {}
                    
                    # Title from name
                    license_data['title'] = json_data.get('name', '')
                    
                    # Description
                    license_data['description'] = json_data.get('description', '')
                    
                    # Profile from senderResponsible (primary) or targetChannel (fallback)
                    profile = None
                    sender_responsible = json_data.get('senderResponsible')
                    target_channel = json_data.get('targetChannel')
                    
                    # Get media_authority from targetChannel if available
                    media_authority = None
                    if target_channel:
                        try:
                            media_authority = MediaAuthority.objects.get(target_channel=target_channel)
                        except MediaAuthority.DoesNotExist:
                            logger.warning(f'Unknown targetChannel: {target_channel}')
                    
                    # Try to find profile by senderResponsible
                    if sender_responsible:
                        profile = get_profile_by_name(sender_responsible)
                        if not profile:
                            # Profile not found - create it if we have media_authority
                            if media_authority:
                                profile = create_profile_by_name(sender_responsible, media_authority)
                                self.message_user(
                                    request,
                                    _('Profile not found for senderResponsible: %(name)s. '
                                      'Created new profile automatically.') % {
                                        'name': sender_responsible
                                    },
                                    messages.SUCCESS
                                )
                            else:
                                self.message_user(
                                    request,
                                    _('No profile found for senderResponsible: %(name)s. '
                                      'targetChannel is required to create a new profile.') % {
                                        'name': sender_responsible
                                    },
                                    messages.WARNING
                                )
                    
                    # Fallback to targetChannel if senderResponsible didn't work
                    if not profile:
                        if target_channel:
                            profile = get_profile_by_target_channel(target_channel)
                            if not profile:
                                self.message_user(
                                    request,
                                    _('No profile found for targetChannel: %(channel)s. '
                                      'Please create a profile manually in the admin.') % {
                                        'channel': target_channel
                                    },
                                    messages.ERROR
                                )
                                return TemplateResponse(
                                    request,
                                    'admin/licenses/import_json.html',
                                    {'form': form, 'opts': self.model._meta}
                                )
                        else:
                            self.message_user(
                                request,
                                _('Either senderResponsible or targetChannel is required in JSON file.'),
                                messages.ERROR
                            )
                            return TemplateResponse(
                                request,
                                'admin/licenses/import_json.html',
                                {'form': form, 'opts': self.model._meta}
                            )
                    
                    license_data['profile'] = profile
                    
                    # Category mapping
                    category_id = json_data.get('category')
                    if category_id:
                        category = None
                        # Check if category_id is a number
                        try:
                            # Try to convert to int to validate it's numeric
                            numeric_category_id = int(category_id)
                            category = get_category_by_id(numeric_category_id)
                        except (ValueError, TypeError):
                            # If category_id is not numeric, try to find by name
                            category = get_category_by_name(category_id)
                        
                        # If category not found by ID or name, use "Gastbeitrag"
                        if not category:
                            license_data['category'] = Category.objects.get_or_create(
                                name=_('Gastbeitrag')
                            )[0]
                        else:
                            license_data['category'] = category
                    else:
                        # If no category provided, use "Gastbeitrag"
                        license_data['category'] = Category.objects.get_or_create(
                            name=_('Gastbeitrag')
                        )[0]
                    
                    # Exchange permissions
                    license_data['media_authority_exchange_allowed'] = json_data.get(
                        'allowExchange', False
                    )
                    
                    # Media library
                    license_data['store_in_ok_media_library'] = json_data.get(
                        'saveToMediathek', False
                    )
                    
                    # Default values
                    license_data['repetitions_allowed'] = False
                    license_data['media_authority_exchange_allowed_other_states'] = False
                    license_data['youth_protection_necessary'] = False
                    license_data['youth_protection_category'] = 'none'
                    license_data['is_screen_board'] = False
                    license_data['infoblock'] = False
                    license_data['confirmed'] = False
                    license_data['duration'] = datetime.timedelta(seconds=0)
                    
                    # Check for potential duplicates
                    potential_duplicates = find_potential_duplicates(
                        license_data['title'],
                        license_data['profile'],
                        threshold=0.8
                    )
                    
                    if potential_duplicates.exists():
                        # Store license data in session for confirmation
                        # Convert model instances to IDs for JSON serialization
                        license_data_serializable = license_data.copy()
                        license_data_serializable['profile'] = profile.id
                        license_data_serializable['category'] = license_data['category'].id
                        # Convert timedelta to string format HH:MM:SS
                        duration_td = license_data['duration']
                        total_seconds = int(duration_td.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        license_data_serializable['duration'] = f"{hours}:{minutes:02d}:{seconds:02d}"
                        
                        request.session['pending_license_data'] = json.dumps(license_data_serializable)
                        request.session['pending_duplicates'] = list(potential_duplicates.values_list('id', flat=True))
                        
                        # Calculate similarity scores for each duplicate (as percentages)
                        similarity_scores = {}
                        for dup in potential_duplicates:
                            similarity_scores[dup.id] = similarity_ratio(license_data['title'], dup.title) * 100
                        
                        # Show confirmation page with duplicates
                        return TemplateResponse(
                            request,
                            'admin/licenses/import_duplicate_confirmation.html',
                            {
                                'form': form,
                                'opts': self.model._meta,
                                'new_title': license_data['title'],
                                'new_profile': profile,
                                'duplicates': potential_duplicates,
                                'similarity_scores': similarity_scores
                            }
                        )
                    
                    # No duplicates found - create immediately
                    license_obj = License.objects.create(**license_data)
                    
                    self.message_user(
                        request,
                        _('License "%(title)s" successfully imported.') % {
                            'title': license_obj.title
                        },
                        messages.SUCCESS
                    )
                    
                    # Redirect to the created license
                    from django.urls import reverse
                    return redirect(
                        reverse('admin:licenses_license_change', args=[license_obj.id])
                    )
                    
                except json.JSONDecodeError as e:
                    error_msg = str(e)
                    self.message_user(
                        request,
                        _('Invalid JSON file: {}').format(error_msg),
                        messages.ERROR
                    )
                except Exception as e:
                    logger.error(f'Error importing JSON: {str(e)}', exc_info=True)
                    error_msg = str(e)
                    self.message_user(
                        request,
                        _('Error importing license: {}').format(error_msg),
                        messages.ERROR
                    )
        else:
            form = ImportJSONForm()
        
        return TemplateResponse(
            request,
            'admin/licenses/import_json.html',
            {'form': form, 'opts': self.model._meta}
        )


admin.site.register(License, LicenseAdmin)


class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model."""
    
    list_display = ['name', 'numeric_id']
    search_fields = ['name', 'numeric_id']
    fields = ['name', 'numeric_id']


admin.site.register(Category, CategoryAdmin)


class NextcloudVideoFileAdmin(admin.ModelAdmin):
    """Admin interface for NextcloudVideoFile."""

    list_display = (
        'license_number',
        'profile_display',
        'filename',
        'file_size',
        'uploaded_at',
        'user_uploaded',
        'is_deleted',
        'deleted_at',
        'download_to_storage_button',
    )
    list_filter = (
        'is_deleted',
        'user_uploaded',
        'uploaded_at',
        'deleted_at',
    )
    search_fields = (
        'filename',
        'license__number',
        'license__title',
    )
    readonly_fields = (
        'uploaded_at',
        'deleted_at',
    )
    autocomplete_fields = ['license']

    actions = ['download_selected_videos_to_storage']
    
    fieldsets = (
        (_('File Information'), {
            'fields': ('license', 'filename', 'file_size', 'nextcloud_file_id', 'nextcloud_url')
        }),
        (_('Status'), {
            'fields': ('user_uploaded', 'is_deleted', 'uploaded_at', 'deleted_at')
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('license', 'license__profile')

    def get_urls(self):
        """Add custom URLs for Nextcloud video download."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:video_id>/download-to-storage/',
                self.admin_site.admin_view(self.download_to_storage_view),
                name='licenses_nextcloudvideofile_download',
            ),
        ]
        return custom_urls + urls
    
    def license_number(self, obj):
        """Display license number."""
        if obj.license and obj.license.number:
            return obj.license.number
        return '-'
    license_number.short_description = _('License Number')
    license_number.admin_order_field = 'license__number'
    
    def profile_display(self, obj):
        """Display profile name."""
        if obj.license and obj.license.profile:
            profile = obj.license.profile
            if profile.first_name and profile.last_name:
                return f"{profile.first_name} {profile.last_name}"
            elif profile.first_name:
                return profile.first_name
            elif profile.last_name:
                return profile.last_name
            else:
                return str(profile)
        return '-'
    profile_display.short_description = _('Profile')
    profile_display.admin_order_field = 'license__profile'

    def download_to_storage_button(self, obj):
        """Button to enqueue download of this file to local storage."""
        if obj.is_deleted:
            return '-'
        url = reverse('admin:licenses_nextcloudvideofile_download', args=[obj.pk])
        return format_html('<a class="button" href="{}">{}</a>', url, _('Download'))
    download_to_storage_button.short_description = _('Download')

    def download_to_storage_view(self, request, video_id: int):
        """Enqueue download of a single Nextcloud video to local storage."""
        from django.contrib import messages
        from .tasks import download_nextcloud_video_file_to_storage

        video = get_object_or_404(NextcloudVideoFile, pk=video_id)
        if video.is_deleted:
            self.message_user(
                request,
                _('Cannot download: file is marked deleted.'),
                messages.WARNING
            )
        else:
            download_nextcloud_video_file_to_storage.delay(video.pk)
            self.message_user(
                request,
                _('Download queued for "%(filename)s".') % {'filename': video.filename},
                messages.SUCCESS
            )

        return HttpResponseRedirect(
            request.META.get(
                'HTTP_REFERER',
                reverse('admin:licenses_nextcloudvideofile_changelist')
            )
        )

    def download_selected_videos_to_storage(self, request, queryset):
        """Enqueue download of selected Nextcloud videos to local storage."""
        from django.contrib import messages
        from .tasks import download_nextcloud_video_file_to_storage

        queued = 0
        skipped = 0
        for video in queryset:
            if video.is_deleted:
                skipped += 1
                continue
            download_nextcloud_video_file_to_storage.delay(video.pk)
            queued += 1

        if queued:
            self.message_user(
                request,
                _p('Queued download for %(count)d file.', 'Queued download for %(count)d files.', queued) % {'count': queued},
                messages.SUCCESS
            )
        if skipped:
            self.message_user(
                request,
                _p('Skipped %(count)d deleted file.', 'Skipped %(count)d deleted files.', skipped) % {'count': skipped},
                messages.WARNING
            )
    download_selected_videos_to_storage.short_description = _('Download selected to storage')


# Only register if Nextcloud is enabled
from django.conf import settings
if settings.NEXTCLOUD_ENABLED:
    admin.site.register(NextcloudVideoFile, NextcloudVideoFileAdmin)


class LicensesConfigForm(forms.ModelForm):
    """Form for LicensesConfig with multi-select for Media Authorities."""

    notification_media_authority_names = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_('Send notifications to (Media Authorities)'),
        help_text=_(
            'Send status emails only to users whose profile belongs to one of these '
            'Media Authorities (Offene Kanäle/Bürgermedien). Empty = send to all.'
        ),
    )

    class Meta:
        model = LicensesConfig
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(ma.name, ma.name) for ma in MediaAuthority.objects.order_by('name')]
        self.fields['notification_media_authority_names'].choices = choices
        self.fields['notification_media_authority_names'].initial = (
            self.instance.notification_media_authority_names or []
            if self.instance.pk else []
        )

    def clean_notification_media_authority_names(self):
        value = self.cleaned_data.get('notification_media_authority_names') or []
        return [str(v).strip() for v in value if v]


@admin.register(LicensesConfig)
class LicensesConfigAdmin(admin.ModelAdmin):
    """Admin interface for LicensesConfig model."""

    form = LicensesConfigForm

    def has_add_permission(self, request):
        """Only one config instance allowed."""
        return not LicensesConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of config."""
        return False

    fieldsets = (
        (_('Email Notifications'), {
            'fields': ('send_status_emails', 'notification_media_authority_names'),
        }),
        (_('Storage Settings'), {
            'fields': ('download_storage_path', 'create_videofile_on_nextcloud_download'),
        }),
        (_('Screen Board Settings'), {
            'fields': ('screen_board_duration',),
        }),
    )
