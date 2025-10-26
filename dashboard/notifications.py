from .services.notification_service import NotificationService
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.utils import timezone
import json


def is_admin(user):
    """Check if user is admin."""
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_admin)
def api_notifications_statistics(request):
    """API endpoint for notifications statistics"""
    notification_service = NotificationService()
    result = notification_service.get_notifications_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_alerts_list(request):
    """API endpoint for alerts and thresholds."""
    notification_service = NotificationService()
    result = notification_service.get_alerts_list(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_alerts_resolve(request, alert_id):
    """API endpoint to resolve an alert."""
    notification_service = NotificationService()
    result = notification_service.resolve_alert(alert_id)
    
    if result['success']:
        return JsonResponse(result)
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return JsonResponse(result, status=status_code)


@login_required
@user_passes_test(is_admin)
def api_notifications_detail(request):
    """API endpoint for detailed notifications data."""
    notification_service = NotificationService()
    result = notification_service.get_notifications_detail(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_notifications_toggle(request, notification_id):
    """API endpoint to toggle notification status."""
    notification_service = NotificationService()
    result = notification_service.toggle_notification(notification_id)
    
    if result['success']:
        return JsonResponse(result)
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return JsonResponse(result, status=status_code)


@login_required
@user_passes_test(is_admin)
def api_threshold_update(request, threshold_id):
    """API endpoint for updating a threshold."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    
    notification_service = NotificationService()
    result = notification_service.update_threshold(threshold_id, data)
    
    if result['success']:
        return JsonResponse(result)
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return JsonResponse(result, status=status_code)


@login_required
@user_passes_test(is_admin)
def api_threshold_toggle(request, threshold_id):
    """API endpoint for toggling a threshold active status."""
    notification_service = NotificationService()
    result = notification_service.toggle_threshold(threshold_id)
    
    if result['success']:
        return JsonResponse(result)
    else:
        status_code = 404 if 'not found' in result.get('error', '').lower() else 500
        return JsonResponse(result, status=status_code)