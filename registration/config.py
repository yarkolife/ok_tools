"""Configuration helpers for registration module with env fallbacks."""

import os
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_registration_form_pdf():
    """Get registration form PDF template name."""
    try:
        from .models import RegistrationConfig
        config = RegistrationConfig.get_config()
        return config.form_pdf
    except Exception:
        # Fallback to env variable for backward compatibility
        return os.getenv('REGISTRATION_FORM_PDF', 'Nutzerkartei_Anmeldung_2022_n.pdf')


def get_registration_form_type():
    """Get registration form type (PDF, HTML, or TEXT)."""
    try:
        from .models import RegistrationConfig
        config = RegistrationConfig.get_config()
        return config.form_type
    except Exception:
        # Fallback to env variable for backward compatibility
        return os.getenv('REGISTRATION_FORM_TYPE', 'PDF')
