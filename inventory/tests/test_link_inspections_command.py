"""
Tests for the deprecated link_inspections management command.

Inspection.inventory_item is a foreign key that stores the inventory number in
its own db column (to_field="inventory_number"), so linking happens during the
import itself. The command is kept as a no-op for backwards compatibility.
"""
from datetime import date
from django.core.management import call_command
from django.test import TestCase
from inventory.models import Inspection, InventoryItem, Location
from io import StringIO


class LinkInspectionsCommandTest(TestCase):
    """Unit tests for link_inspections management command."""

    def setUp(self):
        """Set up one linked and one unlinked inspection."""
        self.location = Location.objects.create(name='Test Location')
        self.item = InventoryItem.objects.create(
            description='Test Item 1',
            inventory_number='INV001',
            location=self.location,
            quantity=1,
        )
        self.linked = Inspection.objects.create(
            inspection_number='INSP001',
            inventory_item=self.item,
            target_part=Inspection.TargetPart.DEVICE,
            inspection_date=date(2023, 1, 1),
            result='Passed',
        )
        self.unlinked = Inspection.objects.create(
            inspection_number='INSP002',
            inventory_item=None,
            target_part=Inspection.TargetPart.CABLE,
            inspection_date=date(2023, 1, 2),
            result='Failed',
        )

    def _run(self):
        """Run the command and return its output."""
        out = StringIO()
        call_command('link_inspections', stdout=out)
        return out.getvalue()

    def test_command_warns_that_it_is_deprecated(self):
        """The command tells the caller it no longer does anything."""
        output = self._run()

        self.assertIn('deprecated', output)
        self.assertIn('linked on import', output)

    def test_command_reports_unlinked_count(self):
        """The command reports how many inspections have no inventory item."""
        self.assertIn('Unlinked inspection(s): 1.', self._run())

        self.unlinked.delete()

        self.assertIn('Unlinked inspection(s): 0.', self._run())

    def test_command_does_not_change_any_inspection(self):
        """Neither linked nor unlinked inspections are touched."""
        self._run()

        self.linked.refresh_from_db()
        self.unlinked.refresh_from_db()

        self.assertEqual(self.linked.inventory_item, self.item)
        self.assertIsNone(self.unlinked.inventory_item)
