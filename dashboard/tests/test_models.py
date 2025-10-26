"""
Tests for Dashboard models.
"""
from datetime import date, datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from registration.models import OKUser, Profile, MediaAuthority
from licenses.models import License
from contributions.models import Contribution
from rental.models import RentalRequest
from dashboard.models import (
    UserJourneyStage, UserJourney, FunnelMetrics, AlertThreshold, AlertLog
)


class UserJourneyStageTest(TestCase):
    """Test cases for UserJourneyStage choices."""
    
    def test_user_journey_stage_choices(self):
        """Test that all expected user journey stage choices are available."""
        choices = UserJourneyStage.choices
        
        expected_stages = [
            ('registered', 'Registered'),
            ('verified', 'Verified'),
            ('rental_requested', 'Rental Requested'),
            ('rental_completed', 'Rental Completed'),
            ('license_created', 'License Created'),
            ('contribution_created', 'Contribution Created'),
            ('first_broadcast', 'First Broadcast'),
            ('multiple_broadcasts', 'Multiple Broadcasts')
        ]
        
        for expected_stage in expected_stages:
            # Account for localization - check if the key is present
            stage_keys = [choice[0] for choice in choices]
            for expected_stage in expected_stages:
                self.assertIn(expected_stage[0], stage_keys)


