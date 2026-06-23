"""Tests for auto-copy on planning (media_files.tasks.copy_videos_for_plan).

Covers the primary-version selection and the lifecycle:
  CUSTOM (staging) -> ARCHIVE (permanent, all versions, primary flagged)
                   -> PLAYOUT (temporary, primary only, no primary flag)
  CUSTOM sources are auto-deleted once archived + played out.
"""

import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.test import TestCase

from media_files.models import MediaFilesConfig, StorageLocation, VideoFile
from media_files.tasks import copy_videos_for_plan


def _make_video(storage, number, filename, *, is_manual_primary=False,
                total_bitrate=5_000_000, content=None):
    """Create a real file on disk in ``storage`` and a matching VideoFile row."""
    path = Path(storage.path) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content or f"fake video content {filename}".encode())
    return VideoFile.objects.create(
        number=number,
        filename=filename,
        storage_location=storage,
        file_path=filename,
        is_available=True,
        is_manual_primary=is_manual_primary,
        total_bitrate=total_bitrate,
        file_size=path.stat().st_size,
    )


def _enable_auto_copy(playout_storage_name="Test Sendungen"):
    """Turn on all auto-copy flags in the singleton MediaFilesConfig."""
    config = MediaFilesConfig.get_config()
    config.auto_copy_on_schedule = True
    config.auto_copy_to_archive = True
    config.auto_copy_to_playout = True
    config.auto_delete_from_custom = True
    config.copy_verify_checksum = False
    config.use_weekly_folders = True
    config.default_playout_storage_name = playout_storage_name
    config.save()
    return config


