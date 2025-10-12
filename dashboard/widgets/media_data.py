"""
Media Data Widget for dashboard.
Provides statistics about licenses and contributions.
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Q, F, Sum, Count, Case, When, IntegerField, FloatField, ExpressionWrapper, DurationField
from django.db.models.functions import ExtractYear
from django.utils.translation import gettext_lazy as _
from licenses.models import License, Category
from contributions.models import Contribution
from registration.models import Profile
from .filters import DashboardFilters


class MediaDataWidget:
    """Widget for media data statistics."""

    def __init__(self, request):
        self.filters = DashboardFilters(request)
        self.now = datetime.now().date()

    def get_age_group(self, birthday):
        """Calculate age group from birthday."""
        if not birthday or birthday.year == 1800:
            return 'unknown'
        
        age = relativedelta(self.now, birthday).years
        
        if age <= 34:
            return 'up_to_34'
        elif age <= 50:
            return '35_50'
        elif age <= 65:
            return '51_65'
        else:
            return 'over_65'
    
    def _get_age_group_annotation(self):
        """Create Django ORM annotation for age groups."""
        return Case(
            # Unknown age
            When(
                Q(profile__birthday__isnull=True) | Q(profile__birthday__year=1800),
                then='unknown'
            ),
            # Up to 34
            When(
                profile__birthday__gte=self.now.replace(year=self.now.year - 34),
                then='up_to_34'
            ),
            # 35-50
            When(
                profile__birthday__gte=self.now.replace(year=self.now.year - 50),
                profile__birthday__lt=self.now.replace(year=self.now.year - 34),
                then='35_50'
            ),
            # 51-65
            When(
                profile__birthday__gte=self.now.replace(year=self.now.year - 65),
                profile__birthday__lt=self.now.replace(year=self.now.year - 50),
                then='51_65'
            ),
            # Over 65
            When(
                profile__birthday__lt=self.now.replace(year=self.now.year - 65),
                then='over_65'
            ),
            default='unknown',
            output_field=IntegerField()
        )

    def _apply_filters(self, queryset):
        """Apply filters to queryset."""
        filters = self.filters.filters
        date_range = self.filters.date_range

        # Date range filter
        if date_range['start_date'] and date_range['end_date']:
            queryset = queryset.filter(
                created_at__date__gte=date_range['start_date'],
                created_at__date__lte=date_range['end_date']
            )

        # Media authority filter
        if filters['media_authority']:
            queryset = queryset.filter(profile__media_authority__name=filters['media_authority'])

        # Gender filter
        if filters['gender']:
            queryset = queryset.filter(profile__gender=filters['gender'])

        # Age group filter
        if filters['age_group']:
            if filters['age_group'] == 'up_to_34':
                queryset = queryset.filter(
                    profile__birthday__isnull=False
                ).exclude(profile__birthday__year=1800).filter(
                    profile__birthday__gte=datetime.now().date().replace(
                        year=datetime.now().year - 34
                    )
                )
            elif filters['age_group'] == '35_50':
                queryset = queryset.filter(
                    profile__birthday__isnull=False
                ).exclude(profile__birthday__year=1800).filter(
                    profile__birthday__lt=datetime.now().date().replace(
                        year=datetime.now().year - 34
                    ),
                    profile__birthday__gte=datetime.now().date().replace(
                        year=datetime.now().year - 50
                    )
                )
            elif filters['age_group'] == '51_65':
                queryset = queryset.filter(
                    profile__birthday__isnull=False
                ).exclude(profile__birthday__year=1800).filter(
                    profile__birthday__lt=datetime.now().date().replace(
                        year=datetime.now().year - 50
                    ),
                    profile__birthday__gte=datetime.now().date().replace(
                        year=datetime.now().year - 65
                    )
                )
            elif filters['age_group'] == 'over_65':
                queryset = queryset.filter(
                    profile__birthday__isnull=False
                ).exclude(profile__birthday__year=1800).filter(
                    profile__birthday__lt=datetime.now().date().replace(
                        year=datetime.now().year - 65
                    )
                )
            elif filters['age_group'] == 'unknown':
                queryset = queryset.filter(
                    Q(profile__birthday__isnull=True) | Q(profile__birthday__year=1800)
                )

        # Member status filter
        if filters['member']:
            if filters['member'] == 'true':
                queryset = queryset.filter(profile__member=True)
            elif filters['member'] == 'false':
                queryset = queryset.filter(profile__member=False)

        # Verification filter
        if filters['verified']:
            if filters['verified'] == 'true':
                queryset = queryset.filter(profile__verified=True)
            elif filters['verified'] == 'false':
                queryset = queryset.filter(profile__verified=False)

        # Category filter
        if filters['category']:
            queryset = queryset.filter(category__id=filters['category'])

        return queryset

    def get_users_with_licenses_and_broadcasts(self):
        """Get age distribution of users who created licenses and have primary contributions."""
        from django.db.models import Min
        
        # Получаем primary contributions в заданном периоде
        primary_dates = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date']
        ).values('license').annotate(
            min_date=Min('broadcast_date')
        )
        
        # Словарь license_id -> min_date
        license_primary_dates = {item['license']: item['min_date'] for item in primary_dates}
        
        # Получаем contributions которые являются primary (первые по дате)
        contributions = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date']
        ).select_related('license__profile', 'license__profile__media_authority', 'license__category')
        
        # Применяем фильтры через license
        filters = self.filters.filters
        if filters['media_authority']:
            contributions = contributions.filter(license__profile__media_authority__name=filters['media_authority'])
        if filters['gender']:
            contributions = contributions.filter(license__profile__gender=filters['gender'])
        if filters['member']:
            contributions = contributions.filter(license__profile__member=(filters['member'] == 'true'))
        if filters['verified']:
            contributions = contributions.filter(license__profile__verified=(filters['verified'] == 'true'))
        if filters['category']:
            contributions = contributions.filter(license__category__id=filters['category'])
        
        # Подсчитываем уникальных пользователей с primary contributions
        age_groups = {
            'up_to_34': 0,
            '35_50': 0,
            '51_65': 0,
            'over_65': 0,
            'unknown': 0
        }
        
        seen_profiles = set()
        for contribution in contributions:
            # Проверяем что это primary contribution
            if contribution.license_id in license_primary_dates and contribution.broadcast_date == license_primary_dates[contribution.license_id]:
                profile_id = contribution.license.profile.id
                if profile_id not in seen_profiles:
                    seen_profiles.add(profile_id)
                    age_group = self.get_age_group(contribution.license.profile.birthday)
                    age_groups[age_group] += 1
        
        return age_groups

    def get_new_broadcasts_by_age(self):
        """Get number of primary broadcasts by age group."""
        from django.db.models import Min
        
        # Получаем минимальную дату для каждой лицензии (это будут primary contributions)
        primary_dates = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date']
        ).values('license').annotate(
            min_date=Min('broadcast_date')
        )
        
        # Создаём словарь license_id -> min_date для быстрого поиска
        license_primary_dates = {item['license']: item['min_date'] for item in primary_dates}
        
        # Базовый queryset с фильтрами
        contributions = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date']
        ).select_related('license__profile', 'license__profile__media_authority', 'license__category')
        
        # Применяем фильтры через license
        filters = self.filters.filters
        if filters['media_authority']:
            contributions = contributions.filter(license__profile__media_authority__name=filters['media_authority'])
        if filters['gender']:
            contributions = contributions.filter(license__profile__gender=filters['gender'])
        if filters['member']:
            contributions = contributions.filter(license__profile__member=(filters['member'] == 'true'))
        if filters['verified']:
            contributions = contributions.filter(license__profile__verified=(filters['verified'] == 'true'))
        if filters['category']:
            contributions = contributions.filter(license__category__id=filters['category'])
        
        # Фильтруем только primary contributions и группируем
        age_groups = {
            'up_to_34': 0,
            '35_50': 0,
            '51_65': 0,
            'over_65': 0,
            'unknown': 0
        }
        
        for contribution in contributions:
            # Проверяем что это primary contribution (первая по дате для лицензии)
            if contribution.license_id in license_primary_dates and contribution.broadcast_date == license_primary_dates[contribution.license_id]:
                age_group = self.get_age_group(contribution.license.profile.birthday)
                age_groups[age_group] += 1
        
        return age_groups

    def get_duration_by_age(self):
        """Get total duration by age group in minutes."""
        from django.db.models import Min
        
        # Получаем минимальную дату для каждой лицензии (это будут primary contributions)
        primary_dates = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date']
        ).values('license').annotate(
            min_date=Min('broadcast_date')
        )
        
        # Создаём словарь license_id -> min_date для быстрого поиска
        license_primary_dates = {item['license']: item['min_date'] for item in primary_dates}
        
        # Базовый queryset с фильтрами
        contributions = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date'],
            license__duration__isnull=False
        ).select_related('license__profile', 'license__profile__media_authority', 'license__category')
        
        # Применяем фильтры через license
        filters = self.filters.filters
        if filters['media_authority']:
            contributions = contributions.filter(license__profile__media_authority__name=filters['media_authority'])
        if filters['gender']:
            contributions = contributions.filter(license__profile__gender=filters['gender'])
        if filters['member']:
            contributions = contributions.filter(license__profile__member=(filters['member'] == 'true'))
        if filters['verified']:
            contributions = contributions.filter(license__profile__verified=(filters['verified'] == 'true'))
        if filters['category']:
            contributions = contributions.filter(license__category__id=filters['category'])
        
        # Группируем по возрасту и суммируем длительность
        age_groups = {
            'up_to_34': 0,
            '35_50': 0,
            '51_65': 0,
            'over_65': 0,
            'unknown': 0
        }
        
        for contribution in contributions:
            # Проверяем что это primary contribution (первая по дате для лицензии)
            if contribution.license_id in license_primary_dates and contribution.broadcast_date == license_primary_dates[contribution.license_id]:
                age_group = self.get_age_group(contribution.license.profile.birthday)
                duration_minutes = contribution.license.duration.total_seconds() / 60
                age_groups[age_group] += duration_minutes
        
        return age_groups

    def get_duration_by_category(self):
        """Get total duration by category in minutes."""
        from django.db.models import Min
        
        # Получаем минимальную дату для каждой лицензии (это будут primary contributions)
        primary_dates = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date']
        ).values('license').annotate(
            min_date=Min('broadcast_date')
        )
        
        # Создаём словарь license_id -> min_date для быстрого поиска
        license_primary_dates = {item['license']: item['min_date'] for item in primary_dates}
        
        # Базовый queryset с фильтрами
        contributions = Contribution.objects.filter(
            broadcast_date__date__gte=self.filters.date_range['start_date'],
            broadcast_date__date__lte=self.filters.date_range['end_date'],
            license__duration__isnull=False,
            license__category__isnull=False
        ).select_related('license__profile', 'license__profile__media_authority', 'license__category')
        
        # Применяем фильтры через license
        filters = self.filters.filters
        if filters['media_authority']:
            contributions = contributions.filter(license__profile__media_authority__name=filters['media_authority'])
        if filters['gender']:
            contributions = contributions.filter(license__profile__gender=filters['gender'])
        if filters['member']:
            contributions = contributions.filter(license__profile__member=(filters['member'] == 'true'))
        if filters['verified']:
            contributions = contributions.filter(license__profile__verified=(filters['verified'] == 'true'))
        if filters['category']:
            contributions = contributions.filter(license__category__id=filters['category'])
        
        # Группируем по категориям и суммируем длительность
        category_durations = {}
        for contribution in contributions:
            # Проверяем что это primary contribution (первая по дате для лицензии)
            if contribution.license_id in license_primary_dates and contribution.broadcast_date == license_primary_dates[contribution.license_id]:
                category_name = contribution.license.category.name
                duration_minutes = contribution.license.duration.total_seconds() / 60
                
                if category_name in category_durations:
                    category_durations[category_name] += duration_minutes
                else:
                    category_durations[category_name] = duration_minutes
        
        return category_durations

    def _matches_license_filters(self, license):
        """Check if license matches current filters."""
        filters = self.filters.filters

        # Media authority filter
        if filters['media_authority'] and license.profile.media_authority.name != filters['media_authority']:
            return False

        # Gender filter
        if filters['gender'] and license.profile.gender != filters['gender']:
            return False

        # Age group filter
        if filters['age_group']:
            age_group = self.get_age_group(license.profile.birthday)
            if age_group != filters['age_group']:
                return False

        # Member status filter
        if filters['member']:
            if filters['member'] == 'true' and not license.profile.member:
                return False
            elif filters['member'] == 'false' and license.profile.member:
                return False

        # Verification filter
        if filters['verified']:
            if filters['verified'] == 'true' and not license.profile.verified:
                return False
            elif filters['verified'] == 'false' and license.profile.verified:
                return False

        # Category filter
        if filters['category'] and str(license.category.id) != filters['category']:
            return False

        return True

    def get_all_data(self):
        """Get all widget data."""
        return {
            'users_with_licenses_and_broadcasts': self.get_users_with_licenses_and_broadcasts(),
            'new_broadcasts_by_age': self.get_new_broadcasts_by_age(),
            'duration_by_age': self.get_duration_by_age(),
            'duration_by_category': self.get_duration_by_category(),
            'filters': {
                'filters': self.filters.filters,
                'date_range': self.filters.date_range,
                'context': {
                    'media_authorities': list(self.filters.context['media_authorities'].values('name')),
                    'gender_choices': self.filters.context['gender_choices'],
                    'age_groups': self.filters.context['age_groups'],
                    'member_choices': self.filters.context['member_choices'],
                    'verified_choices': self.filters.context['verified_choices'],
                    'date_range_options': self.filters.context['date_range_options']
                }
            }
        }
