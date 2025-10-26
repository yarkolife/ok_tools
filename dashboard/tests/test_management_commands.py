from datetime import date
from datetime import timedelta
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from unittest.mock import MagicMock
from dashboard.models import AlertThreshold
from dashboard.models import UserJourneyStage
from dashboard.models import AlertLog
from dashboard.models import FunnelMetrics
from registration.models import OKUser
from registration.models import Profile


class TestCheckAlertsCommand(TestCase):
    """Test cases for the check_alerts management command."""

    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = OKUser.objects.create(email='test@example.com')
        Profile.objects.create(
            okuser=self.user,
            first_name='Test',
            last_name='User',
            verified=True
        )

    @patch('dashboard.management.commands.check_alerts.AlertManager')
    @patch('dashboard.management.commands.check_alerts.FunnelTracker')
    def test_check_alerts_command_success(self, mock_tracker, mock_alert_manager):
        """Test check_alerts command runs successfully."""
        # Mock the tracker and alert manager
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value = mock_tracker_instance
        
        mock_alert_manager_instance = MagicMock()
        mock_alert_manager.return_value = mock_alert_manager_instance
        
        # Mock return values
        mock_tracker_instance.get_funnel_metrics.return_value = {
            'metrics': {'total_registrations': 100},
            'conversion_rates': {'verification_rate': 50.0}
        }
        mock_alert_manager_instance.check_thresholds.return_value = []
        
        # Call the command
        call_command('check_alerts', days=1)
        
        # Verify the mocks were called
        mock_tracker_instance.get_funnel_metrics.assert_called_once()
        mock_alert_manager_instance.check_thresholds.assert_called_once()
        mock_tracker_instance.cache_funnel_metrics.assert_called_once()

    @patch('dashboard.management.commands.check_alerts.AlertManager')
    @patch('dashboard.management.commands.check_alerts.FunnelTracker')
    def test_check_alerts_command_with_triggered_alerts(self, mock_tracker, mock_alert_manager):
        """Test check_alerts command with triggered alerts."""
        # Mock the tracker and alert manager
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value = mock_tracker_instance
        
        mock_alert_manager_instance = MagicMock()
        mock_alert_manager.return_value = mock_alert_manager_instance
        
        # Create a mock alert
        mock_alert = MagicMock()
        mock_alert.message = 'Test alert message'
        
        # Mock return values
        mock_tracker_instance.get_funnel_metrics.return_value = {
            'metrics': {'total_registrations': 100},
            'conversion_rates': {'verification_rate': 50.0}
        }
        mock_alert_manager_instance.check_thresholds.return_value = [mock_alert]
        
        # Call the command
        call_command('check_alerts', days=1)
        
        # Verify the mocks were called
        mock_tracker_instance.get_funnel_metrics.assert_called_once()
        mock_alert_manager_instance.check_thresholds.assert_called_once()
        mock_tracker_instance.cache_funnel_metrics.assert_called_once()

    @patch('dashboard.management.commands.check_alerts.AlertManager')
    @patch('dashboard.management.commands.check_alerts.FunnelTracker')
    def test_check_alerts_command_dry_run(self, mock_tracker, mock_alert_manager):
        """Test check_alerts command with dry-run option."""
        # Mock the tracker and alert manager
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value = mock_tracker_instance
        
        mock_alert_manager_instance = MagicMock()
        mock_alert_manager.return_value = mock_alert_manager_instance
        
        # Mock return values
        mock_tracker_instance.get_funnel_metrics.return_value = {
            'metrics': {'total_registrations': 100},
            'conversion_rates': {'verification_rate': 50.0}
        }
        mock_alert_manager_instance.check_thresholds.return_value = []
        
        # Call the command with dry-run
        call_command('check_alerts', days=1, dry_run=True)
        
        # Verify the mocks were called
        mock_tracker_instance.get_funnel_metrics.assert_called_once()
        mock_alert_manager_instance.check_thresholds.assert_called_once()
        mock_tracker_instance.cache_funnel_metrics.assert_called_once()
    @patch('dashboard.management.commands.populate_funnel_data.random')
    @patch('dashboard.management.commands.populate_funnel_data.FunnelTracker')
    def test_populate_funnel_data_command_success(self, mock_funnel_tracker, mock_random):
        """Test populate_funnel_data command runs successfully."""
        # Mock random functions
        mock_random.choice.return_value = 'M'
        mock_random.randint.return_value = 25
        mock_random.sample.return_value = []
        mock_random.random.return_value = 0.5
        
        # Mock funnel tracker
        mock_tracker_instance = MagicMock()
        mock_funnel_tracker.return_value = mock_tracker_instance
        
        # Call the command
        call_command('populate_funnel_data', users=10, days=5)
        
        # Verify the funnel tracker was called
        mock_tracker_instance.cache_funnel_metrics.assert_called()

    @patch('dashboard.management.commands.populate_funnel_data.random')
    @patch('dashboard.management.commands.populate_funnel_data.FunnelTracker')
    def test_populate_funnel_data_command_with_defaults(self, mock_funnel_tracker, mock_random):
        """Test populate_funnel_data command with default parameters."""
        # Mock random functions
        mock_random.choice.return_value = 'F'
        mock_random.randint.return_value = 30
        mock_random.sample.return_value = []
        mock_random.random.return_value = 0.3
        
        # Mock funnel tracker
        mock_tracker_instance = MagicMock()
        mock_funnel_tracker.return_value = mock_tracker_instance
        
        # Call the command with defaults
        call_command('populate_funnel_data')
        
        # Verify the funnel tracker was called
        mock_tracker_instance.cache_funnel_metrics.assert_called()
    def test_setup_default_thresholds_command_success(self):
        """Test setup_default_thresholds command runs successfully."""
        # Call the command
        call_command('setup_default_thresholds')
        
        # Verify that the default thresholds were created
        self.assertGreater(AlertThreshold.objects.count(), 0)
        
        # Check that specific thresholds exist
        threshold_names = [
            'Low Verification Rate',
            'Low License Creation Rate', 
            'Low Broadcast Rate',
            'High Registration Count',
            'Low Rental Completion Rate'
        ]
        
        for name in threshold_names:
            with self.subTest(threshold_name=name):
                self.assertTrue(AlertThreshold.objects.filter(name=name).exists())

    def test_setup_default_thresholds_command_idempotent(self):
        """Test setup_default_thresholds command is idempotent."""
        # Call the command twice
        call_command('setup_default_thresholds')
        count_after_first_call = AlertThreshold.objects.count()
        
        call_command('setup_default_thresholds')
        count_after_second_call = AlertThreshold.objects.count()
        
        # The count should be the same, as the command should update existing thresholds
        self.assertEqual(count_after_first_call, count_after_second_call)
        
        # Check that the thresholds have the expected values
        low_verification_threshold = AlertThreshold.objects.get(name='Low Verification Rate')
        self.assertEqual(low_verification_threshold.threshold_value, 50.0)
        self.assertEqual(low_verification_threshold.comparison_operator, 'lt')
        self.assertEqual(low_verification_threshold.metric_type, 'conversion_rate')
        self.assertIn('admin@ok-tools.de', low_verification_threshold.notification_recipients)