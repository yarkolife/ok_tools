"""
Django signals for rental application.

This module contains signal handlers that automatically respond to model changes
in the rental system: audit logging and the issued/returned quantities of rental items.
"""

from .models import RentalItem
from .models import RentalRequest
from .models import RentalTransaction
from .models import RoomRental
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from inventory.models import AuditLog
import logging

logger = logging.getLogger('django')


@receiver(post_save, sender=RentalRequest)
def log_rental_request_changes(sender, instance: RentalRequest, created, **kwargs):
    """
    Log rental request changes to AuditLog.

    Writes to general AuditLog with model_name="RentalRequest".
    If created — action="created"; otherwise records changed fields.

    Args:
        sender: The model class that sent the signal
        instance: The RentalRequest instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    action = "created" if created else "updated"
    changes = None
    if not created and hasattr(instance, '_original_state'):
        changes = {}
        for field in instance._meta.fields:
            # Use attname to avoid RelatedObjectDoesNotExist on empty FK
            attr_name = getattr(field, 'attname', field.name)
            old_value = getattr(instance._original_state, field.name, None)
            new_value = getattr(instance, attr_name, None)
            if old_value != new_value:
                if hasattr(old_value, '__str__'):
                    old_value = str(old_value)
                if hasattr(new_value, '__str__'):
                    new_value = str(new_value)
                changes[field.name] = {'old': old_value, 'new': new_value}
        if not changes:
            changes = None

    from registration.models import OKUser
    AuditLog.objects.create(
        model_name="RentalRequest",
        object_id=str(instance.pk),
        action=action,
        changes=changes,
        user=instance.created_by if hasattr(instance, 'created_by') and instance.created_by else None
    )


@receiver(post_save, sender=RentalTransaction)
def update_inventory_quantities(sender, instance: RentalTransaction, created, **kwargs):
    """
    Count issued and returned quantities on the rental item.

    Args:
        sender: The model class that sent the signal
        instance: The RentalTransaction instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if not created:
        return

    # Skip room transactions (they don't have rental_item)
    if not instance.rental_item:
        return

    rental_item = instance.rental_item
    qty = int(instance.quantity or 0)
    user_id = instance.performed_by.id if instance.performed_by else None
    
    if not user_id:
        # If no user is specified, we can't perform the operation
        return

    if instance.transaction_type == 'issue':
        rental_item.quantity_issued = (rental_item.quantity_issued or 0) + qty
        rental_item.save(update_fields=['quantity_issued'])
    elif instance.transaction_type == 'return':
        rental_item.quantity_returned = (rental_item.quantity_returned or 0) + qty
        rental_item.save(update_fields=['quantity_returned'])

    # The inventory events (handle_rental_*_event) are no longer sent: they
    # moved reserved_quantity/rented_quantity of the item, but rentals have
    # not created 'reserve' transactions since 2025, so every issue and
    # return was reported as failed and changed nothing. What is out and
    # back is counted on the rental item above; availability per period is
    # checked from the rental items.


