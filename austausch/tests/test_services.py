"""Tests for Austausch services."""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from austausch.models import ExchangeItem, ExchangeConfig
from austausch.services.nextcloud_exchange_service import NextcloudExchangeService
from austausch.services.export_to_server_service import ExportToServerService


@pytest.mark.django_db
class TestNextcloudExchangeService(TestCase):
    """Tests for NextcloudExchangeService."""
    
    def setUp(self):
        """Set up test data."""
        self.config = ExchangeConfig.get_config()
        self.config.nextcloud_base_url = 'https://cloud.example.com'
        self.config.nextcloud_username = 'test_user'
        self.config.nextcloud_password = 'test_pass'
        self.config.download_storage_path = '/tmp'
        self.config.upload_server_path = 'GroupFolders/Test-Upload'
        self.config.save()
    
    def test_parse_contribution_id(self):
        """Test parsing contribution ID from filename."""
        # OK-Tools managed filename
        self.assertEqual(
            NextcloudExchangeService.parse_contribution_id('12345_20240101_video.mp4'),
            12345
        )
        
        # Legacy filename
        self.assertIsNone(
            NextcloudExchangeService.parse_contribution_id('legacy_video.mp4')
        )
        
        # Edge cases
        self.assertIsNone(NextcloudExchangeService.parse_contribution_id(''))
        self.assertIsNone(NextcloudExchangeService.parse_contribution_id('no_number.mp4'))
    
    def test_detect_file_type(self):
        """Test file type detection."""
        self.assertEqual(
            NextcloudExchangeService.detect_file_type('video.mp4'),
            'video'
        )
        self.assertEqual(
            NextcloudExchangeService.detect_file_type('document.pdf'),
            'pdf'
        )
        self.assertEqual(
            NextcloudExchangeService.detect_file_type('unknown.txt'),
            'unknown'
        )


@pytest.mark.django_db
class TestExportToServerServiceNetworkShare(TestCase):
    """Tests for network share export helpers."""

    def setUp(self):
        self.config = ExchangeConfig.get_config()
        self.config.nextcloud_base_url = 'https://cloud.example.com'
        self.config.nextcloud_username = 'test_user'
        self.config.nextcloud_password = 'test_pass'
        self.config.export_destination = 'network_share'
        self.config.network_share_windows_root = r'Z:\Vorschau\2025'
        self.config.network_share_subfolder = 'austausch'
        self.tmpdir = tempfile.mkdtemp(prefix='austausch_test_')
        self.config.network_share_base_path = self.tmpdir
        self.config.download_storage_path = self.tmpdir
        self.config.save()
        self.service = ExportToServerService()

    def test_build_windows_files_txt_entry(self):
        entry = self.service._build_windows_files_txt_entry('Lassa_Sendung.mp4')
        self.assertEqual(entry, r'"Z:\Vorschau\2025\Lassa_Sendung.mp4"')

    def test_append_to_files_txt(self):
        export_dir = self.service._network_share_export_dir()
        os.makedirs(export_dir, exist_ok=True)
        ok1 = self.service._append_to_files_txt(export_dir, 'video.mp4')
        ok2 = self.service._append_to_files_txt(export_dir, 'video.meta.json')
        self.assertTrue(ok1)
        self.assertTrue(ok2)

        files_txt = os.path.join(export_dir, 'files.txt')
        self.assertTrue(os.path.isfile(files_txt))
        with open(files_txt, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], r'"Z:\Vorschau\2025\video.mp4"')
        self.assertEqual(lines[1], r'"Z:\Vorschau\2025\video.meta.json"')

    def test_copy_file_atomic(self):
        export_dir = self.service._network_share_export_dir()
        os.makedirs(export_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False) as src:
            src.write(b'test_payload')
            src_path = src.name

        target_path = os.path.join(export_dir, 'copied.bin')
        try:
            ok = self.service._copy_file_atomic(src_path, target_path)
            self.assertTrue(ok)
            with open(target_path, 'rb') as f:
                self.assertEqual(f.read(), b'test_payload')
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)
