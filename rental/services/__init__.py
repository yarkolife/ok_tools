"""
Services module for the rental application.

This module contains service classes that encapsulate business logic
for rental operations, separating it from views and models.
"""

from .rental_service import RentalService

__all__ = [
    'RentalService',
]