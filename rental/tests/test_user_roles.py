"""User classification shown on every rental screen."""

from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from registration.models import Profile
from rental.views import serialize_user


class SerializeUserRoleTests(TestCase):
    """Staff win, then the mutually exclusive profile flags, then plain user."""

    def _user(self, email, *, staff=False, member=False, rental_only=False):
        user = get_user_model().objects.create_user(email, password='x',
                                                    is_staff=staff)
        Profile.objects.create(
            okuser=user, first_name='A', last_name='B',
            birthday=date(1990, 1, 1), member=member, rental_only=rental_only)
        return user

    def test_staff_is_an_employee(self):
        data = serialize_user(self._user('e@example.invalid', staff=True))
        self.assertEqual(data['role_key'], 'employee')

    def test_member_profile(self):
        data = serialize_user(self._user('m@example.invalid', member=True))
        self.assertEqual(data['role_key'], 'member')

    def test_rental_only_profile_is_not_a_plain_user(self):
        data = serialize_user(
            self._user('r@example.invalid', rental_only=True))
        self.assertEqual(data['role_key'], 'rental_only')
        self.assertEqual(data['role'], 'Rental only')

    def test_plain_user(self):
        data = serialize_user(self._user('u@example.invalid'))
        self.assertEqual(data['role_key'], 'user')

    def test_staff_flag_wins_over_the_profile(self):
        data = serialize_user(
            self._user('s@example.invalid', staff=True, rental_only=True))
        self.assertEqual(data['role_key'], 'employee')

    def test_user_without_a_profile_stays_a_plain_user(self):
        user = get_user_model().objects.create_user(
            'noprofile@example.invalid', password='x')
        self.assertEqual(serialize_user(user)['role_key'], 'user')