@receiver(post_save, sender=RoomRental)
def sync_room_rental_to_nextcloud(sender, instance: RoomRental, created, **kwargs):
    """
    Sync room rental to Nextcloud Calendar when created or updated.
    
    Only syncs if:
    - Nextcloud Calendar integration is enabled
    - Rental request status is 'reserved' or 'issued'
    
    Args:
        sender: The model class that sent the signal
        instance: The RoomRental instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    
    enabled = getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False)
    
    if not enabled:
        return
    
    # Only sync confirmed bookings
    status = instance.rental_request.status if hasattr(instance, 'rental_request') else None
    
    if status not in ['reserved', 'issued']:
        return
    
    try:
        from .services.nextcloud_calendar_service import NextcloudCalendarService
        service = NextcloudCalendarService()
        # Sync the entire rental request (which handles all rooms in one event)
        event_href = service.sync_room_rental_to_calendar(instance)
        
        # The sync_room_rental_to_calendar method now handles updating all room rentals in the request
        
    except Exception as e:
        # Log error but don't fail the save operation
        logger.error(f'Error syncing room rental {instance.id} to Nextcloud: {e}', exc_info=True)


@receiver(post_save, sender=RentalRequest)
def sync_rental_request_rooms_to_nextcloud(sender, instance: RentalRequest, created, **kwargs):
    """
    Sync all room rentals in a rental request to Nextcloud when status changes.
    
    This handles cases where the rental request status changes (e.g., from draft to reserved),
    which should trigger sync for all associated room rentals.
    
    Args:
        sender: The model class that sent the signal
        instance: The RentalRequest instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    
    if not getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False):
        return
    
    # Check if status changed to reserved/issued or from reserved/issued
    old_status = None
    if hasattr(instance, '_original_state'):
        old_status = getattr(instance._original_state, 'status', None)
    new_status = instance.status
    
    
    # Determine if we need to sync or delete
    # Check if any room rentals have events (to detect status changes even if _original_state is missing)
    has_events = any(rr.nextcloud_event_href for rr in instance.room_rentals.all())
    
    if old_status is not None:
        # Status changed - use old_status
        if old_status == new_status:
            return
        
        should_sync = (
            new_status in ['reserved', 'issued'] or
            (old_status in ['reserved', 'issued'] and new_status not in ['reserved', 'issued'])
        )
        
        
        if not should_sync:
            return
    elif new_status not in ['reserved', 'issued']:
        # New request with non-sync status, but check if events exist (shouldn't happen, but handle it)
        if has_events:
            # Status is not sync-able but events exist - delete them below.
            # This handles cases where _original_state was not preserved
            pass
        else:
            return
    else:
        # New request with sync status - will sync below
        pass
    
    try:
        from .services.nextcloud_calendar_service import NextcloudCalendarService
        service = NextcloudCalendarService()
        
        # Sync all room rentals
        room_rentals = list(instance.room_rentals.all())
        
        for room_rental in room_rentals:
            if new_status in ['reserved', 'issued']:
                event_href = service.sync_room_rental_to_calendar(room_rental)
                if event_href and room_rental.nextcloud_event_href != event_href:
                    RoomRental.objects.filter(pk=room_rental.pk).update(nextcloud_event_href=event_href)
            else:
                # Status changed away from reserved/issued, delete events
                # Also delete if event exists but status is not sync-able (handles missing _original_state)
                if room_rental.nextcloud_event_href:
                    deleted = service.delete_room_rental_event(room_rental)
                    RoomRental.objects.filter(pk=room_rental.pk).update(nextcloud_event_href=None)
    except Exception as e:
        # Log error but don't fail the save operation
        logger.error(f'Error syncing rental request {instance.id} rooms to Nextcloud: {e}', exc_info=True)


@receiver(post_delete, sender=RoomRental)
def delete_room_rental_from_nextcloud(sender, instance: RoomRental, **kwargs):
    """
    Delete room rental event from Nextcloud Calendar when room rental is deleted.
    
    Args:
        sender: The model class that sent the signal
        instance: The RoomRental instance being deleted
        **kwargs: Additional keyword arguments
    """
    if not getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False):
        return
    
    # Check if there are other room rentals in the same request
    # If this is the last room rental in the request, delete the shared event
    remaining_room_rentals = instance.rental_request.room_rentals.exclude(id=instance.id).count()
    
    if remaining_room_rentals == 0:
        # This is the last room rental in the request, so delete the shared event
        try:
            from .services.nextcloud_calendar_service import NextcloudCalendarService
            service = NextcloudCalendarService()
            service.delete_room_rental_event(instance)
        except Exception as e:
            # Log error but don't fail the delete operation
            logger.error(f'Error deleting room rental {instance.id} from Nextcloud: {e}', exc_info=True)
    else:
        # There are other room rentals in this request, so we need to resync to update the event without this room
        try:
            from .services.nextcloud_calendar_service import NextcloudCalendarService
            service = NextcloudCalendarService()
            # Resync the rental request to update the event without the deleted room
            if instance.rental_request.status in ['reserved', 'issued']:
                service._sync_rental_request_to_calendar(instance.rental_request)
        except Exception as e:
            # Log error but don't fail the delete operation
            logger.error(f'Error resyncing rental request {instance.rental_request.id} after room rental deletion: {e}', exc_info=True)
