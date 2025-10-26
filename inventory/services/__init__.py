"""
Services module for the inventory application.

This module contains service classes that encapsulate business logic
for inventory operations, separating it from views and models.
"""

from .inventory_service import InventoryService

__all__ = [
    'InventoryService',
]