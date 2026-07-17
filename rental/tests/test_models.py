"""
Tests for Rental models.
"""
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from registration.models import OKUser, Profile, MediaAuthority
from inventory.models import InventoryItem, Category, Location, Organization, Manufacturer
from rental.models import (
    RentalRequest, RentalItem, RentalTransaction, EquipmentSet, EquipmentSetItem,
    Room, RoomRental, RentalIssue
)


class RentalRequestModelTest(TestCase):
    """Test cases for RentalRequest model."""
    
    def setUp(self):
        """Set up test data."""
        self.media_authority = MediaAuthority.objects.create(name='Test Authority')
        
        self.user = OKUser.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        self.user_profile = Profile.objects.create(
            okuser=self.user,
            first_name='Test',
            last_name='User',
            member=True,
            media_authority=self.media_authority
        )
        
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create organization with names that match the settings
        self.state_institution_org = Organization.objects.create(name='MSA')  # STATE_MEDIA_INSTITUTION
        self.organization_owner_org = Organization.objects.create(name='OKMQ')  # ORGANIZATION_OWNER
        self.organization = self.state_institution_org  # Use state institution organization for tests
        self.manufacturer = Manufacturer.objects.create(name='Test Manufacturer')
        self.category = Category.objects.create(name='Test Category')
        self.location = Location.objects.create(name='Test Location')
        
        self.inventory_item = InventoryItem.objects.create(
            inventory_number='OK-001',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
    
    def test_rental_request_creation(self):
        """Test creating a rental request."""
        start_date = timezone.now() + timedelta(days=1)
        end_date = timezone.now() + timedelta(days=3)
        
        rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=start_date,
            requested_end_date=end_date,
            rental_type='equipment',
            notes='Test notes'
        )
        
        self.assertEqual(rental_request.user, self.user)
        self.assertEqual(rental_request.created_by, self.admin_user)
        self.assertEqual(rental_request.project_name, 'Test Project')
        self.assertEqual(rental_request.purpose, 'Test Purpose')
        self.assertEqual(rental_request.requested_start_date, start_date)
        self.assertEqual(rental_request.requested_end_date, end_date)
        self.assertEqual(rental_request.rental_type, 'equipment')
        self.assertEqual(rental_request.notes, 'Test notes')
        self.assertEqual(rental_request.status, 'draft')
        self.assertIsNotNone(rental_request.created_at)
        self.assertIsNotNone(rental_request.updated_at)
        self.assertEqual(str(rental_request), 'Test Project (user@example.com)')
    
    def test_can_user_access_item_member(self):
        """Test user access rights for member user."""
        rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        # Member should have access to items from organization owner and state institution
        result = rental_request.can_user_access_item(self.inventory_item)
        self.assertTrue(result)
        
        # Test with organization owner
        org_owner_item = InventoryItem.objects.create(
            inventory_number='OK-002',
            description='Org Owner Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization_owner_org,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        result = rental_request.can_user_access_item(org_owner_item)
        self.assertTrue(result)
        
        # Test with different organization (should fail)
        other_org = Organization.objects.create(name='Other Organization')
        other_item = InventoryItem.objects.create(
            inventory_number='OK-003',
            description='Other Org Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=other_org,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        result = rental_request.can_user_access_item(other_item)
        self.assertFalse(result)
    
    def test_can_user_access_item_non_member(self):
        """Test user access rights for non-member user."""
        # Create a non-member user
        non_member_user = OKUser.objects.create_user(
            email='nonmember@example.com',
            password='testpass123'
        )
        Profile.objects.create(
            okuser=non_member_user,
            first_name='Non-Member',
            last_name='User',
            member=False,
            media_authority=self.media_authority
        )
        
        rental_request = RentalRequest.objects.create(
            user=non_member_user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        # Non-member should only have access to items from state institution
        result = rental_request.can_user_access_item(self.inventory_item)
        self.assertTrue(result)  # Should have access to state institution item
        
        # Test with organization owner (should fail for non-member)
        org_owner_item = InventoryItem.objects.create(
            inventory_number='OK-004',
            description='Org Owner Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization_owner_org,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        result = rental_request.can_user_access_item(org_owner_item)
        self.assertFalse(result)  # Non-member should not have access to organization owner item
        
        # Test with different organization (should fail)
        other_org = Organization.objects.create(name='Other Organization')
        other_item = InventoryItem.objects.create(
            inventory_number='OK-005',
            description='Other Org Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=other_org,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        result = rental_request.can_user_access_item(other_item)
        self.assertFalse(result)  # Non-member should not have access to other organization items
    
    def test_total_items_count(self):
        """Test total_items_count property."""
        rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        # Add rental items
        RentalItem.objects.create(
            rental_request=rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2
        )
        
        RentalItem.objects.create(
            rental_request=rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=3
        )
        
        # Note: The total_items_count property uses Sum which would aggregate across all items
        # Since our implementation sums quantity_requested, we expect 2+3=5
        self.assertEqual(rental_request.total_items_count, 5)
    
    def test_rental_request_status_choices(self):
        """Test rental request status choices."""
        rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        # Test different statuses
        statuses = ['draft', 'reserved', 'issued', 'returned', 'cancelled']
        for status in statuses:
            rental_request.status = status
            rental_request.save()
            self.assertEqual(rental_request.status, status)


class RentalItemModelTest(TestCase):
    """Test cases for RentalItem model."""
    
    def setUp(self):
        """Set up test data."""
        self.media_authority = MediaAuthority.objects.create(name='Test Authority')
        
        self.user = OKUser.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        self.user_profile = Profile.objects.create(
            okuser=self.user,
            first_name='Test',
            last_name='User',
            member=True,
            media_authority=self.media_authority
        )
        
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.organization = Organization.objects.create(name='Test Organization')
        self.manufacturer = Manufacturer.objects.create(name='Test Manufacturer')
        self.category = Category.objects.create(name='Test Category')
        self.location = Location.objects.create(name='Test Location')
        
        self.inventory_item = InventoryItem.objects.create(
            inventory_number='OK-001',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        
        self.rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
    
    def test_rental_item_creation(self):
        """Test creating a rental item."""
        rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2,
            quantity_issued=1,
            quantity_returned=0,
            notes='Test notes'
        )
        
        self.assertEqual(rental_item.rental_request, self.rental_request)
        self.assertEqual(rental_item.inventory_item, self.inventory_item)
        self.assertEqual(rental_item.quantity_requested, 2)
        self.assertEqual(rental_item.quantity_issued, 1)
        self.assertEqual(rental_item.quantity_returned, 0)
        self.assertEqual(rental_item.notes, 'Test notes')
        self.assertEqual(str(rental_item), 'Test Item [OK-001] x2')
    
    def test_outstanding_to_issue(self):
        """Test outstanding_to_issue property."""
        rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=5,
            quantity_issued=2
        )
        
        self.assertEqual(rental_item.outstanding_to_issue, 3)  # 5 - 2 = 3
    
    def test_outstanding_to_return(self):
        """Test outstanding_to_return property."""
        rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=5,
            quantity_issued=3,
            quantity_returned=1
        )
        
        self.assertEqual(rental_item.outstanding_to_return, 2)  # 3 - 1 = 2
    
    def test_is_overdue_not_returned(self):
        """Test is_overdue property for not yet returned items."""
        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=1)
        
        rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2
        )
        
        # Update the rental request end date to be in the past
        self.rental_request.requested_end_date = past_date
        self.rental_request.save()
        
        self.assertTrue(rental_item.is_overdue)
        
        # Update end date to be in the future
        self.rental_request.requested_end_date = future_date
        self.rental_request.save()
        
        self.assertFalse(rental_item.is_overdue)
    
    def test_is_overdue_already_returned(self):
        """Test is_overdue property for already returned items."""
        past_due_date = timezone.now() - timedelta(days=2)
        return_date = timezone.now() - timedelta(days=1)  # After due date
        
        rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=past_due_date,  # Past due date
        )
        
        rental_item = RentalItem.objects.create(
            rental_request=rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2,
            actual_return_date=return_date  # Returned after due date
        )
        
        self.assertTrue(rental_item.is_overdue)
        
        # Test with return before due date
        early_return_date = timezone.now() - timedelta(days=3)  # Before due date
        rental_item.actual_return_date = early_return_date
        rental_item.save()
        
        self.assertFalse(rental_item.is_overdue)


