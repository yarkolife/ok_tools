"""Object-level authorization for the rental DRF endpoints.

The permission classes only assert that somebody is logged in, so the ViewSets
carry the per-object rules. These tests pin that behaviour down: without them a
regression would silently re-open every rental request to every account.
"""

import json

import pytest
from django.urls import reverse
from django.utils import timezone

from ok_tools.testing import create_user
from rental.models import RentalRequest


def _create_user(email, is_staff=False):
    user_dict = {
        'email': email,
        'first_name': 'Api',
        'last_name': 'Tester',
        'gender': 'm',
        'phone_number': None,
        'mobile_number': None,
        'birthday': '01.01.1990',
        'street': 'main street',
        'house_number': '1',
        'zipcode': '12345',
        'city': 'example-city',
    }
    return create_user(user_dict, is_staff=is_staff)


def _create_rental_request(user, project_name='Api test rental'):
    return RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name=project_name,
        purpose='Testing object level authorization',
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=1),
    )


def _results(response):
    payload = response.json()
    return payload['results'] if isinstance(payload, dict) else payload


@pytest.mark.django_db
def test__rental__RentalRequestViewSet__list_hides_foreign_requests(client):
    """The list endpoint must not leak other people's rentals."""
    owner = _create_user('api-owner@example.com')
    other = _create_user('api-other@example.com')
    own = _create_rental_request(owner, 'Own rental')
    _create_rental_request(other, 'Foreign rental')
    client.force_login(owner)

    response = client.get(reverse('rental:rental-request-list'))

    assert response.status_code == 200
    ids = [item['id'] for item in _results(response)]
    assert ids == [own.id]


@pytest.mark.django_db
def test__rental__RentalRequestViewSet__detail_of_foreign_request_is_404(client):
    """Guessing an id must not expose a foreign rental request."""
    owner = _create_user('api-detail-owner@example.com')
    intruder = _create_user('api-detail-intruder@example.com')
    foreign = _create_rental_request(owner)
    client.force_login(intruder)

    url = reverse('rental:rental-request-detail', kwargs={'pk': foreign.pk})

    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    foreign.refresh_from_db()
    assert foreign.pk is not None


@pytest.mark.django_db
def test__rental__RentalRequestViewSet__staff_sees_every_request(client):
    """Staff keep full visibility - the filter only narrows normal users."""
    owner = _create_user('api-staff-owner@example.com')
    staff = _create_user('api-staff@example.com', is_staff=True)
    _create_rental_request(owner, 'Borrower rental')
    client.force_login(staff)

    response = client.get(reverse('rental:rental-request-list'))

    assert response.status_code == 200
    assert len(_results(response)) == 1


@pytest.mark.django_db
def test__rental__RentalRequestSerializer__status_is_not_writable(client):
    """A borrower must not promote their own reservation to "issued".

    Status transitions belong to the workflow endpoints, which also write the
    matching RentalTransaction rows.
    """
    owner = _create_user('api-status@example.com')
    rental_request = _create_rental_request(owner)
    original_status = rental_request.status
    client.force_login(owner)

    url = reverse('rental:rental-request-detail', kwargs={'pk': rental_request.pk})
    response = client.patch(
        url,
        data=json.dumps({'status': 'issued'}),
        content_type='application/json',
    )

    assert response.status_code == 200
    rental_request.refresh_from_db()
    assert rental_request.status == original_status


@pytest.mark.django_db
def test__rental__RentalRequestViewSet__owner_cannot_be_reassigned(client):
    """Handing your own rental over to another account must not stick."""
    owner = _create_user('api-reassign-owner@example.com')
    victim = _create_user('api-reassign-victim@example.com')
    rental_request = _create_rental_request(owner)
    client.force_login(owner)

    url = reverse('rental:rental-request-detail', kwargs={'pk': rental_request.pk})
    response = client.patch(
        url,
        data=json.dumps({'user': victim.id}),
        content_type='application/json',
    )

    assert response.status_code == 200
    rental_request.refresh_from_db()
    assert rental_request.user_id == owner.id
