from django.core.management.base import BaseCommand
from inventory.models import Inspection


class Command(BaseCommand):
    """Deprecated no-op kept for backwards compatibility of existing call sites."""

    help = (
        "Deprecated. Inspections are linked to inventory items during import; "
        "the inventory number is the foreign key column itself, so there is "
        "nothing left to link afterwards."
    )

    def handle(self, *args, **options):
        """Report the number of unlinked inspections without changing anything."""
        unlinked = Inspection.objects.filter(inventory_item__isnull=True).count()
        self.stdout.write(self.style.WARNING(
            "link_inspections is deprecated and does nothing: inspections are "
            "linked on import (inventory_number is the foreign key column)."
        ))
        self.stdout.write(f"Unlinked inspection(s): {unlinked}.")