class EquipmentSetModelTest(TestCase):
    """Test cases for EquipmentSet model."""
    
    def setUp(self):
        """Set up test data."""
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
    
    def test_equipment_set_creation(self):
        """Test creating an equipment set."""
        equipment_set = EquipmentSet.objects.create(
            name='Test Set',
            description='Test Description',
            is_template=False,
            created_by=self.admin_user,
            is_active=True
        )
        
        self.assertEqual(equipment_set.name, 'Test Set')
        self.assertEqual(equipment_set.description, 'Test Description')
        self.assertFalse(equipment_set.is_template)
        self.assertEqual(equipment_set.created_by, self.admin_user)
        self.assertTrue(equipment_set.is_active)
        self.assertIsNotNone(equipment_set.created_at)
        self.assertEqual(str(equipment_set), 'Test Set')
    
    def test_equipment_set_item_creation(self):
        """Test creating an equipment set item."""
        equipment_set = EquipmentSet.objects.create(
            name='Test Set',
            created_by=self.admin_user
        )
        
        # Create inventory item for the test
        organization = Organization.objects.create(name='Test Organization')
        manufacturer = Manufacturer.objects.create(name='Test Manufacturer')
        category = Category.objects.create(name='Test Category')
        location = Location.objects.create(name='Test Location')
        
        inventory_item = InventoryItem.objects.create(
            inventory_number='OK-001',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=organization,
            manufacturer=manufacturer,
            category=category,
            location=location
        )
        
        equipment_set_item = EquipmentSetItem.objects.create(
            equipment_set=equipment_set,
            inventory_item=inventory_item,
            quantity=2,
            is_required=True,
            notes='Test notes'
        )
        
        self.assertEqual(equipment_set_item.equipment_set, equipment_set)
        self.assertEqual(equipment_set_item.inventory_item, inventory_item)
        self.assertEqual(equipment_set_item.quantity, 2)
        self.assertTrue(equipment_set_item.is_required)
        self.assertEqual(equipment_set_item.notes, 'Test notes')
        self.assertEqual(str(equipment_set_item), 'Test Set: Test Item [OK-001] x2')


