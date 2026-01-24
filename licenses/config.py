"""Configuration helpers for licenses module with env fallbacks."""

import os
from django.conf import settings


def get_screen_board_duration():
    """Get screen board duration in seconds."""
    try:
        from .models import LicensesConfig
        config = LicensesConfig.get_config()
        return config.screen_board_duration
    except Exception:
        # Fallback to env variable for backward compatibility
        try:
            return int(os.getenv('SCREEN_BOARD_DURATION', '20'))
        except ValueError:
            return 20


def get_send_status_emails() -> bool:
    """Return whether status emails should be sent."""
    try:
        from .models import LicensesConfig
        config = LicensesConfig.get_config()
        return bool(getattr(config, "send_status_emails", True))
    except Exception:
        # Default to enabled if config is not available.
        return True


def get_notification_media_authority_names() -> list:
    """
    Return list of MediaAuthority names to send license notifications to.
    Empty = send to all (backward compatible).
    """
    try:
        from .models import LicensesConfig
        config = LicensesConfig.get_config()
        names = getattr(config, "notification_media_authority_names", None)
        if names is None or not isinstance(names, list):
            return []
        return [str(n).strip() for n in names if n]
    except Exception:
        return []


def should_send_notification_for_license(license_obj) -> bool:
    """
    Return True if status emails should be sent for this license's recipient.

    Checks notification_media_authority_names: if empty, allow all; otherwise
    only if license.profile.media_authority.name is in the list.
    """
    names = get_notification_media_authority_names()
    if not names:
        return True
    try:
        profile = getattr(license_obj, "profile", None)
        if not profile:
            return False
        ma = getattr(profile, "media_authority", None)
        if not ma:
            return False
        return (getattr(ma, "name", None) or "").strip() in names
    except Exception:
        return False
