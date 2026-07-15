"""
Inventory Service Interface

This module defines an abstract interface for interacting with the inventory system
and provides implementations that use either direct model calls or API calls.

The interface allows for decoupling the rental module from direct dependencies
on inventory models, preparing for a future transition to microservices.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import requests
import logging

logger = logging.getLogger(__name__)


class InventoryOperationResult(Enum):
    """Results of inventory operations."""
    SUCCESS = "success"
    INSUFFICIENT_QUANTITY = "insufficient_quantity"
    ITEM_NOT_FOUND = "item_not_found"
    ITEM_NOT_AVAILABLE = "item_not_available"
    ACCESS_DENIED = "access_denied"
    INVALID_QUANTITY = "invalid_quantity"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class InventoryOperationResponse:
    """Structured response for inventory operations."""
    result: InventoryOperationResult
    message: str
    data: Optional[Dict[str, Any]] = None
    item_id: Optional[int] = None


class InventoryServiceInterface(ABC):
    """
    Abstract interface for inventory interactions.
    
    This interface defines the contract for all operations with the inventory system
    used by the rental module. Initially, the implementation will use direct calls
    to inventory models, but in the future it can be replaced with API calls when
    transitioning to a microservices architecture.
    """
    
    # Read methods
    @abstractmethod
    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get item information by ID.
        
        Args:
            item_id: ID of the inventory item
            
        Returns:
            Dictionary with item data or None if item not found
        """
        pass
    
    @abstractmethod
    def get_available_items(self, user_id: Optional[int] = None, 
                          filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Get list of available items for rent.
        
        Args:
            user_id: ID of user for access filtering (optional)
            filters: Additional filters (category, location, etc.)
            
        Returns:
            List of dictionaries with available item data
        """
        pass
    
    @abstractmethod
    def check_availability(self, item_id: int, quantity: int, 
                         start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check item availability for specified quantity and period.
        
        Args:
            item_id: ID of the inventory item
            quantity: Required quantity
            start_date: Start date of period (optional)
            end_date: End date of period (optional)
            
        Returns:
            Tuple of (is_available, status_message)
        """
        pass
    
    @abstractmethod
    def get_available_quantity(self, item_id: int) -> int:
        """
        Get available quantity for an item.
        
        Args:
            item_id: ID of the inventory item
            
        Returns:
            Available quantity
        """
        pass
    
    @abstractmethod
    def can_user_access_item(self, user_id: int, item_id: int) -> bool:
        """
        Check if user has access to an item.
        
        Args:
            user_id: ID of the user
            item_id: ID of the inventory item
            
        Returns:
            True if user has access, False otherwise
        """
        pass
    
    # Helper methods
    @abstractmethod
    def get_items_by_ids(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get multiple items by their IDs.
        
        Args:
            item_ids: List of item IDs
            
        Returns:
            List of dictionaries with item data
        """
        pass
    
    @abstractmethod
    def get_item_categories(self) -> List[Dict[str, Any]]:
        """
        Get list of item categories.
        
        Returns:
            List of dictionaries with category data
        """
        pass
    
    @abstractmethod
    def get_item_locations(self) -> List[Dict[str, Any]]:
        """
        Get list of item locations.
        
        Returns:
            List of dictionaries with location data
        """
        pass
    
    @abstractmethod
    def get_item_organizations(self) -> List[Dict[str, Any]]:
        """
        Get list of item organizations.
        
        Returns:
            List of dictionaries with organization data
        """
        pass


class DirectInventoryService(InventoryServiceInterface):
    """
    Implementation of InventoryServiceInterface using direct model calls.
    
    This is a temporary implementation that will be replaced with API calls
    when transitioning to microservices architecture.
    """
    
    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get item information by ID."""
        try:
            from inventory.models import InventoryItem
            item = InventoryItem.objects.get(id=item_id)
            return {
                'id': item.id,
                'inventory_number': item.inventory_number,
                'description': item.description,
                'manufacturer': item.manufacturer,
                'location': item.location.id if item.location else None,
                'quantity': item.quantity,
                'status': item.status,
                'owner': item.owner.id if item.owner else None,
                'available_for_rent': item.available_for_rent,
                'reserved_quantity': item.reserved_quantity,
                'rented_quantity': item.rented_quantity
            }
        except InventoryItem.DoesNotExist:
            return None
    
    def get_items_by_ids(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple items by their IDs."""
        from inventory.models import InventoryItem
        
        if not item_ids:
            return []
        
        items = InventoryItem.objects.filter(id__in=item_ids)
        result = []
        for item in items:
            result.append({
                'id': item.id,
                'inventory_number': item.inventory_number,
                'description': item.description,
                'manufacturer': item.manufacturer,
                'location': {
                    'id': item.location.id,
                    'name': item.location.name,
                    'full_path': item.location.full_path
                } if item.location else None,
                'quantity': item.quantity,
                'status': item.status,
                'owner': {
                    'id': item.owner.id,
                    'name': item.owner.name
                } if item.owner else None,
                'available_for_rent': item.available_for_rent,
                'reserved_quantity': item.reserved_quantity,
                'rented_quantity': item.rented_quantity,
                'category': {
                    'id': item.category.id,
                    'name': item.category.name
                } if item.category else None
            })
        return result
    
    def get_item_by_inventory_number(self, inventory_number: str) -> Optional[Dict[str, Any]]:
        """
        Get item information by inventory number.
        
        Args:
            inventory_number: Inventory number of the item
            
        Returns:
            Dictionary with item data or None if item not found
        """
        try:
            from inventory.models import InventoryItem
            item = InventoryItem.objects.get(inventory_number=inventory_number)
            return {
                'id': item.id,
                'inventory_number': item.inventory_number,
                'description': item.description,
                'manufacturer': item.manufacturer,
                'location': {
                    'id': item.location.id,
                    'name': item.location.name,
                    'full_path': item.location.full_path
                } if item.location else None,
                'quantity': item.quantity,
                'status': item.status,
                'owner': {
                    'id': item.owner.id,
                    'name': item.owner.name
                } if item.owner else None,
                'available_for_rent': item.available_for_rent,
                'reserved_quantity': item.reserved_quantity,
                'rented_quantity': item.rented_quantity,
                'category': {
                    'id': item.category.id,
                    'name': item.category.name
                } if item.category else None
            }
        except InventoryItem.DoesNotExist:
            return None
    
    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get item information by ID (alias for get_item_by_id).
        
        Args:
            item_id: ID of the inventory item
            
        Returns:
            Dictionary with item data or None if item not found
        """
        return self.get_item_by_id(item_id)
    
    def get_available_items(self, user_id: Optional[int] = None,
                          filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get list of available items for rent."""
        from inventory.models import InventoryItem
        from django.conf import settings
        
        query = InventoryItem.objects.filter(
            available_for_rent=True,
            status='in_stock'
        )
        
        # Apply user-specific filters if user_id provided
        if user_id:
            try:
                from registration.models import OKUser
                from rental.models import RentalConfig
                user = OKUser.objects.get(id=user_id)

                # Staff users (Mitarbeiter) have access to all items
                if user.is_staff:
                    # No filtering needed - staff can access all items
                    pass
                else:
                    orgs = RentalConfig.get_organizations_for(user)
                    profile = getattr(user, 'profile', None)
                    if orgs.exists():
                        query = query.filter(
                            owner__isnull=False,
                            owner__in=orgs
                        )
                    elif profile and profile.member:
                        # Fallback to hardcoded behavior
                        state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
                        organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
                        query = query.filter(
                            owner__isnull=False,
                            owner__name__in=[state_institution, organization_owner]
                        )
                    else:
                        # Fallback to hardcoded behavior. A rental-only profile
                        # without its own organizations lands here too, i.e. it
                        # is treated like a regular confirmed user.
                        state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
                        query = query.filter(
                            owner__isnull=False,
                            owner__name=state_institution
                        )
            except OKUser.DoesNotExist:
                # If user doesn't exist, return empty list
                return []
        
        # Apply additional filters if provided
        if filters:
            if 'category' in filters:
                query = query.filter(category=filters['category'])
            if 'location' in filters:
                query = query.filter(location=filters['location'])
            # Add more filter conditions as needed
        
        # Convert to list of dictionaries
        items = []
        for item in query.select_related('manufacturer', 'category', 'location', 'owner'):
            items.append({
                'id': item.id,
                'inventory_number': item.inventory_number,
                'description': item.description,
                'manufacturer': item.manufacturer.name if item.manufacturer else None,
                'location': {
                    'id': item.location.id,
                    'name': item.location.name,
                    'full_path': item.location.full_path
                } if item.location else None,
                'quantity': item.quantity,
                'status': item.status,
                'owner': {
                    'id': item.owner.id,
                    'name': item.owner.name
                } if item.owner else None,
                'available_for_rent': item.available_for_rent,
                'reserved_quantity': item.reserved_quantity,
                'rented_quantity': item.rented_quantity,
                'category': {
                    'id': item.category.id,
                    'name': item.category.name
                } if item.category else None
            })
        
        return items
    
    def check_availability(self, item_id: int, quantity: int, 
                         start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> Tuple[bool, str]:
        """Check item availability for specified quantity and period."""
        item_data = self.get_item_by_id(item_id)
        if not item_data:
            return False, "Item not found"
        
        available = (item_data['quantity'] or 0) - (item_data['reserved_quantity'] or 0) - (item_data['rented_quantity'] or 0)
        
        if quantity <= available:
            return True, f"Available: {available} items"
        else:
            return False, f"Insufficient quantity: requested {quantity}, available {available}"
    
    def get_available_quantity(self, item_id: int) -> int:
        """Get available quantity for an item."""
        item_data = self.get_item_by_id(item_id)
        if not item_data:
            return 0
        
        return (item_data['quantity'] or 0) - (item_data['reserved_quantity'] or 0) - (item_data['rented_quantity'] or 0)
    
    def can_user_access_item(self, user_id: int, item_id: int) -> bool:
        """Check if user has access to an item."""
        try:
            from registration.models import OKUser
            from inventory.models import InventoryItem
            from django.conf import settings
            
            user = OKUser.objects.get(id=user_id)
            item = InventoryItem.objects.get(id=item_id)
            
            # If item is not available for rent, no one can access it
            if not item.available_for_rent or item.status != 'in_stock':
                return False
            
            # Staff users (Mitarbeiter) have access to all items
            if user.is_staff:
                return True
            
            # Check ownership-based access
            if hasattr(user, 'profile') and user.profile and user.profile.member:
                # Member can access state institution + organization
                state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
                organization_owner = getattr(settings, 'ORGANIZATION_OWNER', 'OKMQ')
                return item.owner.name in [state_institution, organization_owner] if item.owner else False
            else:
                # Non-member can only access state media institution
                state_institution = getattr(settings, 'STATE_MEDIA_INSTITUTION', 'MSA')
                return item.owner.name == state_institution if item.owner else False
                
        except (OKUser.DoesNotExist, InventoryItem.DoesNotExist):
            return False
    
    def get_item_categories(self) -> List[Dict[str, Any]]:
        """Get list of item categories."""
        try:
            from inventory.models import Category
            categories = []
            for category in Category.objects.all():
                categories.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description
                })
            return categories
        except Exception:
            return []
    
    def get_item_locations(self) -> List[Dict[str, Any]]:
        """Get list of item locations."""
        try:
            from inventory.models import Location
            locations = []
            for location in Location.objects.all():
                locations.append({
                    'id': location.id,
                    'name': location.name,
                    'description': location.description,
                    'full_path': location.full_path
                })
            return locations
        except Exception:
            return []
    
    def get_item_organizations(self) -> List[Dict[str, Any]]:
        """Get list of item organizations."""
        try:
            from inventory.models import Organization
            organizations = []
            for org in Organization.objects.all():
                organizations.append({
                    'id': org.id,
                    'name': org.name,
                    'description': org.description
                })
            return organizations
        except Exception:
            return []


class ApiInventoryService(InventoryServiceInterface):
    """
    Implementation of InventoryServiceInterface using API calls to inventory service.
    
    This implementation calls the inventory API instead of directly accessing
    inventory models, allowing for better decoupling between the rental and
    inventory applications.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the API service with base URL.
        
        Args:
            base_url: Base URL for the inventory API. If not provided,
                     will use the INVENTORY_API_BASE_URL setting or default to /inventory/api/
        """
        from django.conf import settings
        self.base_url = base_url or getattr(settings, 'INVENTORY_API_BASE_URL', '/inventory/api/')
        if not self.base_url.endswith('/'):
            self.base_url += '/'
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request to the inventory API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint to call
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response object or None if request failed
        """
        try:
            import requests
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            response = requests.request(method, url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to inventory API: {e}")
            return None
        except ImportError:
            logger.error("Requests library not available")
            return None
    
    def get_items_by_ids(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple items by their IDs via API."""
        if not item_ids:
            return []
        
        # Build query parameters
        params = {
            'ids': ','.join(map(str, item_ids))
        }
        
        response = self._make_request('GET', 'items/batch/', params=params)
        if response and response.status_code == 200:
            return response.json()
        return []
    
    def get_item_by_inventory_number(self, inventory_number: str) -> Optional[Dict[str, Any]]:
        """
        Get item information by inventory number via API.
        
        Args:
            inventory_number: Inventory number of the item
            
        Returns:
            Dictionary with item data or None if item not found
        """
        params = {
            'inventory_number': inventory_number
        }
        
        response = self._make_request('GET', 'items/by_inventory_number/', params=params)
        if response and response.status_code == 200:
            return response.json()
        return None
    
    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get item information by ID via API (alias for get_item_by_id).
        
        Args:
            item_id: ID of the inventory item
            
        Returns:
            Dictionary with item data or None if item not found
        """
        return self.get_item_by_id(item_id)
    
    def get_item_by_id(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get item information by ID via API."""
        response = self._make_request('GET', f'items/{item_id}/')
        if response and response.status_code == 200:
            return response.json()
        return None
    
    def get_available_items(self, user_id: Optional[int] = None,
                          filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get list of available items for rent via API."""
        # Build query parameters
        params = {
            'available_for_rent': 'true',
            'status': 'in_stock'
        }
        
        if user_id:
            params['user_id'] = user_id
            
        # Apply additional filters if provided
        if filters:
            params.update(filters)
        
        response = self._make_request('GET', 'items/', params=params)
        if response and response.status_code == 200:
            return response.json()
        return []
    
    def check_availability(self, item_id: int, quantity: int,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> Tuple[bool, str]:
        """Check item availability via API."""
        params = {
            'quantity': quantity
        }
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        response = self._make_request('GET', f'items/{item_id}/check_availability/', params=params)
        if response and response.status_code == 200:
            data = response.json()
            return data['available'], data['message']
        elif response and response.status_code == 400:
            data = response.json()
            return data['available'], data['message']
        elif response and response.status_code == 404:
            return False, "Item not found"
        else:
            return False, "Error checking availability"
    
    def get_available_quantity(self, item_id: int) -> int:
        """Get available quantity for an item via API."""
        response = self._make_request('GET', f'items/{item_id}/available_quantity/')
        if response and response.status_code == 200:
            data = response.json()
            return data.get('available_quantity', 0)
        return 0
    
    def can_user_access_item(self, user_id: int, item_id: int) -> bool:
        """Check if user has access to an item via API."""
        # Get item details and check if it's available for the user
        item_data = self.get_item_by_id(item_id)
        if not item_data:
            return False
        
        # Check if item is available for rent and in stock
        if not item_data.get('available_for_rent', False) or item_data.get('status') != 'in_stock':
            return False
        
        # If user_id is provided, we can check access based on user's permissions
        if user_id:
            # Get available items for this user to see if the item appears in the list
            available_items = self.get_available_items(user_id=user_id)
            return any(item['id'] == item_id for item in available_items)
        else:
            # If no user_id provided, just check if item is available for general rent
            return item_data.get('available_for_rent', False)
    
    def get_item_categories(self) -> List[Dict[str, Any]]:
        """Get list of item categories via API."""
        response = self._make_request('GET', 'categories/')
        if response and response.status_code == 200:
            return response.json()
        return []
        
        
    def get_item_locations(self) -> List[Dict[str, Any]]:
        """Get list of item locations via API."""
        response = self._make_request('GET', 'locations/')
        if response and response.status_code == 200:
            return response.json()
        return []
     
    def get_item_organizations(self) -> List[Dict[str, Any]]:
        """Get list of item organizations via API."""
        response = self._make_request('GET', 'organizations/')
        if response and response.status_code == 200:
            return response.json()
        return []
        
# Global instance for use throughout the rental module
# Use DirectInventoryService for now to avoid API URL issues in tests
inventory_service = DirectInventoryService()