"""Tests for media files module."""

import os
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from .models import StorageLocation, VideoFile, FileOperation
from .utils import (
    extract_number_from_filename,
    scan_directory,
    calculate_checksum,
)


class ExtractNumberFromFilenameTests(TestCase):
    """Tests for extract_number_from_filename function."""

    def test_extract_valid_number(self):
        """Test extracting number from valid filename."""
        filename = "12345_my_video.mp4"
        result = extract_number_from_filename(filename)
        self.assertEqual(result, 12345)

    def test_extract_with_leading_zeros(self):
        """Test extracting number with leading zeros."""
        filename = "00123_video.mov"
        result = extract_number_from_filename(filename)
        self.assertEqual(result, 123)

    def test_no_underscore(self):
        """Test filename without underscore."""
        filename = "12345.mp4"
        result = extract_number_from_filename(filename)
        self.assertIsNone(result)

    def test_no_number(self):
        """Test filename without number."""
        filename = "video_file.mp4"
        result = extract_number_from_filename(filename)
        self.assertIsNone(result)

    def test_number_in_middle(self):
        """Test number not at start."""
        filename = "video_12345_test.mp4"
        result = extract_number_from_filename(filename)
        self.assertIsNone(result)


class StorageLocationModelTests(TestCase):
    """Tests for StorageLocation model."""

    def setUp(self):
        """Set up test storage location."""
        self.storage = StorageLocation.objects.create(
            name="Test Archive",
            storage_type="ARCHIVE",
            path="/tmp/test_archive/",
            is_active=True,
            scan_enabled=False
        )

    def test_storage_creation(self):
        """Test storage location can be created."""
        self.assertEqual(self.storage.name, "Test Archive")
        self.assertEqual(self.storage.storage_type, "ARCHIVE")
        self.assertTrue(self.storage.is_active)

    def test_storage_string_representation(self):
        """Test string representation of storage."""
        expected = "Test Archive (Archive)"
        self.assertEqual(str(self.storage), expected)

    def test_video_count_property(self):
        """Test video count property."""
        self.assertEqual(self.storage.video_count, 0)
        
        # Create video file
        VideoFile.objects.create(
            number=12345,
            filename="12345_test.mp4",
            storage_location=self.storage,
            file_path="12345_test.mp4",
            is_available=True
        )
        
        self.assertEqual(self.storage.video_count, 1)


class VideoFileModelTests(TestCase):
    """Tests for VideoFile model."""

    def setUp(self):
        """Set up test data."""
        self.storage = StorageLocation.objects.create(
            name="Test Storage",
            storage_type="ARCHIVE",
            path="/tmp/test/",
            is_active=True
        )
        
        self.video = VideoFile.objects.create(
            number=12345,
            filename="12345_test_video.mp4",
            storage_location=self.storage,
            file_path="12345_test_video.mp4",
            file_size=1048576,  # 1 MB
            duration=timedelta(minutes=5, seconds=30),
            format="mp4",
            is_available=True,
            width=1920,
            height=1080,
            fps=25.0,
            total_bitrate=5000000
        )

    def test_video_creation(self):
        """Test video file can be created."""
        self.assertEqual(self.video.number, 12345)
        self.assertEqual(self.video.filename, "12345_test_video.mp4")
        self.assertTrue(self.video.is_available)

    def test_full_path_property(self):
        """Test full_path property."""
        expected = "/tmp/test/12345_test_video.mp4"
        self.assertEqual(self.video.full_path, expected)

    def test_resolution_display(self):
        """Test resolution_display property."""
        self.assertEqual(self.video.resolution_display, "1920x1080")

    def test_file_size_mb(self):
        """Test file_size_mb property."""
        self.assertEqual(self.video.file_size_mb, 1.0)

    def test_bitrate_mbps(self):
        """Test bitrate_mbps property."""
        self.assertEqual(self.video.bitrate_mbps, 5.0)

    def test_string_representation(self):
        """Test string representation."""
        expected = "12345 - 12345_test_video.mp4"
        self.assertEqual(str(self.video), expected)