class UserJourneyModelTest(TestCase):
    """Test cases for UserJourney model."""
    
    def setUp(self):
        """Set up test data."""
        self.media_authority = MediaAuthority.objects.create(name='Test Authority')
        
        # Create a base user for shared test data
        self.base_user = OKUser.objects.create_user(
            email='base_user@example.com',
            password='testpass123'
        )
        self.base_profile = Profile.objects.create(
            okuser=self.base_user,
            first_name='Base',
            last_name='User',
            media_authority=self.media_authority
        )
        
        # Create related objects for testing using base user
        self.license = License.objects.create(
            profile=self.base_profile,
            title='Test License',
            confirmed=True
        )
        
        self.contribution = Contribution.objects.create(
            license=self.license,
            broadcast_date=timezone.now(),
            live=True
        )
        
        self.rental_request = RentalRequest.objects.create(
            user=self.base_user,
            created_by=self.base_user,
            project_name='Test Project',
            purpose='Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now() + timedelta(days=1),
        )
    
    def test_user_journey_creation(self):
        """Test creating a user journey stage."""
        # Create a unique user for this test
        unique_user = OKUser.objects.create_user(
            email='unique_user1@example.com',
            password='testpass123'
        )
        Profile.objects.create(
            okuser=unique_user,
            first_name='Unique',
            last_name='User 1',
            media_authority=self.media_authority
        )
        
        journey, created = UserJourney.objects.get_or_create(
            user=unique_user,
            stage=UserJourneyStage.REGISTERED,
            defaults={'achieved_at': timezone.now()}
        )
        
        self.assertEqual(journey.user, unique_user)
        self.assertEqual(journey.stage, UserJourneyStage.REGISTERED)
        self.assertIsNotNone(journey.achieved_at)
        self.assertEqual(
            str(journey),
            f"{unique_user.email} - {UserJourneyStage.REGISTERED.label}"
        )
    
    def test_user_journey_with_related_objects(self):
        """Test creating a user journey with related objects."""
        # Create a unique user for this test
        unique_user = OKUser.objects.create_user(
            email='unique_user2@example.com',
            password='testpass123'
        )
        unique_profile = Profile.objects.create(
            okuser=unique_user,
            first_name='Unique',
            last_name='User 2',
            media_authority=self.media_authority
        )
        
        # Create a unique license for this user
        unique_license = License.objects.create(
            profile=unique_profile,
            title='Unique Test License',
            confirmed=True
        )
        
        journey, created = UserJourney.objects.get_or_create(
            user=unique_user,
            stage=UserJourneyStage.LICENSE_CREATED,
            defaults={
                'license': unique_license,
                'metadata': {'source': 'web_form'}
            }
        )
        
        # Update the journey with our test data if it was created by signal
        if not created:
            journey.license = unique_license
            journey.metadata = {'source': 'web_form'}
            journey.save()
        
        self.assertEqual(journey.user, unique_user)
        self.assertEqual(journey.stage, UserJourneyStage.LICENSE_CREATED)
        self.assertEqual(journey.license, unique_license)
        self.assertEqual(journey.metadata, {'source': 'web_form'})
    
    def test_user_journey_with_rental_request(self):
        """Test creating a user journey with rental request."""
        # Create a unique user for this test
        unique_user = OKUser.objects.create_user(
            email='unique_user3@example.com',
            password='testpass123'
        )
        Profile.objects.create(
            okuser=unique_user,
            first_name='Unique',
            last_name='User 3',
            media_authority=self.media_authority
        )
        
        # Create a unique rental request for this user
        unique_rental_request = RentalRequest.objects.create(
            user=unique_user,
            created_by=unique_user,
            project_name='Unique Test Project',
            purpose='Unique Test Purpose',
            requested_start_date=timezone.now(),
            requested_end_date=timezone.now() + timedelta(days=1),
        )
        
        journey, created = UserJourney.objects.get_or_create(
            user=unique_user,
            stage=UserJourneyStage.RENTAL_REQUESTED,
            defaults={'rental_request': unique_rental_request}
        )
        
        self.assertEqual(journey.user, unique_user)
        self.assertEqual(journey.stage, UserJourneyStage.RENTAL_REQUESTED)
        self.assertEqual(journey.rental_request, unique_rental_request)
    
    def test_user_journey_with_contribution(self):
        """Test creating a user journey with contribution."""
        # Create a unique user for this test
        unique_user = OKUser.objects.create_user(
            email='unique_user4@example.com',
            password='testpass123'
        )
        unique_profile = Profile.objects.create(
            okuser=unique_user,
            first_name='Unique',
            last_name='User 4',
            media_authority=self.media_authority
        )
        
        # Create a unique contribution for this user
        unique_license = License.objects.create(
            profile=unique_profile,
            title='Unique Test License',
            confirmed=True
        )
        
        unique_contribution = Contribution.objects.create(
            license=unique_license,
            broadcast_date=timezone.now(),
            live=True
        )
        
        journey, created = UserJourney.objects.get_or_create(
            user=unique_user,
            stage=UserJourneyStage.CONTRIBUTION_CREATED,
            defaults={'contribution': unique_contribution}
        )
        
        self.assertEqual(journey.user, unique_user)
        self.assertEqual(journey.stage, UserJourneyStage.CONTRIBUTION_CREATED)
        self.assertEqual(journey.contribution, unique_contribution)
    
    def test_unique_constraint(self):
        """Test that a user can only have one instance of each stage."""
        # Create a unique user for this test
        unique_user = OKUser.objects.create_user(
            email='unique_user5@example.com',
            password='testpass123'
        )
        Profile.objects.create(
            okuser=unique_user,
            first_name='Unique',
            last_name='User 5',
            media_authority=self.media_authority
        )
        
        # Create first journey stage using get_or_create to handle signal-created records
        journey, created = UserJourney.objects.get_or_create(
            user=unique_user,
            stage=UserJourneyStage.REGISTERED
        )
        
        # Try to create the same stage again - should fail due to unique constraint
        with self.assertRaises(Exception):  # Django will raise an IntegrityError
            UserJourney.objects.create(
                user=unique_user,
                stage=UserJourneyStage.REGISTERED
            )


