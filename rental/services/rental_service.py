"""
Rental service module containing business logic for rental operations.

This module encapsulates the business logic for rental operations,
separating it from views and models.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.conf import settings

from ..models import (
    RentalRequest, RentalItem, RentalTransaction, EquipmentSet,
    EquipmentSetItem, Room, RoomRental, EquipmentTemplate, EquipmentTemplateItem
)
from .inventory_service_interface import inventory_service


class RentalService:
    """
    Service class for rental operations.
    
    Encapsulates business logic for creating, updating, and managing rentals,
    equipment availability checking, room scheduling, and equipment set management.
    """
    
    @staticmethod
    def check_user_inventory_access(user, inventory_item_id: int) -> bool:
        """
        Check if user has access to inventory item based on membership status.
        
        Args:
            user: The user object
            inventory_item_id: The ID of the inventory item to check access for
            
        Returns:
            bool: True if user has access, False otherwise
        """
        return inventory_service.can_user_access_item(user.id, inventory_item_id)
    
    @staticmethod
    def get_user_available_inventory(user) -> List[Dict[str, Any]]:
        """
        Get available inventory items for a user based on their access rights.
        
        Args:
            user: The user object
            
        Returns:
            List[Dict]: Available inventory items for the user
        """
        return inventory_service.get_available_items(user.id)
    
    @staticmethod
    def get_available_quantity_for_period(
        inventory_item_id: int,
        start_date: datetime,
        end_date: datetime,
        exclude_rental_request: Optional[int] = None
    ) -> int:
        """
        Calculate available quantity of an inventory item for a specific time period.
        
        Args:
            inventory_item_id: The ID of the inventory item to check
            start_date: Start of the rental period
            end_date: End of the rental period
            exclude_rental_request: Optional rental request ID to exclude from calculation
            
        Returns:
            int: Available quantity for the period
        """
        # Get total quantity of the item
        item_data = inventory_service.get_item_by_id(inventory_item_id)
        if not item_data:
            return 0
        total_quantity = item_data['quantity'] or 0
        
        # Get all rental items for this inventory item that overlap with the requested period
        conflicting_rentals = RentalItem.objects.filter(
            inventory_item_id=inventory_item_id,
            rental_request__status__in=['reserved', 'issued']
        )
        
        # Exclude specific rental request if provided
        if exclude_rental_request:
            conflicting_rentals = conflicting_rentals.exclude(
                rental_request_id=exclude_rental_request
            )
        
        # Filter by time overlap
        available_quantity = total_quantity
        for rental_item in conflicting_rentals:
            rental_start = rental_item.rental_request.requested_start_date
            rental_end = rental_item.rental_request.requested_end_date
            
            # Check time interval overlap
            if rental_start and rental_end:
                if (start_date < rental_end and end_date > rental_start):
                    # There is overlap, subtract the quantity
                    available_quantity -= (rental_item.quantity_issued or rental_item.quantity_requested or 0)
        
        return max(0, available_quantity)
    
    @staticmethod
    def check_room_availability(
        room: Room, 
        start_date: datetime, 
        end_date: datetime,
        exclude_rental_request: Optional[int] = None
    ) -> bool:
        """
        Check if a room is available for the specified time period.
        
        Args:
            room: The room to check
            start_date: Start of the rental period
            end_date: End of the rental period
            exclude_rental_request: Optional rental request ID to exclude
            
        Returns:
            bool: True if room is available, False otherwise
        """
        return room.is_available_for_time(start_date, end_date, exclude_rental_request)
    
    @staticmethod
    def get_available_rooms(start_date: datetime, end_date: datetime) -> List[Room]:
        """
        Get list of available rooms for the specified time period.
        
        Args:
            start_date: Start of the rental period
            end_date: End of the rental period
            
        Returns:
            QuerySet: Available rooms
        """
        all_rooms = Room.objects.filter(is_active=True)
        available_rooms = []
        
        for room in all_rooms:
            if RentalService.check_room_availability(room, start_date, end_date):
                available_rooms.append(room)
        
        return available_rooms
    
    @staticmethod
    def create_rental_request(
        user,
        created_by,
        project_name: str,
        purpose: str,
        start_date: datetime,
        end_date: datetime,
        rental_type: str = 'equipment',
        notes: str = ''
    ) -> RentalRequest:
        """
        Create a new rental request.
        
        Args:
            user: The user requesting the rental
            created_by: The user creating the rental request
            project_name: Name of the project
            purpose: Purpose of the rental
            start_date: Start date of the rental
            end_date: End date of the rental
            rental_type: Type of rental (equipment, room, mixed)
            notes: Additional notes
            
        Returns:
            RentalRequest: The created rental request
        """
        rental_request = RentalRequest.objects.create(
            user=user,
            created_by=created_by,
            project_name=project_name,
            purpose=purpose,
            requested_start_date=start_date,
            requested_end_date=end_date,
            rental_type=rental_type,
            notes=notes,
            status='draft'
        )
        
        return rental_request
    
    @staticmethod
    def add_items_to_rental_request(
        rental_request: RentalRequest,
        items_data: List[Dict[str, Any]]
    ) -> List[RentalItem]:
        """
        Add items to a rental request.
        
        Args:
            rental_request: The rental request to add items to
            items_data: List of dictionaries containing item data
                       (inventory_item_id, quantity_requested, notes)
                       
        Returns:
            List[RentalItem]: List of created rental items
        """
        rental_items = []
        
        for item_data in items_data:
            # Check if user has access to this item
            if not RentalService.check_user_inventory_access(rental_request.user, item_data['inventory_item_id']):
                continue
                
            # Check availability
            available_quantity = RentalService.get_available_quantity_for_period(
                item_data['inventory_item_id'],
                rental_request.requested_start_date,
                rental_request.requested_end_date,
                rental_request.id if rental_request.id else None
            )
            
            if available_quantity >= item_data['quantity_requested']:
                rental_item = RentalItem.objects.create(
                    rental_request=rental_request,
                    inventory_item_id=item_data['inventory_item_id'],
                    quantity_requested=item_data['quantity_requested'],
                    notes=item_data.get('notes', '')
                )
                rental_items.append(rental_item)
        
        return rental_items
    
    @staticmethod
    def add_rooms_to_rental_request(
        rental_request: RentalRequest,
        rooms_data: List[Dict[str, Any]]
    ) -> List[RoomRental]:
        """
        Add rooms to a rental request.
        
        Args:
            rental_request: The rental request to add rooms to
            rooms_data: List of dictionaries containing room data
                        (room_id, people_count, notes)
                        
        Returns:
            List[RoomRental]: List of created room rentals
        """
        room_rentals = []
        
        for room_data in rooms_data:
            room = Room.objects.get(id=room_data['room_id'])
            
            # Check availability
            if RentalService.check_room_availability(
                room,
                rental_request.requested_start_date,
                rental_request.requested_end_date,
                rental_request.id if rental_request.id else None
            ):
                room_rental = RoomRental.objects.create(
                    rental_request=rental_request,
                    room=room,
                    people_count=room_data['people_count'],
                    notes=room_data.get('notes', '')
                )
                room_rentals.append(room_rental)
        
        return room_rentals
    
    @staticmethod
    @transaction.atomic
    def create_transaction(
        rental_item: Optional[RentalItem] = None,
        room: Optional[Room] = None,
        transaction_type: str = 'reserve',
        quantity: int = 1,
        performed_by=None,
        condition: str = '',
        notes: str = ''
    ) -> RentalTransaction:
        """
        Create a rental transaction (reserve, issue, return, cancel).
        
        Args:
            rental_item: The rental item (optional)
            room: The room (optional)
            transaction_type: Type of transaction
            quantity: Quantity for the transaction
            performed_by: User performing the transaction
            condition: Condition of the item (for returns)
            notes: Additional notes
            
        Returns:
            RentalTransaction: The created transaction
        """
        if not rental_item and not room:
            raise ValueError("Either rental_item or room must be provided")
        
        transaction = RentalTransaction.objects.create(
            rental_item=rental_item,
            room=room,
            transaction_type=transaction_type,
            quantity=quantity,
            performed_by=performed_by,
            condition=condition,
            notes=notes
        )
        
        # Update rental item quantities if applicable
        if rental_item:
            if transaction_type == 'issue':
                rental_item.quantity_issued = (rental_item.quantity_issued or 0) + quantity
                rental_item.save(update_fields=['quantity_issued'])
            elif transaction_type == 'return':
                rental_item.quantity_returned = (rental_item.quantity_returned or 0) + quantity
                rental_item.actual_return_date = timezone.now()
                rental_item.save(update_fields=['quantity_returned', 'actual_return_date'])
        
        return transaction
    
    @staticmethod
    def apply_equipment_set_to_rental_request(
        equipment_set: EquipmentSet,
        rental_request: RentalRequest
    ) -> List[RentalItem]:
        """
        Apply an equipment set to a rental request.
        
        Args:
            equipment_set: The equipment set to apply
            rental_request: The rental request to apply the set to
            
        Returns:
            List[RentalItem]: List of created/updated rental items
        """
        return equipment_set.apply_to_rental_request(rental_request)
    
    @staticmethod
    def create_equipment_set(
        name: str,
        description: str,
        created_by,
        is_template: bool = False,
        items_data: List[Dict[str, Any]] = None
    ) -> EquipmentSet:
        """
        Create a new equipment set.
        
        Args:
            name: Name of the equipment set
            description: Description of the set
            created_by: User creating the set
            is_template: Whether this is a template set
            items_data: List of items to include in the set
                        (inventory_item_id, quantity, is_required, notes)
                        
        Returns:
            EquipmentSet: The created equipment set
        """
        equipment_set = EquipmentSet.objects.create(
            name=name,
            description=description,
            created_by=created_by,
            is_template=is_template
        )
        
        if items_data:
            for item_data in items_data:
                EquipmentSetItem.objects.create(
                    equipment_set=equipment_set,
                    inventory_item_id=item_data['inventory_item_id'],
                    quantity=item_data['quantity'],
                    is_required=item_data.get('is_required', True),
                    notes=item_data.get('notes', '')
                )
        
        return equipment_set
    
    @staticmethod
    def create_equipment_template(
        name: str,
        description: str,
        created_by,
        items_data: List[Dict[str, Any]] = None
    ) -> EquipmentTemplate:
        """
        Create a new equipment template.
        
        Args:
            name: Name of the template
            description: Description of the template
            created_by: User creating the template
            items_data: List of items to include in the template
                        (inventory_item_id, quantity)
                        
        Returns:
            EquipmentTemplate: The created equipment template
        """
        template = EquipmentTemplate.objects.create(
            name=name,
            description=description,
            created_by=created_by
        )
        
        if items_data:
            for item_data in items_data:
                EquipmentTemplateItem.objects.create(
                    template=template,
                    inventory_item_id=item_data['inventory_item_id'],
                    quantity=item_data['quantity']
                )
        
        return template
    
    @staticmethod
    def get_room_schedule(room: Room, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get the schedule for a room within a date range.
        
        Args:
            room: The room to get schedule for
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            List[Dict]: List of scheduled rentals with details
        """
        room_rentals = RoomRental.objects.filter(
            room=room,
            rental_request__status__in=['reserved', 'issued']
        ).filter(
            Q(rental_request__requested_start_date__lte=end_date) &
            Q(rental_request__requested_end_date__gte=start_date)
        ).select_related('rental_request', 'rental_request__user')
        
        schedule = []
        for room_rental in room_rentals:
            schedule.append({
                'id': room_rental.rental_request.id,
                'project_name': room_rental.rental_request.project_name,
                'user': room_rental.rental_request.user.email,
                'start_date': room_rental.rental_request.requested_start_date,
                'end_date': room_rental.rental_request.requested_end_date,
                'status': room_rental.rental_request.status,
                'people_count': room_rental.people_count,
                'notes': room_rental.notes
            })
        
        return schedule
    
    @staticmethod
    def get_inventory_schedule(
        inventory_item_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Get the schedule for an inventory item within a date range.
        
        Args:
            inventory_item_id: The ID of the inventory item to get schedule for
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            List[Dict]: List of scheduled rentals with details
        """
        rental_items = RentalItem.objects.filter(
            inventory_item_id=inventory_item_id,
            rental_request__status__in=['reserved', 'issued']
        ).filter(
            Q(rental_request__requested_start_date__lte=end_date) &
            Q(rental_request__requested_end_date__gte=start_date)
        ).select_related('rental_request', 'rental_request__user')
        
        schedule = []
        for rental_item in rental_items:
            schedule.append({
                'id': rental_item.rental_request.id,
                'project_name': rental_item.rental_request.project_name,
                'user': rental_item.rental_request.user.email,
                'start_date': rental_item.rental_request.requested_start_date,
                'end_date': rental_item.rental_request.requested_end_date,
                'status': rental_item.rental_request.status,
                'quantity_requested': rental_item.quantity_requested,
                'quantity_issued': rental_item.quantity_issued,
                'quantity_returned': rental_item.quantity_returned,
                'notes': rental_item.notes
            })
        
        return schedule
    
    @staticmethod
    def cancel_rental_request(rental_request: RentalRequest, performed_by) -> None:
        """
        Cancel a rental request and handle related transactions.
        
        Args:
            rental_request: The rental request to cancel
            performed_by: User performing the cancellation
        """
        with transaction.atomic():
            # Update status
            rental_request.status = 'cancelled'
            rental_request.save(update_fields=['status'])
            
            # Cancel all reservations for items
            for rental_item in rental_request.items.all():
                reserved_balance = rental_item.reserved_balance
                if reserved_balance > 0:
                    RentalService.create_transaction(
                        rental_item=rental_item,
                        transaction_type='cancel',
                        quantity=reserved_balance,
                        performed_by=performed_by,
                        notes=f"Cancelled rental request: {rental_request.project_name}"
                    )
    
    @staticmethod
    def extend_rental(
        rental_request: RentalRequest,
        new_end_date: datetime,
        performed_by
    ) -> bool:
        """
        Extend the end date of a rental request if possible.
        
        Args:
            rental_request: The rental request to extend
            new_end_date: New end date for the rental
            performed_by: User performing the extension
            
        Returns:
            bool: True if extension was successful, False otherwise
        """
        if new_end_date <= rental_request.requested_end_date:
            return False
        
        # Check availability for all items and rooms
        for rental_item in rental_request.items.all():
            available_quantity = RentalService.get_available_quantity_for_period(
                rental_item.inventory_item_id,
                rental_request.requested_end_date,
                new_end_date,
                rental_request.id
            )
            
            if available_quantity < (rental_item.quantity_issued or rental_item.quantity_requested or 0):
                return False
        
        for room_rental in rental_request.room_rentals.all():
            if not RentalService.check_room_availability(
                room_rental.room,
                rental_request.requested_end_date,
                new_end_date,
                rental_request.id
            ):
                return False
        
        # All checks passed, update the rental request
        rental_request.requested_end_date = new_end_date
        rental_request.save(update_fields=['requested_end_date'])
        
        return True
    
    @staticmethod
    def cancel_rental(rental_id, user):
        """
        Cancel a rental request.
        
        Cancels active rentals by creating appropriate transactions
        and updating the rental status to cancelled.
        
        Args:
            rental_id: ID of the rental request to cancel
            user: User performing the cancellation
            
        Returns:
            dict: Result with success status and message
        """
        try:
            from django.shortcuts import get_object_or_404
            from django.utils.translation import gettext_lazy as _
            
            rental_request = get_object_or_404(RentalRequest, id=rental_id)
            
            # Check if rental can be cancelled
            if rental_request.status not in ['draft', 'reserved', 'issued']:
                return {
                    'success': False,
                    'error': _('Only draft, reserved or issued rentals can be cancelled')
                }
            
            # Create cancellation transactions for all items
            for rental_item in rental_request.items.all():
                # Cancel reserved quantity (if any)
                reserved_qty = (rental_item.quantity_requested or 0) - (rental_item.quantity_issued or 0)
                if reserved_qty > 0:
                    RentalTransaction.objects.create(
                        rental_item=rental_item,
                        transaction_type='cancel',
                        quantity=reserved_qty,
                        performed_by=user,
                        notes=_('Cancelled reserved quantity via admin interface')
                    )
                
                # Return issued quantity (if any)
                issued_qty = (rental_item.quantity_issued or 0) - (rental_item.quantity_returned or 0)
                if issued_qty > 0:
                    RentalTransaction.objects.create(
                        rental_item=rental_item,
                        transaction_type='return',
                        quantity=issued_qty,
                        performed_by=user,
                        notes=_('Returned issued quantity due to cancellation via admin interface')
                    )
            
            # Update rental request status
            rental_request.status = 'cancelled'
            rental_request.actual_end_date = timezone.now()
            rental_request.save(update_fields=['status', 'actual_end_date'])
            
            return {
                'success': True,
                'message': _('Rental request {rental_id} has been cancelled successfully').format(rental_id=rental_id or '')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def return_items(items_data, user):
        """
        Return selected items (creates RentalTransaction 'return').
        
        Processes item returns and updates rental status when all items
        in a rental request are fully returned.
        
        Args:
            items_data: List of items to return with rental_item_id and quantity
            user: User performing the return
            
        Returns:
            dict: Result with success status
        """
        try:
            from django.shortcuts import get_object_or_404
            
            for entry in items_data:
                rental_item_id = entry['rental_item_id']
                qty = int(entry['quantity'])
                rental_item = get_object_or_404(RentalItem, id=rental_item_id)
                
                RentalService.create_transaction(
                    rental_item=rental_item,
                    transaction_type='return',
                    quantity=qty,
                    performed_by=user,
                )
                
                # Update actual return date when item is fully returned
                ri = RentalItem.objects.get(id=rental_item_id)
                if (ri.quantity_issued or 0) <= (ri.quantity_returned or 0):
                    # Item is fully returned - set actual return date
                    ri.actual_return_date = timezone.now()
                    ri.save(update_fields=['actual_return_date'])
                    
                    req = ri.rental_request
                    # Check if all items in the rental request are returned
                    open_left = any((x.quantity_issued or 0) > (x.quantity_returned or 0) for x in req.items.all())
                    if not open_left:
                        req.status = 'returned'
                        req.actual_end_date = timezone.now()
                        req.save(update_fields=['status', 'actual_end_date'])
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}