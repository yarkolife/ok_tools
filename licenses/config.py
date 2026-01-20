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
