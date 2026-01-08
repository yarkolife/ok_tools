"""Tests for Austausch services."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from austausch.models import ExchangeItem, ExchangeConfig
from austausch.services.nextcloud_exchange_service import NextcloudExchangeService


@pytest.mark.django_db
class TestNextcloudExchangeService(TestCase):
    """Tests for NextcloudExchangeService."""
    
    def setUp(self):
        """Set up test data."""
        self.config = ExchangeConfig.get_config()
        self.config.nextcloud_base_url = 'https://cloud.example.com'
        self.config.nextcloud_username = 'test_user'
        self.config.nextcloud_password = 'test_pass'
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

