from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RegistrationConfig(AppConfig):
    """Configuration class for the application 'registration'."""

    name = 'registration'
    verbose_name = _('Registration')

    def ready(self):
        """Import Signals to set send email after verification."""
        from . import signals  # noqa F401
        
        # Auto-create organizations from configuration on startup
        # Only run during actual Django startup, not during migrations
        import sys
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            self._setup_organizations()
    
    def _setup_organizations(self):
        """Create MediaAuthority and Organization from settings."""
        try:
            from django.conf import settings
            from django.db import connection
            from django.db.utils import OperationalError
            
            # Check if database is ready
            try:
                connection.ensure_connection()
            except OperationalError:
                # Database not ready yet, skip
                return
            
            # Import models here to avoid AppRegistryNotReady error
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
            # Silently ignore errors during startup
            # (e.g., when tables don't exist yet)
            pass