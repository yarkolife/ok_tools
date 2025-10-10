"""
Django management command to create MediaAuthority and Organization
based on settings from configuration file.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from registration.models import MediaAuthority
from inventory.models import Organization


class Command(BaseCommand):
    """Command to setup organizations from configuration."""

    help = 'Create MediaAuthority and Organization objects from configuration'

    def handle(self, *args, **options):
        """Execute the command."""
        # Get values from settings
        state_media_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
        organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
        ok_name = getattr(settings, 'OK_NAME', 'Offener Kanal Merseburg-Querfurt e.V.')
        
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

