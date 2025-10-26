from django.core.management import call_command
from django.test import TestCase
from io import StringIO
from unittest.mock import patch
from rental.models import RoomRental, RentalRequest, RentalTransaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging


class ExpireRoomRentalsCommandTest(TestCase):
    """Unit tests for expire_room_rentals management command."""

    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin'
        )

        # Create a test room
        from rental.models import Room
        self.room = Room.objects.create(
            name='Test Room',
            description='A test room',
            capacity=10
        )

        # Create rental requests with different statuses and dates
        self.now = timezone.now()
        
        # Create a reserved rental that has expired
        self.expired_reservation_request = RentalRequest.objects.create(
            project_name='Expired Reservation',
            status='reserved',
            requested_start_date=self.now - timedelta(days=2),
            requested_end_date=self.now - timedelta(hours=1)
        )
        self.expired_reservation = RoomRental.objects.create(
            room=self.room,
            rental_request=self.expired_reservation_request
        )

        # Create an issued rental that has expired
        self.expired_issued_request = RentalRequest.objects.create(
            project_name='Expired Issued Rental',
            status='issued',
            requested_start_date=self.now - timedelta(days=2),
            requested_end_date=self.now - timedelta(hours=1)
        )
        self.expired_issued_rental = RoomRental.objects.create(
            room=self.room,
            rental_request=self.expired_issued_request
        )

        # Create a current reservation that has not expired
        self.current_reservation_request = RentalRequest.objects.create(
            project_name='Current Reservation',
            status='reserved',
            requested_start_date=self.now + timedelta(days=1),
            requested_end_date=self.now + timedelta(days=2)
        )
        self.current_reservation = RoomRental.objects.create(
            room=self.room,
            rental_request=self.current_reservation_request
        )

    @patch('django.utils.timezone.now')
    def test_command_expires_reserved_rentals(self, mock_now):
        """Test that command expires reserved rentals that have passed their end date."""
        mock_now.return_value = self.now

        # Run the command
        out = StringIO()
        call_command('expire_room_rentals', stdout=out)

        # Refresh from database
        self.expired_reservation_request.refresh_from_db()
        self.expired_issued_request.refresh_from_db()
        self.current_reservation_request.refresh_from_db()

        # Verify that expired reservations are marked as returned
        self.assertEqual(self.expired_reservation_request.status, 'returned')
        self.assertIsNotNone(self.expired_reservation_request.actual_end_date)

        # Verify that expired issued rentals are marked as returned
        self.assertEqual(self.expired_issued_request.status, 'returned')
        self.assertIsNotNone(self.expired_issued_request.actual_end_date)

        # Verify that current reservations remain unchanged
        self.assertEqual(self.current_reservation_request.status, 'reserved')

        # Verify that return transactions were created
        return_transactions = RentalTransaction.objects.filter(transaction_type='return')
        self.assertEqual(return_transactions.count(), 2)  # One for each expired rental

        # Verify output contains success messages
        output = out.getvalue()
        self.assertIn('Found 2 expired room rentals', output)
        self.assertIn('1 expired room reservations (will be auto-returned)', output)
        self.assertIn('1 expired room rentals (will be returned)', output)
        self.assertIn('Successfully processed 2 expired room rentals', output)

    @patch('django.utils.timezone.now')
    def test_command_with_dry_run(self, mock_now):
        """Test that command with dry-run doesn't make changes."""
        mock_now.return_value = self.now

        # Run the command with dry-run
        out = StringIO()
        call_command('expire_room_rentals', '--dry-run', stdout=out)

        # Refresh from database
        self.expired_reservation_request.refresh_from_db()
        self.expired_issued_request.refresh_from_db()

        # Verify that statuses remain unchanged
        self.assertEqual(self.expired_reservation_request.status, 'reserved')
        self.assertEqual(self.expired_issued_request.status, 'issued')

        # Verify that no return transactions were created
        return_transactions = RentalTransaction.objects.filter(transaction_type='return')
        self.assertEqual(return_transactions.count(), 0)

        # Verify output contains dry-run message
        output = out.getvalue()
        self.assertIn('TEST MODE - changes will not be applied', output)
        self.assertIn('In test mode, changes are not applied', output)

    @patch('django.utils.timezone.now')
    def test_command_with_verbose(self, mock_now):
        """Test that command with verbose option shows detailed output."""
        mock_now.return_value = self.now

        # Run the command with verbose
        out = StringIO()
        call_command('expire_room_rentals', '--verbose', stdout=out)

        # Verify output contains detailed information
        output = out.getvalue()
        self.assertIn('Details of expired rentals:', output)
        self.assertIn('Test Room - Expired Reservation', output)
        self.assertIn('Test Room - Expired Issued Rental', output)

    @patch('django.utils.timezone.now')
    def test_command_no_expired_rentals(self, mock_now):
        """Test that command handles case where there are no expired rentals."""
        mock_now.return_value = self.now - timedelta(days=10)  # Set time to past all rentals

        # Update all rentals to not be expired
        RentalRequest.objects.all().update(
            requested_end_date=self.now + timedelta(days=1)
        )

        # Run the command
        out = StringIO()
        call_command('expire_room_rentals', stdout=out)

        # Verify output indicates no expired rentals
        output = out.getvalue()
        self.assertIn('No expired room rentals found', output)

    @patch('django.utils.timezone.now')
    @patch('rental.management.commands.expire_room_rentals.logger')
    def test_command_logs_errors(self, mock_logger, mock_now):
        """Test that command logs errors when exceptions occur."""
        mock_now.return_value = self.now

        # Mock transaction.atomic to raise an exception
        with patch('django.db.transaction.atomic') as mock_atomic:
            mock_atomic.return_value.__enter__.side_effect = Exception('Database error')
            
            # Run the command and expect it to raise an exception
            out = StringIO()
            with self.assertRaises(Exception):
                call_command('expire_room_rentals', stdout=out)

            # Verify that error was logged
            mock_logger.error.assert_called_once()