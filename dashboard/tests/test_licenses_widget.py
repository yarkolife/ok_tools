"""
Unit tests for dashboard/widgets/licenses.py
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.utils import timezone
from dashboard.widgets.licenses import LicensesWidget
from dashboard.widgets.filters import DashboardFilters
from licenses.models import License


class TestLicensesWidget(TestCase):
    """Test LicensesWidget class"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/dashboard/')
        self.widget = LicensesWidget(self.request)
    
    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.widget.request, self.request)
        self.assertIsInstance(self.widget.filters, DashboardFilters)
        self.assertEqual(self.widget._cache, {})
    
    def test_get_data(self):
        """Test getting all data"""
        # Mock individual methods to return test data
        with patch.object(self.widget, 'get_basic_stats') as mock_get_basic_stats, \
             patch.object(self.widget, 'get_licenses_by_category') as mock_get_licenses_by_category, \
             patch.object(self.widget, 'get_licenses_by_authority') as mock_get_licenses_by_authority, \
             patch.object(self.widget, 'get_licenses_by_gender') as mock_get_licenses_by_gender, \
             patch.object(self.widget, 'get_licenses_by_age') as mock_get_licenses_by_age, \
             patch.object(self.widget, 'get_licenses_trend') as mock_get_licenses_trend, \
             patch.object(self.widget, 'get_confirmation_rate') as mock_get_confirmation_rate, \
             patch.object(self.widget, 'get_duration_stats') as mock_get_duration_stats, \
             patch.object(self.widget, 'get_youth_protection_stats') as mock_get_youth_protection_stats, \
             patch.object(self.widget, 'get_media_library_stats') as mock_get_media_library_stats, \
             patch.object(self.widget, 'get_exchange_stats') as mock_get_exchange_stats, \
             patch.object(self.widget, 'get_archive_stats') as mock_get_archive_stats:
            
            # Set return values
            mock_get_basic_stats.return_value = {'total_licenses': 100}
            mock_get_licenses_by_category.return_value = []
            mock_get_licenses_by_authority.return_value = []
            mock_get_licenses_by_gender.return_value = []
            mock_get_licenses_by_age.return_value = {}
            mock_get_licenses_trend.return_value = []
            mock_get_confirmation_rate.return_value = {'rate': 80.0}
            mock_get_duration_stats.return_value = {'average_duration_minutes': 30}
            mock_get_youth_protection_stats.return_value = {'youth_protection_rate': 10.0}
            mock_get_media_library_stats.return_value = {'library_rate': 50.0}
            mock_get_exchange_stats.return_value = {'saxony_rate': 20.0}
            mock_get_archive_stats.return_value = {'archive_percentage': 15.0}
            
            result = self.widget.get_data()
            
            self.assertIn('basic_stats', result)
            self.assertIn('licenses_by_category', result)
            self.assertIn('licenses_by_authority', result)
            self.assertIn('licenses_by_gender', result)
            self.assertIn('licenses_by_age', result)
            self.assertIn('licenses_trend', result)
            self.assertIn('confirmation_rate', result)
            self.assertIn('duration_stats', result)
            self.assertIn('youth_protection_stats', result)
            self.assertIn('media_library_stats', result)
            self.assertIn('exchange_stats', result)
            self.assertIn('archive_stats', result)
    
    @patch('dashboard.widgets.licenses.cache')
    def test_get_basic_stats_cached(self, mock_cache):
        """Test getting basic stats with cached result"""
        mock_cache.get.return_value = {'total_licenses': 100, 'confirmed_licenses': 80, 'pending_licenses': 20}
        
        result = self.widget.get_basic_stats()
        
        self.assertEqual(result['total_licenses'], 100)
        mock_cache.get.assert_called_once()
    
    @patch('dashboard.widgets.licenses.cache')
    @patch('dashboard.widgets.licenses.License')
    def test_get_basic_stats_not_cached(self, mock_license_model, mock_cache):
        """Test getting basic stats without cached result"""
        # Mock no cached result
        mock_cache.get.return_value = None
        
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        mock_filtered_queryset.count.return_value = 100

        # Use side_effect to return different querysets depending on confirmed flag
        mock_confirmed_qs = Mock()
        mock_confirmed_qs.count.return_value = 80
        mock_pending_qs = Mock()
        mock_pending_qs.count.return_value = 20

        def filter_side_effect(*args, **kwargs):
            if kwargs.get('confirmed') is True:
                return mock_confirmed_qs
            if kwargs.get('confirmed') is False:
                return mock_pending_qs
            return mock_filtered_queryset

        mock_filtered_queryset.filter.side_effect = filter_side_effect
        
        result = self.widget.get_basic_stats()
        
        self.assertEqual(result['total_licenses'], 100)
        self.assertEqual(result['confirmed_licenses'], 80)
        self.assertEqual(result['pending_licenses'], 20)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.licenses.cache')
    @patch('dashboard.widgets.licenses.License')
    def test_get_duration_stats(self, mock_license_model, mock_cache):
        """Test getting duration stats"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        # Mock the filter chain
        mock_duration_queryset = Mock()
        mock_filtered_queryset.filter.return_value = mock_duration_queryset
        mock_duration_queryset.exclude.return_value = mock_duration_queryset
        
        # Mock a license with duration
        mock_license = Mock()
        mock_license.duration = timedelta(minutes=30)
        mock_duration_queryset.__iter__ = Mock(return_value=iter([mock_license]))
        mock_duration_queryset.count.return_value = 1
        
        result = self.widget.get_duration_stats()
        
        self.assertIn('total_with_duration', result)
        self.assertIn('average_duration_minutes', result)
        self.assertIn('total_duration_hours', result)
        self.assertIn('duration_distribution', result)
        self.assertIn('longest_duration', result)
        self.assertIn('shortest_duration', result)
    
    @patch('dashboard.widgets.licenses.cache')
    @patch('dashboard.widgets.licenses.License')
    def test_get_licenses_by_category(self, mock_license_model, mock_cache):
        """Test getting licenses by category"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        # Mock the values and annotate chain
        mock_values_queryset = Mock()
        mock_filtered_queryset.values.return_value = mock_values_queryset
        mock_annotated_result = Mock()
        mock_annotated_result.order_by.return_value = [{'category__name': 'Test Category', 'count': 5}]
        mock_values_queryset.annotate.return_value = mock_annotated_result
        
        result = self.widget.get_licenses_by_category()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['category__name'], 'Test Category')
        self.assertEqual(result[0]['count'], 5)
    
    @patch('dashboard.widgets.licenses.cache')
    @patch('dashboard.widgets.licenses.License')
    def test_get_licenses_by_authority(self, mock_license_model, mock_cache):
        """Test getting licenses by authority"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        mock_filtered_queryset.select_related.return_value = mock_filtered_queryset
        
        # Mock the values and annotate chain
        mock_values_queryset = Mock()
        mock_filtered_queryset.values.return_value = mock_values_queryset
        mock_annotated_result = Mock()
        mock_annotated_result.order_by.return_value = [{'profile__media_authority__name': 'Test Authority', 'count': 3}]
        mock_values_queryset.annotate.return_value = mock_annotated_result
        
        result = self.widget.get_licenses_by_authority()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['profile__media_authority__name'], 'Test Authority')
        self.assertEqual(result[0]['count'], 3)
    
    @patch('dashboard.widgets.licenses.cache')
    @patch('dashboard.widgets.licenses.License')
    def test_get_licenses_by_gender(self, mock_license_model, mock_cache):
        """Test getting licenses by gender"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        # Mock the values and annotate chain
        mock_values_queryset = Mock()
        mock_filtered_queryset.values.return_value = mock_values_queryset
        mock_annotated_result = Mock()
        mock_annotated_result.order_by.return_value = [{'profile__gender': 'M', 'count': 2}]
        mock_values_queryset.annotate.return_value = mock_annotated_result
        
        result = self.widget.get_licenses_by_gender()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['profile__gender'], 'M')
        self.assertEqual(result[0]['count'], 2)
    
    def test_get_licenses_by_age(self):
        """Test getting licenses by age"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        with patch.object(self.widget, 'filters') as mock_filters:
            mock_filters.apply_filters_to_queryset.return_value = mock_filtered_queryset
            mock_filtered_queryset.select_related.return_value = mock_filtered_queryset
            mock_filtered_queryset.only.return_value = mock_filtered_queryset

            # Ensure date_range is defined for age calculation
            end_date = timezone.now().date()
            mock_filters.date_range = {'end_date': end_date}

            # Create a mock license with a profile that has a birthday exactly 25 years ago
            mock_license = Mock()
            mock_profile = Mock()
            mock_profile.birthday = end_date - relativedelta(years=25)
            mock_license.profile = mock_profile
            mock_filtered_queryset.iterator.return_value = [mock_license]
            
            result = self.widget.get_licenses_by_age()
            
            # Check that the 25-year-old falls into the '18_25' category
            self.assertEqual(result['18_25'], 1)
            self.assertEqual(result['under_18'], 0)
            self.assertEqual(result['26_35'], 0)
            self.assertEqual(result['36_50'], 0)
            self.assertEqual(result['over_50'], 0)
    
    def test_get_licenses_trend(self):
        """Test getting licenses trend"""
        with patch.object(self.widget, 'filters') as mock_filters:
            # Set up date range
            start_date = timezone.now().date() - timedelta(days=15)
            end_date = timezone.now().date()
            mock_filters.date_range = {'start_date': start_date, 'end_date': end_date}
            
            with patch('dashboard.widgets.licenses.License') as mock_license_model:
                # Mock the filter to count licenses
                mock_license_queryset = Mock()
                mock_license_model.objects.filter.return_value = mock_license_queryset
                mock_license_queryset.count.return_value = 5
                
                result = self.widget.get_licenses_trend()
                
                # For a 15-day period, we should get daily data
                self.assertGreater(len(result), 0)
                self.assertIn('date', result[0])
                self.assertIn('count', result[0])
    
    @patch('dashboard.widgets.licenses.cache')
    @patch('dashboard.widgets.licenses.License')
    def test_get_confirmation_rate(self, mock_license_model, mock_cache):
        """Test getting confirmation rate"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        mock_filtered_queryset.count.return_value = 100
        mock_filtered_queryset.filter.return_value.count.return_value = 80  # confirmed
        
        result = self.widget.get_confirmation_rate()
        
        self.assertEqual(result['total'], 100)
        self.assertEqual(result['confirmed'], 80)
        self.assertEqual(result['rate'], 80.0)
    
    @patch('dashboard.widgets.licenses.License')
    def test_get_youth_protection_stats(self, mock_license_model):
        """Test getting youth protection stats"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        mock_filtered_queryset.count.return_value = 100
        mock_youth_necessary = Mock()
        mock_youth_necessary.count.return_value = 10  # youth protection necessary
        mock_youth_not_necessary = Mock()
        mock_youth_not_necessary.count.return_value = 85  # youth protection not necessary
        mock_youth_unknown = Mock()
        mock_youth_unknown.count.return_value = 5  # youth protection unknown
        mock_filtered_queryset.filter.return_value = mock_youth_necessary
        mock_filtered_queryset.filter.return_value = mock_youth_not_necessary
        mock_filtered_queryset.filter.return_value = mock_youth_unknown
        
        # Mock the values and annotate for categories
        mock_values_queryset = Mock()
        mock_filtered_queryset.values.return_value = mock_values_queryset
        mock_annotated_result = Mock()
        mock_annotated_result.order_by.return_value = [{'youth_protection_category': 'FSK 12', 'count': 5}]
        mock_values_queryset.annotate.return_value = mock_annotated_result
        
        result = self.widget.get_youth_protection_stats()
        
        self.assertEqual(result['total_licenses'], 100)
        self.assertEqual(result['youth_protection_necessary'], 10)
        self.assertEqual(result['youth_protection_not_necessary'], 85)
        self.assertEqual(result['youth_protection_unknown'], 5)
        self.assertEqual(result['youth_protection_rate'], 10.0)
        self.assertEqual(len(result['youth_categories']), 1)
    
    @patch('dashboard.widgets.licenses.License')
    def test_get_media_library_stats(self, mock_license_model):
        """Test getting media library stats"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        mock_filtered_queryset.count.return_value = 100

        # Prepare distinct mocks for different filter conditions
        qs_store_true = Mock()
        qs_store_true.count.return_value = 50
        qs_store_false = Mock()
        qs_store_false.count.return_value = 45
        qs_store_unknown = Mock()
        qs_store_unknown.count.return_value = 5

        def filter_side_effect(*args, **kwargs):
            if kwargs.get('store_in_ok_media_library') is True:
                return qs_store_true
            if kwargs.get('store_in_ok_media_library') is False:
                return qs_store_false
            if kwargs.get('store_in_ok_media_library__isnull') is True:
                return qs_store_unknown
            return mock_filtered_queryset

        mock_filtered_queryset.filter.side_effect = filter_side_effect
        result = self.widget.get_media_library_stats()
        
        self.assertEqual(result['total_licenses'], 100)
        self.assertEqual(result['store_in_library'], 50)
        self.assertEqual(result['not_store_in_library'], 45)
        self.assertEqual(result['library_unknown'], 5)
        self.assertEqual(result['library_rate'], 50.0)
    
    @patch('dashboard.widgets.licenses.License')
    def test_get_exchange_stats(self, mock_license_model):
        """Test getting exchange stats"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        mock_filtered_queryset.count.return_value = 100

        # Distinct mocks for Saxony exchange
        saxony_allowed_qs = Mock()
        saxony_allowed_qs.count.return_value = 20
        saxony_not_allowed_qs = Mock()
        saxony_not_allowed_qs.count.return_value = 75
        saxony_unknown_qs = Mock()
        saxony_unknown_qs.count.return_value = 5

        # Distinct mocks for other states exchange
        other_allowed_qs = Mock()
        other_allowed_qs.count.return_value = 15
        other_not_allowed_qs = Mock()
        other_not_allowed_qs.count.return_value = 80
        other_unknown_qs = Mock()
        other_unknown_qs.count.return_value = 5

        def filter_side_effect(*args, **kwargs):
            # Saxony-Anhalt exchange flags
            if kwargs.get('media_authority_exchange_allowed') is True:
                return saxony_allowed_qs
            if kwargs.get('media_authority_exchange_allowed') is False:
                return saxony_not_allowed_qs
            if kwargs.get('media_authority_exchange_allowed__isnull') is True:
                return saxony_unknown_qs

            # Other states flags
            if kwargs.get('media_authority_exchange_allowed_other_states') is True:
                return other_allowed_qs
            if kwargs.get('media_authority_exchange_allowed_other_states') is False:
                return other_not_allowed_qs
            if kwargs.get('media_authority_exchange_allowed_other_states__isnull') is True:
                return other_unknown_qs

            return mock_filtered_queryset

        mock_filtered_queryset.filter.side_effect = filter_side_effect

        result = self.widget.get_exchange_stats()
        
        self.assertEqual(result['total_licenses'], 100)
        self.assertEqual(result['saxony_exchange_allowed'], 20)
        self.assertEqual(result['saxony_exchange_not_allowed'], 75)
        self.assertEqual(result['saxony_exchange_unknown'], 5)
        self.assertEqual(result['saxony_rate'], 20.0)
    
    @patch('dashboard.widgets.licenses.License')
    def test_get_archive_stats(self, mock_license_model):
        """Test getting archive stats"""
        # Mock filtered queryset
        mock_filtered_queryset = Mock()
        mock_license_model.objects.all.return_value = mock_filtered_queryset
        self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
        
        # Mock the values_list for filtered license IDs
        mock_filtered_queryset.values_list.return_value = [1, 2, 3]
        mock_filtered_queryset.count.return_value = 3
        
        with patch('dashboard.widgets.licenses.License') as inner_mock_license:
            # Mock the annotate → values chain to return list of dicts
            first_broadcast = timezone.now() - timedelta(days=400)
            annotated = inner_mock_license.objects.filter.return_value.annotate.return_value
            annotated.values.return_value = [{
                'id': 1,
                'first_broadcast': first_broadcast,
                'created_at': timezone.now()
            }]
            
            result = self.widget.get_archive_stats()
            
            self.assertIn('total_licenses', result)
            self.assertIn('archive_licenses', result)
            self.assertIn('active_licenses', result)
            self.assertIn('recent_licenses', result)
            self.assertIn('archive_percentage', result)
            self.assertIn('active_percentage', result)
            self.assertIn('recent_percentage', result)
            self.assertIn('archive_threshold_days', result)
    
    def test_get_detailed_licenses(self):
        """Test getting detailed licenses"""
        with patch('dashboard.widgets.licenses.License') as mock_license_model:
            # Mock the select_related queryset
            mock_queryset = Mock()
            mock_license_model.objects.select_related.return_value = mock_queryset
            mock_select_related = Mock()
            mock_select_related.all.return_value = mock_select_related
            mock_license_model.objects.select_related.return_value = mock_select_related
            
            # Mock filtered queryset
            mock_filtered_queryset = MagicMock()
            self.widget.filters.apply_filters_to_queryset = Mock(return_value=mock_filtered_queryset)
            
            # Mock pagination
            mock_filtered_queryset.count.return_value = 1

            def _getitem(item):
                data = [mock_license]
                if isinstance(item, slice):
                    return data[item]
                return data[item]

            mock_filtered_queryset.__getitem__.side_effect = _getitem
            # Create a mock license object
            mock_license = Mock()
            mock_license.id = 1
            mock_license.number = "TEST001"
            mock_license.title = "Test License"
            mock_license.subtitle = "Test Subtitle"
            mock_license.duration = timedelta(minutes=30)
            mock_profile = Mock()
            mock_profile.first_name = "John"
            mock_profile.last_name = "Doe"
            mock_okuser = Mock()
            mock_okuser.email = "john@example.com"
            mock_profile.okuser = mock_okuser
            mock_category = Mock()
            mock_category.name = "Test Category"
            mock_media_authority = Mock()
            mock_media_authority.name = "Test Authority"
            mock_profile.media_authority = mock_media_authority
            mock_profile.city = "Test City"
            mock_license.profile = mock_profile
            mock_license.category = mock_category
            mock_license.created_at = timezone.now()
            mock_license.confirmed = True
            mock_filtered_queryset.__iter__ = Mock(return_value=iter([mock_license]))
            
            result = self.widget.get_detailed_licenses()
            
            self.assertIn('licenses', result)
            self.assertIn('total_count', result)
            self.assertIn('displayed_count', result)
            self.assertIn('pagination', result)
            self.assertEqual(len(result['licenses']), 1)
            self.assertEqual(result['licenses'][0]['number'], 'TEST001')
    
    def test_get_detailed_data(self):
        """Test getting detailed data"""
        with patch.object(self.widget, 'get_detailed_licenses') as mock_get_detailed_licenses, \
             patch.object(self.widget, 'get_basic_stats') as mock_get_basic_stats, \
             patch.object(self.widget, 'get_licenses_by_category') as mock_get_licenses_by_category, \
             patch.object(self.widget, 'get_licenses_by_authority') as mock_get_licenses_by_authority, \
             patch.object(self.widget, 'get_licenses_by_gender') as mock_get_licenses_by_gender, \
             patch.object(self.widget, 'get_licenses_by_age') as mock_get_licenses_by_age, \
             patch.object(self.widget, 'get_licenses_trend') as mock_get_licenses_trend, \
             patch.object(self.widget, 'get_confirmation_rate') as mock_get_confirmation_rate, \
             patch.object(self.widget, 'get_duration_stats') as mock_get_duration_stats, \
             patch.object(self.widget, 'get_youth_protection_stats') as mock_get_youth_protection_stats, \
             patch.object(self.widget, 'get_media_library_stats') as mock_get_media_library_stats, \
             patch.object(self.widget, 'get_exchange_stats') as mock_get_exchange_stats, \
             patch.object(self.widget, 'get_archive_stats') as mock_get_archive_stats:
            
            # Set return values
            mock_get_detailed_licenses.return_value = {
                'licenses': [],
                'total_count': 0,
                'displayed_count': 0,
                'pagination': {}
            }
            mock_get_basic_stats.return_value = {'total_licenses': 100}
            mock_get_licenses_by_category.return_value = []
            mock_get_licenses_by_authority.return_value = []
            mock_get_licenses_by_gender.return_value = []
            mock_get_licenses_by_age.return_value = {}
            mock_get_licenses_trend.return_value = []
            mock_get_confirmation_rate.return_value = {'rate': 80.0}
            mock_get_duration_stats.return_value = {'average_duration_minutes': 30}
            mock_get_youth_protection_stats.return_value = {'youth_protection_rate': 10.0}
            mock_get_media_library_stats.return_value = {'library_rate': 50.0}
            mock_get_exchange_stats.return_value = {'saxony_rate': 20.0}
            mock_get_archive_stats.return_value = {'archive_percentage': 15.0}
            
            result = self.widget.get_detailed_data()
            
            self.assertIn('licenses', result)
            self.assertIn('total_count', result)
            self.assertIn('displayed_count', result)
            self.assertIn('pagination', result)
            self.assertIn('basic_stats', result)
            self.assertIn('licenses_by_category', result)
            self.assertIn('licenses_by_authority', result)
            self.assertIn('licenses_by_gender', result)
            self.assertIn('licenses_by_age', result)
            self.assertIn('licenses_trend', result)
            self.assertIn('confirmation_rate', result)
            self.assertIn('duration_stats', result)
            self.assertIn('youth_protection_stats', result)
            self.assertIn('media_library_stats', result)
            self.assertIn('exchange_stats', result)
            self.assertIn('archive_stats', result)