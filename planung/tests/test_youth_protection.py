"""Youth protection windows block daytime planning of rated material."""

from django.test import TestCase
from licenses.models import License
from licenses.models import YouthProtectionCategory
from licenses.models import YouthProtectionWindow
from planung.services.validation_service import PlanningValidationError
from planung.services.validation_service import check_youth_protection
from planung.services.validation_service import validate_day_plan_payload
from registration.models import OKUser
from registration.models import Profile
import datetime


def _window(category, start, end, enabled=True):
    window, _created = YouthProtectionWindow.objects.update_or_create(
        category=category,
        defaults={
            'start_time': start, 'end_time': end, 'enabled': enabled},
    )
    return window


class WindowMathTests(TestCase):
    """The window may wrap around midnight, and so may the item."""

    def setUp(self):
        self.window = YouthProtectionWindow(
            category=YouthProtectionCategory.FROM_16,
            start_time=datetime.time(22, 0),
            end_time=datetime.time(6, 0),
        )

    def test_item_inside_window(self):
        self.assertTrue(self.window.allows(22 * 3600, 3600))

    def test_item_starting_before_the_window(self):
        self.assertFalse(self.window.allows(21 * 3600 + 3540, 3600))

    def test_item_crossing_midnight_stays_inside(self):
        self.assertTrue(self.window.allows(23 * 3600 + 1800, 3600))

    def test_item_running_past_the_window_end(self):
        self.assertFalse(self.window.allows(5 * 3600 + 1800, 3600))

    def test_item_exactly_filling_the_window(self):
        self.assertTrue(self.window.allows(22 * 3600, 8 * 3600))
        self.assertFalse(self.window.allows(22 * 3600, 8 * 3600 + 1))

    def test_empty_window_means_the_whole_day(self):
        window = YouthProtectionWindow(
            category=YouthProtectionCategory.FROM_12,
            start_time=datetime.time(0, 0),
            end_time=datetime.time(0, 0),
        )
        self.assertEqual(window.length_seconds(), 86400)
        self.assertTrue(window.allows(12 * 3600, 3600))


class CheckYouthProtectionTests(TestCase):

    def setUp(self):
        user = OKUser.objects.create_user(
            email='yp@example.invalid', password='x')
        self.profile = Profile.objects.create(
            okuser=user, first_name='A', last_name='B',
            birthday=datetime.date(1990, 1, 1))
        _window(YouthProtectionCategory.FROM_16,
                datetime.time(22, 0), datetime.time(6, 0))

    def _license(self, number, category):
        return License.objects.create(
            number=number, profile=self.profile, title=f'L{number}',
            duration=datetime.timedelta(minutes=30),
            youth_protection_category=category,
            youth_protection_necessary=category != YouthProtectionCategory.NONE,
        )

    def test_rated_item_in_the_afternoon_is_rejected(self):
        self._license(9001, YouthProtectionCategory.FROM_16)
        errors = check_youth_protection(
            [{'number': 9001, 'start': '14:00', 'duration': 1800,
              'title': 'L9001'}])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['youth_protection']['allowed_from'], '22:00')
        self.assertEqual(
            errors[0]['youth_protection']['allowed_until'], '06:00')
        self.assertIn('22:00', errors[0]['message'])

    def test_rated_item_inside_the_window_passes(self):
        self._license(9002, YouthProtectionCategory.FROM_16)
        self.assertEqual(check_youth_protection(
            [{'number': 9002, 'start': '23:00', 'duration': 1800}]), [])

    def test_unrated_item_is_never_restricted(self):
        self._license(9003, YouthProtectionCategory.NONE)
        self.assertEqual(check_youth_protection(
            [{'number': 9003, 'start': '14:00', 'duration': 1800}]), [])

    def test_disabled_window_stops_enforcing(self):
        self._license(9004, YouthProtectionCategory.FROM_16)
        _window(YouthProtectionCategory.FROM_16,
                datetime.time(22, 0), datetime.time(6, 0), enabled=False)
        self.assertEqual(check_youth_protection(
            [{'number': 9004, 'start': '14:00', 'duration': 1800}]), [])

    def test_unknown_license_number_is_skipped(self):
        self.assertEqual(check_youth_protection(
            [{'number': 987654, 'start': '14:00', 'duration': 1800}]), [])

    def test_save_payload_is_refused(self):
        self._license(9005, YouthProtectionCategory.FROM_16)
        payload = {
            'date': '2026-08-20',
            'items': [{'number': 9005, 'start': '14:00', 'duration': 1800}],
        }
        with self.assertRaises(PlanningValidationError) as caught:
            validate_day_plan_payload(payload)
        self.assertTrue(any(
            'youth_protection' in error for error in caught.exception.errors))
