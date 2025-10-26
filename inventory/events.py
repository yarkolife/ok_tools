"""
Event handlers for inventory operations triggered by rental service.

This module defines Celery tasks that handle events from the rental service
in an asynchronous, event-driven manner.
"""

from celery import shared_task
from django.db import transaction
from typing import Dict, Any
import logging

logger = logging.getLogger('django')


@shared_task
def handle_rental_created_event(item_id: int, quantity: int, user_id: int) -> Dict[str, Any]:
    """
    Handle event when a rental is created.
    
    This task is triggered when equipment is reserved in the rental service.
    It updates the inventory item's reserved quantity.
    
    Args:
        item_id: ID of the inventory item
        quantity: Quantity being reserved
        user_id: ID of the user performing the operation
        
    Returns:
        Dict with result of the operation
    """
    try:
        from .models import InventoryItem
        from .services.inventory_service import InventoryService
        
        logger.info(f"Processing rental created event for item {item_id}, quantity {quantity}")
        
        with transaction.atomic():
            try:
                item = InventoryItem.objects.select_for_update().get(id=item_id)
                
                # Reserve the quantity in inventory
                success = InventoryService.reserve_inventory_item(item, quantity)
                
                if success:
                    logger.info(f"Successfully reserved {quantity} of item {item_id}")
                    return {
                        'status': 'success',
                        'message': f'Successfully reserved {quantity} items',
                        'item_id': item_id
                    }
                else:
                    logger.warning(f"Failed to reserve {quantity} of item {item_id} - insufficient quantity")
                    return {
                        'status': 'failed',
                        'message': 'Insufficient quantity available',
                        'item_id': item_id
                    }
                    
            except InventoryItem.DoesNotExist:
                logger.error(f"Inventory item {item_id} not found")
                return {
                    'status': 'failed',
                    'message': 'Item not found',
                    'item_id': item_id
                }
                
    except Exception as e:
        logger.error(f"Error processing rental created event for item {item_id}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing event: {str(e)}',
            'item_id': item_id
        }


@shared_task
def handle_rental_issued_event(item_id: int, quantity: int, user_id: int) -> Dict[str, Any]:
    """
    Handle event when a rental is issued.
    
    This task is triggered when reserved equipment is actually issued to a user.
    It updates the inventory item's reserved and rented quantities.
    
    Args:
        item_id: ID of the inventory item
        quantity: Quantity being issued
        user_id: ID of the user performing the operation
        
    Returns:
        Dict with result of the operation
    """
    try:
        from .models import InventoryItem
        from .services.inventory_service import InventoryService
        
        logger.info(f"Processing rental issued event for item {item_id}, quantity {quantity}")
        
        with transaction.atomic():
            try:
                item = InventoryItem.objects.select_for_update().get(id=item_id)
                
                # Rent out the quantity (convert from reserved to rented)
                success = InventoryService.rent_inventory_item(item, quantity)
                
                if success:
                    logger.info(f"Successfully issued {quantity} of item {item_id}")
                    return {
                        'status': 'success',
                        'message': f'Successfully issued {quantity} items',
                        'item_id': item_id
                    }
                else:
                    logger.warning(f"Failed to issue {quantity} of item {item_id} - insufficient reserved quantity")
                    return {
                        'status': 'failed',
                        'message': 'Insufficient reserved quantity',
                        'item_id': item_id
                    }
                    
            except InventoryItem.DoesNotExist:
                logger.error(f"Inventory item {item_id} not found")
                return {
                    'status': 'failed',
                    'message': 'Item not found',
                    'item_id': item_id
                }
                
    except Exception as e:
        logger.error(f"Error processing rental issued event for item {item_id}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing event: {str(e)}',
            'item_id': item_id
        }


@shared_task
def handle_rental_returned_event(item_id: int, quantity: int, user_id: int) -> Dict[str, Any]:
    """
    Handle event when equipment is returned.
    
    This task is triggered when rented equipment is returned.
    It updates the inventory item's rented quantity.
    
    Args:
        item_id: ID of the inventory item
        quantity: Quantity being returned
        user_id: ID of the user performing the operation
        
    Returns:
        Dict with result of the operation
    """
    try:
        from .models import InventoryItem
        from .services.inventory_service import InventoryService
        
        logger.info(f"Processing rental returned event for item {item_id}, quantity {quantity}")
        
        with transaction.atomic():
            try:
                item = InventoryItem.objects.select_for_update().get(id=item_id)
                
                # Return the quantity to inventory
                success = InventoryService.return_inventory_item(item, quantity)
                
                if success:
                    logger.info(f"Successfully returned {quantity} of item {item_id}")
                    return {
                        'status': 'success',
                        'message': f'Successfully returned {quantity} items',
                        'item_id': item_id
                    }
                else:
                    logger.warning(f"Failed to return {quantity} of item {item_id} - invalid quantity")
                    return {
                        'status': 'failed',
                        'message': 'Invalid return quantity',
                        'item_id': item_id
                    }
                    
            except InventoryItem.DoesNotExist:
                logger.error(f"Inventory item {item_id} not found")
                return {
                    'status': 'failed',
                    'message': 'Item not found',
                    'item_id': item_id
                }
                
    except Exception as e:
        logger.error(f"Error processing rental returned event for item {item_id}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing event: {str(e)}',
            'item_id': item_id
        }


@shared_task
def handle_rental_cancelled_event(item_id: int, quantity: int, user_id: int) -> Dict[str, Any]:
    """
    Handle event when a rental is cancelled.
    
    This task is triggered when a rental reservation is cancelled.
    It updates the inventory item's reserved quantity.
    
    Args:
        item_id: ID of the inventory item
        quantity: Quantity being cancelled
        user_id: ID of the user performing the operation
        
    Returns:
        Dict with result of the operation
    """
    try:
        from .models import InventoryItem
        from .services.inventory_service import InventoryService
        
        logger.info(f"Processing rental cancelled event for item {item_id}, quantity {quantity}")
        
        with transaction.atomic():
            try:
                item = InventoryItem.objects.select_for_update().get(id=item_id)
                
                # Release the reservation
                success = InventoryService.release_inventory_reservation(item, quantity)
                
                if success:
                    logger.info(f"Successfully cancelled reservation of {quantity} of item {item_id}")
                    return {
                        'status': 'success',
                        'message': f'Successfully cancelled reservation of {quantity} items',
                        'item_id': item_id
                    }
                else:
                    logger.warning(f"Failed to cancel reservation of {quantity} of item {item_id} - invalid quantity")
                    return {
                        'status': 'failed',
                        'message': 'Invalid cancellation quantity',
                        'item_id': item_id
                    }
                    
            except InventoryItem.DoesNotExist:
                logger.error(f"Inventory item {item_id} not found")
                return {
                    'status': 'failed',
                    'message': 'Item not found',
                    'item_id': item_id
                }
                
    except Exception as e:
        logger.error(f"Error processing rental cancelled event for item {item_id}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing event: {str(e)}',
            'item_id': item_id
        }