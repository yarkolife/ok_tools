from ..widgets.filters import DashboardFilters
from ..widgets.media_data import MediaDataWidget
from ..widgets.inventory import InventoryWidget
from contributions.models import Contribution
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from licenses.models import Category
from licenses.models import License
from django.utils.translation import gettext_lazy as _
from registration.models import MediaAuthority
from registration.models import Profile


class StatisticsService:
    """Service class for handling statistics-related business logic."""
    
    def __init__(self, request=None):
        self.request = request
    
    def get_licenses_statistics(self, request):
        """Get licenses statistics."""
        try:
            # Create cache key based on request parameters
            cache_key = f"licenses_stats_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            from ..widgets.licenses import LicensesWidget

            # Initialize widget
            widget = LicensesWidget(request)

            # Get all data
            data = widget.get_data()

            result = {'success': True, 'data': data}
            
            # Cache for 30 minutes
            cache.set(cache_key, result, 1800)
            
            return result

        except Exception as e:
            import traceback
            print(f"Error in get_licenses_statistics: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_contributions_statistics(self, request):
        """Get contributions statistics."""
        try:
            # Create cache key based on request parameters
            cache_key = f"contributions_stats_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            from ..widgets.contributions import ContributionsWidget

            # Initialize widget
            widget = ContributionsWidget(request)

            # Get all data
            data = widget.get_data()

            result = {'success': True, 'data': data}
            
            # Cache for 30 minutes
            cache.set(cache_key, result, 1800)
            
            return result

        except Exception as e:
            import traceback
            print(f"Error in get_contributions_statistics: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_projects_statistics(self, request):
        """Get projects statistics."""
        try:
            # Create cache key based on request parameters
            cache_key = f"projects_stats_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            from ..widgets.projects import ProjectsWidget

            # Initialize widget
            widget = ProjectsWidget(request)

            # Get all data
            data = widget.get_data()

            result = {'success': True, 'data': data}
            
            # Cache for 30 minutes
            cache.set(cache_key, result, 1800)
            
            return result

        except Exception as e:
            import traceback
            print(f"Error in get_projects_statistics: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_filters_data(self, request):
        """Get filter options for dashboard."""
        try:
            # Initialize filters to get context
            filters = DashboardFilters(request)

            # Get real media authorities from database
            try:
                media_authorities = MediaAuthority.objects.all().order_by('name')
                media_authorities_data = [{'name': authority.name} for authority in media_authorities]
            except Exception as e:
                media_authorities_data = []

            # Get gender choices from Profile model
            try:
                gender_choices = list(Profile.Gender.choices)
            except Exception as e:
                gender_choices = [
                    ('m', 'Male'),
                    ('f', 'Female'),
                    ('d', 'Diverse')
                ]

            # Get license categories from Category model
            try:
                from licenses.models import Category
                categories = Category.objects.all().order_by('name')
                category_choices = [{'id': cat.id, 'name': cat.name} for cat in categories]
            except Exception as e:
                category_choices = []

            # Get project categories from ProjectCategory model
            try:
                from projects.models import ProjectCategory
                project_categories = ProjectCategory.objects.all().order_by('name')
                project_category_choices = [{'id': cat.id, 'name': cat.name} for cat in project_categories]
            except Exception as e:
                project_category_choices = []

            # Get target groups from TargetGroup model
            try:
                from projects.models import TargetGroup
                target_groups = TargetGroup.objects.all().order_by('name')
                target_group_choices = [{'id': group.id, 'name': group.name} for group in target_groups]
            except Exception as e:
                target_group_choices = []

            # Get project leaders from ProjectLeader model
            try:
                from projects.models import ProjectLeader
                project_leaders = ProjectLeader.objects.all().order_by('name')
                project_leader_choices = [{'id': leader.id, 'name': leader.name} for leader in project_leaders]
            except Exception as e:
                project_leader_choices = []

            # Age groups
            age_groups = [
                ('under_18', 'Under 18'),
                ('18_25', '18-25'),
                ('26_35', '26-35'),
                ('36_50', '36-50'),
                ('over_50', 'Over 50')
            ]

            # Member and verification choices
            member_choices = [
                ('', 'All Users'),
                ('true', 'Members Only'),
                ('false', 'Non-Members Only')
            ]

            verified_choices = [
                ('', 'All Users'),
                ('true', 'Verified Only'),
                ('false', 'Not Verified')
            ]

            # Date range options
            date_range_options = [
                (7, 'Last 7 days'),
                (30, 'Last 30 days'),
                (90, 'Last 90 days'),
                (365, 'Last year'),
                ('all', 'All Time'),
                ('custom', 'Custom Period')
            ]

            # Inventory-specific data
            try:
                from inventory.models import Category as InventoryCategory
                from inventory.models import Location
                from inventory.models import Organization

                # Organizations (owners)
                organizations = Organization.objects.all().values('id', 'name').order_by('name')
                # Locations
                locations = Location.objects.all().values('id', 'name').order_by('name')

                # Inventory categories (using inventory categories)
                inventory_categories = InventoryCategory.objects.all().values('id', 'name').order_by('name')

            except Exception as e:
                print(f"Error loading inventory data: {e}")
                import traceback
                traceback.print_exc()
                organizations = []
                locations = []
                inventory_categories = []

            response_data = {
                'success': True,
                'data': {
                    'context': {
                        'media_authorities': media_authorities_data,
                        'gender_choices': gender_choices,
                        'category_choices': category_choices,
                        'project_categories': project_category_choices,
                        'target_groups': target_group_choices,
                        'project_leaders': project_leader_choices,
                        'age_groups': age_groups,
                        'member_choices': member_choices,
                        'verified_choices': verified_choices,
                        'date_range_options': date_range_options
                    },
                    'filters': filters.get_all_data()
                },
                # Direct access for inventory widget
                'media_authorities': media_authorities_data,
                'organizations': list(organizations),
                'locations': list(locations),
                'inventory_categories': list(inventory_categories)
            }

            return response_data

        except Exception as e:
            import traceback
            print(f"Error in get_filters_data: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_inventory_statistics(self, request):
        """Get inventory and rental statistics."""
        try:
            # Create cache key based on request parameters
            cache_key = f"inventory_stats_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            # Initialize filters
            filters = DashboardFilters(request)

            # Get filter parameters
            filter_params = {}
            if 'days' in request.GET:
                filter_params['days'] = request.GET['days']
            if 'start_date' in request.GET:
                filter_params['start_date'] = request.GET['start_date']
            if 'end_date' in request.GET:
                filter_params['end_date'] = request.GET['end_date']

            # Extended filters
            if 'gender' in request.GET and request.GET['gender'] not in ['', 'undefined', 'null']:
                filter_params['gender'] = request.GET['gender']
            if 'member' in request.GET and request.GET['member'] not in ['', 'undefined', 'null']:
                filter_params['member'] = request.GET['member']
            if 'category' in request.GET and request.GET['category'] not in ['', 'undefined', 'null']:
                filter_params['category'] = request.GET['category']
            if 'owner' in request.GET and request.GET['owner'] not in ['', 'undefined', 'null']:
                filter_params['owner'] = request.GET['owner']
            if 'location' in request.GET and request.GET['location'] not in ['', 'undefined', 'null']:
                filter_params['location'] = request.GET['location']
            if 'status' in request.GET and request.GET['status'] not in ['', 'undefined', 'null']:
                filter_params['status'] = request.GET['status']

            # Initialize inventory widget
            inventory_widget = InventoryWidget(filter_params)

            # Get all data
            data = inventory_widget.get_all_data()

            response_data = {
                'success': True,
                'data': data
            }
            
            # Cache for 15 minutes (inventory data changes more frequently)
            cache.set(cache_key, response_data, 900)

            return response_data

        except Exception as e:
            import traceback
            print(f"Error in get_inventory_statistics: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_funnel_metrics(self, request):
        """Get funnel metrics."""
        try:
            # Create cache key based on request parameters
            cache_key = f"funnel_metrics_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            from ..utils import FunnelTracker

            # Get date range from request
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            days = request.GET.get('days')

            if days and days != 'all' and days != 'custom':
                # Convert days to date range
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=int(days))
            elif days == 'all':
                # All time - no date filtering
                start_date = None
                end_date = None
            elif days == 'custom':
                # Custom date range - use provided dates
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            elif start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date and not days:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            # Get additional filters
            filters = {
                'media_authority': request.GET.get('media_authority'),
                'gender': request.GET.get('gender'),
                'age_group': request.GET.get('age_group'),
                'category': request.GET.get('category'),
                'status': request.GET.get('status')
            }

            # Get funnel metrics
            tracker = FunnelTracker()
            metrics = tracker.get_funnel_metrics(start_date, end_date, filters)
            breakdown = tracker.get_stage_breakdown(start_date, end_date, filters)

            result = {
                'success': True,
                'data': {
                    'metrics': metrics['metrics'],
                    'conversion_rates': metrics['conversion_rates'],
                    'funnel_data': breakdown
                }
            }
            
            # Cache for 20 minutes
            cache.set(cache_key, result, 1200)
            
            return result

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_funnel_breakdown(self, request):
        """Get detailed funnel breakdown."""
        try:
            from ..utils import FunnelTracker

            # Get date range from request
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            # Get stage breakdown
            tracker = FunnelTracker()
            breakdown = tracker.get_stage_breakdown(start_date, end_date)

            return {
                'success': True,
                'data': breakdown
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_funnel_trends(self, request):
        """Get funnel trends over time."""
        try:
            from ..utils import FunnelTracker

            # Get date range from request
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            days = request.GET.get('days', '30')
            if days == 'all':
                start_date = None
                end_date = None
            elif days == 'custom':
                # Custom date range - use provided dates
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                days = int(days)
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=days)

            # Get additional filters
            filters = {
                'media_authority': request.GET.get('media_authority'),
                'gender': request.GET.get('gender'),
                'age_group': request.GET.get('age_group'),
                'category': request.GET.get('category'),
                'status': request.GET.get('status')
            }

            # Get trends data
            tracker = FunnelTracker()
            trends = tracker.get_funnel_trends(start_date, end_date, filters)

            return {
                'success': True,
                'data': trends
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_recent_licenses(self, request):
        """Get recent license activities."""
        try:
            # Get recent licenses (last 7 days by default)
            days = int(request.GET.get('days', 7))
            since_date = timezone.now() - timedelta(days=days)

            # Get recent license activities
            activities = []

            # Get recent licenses
            try:
                recent_licenses = License.objects.filter(
                    created_at__gte=since_date
                ).select_related('profile__okuser', 'profile__media_authority').order_by('-created_at')[:10]

                for license in recent_licenses:
                    status_color = 'success' if license.confirmed else 'warning'
                    status_icon = 'bi-check-circle' if license.confirmed else 'bi-clock'
                    status_text = 'confirmed' if license.confirmed else 'pending'

                    activities.append({
                        'type': 'license_created',
                        'title': f'License {status_text}: {license.title}',
                        'user_name': f'{license.profile.first_name} {license.profile.last_name}',
                        'user_email': license.profile.okuser.email if license.profile.okuser else '',
                        'timestamp': license.created_at,
                        'icon': status_icon,
                        'color': status_color,
                        'license_id': license.id
                    })

            except ImportError:
                # If licenses app is not available, return empty list
                pass

            # Sort all activities by timestamp
            activities.sort(key=lambda x: x['timestamp'], reverse=True)

            # Format timestamps for display
            for activity in activities:
                time_diff = timezone.now() - activity['timestamp']
                if time_diff.days > 0:
                    activity['time_ago'] = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
                elif time_diff.seconds > 3600:
                    hours = time_diff.seconds // 3600
                    activity['time_ago'] = f"{hours} hour{'s' if hours > 1 else ''} ago"
                else:
                    minutes = time_diff.seconds // 60
                    activity['time_ago'] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"

            return {
                'success': True,
                'data': {
                    'activities': activities[:5],  # Limit to 5 most recent
                    'total_count': len(activities),
                    'period_days': days
                }
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_system_status(self, request):
        """Get system status checks."""
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

            return {
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
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_quick_stats(self, request):
        """Get quick statistics overview."""
        try:
            # Create cache key based on request parameters
            cache_key = f"quick_stats_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            # Initialize filters
            filters = DashboardFilters(request)

            # Get base querysets
            profiles_queryset = Profile.objects.all()
            filtered_profiles = filters.apply_filters_to_queryset(profiles_queryset, 'profile')

            # Active Users (verified users)
            active_users = filtered_profiles.filter(verified=True).count()

            # Get license statistics
            try:
                licenses_queryset = License.objects.all()
                filtered_licenses = filters.apply_filters_to_queryset(licenses_queryset, 'license')

                confirmed_licenses = filtered_licenses.filter(confirmed=True).count()
                pending_licenses = filtered_licenses.filter(confirmed=False).count()
            except ImportError:
                confirmed_licenses = 0
                pending_licenses = 0

            # Get contribution statistics
            try:
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

            result = {
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            }
            
            # Cache for 10 minutes (quick stats should be relatively fresh)
            cache.set(cache_key, result, 600)
            
            return result

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_licenses_detail(self, request):
        """Get detailed licenses data."""
        try:
            from ..widgets.licenses import LicensesWidget

            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            type_filter = request.GET.get('type', 'total')

            widget = LicensesWidget(request)
            data = widget.get_detailed_data(page=page, per_page=per_page, type_filter=type_filter)

            return {
                'success': True,
                'data': data
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_contributions_detail(self, request):
        """Get detailed contributions data."""
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

            return {
                'success': True,
                'data': data
            }

        except Exception as e:
            import traceback
            print(f"Error in get_contributions_detail: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_projects_detail(self, request):
        """Get detailed projects data with pagination and filtering."""
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

            return {
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
            }

        except Exception as e:
            import traceback
            print(f"Error in get_projects_detail: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            logger = __import__('logging').getLogger(__name__)
            logger.error(_('Error calculating statistics: %s'), e)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_inventory_detail(self, request):
        """Get detailed inventory data."""
        try:
            # Get the type parameter from request
            inventory_type = request.GET.get('type', 'total')

            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))

            # Create filters dict from request parameters
            filters_dict = {}
            for key, value in request.GET.items():
                if key not in ['type', 'page', 'per_page'] and value:
                    filters_dict[key] = value

            # Initialize widget with filters dict
            widget = InventoryWidget(filters_dict)

            # Get detailed inventory data based on type with pagination
            data = widget.get_detailed_inventory(inventory_type, page, per_page)

            return {
                'success': True,
                'data': data
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_funnel_detail(self, request):
        """Get funnel detail data."""
        try:
            from ..utils import FunnelTracker

            # Get parameters
            type_filter = request.GET.get('type', 'registrations')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            days = request.GET.get('days')

            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))

            # Calculate date range
            if days and days != 'all' and days != 'custom':
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=int(days))
            elif days == 'all':
                start_date = None
                end_date = None
            elif days == 'custom':
                # Custom date range - use provided dates
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            elif start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date and not days:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            # Get additional filters
            filters = {
                'media_authority': request.GET.get('media_authority'),
                'gender': request.GET.get('gender'),
                'age_group': request.GET.get('age_group'),
                'category': request.GET.get('category'),
                'status': request.GET.get('status')
            }

            # Get data based on type
            tracker = FunnelTracker()

            if type_filter == 'registrations':
                data = tracker.get_registrations_detail(start_date, end_date, filters, page, per_page)
            elif type_filter == 'verified':
                data = tracker.get_verified_detail(start_date, end_date, filters, page, per_page)
            elif type_filter == 'licenses':
                data = tracker.get_licenses_detail(start_date, end_date, filters, page, per_page)
            elif type_filter == 'broadcasts':
                data = tracker.get_broadcasts_detail(start_date, end_date, filters, page, per_page)
            else:
                return {
                    'success': False,
                    'error': 'Invalid type filter'
                }

            return {
                'success': True,
                'data': data
            }

        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }
    
    def get_media_data_statistics(self, request):
        """Get media data statistics."""
        try:
            # Create cache key based on request parameters
            cache_key = f"media_data_stats_{request.GET.urlencode()}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
                
            # Initialize media data widget
            media_data_widget = MediaDataWidget(request)
            
            # Get all data
            data = media_data_widget.get_all_data()
            
            # Add categories to context
            data['filters']['context']['categories'] = [
                {'id': cat.id, 'name': cat.name}
                for cat in Category.objects.all().order_by('name')
            ]
            
            result = {
                'success': True,
                'data': data
            }
            
            # Cache for 25 minutes
            cache.set(cache_key, result, 1500)
            
            return result
            
        except Exception as e:
            
            return {
                'success': False,
                'error': _('Data retrieval failed')
            }