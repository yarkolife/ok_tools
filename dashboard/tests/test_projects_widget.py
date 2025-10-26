"""
Unit tests for dashboard/widgets/projects.py
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.utils import timezone
from dashboard.widgets.projects import ProjectsWidget
from projects.models import Project


class TestProjectsWidget(TestCase):
    """Test ProjectsWidget class"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/dashboard/')
        self.widget = ProjectsWidget(self.request)
    
    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.widget.request, self.request)
        self.assertEqual(self.widget._cache, {})
        self.assertEqual(self.widget._cache_timeout, 300)
    
    def test_get_data(self):
        """Test getting all data"""
        # Mock individual methods to return test data
        with patch.object(self.widget, 'get_basic_stats') as mock_get_basic_stats, \
             patch.object(self.widget, 'get_projects_by_category') as mock_get_projects_by_category, \
             patch.object(self.widget, 'get_projects_by_target_group') as mock_get_projects_by_target_group, \
             patch.object(self.widget, 'get_projects_by_leader') as mock_get_projects_by_leader, \
             patch.object(self.widget, 'get_projects_trend') as mock_get_projects_trend, \
             patch.object(self.widget, 'get_participants_stats') as mock_get_participants_stats, \
             patch.object(self.widget, 'get_demographic_stats') as mock_get_demographic_stats, \
             patch.object(self.widget, 'get_project_characteristics') as mock_get_project_characteristics:
            
            # Set return values
            mock_get_basic_stats.return_value = {'total_projects': 100}
            mock_get_projects_by_category.return_value = []
            mock_get_projects_by_target_group.return_value = []
            mock_get_projects_by_leader.return_value = []
            mock_get_projects_trend.return_value = []
            mock_get_participants_stats.return_value = {'age_groups': {}, 'gender_groups': {}}
            mock_get_demographic_stats.return_value = {'age_distribution': {}, 'gender_distribution': {}}
            mock_get_project_characteristics.return_value = {'external_venue_rate': 20.0}
            
            result = self.widget.get_data()
            
            self.assertIn('basic_stats', result)
            self.assertIn('projects_by_category', result)
            self.assertIn('projects_by_target_group', result)
            self.assertIn('projects_by_leader', result)
            self.assertIn('projects_trend', result)
            self.assertIn('participants_stats', result)
            self.assertIn('demographic_stats', result)
            self.assertIn('project_characteristics', result)
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_basic_stats_cached(self, mock_project_model, mock_cache):
        """Test getting basic stats with cached result"""
        mock_cache.get.return_value = {
            'total_projects': 100,
            'external_venue_projects': 20,
            'jugendmedienschutz_projects': 10,
            'democracy_projects': 5,
            'total_participants': 500,
            'avg_participants_per_project': 5.0
        }
        
        result = self.widget.get_basic_stats()
        
        self.assertEqual(result['total_projects'], 100)
        mock_cache.get.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_basic_stats_not_cached(self, mock_project_model, mock_cache):
        """Test getting basic stats without cached result"""
        # Mock no cached result
        mock_cache.get.return_value = None
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        mock_filtered_projects.count.return_value = 100
        mock_filtered_projects.filter.return_value.count.return_value = 20  # external venue
        mock_filtered_projects.filter.return_value.count.return_value = 10  # jugendmedienschutz
        mock_filtered_projects.filter.return_value.count.return_value = 5  # democracy
        
        # Mock aggregation for participants
        mock_filtered_projects.aggregate.side_effect = [
            {'total': 500},  # for total participants
            {'avg': 5.0}     # for average participants
        ]
        
        result = self.widget.get_basic_stats()
        
        self.assertEqual(result['total_projects'], 100)
        self.assertEqual(result['external_venue_projects'], 20)
        self.assertEqual(result['jugendmedienschutz_projects'], 10)
        self.assertEqual(result['democracy_projects'], 5)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_projects_by_category(self, mock_project_model, mock_cache):
        """Test getting projects by category"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        # Mock the values and annotate chain
        mock_values_queryset = Mock()
        mock_filtered_projects.values.return_value = mock_values_queryset
        mock_values_annotated = Mock()
        mock_values_queryset.annotate.return_value = mock_values_annotated
        mock_annotated_result = [{'project_category__name': 'Education', 'count': 10}]
        mock_values_annotated.order_by.return_value = mock_annotated_result
        
        result = self.widget.get_projects_by_category()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['project_category__name'], 'Education')
        self.assertEqual(result[0]['count'], 10)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_projects_by_target_group(self, mock_project_model, mock_cache):
        """Test getting projects by target group"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        # Mock the values and annotate chain
        mock_values_queryset = Mock()
        mock_filtered_projects.values.return_value = mock_values_queryset
        mock_values_annotated = Mock()
        mock_values_queryset.annotate.return_value = mock_values_annotated
        mock_annotated_result = [{'target_group__name': 'Children', 'count': 5}]
        mock_values_annotated.order_by.return_value = mock_annotated_result
        
        result = self.widget.get_projects_by_target_group()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['target_group__name'], 'Children')
        self.assertEqual(result[0]['count'], 5)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_projects_by_leader(self, mock_project_model, mock_cache):
        """Test getting projects by leader"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        # Mock the values and annotate chain
        mock_values_queryset = Mock()
        mock_filtered_projects.values.return_value = mock_values_queryset
        mock_values_annotated = Mock()
        mock_values_queryset.annotate.return_value = mock_values_annotated
        mock_annotated_result = [{'project_leader__name': 'John Doe', 'count': 8}]
        mock_values_annotated.order_by.return_value = mock_annotated_result
        
        result = self.widget.get_projects_by_leader()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['project_leader__name'], 'John Doe')
        self.assertEqual(result[0]['count'], 8)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_projects_trend(self, mock_project_model, mock_cache):
        """Test getting projects trend"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        # Mock the extra and values chain for trend data
        mock_extra_queryset = Mock()
        mock_filtered_projects.extra.return_value = mock_extra_queryset
        mock_values_queryset = Mock()
        mock_extra_queryset.values.return_value = mock_values_queryset
        mock_annotated_queryset = Mock()
        mock_values_queryset.annotate.return_value = mock_annotated_queryset
        mock_result_list = [{'month': '2023-01-01', 'count': 5}]
        mock_annotated_queryset.order_by.return_value = mock_result_list
        
        result = self.widget.get_projects_trend()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['month'], '2023-01-01')
        self.assertEqual(result[0]['count'], 5)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_participants_stats(self, mock_project_model, mock_cache):
        """Test getting participants stats"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        # Mock the aggregate for age stats
        age_stats = {
            'tn_0_bis_6': 10,
            'tn_7_bis_10': 15,
            'tn_11_bis_14': 20,
            'tn_15_bis_18': 25,
            'tn_19_bis_34': 30,
            'tn_35_bis_50': 35,
            'tn_51_bis_65': 40,
            'tn_ueber_65': 45,
            'tn_age_not_given': 5
        }
        gender_stats = {
            'tn_female': 100,
            'tn_male': 80,
            'tn_diverse': 10,
            'tn_gender_not_given': 5
        }
        
        mock_filtered_projects.aggregate.side_effect = [age_stats, gender_stats]
        
        result = self.widget.get_participants_stats()
        
        self.assertEqual(result['age_groups'], age_stats)
        self.assertEqual(result['gender_groups'], gender_stats)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_demographic_stats(self, mock_project_model, mock_cache):
        """Test getting demographic stats"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        # Mock the aggregate calls for age distribution
        mock_filtered_projects.aggregate.side_effect = [
            {'total': 70},  # under_18 (sum of 0-6, 7-10, 11-14, 15-18)
            {'total': 30},  # 18-34
            {'total': 35},  # 35-50
            {'total': 85}   # over_50 (sum of 51-65, over_65)
        ]
        
        # Mock the aggregate calls for gender distribution
        mock_filtered_projects.aggregate.side_effect = [
            {'total': 70},  # under_18
            {'total': 30},  # 18-34
            {'total': 35},  # 35-50
            {'total': 85},  # over_50 (sum of 51-65, over_65)
            {'total': 100}, # female
            {'total': 80},  # male
            {'total': 10},  # diverse
            {'total': 5}    # not_given
        ]
        
        result = self.widget.get_demographic_stats()
        
        self.assertIn('age_distribution', result)
        self.assertIn('gender_distribution', result)
        mock_cache.set.assert_called_once()
    
    @patch('dashboard.widgets.projects.cache')
    @patch('dashboard.widgets.projects.Project')
    def test_get_project_characteristics(self, mock_project_model, mock_cache):
        """Test getting project characteristics"""
        mock_cache.get.return_value = None  # No cached result
        
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        mock_filtered_projects.count.return_value = 100
        mock_filtered_projects.filter.return_value.count.return_value = 20  # external venue
        mock_filtered_projects.filter.return_value.count.return_value = 10  # jugendmedienschutz
        mock_filtered_projects.filter.return_value.count.return_value = 5  # democracy
        
        result = self.widget.get_project_characteristics()
        
        self.assertEqual(result['external_venue_rate'], 20.0)
        self.assertEqual(result['jugendmedienschutz_rate'], 10.0)
        self.assertEqual(result['democracy_rate'], 5.0)
        mock_cache.set.assert_called_once()
    
    def test_get_filtered_projects_default(self):
        """Test getting filtered projects with default parameters"""
        # Create a request with default parameters
        request = self.factory.get('/dashboard/')
        
        request = self.factory.get('/dashboard/?days=all')
        
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset

            widget = ProjectsWidget(request)
            projects = widget._get_filtered_projects()

            # Should return all projects since no date filter is applied
            self.assertEqual(projects, mock_queryset)
    
    def test_get_filtered_projects_with_days_filter(self):
        """Test getting filtered projects with days filter"""
        # Create a request with days parameter
        request = self.factory.get('/dashboard/?days=7')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by date
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_custom_date_range(self):
        """Test getting filtered projects with custom date range"""
        # Create a request with custom date range
        request = self.factory.get('/dashboard/?start_date=2023-01-01&end_date=2023-01-31')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by date range
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_category_filter(self):
        """Test getting filtered projects with category filter"""
        # Create a request with category parameter
        request = self.factory.get('/dashboard/?days=all&category=1')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by category
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_target_group_filter(self):
        """Test getting filtered projects with target group filter"""
        # Create a request with target group parameter
        request = self.factory.get('/dashboard/?days=all&target_group=1')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by target group
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_leader_filter(self):
        """Test getting filtered projects with leader filter"""
        # Create a request with project leader parameter
        request = self.factory.get('/dashboard/?days=all&project_leader=1')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by project leader
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_external_venue_filter(self):
        """Test getting filtered projects with external venue filter"""
        # Create a request with external venue parameter
        request = self.factory.get('/dashboard/?days=all&external_venue=true')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by external venue
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_jugendmedienschutz_filter(self):
        """Test getting filtered projects with jugendmedienschutz filter"""
        # Create a request with jugendmedienschutz parameter
        request = self.factory.get('/dashboard/?days=all&jugendmedienschutz=true')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by jugendmedienschutz
            self.assertEqual(projects, filtered_mock)
    
    def test_get_filtered_projects_with_democracy_project_filter(self):
        """Test getting filtered projects with democracy project filter"""
        # Create a request with democracy project parameter
        request = self.factory.get('/dashboard/?days=all&democracy_project=true')
        
        widget = ProjectsWidget(request)
        # Mock Project.objects.all() to return a mock queryset
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            mock_queryset = Mock()
            mock_project_model.objects.all.return_value = mock_queryset
            
            # Mock the filter method
            filtered_mock = Mock()
            mock_queryset.filter.return_value = filtered_mock
            
            projects = widget._get_filtered_projects()
            
            # Should have been filtered by democracy project
            self.assertEqual(projects, filtered_mock)
    
    def test_get_detailed_projects(self):
        """Test getting detailed projects"""
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            # Mock the select_related queryset
            mock_queryset = Mock()
            mock_project_model.objects.select_related.return_value = mock_queryset
            mock_select_related = Mock()
            mock_select_related.all.return_value = mock_select_related
            mock_project_model.objects.select_related.return_value = mock_select_related
            
            # Mock filtered projects
            mock_filtered_queryset = MagicMock()
            self.widget._get_filtered_projects = Mock(return_value=mock_filtered_queryset)
            
            # Create a mock project
            mock_project = Mock()
            mock_project.id = 1
            mock_project.title = "Test Project"
            mock_project.date = timezone.now().date()
            mock_project_category = Mock()
            mock_project_category.name = "Education"
            mock_target_group = Mock()
            mock_target_group.name = "Children"
            mock_project_leader = Mock()
            mock_project_leader.name = "John Doe"
            mock_project.project_category = mock_project_category
            mock_project.target_group = mock_target_group
            mock_project.project_leader = mock_project_leader
            mock_project.external_venue = False
            mock_project.jugendmedienschutz = True
            mock_project.democracy_project = False
            mock_project.tn_female = 10
            mock_project.tn_male = 8
            mock_project.tn_diverse = 2
            mock_project.tn_gender_not_given = 0
            mock_project.tn_0_bis_6 = 5
            mock_project.tn_7_bis_10 = 3
            mock_project.tn_11_bis_14 = 4
            mock_project.tn_15_bis_18 = 2
            mock_project.tn_19_bis_34 = 6
            mock_project.tn_35_bis_50 = 7
            mock_project.tn_51_bis_65 = 8
            mock_project.tn_ueber_65 = 5
            
            # Mock the filtered queryset iteration and slicing
            mock_filtered_queryset.__iter__.return_value = iter([mock_project])

            def _getitem(item):
                data = [mock_project]
                if isinstance(item, slice):
                    return data[item]
                return data[item]

            mock_filtered_queryset.__getitem__.side_effect = _getitem
            mock_filtered_queryset.count.return_value = 1
            
            result = self.widget.get_detailed_projects()
            
            self.assertIn('projects', result)
            self.assertIn('total_count', result)
            self.assertIn('displayed_count', result)
            self.assertEqual(len(result['projects']), 1)
            self.assertEqual(result['projects'][0]['title'], 'Test Project')
            self.assertEqual(result['projects'][0]['category'], 'Education')
    
    def test_get_detailed_projects_by_participants(self):
        """Test getting detailed projects by participants"""
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            # Mock filtered projects
            mock_filtered_queryset = Mock()
            self.widget._get_filtered_projects = Mock(return_value=mock_filtered_queryset)
            
            # Create a mock project
            mock_project = Mock()
            mock_project.id = 1
            mock_project.title = "Test Project"
            mock_project.date = timezone.now().date()
            mock_project_category = Mock()
            mock_project_category.name = "Education"
            mock_target_group = Mock()
            mock_target_group.name = "Children"
            mock_project_leader = Mock()
            mock_project_leader.name = "John Doe"
            mock_project.project_category = mock_project_category
            mock_project.target_group = mock_target_group
            mock_project.project_leader = mock_project_leader
            mock_project.external_venue = False
            mock_project.jugendmedienschutz = True
            mock_project.democracy_project = False
            mock_project.tn_female = 10
            mock_project.tn_male = 8
            mock_project.tn_diverse = 2
            mock_project.tn_gender_not_given = 0
            mock_project.tn_gender_not_given = 0
            
            # Mock the filtered queryset
            mock_filtered_queryset.__iter__ = Mock(return_value=iter([mock_project]))
            
            result = self.widget.get_detailed_projects_by_participants()
            
            self.assertIn('projects', result)
            self.assertIn('total_count', result)
            self.assertIn('displayed_count', result)
            self.assertEqual(len(result['projects']), 1)
            self.assertEqual(result['projects'][0]['title'], 'Test Project')
            self.assertEqual(result['projects'][0]['total_participants'], 20)  # 10+8+2+0
    
    def test_get_detailed_projects_by_average_participants(self):
        """Test getting detailed projects by average participants"""
        with patch('dashboard.widgets.projects.Project') as mock_project_model:
            # Mock filtered projects
            mock_filtered_queryset = Mock()
            self.widget._get_filtered_projects = Mock(return_value=mock_filtered_queryset)
            
            # Create a mock project
            mock_project = Mock()
            mock_project.id = 1
            mock_project.title = "Test Project"
            mock_project.date = timezone.now().date()
            mock_project_category = Mock()
            mock_project_category.name = "Education"
            mock_target_group = Mock()
            mock_target_group.name = "Children"
            mock_project_leader = Mock()
            mock_project_leader.name = "John Doe"
            mock_project.project_category = mock_project_category
            mock_project.target_group = mock_target_group
            mock_project.project_leader = mock_project_leader
            mock_project.external_venue = False
            mock_project.jugendmedienschutz = True
            mock_project.democracy_project = False
            mock_project.tn_female = 10
            mock_project.tn_male = 8
            mock_project.tn_diverse = 2
            mock_project.tn_gender_not_given = 0
            mock_project.tn_gender_not_given = 0
            
            # Mock the filtered queryset
            mock_filtered_queryset.__iter__ = Mock(return_value=iter([mock_project]))
            
            result = self.widget.get_detailed_projects_by_average_participants()
            
            self.assertIn('projects', result)
            self.assertIn('total_count', result)
            self.assertIn('displayed_count', result)
            self.assertEqual(len(result['projects']), 1)
            self.assertEqual(result['projects'][0]['title'], 'Test Project')
            self.assertEqual(result['projects'][0]['total_participants'], 20)  # 10+8+2+0
    
    def test_calculate_total_participants(self):
        """Test calculating total participants"""
        # Create a mock project
        mock_project = Mock()
        mock_project.tn_female = 10
        mock_project.tn_male = 8
        mock_project.tn_diverse = 2
        mock_project.tn_gender_not_given = 1
        
        result = self.widget._calculate_total_participants(mock_project)
        
        self.assertEqual(result, 21)  # 10+8+2+1
    
    @patch('dashboard.widgets.projects.Project')
    def test_get_projects_by_venue(self, mock_project_model):
        """Test getting projects by venue"""
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        external_qs = Mock()
        external_qs.count.return_value = 15
        internal_qs = Mock()
        internal_qs.count.return_value = 25
        mock_filtered_projects.filter.side_effect = [external_qs, internal_qs]
        
        result = self.widget.get_projects_by_venue()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['venue_type'], 'External')
        self.assertEqual(result[0]['count'], 15)
        self.assertEqual(result[1]['venue_type'], 'Internal')
        self.assertEqual(result[1]['count'], 25)
    
    def test_get_gender_distribution(self):
        """Test getting gender distribution"""
        with patch.object(self.widget, 'get_participants_stats') as mock_get_participants_stats:
            mock_get_participants_stats.return_value = {
                'gender_groups': {
                    'tn_female': 100,
                    'tn_male': 80,
                    'tn_diverse': 10,
                    'tn_gender_not_given': 5
                }
            }
            
            result = self.widget.get_gender_distribution()
            
            self.assertEqual(result['female'], 100)
            self.assertEqual(result['male'], 80)
            self.assertEqual(result['diverse'], 10)
            self.assertEqual(result['not_given'], 5)
    
    def test_get_age_distribution(self):
        """Test getting age distribution"""
        with patch.object(self.widget, 'get_participants_stats') as mock_get_participants_stats:
            mock_get_participants_stats.return_value = {
                'age_groups': {
                    'tn_0_bis_6': 5,
                    'tn_7_bis_10': 10,
                    'tn_11_bis_14': 15,
                    'tn_15_bis_18': 20,
                    'tn_19_bis_34': 25,
                    'tn_35_bis_50': 30,
                    'tn_51_bis_65': 35,
                    'tn_ueber_65': 40
                }
            }
            
            result = self.widget.get_age_distribution()
            
            self.assertEqual(result['age_0_6'], 5)
            self.assertEqual(result['age_7_10'], 10)
            self.assertEqual(result['age_11_14'], 15)
            self.assertEqual(result['age_15_18'], 20)
            self.assertEqual(result['age_19_34'], 25)
            self.assertEqual(result['age_35_50'], 30)
            self.assertEqual(result['age_51_65'], 35)
            self.assertEqual(result['age_over_65'], 40)
    
    @patch('dashboard.widgets.projects.Project')
    def test_get_youth_protection_stats(self, mock_project_model):
        """Test getting youth protection stats"""
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        mock_filtered_projects.count.return_value = 100
        mock_filtered_projects.filter.return_value.count.return_value = 25  # jugendmedienschutz projects
        
        result = self.widget.get_youth_protection_stats()
        
        self.assertEqual(result['total_projects'], 100)
        self.assertEqual(result['youth_protection_projects'], 25)
        self.assertEqual(result['percentage'], 25.0)
    
    @patch('dashboard.widgets.projects.Project')
    def test_get_democracy_project_stats(self, mock_project_model):
        """Test getting democracy project stats"""
        # Mock filtered projects
        mock_filtered_projects = Mock()
        self.widget._get_filtered_projects = Mock(return_value=mock_filtered_projects)
        
        mock_filtered_projects.count.return_value = 100
        mock_filtered_projects.filter.return_value.count.return_value = 15  # democracy projects
        
        result = self.widget.get_democracy_project_stats()
        
        self.assertEqual(result['total_projects'], 100)
        self.assertEqual(result['democracy_projects'], 15)
        self.assertEqual(result['percentage'], 15.0)
    
    def test_get_detailed_data(self):
        """Test getting detailed data"""
        with patch.object(self.widget, 'get_detailed_projects') as mock_get_detailed_projects, \
             patch.object(self.widget, 'get_basic_stats') as mock_get_basic_stats, \
             patch.object(self.widget, 'get_projects_by_category') as mock_get_projects_by_category, \
             patch.object(self.widget, 'get_projects_by_target_group') as mock_get_projects_by_target_group, \
             patch.object(self.widget, 'get_projects_by_leader') as mock_get_projects_by_leader, \
             patch.object(self.widget, 'get_projects_by_venue') as mock_get_projects_by_venue, \
             patch.object(self.widget, 'get_projects_trend') as mock_get_projects_trend, \
             patch.object(self.widget, 'get_participant_stats') as mock_get_participant_stats, \
             patch.object(self.widget, 'get_gender_distribution') as mock_get_gender_distribution, \
             patch.object(self.widget, 'get_age_distribution') as mock_get_age_distribution, \
             patch.object(self.widget, 'get_youth_protection_stats') as mock_get_youth_protection_stats, \
             patch.object(self.widget, 'get_democracy_project_stats') as mock_get_democracy_project_stats:
            
            # Set return values
            mock_get_detailed_projects.return_value = {'projects': [], 'total_count': 0, 'displayed_count': 0}
            mock_get_basic_stats.return_value = {'total_projects': 100}
            mock_get_projects_by_category.return_value = []
            mock_get_projects_by_target_group.return_value = []
            mock_get_projects_by_leader.return_value = []
            mock_get_projects_by_venue.return_value = []
            mock_get_projects_trend.return_value = []
            mock_get_participant_stats.return_value = {}
            mock_get_gender_distribution.return_value = {}
            mock_get_age_distribution.return_value = {}
            mock_get_youth_protection_stats.return_value = {'percentage': 10.0}
            mock_get_democracy_project_stats.return_value = {'percentage': 5.0}
            
            result = self.widget.get_detailed_data()
            
            self.assertIn('projects', result)
            self.assertIn('basic_stats', result)
            self.assertIn('projects_by_category', result)
            self.assertIn('projects_by_target_group', result)
            self.assertIn('projects_by_leader', result)
            self.assertIn('projects_by_venue', result)
            self.assertIn('projects_trend', result)
            self.assertIn('participant_stats', result)
            self.assertIn('gender_distribution', result)
            self.assertIn('age_distribution', result)
            self.assertIn('youth_protection_stats', result)
            self.assertIn('democracy_project_stats', result)