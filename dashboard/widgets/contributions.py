from .filters import DashboardFilters
from contributions.models import Contribution
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from registration.models import Profile


class BaseContributionCache:
    """Base class for caching query results using Redis."""
    
    def __init__(self, cache_timeout=300):
        self._cache_timeout = cache_timeout  # 5 minutes by default

    def _get_cache_key(self, method_name, filters):
        """Generate cache key based on filters and method name."""
        import hashlib
        filter_str = str(sorted(filters.items()))
        return f"contributions:{method_name}:{hashlib.md5(filter_str.encode()).hexdigest()}"

    def _get_cached_result(self, method_name, filters):
        """Get cached result from Redis."""
        cache_key = self._get_cache_key(method_name, filters)
        return cache.get(cache_key)

    def _set_cached_result(self, method_name, filters, result):
        """Cache result in Redis."""
        cache_key = self._get_cache_key(method_name, filters)
        cache.set(cache_key, result, self._cache_timeout)


class ContributionQuerySet:
    """Class for working with filtering and basic QuerySet operations."""
    
    def __init__(self, filters):
        self.filters = filters
    
    def get_filtered_queryset(self, model=None, queryset_type='contribution'):
        """Get filtered QuerySet."""
        if model is None:
            model = Contribution
        
        queryset = model.objects.all()
        return self.filters.apply_filters_to_queryset(queryset, queryset_type)
    
    def get_license_ids_from_queryset(self, queryset):
        """Get unique license IDs from QuerySet."""
        return queryset.values_list('license_id', flat=True).distinct()
    
    def get_primary_dates_for_licenses(self, license_ids):
        """Get dates of first broadcasts for a list of licenses."""
        from django.db.models import Min
        
        primary_dates = Contribution.objects.filter(
            license_id__in=license_ids
        ).values('license').annotate(
            min_date=Min('broadcast_date')
        )
        return {item['license']: item['min_date'] for item in primary_dates}
    
    def count_primary_contributions(self, queryset, license_primary_dates):
        """Count primary contributions (first broadcasts for each license)."""
        primary_count = 0
        for contribution in queryset.select_related('license'):
            if (contribution.license_id in license_primary_dates and 
                contribution.broadcast_date == license_primary_dates[contribution.license_id]):
                primary_count += 1
        return primary_count


class ContributionBasicStats:
    """Class for working with basic contribution statistics."""
    
    def __init__(self, cache_manager, queryset_manager):
        self.cache_manager = cache_manager
        self.queryset_manager = queryset_manager
    
    def get_basic_stats(self):
        """Get basic contribution statistics."""
        cached_result = self.cache_manager._get_cached_result('basic_stats', self.queryset_manager.filters.filters)
        if cached_result:
            return cached_result
        
        filtered_queryset = self.queryset_manager.get_filtered_queryset()
        filtered_queryset = filtered_queryset.select_related('license', 'license__profile')
        
        total_contributions = filtered_queryset.count()
        live_contributions = filtered_queryset.filter(live=True).count()
        recorded_contributions = filtered_queryset.filter(live=False).count()
        
        try:
            license_ids = self.queryset_manager.get_license_ids_from_queryset(filtered_queryset)
            license_primary_dates = self.queryset_manager.get_primary_dates_for_licenses(license_ids)
            primary_contributions = self.queryset_manager.count_primary_contributions(
                filtered_queryset, license_primary_dates
            )
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
        
        self.cache_manager._set_cached_result('basic_stats', self.queryset_manager.filters.filters, result)
        return result
    
    def get_live_vs_recorded(self):
        """Get statistics of live and recorded broadcasts."""
        filtered_queryset = self.queryset_manager.get_filtered_queryset()
        
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
    
    def get_primary_vs_repetitions(self):
        """Get statistics of primary and repeated contributions."""
        filtered_queryset = self.queryset_manager.get_filtered_queryset()
        total = filtered_queryset.count()
        
        license_ids = self.queryset_manager.get_license_ids_from_queryset(filtered_queryset)
        license_primary_dates = self.queryset_manager.get_primary_dates_for_licenses(license_ids)
        
        primary = self.queryset_manager.count_primary_contributions(
            filtered_queryset, license_primary_dates
        )
        
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


