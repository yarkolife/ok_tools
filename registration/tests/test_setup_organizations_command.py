from django.core.management import call_command
from django.test import TestCase
from io import StringIO
from unittest.mock import patch
from registration.models import MediaAuthority
from inventory.models import Organization
from django.conf import settings


class SetupOrganizationsCommandTest(TestCase):
    """Unit tests for setup_organizations management command."""

    def setUp(self):
        """Clean up any existing data before each test."""
        MediaAuthority.objects.all().delete()
        Organization.objects.all().delete()

    @patch('django.conf.settings.STATE_MEDIA_INSTITUTION', 'MSA_TEST')
    @patch('django.conf.settings.ORGANIZATION_OWNER', 'OKMQ_TEST')
    @patch('django.conf.settings.OK_NAME', 'Test Organization')
    def test_command_creates_organizations_with_custom_settings(self):
        """Test that command creates organizations using custom settings."""
        # The command reads names from OrganizationConfig, not settings.
        from registration.models import OrganizationConfig
        config = OrganizationConfig.get_config()
        config.state_media_institution = 'MSA_TEST'
        config.organization_owner = 'OKMQ_TEST'
        config.name = 'Test Organization'
        config.save()
        # Run the command
        out = StringIO()
        call_command('setup_organizations', stdout=out)

        # Verify MediaAuthority was created
        media_authority = MediaAuthority.objects.get(name='OKMQ_TEST')
        self.assertIsNotNone(media_authority)

        # Verify Organizations were created
        org_state = Organization.objects.get(name='MSA_TEST')
        self.assertEqual(org_state.description, 'State Media Institution: MSA_TEST')

        org_owner = Organization.objects.get(name='OKMQ_TEST')
        self.assertEqual(org_owner.description, 'Test Organization')

        # Verify output contains success messages
        output = out.getvalue()
        self.assertIn('✓ Created MediaAuthority: OKMQ_TEST', output)
        self.assertIn('✓ Created Organization: MSA_TEST', output)
        self.assertIn('✓ Created Organization: OKMQ_TEST (Test Organization)', output)

    @patch('django.conf.settings.STATE_MEDIA_INSTITUTION', 'MSA')
    @patch('django.conf.settings.ORGANIZATION_OWNER', 'OKMQ')
    @patch('django.conf.settings.OK_NAME', 'Offener Kanal Merseburg-Querfurt e.V.')
    def test_command_creates_organizations_with_default_settings(self):
        """Test that command creates organizations using default settings."""
        # Run the command
        out = StringIO()
        call_command('setup_organizations', stdout=out)

        # Verify MediaAuthority was created
        media_authority = MediaAuthority.objects.get(name='OKMQ')
        self.assertIsNotNone(media_authority)

        # Verify Organizations were created
        org_state = Organization.objects.get(name='MSA')
        self.assertEqual(org_state.description, 'State Media Institution: MSA')

        org_owner = Organization.objects.get(name='OKMQ')
        self.assertEqual(org_owner.description, 'Open Channel Merseburg-Querfurt e.V.')

        # Verify output contains success messages
        output = out.getvalue()
        self.assertIn('✓ Created MediaAuthority: OKMQ', output)
        self.assertIn('✓ Created Organization: MSA', output)
        self.assertIn('✓ Created Organization: OKMQ (Open Channel Merseburg-Querfurt e.V.)', output)

    @patch('django.conf.settings.STATE_MEDIA_INSTITUTION', 'MSA_EXISTING')
    @patch('django.conf.settings.ORGANIZATION_OWNER', 'OKMQ_EXISTING')
    @patch('django.conf.settings.OK_NAME', 'Existing Organization')
    def test_command_handles_existing_organizations(self):
        """Test that command handles existing organizations correctly."""
        # The command reads the names from OrganizationConfig (not settings),
        # so point it at these organizations.
        from registration.models import OrganizationConfig
        config = OrganizationConfig.get_config()
        config.state_media_institution = 'MSA_EXISTING'
        config.organization_owner = 'OKMQ_EXISTING'
        config.name = 'Existing Organization'
        config.save()
        # Create organizations manually first
        MediaAuthority.objects.create(name='OKMQ_EXISTING')
        Organization.objects.create(name='MSA_EXISTING', description='State Media Institution: MSA_EXISTING')
        Organization.objects.create(name='OKMQ_EXISTING', description='Old Description')

        # Run the command
        out = StringIO()
        call_command('setup_organizations', stdout=out)

        # Verify MediaAuthority still exists
        media_authority = MediaAuthority.objects.get(name='OKMQ_EXISTING')
        self.assertIsNotNone(media_authority)

        # Verify Organizations still exist and were updated if needed
        org_state = Organization.objects.get(name='MSA_EXISTING')
        self.assertEqual(org_state.description, 'State Media Institution: MSA_EXISTING')

        org_owner = Organization.objects.get(name='OKMQ_EXISTING')
        # Description should be updated to the new value
        self.assertEqual(org_owner.description, 'Existing Organization')

        # Verify output contains warning messages for existing items
        output = out.getvalue()
        self.assertIn('MediaAuthority already exists: OKMQ_EXISTING', output)
        self.assertIn('Organization already exists: MSA_EXISTING', output)
        self.assertIn('✓ Updated Organization: OKMQ_EXISTING (Existing Organization)', output)

    @patch('django.conf.settings.STATE_MEDIA_INSTITUTION', 'MSA_NO_OVERRIDE')
    @patch('django.conf.settings.ORGANIZATION_OWNER', 'OKMQ_NO_OVERRIDE')
    @patch('django.conf.settings.OK_NAME', 'No Override Organization')
    def test_command_does_not_update_description_if_same(self):
        """Test that command doesn't update description if it's already correct."""
        # The command reads the owner name from OrganizationConfig (not
        # settings), so point it at this organization.
        from registration.models import OrganizationConfig
        config = OrganizationConfig.get_config()
        config.organization_owner = 'OKMQ_NO_OVERRIDE'
        config.name = 'No Override Organization'
        config.save()
        # Create organization with correct description
        Organization.objects.create(name='OKMQ_NO_OVERRIDE', description='No Override Organization')

        # Run the command
        out = StringIO()
        call_command('setup_organizations', stdout=out)

        # Verify output shows that organization already exists (no update message)
        output = out.getvalue()
        self.assertIn('Organization already exists: OKMQ_NO_OVERRIDE', output)
        # Should not contain the update message
        self.assertNotIn('✓ Updated Organization:', output)