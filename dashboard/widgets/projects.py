from datetime import datetime, timedelta
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from projects.models import Project, ProjectCategory, TargetGroup, ProjectLeader, MediaEducationSupervisor


class ProjectsWidget:
    """Widget for projects statistics and analytics."""
    
    def __init__(self, request):
        self.request = request
        self._cache = {}
        self._cache_timeout = 300  # 5 minutes
    
    def get_data(self):
        """Get all projects data."""
        return {
            'basic_stats': self.get_basic_stats(),
            'projects_by_category': self.get_projects_by_category(),
            'projects_by_target_group': self.get_projects_by_target_group(),
            'projects_by_leader': self.get_projects_by_leader(),
            'projects_trend': self.get_projects_trend(),
            'participants_stats': self.get_participants_stats(),
            'demographic_stats': self.get_demographic_stats(),
            'project_characteristics': self.get_project_characteristics(),
        }
    
    def get_basic_stats(self):
        """Get basic project statistics."""
        filtered_projects = self._get_filtered_projects()
        
        total_projects = filtered_projects.count()
        external_venue_projects = filtered_projects.filter(external_venue=True).count()
        jugendmedienschutz_projects = filtered_projects.filter(jugendmedienschutz=True).count()
        democracy_projects = filtered_projects.filter(democracy_project=True).count()
        
        # Calculate total participants
        total_participants = filtered_projects.aggregate(
            total=Sum('tn_female') + Sum('tn_male') + Sum('tn_gender_not_given') + Sum('tn_diverse')
        )['total'] or 0
        
        # Calculate average participants per project
        avg_participants = filtered_projects.aggregate(
            avg=Avg('tn_female') + Avg('tn_male') + Avg('tn_gender_not_given') + Avg('tn_diverse')
        )['avg'] or 0
        
        return {
            'total_projects': total_projects,
            'external_venue_projects': external_venue_projects,
            'jugendmedienschutz_projects': jugendmedienschutz_projects,
            'democracy_projects': democracy_projects,
            'total_participants': total_participants,
            'avg_participants_per_project': round(avg_participants, 1),
        }
    
    def get_projects_by_category(self):
        """Get projects grouped by category."""
        filtered_projects = self._get_filtered_projects()
        
        return list(filtered_projects.values(
            'project_category__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count'))
    
    def get_projects_by_target_group(self):
        """Get projects grouped by target group."""
        filtered_projects = self._get_filtered_projects()
        
        return list(filtered_projects.values(
            'target_group__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count'))
    
    def get_projects_by_leader(self):
        """Get projects grouped by project leader."""
        filtered_projects = self._get_filtered_projects()
        
        return list(filtered_projects.values(
            'project_leader__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10])  # Top 10 leaders
    
    def get_projects_trend(self):
        """Get projects trend over time."""
        filtered_projects = self._get_filtered_projects()
        
        # Group by month
        return list(filtered_projects.extra(
            select={'month': "DATE_TRUNC('month', date)"}
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month'))
    
    def get_participants_stats(self):
        """Get participants statistics by age groups."""
        filtered_projects = self._get_filtered_projects()
        
        age_stats = filtered_projects.aggregate(
            tn_0_bis_6=Sum('tn_0_bis_6'),
            tn_7_bis_10=Sum('tn_7_bis_10'),
            tn_11_bis_14=Sum('tn_11_bis_14'),
            tn_15_bis_18=Sum('tn_15_bis_18'),
            tn_19_bis_34=Sum('tn_19_bis_34'),
            tn_35_bis_50=Sum('tn_35_bis_50'),
            tn_51_bis_65=Sum('tn_51_bis_65'),
            tn_ueber_65=Sum('tn_ueber_65'),
            tn_age_not_given=Sum('tn_age_not_given'),
        )
        
        gender_stats = filtered_projects.aggregate(
            tn_female=Sum('tn_female'),
            tn_male=Sum('tn_male'),
            tn_diverse=Sum('tn_diverse'),
            tn_gender_not_given=Sum('tn_gender_not_given'),
        )
        
        return {
            'age_groups': age_stats,
            'gender_groups': gender_stats,
        }
    
    def get_demographic_stats(self):
        """Get demographic statistics."""
        filtered_projects = self._get_filtered_projects()
        
        # Age group distribution
        age_distribution = {
            'under_18': filtered_projects.aggregate(
                total=Sum('tn_0_bis_6') + Sum('tn_7_bis_10') + Sum('tn_11_bis_14') + Sum('tn_15_bis_18')
            )['total'] or 0,
            '18_34': filtered_projects.aggregate(
                total=Sum('tn_19_bis_34')
            )['total'] or 0,
            '35_50': filtered_projects.aggregate(
                total=Sum('tn_35_bis_50')
            )['total'] or 0,
            'over_50': filtered_projects.aggregate(
                total=Sum('tn_51_bis_65') + Sum('tn_ueber_65')
            )['total'] or 0,
        }
        
        # Gender distribution
        gender_distribution = {
            'female': filtered_projects.aggregate(total=Sum('tn_female'))['total'] or 0,
            'male': filtered_projects.aggregate(total=Sum('tn_male'))['total'] or 0,
            'diverse': filtered_projects.aggregate(total=Sum('tn_diverse'))['total'] or 0,
            'not_given': filtered_projects.aggregate(total=Sum('tn_gender_not_given'))['total'] or 0,
        }
        
        return {
            'age_distribution': age_distribution,
            'gender_distribution': gender_distribution,
        }
    
    def get_project_characteristics(self):
        """Get project characteristics statistics."""
        filtered_projects = self._get_filtered_projects()
        
        total_projects = filtered_projects.count()
        
        if total_projects == 0:
            return {
                'external_venue_rate': 0,
                'jugendmedienschutz_rate': 0,
                'democracy_rate': 0,
            }
        
        external_venue_rate = (filtered_projects.filter(external_venue=True).count() / total_projects) * 100
        jugendmedienschutz_rate = (filtered_projects.filter(jugendmedienschutz=True).count() / total_projects) * 100
        democracy_rate = (filtered_projects.filter(democracy_project=True).count() / total_projects) * 100
        
        return {
            'external_venue_rate': round(external_venue_rate, 1),
            'jugendmedienschutz_rate': round(jugendmedienschutz_rate, 1),
            'democracy_rate': round(democracy_rate, 1),
        }
    
    def _get_filtered_projects(self):
        """Get projects filtered by request parameters."""
        projects = Project.objects.all()
        
        # Date range filter
        days = self.request.GET.get('days', '30')
        if days != 'all':
            try:
                days_int = int(days)
                start_date = timezone.now().date() - timedelta(days=days_int)
                projects = projects.filter(date__gte=start_date)
            except (ValueError, TypeError):
                pass
        
        # Custom date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                projects = projects.filter(date__range=[start_date_obj, end_date_obj])
            except ValueError:
                pass
        
        # Category filter
        category = self.request.GET.get('category')
        if category:
            projects = projects.filter(project_category_id=category)
        
        # Target group filter
        target_group = self.request.GET.get('target_group')
        if target_group:
            projects = projects.filter(target_group_id=target_group)
        
        # Project leader filter
        project_leader = self.request.GET.get('project_leader')
        if project_leader:
            projects = projects.filter(project_leader_id=project_leader)
        
        # External venue filter
        external_venue = self.request.GET.get('external_venue')
        if external_venue == 'true':
            projects = projects.filter(external_venue=True)
        elif external_venue == 'false':
            projects = projects.filter(external_venue=False)
        
        # Jugendmedienschutz filter
        jugendmedienschutz = self.request.GET.get('jugendmedienschutz')
        if jugendmedienschutz == 'true':
            projects = projects.filter(jugendmedienschutz=True)
        elif jugendmedienschutz == 'false':
            projects = projects.filter(jugendmedienschutz=False)
        
        # Democracy project filter
        democracy_project = self.request.GET.get('democracy_project')
        if democracy_project == 'true':
            projects = projects.filter(democracy_project=True)
        elif democracy_project == 'false':
            projects = projects.filter(democracy_project=False)
        
        return projects
