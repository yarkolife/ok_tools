from django.conf import settings


def context(request):
    """Make organization settings available in templates."""
    return {
        'OK_NAME': settings.OK_NAME,
        'OK_NAME_SHORT': settings.OK_NAME_SHORT,
        'OK_WEBSITE': getattr(settings, 'OK_WEBSITE', ''),
        'OK_EMAIL': getattr(settings, 'OK_EMAIL', ''),
        'OK_ADDRESS': getattr(settings, 'OK_ADDRESS', ''),
        'OK_PHONE': getattr(settings, 'OK_PHONE', ''),
        'OK_FAX': getattr(settings, 'OK_FAX', ''),
        'OK_DESCRIPTION': getattr(settings, 'OK_DESCRIPTION', ''),
        'OK_OPENING_HOURS': getattr(settings, 'OK_OPENING_HOURS', ''),
        'STATE_MEDIA_INSTITUTION': getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA'),
        'ORGANIZATION_OWNER': getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ'),
        'EQUIPMENT_OWNERS': getattr(settings, 'EQUIPMENT_OWNERS', []),  # For backward compatibility
    }
