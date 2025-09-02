from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from registration.models import Profile, MediaAuthority
from licenses.models import License, Category
from contributions.models import Contribution
from .widgets.filters import DashboardFilters
from .widgets.inventory import InventoryWidget
from .widgets.notifications import NotificationsWidget


def is_admin(user):
    """Check if user is admin."""
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_admin)
def api_users_statistics(request):
    """API endpoint for users statistics."""
    try:
        print(f"DEBUG: api_users_statistics called with request: {request.GET}")
        
        # Initialize filters
        filters = DashboardFilters(request)
        print(f"DEBUG: filters initialized successfully")
        
        # Get base queryset
        queryset = Profile.objects.all()
        print(f"DEBUG: Base queryset has {queryset.count()} profiles")
        
        # Apply filters
        filtered_queryset = filters.apply_filters_to_queryset(queryset, 'profile')
        print(f"DEBUG: After filtering: {filtered_queryset.count()} profiles")
        
        # Calculate basic statistics
        total_users = filtered_queryset.count()
        
        # Gender distribution
        male_users = filtered_queryset.filter(gender='m').count()
        female_users = filtered_queryset.filter(gender='f').count()
        diverse_users = filtered_queryset.filter(gender='d').count()
        
        # Verification and membership
        verified_users = filtered_queryset.filter(verified=True).count()
        member_users = filtered_queryset.filter(member=True).count()
        
        # New users in the selected period
        try:
            # Check if created_at field exists in the model
            if hasattr(filtered_queryset.model, 'created_at'):
                new_users = filtered_queryset.filter(
                    created_at__date__gte=filters.date_range['start_date'],
                    created_at__date__lte=filters.date_range['end_date']
                ).count()
            else:
                # If created_at field doesn't exist, use total count
                new_users = total_users
        except Exception:
            # If there's an error, use total count
            new_users = total_users
        
        # Users by media authority
        try:
            users_by_authority = list(filtered_queryset.values(
                'media_authority__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            users_by_authority = []
        
        # Age groups
        age_groups = {
            'under_18': 0,
            '18_25': 0,
            '26_35': 0,
            '36_50': 0,
            'over_50': 0
        }
        
        try:
            for profile in filtered_queryset:
                if profile.birthday:
                    age = relativedelta(filters.date_range['end_date'], profile.birthday).years
                    if age < 18:
                        age_groups['under_18'] += 1
                    elif age < 26:
                        age_groups['18_25'] += 1
                    elif age < 36:
                        age_groups['26_35'] += 1
                    elif age < 51:
                        age_groups['36_50'] += 1
                    else:
                        age_groups['over_50'] += 1
        except Exception:
            # If there's an error calculating ages, keep default values
            pass
        
        # Registration trend based on selected period
        try:
            start_date = filters.date_range['start_date']
            end_date = filters.date_range['end_date']
            registration_trend = []
            
            # Calculate number of days in the period
            days_diff = (end_date - start_date).days
            
            # For periods longer than 30 days, group by weeks
            if days_diff > 30:
                # Group by weeks
                current_date = start_date
                while current_date <= end_date:
                    week_end = min(current_date + timedelta(days=6), end_date)
                    try:
                        if hasattr(filtered_queryset.model, 'created_at'):
                            count = filtered_queryset.filter(
                                created_at__date__gte=current_date,
                                created_at__date__lte=week_end
                            ).count()
                        else:
                            count = 0
                    except Exception:
                        count = 0
                    
                    registration_trend.append({
                        'date': f"{current_date.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}",
                        'count': count
                    })
                    
                    current_date = week_end + timedelta(days=1)
            else:
                # For shorter periods, show daily data
                current_date = start_date
                while current_date <= end_date:
                    try:
                        if hasattr(filtered_queryset.model, 'created_at'):
                            count = filtered_queryset.filter(
                                created_at__date=current_date
                            ).count()
                        else:
                            count = 0
                    except Exception:
                        count = 0
                    
                    registration_trend.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'count': count
                    })
                    
                    current_date += timedelta(days=1)
                    
        except Exception as e:
            print(f"DEBUG: Error calculating registration trend: {e}")
            registration_trend = []
        
        # Member distribution
        member_distribution = {
            'members': member_users,
            'non_members': total_users - member_users
        }
        
        # Get filters data with error handling
        try:
            filters_data = filters.get_all_data()
            print(f"DEBUG: filters_data type: {type(filters_data)}")
            print(f"DEBUG: filters_data: {filters_data}")
        except Exception as e:
            print(f"DEBUG: Error getting filters data: {e}")
            filters_data = {}
        
        data = {
            'basic_stats': {
                'total_users': total_users,
                'male_users': male_users,
                'female_users': female_users,
                'diverse_users': diverse_users,
                'verified_users': verified_users,
                'member_users': member_users,
                'new_users': new_users,
            },
            'users_by_authority': users_by_authority,
            'age_groups': age_groups,
            'registration_trend': registration_trend,
            'member_distribution': member_distribution,
            'filters': filters_data,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        import traceback
        print(f"Error in api_users_statistics: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_licenses_statistics(request):
    """API endpoint for licenses statistics."""
    try:
        from .widgets.licenses import LicensesWidget
        
        # Initialize widget
        widget = LicensesWidget(request)
        
        # Get all data
        data = widget.get_data()
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        import traceback
        print(f"Error in api_licenses_statistics: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_contributions_statistics(request):
    """API endpoint for contributions statistics."""
    try:
        from .widgets.contributions import ContributionsWidget
        
        # Initialize widget
        widget = ContributionsWidget(request)
        
        # Get all data
        data = widget.get_data()
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        import traceback
        print(f"Error in api_contributions_statistics: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_projects_statistics(request):
    """API endpoint for projects statistics."""
    try:
        from .widgets.projects import ProjectsWidget
        
        # Initialize widget
        widget = ProjectsWidget(request)
        
        # Get all data
        data = widget.get_data()
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        import traceback
        print(f"Error in api_projects_statistics: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)



@login_required
@user_passes_test(is_admin)
def api_filters_data(request):
    """API endpoint for getting filter options."""
    try:
        print(f"DEBUG: api_filters_data called with request: {request.GET}")
        
        # Initialize filters to get context
        filters = DashboardFilters(request)
        print(f"DEBUG: filters initialized successfully")
        
        # Get real media authorities from database
        try:
            media_authorities = MediaAuthority.objects.all().order_by('name')
            media_authorities_data = [{'name': authority.name} for authority in media_authorities]
            print(f"DEBUG: Found {len(media_authorities_data)} media authorities")
        except Exception as e:
            print(f"DEBUG: Error getting media authorities: {e}")
            media_authorities_data = []
        
        # Get gender choices from Profile model
        try:
            gender_choices = list(Profile.Gender.choices)
            print(f"DEBUG: Found {len(gender_choices)} gender choices")
        except Exception as e:
            print(f"DEBUG: Error getting gender choices: {e}")
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
            print(f"DEBUG: Found {len(category_choices)} license categories")
        except Exception as e:
            print(f"DEBUG: Error getting license categories: {e}")
            category_choices = []
        
        # Get project categories from ProjectCategory model
        try:
            from projects.models import ProjectCategory
            project_categories = ProjectCategory.objects.all().order_by('name')
            project_category_choices = [{'id': cat.id, 'name': cat.name} for cat in project_categories]
            print(f"DEBUG: Found {len(project_category_choices)} project categories")
        except Exception as e:
            print(f"DEBUG: Error getting project categories: {e}")
            project_category_choices = []
        
        # Get target groups from TargetGroup model
        try:
            from projects.models import TargetGroup
            target_groups = TargetGroup.objects.all().order_by('name')
            target_group_choices = [{'id': group.id, 'name': group.name} for group in target_groups]
            print(f"DEBUG: Found {len(target_group_choices)} target groups")
        except Exception as e:
            print(f"DEBUG: Error getting target groups: {e}")
            target_group_choices = []
        
        # Get project leaders from ProjectLeader model
        try:
            from projects.models import ProjectLeader
            project_leaders = ProjectLeader.objects.all().order_by('name')
            project_leader_choices = [{'id': leader.id, 'name': leader.name} for leader in project_leaders]
            print(f"DEBUG: Found {len(project_leader_choices)} project leaders")
        except Exception as e:
            print(f"DEBUG: Error getting project leaders: {e}")
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
            from inventory.models import Organization, Location, Category as InventoryCategory
            
            # Organizations (owners)
            organizations = Organization.objects.all().values('id', 'name').order_by('name')
            print(f"DEBUG: Found {len(organizations)} organizations")
            
            # Locations
            locations = Location.objects.all().values('id', 'name').order_by('name')
            print(f"DEBUG: Found {len(locations)} locations")
            
            # Inventory categories (using inventory categories)
            inventory_categories = InventoryCategory.objects.all().values('id', 'name').order_by('name')
            print(f"DEBUG: Found {len(inventory_categories)} inventory categories")
            
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
        
        print(f"DEBUG: Returning successful response")
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        print(f"Error in api_filters_data: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_inventory_statistics(request):
    """API endpoint for inventory and rental statistics."""
    try:
        print(f"DEBUG: api_inventory_statistics called with request: {request.GET}")
        
        # Initialize filters
        filters = DashboardFilters(request)
        print(f"DEBUG: filters initialized successfully")
        
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
        
        print(f"DEBUG: Returning successful response")
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        print(f"Error in api_inventory_statistics: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_admin)
def api_notifications_statistics(request):
    """API endpoint for notifications statistics"""
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
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
