"""Configuration helpers for organization settings with env fallbacks."""

import os
from django.conf import settings
from django.utils.translation import gettext_lazy as _


def get_organization_name():
    """Get organization name."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.name
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_NAME') or getattr(settings, 'OK_NAME', _('Open Channel Merseburg-Querfurt e.V.'))


def get_organization_short_name():
    """Get organization short name."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.short_name
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_SHORT_NAME') or getattr(settings, 'OK_NAME_SHORT', _('OK Merseburg'))


def get_organization_website():
    """Get organization website."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.website
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_WEBSITE') or getattr(settings, 'OK_WEBSITE', '')


def get_organization_email():
    """Get organization email."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.email
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_EMAIL') or getattr(settings, 'OK_EMAIL', '')


def get_organization_phone():
    """Get organization phone."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.phone
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_PHONE') or getattr(settings, 'OK_PHONE', '')


def get_organization_fax():
    """Get organization fax."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.fax
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_FAX') or getattr(settings, 'OK_FAX', '')


def get_organization_address():
    """Get organization address."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.address
    except Exception:
        # Fallback to env variable or settings
        address = os.getenv('ORG_ADDRESS') or getattr(settings, 'OK_ADDRESS', '')
        # Replace \\n with actual newlines
        return address.replace('\\n', '\n') if address else ''


def get_organization_description():
    """Get organization description."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.description
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_DESCRIPTION') or getattr(settings, 'OK_DESCRIPTION', '')


def get_organization_opening_hours():
    """Get organization opening hours."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.opening_hours
    except Exception:
        # Fallback to env variable or settings
        hours = os.getenv('ORG_OPENING_HOURS') or getattr(settings, 'OK_OPENING_HOURS', '')
        # Replace \\n with actual newlines
        return hours.replace('\\n', '\n') if hours else ''


def get_state_media_institution():
    """Get state media institution code."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.state_media_institution
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('STATE_MEDIA_INSTITUTION') or getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')


def get_organization_owner():
    """Get organization owner identifier."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.organization_owner
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_ORGANIZATION_OWNER') or getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')


def get_broadcast_start():
    """Get broadcast start time."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.broadcast_start.strftime('%H:%M') if config.broadcast_start else '06:00'
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_BROADCAST_START') or getattr(settings, 'BROADCAST_START', '06:00')


def get_broadcast_end():
    """Get broadcast end time."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.broadcast_end.strftime('%H:%M') if config.broadcast_end else '23:00'
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_BROADCAST_END') or getattr(settings, 'BROADCAST_END', '23:00')


def get_peertube_channel():
    """Get PeerTube channel identifier."""
    try:
        from .models import OrganizationConfig
        config = OrganizationConfig.get_config()
        return config.peertube_channel
    except Exception:
        # Fallback to env variable or settings
        return os.getenv('ORG_PEERTUBE_CHANNEL') or getattr(settings, 'PEERTUBE_CHANNEL', '')
