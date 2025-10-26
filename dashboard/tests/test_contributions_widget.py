"""
Unit tests for dashboard/widgets/contributions.py
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth.models import User
from dashboard.widgets.contributions import (
    BaseContributionCache,
    ContributionQuerySet,
    ContributionBasicStats,
    ContributionMetrics,
    ContributionDataGrouping,
    ContributionDetailedData,
    ContributionsWidget
)
from dashboard.widgets.filters import DashboardFilters
from contributions.models import Contribution
from licenses.models import License
from registration.models import Profile


class TestBaseContributionCache(TestCase):
    """Test BaseContributionCache class"""
    
    def setUp(self):
        self.cache_manager = BaseContributionCache(cache_timeout=300)
    
    @patch('dashboard.widgets.contributions.cache')
    def test_get_cache_key(self, mock_cache):
        """Test cache key generation"""
        filters = {'test': 'value'}
        key = self.cache_manager._get_cache_key('test_method', filters)
        self.assertTrue(key.startswith('contributions:test_method:'))
    
    @patch('dashboard.widgets.contributions.cache')
    def test_get_cached_result(self, mock_cache):
        """Test getting cached result"""
        mock_cache.get.return_value = {'cached': 'result'}
        filters = {'test': 'value'}
        
        result = self.cache_manager._get_cached_result('test_method', filters)
        
        self.assertEqual(result, {'cached': 'result'})
        mock_cache.get.assert_called_once()
    
    @patch('dashboard.widgets.contributions.cache')
    def test_set_cached_result(self, mock_cache):
        """Test setting cached result"""
        filters = {'test': 'value'}
        result = {'test': 'result'}
        
        self.cache_manager._set_cached_result('test_method', filters, result)
        
        mock_cache.set.assert_called_once()


class TestContributionQuerySet(TestCase):
    """Test ContributionQuerySet class"""
    
    def setUp(self):
        # Create a mock request and filters
        self.mock_request = Mock()
        self.mock_request.GET = {}
        self.filters = DashboardFilters(self.mock_request)
        self.queryset_manager = ContributionQuerySet(self.filters)
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_filtered_queryset(self, mock_contribution_model):
        """Test getting filtered queryset"""
        mock_queryset = Mock()
        mock_contribution_model.objects.all.return_value = mock_queryset
        mock_queryset.filter.return_value = mock_queryset
        
        result = self.queryset_manager.get_filtered_queryset()
        
        self.assertEqual(result, mock_queryset)
    
    def test_get_license_ids_from_queryset(self):
        """Test getting license IDs from queryset"""
        # Create a mock queryset with license IDs
        mock_queryset = Mock()
        mock_values_queryset = Mock()
        mock_values_queryset.distinct.return_value = [1, 2, 3]
        mock_queryset.values_list.return_value = mock_values_queryset
        
        result = self.queryset_manager.get_license_ids_from_queryset(mock_queryset)
        
        self.assertEqual(result, [1, 2, 3])
        mock_queryset.values_list.assert_called_once_with('license_id', flat=True)
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_primary_dates_for_licenses(self, mock_contribution_model):
        """Test getting primary dates for licenses"""
        mock_queryset = Mock()
        mock_contribution_model.objects.filter.return_value = mock_queryset
        
        # Mock the annotate result
        mock_values_queryset = Mock()
        mock_aggregate_result = [{'license': 1, 'min_date': timezone.now()}]
        mock_values_queryset.annotate.return_value = mock_aggregate_result
        mock_queryset.values.return_value = mock_values_queryset
        
        result = self.queryset_manager.get_primary_dates_for_licenses([1])
        
        self.assertEqual(len(result), 1)
        self.assertIn(1, result)


class TestContributionBasicStats(TestCase):
    """Test ContributionBasicStats class"""
    
    def setUp(self):
        # Create a mock request and filters
        self.mock_request = Mock()
        self.mock_request.GET = {}
        self.filters = DashboardFilters(self.mock_request)
        
        # Create mock cache and queryset managers
        self.mock_cache_manager = Mock()
        self.mock_queryset_manager = Mock()
        self.mock_queryset_manager.filters = self.filters
        
        self.basic_stats = ContributionBasicStats(
            self.mock_cache_manager,
            self.mock_queryset_manager
        )
    
    @patch('dashboard.widgets.contributions.cache')
    def test_get_basic_stats_cached(self, mock_cache):
        """Test getting basic stats with cached result"""
        # Mock cached result exists
        cached_result = {
            'total_contributions': 100,
            'live_contributions': 60,
            'recorded_contributions': 40,
            'primary_contributions': 30,
            'repetition_contributions': 70,
        }
        self.mock_cache_manager._get_cached_result.return_value = cached_result
        
        result = self.basic_stats.get_basic_stats()
        
        self.assertEqual(result, cached_result)
        self.mock_cache_manager._get_cached_result.assert_called_once()
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_basic_stats_not_cached(self, mock_contribution_model):
        """Test getting basic stats without cached result"""
        # Mock no cached result
        self.mock_cache_manager._get_cached_result.return_value = None
        
        # Create a proper mock queryset that returns integer values for count
        mock_filtered_queryset = Mock()
        # Set up the count method to return an integer directly
        type(mock_filtered_queryset).count = Mock(return_value=100)
        
        # Since the implementation calls select_related, we need to make sure that returns the same mock
        mock_filtered_queryset.select_related.return_value = mock_filtered_queryset
        
        # Make sure the queryset manager returns our mock
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        
        # Create separate mock objects for live and recorded filters
        mock_filtered_live = Mock()
        type(mock_filtered_live).count = Mock(return_value=60)  # live
        mock_filtered_recorded = Mock()
        type(mock_filtered_recorded).count = Mock(return_value=40)  # recorded
        mock_filtered_queryset.filter.side_effect = [mock_filtered_live, mock_filtered_recorded]
        
        # Mock license IDs and primary dates
        self.mock_queryset_manager.get_license_ids_from_queryset.return_value = [1, 2, 3]
        self.mock_queryset_manager.get_primary_dates_for_licenses.return_value = {1: timezone.now()}
        self.mock_queryset_manager.count_primary_contributions.return_value = 30
        
        result = self.basic_stats.get_basic_stats()
        
        self.mock_cache_manager._get_cached_result.assert_called_once()
        self.mock_cache_manager._set_cached_result.assert_called_once()
        self.assertEqual(result['total_contributions'], 100)
        self.assertEqual(result['primary_contributions'], 30)
    
    def test_get_live_vs_recorded(self):
        """Test getting live vs recorded stats"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        mock_filtered_queryset.count.return_value = 100
        
        # Create separate mock objects for live and recorded filters
        mock_filtered_live = Mock()
        mock_filtered_live.count.return_value = 60  # live
        mock_filtered_recorded = Mock()
        mock_filtered_recorded.count.return_value = 40  # recorded
        mock_filtered_queryset.filter.side_effect = [mock_filtered_live, mock_filtered_recorded]
        
        # Fix the issue where total_contributions is a Mock object instead of an integer
        mock_filtered_queryset.count.return_value = 100
        
        result = self.basic_stats.get_live_vs_recorded()
        
        self.assertEqual(result['total'], 100)
        self.assertEqual(result['live'], 60)
        self.assertEqual(result['recorded'], 40)
        self.assertEqual(result['live_percentage'], 60.0)
        self.assertEqual(result['recorded_percentage'], 40.0)
    
    def test_get_primary_vs_repetitions(self):
        """Test getting primary vs repetitions stats"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        mock_filtered_queryset.count.return_value = 100
        
        # Mock license IDs and primary dates
        self.mock_queryset_manager.get_license_ids_from_queryset.return_value = [1, 2, 3]
        self.mock_queryset_manager.get_primary_dates_for_licenses.return_value = {1: timezone.now()}
        self.mock_queryset_manager.count_primary_contributions.return_value = 30
        
        result = self.basic_stats.get_primary_vs_repetitions()
        
        self.assertEqual(result['total'], 100)
        self.assertEqual(result['primary'], 30)
        self.assertEqual(result['repetition'], 70)
        self.assertEqual(result['primary_percentage'], 30.0)
        self.assertEqual(result['repetition_percentage'], 70.0)


class TestContributionMetrics(TestCase):
    """Test ContributionMetrics class"""
    
    def setUp(self):
        # Create a mock request and filters
        self.mock_request = Mock()
        self.mock_request.GET = {}
        self.filters = DashboardFilters(self.mock_request)
        
        # Create mock cache and queryset managers
        self.mock_cache_manager = Mock()
        self.mock_queryset_manager = Mock()
        self.mock_queryset_manager.filters = self.filters
        
        self.metrics = ContributionMetrics(
            self.mock_cache_manager,
            self.mock_queryset_manager
        )
    
    @patch('dashboard.widgets.contributions.cache')
    def test_get_unified_metrics_cached(self, mock_cache):
        """Test getting unified metrics with cached result"""
        cached_result = {
            'total_contributions': 100,
            'live_contributions': 60,
            'recorded_contributions': 40,
            'unique_licenses': 50,
            'primary_contributions': 30,
            'repetitions': 70,
            'conversion_rate': 60.0,
            'archive_licenses': 10,
            'active_licenses': 30,
            'recent_licenses': 10,
            'archive_rate': 10.0
        }
        self.mock_cache_manager._get_cached_result.return_value = cached_result
        
        result = self.metrics.get_unified_metrics()
        
        self.assertEqual(result, cached_result)
        self.mock_cache_manager._get_cached_result.assert_called_once()
    
    @patch('licenses.models.License')
    @patch('dashboard.widgets.contributions.timezone')
    def test_get_unified_metrics_not_cached(self, mock_timezone, mock_license_model):
        """Test getting unified metrics without cached result"""
        # Mock no cached result
        self.mock_cache_manager._get_cached_result.return_value = None
        
        # Mock filtered contributions
        mock_filtered_contributions = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_contributions
        mock_filtered_contributions.count.return_value = 100
        
        # Create separate mock objects for live and recorded filters
        mock_filtered_live = Mock()
        mock_filtered_live.count.return_value = 60  # live
        mock_filtered_recorded = Mock()
        mock_filtered_recorded.count.return_value = 40  # recorded
        mock_filtered_contributions.filter.side_effect = [mock_filtered_live, mock_filtered_recorded]
        
        # Mock license IDs - this method returns a list of IDs, but in the code it's used differently
        # Looking at the error, the issue is that in the original code, license_ids_in_period is used as a queryset in some places
        # Let's mock it properly to return a queryset that also behaves as a list when needed
        mock_license_ids_queryset = Mock()
        mock_license_ids_queryset.count.return_value = 3  # unique licenses count
        mock_license_ids_queryset.__iter__ = Mock(return_value=iter([1, 2, 3]))  # for iteration
        self.mock_queryset_manager.get_license_ids_from_queryset.return_value = mock_license_ids_queryset
        
        # Mock primary dates
        self.mock_queryset_manager.get_primary_dates_for_licenses.return_value = {1: timezone.now()}
        self.mock_queryset_manager.count_primary_contributions.return_value = 30
        
        # Mock licenses dict
        mock_license1 = Mock()
        mock_license1.id = 1
        mock_license1.created_at = timezone.now()
        mock_license_model.objects.filter.return_value.only.return_value = [mock_license1]
        
        # Mock timezone operations
        mock_timezone.now.return_value = timezone.now()
        mock_timezone.make_aware = lambda x: x
        
        result = self.metrics.get_unified_metrics()
        
        self.mock_cache_manager._get_cached_result.assert_called_once()
        self.mock_cache_manager._set_cached_result.assert_called_once()
        self.assertEqual(result['total_contributions'], 100)
        self.assertEqual(result['primary_contributions'], 30)


class TestContributionDataGrouping(TestCase):
    """Test ContributionDataGrouping class"""
    
    def setUp(self):
        # Create a mock request and filters
        self.mock_request = Mock()
        self.mock_request.GET = {}
        self.filters = DashboardFilters(self.mock_request)
        
        # Create mock cache and queryset managers
        self.mock_cache_manager = Mock()
        self.mock_queryset_manager = Mock()
        self.mock_queryset_manager.filters = self.filters
        
        self.data_grouping = ContributionDataGrouping(
            self.mock_cache_manager,
            self.mock_queryset_manager
        )
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_contributions_by_authority(self, mock_contribution_model):
        """Test getting contributions by authority"""
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        mock_filtered_queryset.select_related.return_value = mock_filtered_queryset
        
        # Mock the values() call chain properly
        mock_values_queryset = Mock()
        mock_annotated_result = [{'license__profile__media_authority__name': 'Test Authority', 'count': 5}]
        mock_values_queryset.annotate.return_value = mock_values_queryset
        mock_values_queryset.order_by.return_value = mock_annotated_result
        mock_filtered_queryset.values.return_value = mock_values_queryset
        
        result = self.data_grouping.get_contributions_by_authority()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['license__profile__media_authority__name'], 'Test Authority')
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_contributions_by_category(self, mock_contribution_model):
        """Test getting contributions by category"""
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        mock_filtered_queryset.select_related.return_value = mock_filtered_queryset
        
        # Mock the values() call chain properly
        mock_values_queryset = Mock()
        mock_annotated_result = [{'license__category__name': 'Test Category', 'count': 3}]
        mock_values_queryset.annotate.return_value = mock_values_queryset
        mock_values_queryset.order_by.return_value = mock_annotated_result
        mock_filtered_queryset.values.return_value = mock_values_queryset
        
        result = self.data_grouping.get_contributions_by_category()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['license__category__name'], 'Test Category')
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_contributions_by_gender(self, mock_contribution_model):
        """Test getting contributions by gender"""
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        
        # Mock the values() call chain properly
        mock_values_queryset = Mock()
        mock_annotated_result = [{'license__profile__gender': 'M', 'count': 2}]
        mock_values_queryset.annotate.return_value = mock_values_queryset
        mock_values_queryset.order_by.return_value = mock_annotated_result
        mock_filtered_queryset.values.return_value = mock_values_queryset
        
        result = self.data_grouping.get_contributions_by_gender()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['license__profile__gender'], 'M')
    
    def test_get_contributions_by_age(self):
        """Test getting contributions by age"""
        # Create a mock filtered queryset with contributions
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        mock_filtered_queryset.select_related.return_value = mock_filtered_queryset
        mock_filtered_queryset.only.return_value = mock_filtered_queryset
        
        # Create a mock contribution with a profile that has a birthday
        mock_contribution = Mock()
        mock_license = Mock()
        mock_profile = Mock()
        mock_profile.birthday = timezone.now().date() - timedelta(days=365*25)  # 25 years old
        mock_license.profile = mock_profile
        mock_contribution.license = mock_license
        
        # Mock iterator to return the contribution
        mock_filtered_queryset.iterator.return_value = [mock_contribution]
        
        # Mock the date range for age calculation
        with patch.object(self.data_grouping.queryset_manager.filters, 'date_range',
                         {'start_date': timezone.now().date(), 'end_date': timezone.now().date()}):
            result = self.data_grouping.get_contributions_by_age()
        
        # Check that the 25-year-old falls into the '18_25' category (this will be 0 since age is calculated differently)
        # Actually, 25 years old should fall into '18_25' category, so let's fix the age
        # The age is calculated using relativedelta(self.queryset_manager.filters.date_range['end_date'], contribution.license.profile.birthday).years
        # So we need to make sure the calculation matches
        self.assertEqual(result['18_25'], 1)
        self.assertEqual(result['under_18'], 0)
        self.assertEqual(result['26_35'], 0)
        self.assertEqual(result['36_50'], 0)
        self.assertEqual(result['over_50'], 0)


class TestContributionDetailedData(TestCase):
    """Test ContributionDetailedData class"""
    
    def setUp(self):
        # Create a mock request and filters
        self.mock_request = Mock()
        self.mock_request.GET = {}
        self.filters = DashboardFilters(self.mock_request)
        
        # Create mock cache and queryset managers
        self.mock_cache_manager = Mock()
        self.mock_queryset_manager = Mock()
        self.mock_queryset_manager.filters = self.filters
        
        self.detailed_data = ContributionDetailedData(
            self.mock_cache_manager,
            self.mock_queryset_manager
        )
    
    def test_format_duration(self):
        """Test formatting duration"""
        from datetime import timedelta
        
        # Test with a duration
        duration = timedelta(hours=2, minutes=30, seconds=45)
        result = self.detailed_data.format_duration(duration)
        self.assertEqual(result, "02:30:45")
        
        # Test with None
        result = self.detailed_data.format_duration(None)
        self.assertEqual(result, "00:00:00")
        
        # Test with zero duration
        duration = timedelta(seconds=0)
        result = self.detailed_data.format_duration(duration)
        self.assertEqual(result, "00:00:00")
    
    @patch('dashboard.widgets.contributions.Contribution')
    def test_get_broadcast_hours(self, mock_contribution_model):
        """Test getting broadcast hours"""
        mock_filtered_queryset = Mock()
        self.mock_queryset_manager.get_filtered_queryset.return_value = mock_filtered_queryset
        
        # Create a mock contribution with broadcast date
        mock_contribution = Mock()
        mock_contribution.broadcast_date = timezone.now().replace(hour=14)
        
        mock_filtered_queryset.iterator.return_value = [mock_contribution]
        
        result = self.detailed_data.get_broadcast_hours()
        
        # Should have 24 entries, one for each hour
        self.assertEqual(len(result), 24)
        # Hour 14 should have count of 1
        hour_14 = next((item for item in result if item['hour'] == 14), None)
        self.assertIsNotNone(hour_14)
        self.assertEqual(hour_14['count'], 1)


class TestContributionsWidget(TestCase):
    """Test ContributionsWidget class"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/dashboard/')
        self.widget = ContributionsWidget(self.request)
    
    @patch('dashboard.widgets.contributions.ContributionMetrics')
    def test_get_unified_metrics(self, mock_metrics_class):
        """Test getting unified metrics"""
        mock_metrics_instance = Mock()
        mock_metrics_class.return_value = mock_metrics_instance
        mock_metrics_instance.get_unified_metrics.return_value = {'test': 'data'}
        
        # We need to recreate the widget to use the patched class
        widget = ContributionsWidget(self.request)
        # Replace the metrics instance with our mock
        widget.metrics = mock_metrics_instance
        
        result = widget.get_unified_metrics()
        
        self.assertEqual(result, {'test': 'data'})
        mock_metrics_instance.get_unified_metrics.assert_called_once()
    
    @patch('dashboard.widgets.contributions.ContributionBasicStats')
    def test_get_basic_stats(self, mock_basic_stats_class):
        """Test getting basic stats"""
        mock_basic_stats_instance = Mock()
        mock_basic_stats_class.return_value = mock_basic_stats_instance
        mock_basic_stats_instance.get_basic_stats.return_value = {'total_contributions': 100}
        
        # We need to recreate the widget to use the patched class
        widget = ContributionsWidget(self.request)
        # Replace the basic stats instance with our mock
        widget.basic_stats = mock_basic_stats_instance
        
        result = widget.get_basic_stats()
        
        self.assertEqual(result, {'total_contributions': 100})
        mock_basic_stats_instance.get_basic_stats.assert_called_once()
    
    def test_get_data(self):
        """Test getting all data"""
        # Mock the individual methods
        with patch.object(self.widget, 'get_unified_metrics') as mock_get_unified_metrics, \
             patch.object(self.widget, 'get_basic_stats') as mock_get_basic_stats, \
             patch.object(self.widget, 'get_contributions_by_authority') as mock_get_contributions_by_authority, \
             patch.object(self.widget, 'get_contributions_by_gender') as mock_get_contributions_by_gender, \
             patch.object(self.widget, 'get_contributions_by_age') as mock_get_contributions_by_age, \
             patch.object(self.widget, 'get_contributions_trend') as mock_get_contributions_trend, \
             patch.object(self.widget, 'get_live_vs_recorded') as mock_get_live_vs_recorded, \
             patch.object(self.widget, 'get_primary_vs_repetitions') as mock_get_primary_vs_repetitions, \
             patch.object(self.widget, 'get_conversion_metrics') as mock_get_conversion_metrics, \
             patch.object(self.widget, 'get_archive_metrics') as mock_get_archive_metrics:
            
            # Set return values
            mock_get_unified_metrics.return_value = {'total_contributions': 100}
            mock_get_basic_stats.return_value = {'total_contributions': 100}
            mock_get_contributions_by_authority.return_value = []
            mock_get_contributions_by_gender.return_value = []
            mock_get_contributions_by_age.return_value = {}
            mock_get_contributions_trend.return_value = []
            mock_get_live_vs_recorded.return_value = {'total': 100}
            mock_get_primary_vs_repetitions.return_value = {'total': 10}
            mock_get_conversion_metrics.return_value = {'conversion_rate': 50.0}
            mock_get_archive_metrics.return_value = {'archive_licenses': 10}
            
            result = self.widget.get_data()
            
            self.assertIn('unified_metrics', result)
            self.assertIn('basic_stats', result)
            self.assertIn('contributions_by_authority', result)
            self.assertIn('contributions_by_gender', result)
            self.assertIn('contributions_by_age', result)
            self.assertIn('contributions_trend', result)
            self.assertIn('live_vs_recorded', result)
            self.assertIn('primary_vs_repetitions', result)
            self.assertIn('conversion_metrics', result)
            self.assertIn('archive_metrics', result)
    
    @patch('dashboard.widgets.contributions.timezone')
    def test_get_data_exception_handling(self, mock_timezone):
        """Test get_data method with exception handling"""
        # Mock an exception in get_unified_metrics
        with patch.object(self.widget, 'get_unified_metrics') as mock_get_unified_metrics:
            mock_get_unified_metrics.side_effect = Exception("Test error")
            
            result = self.widget.get_data()
            
            # Should return default values in case of exception
            self.assertIn('unified_metrics', result)
            self.assertEqual(result['unified_metrics']['total_contributions'], 0)
            self.assertEqual(result['unified_metrics']['live_contributions'], 0)
            self.assertEqual(result['unified_metrics']['recorded_contributions'], 0)
            self.assertEqual(result['unified_metrics']['unique_licenses'], 0)
            self.assertEqual(result['unified_metrics']['primary_contributions'], 0)
            self.assertEqual(result['unified_metrics']['archive_licenses'], 0)
            self.assertEqual(result['unified_metrics']['active_licenses'], 0)
            self.assertEqual(result['unified_metrics']['recent_licenses'], 0)
            self.assertEqual(result['unified_metrics']['repetitions'], 0)
            self.assertEqual(result['unified_metrics']['conversion_rate'], 0)
            self.assertEqual(result['unified_metrics']['archive_rate'], 0)