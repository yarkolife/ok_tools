"""
Celery task registration for the inventory app.

Celery's Django autodiscovery imports `<app>.tasks` modules by default.
The inventory event tasks live in `inventory.events`, so we import them here
to ensure they are registered in the worker.
"""

# Import tasks for side effects (registration via @shared_task decorators).
from .events import (  # noqa: F401
    handle_rental_cancelled_event,
    handle_rental_created_event,
    handle_rental_issued_event,
    handle_rental_returned_event,
)