class FileOperationModelTests(TestCase):
    """Tests for FileOperation model."""

    def setUp(self):
        """Set up test data."""
        self.storage = StorageLocation.objects.create(
            name="Test Storage",
            storage_type="ARCHIVE",
            path="/tmp/test/",
            is_active=True
        )
        
        self.video = VideoFile.objects.create(
            number=12345,
            filename="12345_test.mp4",
            storage_location=self.storage,
            file_path="12345_test.mp4",
            is_available=True
        )

    def test_operation_creation(self):
        """Test file operation can be created."""
        operation = FileOperation.objects.create(
            video_file=self.video,
            operation_type='SCAN',
            source_location=self.storage,
            status='SUCCESS'
        )
        
        self.assertEqual(operation.video_file, self.video)
        self.assertEqual(operation.operation_type, 'SCAN')
        self.assertEqual(operation.status, 'SUCCESS')

    def test_operation_string_representation(self):
        """Test string representation."""
        operation = FileOperation.objects.create(
            video_file=self.video,
            operation_type='COPY',
            status='IN_PROGRESS'
        )
        
        expected_substring = "Copy"
        self.assertIn(expected_substring, str(operation))


class ScanDirectoryTests(TestCase):
    """Tests for scan_directory function."""

    def setUp(self):
        """Set up temporary directory with test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = StorageLocation.objects.create(
            name="Test Storage",
            storage_type="ARCHIVE",
            path=self.temp_dir,
            is_active=True
        )
        
        # Create test files
        self.test_files = [
            "12345_video1.mp4",
            "67890_video2.mov",
            "11111_video3.mpeg",
            "readme.txt"  # Should be ignored
        ]
        
        for filename in self.test_files:
            filepath = Path(self.temp_dir) / filename
            filepath.touch()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_finds_video_files(self):
        """Test that scan_directory finds video files."""
        found_files = scan_directory(self.storage)
        
        # Should find 3 video files, ignore txt file
        self.assertEqual(len(found_files), 3)
        
        # Check that found files are video files
        video_filenames = [f[0] for f in found_files]
        self.assertIn("12345_video1.mp4", video_filenames)
        self.assertIn("67890_video2.mov", video_filenames)
        self.assertIn("11111_video3.mpeg", video_filenames)
        self.assertNotIn("readme.txt", video_filenames)


class CalculateChecksumTests(TestCase):
    """Tests for calculate_checksum function."""

    def setUp(self):
        """Create temporary file for testing."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"Test content for checksum")
        self.temp_file.close()

    def tearDown(self):
        """Clean up temporary file."""
        os.unlink(self.temp_file.name)

    def test_calculate_sha256(self):
        """Test SHA256 checksum calculation."""
        checksum = calculate_checksum(self.temp_file.name, algorithm='sha256')
        
        # Should return non-empty hex string
        self.assertTrue(checksum)
        self.assertEqual(len(checksum), 64)  # SHA256 produces 64 hex characters

    def test_calculate_md5(self):
        """Test MD5 checksum calculation."""
        checksum = calculate_checksum(self.temp_file.name, algorithm='md5')
        
        # Should return non-empty hex string
        self.assertTrue(checksum)
        self.assertEqual(len(checksum), 32)  # MD5 produces 32 hex characters

    def test_consistent_checksum(self):
        """Test that checksum is consistent for same content."""
        checksum1 = calculate_checksum(self.temp_file.name)
        checksum2 = calculate_checksum(self.temp_file.name)
        
        self.assertEqual(checksum1, checksum2)


class IntegrationTests(TestCase):
    """Integration tests for media files workflows."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.archive = StorageLocation.objects.create(
            name="Archive",
            storage_type="ARCHIVE",
            path=self.temp_dir,
            is_active=True
        )

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_workflow(self):
        """Test complete workflow: create file, scan, create VideoFile."""
        # Create test video file
        test_filename = "12345_integration_test.mp4"
        test_filepath = Path(self.temp_dir) / test_filename
        test_filepath.write_bytes(b"fake video content")
        
        # Scan directory
        found_files = scan_directory(self.archive)
        self.assertEqual(len(found_files), 1)
        
        filename, rel_path, abs_path = found_files[0]
        self.assertEqual(filename, test_filename)
        
        # Extract number
        number = extract_number_from_filename(filename)
        self.assertEqual(number, 12345)
        
        # Create VideoFile
        video = VideoFile.objects.create(
            number=number,
            filename=filename,
            storage_location=self.archive,
            file_path=rel_path,
            is_available=True
        )
        
        self.assertEqual(video.number, 12345)
        self.assertEqual(video.filename, test_filename)
        
        # Create operation log
        operation = FileOperation.objects.create(
            video_file=video,
            operation_type='SCAN',
            source_location=self.archive,
            status='SUCCESS'
        )
        
        self.assertEqual(operation.video_file, video)
        self.assertEqual(operation.status, 'SUCCESS')

