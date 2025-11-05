from ..widgets.filters import DashboardFilters
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


class UserService:
    """Service class for handling user-related business logic."""
    
    def __init__(self, request=None):
        self.request = request
    
    def get_users_statistics(self, request):
        """
        Get comprehensive user statistics including demographics, 
        registration trends, and other metrics.
        """
        try:
            # Initialize filters
            filters = DashboardFilters(request)

            # Get base queryset
            queryset = Profile.objects.all()

            # Apply filters
            filtered_queryset = filters.apply_filters_to_queryset(queryset, 'profile')

            # Calculate basic statistics
            total_users = filtered_queryset.count()

            # Gender distribution
            male_users = filtered_queryset.filter(gender='m').count()
            female_users = filtered_queryset.filter(gender='f').count()
            diverse_users = filtered_queryset.filter(gender='d').count()

            # Verification and membership
            verified_users = filtered_queryset.filter(verified=True).count()
            member_users = filtered_queryset.filter(member=True).count()
            global_producer_users = filtered_queryset.filter(global_producer=True).count()

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
                'up_to_34': 0,
                '35_50': 0,
                '51_65': 0,
                'over_65': 0,
                'unknown': 0
            }

            try:
                for profile in filtered_queryset.select_related('media_authority'):
                    if profile.birthday:
                        # Check if birthday is the default unknown date (01.01.1800)
                        if profile.birthday.year == 1800 and profile.birthday.month == 1 and profile.birthday.day == 1:
                            age_groups['unknown'] += 1
                        else:
                            # Use current date if end_date is None (fallback for old code)
                            end_date = filters.date_range['end_date'] or datetime.now().date()
                            age = relativedelta(end_date, profile.birthday).years
                            if age <= 34:
                                age_groups['up_to_34'] += 1
                            elif age <= 50:
                                age_groups['35_50'] += 1
                            elif age <= 65:
                                age_groups['51_65'] += 1
                            else:
                                age_groups['over_65'] += 1
                    else:
                        age_groups['unknown'] += 1
            except Exception:
                # If there's an error calculating ages, keep default values
                pass

            # Registration trend based on selected period
            try:
                start_date = filters.date_range['start_date']
                end_date = filters.date_range['end_date']
                registration_trend = []

                # If no date range (days=all), skip trend generation
                if start_date is None or end_date is None:
                    registration_trend = []
                else:
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
                registration_trend = []

            # Member distribution
            member_distribution = {
                'members': member_users,
                'non_members': total_users - member_users
            }

            # Age-Gender distribution
            age_gender_distribution = {
                'female': {
                    'up_to_34': 0,
                    '35_50': 0,
                    '51_65': 0,
                    'over_65': 0,
                    'unknown': 0
                },
                'male': {
                    'up_to_34': 0,
                    '35_50': 0,
                    '51_65': 0,
                    'over_65': 0,
                    'unknown': 0
                },
                'diverse': {
                    'up_to_34': 0,
                    '35_50': 0,
                    '51_65': 0,
                    'over_65': 0,
                    'unknown': 0
                },
                'unspecified': {
                    'up_to_34': 0,
                    '35_50': 0,
                    '51_65': 0,
                    'over_65': 0,
                    'unknown': 0
                }
            }

            try:
                for profile in filtered_queryset.select_related('media_authority'):
                    # Determine gender category
                    gender_key = 'unspecified'
                    if profile.gender == 'f':
                        gender_key = 'female'
                    elif profile.gender == 'm':
                        gender_key = 'male'
                    elif profile.gender == 'd':
                        gender_key = 'diverse'
                    
                    # Determine age group
                    age_group_key = 'unknown'
                    if profile.birthday:
                        # Check if birthday is the default unknown date (01.01.1800)
                        if profile.birthday.year == 1800 and profile.birthday.month == 1 and profile.birthday.day == 1:
                            age_group_key = 'unknown'
                        else:
                            # Use current date if end_date is None (fallback for old code)
                            end_date = filters.date_range['end_date'] or datetime.now().date()
                            age = relativedelta(end_date, profile.birthday).years
                            if age <= 34:
                                age_group_key = 'up_to_34'
                            elif age <= 50:
                                age_group_key = '35_50'
                            elif age <= 65:
                                age_group_key = '51_65'
                            else:
                                age_group_key = 'over_65'
                    else:
                        age_group_key = 'unknown'
                    
                    # Increment the count
                    age_gender_distribution[gender_key][age_group_key] += 1
            except Exception:
                # If there's an error, keep default values
                pass

            # Get filters data with error handling
            try:
                filters_data = filters.get_all_data()
            except Exception as e:
                filters_data = {}

            data = {
                'basic_stats': {
                    'total_users': total_users,
                    'male_users': male_users,
                    'female_users': female_users,
                    'diverse_users': diverse_users,
                    'verified_users': verified_users,
                    'member_users': member_users,
                    'global_producer_users': global_producer_users,
                },
                'users_by_authority': users_by_authority,
                'age_groups': age_groups,
                'age_gender_distribution': age_gender_distribution,
                'registration_trend': registration_trend,
                'member_distribution': member_distribution,
                'filters': filters_data,
            }

            return {'success': True, 'data': data}

        except Exception as e:
            import traceback
            print(f"Error in get_users_statistics: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_recent_users(self, request):
        """
        Get recent user activities including new registrations, 
        profile verifications, and license activities.
        """
        try:
            # Get recent profiles (last 7 days by default)
            days = int(request.GET.get('days', 7))
            since_date = timezone.now() - timedelta(days=days)

            # Get recent profiles
            recent_profiles = Profile.objects.filter(
                created_at__gte=since_date
            ).order_by('-created_at')[:10]

            # Get recent user activities
            activities = []

            # Add newly registered users
            for profile in recent_profiles.select_related('okuser'):
                activities.append({
                    'type': 'user_registered',
                    'title': f'New user registered: {profile.first_name} {profile.last_name}',
                    'user_name': f'{profile.first_name} {profile.last_name}',
                    'user_email': profile.okuser.email if profile.okuser else '',
                    'timestamp': profile.created_at,
                    'icon': 'bi-person-plus',
                    'color': 'success'
                })

            # Get recent profile updates (if we had updated_at field)
            # For now, we'll use verified status changes as an example
            recently_verified = Profile.objects.filter(
                verified=True,
                created_at__gte=since_date
            ).select_related('okuser').order_by('-created_at')[:5]
            
            for profile in recently_verified:
                activities.append({
                    'type': 'profile_verified',
                    'title': f'Profile verified: {profile.first_name} {profile.last_name}',
                    'user_name': f'{profile.first_name} {profile.last_name}',
                    'user_email': profile.okuser.email if profile.okuser else '',
                    'timestamp': profile.created_at,
                    'icon': 'bi-check-circle',
                    'color': 'info'
                })

            # Get recent license activities
            try:
                recent_licenses = License.objects.filter(
                    created_at__gte=since_date
                ).select_related('profile__okuser', 'profile__media_authority').order_by('-created_at')[:5]

                for license in recent_licenses:
                    activities.append({
                        'type': 'license_created',
                        'title': f'License created: {license.title}',
                        'user_name': f'{license.profile.first_name} {license.profile.last_name}',
                        'user_email': license.profile.okuser.email if license.profile.okuser else '',
                        'timestamp': license.created_at,
                        'icon': 'bi-file-earmark-text',
                        'color': 'primary'
                    })
            except ImportError:
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
                'error': str(e)
            }
    
    def get_users_detail(self, request):
        """
        Get detailed user data with pagination and filtering.
        """
        try:
            filters = DashboardFilters(request)
            queryset = Profile.objects.all()
            filtered_queryset = filters.apply_filters_to_queryset(queryset, 'profile')
            
            # PERFORMANCE OPTIMIZATION: Add select_related for FK accessed in loop
            filtered_queryset = filtered_queryset.select_related('okuser', 'media_authority')

            # Apply additional filtering based on type parameter
            type_filter = request.GET.get('type', 'total')
            if type_filter == 'male':
                filtered_queryset = filtered_queryset.filter(gender='m')
            elif type_filter == 'female':
                filtered_queryset = filtered_queryset.filter(gender='f')
            elif type_filter == 'verified':
                filtered_queryset = filtered_queryset.filter(verified=True)
            elif type_filter == 'member':
                filtered_queryset = filtered_queryset.filter(member=True)
            # For 'total' type, no additional filtering needed

            # Pagination
            page = int(request.GET.get('page', 1))
            per_page = 20  # Users per page
            start = (page - 1) * per_page
            end = start + per_page

            # Get total count for pagination
            total_count = filtered_queryset.count()

            # Get detailed user data for current page
            users_data = []
            for profile in filtered_queryset[start:end]:
                # Calculate age from birthday
                age = None
                if profile.birthday:
                    from datetime import date
                    today = date.today()
                    age = today.year - profile.birthday.year - ((today.month, today.day) < (profile.birthday.month, profile.birthday.day))

                users_data.append({
                    'id': profile.id,
                    'name': f"{profile.first_name} {profile.last_name}".strip(),
                    'email': profile.okuser.email if profile.okuser and hasattr(profile.okuser, 'email') else '',
                    'gender': profile.get_gender_display(),
                    'age': age,
                    'verified': profile.verified,
                    'member': profile.member,
                    'media_authority': profile.media_authority.name if profile.media_authority else '',
                    'city': profile.city or '',
                    'created_at': profile.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(profile, 'created_at') else None
                })

            # Calculate pagination info
            total_pages = (total_count + per_page - 1) // per_page
            has_previous = page > 1
            has_next = page < total_pages

            return {
                'success': True,
                'data': {
                    'users': users_data,
                    'total_count': total_count,
                    'displayed_count': len(users_data),
                    'pagination': {
                        'current_page': page,
                        'total_pages': total_pages,
                        'per_page': per_page,
                        'has_previous': has_previous,
                        'has_next': has_next,
                        'start_index': start + 1,
                        'end_index': min(start + per_page, total_count)
                    }
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }