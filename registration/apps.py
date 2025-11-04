from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_migrate


def setup_organizations_handler(sender, **kwargs):
    """Create MediaAuthority and Organization from settings after migrations."""
    try:
        from django.conf import settings
        from registration.models import MediaAuthority
        from inventory.models import Organization
        
        # Get values from settings
        state_media_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
        organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
        ok_name = getattr(settings, 'OK_NAME', 'Offener Kanal Merseburg-Querfurt e.V.')
        
        # Create MediaAuthority for the organization (used for user profiles)
        MediaAuthority.objects.get_or_create(name=organization_owner)
        
        # Create Organizations for equipment ownership
        Organization.objects.get_or_create(
            name=state_media_institution,
            defaults={'description': f'State Media Institution: {state_media_institution}'}
        )
        Organization.objects.get_or_create(
            name=organization_owner,
            defaults={'description': ok_name}
        )
    except Exception:
        # Silently ignore errors (e.g., when settings are not configured)
        pass


class RegistrationConfig(AppConfig):
    """Configuration class for the application 'registration'."""

    name = 'registration'
    verbose_name = _('Registration')

    def ready(self):
        """Import Signals to set send email after verification."""
        from . import signals  # noqa F401
        
        # Connect to post_migrate signal to auto-create organizations after migrations
        # This avoids RuntimeWarning about database access during app initialization
        post_migrate.connect(setup_organizations_handler, sender=self)