class CopyVideosForPlanTests(TestCase):
    """End-to-end tests for copy_videos_for_plan."""

    def setUp(self):
        self.custom_dir = tempfile.mkdtemp(prefix="custom_")
        self.archive_dir = tempfile.mkdtemp(prefix="archive_")
        self.playout_dir = tempfile.mkdtemp(prefix="playout_")

        self.custom = StorageLocation.objects.create(
            name="Custom Staging", storage_type="CUSTOM",
            path=self.custom_dir, is_active=True,
        )
        self.archive = StorageLocation.objects.create(
            name="Test Archive", storage_type="ARCHIVE",
            path=self.archive_dir, is_active=True,
        )
        self.playout = StorageLocation.objects.create(
            name="Test Sendungen", storage_type="PLAYOUT",
            path=self.playout_dir, is_active=True,
        )
        _enable_auto_copy()
        # Monday in ISO week 02 of 2025 -> week_folder "2025_KW_02"
        self.plan_date = date(2025, 1, 6)
        self.week_folder = "2025_KW_02"

    def tearDown(self):
        shutil.rmtree(self.custom_dir, ignore_errors=True)
        shutil.rmtree(self.archive_dir, ignore_errors=True)
        shutil.rmtree(self.playout_dir, ignore_errors=True)

    def _run(self, numbers):
        return copy_videos_for_plan(numbers, self.plan_date, user_id=None)

    # --- playout: only PRIMARY ---------------------------------------------

    def test_only_primary_copied_to_playout(self):
        """Playout receives the primary version, not the non-primary one."""
        primary = _make_video(
            self.custom, 18676, "18676_Teil_1_v1.mp4",
            is_manual_primary=True, total_bitrate=4_000_000,
        )
        _make_video(
            self.custom, 18676, "18676_Teil_1.mp4",
            is_manual_primary=False, total_bitrate=10_000_000,
        )

        self._run([18676])

        playout_files = list(
            VideoFile.objects.filter(
                number=18676, storage_location=self.playout, is_available=True,
            )
        )
        self.assertEqual(len(playout_files), 1)
        self.assertEqual(playout_files[0].filename, primary.filename)

    # --- archive: ALL versions ---------------------------------------------

    def test_all_versions_copied_to_archive(self):
        """Archive receives every source version, not just the primary."""
        _make_video(
            self.custom, 18676, "18676_Teil_1_v1.mp4",
            is_manual_primary=True, total_bitrate=4_000_000,
        )
        _make_video(
            self.custom, 18676, "18676_Teil_1.mp4",
            is_manual_primary=False, total_bitrate=10_000_000,
        )

        self._run([18676])

        archive_filenames = sorted(
            VideoFile.objects.filter(
                number=18676, storage_location=self.archive, is_available=True,
            ).values_list("filename", flat=True)
        )
        self.assertEqual(
            archive_filenames, ["18676_Teil_1.mp4", "18676_Teil_1_v1.mp4"],
        )

    # --- primary flag: archive only, not playout ---------------------------

    def test_primary_flag_propagates_to_archive_not_playout(self):
        """Archive copy of primary keeps the flag; playout copy does not."""
        _make_video(
            self.custom, 18676, "18676_Teil_1_v1.mp4",
            is_manual_primary=True, total_bitrate=4_000_000,
        )
        _make_video(
            self.custom, 18676, "18676_Teil_1.mp4",
            is_manual_primary=False, total_bitrate=10_000_000,
        )

        self._run([18676])

        archive_v1 = VideoFile.objects.get(
            number=18676, storage_location=self.archive,
            filename="18676_Teil_1_v1.mp4",
        )
        archive_master = VideoFile.objects.get(
            number=18676, storage_location=self.archive,
            filename="18676_Teil_1.mp4",
        )
        playout_v1 = VideoFile.objects.get(
            number=18676, storage_location=self.playout,
            filename="18676_Teil_1_v1.mp4",
        )
        self.assertTrue(archive_v1.is_manual_primary)
        self.assertFalse(archive_master.is_manual_primary)
        self.assertFalse(playout_v1.is_manual_primary)

    # --- filename-aware duplicate: existing non-primary does not block ------

    def test_existing_non_primary_in_archive_does_not_block_primary(self):
        """A 50fps master already in archive must not block the primary copy."""
        _make_video(
            self.archive, 18676, "18676_Teil_1.mp4",
            is_manual_primary=False, total_bitrate=10_000_000,
        )
        _make_video(
            self.custom, 18676, "18676_Teil_1_v1.mp4",
            is_manual_primary=True, total_bitrate=4_000_000,
        )

        self._run([18676])

        archive_filenames = sorted(
            VideoFile.objects.filter(
                number=18676, storage_location=self.archive, is_available=True,
            ).values_list("filename", flat=True)
        )
        self.assertEqual(
            archive_filenames, ["18676_Teil_1.mp4", "18676_Teil_1_v1.mp4"],
        )
        # The pre-existing master keeps its non-primary status; the freshly
        # copied primary becomes the archive's primary.
        self.assertFalse(
            VideoFile.objects.get(
                number=18676, storage_location=self.archive,
                filename="18676_Teil_1.mp4",
            ).is_manual_primary
        )
        self.assertTrue(
            VideoFile.objects.get(
                number=18676, storage_location=self.archive,
                filename="18676_Teil_1_v1.mp4",
            ).is_manual_primary
        )

    # --- auto-delete from CUSTOM -------------------------------------------

    def test_custom_auto_deleted_after_archive_and_playout(self):
        """CUSTOM sources are removed once archived and played out."""
        _make_video(
            self.custom, 18676, "18676_Teil_1_v1.mp4",
            is_manual_primary=True, total_bitrate=4_000_000,
        )
        _make_video(
            self.custom, 18676, "18676_Teil_1.mp4",
            is_manual_primary=False, total_bitrate=10_000_000,
        )

        self._run([18676])

        self.assertFalse(
            VideoFile.objects.filter(
                number=18676, storage_location=self.custom, is_available=True,
            ).exists()
        )

    # --- primary selection fallback (no manual primary) --------------------

    def test_primary_selection_falls_back_to_algorithm(self):
        """Without a manual flag, is_primary_version() picks the source."""
        from django.utils import timezone
        from datetime import timedelta

        # Two CUSTOM versions, neither manually marked. The newer acceptable
        # one (>= 80% of max bitrate) wins per is_primary_version() rules.
        # created_at (auto_now_add) determines recency, so create older first.
        older = _make_video(
            self.custom, 55555, "55555_old_high.mp4",
            is_manual_primary=False, total_bitrate=10_000_000,
        )
        older.last_scanned = timezone.now() - timedelta(days=2)
        older.save(update_fields=["last_scanned"])
        newer = _make_video(
            self.custom, 55555, "55555_new_ok.mp4",
            is_manual_primary=False, total_bitrate=8_100_000,
        )
        newer.last_scanned = timezone.now()
        newer.save(update_fields=["last_scanned"])

        self._run([55555])

        playout_files = list(
            VideoFile.objects.filter(
                number=55555, storage_location=self.playout, is_available=True,
            )
        )
        self.assertEqual(len(playout_files), 1)
        self.assertEqual(playout_files[0].filename, newer.filename)

    # --- missing video is a non-critical warning ---------------------------

    def test_missing_video_is_warning_not_error(self):
        """A number with no source versions is skipped, not raised."""
        result = self._run([99999])
        self.assertEqual(result["warnings"], 1)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["copied_to_archive"], 0)
        self.assertEqual(result["copied_to_playout"], 0)