class RentalTransactionModelTest(TestCase):
    """Test cases for RentalTransaction model."""
    
    def setUp(self):
        """Set up test data."""
        self.media_authority = MediaAuthority.objects.create(name='Test Authority')
        
        self.user = OKUser.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.organization = Organization.objects.create(name='Test Organization')
        self.manufacturer = Manufacturer.objects.create(name='Test Manufacturer')
        self.category = Category.objects.create(name='Test Category')
        self.location = Location.objects.create(name='Test Location')
        
        self.inventory_item = InventoryItem.objects.create(
            inventory_number='OK-01',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        
        self.rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        self.rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2
        )
        
        self.room = Room.objects.create(
            name='Test Room',
            capacity=10,
            is_active=True
        )
    
    def test_rental_transaction_creation_with_item(self):
        """Test creating a rental transaction with an item."""
        transaction = RentalTransaction.objects.create(
            rental_item=self.rental_item,
            transaction_type='issue',
            quantity=1,
            performed_by=self.admin_user,
            condition='good',
            notes='Test transaction'
        )
        
        self.assertEqual(transaction.rental_item, self.rental_item)
        self.assertIsNone(transaction.room)
        self.assertEqual(transaction.transaction_type, 'issue')
        self.assertEqual(transaction.quantity, 1)
        self.assertEqual(transaction.performed_by, self.admin_user)
        self.assertEqual(transaction.condition, 'good')
        self.assertEqual(transaction.notes, 'Test transaction')
        self.assertIsNotNone(transaction.performed_at)
        # Account for localization - German strings
        expected_values = ['Issue 1 → Test Item [OK-01] x2', 'Ausgeben 1 → Test Item [OK-01] x2']
        self.assertIn(str(transaction), expected_values)
    
    def test_rental_transaction_creation_with_room(self):
        """Test creating a rental transaction with a room."""
        transaction = RentalTransaction.objects.create(
            room=self.room,
            transaction_type='reserve',
            quantity=1,
            performed_by=self.admin_user,
            condition='excellent',
            notes='Room reservation'
        )
        
        self.assertIsNone(transaction.rental_item)
        self.assertEqual(transaction.room, self.room)
        self.assertEqual(transaction.transaction_type, 'reserve')
        self.assertEqual(transaction.quantity, 1)
        self.assertEqual(transaction.performed_by, self.admin_user)
        self.assertEqual(transaction.condition, 'excellent')
        self.assertEqual(transaction.notes, 'Room reservation')
        self.assertIsNotNone(transaction.performed_at)
        # Account for localization - German strings
        expected_values = ['Reserve 1 → Test Room', 'Reservieren 1 → Test Room']
        self.assertIn(str(transaction), expected_values)
    
    def test_transaction_type_choices(self):
        """Test transaction type choices."""
        transaction = RentalTransaction.objects.create(
            rental_item=self.rental_item,
            transaction_type='issue',
            quantity=1,
            performed_by=self.admin_user
        )
        
        # Test different transaction types
        types = ['reserve', 'issue', 'return', 'cancel']
        for trans_type in types:
            transaction.transaction_type = trans_type
            transaction.save()
            self.assertEqual(transaction.transaction_type, trans_type)
    
    def test_condition_choices(self):
        """Test condition choices."""
        transaction = RentalTransaction.objects.create(
            rental_item=self.rental_item,
            transaction_type='issue',
            quantity=1,
            performed_by=self.admin_user
        )
        
        # Test different conditions
        conditions = ['excellent', 'good', 'fair', 'poor']
        for condition in conditions:
            transaction.condition = condition
            transaction.save()
            self.assertEqual(transaction.condition, condition)
    
    def test_transaction_clean_method(self):
        """Test clean method validation."""
        # Should raise ValidationError if neither rental_item nor room is specified
        with self.assertRaises(Exception):  # Django ValidationError is a subclass of Exception
            transaction = RentalTransaction(
                transaction_type='issue',
                quantity=1,
                performed_by=self.admin_user
            )
            transaction.full_clean()  # This will call clean() method
        
        # Should raise ValidationError if both rental_item and room are specified
        with self.assertRaises(Exception):  # Django ValidationError is a subclass of Exception
            transaction = RentalTransaction(
                rental_item=self.rental_item,
                room=self.room,
                transaction_type='issue',
                quantity=1,
                performed_by=self.admin_user
            )
            transaction.full_clean()  # This will call clean() method


