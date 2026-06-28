"""Tests for media files module."""

from .admin import VideoFileAdmin
from .models import FileOperation
from .models import StorageLocation
from .models import VideoFile
from .utils import calculate_checksum
from .utils import extract_number_from_filename
from .utils import is_reel_filename
from .utils import scan_directory
from datetime import timedelta
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile


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


class ReelFilenameTests(TestCase):
    """Tests for generated reel file detection."""

    def test_detects_reel_segment(self):
        self.assertTrue(is_reel_filename("18480_Reel_260627.mp4"))
        self.assertTrue(is_reel_filename("18480_Programmvorschau_Reel_260627.mp4"))

    def test_does_not_detect_full_sendung(self):
        self.assertFalse(is_reel_filename("18480_Campusfernsehen_Sendedatei.mp4"))


class ReelSourceSelectionTests(TestCase):
    """Tests for License admin Reel Studio source selection."""

    def setUp(self):
        self.playout = StorageLocation.objects.create(
            name="Playout",
            storage_type="PLAYOUT",
            path="/tmp/playout/",
            is_active=True,
        )
        self.archive = StorageLocation.objects.create(
            name="Archive",
            storage_type="ARCHIVE",
            path="/tmp/archive/",
            is_active=True,
        )

    def test_reel_source_ignores_reel_files(self):
        from licenses.admin import LicenseAdmin

        number = 18480
        VideoFile.objects.create(
            number=number,
            filename="18480_Reel_260627.mp4",
            storage_location=self.playout,
            file_path="18480_Reel_260627.mp4",
            is_available=True,
            width=1080,
            height=1920,
        )
        playout_full = VideoFile.objects.create(
            number=number,
            filename="18480_Campusfernsehen_Sendedatei.mp4",
            storage_location=self.playout,
            file_path="18480_Campusfernsehen_Sendedatei.mp4",
            is_available=True,
            width=1920,
            height=1080,
        )
        VideoFile.objects.create(
            number=number,
            filename="18480_Campusfernsehen_Sendedatei.mp4",
            storage_location=self.archive,
            file_path="18480_Campusfernsehen_Sendedatei.mp4",
            is_available=True,
            width=1920,
            height=1080,
        )
        license_obj = SimpleNamespace(number=number, get_video_file=lambda: None)

        self.assertEqual(LicenseAdmin._reel_video_file(license_obj), playout_full)

    def test_reel_source_returns_none_for_reel_only_number(self):
        from licenses.admin import LicenseAdmin

        number = 18481
        VideoFile.objects.create(
            number=number,
            filename="18481_Reel_260627.mp4",
            storage_location=self.playout,
            file_path="18481_Reel_260627.mp4",
            is_available=True,
        )
        license_obj = SimpleNamespace(number=number, get_video_file=lambda: None)

        self.assertIsNone(LicenseAdmin._reel_video_file(license_obj))


class ScanVideoStorageReelTests(TestCase):
    """Tests for scan-time reel classification."""

    def test_scan_marks_reel_file_as_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = StorageLocation.objects.create(
                name="Reel Playout",
                storage_type="PLAYOUT",
                path=tmpdir,
                is_active=True,
                scan_enabled=True,
            )
            Path(tmpdir, "18480_Reel_260627.mp4").write_bytes(b"not-a-real-video")

            call_command(
                "scan_video_storage",
                "--storage-id",
                str(storage.id),
                "--skip-metadata",
            )

            video = VideoFile.objects.get(number=18480)
            self.assertTrue(video.is_preview)


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

    def test_is_primary_version_custom_only_no_type_error(self):
        """Ensure is_primary_version works for CUSTOM-only versions without TypeError."""
        custom_storage = StorageLocation.objects.create(
            name="Custom Storage",
            storage_type="CUSTOM",
            path="/tmp/custom/",
            is_active=True,
        )

        older_high = VideoFile.objects.create(
            number=77777,
            filename="77777_old_high.mp4",
            storage_location=custom_storage,
            file_path="77777_old_high.mp4",
            is_available=True,
            total_bitrate=10_000_000,
            last_scanned=timezone.now() - timedelta(days=2),
        )
        newer_acceptable = VideoFile.objects.create(
            number=77777,
            filename="77777_new_ok.mp4",
            storage_location=custom_storage,
            file_path="77777_new_ok.mp4",
            is_available=True,
            total_bitrate=8_100_000,  # >= 80% of max bitrate
            last_scanned=timezone.now(),
        )

        # Must not raise TypeError, and newer acceptable CUSTOM version should win.
        self.assertFalse(older_high.is_primary_version())
        self.assertTrue(newer_acceptable.is_primary_version())

    def test_is_primary_version_custom_only_prefers_quality_below_80_percent(self):
        """For CUSTOM-only versions, very low bitrate should not override quality with recency."""
        custom_storage = StorageLocation.objects.create(
            name="Custom Storage 2",
            storage_type="CUSTOM",
            path="/tmp/custom2/",
            is_active=True,
        )

        older_high = VideoFile.objects.create(
            number=88888,
            filename="88888_old_high.mp4",
            storage_location=custom_storage,
            file_path="88888_old_high.mp4",
            is_available=True,
            total_bitrate=10_000_000,
            last_scanned=timezone.now() - timedelta(days=2),
        )
        newer_low = VideoFile.objects.create(
            number=88888,
            filename="88888_new_low.mp4",
            storage_location=custom_storage,
            file_path="88888_new_low.mp4",
            is_available=True,
            total_bitrate=7_000_000,  # < 80% of max bitrate
            last_scanned=timezone.now(),
        )

        self.assertTrue(older_high.is_primary_version())
        self.assertFalse(newer_low.is_primary_version())


class VideoFileAdminDisplayTests(TestCase):
    def setUp(self):
        self.storage = StorageLocation.objects.create(
            name="Admin Display Storage",
            storage_type="ARCHIVE",
            path="/tmp/admin-display/",
            is_active=True,
        )
        self.video = VideoFile.objects.create(
            number=99901,
            filename="99901_admin_display.mp4",
            storage_location=self.storage,
            file_path="99901_admin_display.mp4",
            is_available=True,
        )
        self.admin = VideoFileAdmin(VideoFile, AdminSite())

    def test_fps_display_handles_missing_fps_without_format_html_error(self):
        self.video.fps = None

        rendered = self.admin.fps_display(self.video)

        self.assertIn('—', str(rendered))

    def test_duplicate_status_display_handles_unique_video(self):
        rendered = self.admin.duplicate_status_display(self.video)

        self.assertIn('Unique', str(rendered))

    def test_all_versions_display_handles_multiple_versions(self):
        VideoFile.objects.create(
            number=self.video.number,
            filename="99901_admin_display_v2.mp4",
            storage_location=self.storage,
            file_path="99901_admin_display_v2.mp4",
            is_available=True,
            total_bitrate=7_000_000,
        )

        rendered = self.admin.all_versions_display(self.video)

        self.assertIn('99901_admin_display', str(rendered))

    def test_changelist_handles_missing_fps(self):
        user = get_user_model().objects.create_superuser(
            email='media-admin@example.com',
            password='testpassword',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('admin:media_files_videofile_changelist'))

        self.assertEqual(response.status_code, 200)


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
