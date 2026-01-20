"""Tests for Tools models."""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from tools.models import SlideshowProject, SlideshowMedia, SlideshowAudio, ToolsConfig


class SlideshowProjectModelTest(TestCase):
    """Tests for SlideshowProject model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_project(self):
        """Test creating a slideshow project."""
        project = SlideshowProject.objects.create(
            name='Test Project',
            created_by=self.user
        )
        self.assertEqual(project.name, 'Test Project')
        self.assertEqual(project.status, 'draft')
        self.assertEqual(project.slide_duration, 20.0)
        self.assertEqual(project.fps, 25)
    
    def test_project_str(self):
        """Test project string representation."""
        project = SlideshowProject.objects.create(
            name='Test Project',
            created_by=self.user
        )
        self.assertIn('Test Project', str(project))
    
    def test_media_count_property(self):
        """Test media_count property."""
        project = SlideshowProject.objects.create(
            name='Test Project',
            created_by=self.user
        )
        self.assertEqual(project.media_count, 0)


class SlideshowMediaModelTest(TestCase):
    """Tests for SlideshowMedia model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.project = SlideshowProject.objects.create(
            name='Test Project',
            created_by=self.user
        )
    
    def test_create_image_media(self):
        """Test creating image media."""
        image = SimpleUploadedFile(
            "test.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        media = SlideshowMedia.objects.create(
            project=self.project,
            file=image,
            order=1
        )
        self.assertEqual(media.media_type, 'image')
        self.assertEqual(media.order, 1)


class ToolsConfigModelTest(TestCase):
    """Tests for ToolsConfig model."""
    
    def test_singleton_config(self):
        """Test that ToolsConfig is a singleton."""
        config1 = ToolsConfig.get_config()
        config2 = ToolsConfig.get_config()
        self.assertEqual(config1.pk, config2.pk)
        self.assertEqual(config1.pk, 1)
    
    def test_config_defaults(self):
        """Test default config values."""
        config = ToolsConfig.get_config()
        self.assertEqual(config.max_upload_size, 500)
        self.assertEqual(config.ffmpeg_path, 'ffmpeg')
        self.assertEqual(config.ffprobe_path, 'ffprobe')
