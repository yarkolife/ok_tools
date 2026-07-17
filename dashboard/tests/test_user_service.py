"""
Tests for UserService in dashboard application.
"""

from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from registration.models import OKUser

from registration.models import Profile, MediaAuthority
from licenses.models import License
from dashboard.services.user_service import UserService


class UserServiceTestCase(TestCase):
    """Test cases for UserService class."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user_service = UserService()
        
        # Create test user
        self.user = OKUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test media authority
        self.media_authority = MediaAuthority.objects.create(
            name='Test Media Authority'
        )
        
        # Create test profiles
        self.profile1 = Profile.objects.create(
            okuser=self.user,
            first_name='John',
            last_name='Doe',
            gender='m',
            birthday=datetime(1990, 1, 1).date(),
            verified=True,
            member=True,
            media_authority=self.media_authority
        )
        
        self.profile2 = Profile.objects.create(
            okuser=OKUser.objects.create_user(
                email='test2@example.com',
                password='testpass123'
            ),
            first_name='Jane',
            last_name='Smith',
            gender='f',
            birthday=datetime(1985, 5, 15).date(),
            verified=False,
            member=False,
            media_authority=self.media_authority
        )
        
        # Create test license
        self.license = License.objects.create(
            profile=self.profile1,
            title='Test License',
            confirmed=True
        )
    
    def test_get_users_statistics_basic(self):
        """Test basic user statistics functionality."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('basic_stats', result['data'])
            self.assertEqual(result['data']['basic_stats']['total_users'], 2)
            self.assertEqual(result['data']['basic_stats']['male_users'], 1)
            self.assertEqual(result['data']['basic_stats']['female_users'], 1)
            self.assertEqual(result['data']['basic_stats']['verified_users'], 1)
            self.assertEqual(result['data']['basic_stats']['member_users'], 1)
    
    def test_get_users_statistics_with_age_groups(self):
        """Test user statistics with age groups calculation."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': datetime.now().date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for age groups
            self.assertTrue(result['success'])
            self.assertIn('age_groups', result['data'])
            
            # Profile1 (1990) should be in 35_50 group
            # Profile2 (1985) should be in 35_50 group
            self.assertEqual(result['data']['age_groups']['35_50'], 2)
    
    def test_get_users_statistics_with_gender_age_distribution(self):
        """Test user statistics with gender-age distribution."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': datetime.now().date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for gender-age distribution
            self.assertTrue(result['success'])
            self.assertIn('age_gender_distribution', result['data'])
            
            # Check male distribution
            self.assertEqual(result['data']['age_gender_distribution']['male']['35_50'], 1)
            # Check female distribution
            self.assertEqual(result['data']['age_gender_distribution']['female']['35_50'], 1)
    
    def test_get_users_statistics_with_diverse_gender(self):
        """Test user statistics with diverse gender."""
        # Create a profile with diverse gender
        diverse_profile = Profile.objects.create(
            okuser=OKUser.objects.create_user(
                email='diverse@example.com',
                password='testpass123'
            ),
            first_name='Alex',
            last_name='Johnson',
            gender='d',
            birthday=datetime(2000, 1, 1).date(),
            verified=True,
            member=True,
            media_authority=self.media_authority
        )
        
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': datetime.now().date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for diverse gender
            self.assertTrue(result['success'])
            self.assertEqual(result['data']['basic_stats']['diverse_users'], 1)
            self.assertEqual(result['data']['age_gender_distribution']['diverse']['up_to_34'], 1)
    
    def test_get_users_statistics_with_unknown_birthday(self):
        """Test user statistics with unknown birthday (01.01.1800)."""
        # Create a profile with the default unknown birthday
        unknown_birthday_profile = Profile.objects.create(
            okuser=OKUser.objects.create_user(
                email='unknown@example.com',
                password='testpass123'
            ),
            first_name='Unknown',
            last_name='Birthday',
            gender='m',
            birthday=datetime(1800, 1, 1).date(),  # Default unknown date
            verified=True,
            member=True,
            media_authority=self.media_authority
        )
        
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': datetime.now().date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for unknown birthday
            self.assertTrue(result['success'])
            self.assertEqual(result['data']['age_groups']['unknown'], 1)
            self.assertEqual(result['data']['age_gender_distribution']['male']['unknown'], 1)
    
    def test_get_users_statistics_with_no_birthday(self):
        """Test user statistics with no birthday."""
        # Create a profile with no birthday (None)
        no_birthday_profile = Profile.objects.create(
            okuser=OKUser.objects.create_user(
                email='nobirthday@example.com',
                password='testpass123'
            ),
            first_name='No',
            last_name='Birthday',
            gender='f',
            birthday=None,  # No birthday
            verified=True,
            member=True,
            media_authority=self.media_authority
        )
        
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': datetime.now().date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for no birthday
            self.assertTrue(result['success'])
            self.assertEqual(result['data']['age_groups']['unknown'], 1)
            self.assertEqual(result['data']['age_gender_distribution']['female']['unknown'], 1)
    
    def test_get_users_statistics_with_registration_trend(self):
        """Test user statistics with registration trend."""
        # Create mock request with date range
        request = self.factory.get('/?start_date=2023-01-01&end_date=2023-01-31')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': datetime(2023, 1, 1).date(),
                'end_date': datetime(2023, 1, 31).date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for registration trend
            self.assertTrue(result['success'])
            self.assertIn('registration_trend', result['data'])
    
    def test_get_users_statistics_with_weekly_trend(self):
        """Test user statistics with weekly trend (for periods > 30 days)."""
        # Create mock request with date range longer than 30 days
        request = self.factory.get('/?start_date=2023-01-01&end_date=2023-03-01')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': datetime(2023, 1, 1).date(),
                'end_date': datetime(2023, 3, 1).date()
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for weekly trend
            self.assertTrue(result['success'])
            self.assertIn('registration_trend', result['data'])
    
    def test_get_users_statistics_with_users_by_authority(self):
        """Test user statistics with users by authority."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions for users by authority
            self.assertTrue(result['success'])
            self.assertIn('users_by_authority', result['data'])
    
    def test_get_users_statistics_with_authority_error(self):
        """Test user statistics when media authority query fails."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters with error in media authority query
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            # Mock the queryset to raise an exception when filtering by authority
            mock_queryset = Mock()
            mock_queryset.count.return_value = 2
            mock_queryset.filter.return_value.count.return_value = 1
            mock_queryset.values.side_effect = Exception("Database error")
            mock_filter_instance.apply_filters_to_queryset.return_value = mock_queryset
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions - should handle the error gracefully
            self.assertTrue(result['success'])
            # Should have empty list for users_by_authority
            self.assertEqual(result['data']['users_by_authority'], [])
    
    def test_get_users_statistics_with_age_calculation_error(self):
        """Test user statistics when age calculation fails."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters with error in age calculation
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.date_range = {
                'start_date': None,
                'end_date': None
            }
            # Mock the queryset to raise an exception when iterating
            mock_queryset = Mock()
            mock_queryset.count.return_value = 2
            mock_queryset.filter.return_value.count.return_value = 1
            mock_queryset.values.return_value.annotate.return_value.order_by.return_value = []
            # The age calculation iterates select_related(...); make that raise
            # so the service's age try/except is exercised.
            mock_queryset.select_related.side_effect = Exception("Age calc error")
            mock_filter_instance.apply_filters_to_queryset.return_value = mock_queryset
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance

            # Call the method
            result = self.user_service.get_users_statistics(request)

            # Should handle the error gracefully: age groups keep their defaults.
            self.assertTrue(result['success'])
            for count in result['data']['age_groups'].values():
                self.assertEqual(count, 0)
    
    def test_get_users_statistics_with_trend_error(self):
        """Test user statistics when trend calculation fails."""
        # Create mock request with date range
        request = self.factory.get('/?start_date=2023-01-01&end_date=2023-01-31')
        
        # Mock DashboardFilters with error in trend calculation
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            # Base statistics need real integer counts, otherwise the service
            # does arithmetic on Mocks and fails before reaching the trend.
            mock_queryset = Mock()
            mock_queryset.count.return_value = 2
            mock_queryset.filter.return_value.count.return_value = 1
            mock_queryset.values.return_value.annotate.return_value.order_by.return_value = []
            mock_queryset.select_related.return_value = []
            mock_filter_instance.apply_filters_to_queryset.return_value = mock_queryset
            # The trend block is entered by reading filters.date_range; make that
            # raise so the trend try/except is exercised and returns an empty
            # trend, while the rest of the statistics still succeed.
            mock_filter_instance.date_range = MagicMock()
            mock_filter_instance.date_range.__getitem__.side_effect = Exception(
                "Trend error")
            mock_filter_instance.get_all_data.return_value = {}
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions - should handle the error gracefully
            self.assertTrue(result['success'])
            # Trend should be empty list
            self.assertEqual(result['data']['registration_trend'], [])
    
    def test_get_users_statistics_error_handling(self):
        """Test error handling in get_users_statistics."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters to raise an exception
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filters.side_effect = Exception("Test error")
            
            # Call the method
            result = self.user_service.get_users_statistics(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
    
    def test_get_recent_users(self):
        """Test getting recent user activities."""
        # Create mock request
        request = self.factory.get('/?days=7')
        
        # Call the method
        result = self.user_service.get_recent_users(request)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertIn('activities', result['data'])
        self.assertIn('total_count', result['data'])
        self.assertEqual(result['data']['period_days'], 7)
        
        # Check that we have activities for new registrations
        activities = result['data']['activities']
        self.assertTrue(any(activity['type'] == 'user_registered' for activity in activities))
        self.assertTrue(any(activity['type'] == 'profile_verified' for activity in activities))
        self.assertTrue(any(activity['type'] == 'license_created' for activity in activities))
    
    def test_get_recent_users_with_different_days(self):
        """Test getting recent user activities with different day values."""
        # Test with different day values
        for days in [1, 7, 30, 90]:
            request = self.factory.get(f'/?days={days}')
            
            # Call the method
            result = self.user_service.get_recent_users(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('activities', result['data'])
            self.assertEqual(result['data']['period_days'], days)
    
    def test_get_recent_users_time_formatting(self):
        """Test time formatting in recent users."""
        # Create a very recent profile
        recent_profile = Profile.objects.create(
            okuser=OKUser.objects.create_user(
                email='recent@example.com',
                password='testpass123'
            ),
            first_name='Recent',
            last_name='User',
            gender='m',
            verified=True,
            member=True
        )
        
        # Create mock request
        request = self.factory.get('/?days=1')
        
        # Call the method
        result = self.user_service.get_recent_users(request)
        
        # Assertions
        self.assertTrue(result['success'])
        activities = result['data']['activities']
        
        # Find the recent user activity
        recent_activity = next(
            (activity for activity in activities 
             if activity['type'] == 'user_registered' and 'Recent' in activity['title']),
            None
        )
        
        self.assertIsNotNone(recent_activity)
        self.assertIn('time_ago', recent_activity)
        self.assertTrue(
            'minute' in recent_activity['time_ago'] or 
            'hour' in recent_activity['time_ago'] or 
            'day' in recent_activity['time_ago']
        )
    
    def test_get_recent_users_with_license_error(self):
        """Test getting recent users when license query fails."""
        # Create mock request
        request = self.factory.get('/?days=7')
        
        # Mock License model to raise an exception
        with patch('licenses.models.License') as mock_license:
            mock_license.objects.filter.side_effect = ImportError("Module not found")
            
            # Call the method
            result = self.user_service.get_recent_users(request)
            
            # Assertions - should handle the import error gracefully
            self.assertTrue(result['success'])
            # Should still return activities without license data
            self.assertIn('activities', result['data'])
    
    def test_get_recent_users_error_handling(self):
        """Test error handling in get_recent_users."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock Profile model to raise an exception
        with patch('dashboard.services.user_service.Profile') as mock_profile:
            mock_profile.objects.filter.side_effect = Exception("Test error")
            
            # Call the method
            result = self.user_service.get_recent_users(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_users_detail(self):
        """Test getting detailed user data."""
        # Create mock request
        request = self.factory.get('/?page=1')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertIn('users', result['data'])
            self.assertIn('pagination', result['data'])
            self.assertEqual(result['data']['total_count'], 2)
            self.assertEqual(result['data']['pagination']['current_page'], 1)
            self.assertEqual(result['data']['pagination']['per_page'], 20)
            
            # Check user data structure
            users = result['data']['users']
            self.assertEqual(len(users), 2)
            
            # Find our test user
            user_data = next(
                (user for user in users if user['id'] == self.profile1.id),
                None
            )
            self.assertIsNotNone(user_data)
            self.assertEqual(user_data['name'], 'John Doe')
            self.assertEqual(user_data['email'], 'test@example.com')
            # Account for localization - check both English and German values
            expected_genders = ['male', 'männlich']
            self.assertIn(user_data['gender'], expected_genders)
            self.assertTrue(user_data['verified'])
            self.assertTrue(user_data['member'])
    
    def test_get_users_detail_with_type_filter(self):
        """Test getting detailed user data with type filter."""
        # Test with male filter
        request = self.factory.get('/?type=male')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            users = result['data']['users']
            
            # Should only return male users
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]['name'], 'John Doe')
    
    def test_get_users_detail_with_female_filter(self):
        """Test getting detailed user data with female filter."""
        # Test with female filter
        request = self.factory.get('/?type=female')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            users = result['data']['users']
            
            # Should only return female users
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]['name'], 'Jane Smith')
    
    def test_get_users_detail_with_verified_filter(self):
        """Test getting detailed user data with verified filter."""
        # Test with verified filter
        request = self.factory.get('/?type=verified')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            users = result['data']['users']
            
            # Should only return verified users
            self.assertEqual(len(users), 1)  # Only profile1 is verified
            self.assertEqual(users[0]['name'], 'John Doe')
    
    def test_get_users_detail_with_member_filter(self):
        """Test getting detailed user data with member filter."""
        # Test with member filter
        request = self.factory.get('/?type=member')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            users = result['data']['users']
            
            # Should only return member users
            self.assertEqual(len(users), 1)  # Only profile1 is a member
            self.assertEqual(users[0]['name'], 'John Doe')
    
    def test_get_users_detail_pagination(self):
        """Test pagination in get_users_detail."""
        # Create more profiles to test pagination
        for i in range(25):
            Profile.objects.create(
                okuser=OKUser.objects.create_user(
                    email=f'user{i}@example.com',
                    password='testpass123'
                ),
                first_name=f'User{i}',
                last_name='Test',
                gender='m',
                verified=True,
                member=True
            )
        
        # Test first page
        request = self.factory.get('/?page=1')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['data']['users']), 20)  # Default per_page
            self.assertTrue(result['data']['pagination']['has_next'])
            self.assertFalse(result['data']['pagination']['has_previous'])
            
            # Test second page
            request = self.factory.get('/?page=2')
            result = self.user_service.get_users_detail(request)
            
            self.assertTrue(result['success'])
            self.assertGreater(len(result['data']['users']), 0)
            self.assertFalse(result['data']['pagination']['has_next'])
            self.assertTrue(result['data']['pagination']['has_previous'])
    
    def test_get_users_detail_with_age_calculation(self):
        """Test getting detailed user data with age calculation."""
        # Create a profile with a birthday
        profile_with_age = Profile.objects.create(
            okuser=OKUser.objects.create_user(
                email='age@example.com',
                password='testpass123'
            ),
            first_name='Age',
            last_name='Test',
            gender='f',
            birthday=datetime(1995, 6, 15).date(),
            verified=True,
            member=True
        )
        
        # Test request
        request = self.factory.get('/?page=1')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            users = result['data']['users']
            
            # Find the user with age
            age_user = next(
                (user for user in users if user['name'] == 'Age Test'),
                None
            )
            
            if age_user:
                self.assertIsNotNone(age_user['age'])
                # Calculate expected age
                today = datetime.now().date()
                expected_age = today.year - profile_with_age.birthday.year - ((today.month, today.day) < (profile_with_age.birthday.month, profile_with_age.birthday.day))
                self.assertEqual(age_user['age'], expected_age)
    
    def test_get_users_detail_error_handling(self):
        """Test error handling in get_users_detail."""
        # Create mock request
        request = self.factory.get('/')
        
        # Mock DashboardFilters to raise an exception
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filters.side_effect = Exception("Test error")
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Test error')
    
    def test_get_users_detail_with_no_user_email(self):
        """Test getting detailed user data when user has no email."""
        # Create a profile with no user email
        profile_no_email = Profile.objects.create(
            okuser=None,  # No user
            first_name='No',
            last_name='Email',
            gender='m',
            verified=True,
            member=True
        )
        
        # Test request
        request = self.factory.get('/?page=1')
        
        # Mock DashboardFilters
        with patch('dashboard.services.user_service.DashboardFilters') as mock_filters:
            mock_filter_instance = Mock()
            mock_filter_instance.apply_filters_to_queryset.return_value = Profile.objects.all()
            mock_filters.return_value = mock_filter_instance
            
            # Call the method
            result = self.user_service.get_users_detail(request)
            
            # Assertions
            self.assertTrue(result['success'])
            users = result['data']['users']
            
            # Find the user with no email
            no_email_user = next(
                (user for user in users if user['name'] == 'No Email'),
                None
            )
            
            if no_email_user:
                self.assertEqual(no_email_user['email'], '')
    
    def test_init_with_request(self):
        """Test UserService initialization with request."""
        # Create a mock request
        request = self.factory.get('/')
        
        # Initialize UserService with request
        user_service_with_request = UserService(request)
        
        # Assertions
        self.assertEqual(user_service_with_request.request, request)
        
        # Initialize UserService without request
        user_service_without_request = UserService()
        
        # Assertions
        self.assertIsNone(user_service_without_request.request)