"""A repeated submit of the same booking must not create a second request."""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rental.models import RentalRequest
from rental.models import Room
from rental.services import rental_service as service_module
from rental.services.rental_service import RentalService
from unittest.mock import patch
import pytest


def _weekday(offset=1):
    day = timezone.localdate() + timedelta(days=offset)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _data(room, day, **extra):
    data = {
        'project_name': 'Adrian Schnitt',
        'purpose': 'mit Basti',
        'start_date': f'{day.isoformat()}T12:00',
        'end_date': f'{day.isoformat()}T15:00',
        'action': 'draft',
        'items': [],
        'rooms': [{'room_id': room.id, 'people_count': 1}],
        'rental_type': 'room',
    }
    data.update(extra)
    return data


@pytest.fixture
def setup(db):
    user = get_user_model().objects.create_user(email='prakti@example.com', password='x')
    room = Room.objects.create(name='Schnittraum', capacity=2, is_active=True)
    return user, room


@pytest.fixture
def mails():
    with patch('rental.config.get_rental_user_request_requires_approval', return_value=True), \
            patch('rental.email_approval.send_admin_approval_email') as admin, \
            patch('rental.email_approval.send_user_pending_email'):
        yield admin


def test_repeated_submit_returns_the_first_request(setup, mails):
    user, room = setup
    day = _weekday()

    results = [
        RentalService.create_rental_request(_data(room, day), user, user, is_user_request=True)
        for _ in range(5)
    ]

    assert all(r['success'] for r in results)
    assert RentalRequest.objects.count() == 1
    assert {r['rental_id'] for r in results} == {RentalRequest.objects.get().id}
    assert [r.get('duplicate', False) for r in results] == [False, True, True, True, True]
    assert mails.call_count == 1


def test_different_period_or_room_is_a_new_request(setup, mails):
    user, room = setup
    day = _weekday()
    other_room = Room.objects.create(name='Studio', capacity=5, is_active=True)

    RentalService.create_rental_request(_data(room, day), user, user, is_user_request=True)
    RentalService.create_rental_request(
        _data(room, day, end_date=f'{day.isoformat()}T16:00'), user, user, is_user_request=True)
    RentalService.create_rental_request(
        _data(other_room, day, rooms=[{'room_id': other_room.id}]), user, user, is_user_request=True)

    assert RentalRequest.objects.count() == 3


def test_same_request_later_is_a_new_request(setup, mails):
    user, room = setup
    day = _weekday()
    first = RentalService.create_rental_request(_data(room, day), user, user, is_user_request=True)
    RentalRequest.objects.filter(id=first['rental_id']).update(
        created_at=timezone.now() - timedelta(seconds=service_module.DUPLICATE_WINDOW_SECONDS + 1))

    second = RentalService.create_rental_request(_data(room, day), user, user, is_user_request=True)

    assert second['rental_id'] != first['rental_id']
    assert 'duplicate' not in second