class ContributionMetrics:
    """Class for working with contribution metrics."""
    
    def __init__(self, cache_manager, queryset_manager):
        self.cache_manager = cache_manager
        self.queryset_manager = queryset_manager
    
    def get_unified_metrics(self):
        """Get unified metrics combining all contribution statistics."""
        cached_result = self.cache_manager._get_cached_result('unified_metrics', self.queryset_manager.filters.filters)
        if cached_result is not None:
            return cached_result
        
        try:
            from datetime import timedelta
            from django.db.models import Min
            from licenses.models import License
            
            filtered_contributions = self.queryset_manager.get_filtered_queryset()
            
            total_contributions = filtered_contributions.count()
            live_contributions = filtered_contributions.filter(live=True).count()
            recorded_contributions = filtered_contributions.filter(live=False).count()
            
            license_ids_in_period = self.queryset_manager.get_license_ids_from_queryset(filtered_contributions)
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
                self.cache_manager._set_cached_result('unified_metrics', self.queryset_manager.filters.filters, result)
                return result
            
            license_primary_dates = self.queryset_manager.get_primary_dates_for_licenses(license_ids_in_period)
            primary_contributions = self.queryset_manager.count_primary_contributions(
                filtered_contributions, license_primary_dates
            )
            
            archive_threshold = timezone.now() - timedelta(days=365)
            
            archive_contributions = 0
            active_contributions = 0
            recent_contributions = 0
            
            licenses_dict = {
                lic.id: lic for lic in License.objects.filter(
                    id__in=license_ids_in_period
                ).only('id', 'created_at')
            }
            
            for license_id in license_ids_in_period:
                first_broadcast = license_primary_dates.get(license_id)
                
                license_obj = licenses_dict.get(license_id)
                if not license_obj:
                    continue
                    
                reference_date = first_broadcast or license_obj.created_at
                
                if reference_date:
                    if reference_date.tzinfo is None:
                        reference_date = timezone.make_aware(reference_date)
                    elif archive_threshold.tzinfo is None:
                        archive_threshold = timezone.make_aware(archive_threshold)
                    
                    if reference_date < archive_threshold:
                        archive_contributions += 1
                    else:
                        active_contributions += 1
                else:
                    recent_contributions += 1
            
            repetitions = total_contributions - primary_contributions
            
            conversion_rate = round((primary_contributions / unique_licenses_count) * 100, 2) if unique_licenses_count > 0 else 0
            
            archive_rate = round((archive_contributions / total_contributions) * 100, 1) if total_contributions > 0 else 0
            
            result = {
                'total_contributions': total_contributions,
                'live_contributions': live_contributions,
                'recorded_contributions': recorded_contributions,
                'unique_licenses': unique_licenses_count,
                'primary_contributions': primary_contributions,
                'archive_licenses': archive_contributions,
                'active_licenses': active_contributions,
                'recent_licenses': recent_contributions,
                'repetitions': repetitions,
                'conversion_rate': conversion_rate,
                'archive_rate': archive_rate
            }
            
            self.cache_manager._set_cached_result('unified_metrics', self.queryset_manager.filters.filters, result)
            return result
            
        except Exception as e:
            import traceback
            print(f"Error in get_unified_metrics: {e}")
            print(f"Traceback: {traceback.format_exc()}")
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
    
    def get_conversion_metrics(self):
        """Get conversion metrics from license to contribution."""
        try:
            from licenses.models import License
            from django.db.models import Min
            
            license_filtered = self.queryset_manager.get_filtered_queryset(License, 'license')
            
            contribution_filtered = self.queryset_manager.get_filtered_queryset()
            
            total_licenses = license_filtered.count()

            licenses_with_contributions = contribution_filtered.filter(
                license__in=license_filtered
            ).values('license').distinct().count()

            conversion_rate = (licenses_with_contributions / total_licenses) * 100 if total_licenses > 0 else 0

            avg_time_to_first = None
            try:
                total_days = 0
                count = 0

                relevant_contributions = contribution_filtered.filter(
                    license__in=license_filtered
                ).select_related('license')

                license_ids = self.queryset_manager.get_license_ids_from_queryset(relevant_contributions)
                license_primary_dates = self.queryset_manager.get_primary_dates_for_licenses(license_ids)
                
                for contribution in relevant_contributions:
                    if (contribution.license_id in license_primary_dates and 
                        contribution.broadcast_date == license_primary_dates[contribution.license_id]):
                        if (hasattr(contribution, 'broadcast_date') and contribution.broadcast_date and
                            hasattr(contribution.license, 'created_at') and contribution.license.created_at):
                            days_diff = (contribution.broadcast_date.date() - contribution.license.created_at.date()).days
                            if days_diff >= 0:
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
        """Get archival metrics for licenses."""
        try:
            from datetime import datetime, timedelta
            from licenses.models import License
            
            archive_threshold = timedelta(days=365)
            current_date = datetime.now()

            contribution_filtered = self.queryset_manager.get_filtered_queryset()

            license_ids_in_period = self.queryset_manager.get_license_ids_from_queryset(contribution_filtered)
            total_licenses = license_ids_in_period.count()
            archive_contributions = 0
            active_contributions = 0
            recent_contributions = 0

            licenses_in_period = License.objects.filter(id__in=license_ids_in_period).prefetch_related(
                'contribution_set'
            ).select_related('profile')

            for license_obj in licenses_in_period.iterator(chunk_size=500):
                first_contribution = license_obj.contribution_set.order_by('broadcast_date').first()
                
                if first_contribution and first_contribution.broadcast_date:
                    broadcast_date = first_contribution.broadcast_date
                    if broadcast_date.tzinfo is None:
                        broadcast_date = broadcast_date.replace(tzinfo=None)
                    else:
                        broadcast_date = broadcast_date.replace(tzinfo=None)
                    
                    time_since_first = current_date - broadcast_date
                    
                    if time_since_first > archive_threshold:
                        archive_contributions += 1
                    else:
                        active_contributions += 1
                else:
                    if license_obj.created_at:
                        created_at = license_obj.created_at
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=None)
                        else:
                            created_at = created_at.replace(tzinfo=None)
                        
                        time_since_creation = current_date - created_at
                        
                        if time_since_creation > archive_threshold:
                            archive_contributions += 1
                        else:
                            recent_contributions += 1
                    else:
                        recent_contributions += 1
            
            total_unique_licenses = archive_contributions + active_contributions + recent_contributions
            if total_unique_licenses > 0:
                archive_percentage = round((archive_contributions / total_unique_licenses) * 100, 1)
                active_percentage = round((active_contributions / total_unique_licenses) * 100, 1)
                recent_percentage = round((recent_contributions / total_unique_licenses) * 100, 1)
            else:
                archive_percentage = 0
                active_percentage = 0
                recent_percentage = 0
            
            return {
                'total_licenses': total_licenses,
                'archive_licenses': archive_contributions,
                'active_licenses': active_contributions,
                'recent_licenses': recent_contributions,
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


class ContributionDataGrouping:
    """Class for working with contribution data grouping."""
    
    def __init__(self, cache_manager, queryset_manager):
        self.cache_manager = cache_manager
        self.queryset_manager = queryset_manager
    
    def get_contributions_by_authority(self):
        """Get number of contributions by media authority."""
        try:
            filtered_queryset = self.queryset_manager.get_filtered_queryset()
            filtered_queryset = filtered_queryset.select_related(
                'license__profile__media_authority'
            )
            
            return list(filtered_queryset.values('license__profile__media_authority__name').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            return []
    
    def get_contributions_by_category(self):
        """Get number of contributions by license category."""
        try:
            filtered_queryset = self.queryset_manager.get_filtered_queryset()
            filtered_queryset = filtered_queryset.select_related(
                'license__category'
            )
            
            return list(filtered_queryset.values('license__category__name').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            return []
    
    def get_contributions_by_gender(self):
        """Get number of contributions by gender."""
        try:
            filtered_queryset = self.queryset_manager.get_filtered_queryset()
            
            return list(filtered_queryset.values('license__profile__gender').annotate(
                count=Count('id')
            ).order_by('-count'))
        except Exception:
            return []
    
    def get_contributions_by_age(self):
        """Get number of contributions by age groups."""
        filtered_queryset = self.queryset_manager.get_filtered_queryset()
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
            for contribution in filtered_queryset.iterator(chunk_size=1000):
                if contribution.license.profile and contribution.license.profile.birthday:
                    age = relativedelta(self.queryset_manager.filters.date_range['end_date'], 
                                      contribution.license.profile.birthday).years
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
        """Get contribution trends over time."""
        try:
            start_date = self.queryset_manager.filters.date_range['start_date']
            end_date = self.queryset_manager.filters.date_range['end_date']
            contributions_trend = []

            days_diff = (end_date - start_date).days

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


class ContributionDetailedData:
    """Class for working with detailed contribution information."""
    
    def __init__(self, cache_manager, queryset_manager):
        self.cache_manager = cache_manager
        self.queryset_manager = queryset_manager
    
    def get_detailed_contributions(self, contribution_type=None, page=1, per_page=20):
        """Get detailed list of contributions based on filters with pagination."""
        queryset = Contribution.objects.select_related(
            'license__profile__okuser',
            'license__profile__media_authority',
            'license__category'
        ).all()
        
        filtered_queryset = self.queryset_manager.filters.apply_filters_to_queryset(queryset, 'contribution')

        if contribution_type == 'live':
            filtered_queryset = filtered_queryset.filter(live=True)
        elif contribution_type == 'recorded':
            filtered_queryset = filtered_queryset.filter(live=False)
        elif contribution_type == 'primary':
            from django.db.models import Min
            license_ids = self.queryset_manager.get_license_ids_from_queryset(filtered_queryset)
            primary_contributions = []
            
            for license_id in license_ids:
                first_broadcast = Contribution.objects.filter(
                    license_id=license_id
                ).aggregate(first_broadcast=Min('broadcast_date'))['first_broadcast']
                
                if first_broadcast:
                    primary_contribs = filtered_queryset.filter(
                        license_id=license_id,
                        broadcast_date=first_broadcast
                    )
                    contribs_list = list(primary_contribs)
                    primary_contributions.extend(contribs_list)

            filtered_queryset = Contribution.objects.filter(
                id__in=[c.id for c in primary_contributions]
            )
        elif contribution_type == 'repetition':
            from django.db.models import Min
            license_ids = self.queryset_manager.get_license_ids_from_queryset(filtered_queryset)
            repetition_contributions = []
            
            for license_id in license_ids:
                first_broadcast = Contribution.objects.filter(
                    license_id=license_id
                ).aggregate(first_broadcast=Min('broadcast_date'))['first_broadcast']
                
                if first_broadcast:
                    repetition_contribs = filtered_queryset.filter(
                        license_id=license_id
                    ).exclude(broadcast_date=first_broadcast)
                    repetition_contributions.extend(list(repetition_contribs))
            
            filtered_queryset = Contribution.objects.filter(
                id__in=[c.id for c in repetition_contributions]
            )
        elif contribution_type == 'archive':
            from datetime import timedelta
            from django.db.models import Min
            from django.utils import timezone
            from licenses.models import License
            
            archive_threshold = timezone.now() - timedelta(days=365)

            license_ids = self.queryset_manager.get_license_ids_from_queryset(filtered_queryset)
            archive_contributions = []
            
            for license_id in license_ids:
                first_broadcast = Contribution.objects.filter(
                    license_id=license_id
                ).aggregate(first_broadcast=Min('broadcast_date'))['first_broadcast']

                license_obj = License.objects.get(id=license_id)
                reference_date = first_broadcast or license_obj.created_at
                
                if reference_date:
                    if reference_date.tzinfo is None:
                        reference_date = timezone.make_aware(reference_date)
                    elif archive_threshold.tzinfo is None:
                        archive_threshold = timezone.make_aware(archive_threshold)
                    
                    if reference_date < archive_threshold:
                        first_contrib = filtered_queryset.filter(license_id=license_id).first()
                        if first_contrib:
                            archive_contributions.append(first_contrib)

            filtered_queryset = Contribution.objects.filter(
                id__in=[c.id for c in archive_contributions]
            )
        elif contribution_type == 'unique':
            license_ids = self.queryset_manager.get_license_ids_from_queryset(filtered_queryset)
            unique_contributions = []
            for license_id in license_ids:
                first_contrib = filtered_queryset.filter(license_id=license_id).first()
                if first_contrib:
                    unique_contributions.append(first_contrib)
            filtered_queryset = Contribution.objects.filter(
                id__in=[c.id for c in unique_contributions]
            )

        total_count = filtered_queryset.count()
        
        start = (page - 1) * per_page
        end = start + per_page
        total_pages = (total_count + per_page - 1) // per_page
        has_previous = page > 1
        has_next = page < total_pages

        paginated_queryset = filtered_queryset[start:end]

        contributions_data = []
        for contrib in paginated_queryset:
            contrib_data = {
                'id': contrib.id,
                'license_number': contrib.license.number if contrib.license and contrib.license.number else "",
                'license_title': contrib.license.title if contrib.license and contrib.license.title else "",
                'license_subtitle': contrib.license.subtitle if contrib.license and contrib.license.subtitle else "",
                'license_duration': str(contrib.license.duration) if contrib.license and contrib.license.duration else "",
                'license_created_at': contrib.license.created_at.strftime('%Y-%m-%d') if contrib.license and contrib.license.created_at else "",
                'license_confirmed': contrib.license.confirmed if contrib.license else False,
                'name': contrib.license.profile.__str__() if contrib.license and contrib.license.profile else "",
                'email': contrib.license.profile.okuser.email if contrib.license and contrib.license.profile and contrib.license.profile.okuser else "",
                'category': contrib.license.category.name if contrib.license and contrib.license.category else "",
                'broadcast_date': contrib.broadcast_date.strftime('%Y-%m-%d') if contrib.broadcast_date else "",
                'live': contrib.live,
                'duration_minutes': self.format_duration(contrib.license.duration) if contrib.license and contrib.license.duration else "00:00:00",
                'media_authority': contrib.license.profile.media_authority.name if contrib.license and contrib.license.profile and contrib.license.profile.media_authority else "",
                'city': contrib.license.profile.city if contrib.license and contrib.license.profile else "",
                'type': _("Live") if contrib.live else _("Recorded")
            }
            contributions_data.append(contrib_data)
        
        return {
            'contributions': contributions_data,
            'total_count': total_count,
            'displayed_count': len(contributions_data),
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
    
    def format_duration(self, duration):
        """Format duration in HH:MM:SS format."""
        if not duration:
            return "00:00:00"
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_broadcast_hours(self):
        """Get broadcast hours statistics."""
        try:
            filtered_queryset = self.queryset_manager.get_filtered_queryset()

            hours_data = {}
            for contribution in filtered_queryset.iterator():
                if contribution.broadcast_date:
                    hour = contribution.broadcast_date.hour
                    if hour not in hours_data:
                        hours_data[hour] = 0
                    hours_data[hour] += 1

            result = []
            for hour in range(24):
                count = hours_data.get(hour, 0)
                result.append({
                    'hour': hour,
                    'count': count,
                    'hour_label': f"{hour:02d}:00"
                })
            
            return result
        except Exception:
            return []
    
    def get_duration_stats(self):
        """Get duration statistics."""
        try:
            filtered_queryset = self.queryset_manager.get_filtered_queryset()
            filtered_queryset = filtered_queryset.select_related('license').only('license__duration')
            
            durations = []
            for contribution in filtered_queryset.iterator():
                if contribution.license and contribution.license.duration:
                    total_seconds = int(contribution.license.duration.total_seconds())
                    durations.append(total_seconds)
            
            if not durations:
                return {
                    'avg_duration': "00:00:00",
                    'min_duration': "00:00:00",
                    'max_duration': "00:00:00",
                    'total_duration': "00:00:00"
                }
            
            avg_seconds = sum(durations) // len(durations)
            min_seconds = min(durations)
            max_seconds = max(durations)
            total_seconds = sum(durations)
            
            return {
                'avg_duration': self._seconds_to_duration(avg_seconds),
                'min_duration': self._seconds_to_duration(min_seconds),
                'max_duration': self._seconds_to_duration(max_seconds),
                'total_duration': self._seconds_to_duration(total_seconds)
            }
        except Exception:
            return {
                'avg_duration': "00:00:00",
                'min_duration': "00:00:00",
                'max_duration': "00:00:00",
                'total_duration': "00:00:00"
            }
    
    def _seconds_to_duration(self, seconds):
        """Convert seconds to HH:MM:SS format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class ContributionsWidget:
    """Widget for contribution statistics."""

    def __init__(self, request):
        self.request = request
        self.filters = DashboardFilters(request)

        self.cache_manager = BaseContributionCache()
        self.queryset_manager = ContributionQuerySet(self.filters)
        self.basic_stats = ContributionBasicStats(self.cache_manager, self.queryset_manager)
        self.metrics = ContributionMetrics(self.cache_manager, self.queryset_manager)
        self.data_grouping = ContributionDataGrouping(self.cache_manager, self.queryset_manager)
        self.detailed_data = ContributionDetailedData(self.cache_manager, self.queryset_manager)

    def get_unified_metrics(self):
        """Get unified metrics combining all contribution statistics - optimized version."""
        return self.metrics.get_unified_metrics()

    def get_data(self):
        """Get all contribution data."""
        try:
            unified_metrics = self.get_unified_metrics()
        except Exception as e:
            unified_metrics = {
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

        return {
            'unified_metrics': unified_metrics,
            'basic_stats': self.basic_stats.get_basic_stats(),
            'contributions_by_authority': self.data_grouping.get_contributions_by_authority(),
            'contributions_by_gender': self.data_grouping.get_contributions_by_gender(),
            'contributions_by_age': self.data_grouping.get_contributions_by_age(),
            'contributions_trend': self.data_grouping.get_contributions_trend(),
            'live_vs_recorded': self.basic_stats.get_live_vs_recorded(),
            'primary_vs_repetitions': self.basic_stats.get_primary_vs_repetitions(),
            'conversion_metrics': self.metrics.get_conversion_metrics(),
            'archive_metrics': self.metrics.get_archive_metrics(),
        }

    def get_basic_stats(self):
        """Get basic contribution statistics."""
        return self.basic_stats.get_basic_stats()

    def get_contributions_by_authority(self):
        """Get number of contributions by media authority."""
        return self.data_grouping.get_contributions_by_authority()

    def get_contributions_by_category(self):
        """Get number of contributions by license category."""
        return self.data_grouping.get_contributions_by_category()

    def get_contributions_by_gender(self):
        """Get number of contributions by gender."""
        return self.data_grouping.get_contributions_by_gender()

    def get_contributions_by_age(self):
        """Get number of contributions by age groups."""
        return self.data_grouping.get_contributions_by_age()

    def get_contributions_trend(self):
        """Get contribution trends over time."""
        return self.data_grouping.get_contributions_trend()

    def get_live_vs_recorded(self):
        """Get statistics of live and recorded broadcasts."""
        return self.basic_stats.get_live_vs_recorded()

    def get_primary_vs_repetitions(self):
        """Get statistics of primary and repeated contributions."""
        return self.basic_stats.get_primary_vs_repetitions()

    def get_conversion_metrics(self):
        """Get conversion metrics from license to contribution."""
        return self.metrics.get_conversion_metrics()

    def get_archive_metrics(self):
        """Get archival metrics for licenses."""
        return self.metrics.get_archive_metrics()

    def get_detailed_contributions(self, contribution_type=None, page=1, per_page=20):
        """Get detailed list of contributions based on filters with pagination."""
        return self.detailed_data.get_detailed_contributions(contribution_type, page, per_page)

    def format_duration(self, duration):
        """Format duration in HH:MM:SS format."""
        return self.detailed_data.format_duration(duration)

    def get_detailed_data(self):
        """Получение детальных данных для виджета вкладов."""
        return {
            'contributions': self.get_detailed_contributions('total', 1, 20),
            'basic_stats': self.get_basic_stats(),
            'contributions_by_category': self.get_contributions_by_category(),
            'contributions_by_authority': self.get_contributions_by_authority(),
            'contributions_by_gender': self.get_contributions_by_gender(),
            'contributions_by_age': self.get_contributions_by_age(),
            'contributions_trend': self.get_contributions_trend(),
            'live_vs_recorded': self.get_live_vs_recorded(),
            'broadcast_hours': self.get_broadcast_hours(),
            'duration_stats': self.get_duration_stats(),
            'archive_metrics': self.get_archive_metrics(),
        }
    
    def get_broadcast_hours(self):
        """Get broadcast hours statistics."""
        return self.detailed_data.get_broadcast_hours()
    
    def get_duration_stats(self):
        """Get duration statistics."""
        return self.detailed_data.get_duration_stats()
