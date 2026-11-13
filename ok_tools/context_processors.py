from registration.models import Profile
from django.conf import settings


def user_display_name(request):
    """Add user_display_name to global context."""
    if request.user.is_authenticated:
        try:
            profile = Profile.objects.get(okuser=request.user)
            if profile.first_name and profile.last_name:
                return {'user_display_name': f"{profile.first_name} {profile.last_name}"}
            elif profile.first_name:
                return {'user_display_name': profile.first_name}
            elif profile.last_name:
                return {'user_display_name': profile.last_name}
            else:
                return {'user_display_name': request.user.email or request.user.username}
        except Profile.DoesNotExist:
            return {'user_display_name': request.user.email or request.user.username}
    return {'user_display_name': None}


def bootstrap_context(request):
    """Add Bootstrap configuration to global context."""
    return {
        'BOOTSTRAP_VERSION': settings.BOOTSTRAP_VERSION,
        'BOOTSTRAP_CDN_URL': settings.BOOTSTRAP_CDN_URL,
        'BOOTSTRAP_ICONS_VERSION': settings.BOOTSTRAP_ICONS_VERSION,
        'BOOTSTRAP_ICONS_URL': settings.BOOTSTRAP_ICONS_URL,
    }


def nextcloud_context(request):
    """Add Nextcloud configuration to global context."""
    return {
        'NEXTCLOUD_ENABLED': settings.NEXTCLOUD_ENABLED,
    }


def dashboard_theme_context(request):
    """Add dashboard theme configuration to global context."""
    return {
        'DASHBOARD_THEME': settings.DASHBOARD_THEME,
        'DASHBOARD_THEME_FILE': f'css/themes/theme-{settings.DASHBOARD_THEME}.css',
    }


def module_flags(request):
    """Expose module flags to templates."""
    licenses_enabled = getattr(settings, 'LICENSES_ENABLED', True)
    return {
        'LICENSES_ENABLED': licenses_enabled,
        'CONTRIBUTIONS_ENABLED': licenses_enabled,  # Contributions depends on licenses
        'INVENTORY_ENABLED': getattr(settings, 'INVENTORY_ENABLED', False),
        'RENTAL_ENABLED': getattr(settings, 'RENTAL_ENABLED', False),
        'PROJECTS_ENABLED': getattr(settings, 'PROJECTS_ENABLED', False),
        'PLANUNG_ENABLED': getattr(settings, 'PLANUNG_ENABLED', False),
        'MEDIA_FILES_ENABLED': getattr(settings, 'MEDIA_FILES_ENABLED', False),
        'DASHBOARD_ENABLED': getattr(settings, 'DASHBOARD_ENABLED', False),
        'AUSTAUSCH_ENABLED': getattr(settings, 'AUSTAUSCH_ENABLED', False),
        'TOOLS_ENABLED': getattr(settings, 'TOOLS_ENABLED', False),
        'NOTIFICATIONS_ENABLED': getattr(settings, 'NOTIFICATIONS_ENABLED', False),
        'ADMIN_UNFOLD_ENABLED': getattr(settings, 'ADMIN_UNFOLD_ENABLED', False),
    }


def brand_context(request):
    """CSS variables of the brand colour (BRAND_COLOR) for every page.

    Unfold injects its palette only into admin pages; ok_tools/_theme_head.html
    and the classic admin print this block so the pages outside Unfold use
    the same colours.
    """
    from django.utils.safestring import mark_safe
    from ok_tools.brand import css_variables
    return {'OK_BRAND_CSS': mark_safe(_brand_css(settings.BRAND_COLOR, css_variables))}


_BRAND_CSS_CACHE: dict = {}


def _brand_css(color, build):
    if color not in _BRAND_CSS_CACHE:
        _BRAND_CSS_CACHE[color] = build(color)
    return _BRAND_CSS_CACHE[color]


def app_version(request):
    """Installed OK-Tools version and commit, shown in the admin sidebar."""
    from ok_tools import version

    return {'OK_VERSION': version.VERSION, 'OK_COMMIT': version.commit()}
