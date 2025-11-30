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
