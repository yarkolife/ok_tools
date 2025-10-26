from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from io import StringIO
from unittest.mock import patch, mock_open
from inventory.models import Location
import tempfile


class ImportLocationsCommandTest(TestCase):
    """Unit tests for import_locations management command."""

    def test_command_missing_file_raises_error(self):
        """Test that command raises CommandError when file doesn't exist."""
        with self.assertRaises(CommandError):
            call_command('import_locations', file='nonexistent_file.txt')

    @patch('builtins.open', new_callable=mock_open, read_data='Room 1\nCabinet 2\n')
    def test_command_imports_locations_successfully(self, mock_file):
        """Test that command successfully imports locations from file."""
        # Mock Location.objects.get_by_path to return None (new locations)
        with patch.object(Location.objects, 'get_by_path', return_value=None) as mock_get_by_path:
            with patch.object(Location.objects, 'create_by_path') as mock_create_by_path:
                # Capture output
                out = StringIO()
                call_command('import_locations', file='test_file.txt', stdout=out)
                
                # Verify that get_by_path was called for each location
                mock_get_by_path.assert_any_call('Room 1')
                mock_get_by_path.assert_any_call('Cabinet 2')
                
                # Verify that create_by_path was called for each new location
                mock_create_by_path.assert_any_call('Room 1')
                mock_create_by_path.assert_any_call('Cabinet 2')
                
                # Verify output message
                output = out.getvalue().strip()
                self.assertIn('Done. Created 2 new locations.', output)

    @patch('builtins.open', new_callable=mock_open, read_data='Room 1\nCabinet 2\n')
    def test_command_handles_existing_locations(self, mock_file):
        """Test that command handles existing locations correctly."""
        # Mock Location.objects.get_by_path to return existing locations for both
        with patch.object(Location.objects, 'get_by_path', return_value=Location(name='Existing')) as mock_get_by_path:
            with patch.object(Location.objects, 'create_by_path') as mock_create_by_path:
                # Capture output
                out = StringIO()
                call_command('import_locations', file='test_file.txt', stdout=out)
                
                # Verify that get_by_path was called for each location
                mock_get_by_path.assert_any_call('Room 1')
                mock_get_by_path.assert_any_call('Cabinet 2')
                
                # Verify that create_by_path was NOT called since locations exist
                mock_create_by_path.assert_not_called()
                
                # Verify output message (0 new locations created)
                output = out.getvalue().strip()
                self.assertIn('Done. Created 0 new locations.', output)

    @patch('builtins.open', new_callable=mock_open, read_data='Room 1\n\nCabinet 2\n\n')  # Test with blank lines
    def test_command_ignores_blank_lines(self, mock_file):
        """Test that command ignores blank lines in the file."""
        # Mock Location.objects.get_by_path to return None (new locations)
        with patch.object(Location.objects, 'get_by_path', return_value=None) as mock_get_by_path:
            with patch.object(Location.objects, 'create_by_path') as mock_create_by_path:
                # Capture output
                out = StringIO()
                call_command('import_locations', file='test_file.txt', stdout=out)
                
                # Verify that get_by_path was called only for non-blank lines
                calls = [call for call in mock_get_by_path.call_args_list if call[0][0] != '']
                self.assertEqual(len(calls), 2)  # Should only be called for 'Room 1' and 'Cabinet 2'
                
                # Verify that create_by_path was called for each new location
                self.assertEqual(mock_create_by_path.call_count, 2)
                
                # Verify output message
                output = out.getvalue().strip()
                self.assertIn('Done. Created 2 new locations.', output)

    @patch('builtins.open', side_effect=IOError('Permission denied'))
    def test_command_handles_io_error(self, mock_file):
        """Test that command handles IOError when opening file."""
        with self.assertRaises(CommandError) as context:
            call_command('import_locations', file='test_file.txt')
        self.assertEqual(str(context.exception), 'Permission denied')