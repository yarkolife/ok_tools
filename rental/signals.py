"""
Django signals for rental application.

This module contains signal handlers that automatically respond to model changes
in the rental system. It handles audit logging and triggers inventory quantity updates
through asynchronous events.
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
    Trigger inventory quantity updates through asynchronous events.

    - reserve: increases reserved_quantity
    - issue: decreases reserved_quantity and increases rented_quantity
    - return: decreases rented_quantity
    - cancel: decreases reserved_quantity

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
    item_id = rental_item.inventory_item_id
    qty = int(instance.quantity or 0)
    user_id = instance.performed_by.id if instance.performed_by else None
    
    if not user_id:
        # If no user is specified, we can't perform the operation
        return

    # Import the inventory events
    from inventory.events import (
        handle_rental_created_event,
        handle_rental_issued_event,
        handle_rental_returned_event,
        handle_rental_cancelled_event
    )

    # Check if we're running tests to avoid Celery connection issues
    import sys
    if 'pytest' in sys.modules or 'test' in sys.argv or 'migrate' in sys.argv:
        # Skip Celery tasks during tests
        pass
    else:
        # Trigger asynchronous events based on transaction type
        if instance.transaction_type == 'reserve':
            handle_rental_created_event.delay(item_id, qty, user_id)
        elif instance.transaction_type == 'issue':
            handle_rental_issued_event.delay(item_id, qty, user_id)
            # Update rental item quantities locally
            rental_item.quantity_issued = (rental_item.quantity_issued or 0) + qty
            rental_item.save(update_fields=['quantity_issued'])
        elif instance.transaction_type == 'return':
            handle_rental_returned_event.delay(item_id, qty, user_id)
            # Update rental item quantities locally
            rental_item.quantity_returned = (rental_item.quantity_returned or 0) + qty
            rental_item.save(update_fields=['quantity_returned'])
        elif instance.transaction_type == 'cancel':
            handle_rental_cancelled_event.delay(item_id, qty, user_id)


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
    # #region agent log
    import json
    import os
    try:
        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"rental/signals.py:129","message":"Signal sync_room_rental_to_nextcloud called","data":{"room_rental_id":instance.id if instance.id else None,"created":created,"rental_request_id":instance.rental_request.id if hasattr(instance, 'rental_request') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    
    enabled = getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False)
    # #region agent log
    try:
        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"rental/signals.py:144","message":"NEXTCLOUD_CALENDAR_ENABLED check","data":{"enabled":enabled},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    
    if not enabled:
        return
    
    # Only sync confirmed bookings
    status = instance.rental_request.status if hasattr(instance, 'rental_request') else None
    # #region agent log
    try:
        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"rental/signals.py:149","message":"Rental request status check","data":{"status":status,"should_sync":status in ['reserved', 'issued']},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    
    if status not in ['reserved', 'issued']:
        return
    
    try:
        from .services.nextcloud_calendar_service import NextcloudCalendarService
        service = NextcloudCalendarService()
        # Sync the entire rental request (which handles all rooms in one event)
        event_href = service.sync_room_rental_to_calendar(instance)
        
        # The sync_room_rental_to_calendar method now handles updating all room rentals in the request
        # #region agent log
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"rental/signals.py:160","message":"sync_room_rental_to_calendar result","data":{"event_href":event_href,"rental_request_id":instance.rental_request.id if hasattr(instance, 'rental_request') else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
    except Exception as e:
        # Log error but don't fail the save operation
        logger.error(f'Error syncing room rental {instance.id} to Nextcloud: {e}', exc_info=True)
        # #region agent log
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rental/signals.py:172","message":"Exception in sync_room_rental_to_nextcloud","data":{"error":str(e),"room_rental_id":instance.id if instance.id else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion


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
    # #region agent log
    import json
    try:
        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"rental/signals.py:210","message":"Signal sync_rental_request_rooms_to_nextcloud called","data":{"rental_request_id":instance.id if instance.id else None,"created":created,"status":instance.status},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    
    if not getattr(settings, 'NEXTCLOUD_CALENDAR_ENABLED', False):
        return
    
    # Check if status changed to reserved/issued or from reserved/issued
    old_status = None
    if hasattr(instance, '_original_state'):
        old_status = getattr(instance._original_state, 'status', None)
    new_status = instance.status
    
    # #region agent log
    try:
        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H","location":"rental/signals.py:228","message":"Status change check","data":{"old_status":old_status,"new_status":new_status,"status_changed":old_status != new_status},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    
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
        
        # #region agent log
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H","location":"rental/signals.py:250","message":"Should sync check (status changed)","data":{"should_sync":should_sync,"old_in_sync":old_status in ['reserved', 'issued'] if old_status else False,"new_in_sync":new_status in ['reserved', 'issued']},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        if not should_sync:
            return
    elif new_status not in ['reserved', 'issued']:
        # New request with non-sync status, but check if events exist (shouldn't happen, but handle it)
        if has_events:
            # #region agent log
            try:
                with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"K","location":"rental/signals.py:262","message":"Non-sync status but events exist - will delete","data":{"status":new_status,"has_events":has_events},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            # Status is not sync-able but events exist - delete them
            # This handles cases where _original_state was not preserved
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
        # #region agent log
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"rental/signals.py:255","message":"Processing room rentals","data":{"count":len(room_rentals),"status":new_status,"will_sync":new_status in ['reserved', 'issued'],"will_delete":new_status not in ['reserved', 'issued']},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        for room_rental in room_rentals:
            if new_status in ['reserved', 'issued']:
                # #region agent log
                try:
                    with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"rental/signals.py:280","message":"Syncing room rental","data":{"room_rental_id":room_rental.id,"room_name":room_rental.room.name,"status":new_status},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                event_href = service.sync_room_rental_to_calendar(room_rental)
                if event_href and room_rental.nextcloud_event_href != event_href:
                    RoomRental.objects.filter(pk=room_rental.pk).update(nextcloud_event_href=event_href)
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"I","location":"rental/signals.py:286","message":"Updated event href","data":{"room_rental_id":room_rental.id,"event_href":event_href},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
            else:
                # Status changed away from reserved/issued, delete events
                # Also delete if event exists but status is not sync-able (handles missing _original_state)
                if room_rental.nextcloud_event_href:
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/signals.py:293","message":"Deleting room rental event","data":{"room_rental_id":room_rental.id,"current_href":room_rental.nextcloud_event_href,"status":new_status},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    deleted = service.delete_room_rental_event(room_rental)
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/signals.py:297","message":"Delete result","data":{"room_rental_id":room_rental.id,"deleted":deleted},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    RoomRental.objects.filter(pk=room_rental.pk).update(nextcloud_event_href=None)
                    # #region agent log
                    try:
                        with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"rental/signals.py:301","message":"Cleared event href in DB","data":{"room_rental_id":room_rental.id},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
    except Exception as e:
        # Log error but don't fail the save operation
        logger.error(f'Error syncing rental request {instance.id} rooms to Nextcloud: {e}', exc_info=True)
        # #region agent log
        try:
            with open('/Users/pavlo/coding/ok_tools_v3/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rental/signals.py:285","message":"Exception in sync_rental_request_rooms_to_nextcloud","data":{"error":str(e),"rental_request_id":instance.id if instance.id else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion


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
