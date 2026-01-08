"""Tests for Austausch models."""

import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from austausch.models import ExchangeItem, ExchangeImport, ExchangeConfig
from licenses.models import License, Category
from registration.models import Profile, OKUser


@pytest.mark.django_db
class TestExchangeItem(TestCase):
    """Tests for ExchangeItem model."""
    
    def setUp(self):
        """Set up test data."""
        self.item = ExchangeItem.objects.create(
            contribution_id=12345,
            filename='12345_20240101_video.mp4',
            file_path='/channel_austausch/12345_20240101_video.mp4',
            channel='test_channel',
            file_size=1000000,
            file_type='video',
            is_oktools_managed=True,
        )
    
    def test_str_representation(self):
        """Test string representation."""
        self.assertIn('12345', str(self.item))
        self.assertIn('test_channel', str(self.item))
    
    def test_legacy_item(self):
        """Test legacy item creation."""
        legacy = ExchangeItem.objects.create(
            filename='legacy_video.mp4',
            file_path='/channel_austausch/legacy_video.mp4',
            channel='test_channel',
            is_legacy=True,
        )
        self.assertTrue(legacy.is_legacy)
        self.assertIsNone(legacy.contribution_id)


@pytest.mark.django_db
class TestExchangeConfig(TestCase):
    """Tests for ExchangeConfig model."""
    
    def test_singleton(self):
        """Test that only one config can exist."""
        config1 = ExchangeConfig.get_config()
        config2 = ExchangeConfig.get_config()
        self.assertEqual(config1.pk, config2.pk)
        self.assertEqual(config1.pk, 1)
    
    def test_get_config_creates_if_not_exists(self):
        """Test that get_config creates config if it doesn't exist."""
        ExchangeConfig.objects.all().delete()
        config = ExchangeConfig.get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.pk, 1)


@pytest.mark.django_db
class TestExchangeImport(TestCase):
    """Tests for ExchangeImport model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = OKUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.item = ExchangeItem.objects.create(
            filename='test.mp4',
            file_path='/test/test.mp4',
            channel='test',
        )
    
    def test_import_creation(self):
        """Test import record creation."""
        import_record = ExchangeImport.objects.create(
            exchange_item=self.item,
            imported_by=self.user,
            status='pending',
        )
        self.assertEqual(import_record.exchange_item, self.item)
        self.assertEqual(import_record.imported_by, self.user)
        self.assertEqual(import_record.status, 'pending')

