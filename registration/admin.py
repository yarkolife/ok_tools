from .models import Gender
from .models import MediaAuthority
from .models import Notification
from .models import Profile
from .print import generate_registration_form
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext as _p
from django_admin_listfilter_dropdown.filters import DropdownFilter
from import_export import resources
from import_export.admin import ExportMixin
from import_export.fields import Field
from ok_tools.datetime import TZ
from registration.signals import signal
import datetime
import logging


logger = logging.getLogger('django')

# register user
User = get_user_model()

admin.site.unregister(Group)


class UserAdmin(BaseUserAdmin):
    """How should the user be shown on the admin site."""

    fieldsets = (
        (_('E-Mail address'), {
            'fields': ('email',)
        }),
        (_('Password'), {
            'fields': ('password',)
        }),
        (_('Admin'), {
            'fields': ('is_superuser',)
        }),
        (_('permissions'), {
            'fields': ('user_permissions',)
        }),
        (_('Staff'), {
            'fields': ('is_staff',)
        }),
    )
    add_fieldsets = (
        (_('E-Mail address'), {
            'fields': ('email',)
        }),
        (_('Password'), {
            'fields': ('password1', 'password2')
        }),
        (_('Staff'), {
            'fields': ('is_staff',)
        }),
    )
    list_display = ['email', 'last_login', 'is_superuser', 'is_staff']
    ordering = ['email']
    search_fields = ['email']


admin.site.register(User, UserAdmin)


class ProfileResource(resources.ModelResource):
    """Define the export for Profile."""

    def _f(field=None, name=None):
        """Shortcut for field creation."""
        return Field(attribute=field, column_name=name)

    id = _f('id', _('ID'))
    first_name = _f('first_name', _('first name'))
    last_name = _f('last_name', _('last name'))
    gender = _f('gender', _('gender'))
    email = _f('okuser__email', _('email address'))
    phone_number = _f('phone_number', _('phone number'))
    mobile_number = _f('mobile_number', _('mobile number'))
    ausweisnummer = _f('ausweisnummer', _('ID document number'))
    birthday = _f('birthday', _('birthday'))
    street = _f('street', _('street'))
    house_number = _f('house number', _('house number'))
    zipcode = _f('zipcode', _('zipcode'))
    city = _f('city', _('city'))
    created_at = _f('created_at', _('created at'))
    member = _f('member', _('member'))
    media_authority = _f('media_authority__name', _('Media Authority'))
    comment = _f('comment', _('comment'))

    class Meta:
        """Define meta properties for the Project export."""

        model = Profile
        fields = []

    def dehydrate_created_at(self, profile: Profile):
        """Export the created_at datetime object in the current time zone."""
        created_at = profile.created_at.astimezone(TZ)
        return f'{created_at.date()} {created_at.time()}'

    def dehydrate_gender(self, profile: Profile):
        """Export gender as verbose name."""
        return Gender.verbose_name(profile.gender)


class BirthmonthFilter(admin.SimpleListFilter):
    """Filter profiles using a given birth month."""

    template = 'django_admin_listfilter_dropdown/dropdown_filter.html'
    title = _('birthmonth')
    parameter_name = 'birthday'

    def lookups(self, request, model_admin):
        """Labels for the possible months."""
        return (
            (1, _('January')),
            (2, _('February')),
            (3, _('March')),
            (4, _('April')),
            (5, _('May')),
            (6, _('June')),
            (7, _('July')),
            (8, _('August')),
            (9, _('September')),
            (10, _('October')),
            (11, _('November')),
            (12, _('December')),
        )

    def queryset(self, request, queryset):
        """Filter the profiles using the given month."""
        if self.value() is None:
            return

        try:
            value = int(self.value())
        except ValueError:
            raise ValueError(f'Unsupported filter option {self.value()}')

        if value < 1 or value > 12:
            raise ValueError(f'Unsupported filter option {self.value()}')

        return queryset.filter(birthday__month=int(value))


class YearFilter(admin.SimpleListFilter):
    """Filter after this or last year."""

    title = _('created year')

    parameter_name = 'created_year'

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


