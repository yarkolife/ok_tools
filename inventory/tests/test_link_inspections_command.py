from django.core.management import call_command
from django.test import TestCase
from io import StringIO
from unittest.mock import patch
from inventory.models import Inspection, InventoryItem, Location
from django.db import models


class LinkInspectionsCommandTest(TestCase):
    """Unit tests for link_inspections management command."""

    def setUp(self):
        """Set up test data."""
        # InventoryItem has no `name` field (it uses `description`) and
        # requires location and quantity.
        self.location = Location.objects.create(name='Test Location')
        self.item1 = InventoryItem.objects.create(
            description='Test Item 1',
            inventory_number='INV001',
            location=self.location,
            quantity=1,
        )
        self.item2 = InventoryItem.objects.create(
            description='Test Item 2',
            inventory_number='INV002',
            location=self.location,
            quantity=1,
        )
        
        # Create test inspections
        self.inspection1 = Inspection.objects.create(
            inventory_number='INV001',  # Links to item1
            target_part='Part A',
            inspection_date='2023-01-01',
            result='Passed'
        )
        self.inspection2 = Inspection.objects.create(
            inventory_number='INV002',  # Links to item2
            target_part='Part B',
            inspection_date='2023-01-02',
            result='Failed'
        )
        self.inspection3 = Inspection.objects.create(
            inventory_number='',  # No inventory number, won't be linked
            target_part='Part C',
            inspection_date='2023-01-03',
            result='Passed'
        )
        self.inspection4 = Inspection.objects.create(
            inventory_number='INV999',  # Non-existent inventory number, won't be linked
            target_part='Part D',
            inspection_date='2023-01-04',
            result='Passed'
        )

    def test_command_links_unlinked_inspections(self):
        """Test that command links unlinked inspections to inventory items."""
        # Initially, inspections should not be linked to inventory items
        self.assertIsNone(self.inspection1.inventory_item)
        self.assertIsNone(self.inspection2.inventory_item)
        self.assertIsNone(self.inspection3.inventory_item)
        self.assertIsNone(self.inspection4.inventory_item)

        # Run the command
        out = StringIO()
        call_command('link_inspections', stdout=out)

        # Refresh from database
        self.inspection1.refresh_from_db()
        self.inspection2.refresh_from_db()
        self.inspection3.refresh_from_db()
        self.inspection4.refresh_from_db()

        # Verify that inspections with matching inventory numbers are linked
        self.assertEqual(self.inspection1.inventory_item, self.item1)
        self.assertEqual(self.inspection2.inventory_item, self.item2)
        # Inspections without matching inventory numbers should remain unlinked
        self.assertIsNone(self.inspection3.inventory_item)
        self.assertIsNone(self.inspection4.inventory_item)

        # Verify output message
        output = out.getvalue().strip()
        self.assertIn('Linked 2 inspection(s).', output)

    def test_command_only_processes_unlinked_inspections(self):
        """Test that command only processes inspections that are not already linked."""
        # Link one inspection manually
        self.inspection1.inventory_item = self.item1
        self.inspection1.save()

        # Run the command
        out = StringIO()
        call_command('link_inspections', stdout=out)

        # Refresh from database
        self.inspection1.refresh_from_db()
        self.inspection2.refresh_from_db()

        # Verify that already linked inspection remains linked
        self.assertEqual(self.inspection1.inventory_item, self.item1)
        # Verify that unlinked inspection gets linked
        self.assertEqual(self.inspection2.inventory_item, self.item2)

        # Only 1 inspection should have been linked (since 1 was already linked)
        output = out.getvalue().strip()
        self.assertIn('Linked 1 inspection(s).', output)

    def test_command_handles_empty_inventory_numbers(self):
        """Test that command properly handles inspections with empty inventory numbers."""
        # Create an inspection with empty inventory number but no existing link
        inspection_empty = Inspection.objects.create(
            inventory_number='',  # Empty inventory number
            target_part='Part E',
            inspection_date='2023-01-05',
            result='Passed'
        )

        # Run the command
        out = StringIO()
        call_command('link_inspections', stdout=out)

        # Refresh from database
        inspection_empty.refresh_from_db()

        # Verify that inspection with empty inventory number remains unlinked
        self.assertIsNone(inspection_empty.inventory_item)

        # Only the inspections with valid inventory numbers should be linked
        output = out.getvalue().strip()
        self.assertIn('Linked 2 inspection(s).', output)  # Should still link the 2 valid ones