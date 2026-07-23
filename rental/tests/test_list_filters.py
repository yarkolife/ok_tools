"""Tests for the rental dashboard (RentalListView) filters.

Covers the room/inventory content filter and the user-category filter, whose
categories mirror ``RentalConfig.get_organizations_for``.
"""

from datetime import timedelta

from django.test import RequestFactory
from django.test import TestCase
from django.utils import timezone
from inventory.models import Category
from inventory.models import InventoryItem
from inventory.models import Location
from registration.models import OKUser
from registration.models import Profile
from rental.models import RentalItem
from rental.models import RentalRequest
from rental.models import Room
from rental.models import RoomRental
from rental.views import RentalListView


class RentalListFilterTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.staff = OKUser.objects.create_user(
            email='staff@example.com', password='pw', is_staff=True)

        self.location = Location.objects.create(name='Room')
        self.category = Category.objects.create(name='Cat')
        self.item = InventoryItem.objects.create(
            inventory_number='OK-F1', quantity=1, status='in_stock',
            location=self.location, category=self.category)
        self.room = Room.objects.create(name='Studio', capacity=4, is_active=True)

    def _user(self, email, *, is_staff=False, member=False, rental_only=False,
              with_profile=True):
        user = OKUser.objects.create_user(email=email, password='pw',
                                          is_staff=is_staff)
        if with_profile:
            Profile.objects.create(okuser=user, first_name='F', last_name='L',
                                   member=member, rental_only=rental_only)
        return user

    def _rental(self, user, *, with_item=False, with_room=False):
        now = timezone.now()
        rr = RentalRequest.objects.create(
            user=user, created_by=self.staff, project_name='P', purpose='x',
            requested_start_date=now, requested_end_date=now + timedelta(days=1),
            status='reserved')
        if with_item:
            RentalItem.objects.create(
                rental_request=rr, inventory_item=self.item,
                quantity_requested=1)
        if with_room:
            RoomRental.objects.create(
                rental_request=rr, room=self.room, people_count=1,
                requested_start_date=now,
                requested_end_date=now + timedelta(days=1))
        return rr

    def _count(self, **params):
        request = self.factory.get('/rental/admin/', params)
        request.user = self.staff
        view = RentalListView()
        view.request = request
        view.kwargs = {}
        view.args = ()
        return view.get_queryset().count()

    def test_user_category_filter_partitions_all_rentals(self):
        self._rental(self._user('u@x.com'))                          # user
        self._rental(self._user('m@x.com', member=True))             # member
        self._rental(self._user('r@x.com', rental_only=True))        # rental_only
        self._rental(self._user('e@x.com', is_staff=True))           # employee
        self._rental(self._user('noprof@x.com', with_profile=False))  # user

        self.assertEqual(self._count(), 5)
        self.assertEqual(self._count(user_kind='user'), 2)
        self.assertEqual(self._count(user_kind='member'), 1)
        self.assertEqual(self._count(user_kind='rental_only'), 1)
        self.assertEqual(self._count(user_kind='employee'), 1)
        # The four categories must partition the whole set.
        total = sum(self._count(user_kind=k)
                    for k in ('user', 'member', 'rental_only', 'employee'))
        self.assertEqual(total, self._count())

    def test_content_filter_rooms_vs_inventory(self):
        u = self._user('c@x.com')
        self._rental(u, with_item=True)
        self._rental(u, with_room=True)
        self._rental(u, with_item=True, with_room=True)

        self.assertEqual(self._count(), 3)
        self.assertEqual(self._count(kind='inventory'), 2)
        self.assertEqual(self._count(kind='rooms'), 2)

    def test_filters_combine(self):
        self._rental(self._user('a@x.com', member=True), with_room=True)
        self._rental(self._user('b@x.com', is_staff=True), with_room=True)
        self._rental(self._user('c@x.com', member=True), with_item=True)

        self.assertEqual(self._count(user_kind='member', kind='rooms'), 1)

    def test_no_duplicate_rows_with_multiple_items(self):
        item2 = InventoryItem.objects.create(
            inventory_number='OK-F2', quantity=1, status='in_stock',
            location=self.location, category=self.category)
        rr = self._rental(self._user('d@x.com'), with_item=True)
        RentalItem.objects.create(
            rental_request=rr, inventory_item=item2, quantity_requested=1)
        # Two items on one rental must still count the rental once.
        self.assertEqual(self._count(kind='inventory'), 1)