# register profile
class ProfileAdmin(ExportMixin, admin.ModelAdmin):
    """How should the profile be shown on the admin site."""

    resource_classes = [ProfileResource]

    change_form_template = 'admin/registration_change_form_edit.html'

    list_display = [
        'okuser',
        'first_name',
        'last_name',
        'birthday',
        'verified',
        'member',
        'created_at',
    ]
    autocomplete_fields = ['okuser', 'media_authority']
    ordering = ['-created_at']

    search_fields = ['okuser__email', 'first_name', 'last_name']
    search_help_text = _('e-mail, first name, last name')

    list_filter = [
        BirthmonthFilter,
        ('media_authority__name', DropdownFilter),
        'member',
        YearFilter,
    ]
    actions = ['verify', 'unverify']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('okuser', 'first_name', 'last_name', 'gender', 'birthday')
        }),
        (_('Contact Information'), {
            'fields': ('phone_number', 'mobile_number', 'street', 'house_number', 'zipcode', 'city')
        }),
        (_('ID Document'), {
            'fields': ('ausweisnummer',),
            'classes': ('collapse',)
        }),
        (_('Organization'), {
            'fields': ('media_authority', 'member', 'verified')
        }),
        (_('Data Sharing Permissions'), {
            'fields': ('phone_data_sharing_allowed', 'email_data_sharing_allowed'),
            'classes': ('collapse',),
            'description': _('Admin-only: Permissions for sharing data with third parties')
        }),
        (_('Additional Information'), {
            'fields': ('comment', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']

    # PERFORMANCE OPTIMIZATION: Reduce N+1 queries in list view
    def get_queryset(self, request):
        """Optimize queryset with select_related for foreign keys."""
        return super().get_queryset(request).select_related(
            'okuser', 
            'media_authority'
        )

    # inspired from https://stackoverflow.com/a/54579134
    def save_model(self, request, obj, form, change):
        """
        Set update_fields.

        Observed field is 'verified'.
        Set update_fields to use the post_save signal to set permissions.
        Necessary for registration/signals.py/verify_profile.
        """
        if form and form.changed_data:
            initial = form.initial.get('verified')
            new = form.cleaned_data.get('verified')
            if (not (initial is None or new is None)
                    and initial != new
                    and new is True):
                signal.send(sender=self, obj=obj, request=request)

        return super().save_model(request, obj, form, change)

    @admin.action(description=_('Verify selected profiles'))
    def verify(self, request, queryset):
        """Verify all selected profiles."""
        updated = self._set_verified(queryset, True, request)
        self.message_user(request, _p(
            '%d profile was successfully verified.',
            '%d profiles were successfully verified.',
            updated,
        ) % updated, messages.SUCCESS)

    @admin.action(description=_('Unverify selected profiles'))
    def unverify(self, request, queryset):
        """Unverify all selected profiles."""
        updated = self._set_verified(queryset, False, request)
        self.message_user(request, _p(
            '%d profile was successfully unverified.',
            '%d profiles were successfully unverified.',
            updated,
        ) % updated, messages.SUCCESS)

    def _set_verified(self, queryset, value: bool, request) -> int:
        """Set the `verified` attribute.

        Return the amount of updated objects.
        """
        updated = 0
        for obj in queryset:
            if obj.verified == value:
                continue
            obj.verified = value
            obj.save()
            if obj.verified:
                signal.send(sender=self, obj=obj, request=request)
            updated += 1
        return updated

    def response_change(self, request, obj):
        """Add 'Print application' button to profile view."""
        if '_print_application' in request.POST:
            return generate_registration_form(obj.okuser, obj)
        return super().response_change(request, obj)


admin.site.register(Profile, ProfileAdmin)


class MediaAuthorityAdmin(admin.ModelAdmin):
    """Define search_fields."""

    search_fields = ['name']


admin.site.register(MediaAuthority, MediaAuthorityAdmin)


class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = [
        'title',
        'notification_type',
        'icon',
        'is_active',
        'priority',
        'start_date',
        'end_date',
        'created_by',
        'created_at'
    ]

    list_filter = [
        'notification_type',
        'is_active',
        'priority',
        'start_date',
        'created_at'
    ]

    search_fields = ['title', 'message']

    list_editable = ['is_active', 'priority']

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'message', 'notification_type', 'icon')
        }),
        (_('Display Settings'), {
            'fields': ('is_active', 'priority', 'start_date', 'end_date')
        }),
        (_('Metadata'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'created_by']

    def get_readonly_fields(self, request, obj=None):
        """Make created_by readonly when editing existing notification."""
        if obj:  # Editing existing notification
            return self.readonly_fields
        else:  # Creating new notification
            return ['created_at']  # created_by will be auto-filled

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if not set."""
        if not change:  # Creating new notification
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Show all notifications for superusers, only active for staff."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(is_active=True)


admin.site.register(Notification, NotificationAdmin)