class RoomModelTest(TestCase):
    """Test cases for Room model."""
    
    def test_room_creation(self):
        """Test creating a room."""
        room = Room.objects.create(
            name='Conference Room A',
            description='Main conference room',
            capacity=20,
            location='Building A, Floor 2',
            is_active=True
        )
        
        self.assertEqual(room.name, 'Conference Room A')
        self.assertEqual(room.description, 'Main conference room')
        self.assertEqual(room.capacity, 20)
        self.assertEqual(room.location, 'Building A, Floor 2')
        self.assertTrue(room.is_active)
        self.assertEqual(str(room), 'Conference Room A')
    
    def test_room_availability_check(self):
        """Test room availability check."""
        room = Room.objects.create(
            name='Test Room',
            capacity=10,
            is_active=True
        )
        
        # Test with future dates (should be available)
        start_date = timezone.now() + timedelta(days=1)
        end_date = timezone.now() + timedelta(days=2)
        
        is_available = room.is_available_for_time(start_date, end_date)
        self.assertTrue(is_available)
    
    def test_inactive_room_availability(self):
        """Test that inactive rooms are not available."""
        room = Room.objects.create(
            name='Inactive Room',
            capacity=10,
            is_active=False
        )
        
        start_date = timezone.now() + timedelta(days=1)
        end_date = timezone.now() + timedelta(days=2)
        
        is_available = room.is_available_for_time(start_date, end_date)
        self.assertFalse(is_available)


