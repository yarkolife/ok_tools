"""
Django management command to create MediaAuthority and Organization
based on settings from configuration file.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from registration.models import MediaAuthority

# Import Organization only if inventory module is enabled
try:
    from inventory.models import Organization
    INVENTORY_AVAILABLE = True
except (ImportError, RuntimeError, ModuleNotFoundError):
    INVENTORY_AVAILABLE = False
    Organization = None


class Command(BaseCommand):
    """Command to setup organizations from configuration."""

    help = 'Create MediaAuthority and Organization objects from configuration'

    def handle(self, *args, **options):
        """Execute the command."""
        # Get values from OrganizationConfig (with fallback to settings/env)
        from registration import organization_config
        state_media_institution = organization_config.get_state_media_institution()
        organization_owner = organization_config.get_organization_owner()
        ok_name = organization_config.get_organization_name()
        
        # Create or update MediaAuthority (Organization Owner - used for user profiles)
        media_authority, created = MediaAuthority.objects.get_or_create(
            name=organization_owner
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Created MediaAuthority: {organization_owner}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'MediaAuthority already exists: {organization_owner}'
                )
            )
        
        # Create Organization entries only if inventory module is enabled
        if INVENTORY_AVAILABLE and Organization is not None:
            # Create or update Organization (State Media Institution)
            org_state, created = Organization.objects.get_or_create(
                name=state_media_institution,
                defaults={'description': f'State Media Institution: {state_media_institution}'}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created Organization: {state_media_institution}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Organization already exists: {state_media_institution}'
                    )
                )
            
            # Create or update Organization (Organization Owner)
            org_owner, created = Organization.objects.get_or_create(
                name=organization_owner,
                defaults={'description': ok_name}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created Organization: {organization_owner} ({ok_name})'
                    )
                )
            else:
                # Update description if organization exists
                if org_owner.description != ok_name:
                    org_owner.description = ok_name
                    org_owner.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Updated Organization: {organization_owner} ({ok_name})'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Organization already exists: {organization_owner}'
                        )
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n   Organizations (for equipment ownership):'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'   - {state_media_institution} (State Media Institution - accessible to all)'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'   - {organization_owner} ({ok_name} - accessible only to members)'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '\n   Inventory module not enabled - skipping Organization setup'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\n✅ Organization setup completed successfully!'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'\n   MediaAuthority (for user profiles):'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'   - {organization_owner}'
            )
        )

