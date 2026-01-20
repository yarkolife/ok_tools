from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_migrate


def setup_organizations_handler(sender, **kwargs):
    """Create MediaAuthority and Organization from OrganizationConfig after migrations."""
    try:
        from registration.models import MediaAuthority, OrganizationConfig
        from registration import organization_config
        from inventory.models import Organization
        
        # Get values from OrganizationConfig (with fallback to settings/env)
        state_media_institution = organization_config.get_state_media_institution()
        organization_owner = organization_config.get_organization_owner()
        ok_name = organization_config.get_organization_name()
        
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
        # Silently ignore errors (e.g., when DB is not ready or settings are not configured)
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