class FunnelMetricsModelTest(TestCase):
    """Test cases for FunnelMetrics model."""
    
    def test_funnel_metrics_creation(self):
        """Test creating funnel metrics."""
        today = date.today()
        metrics = FunnelMetrics.objects.create(
            date=today,
            total_registrations=100,
            verified_users=80,
            rental_requests=60,
            completed_rentals=50,
            licenses_created=40,
            contributions_created=30,
            first_broadcasts=20,
            multiple_broadcasts=10,
            verification_rate=80.0,
            rental_request_rate=75.0,
            rental_completion_rate=83.33,
            license_creation_rate=66.67,
            contribution_creation_rate=50.0,
            first_broadcast_rate=33.33,
            multiple_broadcast_rate=16.67
        )
        
        self.assertEqual(metrics.date, today)
        self.assertEqual(metrics.total_registrations, 100)
        self.assertEqual(metrics.verified_users, 80)
        self.assertEqual(metrics.rental_requests, 60)
        self.assertEqual(metrics.completed_rentals, 50)
        self.assertEqual(metrics.licenses_created, 40)
        self.assertEqual(metrics.contributions_created, 30)
        self.assertEqual(metrics.first_broadcasts, 20)
        self.assertEqual(metrics.multiple_broadcasts, 10)
        self.assertEqual(metrics.verification_rate, 80.0)
        self.assertEqual(metrics.rental_request_rate, 75.0)
        self.assertEqual(metrics.rental_completion_rate, 83.33)
        self.assertEqual(metrics.license_creation_rate, 66.67)
        self.assertEqual(metrics.contribution_creation_rate, 50.0)
        self.assertEqual(metrics.first_broadcast_rate, 33.33)
        self.assertEqual(metrics.multiple_broadcast_rate, 16.67)
        self.assertIsNotNone(metrics.created_at)
        self.assertIsNotNone(metrics.updated_at)
        self.assertEqual(str(metrics), f"Funnel Metrics - {today}")
    
    def test_unique_date_constraint(self):
        """Test that each date can only have one metrics record."""
        today = date.today()
        
        # Create first metrics record
        FunnelMetrics.objects.create(
            date=today,
            total_registrations=100
        )
        
        # Try to create another record for the same date - should fail due to unique constraint
        with self.assertRaises(Exception):  # Django will raise an IntegrityError
            FunnelMetrics.objects.create(
                date=today,
                total_registrations=150
            )
    
    def test_default_values(self):
        """Test default values for funnel metrics."""
        today = date.today()
        metrics = FunnelMetrics.objects.create(date=today)
        
        self.assertEqual(metrics.total_registrations, 0)
        self.assertEqual(metrics.verified_users, 0)
        self.assertEqual(metrics.rental_requests, 0)
        self.assertEqual(metrics.completed_rentals, 0)
        self.assertEqual(metrics.licenses_created, 0)
        self.assertEqual(metrics.contributions_created, 0)
        self.assertEqual(metrics.first_broadcasts, 0)
        self.assertEqual(metrics.multiple_broadcasts, 0)
        self.assertEqual(metrics.verification_rate, 0.0)
        self.assertEqual(metrics.rental_request_rate, 0.0)
        self.assertEqual(metrics.rental_completion_rate, 0.0)
        self.assertEqual(metrics.license_creation_rate, 0.0)
        self.assertEqual(metrics.contribution_creation_rate, 0.0)
        self.assertEqual(metrics.first_broadcast_rate, 0.0)
        self.assertEqual(metrics.multiple_broadcast_rate, 0.0)


class AlertThresholdModelTest(TestCase):
    """Test cases for AlertThreshold model."""
    
    def test_alert_threshold_creation(self):
        """Test creating an alert threshold."""
        threshold = AlertThreshold.objects.create(
            name='Verification Rate Drop',
            metric_type='conversion_rate',
            stage=UserJourneyStage.VERIFIED,
            threshold_value=75.0,
            comparison_operator='lt',
            is_active=True,
            notification_recipients=['admin@example.com', 'manager@example.com']
        )
        
        self.assertEqual(threshold.name, 'Verification Rate Drop')
        self.assertEqual(threshold.metric_type, 'conversion_rate')
        self.assertEqual(threshold.stage, UserJourneyStage.VERIFIED)
        self.assertEqual(threshold.threshold_value, 75.0)
        self.assertEqual(threshold.comparison_operator, 'lt')
        self.assertTrue(threshold.is_active)
        self.assertEqual(
            threshold.notification_recipients, 
            ['admin@example.com', 'manager@example.com']
        )
        self.assertIsNotNone(threshold.created_at)
        self.assertEqual(
            str(threshold), 
            f"{threshold.name} - {UserJourneyStage.VERIFIED.label}"
        )
    
    def test_metric_type_choices(self):
        """Test metric type choices."""
        threshold = AlertThreshold.objects.create(
            name='Test Threshold',
            metric_type='conversion_rate',
            stage=UserJourneyStage.REGISTERED,
            threshold_value=50.0,
            comparison_operator='gt'
        )
        
        # Test different metric types
        metric_types = ['conversion_rate', 'absolute_count', 'trend_change']
        for metric_type in metric_types:
            threshold.metric_type = metric_type
            threshold.save()
            self.assertEqual(threshold.metric_type, metric_type)
    
    def test_comparison_operator_choices(self):
        """Test comparison operator choices."""
        threshold = AlertThreshold.objects.create(
            name='Test Threshold',
            metric_type='absolute_count',
            stage=UserJourneyStage.LICENSE_CREATED,
            threshold_value=10.0,
            comparison_operator='gt'
        )
        
        # Test different comparison operators
        operators = ['lt', 'lte', 'gt', 'gte', 'eq']
        for operator in operators:
            threshold.comparison_operator = operator
            threshold.save()
            self.assertEqual(threshold.comparison_operator, operator)
    
    def test_alert_threshold_stage_choices(self):
        """Test that alert thresholds can use user journey stage choices."""
        threshold = AlertThreshold.objects.create(
            name='Test Threshold',
            metric_type='absolute_count',
            stage=UserJourneyStage.REGISTERED,
            threshold_value=100.0,
            comparison_operator='gt'
        )
        
        # Test different stages
        stages = [
            UserJourneyStage.REGISTERED,
            UserJourneyStage.VERIFIED,
            UserJourneyStage.LICENSE_CREATED,
            UserJourneyStage.CONTRIBUTION_CREATED
        ]
        for stage in stages:
            threshold.stage = stage
            threshold.save()
            self.assertEqual(threshold.stage, stage)


