from .services.statistics_service import StatisticsService
from .widgets.filters import DashboardFilters
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from registration.models import Profile


def is_admin(user):
    """Check if user is admin."""
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_admin)
def api_licenses_statistics(request):
    """API endpoint for licenses statistics."""
    statistics_service = StatisticsService()
    result = statistics_service.get_licenses_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_contributions_statistics(request):
    """API endpoint for contributions statistics."""
    statistics_service = StatisticsService()
    result = statistics_service.get_contributions_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_projects_statistics(request):
    """API endpoint for projects statistics."""
    statistics_service = StatisticsService()
    result = statistics_service.get_projects_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_filters_data(request):
    """API endpoint for getting filter options."""
    statistics_service = StatisticsService()
    result = statistics_service.get_filters_data(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_inventory_statistics(request):
    """API endpoint for inventory and rental statistics."""
    statistics_service = StatisticsService()
    result = statistics_service.get_inventory_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_funnel_metrics(request):
    """API endpoint for funnel metrics."""
    statistics_service = StatisticsService()
    result = statistics_service.get_funnel_metrics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_funnel_breakdown(request):
    """API endpoint for detailed funnel breakdown."""
    statistics_service = StatisticsService()
    result = statistics_service.get_funnel_breakdown(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_funnel_trends(request):
    """API endpoint for funnel trends over time."""
    statistics_service = StatisticsService()
    result = statistics_service.get_funnel_trends(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_recent_licenses(request):
    """API endpoint for recent license activities."""
    statistics_service = StatisticsService()
    result = statistics_service.get_recent_licenses(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_system_status(request):
    """API endpoint for system status checks."""
    try:
        from django.core.cache import cache
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from django.core.mail import send_mail
        from django.db import connection
        from django.utils import timezone
        import os

        status_checks = {}

        # Check Database Status
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    status_checks['database'] = {
                        'status': 'healthy',
                        'message': 'Database connection successful',
                        'response_time': '< 1ms'
                    }
                else:
                    status_checks['database'] = {
                        'status': 'error',
                        'message': 'Database query failed',
                        'response_time': 'N/A'
                    }
        except Exception as e:
            status_checks['database'] = {
                'status': 'error',
                'message': f'Database connection failed: {str(e)}',
                'response_time': 'N/A'
            }

        # Check API Services Status
        try:
            # Check if we can perform basic database operations
            Profile.objects.first()
            status_checks['api_services'] = {
                'status': 'healthy',
                'message': 'API services responding',
                'response_time': '< 1ms'
            }
        except Exception as e:
            status_checks['api_services'] = {
                'status': 'error',
                'message': f'API services error: {str(e)}',
                'response_time': 'N/A'
            }

        # Check File Storage Status
        try:
            # Test file storage by checking if we can access the storage
            test_file_path = 'system_status_test.txt'
            test_content = f'System status check at {timezone.now()}'

            # Try to write a test file
            default_storage.save(test_file_path, ContentFile(test_content.encode()))

            # Try to read it back
            if default_storage.exists(test_file_path):
                # Clean up test file
                default_storage.delete(test_file_path)
                status_checks['file_storage'] = {
                    'status': 'healthy',
                    'message': 'File storage accessible',
                    'response_time': '< 10ms'
                }
            else:
                status_checks['file_storage'] = {
                    'status': 'warning',
                    'message': 'File storage partially accessible',
                    'response_time': 'N/A'
                }
        except Exception as e:
            status_checks['file_storage'] = {
                'status': 'error',
                'message': f'File storage error: {str(e)}',
                'response_time': 'N/A'
            }

        # Check Email Service Status
        try:
            # Check email configuration
            from django.conf import settings

            if hasattr(settings, 'EMAIL_BACKEND'):
                if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                    status_checks['email_service'] = {
                        'status': 'warning',
                        'message': 'Email service in development mode (console backend)',
                        'response_time': 'N/A'
                    }
                else:
                    # Test email configuration without actually sending
                    if (settings.EMAIL_HOST and
                        settings.EMAIL_PORT and
                        settings.EMAIL_HOST_USER):
                        status_checks['email_service'] = {
                            'status': 'healthy',
                            'message': 'Email service configured',
                            'response_time': 'N/A'
                        }
                    else:
                        status_checks['email_service'] = {
                            'status': 'warning',
                            'message': 'Email service not fully configured',
                            'response_time': 'N/A'
                        }
            else:
                status_checks['email_service'] = {
                    'status': 'error',
                    'message': 'Email backend not configured',
                    'response_time': 'N/A'
                }
        except Exception as e:
            status_checks['email_service'] = {
                'status': 'error',
                'message': f'Email service error: {str(e)}',
                'response_time': 'N/A'
            }

        # Calculate overall system health
        healthy_count = sum(1 for check in status_checks.values() if check['status'] == 'healthy')
        warning_count = sum(1 for check in status_checks.values() if check['status'] == 'warning')
        error_count = sum(1 for check in status_checks.values() if check['status'] == 'error')

        if error_count > 0:
            overall_status = 'error'
            overall_message = f'{error_count} service(s) down'
        elif warning_count > 0:
            overall_status = 'warning'
            overall_message = f'{warning_count} service(s) with warnings'
        else:
            overall_status = 'healthy'
            overall_message = 'All systems operational'

        return JsonResponse({
            'success': True,
            'data': {
                'overall_status': overall_status,
                'overall_message': overall_message,
                'checks': status_checks,
                'summary': {
                    'total_services': len(status_checks),
                    'healthy': healthy_count,
                    'warnings': warning_count,
                    'errors': error_count
                },
                'timestamp': timezone.now().isoformat()
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_quick_stats(request):
    """API endpoint for quick statistics overview."""
    try:
        from datetime import timedelta
        from django.utils import timezone

        # Initialize filters
        filters = DashboardFilters(request)

        # Get base querysets
        profiles_queryset = Profile.objects.all()
        filtered_profiles = filters.apply_filters_to_queryset(profiles_queryset, 'profile')

        # Active Users (verified users)
        active_users = filtered_profiles.filter(verified=True).count()

        # Get license statistics
        try:
            from licenses.models import License
            licenses_queryset = License.objects.all()
            filtered_licenses = filters.apply_filters_to_queryset(licenses_queryset, 'license')

            confirmed_licenses = filtered_licenses.filter(confirmed=True).count()
            pending_licenses = filtered_licenses.filter(confirmed=False).count()
        except ImportError:
            confirmed_licenses = 0
            pending_licenses = 0

        # Get contribution statistics
        try:
            from contributions.models import Contribution
            contributions_queryset = Contribution.objects.all()
            filtered_contributions = filters.apply_filters_to_queryset(contributions_queryset, 'contribution')

            live_contributions = filtered_contributions.filter(live=True).count()
        except ImportError:
            live_contributions = 0

        # Calculate changes (placeholder - would need historical data)
        # For now, return 0 for all changes
        changes = {
            'active_users': 0,
            'confirmed_licenses': 0,
            'live_contributions': 0,
            'pending_licenses': 0
        }

        data = {
            'active_users': {
                'value': active_users,
                'change': changes['active_users'],
                'change_type': 'positive' if changes['active_users'] >= 0 else 'negative'
            },
            'confirmed_licenses': {
                'value': confirmed_licenses,
                'change': changes['confirmed_licenses'],
                'change_type': 'positive' if changes['confirmed_licenses'] >= 0 else 'negative'
            },
            'live_contributions': {
                'value': live_contributions,
                'change': changes['live_contributions'],
                'change_type': 'positive' if changes['live_contributions'] >= 0 else 'negative'
            },
            'pending_licenses': {
                'value': pending_licenses,
                'change': changes['pending_licenses'],
                'change_type': 'positive' if changes['pending_licenses'] >= 0 else 'negative'
            }
        }

        return JsonResponse({
            'success': True,
            'data': data,
            'timestamp': timezone.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_licenses_detail(request):
    """API endpoint for detailed licenses data."""
    try:
        from ..widgets.licenses import LicensesWidget

        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        type_filter = request.GET.get('type', 'total')

        widget = LicensesWidget(request)
        data = widget.get_detailed_data(page=page, per_page=per_page, type_filter=type_filter)

        return JsonResponse({
            'success': True,
            'data': data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_contributions_detail(request):
    """API endpoint for detailed contributions data."""
    try:
        from ..widgets.contributions import ContributionsWidget

        # Get parameters from request
        contribution_type = request.GET.get('type', 'total')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))

        # Initialize widget
        widget = ContributionsWidget(request)

        # Get detailed contributions based on type with pagination
        data = widget.get_detailed_contributions(contribution_type, page, per_page)

        return JsonResponse({
            'success': True,
            'data': data
        })

    except Exception as e:
        import traceback
        print(f"Error in api_contributions_detail: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_projects_detail(request):
    """API endpoint for detailed projects data with pagination and filtering."""
    try:
        from ..widgets.projects import ProjectsWidget
        from django.core.paginator import Paginator

        # Get parameters
        project_type = request.GET.get('type', 'total')  # total, participants, average, external, youth_protection, democracy
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))

        widget = ProjectsWidget(request)

        # Get detailed projects based on type
        if project_type == 'total':
            # Show all projects
            data = widget.get_detailed_projects()
        elif project_type == 'participants':
            # Show projects with participants > 0
            data = widget.get_detailed_projects_by_participants()
        elif project_type == 'average':
            # Show projects with average participants
            data = widget.get_detailed_projects_by_average_participants()
        elif project_type == 'external':
            # Show external venue projects
            data = widget.get_detailed_projects('external')
        elif project_type == 'youth_protection':
            # Show youth protection projects
            data = widget.get_detailed_projects('youth_protection')
        elif project_type == 'democracy':
            # Show democracy projects
            data = widget.get_detailed_projects('democracy')
        else:
            # Default to all projects
            data = widget.get_detailed_projects()

        # Apply pagination
        paginator = Paginator(data['projects'], per_page)
        page_obj = paginator.get_page(page)

        return JsonResponse({
            'success': True,
            'data': {
                'projects': list(page_obj),
                'total_count': data['total_count'],
                'displayed_count': len(page_obj),
                'current_page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            }
        })

    except Exception as e:
        import traceback
        print(f"Error in api_projects_detail: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_inventory_detail(request):
    """API endpoint for detailed inventory data."""
    statistics_service = StatisticsService()
    result = statistics_service.get_inventory_detail(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_funnel_detail(request):
    """API endpoint for funnel detail data."""
    statistics_service = StatisticsService()
    result = statistics_service.get_funnel_detail(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(lambda u: u.is_staff)
def api_media_data_statistics(request):
    """API endpoint for media data statistics."""
    statistics_service = StatisticsService()
    result = statistics_service.get_media_data_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)