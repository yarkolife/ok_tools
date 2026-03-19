"""Configuration helpers for rental module with env fallbacks."""

import os
from django.conf import settings
from typing import List

from .working_hours import get_working_hours_by_weekday
from .working_hours import get_working_hours_summary


def get_rental_user_request_requires_approval():
    """Get whether user rental requests require approval."""
    try:
        from .models import RentalConfig
        config = RentalConfig.get_config()
        return config.user_request_requires_approval
    except Exception:
        # Fallback to env variable for backward compatibility
        value = os.getenv('RENTAL_USER_REQUEST_REQUIRES_APPROVAL', 'false')
        return str(value).lower() in ('true', '1', 'yes', 'on')


def get_rental_site_base_url():
    """Get site base URL for rental approval links."""
    try:
        from .models import RentalConfig
        config = RentalConfig.get_config()
        if config.site_base_url:
            return config.site_base_url
    except Exception:
        pass
    
    # Fallback to env variable or settings
    return os.getenv('SITE_BASE_URL', '') or getattr(settings, 'SITE_BASE_URL', '')


def get_rental_request_url_template():
    """Get rental request URL template."""
    try:
        from .models import RentalConfig
        config = RentalConfig.get_config()
        if config.request_url_template:
            return config.request_url_template
    except Exception:
        pass
    
    # Fallback to env variable
    return os.getenv('RENTAL_REQUEST_URL_TEMPLATE', '')


def get_rental_approval_recipient_emails() -> List[str]:
    """Get list of approval recipient email addresses."""
    try:
        from .models import RentalConfig
        config = RentalConfig.get_config()
        emails = config.get_approval_recipient_emails_list()
        if emails:
            return emails
    except Exception:
        pass
    
    # Fallback to env variable
    env_value = os.getenv('RENTAL_APPROVAL_RECIPIENT_EMAILS', '')
    if env_value:
        return [email.strip() for email in env_value.split(',') if email.strip()]
    return []


def get_rental_approval_token_max_age_seconds():
    """Get approval token max age in seconds."""
    try:
        from .models import RentalConfig
        config = RentalConfig.get_config()
        return config.approval_token_max_age_seconds
    except Exception:
        # Fallback to env variable
        try:
            return int(os.getenv('RENTAL_APPROVAL_TOKEN_MAX_AGE_SECONDS', '604800'))
        except ValueError:
            return 604800  # 7 days default


def get_rental_working_hours():
    try:
        return get_working_hours_by_weekday()
    except Exception:
        return {}


def get_rental_working_hours_summary_text():
    try:
        return get_working_hours_summary()
    except Exception:
        return ''
