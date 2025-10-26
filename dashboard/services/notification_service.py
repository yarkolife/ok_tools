from ..widgets.filters import DashboardFilters
from ..widgets.notifications import NotificationsWidget
from contributions.models import Contribution
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from licenses.models import Category
from licenses.models import License
from registration.models import MediaAuthority
from registration.models import Profile


class NotificationService:
    """Service class for handling notification-related business logic."""
    
    def __init__(self, request=None):
        self.request = request
    
    def get_notifications_statistics(self, request):
        """Get notifications statistics."""
        try:
            # Get filters from request
            filters = {}

            # Date filters
            if 'days' in request.GET:
                filters['days'] = request.GET.get('days')
            if 'start_date' in request.GET:
                filters['start_date'] = request.GET.get('start_date')
            if 'end_date' in request.GET:
                filters['end_date'] = request.GET.get('end_date')

            # Notification filters
            if 'notification_type' in request.GET:
                filters['notification_type'] = request.GET.get('notification_type')
            if 'priority' in request.GET:
                filters['priority'] = request.GET.get('priority')
            if 'is_active' in request.GET:
                filters['is_active'] = request.GET.get('is_active')
            if 'created_by' in request.GET:
                filters['created_by'] = request.GET.get('created_by')

            # Create widget and get data
            widget = NotificationsWidget(filters)
            data = widget.get_all_data()

            return {
                'success': True,
                'data': data
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_alerts_list(self, request):
        """Get alerts and thresholds."""
        try:
            from ..models import AlertThreshold
            from ..utils import FunnelTracker

            # Parse filter parameters
            try:
                filter_manager = DashboardFilters(request)
                start_date = filter_manager.date_range['start_date']
                end_date = filter_manager.date_range['end_date']
            except Exception as e:
                # Fallback to default values
                start_date = None
                end_date = None

            # Get current metrics for the selected period
            try:
                funnel_tracker = FunnelTracker()
                current_metrics = funnel_tracker.get_funnel_metrics(start_date, end_date)
            except Exception as e:
                # Fallback to empty metrics
                current_metrics = {
                    'registered_profiles': 0,
                    'verified_profiles': 0,
                    'licenses_created': 0,
                    'first_broadcasts': 0,
                    'rental_completed': 0,
                    'verification_rate': 0.0,
                    'license_creation_rate': 0.0,
                    'first_broadcast_rate': 0.0,
                    'rental_completion_rate': 0.0
                }

            # Get all thresholds
            thresholds = AlertThreshold.objects.filter(
                is_active=True
            ).select_related().order_by('name')

            # Calculate current alerts based on thresholds and current metrics
            alerts_data = []
            for threshold in thresholds:
                current_value = 0.0
                alert_triggered = False

                # Get current value based on threshold stage and metric type
                if threshold.stage == 'registered':
                    if threshold.metric_type == 'absolute_count':
                        current_value = current_metrics.get('total_registrations', 0)
                    elif threshold.metric_type == 'conversion_rate':
                        current_value = 0.0  # No conversion rate for registered stage
                elif threshold.stage == 'verified':
                    if threshold.metric_type == 'absolute_count':
                        current_value = current_metrics.get('verified_users', 0)
                    elif threshold.metric_type == 'conversion_rate':
                        # Get verification rate from conversion_rates, not metrics
                        conversion_rates = current_metrics.get('conversion_rates', {})
                        current_value = conversion_rates.get('verification_rate', 0.0)
                elif threshold.stage == 'license_created':
                    if threshold.metric_type == 'absolute_count':
                        current_value = current_metrics.get('licenses_created', 0)
                    elif threshold.metric_type == 'conversion_rate':
                        # Get license creation rate from conversion_rates, not metrics
                        conversion_rates = current_metrics.get('conversion_rates', {})
                        current_value = conversion_rates.get('license_creation_rate', 0.0)
                elif threshold.stage == 'first_broadcast':
                    if threshold.metric_type == 'absolute_count':
                        current_value = current_metrics.get('first_broadcasts', 0)
                    elif threshold.metric_type == 'conversion_rate':
                        # Get first broadcast rate from conversion_rates, not metrics
                        conversion_rates = current_metrics.get('conversion_rates', {})
                        current_value = conversion_rates.get('first_broadcast_rate', 0.0)
                elif threshold.stage == 'rental_completed':
                    if threshold.metric_type == 'absolute_count':
                        current_value = current_metrics.get('completed_rentals', 0)
                    elif threshold.metric_type == 'conversion_rate':
                        # Get rental completion rate from conversion_rates, not metrics
                        conversion_rates = current_metrics.get('conversion_rates', {})
                        current_value = conversion_rates.get('rental_completion_rate', 0.0)

                # Check if alert should be triggered
                if threshold.comparison_operator == 'gt':
                    alert_triggered = current_value > threshold.threshold_value
                elif threshold.comparison_operator == 'lt':
                    alert_triggered = current_value < threshold.threshold_value
                elif threshold.comparison_operator == 'eq':
                    alert_triggered = current_value == threshold.threshold_value

                if alert_triggered:
                    alerts_data.append({
                        'id': f"dynamic_{threshold.id}",
                        'threshold_name': threshold.name,
                        'stage': threshold.get_stage_display(),
                        'metric_type': threshold.get_metric_type_display(),
                        'current_value': current_value,
                        'threshold_value': threshold.threshold_value,
                        'message': f"{threshold.name} - {threshold.get_stage_display()} {threshold.get_metric_type_display()} is {current_value:.1f} (threshold: {threshold.threshold_value})",
                        'triggered_at': None,  # Dynamic alert
                        'is_resolved': False
                    })

            thresholds_data = []
            for threshold in thresholds:
                thresholds_data.append({
                    'id': threshold.id,
                    'name': threshold.name,
                    'stage': threshold.get_stage_display(),
                    'metric_type': threshold.get_metric_type_display(),
                    'threshold_value': threshold.threshold_value,
                    'comparison_operator': threshold.get_comparison_operator_display(),
                    'is_active': threshold.is_active
                })

            return {
                'success': True,
                'data': {
                    'alerts': alerts_data,
                    'thresholds': thresholds_data
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def resolve_alert(self, alert_id):
        """Resolve an alert."""
        try:
            from ..models import AlertLog

            alert = AlertLog.objects.select_related('threshold').get(id=alert_id)
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.save()

            return {
                'success': True,
                'message': 'Alert resolved successfully'
            }

        except AlertLog.DoesNotExist:
            return {
                'success': False,
                'error': 'Alert not found'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_notifications_detail(self, request):
        """Get detailed notifications data."""
        try:
            # Get filters from request
            filters = {}

            # Date filters
            if 'days' in request.GET:
                filters['days'] = request.GET.get('days')
            if 'start_date' in request.GET:
                filters['start_date'] = request.GET.get('start_date')
            if 'end_date' in request.GET:
                filters['end_date'] = request.GET.get('end_date')

            # Notification filters
            if 'notification_type' in request.GET:
                filters['notification_type'] = request.GET.get('notification_type')
            if 'priority' in request.GET:
                filters['priority'] = request.GET.get('priority')
            if 'is_active' in request.GET:
                filters['is_active'] = request.GET.get('is_active')
            if 'created_by' in request.GET:
                filters['created_by'] = request.GET.get('created_by')

            # Get detail type from request
            detail_type = request.GET.get('type', 'total')

            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))

            # Create widget and get data
            widget = NotificationsWidget(filters)
            data = widget.get_detailed_notifications(detail_type, page, page_size)

            return {
                'success': True,
                'data': data
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def toggle_notification(self, notification_id):
        """Toggle notification status."""
        try:
            from registration.models import Notification

            notification = Notification.objects.select_related().get(id=notification_id)
            notification.is_read = not notification.is_read
            notification.save()

            return {
                'success': True,
                'is_read': notification.is_read
            }

        except Notification.DoesNotExist:
            return {
                'success': False,
                'error': 'Notification not found'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_threshold(self, threshold_id, data):
        """Update a threshold."""
        try:
            from ..models import AlertThreshold
            import json

            threshold = AlertThreshold.objects.get(id=threshold_id)

            # Update threshold fields
            threshold.name = data.get('name', threshold.name)
            threshold.stage = data.get('stage', threshold.stage)
            threshold.metric_type = data.get('metric_type', threshold.metric_type)
            threshold.threshold_value = data.get('threshold_value', threshold.threshold_value)

            # Convert comparison operator from frontend format to model format
            comparison_operator = data.get('comparison_operator', threshold.comparison_operator)
            if comparison_operator == 'greater_than':
                comparison_operator = 'gt'
            elif comparison_operator == 'less_than':
                comparison_operator = 'lt'
            elif comparison_operator == 'equals':
                comparison_operator = 'eq'

            threshold.comparison_operator = comparison_operator
            threshold.is_active = data.get('is_active', threshold.is_active)

            threshold.save()

            return {
                'success': True,
                'message': 'Threshold updated successfully'
            }

        except AlertThreshold.DoesNotExist:
            return {
                'success': False,
                'error': 'Threshold not found'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def toggle_threshold(self, threshold_id):
        """Toggle a threshold active status."""
        try:
            from ..models import AlertThreshold

            threshold = AlertThreshold.objects.get(id=threshold_id)
            threshold.is_active = not threshold.is_active
            threshold.save()

            return {
                'success': True,
                'message': f'Threshold {"activated" if threshold.is_active else "deactivated"} successfully',
                'is_active': threshold.is_active
            }

        except AlertThreshold.DoesNotExist:
            return {
                'success': False,
                'error': 'Threshold not found'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }