from django.conf import settings
from . import organization_config


def context(request):
    """Make organization settings available in templates."""
    return {
        'OK_NAME': organization_config.get_organization_name(),
        'OK_NAME_SHORT': organization_config.get_organization_short_name(),
        'OK_WEBSITE': organization_config.get_organization_website(),
        'OK_EMAIL': organization_config.get_organization_email(),
        'OK_ADDRESS': organization_config.get_organization_address(),
        'OK_PHONE': organization_config.get_organization_phone(),
        'OK_FAX': organization_config.get_organization_fax(),
        'OK_DESCRIPTION': organization_config.get_organization_description(),
        'OK_OPENING_HOURS': organization_config.get_organization_opening_hours(),
        'STATE_MEDIA_INSTITUTION': organization_config.get_state_media_institution(),
        'ORGANIZATION_OWNER': organization_config.get_organization_owner(),
        'EQUIPMENT_OWNERS': getattr(settings, 'EQUIPMENT_OWNERS', []),  # For backward compatibility
    }