class AlertLogModelTest(TestCase):
    """Test cases for AlertLog model."""
    
    def setUp(self):
        """Set up test data."""
        self.threshold = AlertThreshold.objects.create(
            name='Test Threshold',
            metric_type='conversion_rate',
            stage=UserJourneyStage.VERIFIED,
            threshold_value=75.0,
            comparison_operator='lt'
        )
    
    def test_alert_log_creation(self):
        """Test creating an alert log."""
        alert_log = AlertLog.objects.create(
            threshold=self.threshold,
            current_value=70.0,
            threshold_value=75.0,
            message='Verification rate dropped below threshold'
        )
        
        self.assertEqual(alert_log.threshold, self.threshold)
        self.assertEqual(alert_log.current_value, 70.0)
        self.assertEqual(alert_log.threshold_value, 75.0)
        self.assertEqual(
            alert_log.message, 
            'Verification rate dropped below threshold'
        )
        self.assertFalse(alert_log.is_resolved)
        self.assertIsNone(alert_log.resolved_at)
        self.assertIsNotNone(alert_log.triggered_at)
        self.assertIn('Test Threshold', str(alert_log))
    
    def test_resolving_alert(self):
        """Test resolving an alert."""
        alert_log = AlertLog.objects.create(
            threshold=self.threshold,
            current_value=70.0,
            threshold_value=75.0,
            message='Verification rate dropped below threshold'
        )
        
        # Initially not resolved
        self.assertFalse(alert_log.is_resolved)
        self.assertIsNone(alert_log.resolved_at)
        
        # Resolve the alert
        alert_log.is_resolved = True
        alert_log.resolved_at = timezone.now()
        alert_log.save()
        
        # Check that it's now resolved
        self.assertTrue(alert_log.is_resolved)
        self.assertIsNotNone(alert_log.resolved_at)
    
    def test_alert_log_ordering(self):
        """Test that alert logs are ordered by triggered_at (most recent first)."""
        # Create multiple alerts at different times
        time1 = timezone.now() - timedelta(hours=3)
        time2 = timezone.now() - timedelta(hours=2)
        time3 = timezone.now() - timedelta(hours=1)
        
        alert1 = AlertLog.objects.create(
            threshold=self.threshold,
            current_value=70.0,
            threshold_value=75.0,
            message='First alert',
            triggered_at=time1
        )
        
        alert2 = AlertLog.objects.create(
            threshold=self.threshold,
            current_value=65.0,
            threshold_value=75.0,
            message='Second alert',
            triggered_at=time2
        )
        
        alert3 = AlertLog.objects.create(
            threshold=self.threshold,
            current_value=60.0,
            threshold_value=75.0,
            message='Third alert',
            triggered_at=time3
        )
        
        # Get all alerts ordered by the model's default ordering
        alerts = AlertLog.objects.all()
        
        # Should be in reverse chronological order (most recent first)
        self.assertEqual(alerts[0], alert3)
        self.assertEqual(alerts[1], alert2)
        self.assertEqual(alerts[2], alert1)