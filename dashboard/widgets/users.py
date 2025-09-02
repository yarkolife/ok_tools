"""
Users widget for dashboard.
Provides user statistics and analytics.
"""

from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from registration.models import Profile, MediaAuthority
from .filters import DashboardFilters


class UsersWidget:
    """Widget for displaying user statistics."""
    
    def __init__(self, request):
        self.request = request
        self.filters = DashboardFilters(request)
    
    def get_basic_stats(self):
        """Get basic user statistics."""
        queryset = Profile.objects.all()
        filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
        
        # Calculate statistics
        total_users = filtered_queryset.count()
        male_users = filtered_queryset.filter(gender='m').count()
        female_users = filtered_queryset.filter(gender='f').count()
        diverse_users = filtered_queryset.filter(gender='d').count()
        verified_users = filtered_queryset.filter(verified=True).count()
        member_users = filtered_queryset.filter(member=True).count()
        
        # New users in period (already filtered by date range)
        try:
            # Check if created_at field exists in the model
            if hasattr(filtered_queryset.model, 'created_at'):
                new_users = filtered_queryset.filter(
                    created_at__date__gte=self.filters.date_range['start_date'],
                    created_at__date__lte=self.filters.date_range['end_date']
                ).count()
            else:
                # If created_at field doesn't exist, use total count
                new_users = filtered_queryset.count()
        except Exception:
            # If there's an error, use total count
            new_users = filtered_queryset.count()
        
        return {
            'total_users': total_users,
            'male_users': male_users,
            'female_users': female_users,
            'diverse_users': diverse_users,
            'verified_users': verified_users,
            'member_users': member_users,
            'new_users': new_users,
        }
    
    def get_users_by_authority(self):
        """Get user count by media authority."""
        try:
            queryset = Profile.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
            
            return list(filtered_queryset.values('media_authority__name').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            # Return empty list if there's an error
            return []
    
    def get_age_groups(self):
        """Get user count by age groups."""
        try:
            queryset = Profile.objects.exclude(birthday__isnull=True)
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
            
            # Calculate age groups
            age_groups = {
                'under_18': 0,
                '18_25': 0,
                '26_35': 0,
                '36_50': 0,
                'over_50': 0
            }
            
            for profile in filtered_queryset:
                if profile.birthday:
                    age = relativedelta(self.filters.date_range['end_date'], profile.birthday).years
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
            
            return age_groups
        except Exception:
            # Return default values if there's an error
            return {
                'under_18': 0,
                '18_25': 0,
                '26_35': 0,
                '36_50': 0,
                'over_50': 0
            }
    
    def get_registration_trend(self):
        """Get user registration trend over time."""
        try:
            queryset = Profile.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
            
            # Get last 7 days trend
            end_date = self.filters.date_range['end_date']
            trend_data = []
            
            for i in range(7):
                date = end_date - timedelta(days=i)
                try:
                    # Check if created_at field exists in the model
                    if hasattr(filtered_queryset.model, 'created_at'):
                        count = filtered_queryset.filter(
                            created_at__date=date
                        ).count()
                    else:
                        # If created_at field doesn't exist, use 0
                        count = 0
                except Exception:
                    # If there's an error, use 0
                    count = 0
                
                trend_data.insert(0, {
                    'date': date.strftime('%Y-%m-%d'),
                    'count': count
                })
            
            return trend_data
        except Exception:
            # Return empty trend if there's an error
            return []
    
    def get_gender_distribution(self):
        """Get gender distribution."""
        try:
            queryset = Profile.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
            
            return list(filtered_queryset.values('gender').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            # Return empty list if there's an error
            return []
    
    def get_member_distribution(self):
        """Get member vs non-member distribution."""
        queryset = Profile.objects.all()
        filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
        
        member_count = filtered_queryset.filter(member=True).count()
        non_member_count = filtered_queryset.filter(member=False).count()
        
        return {
            'members': member_count,
            'non_members': non_member_count
        }
    
    def get_verification_distribution(self):
        """Get verified vs non-verified distribution."""
        queryset = Profile.objects.all()
        filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'profile')
        
        verified_count = filtered_queryset.filter(verified=True).count()
        non_verified_count = filtered_queryset.filter(verified=False).count()
        
        return {
            'verified': verified_count,
            'not_verified': non_verified_count
        }
    
    def get_all_data(self):
        """Get all user statistics data."""
        return {
            'basic_stats': self.get_basic_stats(),
            'users_by_authority': list(self.get_users_by_authority()),
            'age_groups': self.get_age_groups(),
            'registration_trend': self.get_registration_trend(),
            'gender_distribution': list(self.get_gender_distribution()),
            'member_distribution': self.get_member_distribution(),
            'verification_distribution': self.get_verification_distribution(),
            'filters': self.filters.get_all_data(),
        }