class RoomRentalModelTest(TestCase):
    """Test cases for RoomRental model."""
    
    def setUp(self):
        """Set up test data."""
        self.media_authority = MediaAuthority.objects.create(name='Test Authority')
        
        self.user = OKUser.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        self.room = Room.objects.create(
            name='Test Room',
            capacity=10,
            is_active=True
        )
    
    def test_room_rental_creation(self):
        """Test creating a room rental."""
        room_rental = RoomRental.objects.create(
            rental_request=self.rental_request,
            room=self.room,
            people_count=5,
            notes='Test notes'
        )
        
        self.assertEqual(room_rental.rental_request, self.rental_request)
        self.assertEqual(room_rental.room, self.room)
        self.assertEqual(room_rental.people_count, 5)
        self.assertEqual(room_rental.notes, 'Test notes')
        self.assertEqual(str(room_rental), 'Test Room - Test Project')
    
    def test_room_rental_status(self):
        """Test room rental status properties."""
        # Create a rental with end date in the past
        past_end_date = timezone.now() - timedelta(hours=1)
        rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Past Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now() - timedelta(days=1),
            requested_end_date=past_end_date,
        )
        
        room_rental = RoomRental.objects.create(
            rental_request=rental_request,
            room=self.room,
            people_count=5
        )
        
        # Should be expired
        self.assertTrue(room_rental.is_expired)
        self.assertEqual(room_rental.time_until_expiry, 0)
        # Account for localization - German strings
        expected_values = ['Expired', 'Abgelaufen']
        self.assertIn(room_rental.status_display, expected_values)


class RentalIssueModelTest(TestCase):
    """Test cases for RentalIssue model."""
    
    def setUp(self):
        """Set up test data."""
        self.media_authority = MediaAuthority.objects.create(name='Test Authority')
        
        self.user = OKUser.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        self.admin_user = OKUser.objects.create_user(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.organization = Organization.objects.create(name='Test Organization')
        self.manufacturer = Manufacturer.objects.create(name='Test Manufacturer')
        self.category = Category.objects.create(name='Test Category')
        self.location = Location.objects.create(name='Test Location')
        
        self.inventory_item = InventoryItem.objects.create(
            inventory_number='OK-01',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            manufacturer=self.manufacturer,
            category=self.category,
            location=self.location
        )
        
        self.rental_request = RentalRequest.objects.create(
            user=self.user,
            created_by=self.admin_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now(),
        )
        
        self.rental_item = RentalItem.objects.create(
            rental_request=self.rental_request,
            inventory_item=self.inventory_item,
            quantity_requested=2
        )
    
    def test_rental_issue_creation(self):
        """Test creating a rental issue."""
        issue = RentalIssue.objects.create(
            rental_item=self.rental_item,
            issue_type='damaged',
            description='Item was damaged during use',
            severity='major',
            reported_by=self.admin_user,
            resolution_notes='Repaired item'
        )
        
        self.assertEqual(issue.rental_item, self.rental_item)
        self.assertEqual(issue.issue_type, 'damaged')
        self.assertEqual(issue.description, 'Item was damaged during use')
        self.assertEqual(issue.severity, 'major')
        self.assertEqual(issue.reported_by, self.admin_user)
        self.assertFalse(issue.resolved)
        self.assertEqual(issue.resolution_notes, 'Repaired item')
        self.assertIsNotNone(issue.reported_at)
        # Account for localization - German strings
        self.assertTrue('Damaged' in str(issue) or 'Beschädigt' in str(issue))
        self.assertTrue('Major' in str(issue) or 'Schwerwiegend' in str(issue))
    
    def test_issue_type_choices(self):
        """Test issue type choices."""
        issue = RentalIssue.objects.create(
            rental_item=self.rental_item,
            issue_type='damaged',
            description='Test',
            severity='minor',
            reported_by=self.admin_user
        )
        
        # Test different issue types
        types = ['damaged', 'missing', 'late_return', 'other']
        for issue_type in types:
            issue.issue_type = issue_type
            issue.save()
            self.assertEqual(issue.issue_type, issue_type)
    
    def test_severity_choices(self):
        """Test severity choices."""
        issue = RentalIssue.objects.create(
            rental_item=self.rental_item,
            issue_type='damaged',
            description='Test',
            severity='minor',
            reported_by=self.admin_user
        )
        
        # Test different severities
        severities = ['minor', 'major', 'critical']
        for severity in severities:
            issue.severity = severity
            issue.save()
            self.assertEqual(issue.severity, severity)