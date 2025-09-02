from django.db.models import Count, Q
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import timedelta

from contributions.models import Contribution
from registration.models import Profile
from .filters import DashboardFilters


class ContributionsWidget:
    """Widget for contributions statistics."""
    
    def __init__(self, request):
        self.request = request
        self.filters = DashboardFilters(request)
        self._cache = {}
        self._cache_timeout = 300  # 5 minutes
    
    def _get_cache_key(self, method_name):
        """Generate cache key based on filters and method name."""
        import hashlib
        filter_str = str(sorted(self.filters.filters.items()))
        return hashlib.md5(f"{method_name}:{filter_str}".encode()).hexdigest()
    
    def _get_cached_result(self, method_name):
        """Get cached result if available and not expired."""
        import time
        cache_key = self._get_cache_key(method_name)
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_timeout:
                return result
        return None
    
    def _set_cached_result(self, method_name, result):
        """Cache result with timestamp."""
        import time
        cache_key = self._get_cache_key(method_name)
        self._cache[cache_key] = (result, time.time())
    
    def get_unified_metrics(self):
        """Get unified metrics combining all contribution statistics - optimized version."""
        # Check cache first
        cached_result = self._get_cached_result('unified_metrics')
        if cached_result is not None:
            return cached_result
        
        try:
            from licenses.models import License
            from datetime import datetime, timedelta
            from django.db.models import Min, Case, When, IntegerField
            
            # Get all contributions in the period
            contribution_queryset = Contribution.objects.all()
            filtered_contributions = self.filters.apply_filters_to_queryset(contribution_queryset, 'contribution')
            
            # Basic contribution stats
            total_contributions = filtered_contributions.count()
            live_contributions = filtered_contributions.filter(live=True).count()
            recorded_contributions = filtered_contributions.filter(live=False).count()
            
            # Get unique licenses that were shown in the period
            license_ids_in_period = filtered_contributions.values_list('license_id', flat=True).distinct()
            unique_licenses_count = license_ids_in_period.count()
            
            if unique_licenses_count == 0:
                result = {
                    'total_contributions': 0,
                    'live_contributions': 0,
                    'recorded_contributions': 0,
                    'unique_licenses': 0,
                    'primary_contributions': 0,
                    'repetitions': 0,
                    'conversion_rate': 0,
                    'archive_licenses': 0,
                    'active_licenses': 0,
                    'recent_licenses': 0,
                    'archive_rate': 0
                }
                self._set_cached_result('unified_metrics', result)
                return result
            
            # Count primary contributions using SQL
            # A contribution is primary if it's the first broadcast for its license
            primary_contributions = 0
            for license_id in license_ids_in_period:
                # Get the first broadcast date for this license
                first_broadcast = Contribution.objects.filter(
                    license_id=license_id
                ).aggregate(first_broadcast=Min('broadcast_date'))['first_broadcast']
                
                if first_broadcast:
                    # Count contributions in the period that match the first broadcast date
                    primary_count = filtered_contributions.filter(
                        license_id=license_id,
                        broadcast_date=first_broadcast
                    ).count()
                    primary_contributions += primary_count
            
            # Get archive statistics using SQL
            archive_threshold = datetime.now() - timedelta(days=365)
            
            # Get licenses with their first broadcast dates
            licenses_with_first_broadcast = License.objects.filter(
                id__in=license_ids_in_period
            ).annotate(
                first_broadcast=Min('contribution__broadcast_date')
            ).values('id', 'first_broadcast', 'created_at')
            
            archive_licenses = 0
            active_licenses = 0
            recent_licenses = 0
            
            for license_data in licenses_with_first_broadcast:
                first_broadcast = license_data['first_broadcast']
                created_at = license_data['created_at']
                
                # Use first broadcast date if available, otherwise use creation date
                reference_date = first_broadcast or created_at
                
                if reference_date:
                    # Handle timezone
                    if reference_date.tzinfo is not None:
                        reference_date = reference_date.replace(tzinfo=None)
                    
                    if reference_date < archive_threshold:
                        archive_licenses += 1
                    else:
                        active_licenses += 1
                else:
                    # No dates available, count as recent
                    recent_licenses += 1
            
            # Calculate repetitions (total contributions minus primary contributions)
            repetitions = total_contributions - primary_contributions
            
            # Calculate conversion rate
            conversion_rate = round((primary_contributions / unique_licenses_count) * 100, 2) if unique_licenses_count > 0 else 0
            
            # Calculate archive rate
            archive_rate = round((archive_licenses / unique_licenses_count) * 100, 1) if unique_licenses_count > 0 else 0
            
            result = {
                'total_contributions': total_contributions,
                'live_contributions': live_contributions,
                'recorded_contributions': recorded_contributions,
                'unique_licenses': unique_licenses_count,
                'primary_contributions': primary_contributions,
                'archive_licenses': archive_licenses,
                'active_licenses': active_licenses,
                'recent_licenses': recent_licenses,
                'repetitions': repetitions,
                'conversion_rate': conversion_rate,
                'archive_rate': archive_rate
            }
            
            # Cache the result
            self._set_cached_result('unified_metrics', result)
            return result
            
        except Exception as e:
            print(f"Error in get_unified_metrics: {e}")
            return {
                'total_contributions': 0,
                'live_contributions': 0,
                'recorded_contributions': 0,
                'unique_licenses': 0,
                'primary_contributions': 0,
                'archive_licenses': 0,
                'active_licenses': 0,
                'recent_licenses': 0,
                'repetitions': 0,
                'conversion_rate': 0,
                'archive_rate': 0
            }

    def get_data(self):
        """Get all contributions data."""

        try:
            unified_metrics = self.get_unified_metrics()

        except Exception as e:

            unified_metrics = {
                'total_contributions': 0,
                'live_contributions': 0,
                'recorded_contributions': 0,
                'unique_licenses': 0,
                'primary_licenses': 0,
                'archive_licenses': 0,
                'active_licenses': 0,
                'recent_licenses': 0,
                'repetitions': 0,
                'conversion_rate': 0,
                'archive_rate': 0
            }
        
        return {
            'unified_metrics': unified_metrics,
            'basic_stats': self.get_basic_stats(),
            'contributions_by_authority': self.get_contributions_by_authority(),
            'contributions_by_gender': self.get_contributions_by_gender(),
            'contributions_by_age': self.get_contributions_by_age(),
            'contributions_trend': self.get_contributions_trend(),
            'live_vs_recorded': self.get_live_vs_recorded(),
            'primary_vs_repetitions': self.get_primary_vs_repetitions(),
            'conversion_metrics': self.get_conversion_metrics(),
            'archive_metrics': self.get_archive_metrics(),
        }
    
    def get_basic_stats(self):
        """Get basic contribution statistics."""
        # Check cache first
        cached_result = self._get_cached_result('basic_stats')
        if cached_result:
            return cached_result
        
        queryset = Contribution.objects.all()
        filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'contribution')
        
        # Optimize with select_related and prefetch_related
        filtered_queryset = filtered_queryset.select_related('license', 'license__profile')
        
        total_contributions = filtered_queryset.count()
        live_contributions = filtered_queryset.filter(live=True).count()
        recorded_contributions = filtered_queryset.filter(live=False).count()
        
        # Optimize primary contributions calculation using SQL
        try:
            from django.db.models import Min
            
            # Get unique license IDs in the filtered set
            license_ids = filtered_queryset.values_list('license_id', flat=True).distinct()
            
            primary_contributions = 0
            for license_id in license_ids:
                # Get the first broadcast date for this license
                first_broadcast = Contribution.objects.filter(
                    license_id=license_id
                ).aggregate(first_broadcast=Min('broadcast_date'))['first_broadcast']
                
                if first_broadcast:
                    # Count contributions in the filtered set that match the first broadcast date
                    primary_count = filtered_queryset.filter(
                        license_id=license_id,
                        broadcast_date=first_broadcast
                    ).count()
                    primary_contributions += primary_count
        except Exception:
            primary_contributions = 0
        
        repetition_contributions = total_contributions - primary_contributions
        

        
        result = {
            'total_contributions': total_contributions,
            'live_contributions': live_contributions,
            'recorded_contributions': recorded_contributions,
            'primary_contributions': primary_contributions,
            'repetition_contributions': repetition_contributions,
        }
        
        # Cache the result
        self._set_cached_result('basic_stats', result)
        return result
    
    def get_contributions_by_authority(self):
        """Get contribution count by media authority."""
        try:
            queryset = Contribution.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'contribution')
            
            # Optimize with select_related
            filtered_queryset = filtered_queryset.select_related(
                'license__profile__media_authority'
            )
            
            return list(filtered_queryset.values('license__profile__media_authority__name').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            return []
    
    def get_contributions_by_gender(self):
        """Get contribution count by gender."""
        try:
            queryset = Contribution.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'contribution')
            
            return list(filtered_queryset.values('license__profile__gender').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            return []
    
    def get_contributions_by_age(self):
        """Get contribution count by age group."""
        queryset = Contribution.objects.all()
        filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'contribution')
        
        # Optimize with select_related and only
        filtered_queryset = filtered_queryset.select_related(
            'license__profile'
        ).only(
            'license__profile__birthday'
        )
        
        age_groups = {
            'under_18': 0,
            '18_25': 0,
            '26_35': 0,
            '36_50': 0,
            'over_50': 0
        }
        
        try:
            # Use iterator for better memory usage
            for contribution in filtered_queryset.iterator(chunk_size=1000):
                if contribution.license.profile and contribution.license.profile.birthday:
                    age = relativedelta(self.filters.date_range['end_date'], contribution.license.profile.birthday).years
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
            pass
        
        return age_groups
    
    def get_contributions_trend(self):
        """Get contributions trend over time."""
        try:
            start_date = self.filters.date_range['start_date']
            end_date = self.filters.date_range['end_date']
            contributions_trend = []
            
            # Calculate number of days in the period
            days_diff = (end_date - start_date).days
            
            # For periods longer than 30 days, group by weeks
            if days_diff > 30:
                current_date = start_date
                while current_date <= end_date:
                    week_end = min(current_date + timedelta(days=6), end_date)
                    try:
                        count = Contribution.objects.filter(
                            broadcast_date__date__gte=current_date,
                            broadcast_date__date__lte=week_end
                        ).count()
                    except Exception:
                        count = 0
                    
                    contributions_trend.append({
                        'date': f"{current_date.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}",
                        'count': count
                    })
                    
                    current_date = week_end + timedelta(days=1)
            else:
                # For shorter periods, show daily data
                current_date = start_date
                while current_date <= end_date:
                    try:
                        count = Contribution.objects.filter(
                            broadcast_date__date=current_date
                        ).count()
                    except Exception:
                        count = 0
                    
                    contributions_trend.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'count': count
                    })
                    
                    current_date += timedelta(days=1)
                    
        except Exception:
            contributions_trend = []
        
        return contributions_trend
    
    def get_live_vs_recorded(self):
        """Get live vs recorded statistics."""
        try:
            queryset = Contribution.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'contribution')
            
            total = filtered_queryset.count()
            live = filtered_queryset.filter(live=True).count()
            recorded = filtered_queryset.filter(live=False).count()
            
            if total > 0:
                live_percentage = (live / total) * 100
                recorded_percentage = (recorded / total) * 100
            else:
                live_percentage = 0
                recorded_percentage = 0
            
            return {
                'total': total,
                'live': live,
                'recorded': recorded,
                'live_percentage': round(live_percentage, 2),
                'recorded_percentage': round(recorded_percentage, 2)
            }
        except Exception:
            return {
                'total': 0,
                'live': 0,
                'recorded': 0,
                'live_percentage': 0,
                'recorded_percentage': 0
            }
    
    def get_primary_vs_repetitions(self):
        """Get primary vs repetition statistics."""
        try:
            queryset = Contribution.objects.all()
            filtered_queryset = self.filters.apply_filters_to_queryset(queryset, 'contribution')
            
            total = filtered_queryset.count()
            primary = 0
            
            for contribution in filtered_queryset:
                if contribution.is_primary():
                    primary += 1
            
            repetition = total - primary
            
            if total > 0:
                primary_percentage = (primary / total) * 100
                repetition_percentage = (repetition / total) * 100
            else:
                primary_percentage = 0
                repetition_percentage = 0
            
            return {
                'total': total,
                'primary': primary,
                'repetition': repetition,
                'primary_percentage': round(primary_percentage, 2),
                'repetition_percentage': round(repetition_percentage, 2)
            }
        except Exception:
            return {
                'total': 0,
                'primary': 0,
                'repetition': 0,
                'primary_percentage': 0,
                'repetition_percentage': 0
            }
    
    def get_conversion_metrics(self):
        """Get conversion metrics from license to contribution."""
        try:
            from licenses.models import License
            
            # Get licenses in the period
            license_queryset = License.objects.all()
            license_filtered = self.filters.apply_filters_to_queryset(license_queryset, 'license')
            
            # Get contributions in the period
            contribution_queryset = Contribution.objects.all()
            contribution_filtered = self.filters.apply_filters_to_queryset(contribution_queryset, 'contribution')
            
            total_licenses = license_filtered.count()
            
            # Get unique licenses that have contributions IN THE SAME PERIOD
            # Only count licenses that exist in the filtered license set
            licenses_with_contributions = contribution_filtered.filter(
                license__in=license_filtered
            ).values('license').distinct().count()
            
            # Calculate conversion rate
            if total_licenses > 0:
                conversion_rate = (licenses_with_contributions / total_licenses) * 100
            else:
                conversion_rate = 0
            

            
            # Calculate average time from license to first contribution
            avg_time_to_first = None
            try:
                total_days = 0
                count = 0
                
                # Only consider contributions from licenses in the filtered period
                relevant_contributions = contribution_filtered.filter(
                    license__in=license_filtered
                ).select_related('license')
                
                for contribution in relevant_contributions:
                    if hasattr(contribution, 'is_primary') and contribution.is_primary():
                        if (hasattr(contribution, 'broadcast_date') and contribution.broadcast_date and 
                            hasattr(contribution.license, 'created_at') and contribution.license.created_at):
                            days_diff = (contribution.broadcast_date.date() - contribution.license.created_at.date()).days
                            if days_diff >= 0:  # Only count if broadcast is after license creation
                                total_days += days_diff
                                count += 1
                
                if count > 0:
                    avg_time_to_first = round(total_days / count, 1)
                

            except Exception as e:
                print(f"Error calculating avg time to first contribution: {e}")
                pass
            
            return {
                'total_licenses': total_licenses,
                'licenses_with_contributions': licenses_with_contributions,
                'conversion_rate': round(conversion_rate, 2),
                'avg_time_to_first_contribution': avg_time_to_first
            }
        except Exception:
            return {
                'total_licenses': 0,
                'licenses_with_contributions': 0,
                'conversion_rate': 0,
                'avg_time_to_first_contribution': None
            }
    
    def get_archive_metrics(self):
        """Get archive metrics for licenses."""
        try:
            from licenses.models import License
            from datetime import datetime, timedelta
            
            # Define archive threshold (1 year - same as in the analysis script)
            archive_threshold = timedelta(days=365)
            current_date = datetime.now()
            
            # Get all licenses (for archive stats, ignore date filter)
            license_queryset = License.objects.all()
            
            # Get all contributions
            contribution_queryset = Contribution.objects.all()
            contribution_filtered = self.filters.apply_filters_to_queryset(contribution_queryset, 'contribution')
            
            # For archive stats, we want to show licenses that were BROADCAST in the selected period
            # Get unique license IDs from contributions that were shown in the period
            license_ids_in_period = contribution_filtered.values_list('license_id', flat=True).distinct()
            total_licenses = license_ids_in_period.count()
            archive_licenses = 0
            active_licenses = 0
            recent_licenses = 0
            
            # Get licenses that were shown in the period
            licenses_in_period = License.objects.filter(id__in=license_ids_in_period).prefetch_related(
                'contribution_set'
            ).select_related('profile')
            
            # Analyze each license (only licenses that were shown in the period)
            for license_obj in licenses_in_period.iterator(chunk_size=500):
                # Get the first contribution for this license (ALL contributions, not just filtered ones)
                first_contribution = license_obj.contribution_set.order_by('broadcast_date').first()
                
                if first_contribution and first_contribution.broadcast_date:
                    # Calculate time since first broadcast
                    # Handle timezone-aware datetime
                    broadcast_date = first_contribution.broadcast_date
                    if broadcast_date.tzinfo is None:
                        broadcast_date = broadcast_date.replace(tzinfo=None)
                    else:
                        broadcast_date = broadcast_date.replace(tzinfo=None)
                    
                    time_since_first = current_date - broadcast_date
                    
                    if time_since_first > archive_threshold:
                        archive_licenses += 1

                    else:
                        active_licenses += 1

                else:
                    # License has no contributions or no broadcast date
                    if license_obj.created_at:
                        created_at = license_obj.created_at
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=None)
                        else:
                            created_at = created_at.replace(tzinfo=None)
                        
                        time_since_creation = current_date - created_at
                        
                        if time_since_creation > archive_threshold:
                            archive_licenses += 1

                        else:
                            recent_licenses += 1

                    else:
                        # No creation date, count as recent
                        recent_licenses += 1

            
            # Calculate percentages
            if total_licenses > 0:
                archive_percentage = round((archive_licenses / total_licenses) * 100, 1)
                active_percentage = round((active_licenses / total_licenses) * 100, 1)
                recent_percentage = round((recent_licenses / total_licenses) * 100, 1)
            else:
                archive_percentage = 0
                active_percentage = 0
                recent_percentage = 0
            

            
            return {
                'total_licenses': total_licenses,
                'archive_licenses': archive_licenses,
                'active_licenses': active_licenses,
                'recent_licenses': recent_licenses,
                'archive_percentage': archive_percentage,
                'active_percentage': active_percentage,
                'recent_percentage': recent_percentage,
                'archive_threshold_days': 365
            }
            
        except Exception as e:
            print(f"Error in get_archive_metrics: {e}")
            return {
                'total_licenses': 0,
                'archive_licenses': 0,
                'active_licenses': 0,
                'recent_licenses': 0,
                'archive_percentage': 0,
                'active_percentage': 0,
                'recent_percentage': 0,
                'archive_threshold_days': 365
            }
