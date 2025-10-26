from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from io import StringIO
from unittest.mock import patch, mock_open
from pathlib import Path
import tempfile


class ImportInspectionsCommandTest(TestCase):
    """Unit tests for import_inspections management command."""

    def test_command_missing_file_raises_error(self):
        """Test that command raises CommandError when file doesn't exist."""
        with self.assertRaises(CommandError) as context:
            call_command('import_inspections', 'nonexistent_file.csv')
        self.assertEqual(str(context.exception), 'File not found')

    @patch('inventory.management.commands.import_inspections.inspection_import')
    def test_command_calls_inspection_import(self, mock_inspection_import):
        """Test that command calls inspection_import with correct parameters."""
        # Mock the return value of inspection_import
        mock_inspection_import.return_value = {'created': 5, 'skipped': 3}
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as temp_file:
            temp_file.write('test data')
            temp_file_path = temp_file.name

        try:
            # Capture output
            out = StringIO()
            call_command('import_inspections', temp_file_path, stdout=out)
            
            # Verify that inspection_import was called with correct parameters
            mock_inspection_import.assert_called_once()
            # Check that the first argument is None (user), second is file object, third is None (import_obj)
            args, kwargs = mock_inspection_import.call_args
            self.assertIsNone(args[0])  # user is None
            self.assertIsNotNone(args[1])  # file object is passed
            self.assertIsNone(args[2])  # import_obj is None
            
            # Verify output message
            output = out.getvalue().strip()
            self.assertIn('Imported 5 new and updated 3 inspections.', output)
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink()

    @patch('inventory.management.commands.import_inspections.inspection_import')
    def test_command_with_xlsx_file(self, mock_inspection_import):
        """Test that command works with XLSX files."""
        # Mock the return value of inspection_import
        mock_inspection_import.return_value = {'created': 2, 'skipped': 0}
        
        # Create a temporary XLSX file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.xlsx') as temp_file:
            temp_file.write('test data')
            temp_file_path = temp_file.name

        try:
            # Capture output
            out = StringIO()
            call_command('import_inspections', temp_file_path, stdout=out)
            
            # Verify that inspection_import was called
            mock_inspection_import.assert_called_once()
            
            # Verify output message
            output = out.getvalue().strip()
            self.assertIn('Imported 2 new and updated 0 inspections.', output)
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink()