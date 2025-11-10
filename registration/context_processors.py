from django.conf import settings


def context(request):
    """Make organization settings available in templates."""
    return {
        'OK_NAME': settings.OK_NAME,
        'OK_NAME_SHORT': settings.OK_NAME_SHORT,
        'OK_WEBSITE': settings.OK_WEBSITE,
        'OK_EMAIL': settings.OK_EMAIL,
        'OK_ADDRESS': settings.OK_ADDRESS,
        'OK_PHONE': settings.OK_PHONE,
        'OK_FAX': settings.OK_FAX,
        'OK_DESCRIPTION': settings.OK_DESCRIPTION,
        'OK_OPENING_HOURS': settings.OK_OPENING_HOURS,
        'STATE_MEDIA_INSTITUTION': settings.STATE_MEDIA_INSTITUTION,
        'ORGANIZATION_OWNER': settings.ORGANIZATION_OWNER,
        'EQUIPMENT_OWNERS': getattr(settings, 'EQUIPMENT_OWNERS', []),  # For backward compatibility
    }
