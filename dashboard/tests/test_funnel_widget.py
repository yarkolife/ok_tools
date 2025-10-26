"""
Unit tests for dashboard/widgets/funnel.py
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.utils import timezone
from dashboard.widgets.funnel import FunnelWidget
from ..utils import FunnelTracker


class TestFunnelWidget(TestCase):
    """Test FunnelWidget class"""
    
    def setUp(self):
        self.widget = FunnelWidget()
    
    def test_init_default_filters(self):
        """Test initialization with default filters"""
        widget = FunnelWidget()
        self.assertEqual(widget.filters, {})
        self.assertEqual(widget._cache, {})
    
    def test_init_with_filters(self):
        """Test initialization with custom filters"""
        filters = {'days': '30', 'start_date': '2023-01-01', 'end_date': '2023-01-31'}
        widget = FunnelWidget(filters)
        self.assertEqual(widget.filters, filters)
    
    @patch('dashboard.widgets.funnel.FunnelTracker')
    def test_get_funnel_overview(self, mock_funnel_tracker_class):
        """Test getting funnel overview"""
        mock_tracker_instance = Mock()
        mock_funnel_tracker_class.return_value = mock_tracker_instance
        
        # Mock the tracker methods
        mock_tracker_instance.get_funnel_metrics.return_value = {
            'total_registrations': 100,
            'verification_rate': 80.0,
            'license_creation_rate': 60.0,
            'first_broadcast_rate': 40.0,
            'multiple_broadcast_rate': 30.0,
            'rental_request_rate': 50.0,
            'rental_completion_rate': 45.0,
            'conversion_rates': {
                'verification_rate': 80.0,
                'license_creation_rate': 60.0,
                'first_broadcast_rate': 40.0,
                'multiple_broadcast_rate': 30.0,
                'rental_request_rate': 50.0,
                'rental_completion_rate': 45.0
            },
            'metrics': {
                'licenses_created': 60,
                'contributions_created': 55,
                'first_broadcasts': 40
            }
        }
        
        mock_tracker_instance.get_stage_breakdown.return_value = {
            'registered': {'name': 'Registered', 'count': 100, 'users': []},
            'verified': {'name': 'Verified', 'count': 80, 'users': []},
            'rental_requested': {'name': 'Rental Requested', 'count': 50, 'users': []},
            'rental_completed': {'name': 'Rental Completed', 'count': 45, 'users': []},
            'license_created': {'name': 'License Created', 'count': 60, 'users': []},
            'contribution_created': {'name': 'Contribution Created', 'count': 55, 'users': []},
            'first_broadcast': {'name': 'First Broadcast', 'count': 40, 'users': []},
            'multiple_broadcasts': {'name': 'Multiple Broadcasts', 'count': 30, 'users': []}
        }
        
        # Create a widget instance to test
        widget = FunnelWidget()
        result = widget.get_funnel_overview()
        
        self.assertIn('metrics', result)
        self.assertIn('breakdown', result)
        self.assertIn('funnel_data', result)
        self.assertIn('conversion_analysis', result)
        
        # Verify that the tracker methods were called
        mock_tracker_instance.get_funnel_metrics.assert_called_once()
        mock_tracker_instance.get_stage_breakdown.assert_called_once()
    
    @patch('dashboard.widgets.funnel.FunnelTracker')
    def test_get_funnel_trends(self, mock_funnel_tracker_class):
        """Test getting funnel trends"""
        mock_tracker_instance = Mock()
        mock_funnel_tracker_class.return_value = mock_tracker_instance
        
        # Mock the _get_trends_data method
        with patch.object(FunnelWidget, '_get_trends_data') as mock_get_trends_data:
            mock_get_trends_data.return_value = {
                'dates': ['2023-01-01', '2023-01-02'],
                'registrations': [10, 15],
                'verified': [8, 12],
                'conversion_rates': {
                    'verification': [80.0, 80.0]
                }
            }
            
            widget = FunnelWidget()
            result = widget.get_funnel_trends()
            
            self.assertIn('trends', result)
            self.assertIn('period', result)
    
    @patch('dashboard.models.AlertLog')
    @patch('dashboard.models.AlertThreshold')
    def test_get_alerts_summary(self, mock_alert_threshold_model, mock_alert_log_model):
        """Test getting alerts summary"""
        # Mock active alerts
        mock_active_alert = Mock()
        mock_active_alert.id = 1
        mock_active_alert.threshold.name = 'Test Threshold'
        mock_active_alert.threshold.get_stage_display.return_value = 'Registration'
        mock_active_alert.current_value = 100
        mock_active_alert.threshold_value = 90
        mock_active_alert.message = 'Test message'
        mock_active_alert.triggered_at = timezone.now()
        
        # Create proper mock QuerySets
        mock_active_alerts_full_qs = MagicMock()
        mock_active_alerts_full_qs.filter.return_value = mock_active_alerts_full_qs
        mock_active_alerts_full_qs.order_by.return_value = mock_active_alerts_full_qs
        
        # Create a list-like object with a custom count() method (no args)
        class ListWithCount(list):
            def count(self):
                return len(self)

        mock_active_alerts_list = ListWithCount([mock_active_alert])
        def _getitem_active(item):
            # Return our custom list for any slice (e.g., [:10], [0:10], etc.)
            if isinstance(item, slice):
                return ListWithCount(mock_active_alerts_list[item])
            # Indexing returns element (not used in code path), keep behavior
            return mock_active_alerts_list[item]

        mock_active_alerts_full_qs.__getitem__.side_effect = _getitem_active
        
        mock_all_alerts_qs = Mock()
        mock_all_alerts_qs.count.return_value = 2  # total alerts
        mock_all_alerts_qs.filter.return_value.count.return_value = 1  # resolved alerts
        
        mock_alert_log_model.objects = mock_all_alerts_qs
        mock_alert_log_model.objects.filter.return_value = mock_active_alerts_full_qs  # for active alerts
        
        mock_threshold_qs = Mock()
        mock_threshold_qs.count.return_value = 5  # total thresholds
        mock_threshold_qs.filter.return_value.count.return_value = 3  # active thresholds
        
        mock_alert_threshold_model.objects = mock_threshold_qs
        
        widget = FunnelWidget()
        result = widget.get_alerts_summary()
        
        self.assertIn('active_alerts', result)
        self.assertIn('statistics', result)
        self.assertEqual(len(result['active_alerts']), 1)
        self.assertEqual(result['statistics']['total_alerts'], 2)  # all alerts
        self.assertEqual(result['statistics']['total_thresholds'], 5)
    
    def test_get_date_range_default(self):
        """Test getting default date range"""
        widget = FunnelWidget()
        start_date, end_date = widget._get_date_range()
        
        # Should default to 30 days
        expected_start = timezone.now().date() - timedelta(days=30)
        expected_end = timezone.now().date()
        
        self.assertEqual(start_date, expected_start)
        self.assertEqual(end_date, expected_end)
    
    def test_get_date_range_custom_days(self):
        """Test getting date range with custom days"""
        widget = FunnelWidget({'days': '7'})
        start_date, end_date = widget._get_date_range()
        
        expected_end = timezone.now().date()
        expected_start = expected_end - timedelta(days=7)
        
        self.assertEqual(start_date, expected_start)
        self.assertEqual(end_date, expected_end)
    
    def test_get_date_range_custom_period(self):
        """Test getting date range with custom period"""
        start_str = '2023-01-01'
        end_str = '2023-01-31'
        
        widget = FunnelWidget({
            'days': 'custom',
            'start_date': start_str,
            'end_date': end_str
        })
        start_date, end_date = widget._get_date_range()
        
        expected_start = datetime.strptime(start_str, '%Y-%m-%d').date()
        expected_end = datetime.strptime(end_str, '%Y-%m-%d').date()
        
        self.assertEqual(start_date, expected_start)
        self.assertEqual(end_date, expected_end)
    
    def test_format_funnel_data(self):
        """Test formatting funnel data"""
        breakdown = {
            'registered': {'name': 'Registered', 'count': 100, 'users': []},
            'verified': {'name': 'Verified', 'count': 80, 'users': []},
            'license_created': {'name': 'License Created', 'count': 60, 'users': []},
            'first_broadcast': {'name': 'First Broadcast', 'count': 40, 'users': []}
        }
        
        widget = FunnelWidget()
        result = widget._format_funnel_data(breakdown)
        
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]['stage'], 'registered')
        self.assertEqual(result[0]['name'], 'Registered')
        self.assertEqual(result[0]['count'], 100)
    
    def test_analyze_conversions(self):
        """Test analyzing conversions"""
        metrics = {
            'conversion_rates': {
                'verification_rate': 80.0,
                'license_creation_rate': 60.0,
                'first_broadcast_rate': 40.0,
                'multiple_broadcast_rate': 30.0,
                'rental_request_rate': 50.0,
                'rental_completion_rate': 45.0
            },
            'metrics': {
                'licenses_created': 60,
                'contributions_created': 55,
                'first_broadcasts': 40
            }
        }
        
        widget = FunnelWidget()
        result = widget._analyze_conversions(metrics)
        
        self.assertIn('overall_conversion', result)
        self.assertIn('rental_conversion', result)
        self.assertIn('content_creation', result)
        self.assertEqual(result['overall_conversion']['registration_to_verification'], 80.0)
    
    def test_calculate_license_to_contribution_rate(self):
        """Test calculating license to contribution rate"""
        metrics = {
            'metrics': {
                'licenses_created': 100,
                'contributions_created': 80
            }
        }
        
        widget = FunnelWidget()
        result = widget._calculate_license_to_contribution_rate(metrics)
        
        self.assertEqual(result, 80.0)  # 80/100 * 100
    
    def test_calculate_license_to_contribution_rate_zero_division(self):
        """Test calculating license to contribution rate with zero division"""
        metrics = {
            'metrics': {
                'licenses_created': 0,
                'contributions_created': 80
            }
        }
        
        widget = FunnelWidget()
        result = widget._calculate_license_to_contribution_rate(metrics)
        
        self.assertEqual(result, 0.0)  # Should handle zero division
    
    def test_calculate_contribution_to_broadcast_rate(self):
        """Test calculating contribution to broadcast rate"""
        metrics = {
            'metrics': {
                'contributions_created': 100,
                'first_broadcasts': 75
            }
        }
        
        widget = FunnelWidget()
        result = widget._calculate_contribution_to_broadcast_rate(metrics)
        
        self.assertEqual(result, 75.0)  # 75/100 * 100
    
    def test_calculate_contribution_to_broadcast_rate_zero_division(self):
        """Test calculating contribution to broadcast rate with zero division"""
        metrics = {
            'metrics': {
                'contributions_created': 0,
                'first_broadcasts': 75
            }
        }
        
        widget = FunnelWidget()
        result = widget._calculate_contribution_to_broadcast_rate(metrics)
        
        self.assertEqual(result, 0.0)  # Should handle zero division
    
    @patch('dashboard.models.FunnelMetrics')
    def test_get_trends_data(self, mock_funnel_metrics):
        """Test getting trends data"""
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
        
        # Mock a FunnelMetrics instance
        mock_metric = Mock()
        mock_metric.date = start_date
        mock_metric.total_registrations = 10
        mock_metric.verified_users = 8
        mock_metric.verification_rate = 80.0
        
        # Mock the queryset properly
        mock_filter_result = Mock()
        mock_filter_result.order_by.return_value = mock_filter_result  # order_by should return a QuerySet-like object
        # When sliced, it returns the list
        mock_metrics_list = [mock_metric]
        mock_filter_result.__iter__ = lambda self: iter(mock_metrics_list)
        mock_filter_result.exists.return_value = True
        mock_funnel_metrics.objects.filter.return_value = mock_filter_result
        
        widget = FunnelWidget()
        result = widget._get_trends_data(start_date, end_date)
        
        self.assertIn('dates', result)
        self.assertIn('registrations', result)
        self.assertIn('conversion_rates', result)
        self.assertEqual(result['dates'], [start_date.isoformat()])
        self.assertEqual(result['registrations'], [10])
        self.assertEqual(result['conversion_rates']['verification'], [80.0])
    
    @patch('dashboard.widgets.funnel.FunnelTracker')
    def test_get_all_data(self, mock_funnel_tracker_class):
        """Test getting all widget data"""
        mock_tracker_instance = Mock()
        mock_funnel_tracker_class.return_value = mock_tracker_instance
        
        # Mock the tracker methods with proper structure
        mock_tracker_instance.get_funnel_metrics.return_value = {
            'conversion_rates': {
                'verification_rate': 80.0,
                'license_creation_rate': 60.0,
                'first_broadcast_rate': 40.0,
                'multiple_broadcast_rate': 30.0,
                'rental_request_rate': 50.0,
                'rental_completion_rate': 45.0
            },
            'metrics': {
                'licenses_created': 60,
                'contributions_created': 55,
                'first_broadcasts': 40
            }
        }
        mock_tracker_instance.get_stage_breakdown.return_value = {'test': 'breakdown'}
        
        with patch.object(FunnelWidget, '_get_trends_data') as mock_get_trends_data:
            mock_get_trends_data.return_value = {'test': 'trends'}
            
            # Mock AlertLog and AlertThreshold for alerts summary
            with patch('dashboard.models.AlertLog') as mock_alert_log, \
                 patch('dashboard.models.AlertThreshold') as mock_alert_threshold:
                
                # Create proper mock QuerySets
                mock_active_alerts_full_qs = MagicMock()
                mock_active_alerts_full_qs.filter.return_value = mock_active_alerts_full_qs
                mock_active_alerts_full_qs.order_by.return_value = mock_active_alerts_full_qs
                
                # Create a list-like object with a custom count() method (no args)
                class ListWithCount(list):
                    def count(self):
                        return len(self)

                mock_active_alerts_list = ListWithCount([])
                def _getitem_active_all(item):
                    if isinstance(item, slice):
                        return ListWithCount(mock_active_alerts_list[item])
                    return mock_active_alerts_list[item]

                mock_active_alerts_full_qs.__getitem__.side_effect = _getitem_active_all
                
                mock_all_alerts_qs = Mock()
                mock_all_alerts_qs.count.return_value = 0  # total alerts
                mock_all_alerts_qs.filter.return_value.count.return_value = 0 # resolved alerts
                
                mock_alert_log.objects = mock_all_alerts_qs
                mock_alert_log.objects.filter.return_value = mock_active_alerts_full_qs  # for active alerts
                
                # Mock AlertThreshold queryset
                mock_threshold_qs = Mock()
                mock_threshold_qs.count.return_value = 0  # total thresholds
                mock_threshold_qs.filter.return_value.count.return_value = 0  # active thresholds
                
                mock_alert_threshold.objects = mock_threshold_qs
                
                widget = FunnelWidget()
                result = widget.get_all_data()
                
                self.assertIn('overview', result)
                self.assertIn('trends', result)
                self.assertIn('alerts', result)