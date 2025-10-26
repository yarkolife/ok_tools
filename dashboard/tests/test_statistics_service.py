"""
Tests for StatisticsService in dashboard application.
"""

from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from registration.models import OKUser
from django.core.cache import cache

from registration.models import Profile, MediaAuthority
from licenses.models import License, Category as LicenseCategory
from contributions.models import Contribution
from projects.models import Project, ProjectLeader, TargetGroup, ProjectCategory
from inventory.models import InventoryItem, Category as InventoryCategory, Organization, Location

from dashboard.services.statistics_service import StatisticsService


class StatisticsServiceTestCase(TestCase):
    """Test cases for StatisticsService class."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.statistics_service = StatisticsService()
        
        # Create test user
        self.user = OKUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test media authority
        self.media_authority = MediaAuthority.objects.create(
            name='Test Media Authority'
        )
        
        # Create test profile
        self.profile = Profile.objects.create(
            okuser=self.user,
            first_name='John',
            last_name='Doe',
            gender='m',
            birthday=datetime(1990, 1, 1).date(),
            verified=True,
            member=True,
            media_authority=self.media_authority
        )
        
        # Create test license category
        self.license_category = LicenseCategory.objects.create(
            name='Test Category'
        )
        
        # Create test license
        self.license = License.objects.create(
            profile=self.profile,
            title='Test License',
            confirmed=True,
            category=self.license_category
        )
        
        # Create test contribution
        self.contribution = Contribution.objects.create(
            license=self.license,
            broadcast_date=timezone.now(),
            live=True
        )
        
        # Create test project
        self.project = Project.objects.create(
            title='Test Project',
            description='Test project description',
            date='2024-01-01',
            external_venue=False,
            jugendmedienschutz=False,
            democracy_project=False,
            project_leader=ProjectLeader.objects.create(name='Test Leader'),
            target_group=TargetGroup.objects.create(name='Test Group'),
            project_category=ProjectCategory.objects.create(name='Test Category')
        )
        
        # Create test organization
        self.organization = Organization.objects.create(
            name='Test Organization'
        )
        
        # Create test location
        self.location = Location.objects.create(
            name='Test Location'
        )
        
        # Create test inventory category
        self.inventory_category = InventoryCategory.objects.create(
            name='Test Inventory Category'
        )
        
        # Create test inventory item
        self.inventory_item = InventoryItem.objects.create(
            inventory_number='OK-001',
            description='Test Item',
            quantity=5,
            status='in_stock',
            available_for_rent=True,
            owner=self.organization,
            category=self.inventory_category,
            location=self.location
        )
    
    def test_get_licenses_statistics(self):
        """Test getting licenses statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock LicensesWidget
        with patch('dashboard.widgets.licenses.LicensesWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_data.return_value = {
                'total_licenses': 1,
                'confirmed_licenses': 1,
                'pending_licenses': 0
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_licenses_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_data.assert_called_once()
    
    def test_get_licenses_statistics_with_cache(self):
        """Test getting licenses statistics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"licenses_stats_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 1800)
        
        # Call the method
        result = self.statistics_service.get_licenses_statistics(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_licenses_statistics_error_handling(self):
        """Test error handling in get_licenses_statistics."""
        # Create mock request
        request = self.factory.get('/?unique_param=error_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock LicensesWidget to raise an exception during instantiation
        with patch('dashboard.widgets.licenses.LicensesWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_licenses_statistics(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
    
    def test_get_contributions_statistics(self):
        """Test getting contributions statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock ContributionsWidget
        with patch('dashboard.widgets.contributions.ContributionsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_data.return_value = {
                'total_contributions': 1,
                'live_contributions': 1
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_contributions_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_data.assert_called_once()
    
    def test_get_contributions_statistics_with_cache(self):
        """Test getting contributions statistics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"contributions_stats_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 1800)
        
        # Call the method
        result = self.statistics_service.get_contributions_statistics(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_projects_statistics(self):
        """Test getting projects statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock ProjectsWidget
        with patch('dashboard.widgets.projects.ProjectsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_data.return_value = {
                'total_projects': 1
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_projects_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_data.assert_called_once()
    
    def test_get_projects_statistics_with_cache(self):
        """Test getting projects statistics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"projects_stats_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 1800)
        
        # Call the method
        result = self.statistics_service.get_projects_statistics(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_filters_data(self):
        """Test getting filters data."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.widgets.filters.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.statistics_service.get_filters_data(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('context', result['data'])
            self.assertIn('filters', result['data'])
    
    def test_get_filters_data_with_model_errors(self):
        """Test getting filters data when models raise errors."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.widgets.filters.DashboardFilters') as mock_filters, \
             patch('registration.models.MediaAuthority') as mock_media_auth, \
             patch('licenses.models.Category') as mock_category, \
             patch('projects.models.ProjectCategory') as mock_proj_cat, \
             patch('projects.models.TargetGroup') as mock_target_group, \
             patch('projects.models.ProjectLeader') as mock_proj_leader, \
             patch('inventory.models.Category') as mock_inv_cat, \
             patch('inventory.models.Location') as mock_location, \
             patch('inventory.models.Organization') as mock_org:
            
            # Configure mocks to raise exceptions
            mock_media_auth.objects.all.side_effect = Exception("Database error")
            mock_category.objects.all.side_effect = Exception("Database error")
            mock_proj_cat.objects.all.side_effect = Exception("Database error")
            mock_target_group.objects.all.side_effect = Exception("Database error")
            mock_proj_leader.objects.all.side_effect = Exception("Database error")
            mock_inv_cat.objects.all.side_effect = Exception("Database error")
            mock_location.objects.all.side_effect = Exception("Database error")
            mock_org.objects.all.side_effect = Exception("Database error")
            
            mock_filter_instance = Mock()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.statistics_service.get_filters_data(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            # Should handle errors gracefully and return empty lists
            self.assertEqual(result['data']['context']['media_authorities'], [])
            self.assertEqual(result['data']['context']['category_choices'], [])
            self.assertEqual(result['data']['context']['project_categories'], [])
            self.assertEqual(result['data']['context']['target_groups'], [])
            self.assertEqual(result['data']['context']['project_leaders'], [])
    
    def test_get_filters_data_with_profile_errors(self):
        """Test getting filters data when Profile model raises errors."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock Profile model to raise error
        with patch('dashboard.widgets.filters.DashboardFilters') as mock_filters, \
             patch('registration.models.Profile') as mock_profile:
            
            mock_profile.Gender.choices.side_effect = Exception("Choices error")
            mock_filter_instance = Mock()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.statistics_service.get_filters_data(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            # Should handle errors gracefully and return default choices
            expected_default_choices = [
                ('m', 'Male'),
                ('f', 'Female'),
                ('d', 'Diverse')
            ]
            self.assertEqual(result['data']['context']['gender_choices'], expected_default_choices)
    
    def test_get_inventory_statistics(self):
        """Test getting inventory statistics."""
        # Create mock request with unique parameters to avoid cache
        request = self.factory.get('/?unique_param=inventory_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock after the import happens inside the method
        with patch('dashboard.services.statistics_service.DashboardFilters') as mock_filters, \
             patch('dashboard.services.statistics_service.InventoryWidget') as mock_widget:
            
            mock_filter_instance = Mock()
            mock_filters.return_value = mock_filter_instance
            
            mock_widget_instance = Mock()
            mock_widget_instance.get_all_data.return_value = {
                'total_items': 1,
                'in_stock_items': 1
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_inventory_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            # Verify DashboardFilters was created with request
            mock_filters.assert_called_once_with(request)
            # Verify widget was created with filters dict, not request
            mock_widget.assert_called_once()
            # Check that the first argument is a dict (filters)
            args, kwargs = mock_widget.call_args
            self.assertIsInstance(args[0], dict)
    
    def test_get_inventory_statistics_with_filters(self):
        """Test getting inventory statistics with various filters."""
        # Create mock request with filters
        request = self.factory.get('/?days=30&start_date=2023-01-01&end_date=2023-01-31&gender=m&member=true&category=1&owner=1&location=1&status=in_stock')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock after the import happens inside the method
        with patch('dashboard.services.statistics_service.DashboardFilters') as mock_filters, \
             patch('dashboard.services.statistics_service.InventoryWidget') as mock_widget:
            
            mock_filter_instance = Mock()
            mock_filters.return_value = mock_filter_instance
            
            mock_widget_instance = Mock()
            mock_widget_instance.get_all_data.return_value = {
                'total_items': 1,
                'in_stock_items': 1
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_inventory_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
    
    def test_get_inventory_statistics_with_cache(self):
        """Test getting inventory statistics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"inventory_stats_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 900)
        
        # Call the method
        result = self.statistics_service.get_inventory_statistics(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_inventory_statistics_error_handling(self):
        """Test error handling in get_inventory_statistics."""
        # Create mock request
        request = self.factory.get('/?unique_param=error_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock to raise an exception
        with patch('dashboard.services.statistics_service.DashboardFilters') as mock_filters:
            mock_filters.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_inventory_statistics(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_funnel_metrics(self):
        """Test getting funnel metrics."""
        # Create mock request
        request = self.factory.get('/?days=30')
        
        # Mock FunnelTracker
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_funnel_metrics.return_value = {
                'metrics': {
                    'registered_profiles': 10,
                    'verified_profiles': 8,
                    'licenses_created': 6,
                    'first_broadcasts': 4,
                    'rental_completed': 2
                },
                'conversion_rates': {
                    'verification_rate': 0.8,
                    'license_creation_rate': 0.75,
                    'first_broadcast_rate': 0.67,
                    'rental_completion_rate': 0.5
                }
            }
            mock_tracker_instance.get_stage_breakdown.return_value = []
            mock_tracker.return_value = mock_tracker_instance
            
            # Call the method
            result = self.statistics_service.get_funnel_metrics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('metrics', result['data'])
            self.assertIn('conversion_rates', result['data'])
            self.assertIn('funnel_data', result['data'])
    
    def test_get_funnel_metrics_with_cache(self):
        """Test getting funnel metrics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"funnel_metrics_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 1200)
        
        # Call the method
        result = self.statistics_service.get_funnel_metrics(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_funnel_metrics_with_different_date_ranges(self):
        """Test getting funnel metrics with different date ranges."""
        # Test with 'all' days
        request = self.factory.get('/?days=all')
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_funnel_metrics.return_value = {
                'metrics': {}, 'conversion_rates': {}
            }
            mock_tracker_instance.get_stage_breakdown.return_value = []
            mock_tracker.return_value = mock_tracker_instance
            
            result = self.statistics_service.get_funnel_metrics(request)
            self.assertTrue(result['success'])
        
        # Test with 'custom' days
        request = self.factory.get('/?days=custom&start_date=2023-01-01&end_date=2023-01-31')
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_funnel_metrics.return_value = {
                'metrics': {}, 'conversion_rates': {}
            }
            mock_tracker_instance.get_stage_breakdown.return_value = []
            mock_tracker.return_value = mock_tracker_instance
            
            result = self.statistics_service.get_funnel_metrics(request)
            self.assertTrue(result['success'])
    
    def test_get_funnel_metrics_error_handling(self):
        """Test error handling in get_funnel_metrics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock to raise an exception
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_funnel_metrics(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_funnel_breakdown(self):
        """Test getting funnel breakdown."""
        # Create mock request
        request = self.factory.get('/?start_date=2023-01-01&end_date=2023-01-31')
        
        # Mock FunnelTracker
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_stage_breakdown.return_value = {
                'registered': 10,
                'verified': 8,
                'license_created': 6
            }
            mock_tracker.return_value = mock_tracker_instance
            
            # Call the method
            result = self.statistics_service.get_funnel_breakdown(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('registered', result['data'])
    
    def test_get_funnel_breakdown_error_handling(self):
        """Test error handling in get_funnel_breakdown."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock to raise an exception
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_funnel_breakdown(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_funnel_trends(self):
        """Test getting funnel trends."""
        # Create mock request
        request = self.factory.get('/?days=30')
        
        # Mock FunnelTracker
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_funnel_trends.return_value = {
                'trend_data': []
            }
            mock_tracker.return_value = mock_tracker_instance
            
            # Call the method
            result = self.statistics_service.get_funnel_trends(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('trend_data', result['data'])
    
    def test_get_funnel_trends_with_filters(self):
        """Test getting funnel trends with various filters."""
        # Create mock request with filters
        request = self.factory.get('/?days=30&media_authority=1&gender=m&age_group=1&category=1&status=active')
        
        # Mock FunnelTracker
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_funnel_trends.return_value = {
                'trend_data': []
            }
            mock_tracker.return_value = mock_tracker_instance
            
            # Call the method
            result = self.statistics_service.get_funnel_trends(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
    
    def test_get_funnel_trends_error_handling(self):
        """Test error handling in get_funnel_trends."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock to raise an exception
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_funnel_trends(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_recent_licenses(self):
        """Test getting recent licenses."""
        # Create mock request
        request = self.factory.get('/?days=7')
        
        # Call the method
        result = self.statistics_service.get_recent_licenses(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertIn('activities', result['data'])
    
    def test_get_recent_licenses_with_different_days(self):
        """Test getting recent licenses with different day values."""
        # Test with different day values
        for days in [1, 7, 30, 90]:
            request = self.factory.get(f'/?days={days}')
            result = self.statistics_service.get_recent_licenses(request)
            self.assertTrue(result['success'])
    
    def test_get_recent_licenses_error_handling(self):
        """Test error handling in get_recent_licenses."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock License model to raise an exception
        with patch('licenses.models.License') as mock_license:
            mock_license.objects.filter.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_recent_licenses(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_system_status(self):
        """Test getting system status."""
        # Create mock request
        request = self.factory.get('/')
        
        # Call the method
        result = self.statistics_service.get_system_status(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertIn('overall_status', result['data'])
        self.assertIn('checks', result['data'])
        self.assertIn('database', result['data']['checks'])
        self.assertIn('api_services', result['data']['checks'])
        self.assertIn('file_storage', result['data']['checks'])
        self.assertIn('email_service', result['data']['checks'])
    
    def test_get_system_status_database_error(self):
        """Test system status with database error."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock database connection to raise an exception
        with patch('django.db.connection.cursor') as mock_cursor:
            mock_cursor.side_effect = Exception("Database error")
            
            # Call the method
            result = self.statistics_service.get_system_status(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('checks', result['data'])
            self.assertEqual(result['data']['checks']['database']['status'], 'error')
    
    def test_get_system_status_file_storage_error(self):
        """Test system status with file storage error."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock file storage to raise an exception
        with patch('django.core.files.storage.default_storage') as mock_storage, \
             patch('django.core.files.base.ContentFile') as mock_content_file:
            
            mock_storage.exists.return_value = True
            mock_storage.save.side_effect = Exception("Storage error")
            
            # Call the method
            result = self.statistics_service.get_system_status(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('checks', result['data'])
            self.assertEqual(result['data']['checks']['file_storage']['status'], 'error')
    
    def test_get_system_status_email_service_warning(self):
        """Test system status with email service in development mode."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock settings to have console backend
        with patch('django.conf.settings') as mock_settings:
            type(mock_settings).EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
            type(mock_settings).EMAIL_HOST = None
            type(mock_settings).EMAIL_PORT = None
            type(mock_settings).EMAIL_HOST_USER = None
            
            # Call the method
            result = self.statistics_service.get_system_status(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('checks', result['data'])
            self.assertEqual(result['data']['checks']['email_service']['status'], 'warning')
    
    def test_get_system_status_error_handling(self):
        """Test error handling in get_system_status."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock to raise an exception
        with patch('django.db.connection') as mock_connection:
            mock_connection.cursor.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_system_status(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_quick_stats(self):
        """Test getting quick statistics."""
        # Create mock request with unique parameters to avoid cache
        request = self.factory.get('/?unique_param=quick_stats_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock after the import happens inside the method
        with patch('dashboard.services.statistics_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            
            # Mock apply_filters_to_queryset to return appropriate querysets based on model type
            def mock_apply_filters(queryset, model_type):
                if model_type == 'profile':
                    return Profile.objects.all()
                elif model_type == 'license':
                    return License.objects.all()
                elif model_type == 'contribution':
                    return Contribution.objects.all()
                return queryset
            
            mock_filter_instance.apply_filters_to_queryset.side_effect = mock_apply_filters
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.statistics_service.get_quick_stats(request)
            
            # Debug output
            print(f"Result: {result}")
            if not result['success']:
                print(f"Error: {result.get('error', 'Unknown error')}")
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('active_users', result['data'])
            self.assertIn('confirmed_licenses', result['data'])
            self.assertIn('live_contributions', result['data'])
            self.assertIn('pending_licenses', result['data'])
            # Verify DashboardFilters was created with request
            mock_filters.assert_called_once_with(request)
    
    def test_get_quick_stats_with_cache(self):
        """Test getting quick statistics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"quick_stats_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 600)
        
        # Call the method
        result = self.statistics_service.get_quick_stats(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_quick_stats_with_import_error(self):
        """Test getting quick statistics when models raise import errors."""
        # Create mock request
        request = self.factory.get('/?unique_param=import_error_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock after the import happens inside the method
        with patch('dashboard.services.statistics_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            
            # Mock apply_filters_to_queryset to raise ImportError for licenses/contributions
            def mock_apply_filters(queryset, model_type):
                if model_type == 'profile':
                    return Profile.objects.all()
                elif model_type == 'license':
                    raise ImportError("Module not found")
                elif model_type == 'contribution':
                    raise ImportError("Module not found")
                return queryset
            
            mock_filter_instance.apply_filters_to_queryset.side_effect = mock_apply_filters
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.statistics_service.get_quick_stats(request)
            
            # Assertions - should handle import errors gracefully
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('active_users', result['data'])
    
    def test_get_quick_stats_error_handling(self):
        """Test error handling in get_quick_stats."""
        # Create mock request
        request = self.factory.get('/?unique_param=error_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock to raise an exception
        with patch('dashboard.services.statistics_service.DashboardFilters') as mock_filters:
            mock_filters.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_quick_stats(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_licenses_detail(self):
        """Test getting detailed licenses data."""
        # Create mock request
        request = self.factory.get('/?page=1&per_page=20&type=total')
        
        # Mock LicensesWidget
        with patch('dashboard.widgets.licenses.LicensesWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_detailed_data.return_value = {
                'licenses': [],
                'total_count': 0
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_licenses_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_detailed_data.assert_called_once_with(page=1, per_page=20, type_filter='total')
    
    def test_get_licenses_detail_with_different_types(self):
        """Test getting detailed licenses data with different types."""
        # Test with different types
        for license_type in ['confirmed', 'pending', 'all']:
            request = self.factory.get(f'/?page=1&per_page=20&type={license_type}')
            
            # Mock LicensesWidget
            with patch('dashboard.widgets.licenses.LicensesWidget') as mock_widget:
                mock_widget_instance = Mock()
                mock_widget_instance.get_detailed_data.return_value = {
                    'licenses': [],
                    'total_count': 0
                }
                mock_widget.return_value = mock_widget_instance
                
                # Call the method
                result = self.statistics_service.get_licenses_detail(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                mock_widget_instance.get_detailed_data.assert_called_once_with(page=1, per_page=20, type_filter=license_type)
    
    def test_get_licenses_detail_error_handling(self):
        """Test error handling in get_licenses_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock LicensesWidget to raise an exception
        with patch('dashboard.widgets.licenses.LicensesWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_licenses_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_contributions_detail(self):
        """Test getting detailed contributions data."""
        # Create mock request
        request = self.factory.get('/?type=total&page=1&per_page=20')
        
        # Mock ContributionsWidget
        with patch('dashboard.widgets.contributions.ContributionsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_detailed_contributions.return_value = {
                'contributions': [],
                'total_count': 0
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_contributions_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            mock_widget_instance.get_detailed_contributions.assert_called_once_with('total', 1, 20)
    
    def test_get_contributions_detail_with_different_types(self):
        """Test getting detailed contributions data with different types."""
        # Test with different types
        for contrib_type in ['live', 'draft', 'archived', 'all']:
            request = self.factory.get(f'/?type={contrib_type}&page=1&per_page=20')
            
            # Mock ContributionsWidget
            with patch('dashboard.widgets.contributions.ContributionsWidget') as mock_widget:
                mock_widget_instance = Mock()
                mock_widget_instance.get_detailed_contributions.return_value = {
                    'contributions': [],
                    'total_count': 0
                }
                mock_widget.return_value = mock_widget_instance
                
                # Call the method
                result = self.statistics_service.get_contributions_detail(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                mock_widget_instance.get_detailed_contributions.assert_called_once_with(contrib_type, 1, 20)
    
    def test_get_contributions_detail_error_handling(self):
        """Test error handling in get_contributions_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock ContributionsWidget to raise an exception
        with patch('dashboard.widgets.contributions.ContributionsWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_contributions_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_projects_detail(self):
        """Test getting detailed projects data."""
        # Create mock request
        request = self.factory.get('/?type=total&page=1&per_page=20')
        
        # Mock ProjectsWidget
        with patch('dashboard.widgets.projects.ProjectsWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_detailed_projects.return_value = {
                'projects': [],
                'total_count': 0
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_projects_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
    
    def test_get_projects_detail_with_different_types(self):
        """Test getting detailed projects data with different types."""
        # Test with different types
        for proj_type in ['total', 'participants', 'average', 'external', 'youth_protection', 'democracy']:
            request = self.factory.get(f'/?type={proj_type}&page=1&per_page=20')
            
            # Mock ProjectsWidget
            with patch('dashboard.widgets.projects.ProjectsWidget') as mock_widget:
                mock_widget_instance = Mock()
                
                if proj_type == 'total':
                    mock_widget_instance.get_detailed_projects.return_value = {
                        'projects': [],
                        'total_count': 0
                    }
                    expected_call = 'get_detailed_projects'
                elif proj_type == 'participants':
                    mock_widget_instance.get_detailed_projects_by_participants.return_value = {
                        'projects': [],
                        'total_count': 0
                    }
                    expected_call = 'get_detailed_projects_by_participants'
                elif proj_type == 'average':
                    mock_widget_instance.get_detailed_projects_by_average_participants.return_value = {
                        'projects': [],
                        'total_count': 0
                    }
                    expected_call = 'get_detailed_projects_by_average_participants'
                else:
                    mock_widget_instance.get_detailed_projects.return_value = {
                        'projects': [],
                        'total_count': 0
                    }
                    expected_call = 'get_detailed_projects'
                
                mock_widget.return_value = mock_widget_instance
                
                # Call the method
                result = self.statistics_service.get_projects_detail(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
    
    def test_get_projects_detail_error_handling(self):
        """Test error handling in get_projects_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock ProjectsWidget to raise an exception
        with patch('dashboard.widgets.projects.ProjectsWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_projects_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_inventory_detail(self):
        """Test getting detailed inventory data."""
        # Create mock request with unique parameters to avoid cache
        request = self.factory.get('/?type=total&page=1&per_page=20&unique_param=inventory_detail_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock after the import happens inside the method
        with patch('dashboard.services.statistics_service.InventoryWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_detailed_inventory.return_value = {
                'items': [],
                'total_count': 0
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_inventory_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            # Verify widget was created with filters dict
            mock_widget.assert_called_once()
            args, kwargs = mock_widget.call_args
            self.assertIsInstance(args[0], dict)
            # Verify method was called with correct parameters
            mock_widget_instance.get_detailed_inventory.assert_called_once_with('total', 1, 20)
    
    def test_get_inventory_detail_with_different_types(self):
        """Test getting detailed inventory data with different types."""
        # Test with different types
        for inv_type in ['total', 'in_stock', 'out_of_stock', 'available', 'rented']:
            request = self.factory.get(f'/?type={inv_type}&page=1&per_page=20')
            
            # Mock InventoryWidget
            with patch('dashboard.services.statistics_service.InventoryWidget') as mock_widget:
                mock_widget_instance = Mock()
                mock_widget_instance.get_detailed_inventory.return_value = {
                    'items': [],
                    'total_count': 0
                }
                mock_widget.return_value = mock_widget_instance
                
                # Call the method
                result = self.statistics_service.get_inventory_detail(request)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                mock_widget_instance.get_detailed_inventory.assert_called_once_with(inv_type, 1, 20)
    
    def test_get_inventory_detail_error_handling(self):
        """Test error handling in get_inventory_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock InventoryWidget to raise an exception
        with patch('dashboard.services.statistics_service.InventoryWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_inventory_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_funnel_detail(self):
        """Test getting funnel detail data."""
        # Create mock request
        request = self.factory.get('/?type=registrations&page=1&per_page=20')
        
        # Mock FunnelTracker
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker_instance.get_registrations_detail.return_value = {
                'registrations': [],
                'total_count': 0
            }
            mock_tracker.return_value = mock_tracker_instance
            
            # Call the method
            result = self.statistics_service.get_funnel_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
    
    def test_get_funnel_detail_with_different_types(self):
        """Test getting funnel detail data with different types."""
        # Test with different types
        for funnel_type in ['registrations', 'verified', 'licenses', 'broadcasts']:
            request = self.factory.get(f'/?type={funnel_type}&page=1&per_page=20')
            
            # Mock FunnelTracker
            with patch('dashboard.utils.FunnelTracker') as mock_tracker:
                mock_tracker_instance = Mock()
                
                if funnel_type == 'registrations':
                    mock_method = 'get_registrations_detail'
                elif funnel_type == 'verified':
                    mock_method = 'get_verified_detail'
                elif funnel_type == 'licenses':
                    mock_method = 'get_licenses_detail'
                elif funnel_type == 'broadcasts':
                    mock_method = 'get_broadcasts_detail'
                
                # Set return value for the appropriate method
                setattr(mock_tracker_instance, mock_method, Mock(return_value={
                    'data': [],
                    'total_count': 0
                }))
                
                mock_tracker.return_value = mock_tracker_instance
                
                # Call the method
                result = self.statistics_service.get_funnel_detail(request)
                
                # Assertions
                self.assertTrue(result['success'] if funnel_type != 'invalid' else False)
    
    def test_get_funnel_detail_with_invalid_type(self):
        """Test getting funnel detail with invalid type."""
        # Create mock request with invalid type
        request = self.factory.get('/?type=invalid&page=1&per_page=20')
        
        # Call the method
        result = self.statistics_service.get_funnel_detail(request)
        
        # Assertions
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Invalid type filter')
    
    def test_get_funnel_detail_error_handling(self):
        """Test error handling in get_funnel_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock FunnelTracker to raise an exception
        with patch('dashboard.utils.FunnelTracker') as mock_tracker:
            mock_tracker.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_funnel_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_media_data_statistics(self):
        """Test getting media data statistics."""
        # Create mock request with unique parameters to avoid cache
        request = self.factory.get('/?unique_param=media_data_test')
        
        # Clear cache to ensure fresh execution
        cache.clear()
        
        # Mock after the import happens inside the method
        with patch('dashboard.services.statistics_service.MediaDataWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_all_data.return_value = {
                'media_data': [],
                'filters': {'context': {}}
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_media_data_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            # Verify widget was created with request
            mock_widget.assert_called_once_with(request)
            mock_widget_instance.get_all_data.assert_called_once()
    
    def test_get_media_data_statistics_with_cache(self):
        """Test getting media data statistics with cache."""
        # Create mock request
        request = self.factory.get('/?param=test')
        
        # Calculate cache key the same way as in the service
        cache_key = f"media_data_stats_{hash(str(request.GET))}"
        cached_result = {
            'success': True,
            'data': {'cached': True}
        }
        cache.set(cache_key, cached_result, 1500)
        
        # Call the method
        result = self.statistics_service.get_media_data_statistics(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'cached': True})
    
    def test_get_media_data_statistics_with_categories(self):
        """Test getting media data statistics with categories."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock MediaDataWidget
        with patch('dashboard.widgets.media_data.MediaDataWidget') as mock_widget:
            mock_widget_instance = Mock()
            mock_widget_instance.get_all_data.return_value = {
                'filters': {'context': {}}
            }
            mock_widget.return_value = mock_widget_instance
            
            # Call the method
            result = self.statistics_service.get_media_data_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('data', result)
            self.assertIn('filters', result['data'])
    
    def test_get_media_data_statistics_error_handling(self):
        """Test error handling in get_media_data_statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock MediaDataWidget to raise an exception
        with patch('dashboard.widgets.media_data.MediaDataWidget') as mock_widget:
            mock_widget.side_effect = Exception("Test error")
            
            # Call the method
            result = self.statistics_service.get_media_data_statistics(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')