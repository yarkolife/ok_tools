"""
Celery task registration for the inventory app.

Celery's Django autodiscovery imports `<app>.tasks` modules by default.
The inventory event tasks live in `inventory.events`, so we import them here
to ensure they are registered in the worker.
"""

import logging

from celery import shared_task
from django.core.management import call_command

# Import tasks for side effects (registration via @shared_task decorators).
from .events import (  # noqa: F401
    handle_rental_cancelled_event,
    handle_rental_created_event,
    handle_rental_issued_event,
    handle_rental_returned_event,
)


logger = logging.getLogger(__name__)


@shared_task(name="inventory.tasks.run_scan_inventory_images")
def run_scan_inventory_images_task(**kwargs):
    """Run the scan_inventory_images management command."""
    logger.info("Starting scan_inventory_images task...")
    args = []
    if kwargs.get("prune"):
        args.append("--prune")
    call_command("scan_inventory_images", *args)
    logger.info("Finished scan_inventory_images task.")

