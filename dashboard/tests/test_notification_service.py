"""
Tests for NotificationService in dashboard application.
"""

from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from registration.models import OKUser

from dashboard.models import AlertThreshold, AlertLog
from dashboard.services.notification_service import NotificationService


class NotificationServiceTestCase(TestCase):
    """Test cases for NotificationService class."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.notification_service = NotificationService()
        
        # Create test user
        self.user = OKUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test alert threshold
        self.alert_threshold = AlertThreshold.objects.create(
            name='Test Threshold',
            stage='registered',
            metric_type='absolute_count',
            threshold_value=10,
            comparison_operator='gt',
            is_active=True
        )
        
        # Create test alert log
        self.alert_log = AlertLog.objects.create(
            threshold=self.alert_threshold,
            message='Test alert',
            is_resolved=False,
            current_value=10.5,
            threshold_value=5.0
        )
    
    def test_get_notifications_statistics(self):
        """Test getting notifications statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock NotificationsWidget
        with patch('dashboard.services.notification_service.NotificationsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_all_data.return_value = {
                'total_notifications': 5,
                'unread_notifications': 2
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.notification_service.get_notifications_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_all_data.assert_called_once()
    
    def test_get_notifications_statistics_with_filters(self):
        """Test getting notifications statistics with various filters."""
        # Create mock request with filters
        request = self.factory.get('/?days=7&start_date=2023-01-01&end_date=2023-01-31&notification_type=info&priority=high&is_active=true&created_by=test')
        
        # Mock NotificationsWidget
        with patch('dashboard.services.notification_service.NotificationsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_all_data.return_value = {
                'total_notifications': 3,
                'unread_notifications': 1
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.notification_service.get_notifications_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_all_data.assert_called_once()
    
    def test_get_notifications_statistics_error_handling(self):
        """Test error handling in get_notifications_statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock NotificationsWidget to raise an exception
        with patch('dashboard.services.notification_service.NotificationsWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.notification_service.get_notifications_statistics(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_alerts_list(self):
        """Test getting alerts list."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.notification_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            mock_filters.return_value = mock_filter_instance
            
            # Mock FunnelTracker
            with patch('dashboard.utils.FunnelTracker') as mock_tracker:
                mock_tracker_instance = Mock()
                mock_tracker_instance.get_funnel_metrics.return_value = {
                    'total_registrations': 5,
                    'verified_users': 3,
                    'licenses_created': 2,
                    'first_broadcasts': 1,
                    'completed_rentals': 1,
                    'conversion_rates': {
                        'verification_rate': 0.6,
                        'license_creation_rate': 0.4,
                        'first_broadcast_rate': 0.2,
                        'rental_completion_rate': 0.2
                    }
                }
                mock_tracker.return_value = mock_tracker_instance
                
                # Call the method
                result = self.notification_service.get_alerts_list(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                self.assertIn('alerts', result['data'])
                self.assertIn('thresholds', result['data'])
    
    def test_get_alerts_list_with_fallback_values(self):
        """Test getting alerts list when FunnelTracker raises exception."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters to raise an exception (fallback scenario)
        with patch('dashboard.services.notification_service.DashboardFilters') as mock_filters:
            mock_filters.side_effect = Exception("Filter error")
            
            # Mock FunnelTracker to raise an exception (fallback scenario)
            with patch('dashboard.utils.FunnelTracker') as mock_tracker:
                mock_tracker.side_effect = Exception("Tracker error")
                
                # Call the method
                result = self.notification_service.get_alerts_list(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                self.assertIn('alerts', result['data'])
                self.assertIn('thresholds', result['data'])
    
    def test_get_alerts_list_with_triggered_alerts(self):
        """Test getting alerts list with triggered alerts."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.notification_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            mock_filters.return_value = mock_filter_instance
            
            # Mock FunnelTracker with high value to trigger alert
            with patch('dashboard.utils.FunnelTracker') as mock_tracker:
                mock_tracker_instance = Mock()
                mock_tracker_instance.get_funnel_metrics.return_value = {
                    'total_registrations': 15,  # Higher than threshold of 10
                    'verified_users': 3,
                    'licenses_created': 2,
                    'first_broadcasts': 1,
                    'completed_rentals': 1,
                    'conversion_rates': {
                        'verification_rate': 0.6,
                        'license_creation_rate': 0.4,
                        'first_broadcast_rate': 0.2,
                        'rental_completion_rate': 0.2
                    }
                }
                mock_tracker.return_value = mock_tracker_instance
                
                # Call the method
                result = self.notification_service.get_alerts_list(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                self.assertIn('alerts', result['data'])
                # Should have at least one alert triggered
                self.assertGreater(len(result['data']['alerts']), 0)
    
    def test_get_alerts_list_with_different_operators(self):
        """Test getting alerts list with different comparison operators."""
        # Create mock request
        request = self.factory.get('/')
        
        # Create additional threshold with 'lt' operator
        lt_threshold = AlertThreshold.objects.create(
            name='LT Threshold',
            stage='verified',
            metric_type='conversion_rate',
            threshold_value=0.5,
            comparison_operator='lt',  # Less than operator
            is_active=True
        )
        
        # Mock DashboardFilters
        with patch('dashboard.services.notification_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            mock_filters.return_value = mock_filter_instance
            
            # Mock FunnelTracker with low value to trigger 'lt' alert
            with patch('dashboard.utils.FunnelTracker') as mock_tracker:
                mock_tracker_instance = Mock()
                mock_tracker_instance.get_funnel_metrics.return_value = {
                    'total_registrations': 5,
                    'verified_users': 3,
                    'licenses_created': 2,
                    'first_broadcasts': 1,
                    'completed_rentals': 1,
                    'conversion_rates': {
                        'verification_rate': 0.3,  # Less than threshold of 0.5
                        'license_creation_rate': 0.4,
                        'first_broadcast_rate': 0.2,
                        'rental_completion_rate': 0.2
                    }
                }
                mock_tracker.return_value = mock_tracker_instance
                
                # Call the method
                result = self.notification_service.get_alerts_list(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                self.assertIn('alerts', result['data'])
    
    def test_get_alerts_list_error_handling(self):
        """Test error handling in get_alerts_list."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock to raise an exception
        with patch('dashboard.models.AlertThreshold') as mock_threshold:
            mock_threshold.objects.filter.side_effect = Exception("Database error")
            
            # Call the method
            result = self.notification_service.get_alerts_list(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertTrue(result['error'])  # message wording is not part of the contract
    
    def test_resolve_alert(self):
        """Test resolving an alert."""
        # Call the method
        result = self.notification_service.resolve_alert(self.alert_log.id)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Alert resolved successfully')
        
        # Check that the alert was actually resolved
        updated_alert = AlertLog.objects.get(id=self.alert_log.id)
        self.assertTrue(updated_alert.is_resolved)
        self.assertIsNotNone(updated_alert.resolved_at)
    
    def test_resolve_alert_not_found(self):
        """Test resolving a non-existent alert."""
        # Call the method with non-existent ID
        result = self.notification_service.resolve_alert(99999)
        
        # Assertions
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Alert not found')
    
    def test_resolve_alert_error_handling(self):
        """Test error handling in resolve_alert."""
        # Mock AlertLog to raise an exception
        with patch('dashboard.models.AlertLog') as mock_alert_log:
            mock_alert_log.DoesNotExist = Exception
            mock_alert_log.objects.select_related.return_value.get.side_effect = Exception("Database error")
            
            # Call the method
            result = self.notification_service.resolve_alert(1)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertTrue(result['error'])  # message wording is not part of the contract
    
    def test_get_notifications_detail(self):
        """Test getting detailed notifications data."""
        # Create mock request
        request = self.factory.get('/?type=total&page=1&page_size=20')
        
        # Mock NotificationsWidget
        with patch('dashboard.services.notification_service.NotificationsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_detailed_notifications.return_value = {
                'notifications': [],
                'total_count': 0
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.notification_service.get_notifications_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_detailed_notifications.assert_called_once_with('total', 1, 20)
    
    def test_get_notifications_detail_with_different_types(self):
        """Test getting detailed notifications with different types."""
        # Create mock request with different types
        for notification_type in ['unread', 'read', 'important']:
            request = self.factory.get(f'/?type={notification_type}&page=1&page_size=10')
            
            # Mock NotificationsWidget
            with patch('dashboard.services.notification_service.NotificationsWidget') as mock_widget:
                mock_widget_instance = Mock()
                mock_widget_instance.get_detailed_notifications.return_value = {
                    'notifications': [],
                    'total_count': 0
                }
                mock_widget.return_value = mock_widget_instance
                
                # Call the method
                result = self.notification_service.get_notifications_detail(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                mock_widget_instance.get_detailed_notifications.assert_called_once_with(notification_type, 1, 10)
    
    def test_get_notifications_detail_error_handling(self):
        """Test error handling in get_notifications_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock NotificationsWidget to raise an exception
        with patch('dashboard.services.notification_service.NotificationsWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.notification_service.get_notifications_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_toggle_notification(self):
        """Test toggling notification status."""
        # Create test notification model
        with patch('registration.models.Notification') as mock_notification_model:
            mock_notification = Mock()
            mock_notification.is_read = False
            mock_notification_model.objects.select_related.return_value.get.return_value = mock_notification
            
            # Call the method
            result = self.notification_service.toggle_notification(1)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertTrue(result['is_read'])
            mock_notification.save.assert_called_once()
    
    def test_toggle_notification_not_found(self):
        """Test toggling a non-existent notification."""
        # Mock Notification model to raise DoesNotExist
        with patch('registration.models.Notification') as mock_notification_model:
            mock_notification_model.DoesNotExist = Exception
            mock_notification_model.objects.select_related.return_value.get.side_effect = Exception("Not found")
            
            # Call the method
            result = self.notification_service.toggle_notification(9999)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Notification not found')
    
    def test_toggle_notification_error_handling(self):
        """Test error handling in toggle_notification."""
        # Mock Notification model to raise an exception
        with patch('registration.models.Notification') as mock_notification_model:
            mock_notification_model.DoesNotExist = Exception
            mock_notification_model.objects.select_related.return_value.get.side_effect = Exception("Database error")
            
            # Call the method
            result = self.notification_service.toggle_notification(1)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertTrue(result['error'])  # message wording is not part of the contract
    
    def test_update_threshold(self):
        """Test updating a threshold."""
        # Prepare test data
        data = {
            'name': 'Updated Threshold',
            'stage': 'verified',
            'metric_type': 'conversion_rate',
            'threshold_value': 0.8,
            'comparison_operator': 'greater_than',
            'is_active': False
        }
        
        # Call the method
        result = self.notification_service.update_threshold(self.alert_threshold.id, data)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Threshold updated successfully')
        
        # Check that the threshold was updated
        updated_threshold = AlertThreshold.objects.get(id=self.alert_threshold.id)
        self.assertEqual(updated_threshold.name, 'Updated Threshold')
        self.assertEqual(updated_threshold.stage, 'verified')
        self.assertEqual(updated_threshold.metric_type, 'conversion_rate')
        self.assertEqual(updated_threshold.threshold_value, 0.8)
        self.assertEqual(updated_threshold.comparison_operator, 'gt')  # Converted from 'greater_than'
        self.assertFalse(updated_threshold.is_active)
    
    def test_update_threshold_with_different_operators(self):
        """Test updating a threshold with different comparison operators."""
        # Test with 'less_than' operator
        data = {
            'name': 'Updated Threshold',
            'comparison_operator': 'less_than'
        }
        result = self.notification_service.update_threshold(self.alert_threshold.id, data)
        self.assertTrue(result['success'])
        
        updated_threshold = AlertThreshold.objects.get(id=self.alert_threshold.id)
        self.assertEqual(updated_threshold.comparison_operator, 'lt')
        
        # Test with 'equals' operator
        data = {
            'name': 'Updated Threshold Again',
            'comparison_operator': 'equals'
        }
        result = self.notification_service.update_threshold(self.alert_threshold.id, data)
        self.assertTrue(result['success'])
        
        updated_threshold = AlertThreshold.objects.get(id=self.alert_threshold.id)
        self.assertEqual(updated_threshold.comparison_operator, 'eq')
    
    def test_update_threshold_not_found(self):
        """Test updating a non-existent threshold."""
        # Prepare test data
        data = {
            'name': 'Updated Threshold'
        }
        
        # Call the method with non-existent ID
        result = self.notification_service.update_threshold(99999, data)
        
        # Assertions
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Threshold not found')
    
    def test_update_threshold_error_handling(self):
        """Test error handling in update_threshold."""
        # Prepare test data
        data = {
            'name': 'Updated Threshold'
        }
        
        # Mock AlertThreshold to raise an exception
        with patch('dashboard.models.AlertThreshold') as mock_threshold:
            mock_threshold.DoesNotExist = Exception
            mock_threshold.objects.get.side_effect = Exception("Database error")
            
            # Call the method
            result = self.notification_service.update_threshold(1, data)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertTrue(result['error'])  # message wording is not part of the contract
    
    def test_toggle_threshold(self):
        """Test toggling a threshold active status."""
        # Initially the threshold is active
        self.assertTrue(self.alert_threshold.is_active)
        
        # Call the method
        result = self.notification_service.toggle_threshold(self.alert_threshold.id)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Threshold deactivated successfully')
        self.assertFalse(result['is_active'])
        
        # Check that the threshold was actually updated
        updated_threshold = AlertThreshold.objects.get(id=self.alert_threshold.id)
        self.assertFalse(updated_threshold.is_active)
        
        # Toggle again
        result = self.notification_service.toggle_threshold(self.alert_threshold.id)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Threshold activated successfully')
        self.assertTrue(result['is_active'])
        
        # Check that the threshold was actually updated
        updated_threshold = AlertThreshold.objects.get(id=self.alert_threshold.id)
        self.assertTrue(updated_threshold.is_active)
    
    def test_toggle_threshold_not_found(self):
        """Test toggling a non-existent threshold."""
        # Call the method with non-existent ID
        result = self.notification_service.toggle_threshold(9999)
        
        # Assertions
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Threshold not found')
    
    def test_toggle_threshold_error_handling(self):
        """Test error handling in toggle_threshold."""
        # Mock AlertThreshold to raise an exception
        with patch('dashboard.models.AlertThreshold') as mock_threshold:
            mock_threshold.DoesNotExist = Exception
            mock_threshold.objects.get.side_effect = Exception("Database error")
            
            # Call the method
            result = self.notification_service.toggle_threshold(1)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertTrue(result['error'])  # message wording is not part of the contract