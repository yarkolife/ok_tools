"""
Tests for RentalService in rental application.
"""

from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from registration.models import OKUser
from django.conf import settings

from rental.models import (
    RentalRequest, RentalItem, RentalTransaction, EquipmentSet,
    EquipmentSetItem, Room, RoomRental
)
from inventory.models import InventoryItem, Organization, Location
from rental.services.rental_service import RentalService


class RentalServiceTestCase(TestCase):
    """Test cases for RentalService class."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.rental_service = RentalService()
        
        # Create test users
        self.user = OKUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create test organization
        self.organization = Organization.objects.create(
            name='Test Organization'
        )
        
        # Create test location first
        self.location = Location.objects.create(name='Test Location')
        
        # Create test inventory item
        self.inventory_item = InventoryItem.objects.create(
            inventory_number='OK-001',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            location=self.location
        )
        
        # Create test room
        self.room = Room.objects.create(
            name='Test Room',
            capacity=10,
            is_active=True
        )
        
        # Create test rental request
        self.rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now() + timedelta(days=1),
            requested_end_date=timezone.now() + timedelta(days=3),
            rental_type='equipment',
            status='draft'
        )
        
        # Create test rental item
        self.rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2,
            notes='Test notes'
        )
        
        # Create test room rental
        self.room_rental = RoomRental.objects.create(
            rental_request=self.rental_request,
            room=self.room,
            people_count=5,
            notes='Test room notes'
        )
    
    def test_check_user_inventory_access_member(self):
        """Test checking user inventory access for member."""
        # Create a profile for the user
        from registration.models import Profile, MediaAuthority
        media_authority = MediaAuthority.objects.create(name='Test Authority')
        profile = Profile.objects.create(
            okuser=self.user,
            first_name='Test',
            last_name='User',
            member=True,
            media_authority=media_authority
        )
        
        # Create organizations with specific names that match the settings
        state_org = Organization.objects.create(name='MSA')
        org_owner = Organization.objects.create(name='OKMQ')
        other_org = Organization.objects.create(name='Other Org')
        
        # Create inventory items with different owners
        state_item = InventoryItem.objects.create(
            inventory_number='OK-STATE',
            description='State Item',
            quantity=1,
            status='in_stock',
            available_for_rent=True,
            owner=state_org,
            location=self.location
        )
        
        org_item = InventoryItem.objects.create(
            inventory_number='OK-ORG',
            description='Org Item',
            quantity=1,
            status='in_stock',
            available_for_rent=True,
            owner=org_owner,
            location=self.location
        )
        
        other_item = InventoryItem.objects.create(
            inventory_number='OK-OTHER',
            description='Other Item',
            quantity=1,
            status='in_stock',
            available_for_rent=True,
            owner=other_org,
            location=self.location
        )
        
        # Mock settings
        with patch('ok_tools.settings.STATE_MEDIA_INSTITUTION', 'MSA'):
            with patch('ok_tools.settings.ORGANIZATION_OWNER', 'OKMQ'):
                # Test with state institution item
                result = self.rental_service.check_user_inventory_access(self.user, state_item.id)
                self.assertTrue(result)
                
                # Test with organization owner item
                result = self.rental_service.check_user_inventory_access(self.user, org_item.id)
                self.assertTrue(result)
                
                # Test with other organization item
                result = self.rental_service.check_user_inventory_access(self.user, other_item.id)
                self.assertFalse(result)
    
    def test_check_user_inventory_access_non_member(self):
        """Test checking user inventory access for non-member."""
        # Create a profile for the user
        from registration.models import Profile, MediaAuthority
        media_authority = MediaAuthority.objects.create(name='Test Authority')
        profile = Profile.objects.create(
            okuser=self.user,
            first_name='Test',
            last_name='User',
            member=False,
            media_authority=media_authority
        )
        
        # Create organizations with specific names that match the settings
        state_org = Organization.objects.create(name='MSA')
        other_org = Organization.objects.create(name='Other Org')
        
        # Create inventory items with different owners
        state_item = InventoryItem.objects.create(
            inventory_number='OK-STATE-NON',
            description='State Item for Non-member',
            quantity=1,
            status='in_stock',
            available_for_rent=True,
            owner=state_org,
            location=self.location
        )
        
        other_item = InventoryItem.objects.create(
            inventory_number='OK-OTHER-NON',
            description='Other Item for Non-member',
            quantity=1,
            status='in_stock',
            available_for_rent=True,
            owner=other_org,
            location=self.location
        )
        
        # Mock settings
        with patch('ok_tools.settings.STATE_MEDIA_INSTITUTION', 'MSA'):
            # Test with state institution item
            result = self.rental_service.check_user_inventory_access(self.user, state_item.id)
            self.assertTrue(result)
            
            # Test with other organization item
            result = self.rental_service.check_user_inventory_access(self.user, other_item.id)
            self.assertFalse(result)
    
    def test_get_user_available_inventory(self):
        """Test getting available inventory for user."""
        # Create a profile for the user
        from registration.models import Profile, MediaAuthority
        media_authority = MediaAuthority.objects.create(name='Test Authority')
        profile = Profile.objects.create(
            okuser=self.user,
            first_name='Test',
            last_name='User',
            member=True,
            media_authority=media_authority
        )
        
        # Create organizations with specific names that match the settings
        state_org = Organization.objects.create(name='MSA')
        org_owner = Organization.objects.create(name='OKMQ')
        other_org = Organization.objects.create(name='Other Org')
        
        # Create additional inventory items with different owners
        org_item = InventoryItem.objects.create(
            inventory_number='OK-002',
            description='Org Item',
            quantity=3,
            status='in_stock',
            available_for_rent=True,
            owner=org_owner,
            location=self.location
        )
        
        state_item = InventoryItem.objects.create(
            inventory_number='OK-003',
            description='State Item',
            quantity=2,
            status='in_stock',
            available_for_rent=True,
            owner=state_org,
            location=self.location
        )
        
        other_item = InventoryItem.objects.create(
            inventory_number='OK-004',
            description='Other Item',
            quantity=1,
            status='in_stock',
            available_for_rent=True,
            owner=other_org,
            location=self.location
        )
        
        # Mock settings
        with patch('ok_tools.settings.STATE_MEDIA_INSTITUTION', 'MSA'):
            with patch('ok_tools.settings.ORGANIZATION_OWNER', 'OKMQ'):
                # Test with member user
                result = self.rental_service.get_user_available_inventory(self.user)
                # Should include items from MSA and OKMQ organizations, but not from Other Org
                # Original item is not included because its owner is 'Test Organization', not MSA or OKMQ
                self.assertEqual(len(result), 2)  # org_item + state_item
                
                # Test with non-member user
                profile.member = False
                profile.save()
                result = self.rental_service.get_user_available_inventory(self.user)
                # Should only include state institution items (MSA)
                state_items = [item for item in result if item['owner'] == state_org.id]
                self.assertEqual(len(state_items), 1)  # Only the state_item
                
                # Verify that items with None owner are not accessible to non-members
                none_owner_item = InventoryItem.objects.create(
                    inventory_number='OK-005',
                    description='No Owner Item',
                    quantity=1,
                    status='in_stock',
                    available_for_rent=True,
                    owner=None,  # No owner
                    location=self.location
                )
                result = self.rental_service.get_user_available_inventory(self.user)
                # Should still only have 1 item (the state_item), not the none_owner_item
                self.assertEqual(len(result), 1)
                self.assertNotIn(none_owner_item.id, [item['id'] for item in result])
    
    def test_get_available_quantity_for_period(self):
        """Test calculating available quantity for a period."""
        start_date = timezone.now() + timedelta(days=1)
        end_date = timezone.now() + timedelta(days=3)
        
        # Test with no conflicting rentals
        result = self.rental_service.get_available_quantity_for_period(
            self.inventory_item.id, start_date, end_date
        )
        self.assertEqual(result, 5)  # Total quantity
        
        # Create a conflicting rental
        conflicting_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Conflicting Project',
            purpose='Conflicting Purpose',
            requested_start_date=timezone.now() + timedelta(days=2),
            requested_end_date=timezone.now() + timedelta(days=4),
            rental_type='equipment',
            status='reserved'
        )
        
        conflicting_item = RentalItem.objects.create(
            rental_request=conflicting_request,
            inventory_item=self.inventory_item,
            quantity_requested=2
        )
        
        # Test with conflicting reserved rentals
        result = self.rental_service.get_available_quantity_for_period(
            self.inventory_item.id, start_date, end_date
        )
        self.assertEqual(result, 3)  # 5 - 2 = 3
        
        # Test with issued rental (should use quantity_issued, not quantity_requested)
        issued_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Issued Project',
            purpose='Issued Purpose',
            requested_start_date=timezone.now() + timedelta(days=2),
            requested_end_date=timezone.now() + timedelta(days=4),
            rental_type='equipment',
            status='issued'
        )
        
        issued_item = RentalItem.objects.create(
            rental_request=issued_request,
            inventory_item=self.inventory_item,
            quantity_requested=3,
            quantity_issued=1  # Only 1 was actually issued
        )
        
        # Should subtract quantity_issued (1), not quantity_requested (3)
        result = self.rental_service.get_available_quantity_for_period(
            self.inventory_item.id, start_date, end_date
        )
        # Total: 5, reserved: 2, issued: 1 = 5 - 2 - 1 = 2
        self.assertEqual(result, 2)
        
        # Test edge case: quantity_issued > quantity_requested (should use quantity_issued)
        issued_item.quantity_issued = 5  # More than requested
        issued_item.save()
        
        result = self.rental_service.get_available_quantity_for_period(
            self.inventory_item.id, start_date, end_date
        )
        # Total: 5, reserved: 2, issued: 5 = 5 - 2 - 5 = -2, but max(0, -2) = 0
        self.assertEqual(result, 0)
    
    def test_check_room_availability(self):
        """Test checking room availability."""
        start_date = timezone.now() + timedelta(days=1)
        end_date = timezone.now() + timedelta(days=3)
        
        # Test with no conflicting rentals
        result = self.rental_service.check_room_availability(
            self.room, start_date, end_date
        )
        self.assertTrue(result)
        
        # Create a conflicting room rental
        conflicting_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Conflicting Project',
            purpose='Conflicting Purpose',
            requested_start_date=timezone.now() + timedelta(days=2),
            requested_end_date=timezone.now() + timedelta(days=4),
            rental_type='room',
            status='reserved'
        )
        
        RoomRental.objects.create(
            rental_request=conflicting_request,
            room=self.room,
            people_count=5
        )
        
        # Test with conflicting rentals
        result = self.rental_service.check_room_availability(
            self.room, start_date, end_date
        )
        # Should be False due to time overlap
        self.assertFalse(result)
    
    def test_get_available_rooms(self):
        """Test getting available rooms."""
        start_date = timezone.now() + timedelta(days=1)
        end_date = timezone.now() + timedelta(days=3)
        
        # Test with no conflicting rentals
        result = self.rental_service.get_available_rooms(start_date, end_date)
        self.assertIn(self.room, result)
        
        # Create a conflicting room rental that occupies the entire period
        conflicting_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Conflicting Project',
            purpose='Conflicting Purpose',
            requested_start_date=timezone.now() + timedelta(days=1),
            requested_end_date=timezone.now() + timedelta(days=3),
            rental_type='room',
            status='reserved'
        )
        
        RoomRental.objects.create(
            rental_request=conflicting_request,
            room=self.room,
            people_count=5
        )
        
        # Test with conflicting rentals
        result = self.rental_service.get_available_rooms(start_date, end_date)
        self.assertNotIn(self.room, result)
    
    def test_create_rental_request(self):
        """Test creating a rental request."""
        start_date = timezone.now() + timedelta(days=5)
        end_date = timezone.now() + timedelta(days=7)
        
        result = self.rental_service.create_rental_request(
            user=self.user,
            created_by=self.admin_user,
            project_name='New Project',
            purpose='New Purpose',
            start_date=start_date,
            end_date=end_date,
            rental_type='mixed',
            notes='New notes'
        )
        
        # Assertions
        self.assertIsInstance(result, RentalRequest)
        self.assertEqual(result.user, self.user)
        self.assertEqual(result.created_by, self.admin_user)
        self.assertEqual(result.project_name, 'New Project')
        self.assertEqual(result.purpose, 'New Purpose')
        self.assertEqual(result.requested_start_date, start_date)
        self.assertEqual(result.requested_end_date, end_date)
        self.assertEqual(result.rental_type, 'mixed')
        self.assertEqual(result.notes, 'New notes')
        self.assertEqual(result.status, 'draft')
    
    def test_add_items_to_rental_request(self):
        """Test adding items to a rental request."""
        # Create additional inventory item
        inventory_item2 = InventoryItem.objects.create(
            inventory_number='OK-002',
            description='Test Item 2',
            quantity=3,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            location=self.location
        )
        
        items_data = [
            {
                'inventory_item_id': self.inventory_item.id,
                'quantity_requested': 1,
                'notes': 'Item 1 notes'
            },
            {
                'inventory_item_id': inventory_item2.id,
                'quantity_requested': 2,
                'notes': 'Item 2 notes'
            }
        ]
        
        # Mock check_user_inventory_access to always return True
        with patch.object(RentalService, 'check_user_inventory_access', return_value=True):
            # Mock get_available_quantity_for_period to always return sufficient quantity
            with patch.object(RentalService, 'get_available_quantity_for_period', return_value=10):
                result = self.rental_service.add_items_to_rental_request(
                    self.rental_request, items_data
                )
                
                # Assertions
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0].inventory_item, self.inventory_item)
                self.assertEqual(result[0].quantity_requested, 1)
                self.assertEqual(result[0].notes, 'Item 1 notes')
                self.assertEqual(result[1].inventory_item, inventory_item2)
                self.assertEqual(result[1].quantity_requested, 2)
                self.assertEqual(result[1].notes, 'Item 2 notes')
    
    def test_add_rooms_to_rental_request(self):
        """Test adding rooms to a rental request."""
        # Create a new rental request to avoid conflicts
        new_rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='New Test Project',
            purpose='New Test Purpose',
            requested_start_date=timezone.now() + timedelta(days=5),
            requested_end_date=timezone.now() + timedelta(days=7),
            rental_type='room',
            status='draft'
        )
        
        # Create additional room
        room2 = Room.objects.create(
            name='Test Room 2',
            capacity=15,
            is_active=True
        )
        
        rooms_data = [
            {
                'room_id': self.room.id,
                'people_count': 5,
                'notes': 'Room 1 notes'
            },
            {
                'room_id': room2.id,
                'people_count': 10,
                'notes': 'Room 2 notes'
            }
        ]
        
        # Mock check_room_availability to always return True
        with patch.object(RentalService, 'check_room_availability', return_value=True):
            result = self.rental_service.add_rooms_to_rental_request(
                new_rental_request, rooms_data
            )
            
            # Assertions
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].room, self.room)
            self.assertEqual(result[0].people_count, 5)
            self.assertEqual(result[0].notes, 'Room 1 notes')
            self.assertEqual(result[1].room, room2)
            self.assertEqual(result[1].people_count, 10)
            self.assertEqual(result[1].notes, 'Room 2 notes')
    
    def test_create_transaction(self):
        """Test creating a rental transaction."""
        # Test creating a reserve transaction
        transaction = self.rental_service.create_transaction(
            rental_item=self.rental_item,
            transaction_type='reserve',
            quantity=1,
            performed_by=self.admin_user,
            notes='Test reservation'
        )
        
        # Assertions
        self.assertIsInstance(transaction, RentalTransaction)
        self.assertEqual(transaction.rental_item, self.rental_item)
        self.assertEqual(transaction.transaction_type, 'reserve')
        self.assertEqual(transaction.quantity, 1)
        self.assertEqual(transaction.performed_by, self.admin_user)
        self.assertEqual(transaction.notes, 'Test reservation')
        
        # Test creating an issue transaction
        transaction = self.rental_service.create_transaction(
            rental_item=self.rental_item,
            transaction_type='issue',
            quantity=1,
            performed_by=self.admin_user,
            notes='Test issue'
        )
        
        # Assertions
        self.assertIsInstance(transaction, RentalTransaction)
        self.assertEqual(transaction.rental_item, self.rental_item)
        self.assertEqual(transaction.transaction_type, 'issue')
        self.assertEqual(transaction.quantity, 1)
        self.assertEqual(transaction.performed_by, self.admin_user)
        self.assertEqual(transaction.notes, 'Test issue')
        
        # Check that rental item quantity_issued was updated
        updated_rental_item = RentalItem.objects.get(id=self.rental_item.id)
        self.assertEqual(updated_rental_item.quantity_issued, 1)
    
    def test_create_equipment_set(self):
        """Test creating an equipment set."""
        items_data = [
            {
                'inventory_item_id': self.inventory_item.id,
                'quantity': 1,
                'is_required': True,
                'notes': 'Required item'
            }
        ]
        
        result = self.rental_service.create_equipment_set(
            name='Test Set',
            description='Test Description',
            created_by=self.admin_user,
            is_template=False,
            items_data=items_data
        )
        
        # Assertions
        self.assertIsInstance(result, EquipmentSet)
        self.assertEqual(result.name, 'Test Set')
        self.assertEqual(result.description, 'Test Description')
        self.assertEqual(result.created_by, self.admin_user)
        self.assertFalse(result.is_template)
        
        # Check that equipment set items were created
        set_items = EquipmentSetItem.objects.filter(equipment_set=result)
        self.assertEqual(len(set_items), 1)
        self.assertEqual(set_items[0].inventory_item, self.inventory_item)
        self.assertEqual(set_items[0].quantity, 1)
        self.assertTrue(set_items[0].is_required)
        self.assertEqual(set_items[0].notes, 'Required item')
    
    def test_cancel_rental_request(self):
        """Test canceling a rental request."""
        # Create a reservation transaction for the rental item
        RentalTransaction.objects.create(
            rental_item=self.rental_item,
            transaction_type='reserve',
            quantity=2,
            performed_by=self.admin_user,
            notes='Reservation'
        )
        
        # Call the method
        self.rental_service.cancel_rental_request(self.rental_request, self.admin_user)
        
        # Assertions
        updated_request = RentalRequest.objects.get(id=self.rental_request.id)
        self.assertEqual(updated_request.status, 'cancelled')
        
        # Check that a cancel transaction was created
        cancel_transactions = RentalTransaction.objects.filter(
            rental_item=self.rental_item,
            transaction_type='cancel'
        )
        self.assertEqual(len(cancel_transactions), 1)
        self.assertEqual(cancel_transactions[0].quantity, 2)
        self.assertEqual(cancel_transactions[0].performed_by, self.admin_user)
    
    def test_extend_rental(self):
        """Test extending a rental request."""
        new_end_date = self.rental_request.requested_end_date + timedelta(days=2)
        
        # Mock get_available_quantity_for_period to always return sufficient quantity
        with patch.object(RentalService, 'get_available_quantity_for_period', return_value=10):
            # Mock check_room_availability to always return True
            with patch.object(RentalService, 'check_room_availability', return_value=True):
                result = self.rental_service.extend_rental(
                    self.rental_request, new_end_date, self.admin_user
                )
                
                # Assertions
                self.assertTrue(result)
                updated_request = RentalRequest.objects.get(id=self.rental_request.id)
                self.assertEqual(updated_request.requested_end_date, new_end_date)
    
    def test_extend_rental_invalid_date(self):
        """Test extending a rental request with invalid date."""
        # Try to extend with a date before the current end date
        new_end_date = self.rental_request.requested_end_date - timedelta(days=1)
        
        result = self.rental_service.extend_rental(
            self.rental_request, new_end_date, self.admin_user
        )
        
        # Assertions
        self.assertFalse(result)
        # The end date should not have changed
        updated_request = RentalRequest.objects.get(id=self.rental_request.id)
        self.assertEqual(updated_request.requested_end_date, self.rental_request.requested_end_date)
    
    def test_cancel_rental(self):
        """Test canceling a rental via the cancel_rental method."""
        # Mock get_object_or_404 to return our rental request
        with patch('django.shortcuts.get_object_or_404') as mock_get:
            mock_get.return_value = self.rental_request
            
            # Call the method
            result = self.rental_service.cancel_rental(self.rental_request.id, self.admin_user)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('message', result)
            
            # Check that the rental request status was updated
            updated_request = RentalRequest.objects.get(id=self.rental_request.id)
            self.assertEqual(updated_request.status, 'cancelled')
    
    def test_return_items(self):
        """Test returning items."""
        # Create an issue transaction first
        RentalTransaction.objects.create(
            rental_item=self.rental_item,
            transaction_type='issue',
            quantity=2,
            performed_by=self.admin_user,
            notes='Issue'
        )
        
        # Update rental item quantities
        self.rental_item.quantity_issued = 2
        self.rental_item.save()
        
        items_data = [
            {
                'rental_item_id': self.rental_item.id,
                'quantity': 2
            }
        ]
        
        # Mock get_object_or_404 to return our rental item
        with patch('django.shortcuts.get_object_or_404') as mock_get:
            mock_get.return_value = self.rental_item
            
            # Call the method
            result = self.rental_service.return_items(items_data, self.admin_user)
            
            # Assertions
            self.assertTrue(result['success'])
            
            # Check that a return transaction was created
            return_transactions = RentalTransaction.objects.filter(
                rental_item=self.rental_item,
                transaction_type='return'
            )
            self.assertEqual(len(return_transactions), 1)
            self.assertEqual(return_transactions[0].quantity, 2)
            self.assertEqual(return_transactions[0].performed_by, self.admin_user)
            
            # Check that the rental item was updated
            updated_rental_item = RentalItem.objects.get(id=self.rental_item.id)
            self.assertEqual(updated_rental_item.quantity_returned, 2)
            self.assertIsNotNone(updated_rental_item.actual_return_date)
            
            # Check that the rental request status was updated to 'returned'
            updated_request = RentalRequest.objects.get(id=self.rental_request.id)
            self.assertEqual(updated_request.status, 'returned')