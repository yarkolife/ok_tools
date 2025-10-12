from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.utils.html import format_html
from django.urls import reverse
from django import forms
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.admin import TokenAdmin as BaseTokenAdmin
from registration.models import Profile

User = get_user_model()


# Using Django's built-in AutocompleteSelect widget instead of custom widget


class StaffFilter(SimpleListFilter):
    """Filter users by staff status."""
    
    title = 'Staff Status'
    parameter_name = 'is_staff'
    
    def lookups(self, request, model_admin):
        return (
            ('staff', 'Staff members'),
            ('non_staff', 'Non-staff'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'staff':
            return queryset.filter(is_staff=True)
        elif self.value() == 'non_staff':
            return queryset.filter(is_staff=False)


class MemberFilter(SimpleListFilter):
    """Filter users by member status."""
    
    title = 'Member Status'
    parameter_name = 'is_member'
    
    def lookups(self, request, model_admin):
        return (
            ('member', 'Members'),
            ('non_member', 'Non-members'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'member':
            return queryset.filter(profile__member=True)
        elif self.value() == 'non_member':
            return queryset.filter(Q(profile__member=False) | Q(profile__isnull=True))


# User admin is handled by registration app, we only customize Token admin


class TokenAdmin(BaseTokenAdmin):
    """Custom Token admin with staff-only users and API link."""
    
    list_display = ('key', 'user_email', 'user_name', 'created', 'api_link')
    list_filter = ('created',)
    search_fields = ('user__email', 'user__profile__first_name', 'user__profile__last_name')
    ordering = ('-created',)
    
    def get_queryset(self, request):
        """Show only staff users in the token creation form."""
        qs = super().get_queryset(request)
        return qs.select_related('user__profile')
    
    def user_email(self, obj):
        """Display user email."""
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def user_name(self, obj):
        """Display user full name."""
        try:
            # Get profile using the reverse relationship
            profile = Profile.objects.get(okuser=obj.user)
            return f"{profile.first_name} {profile.last_name}"
        except Profile.DoesNotExist:
            return "-"
    user_name.short_description = 'Name'
    
    def api_link(self, obj):
        """Display API documentation link."""
        if obj.key:
            api_url = reverse('licenses:api-metadata', args=[1])  # Example with license 1
            api_url = api_url.replace('/1/', '/{license_number}/')
            
            return format_html(
                '<a href="#" onclick="showApiExample(\'{}\', \'{}\')" '
                'style="color: #007cba; text-decoration: none;">'
                '📖 API Example</a>',
                obj.key,
                api_url
            )
        return "-"
    api_link.short_description = 'API'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter users to show only staff members with autocomplete."""
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
            # Use Django's built-in autocomplete widget
            kwargs["widget"] = admin.widgets.AutocompleteSelect(
                db_field, self.admin_site, 
                attrs={'data-placeholder': 'Search by email or name...'}
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    class Media:
        css = {
            'all': ('ok_tools/css/token_admin.css',)
        }
        js = ('ok_tools/js/token_admin.js',)


def register_custom_admin():
    """Register custom admin configurations."""
    # Unregister both Token and TokenProxy to avoid duplicates
    try:
        admin.site.unregister(Token)
    except admin.sites.NotRegistered:
        pass  # Token was not registered, that's fine
    
    try:
        from rest_framework.authtoken.models import TokenProxy
        admin.site.unregister(TokenProxy)
    except admin.sites.NotRegistered:
        pass  # TokenProxy was not registered, that's fine
    
    # Register our custom Token admin (this will handle both Token and TokenProxy)
    admin.site.register(Token, TokenAdmin)
    
    # Update User admin to add search by names for autocomplete
    try:
        from registration.admin import UserAdmin as RegistrationUserAdmin
        # Extend search fields to include profile names
        RegistrationUserAdmin.search_fields = ['email', 'profile__first_name', 'profile__last_name']
        
        # Override get_queryset to show only staff users in autocomplete
        original_get_queryset = RegistrationUserAdmin.get_queryset
        def staff_only_queryset(self, request):
            qs = original_get_queryset(self, request)
            # If this is an autocomplete request, filter to staff only
            if request.GET.get('app_label') == 'authtoken' and request.GET.get('model_name') == 'token':
                return qs.filter(is_staff=True)
            return qs
        RegistrationUserAdmin.get_queryset = staff_only_queryset
    except:
        pass  # If registration admin is not available, continue

# Registration will be handled by apps.py ready() method
