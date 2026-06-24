import json

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from ok_tools.testing import create_user
from rental.models import RentalRequest
from rental.models import RentalSigningSession
from rental.models import RentalSigningSessionStatus


@pytest.fixture(scope='session', autouse=True)
def _ensure_signature_columns(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            existing = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    'rental_rentalrequest',
                )
            }
            if 'signature' not in existing:
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_svg text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_points text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_metadata text NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_method varchar(32) NULL"
                )
                cursor.execute(
                    "ALTER TABLE rental_rentalrequest "
                    "ADD COLUMN signature_signed_at datetime NULL"
                )


def _create_rental_user(email='signature-borrower@example.com'):
    user_dict = {
        'email': email,
        'first_name': 'Signature',
        'last_name': 'Borrower',
        'gender': 'm',
        'phone_number': None,
        'mobile_number': None,
        'birthday': '01.01.1990',
        'street': 'main street',
        'house_number': '1',
        'zipcode': '12345',
        'city': 'example-city',
    }
    return create_user(user_dict, is_staff=True)


def _create_rental_request(user):
    return RentalRequest.objects.create(
        user=user,
        created_by=user,
        project_name='Signature test rental',
        purpose='Testing mobile signature synchronization',
        requested_start_date=timezone.now(),
        requested_end_date=timezone.now() + timezone.timedelta(hours=1),
    )


@pytest.mark.django_db
def test__rental__SigningSession__create_submit_and_status(client):
    user = _create_rental_user()
    rental_request = _create_rental_request(user)
    client.force_login(user)

    create_url = reverse('rental:create_sign_session', kwargs={'pk': rental_request.pk})
    create_response = client.post(create_url)
    assert create_response.status_code == 200
    token = create_response.json()['token']

    signature_points = [
        {
            'points': [
                {'x': 1, 'y': 1, 'time': 1, 'pressure': 0.3},
                {'x': 3, 'y': 3, 'time': 2, 'pressure': 0.8},
            ]
        }
    ]
    submit_url = reverse('rental:sign_session_submit', kwargs={'token': token})
    submit_response = client.post(submit_url, data={
        'signature_svg': '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1 L3 3"/></svg>',
        'signature_points': json.dumps(signature_points),
        'signature_metadata': json.dumps({'source': 'phone'}),
        'signature_method': 'qr_phone',
    })
    assert submit_response.status_code == 200
    assert submit_response.json()['success'] is True

    session = RentalSigningSession.objects.get(token=token)
    assert session.status == RentalSigningSessionStatus.SIGNED
    assert session.signed_at is not None

    status_url = reverse('rental:sign_session_status', kwargs={'token': token})
    status_response = client.get(status_url)
    assert status_response.status_code == 200
    assert status_response.json()['status'] == RentalSigningSessionStatus.SIGNED

    rental_request.refresh_from_db()
    assert isinstance(rental_request.signature_points, list)
    assert rental_request.signature_method == 'qr_phone'
    assert rental_request.signature_signed_at is not None


@pytest.mark.django_db
def test__rental__SigningSessionStatusView__consume_returns_payload_before_delete(client):
    user = _create_rental_user('signature-consume@example.com')
    rental_request = _create_rental_request(user)
    client.force_login(user)

    create_url = reverse('rental:create_sign_session', kwargs={'pk': rental_request.pk})
    token = client.post(create_url).json()['token']
    signature_points = [
        {
            'points': [
                {'x': 5, 'y': 7, 'time': 11, 'pressure': 0.4},
                {'x': 8, 'y': 13, 'time': 12, 'pressure': 0.7},
            ]
        }
    ]
    signature_metadata = {'source': 'phone', 'screen': 'mobile'}
    signature_svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M5 7 L8 13"/></svg>'
    submit_url = reverse('rental:sign_session_submit', kwargs={'token': token})
    submit_response = client.post(submit_url, data={
        'signature_svg': signature_svg,
        'signature_points': json.dumps(signature_points),
        'signature_metadata': json.dumps(signature_metadata),
        'signature_method': 'qr_phone',
    })
    assert submit_response.status_code == 200

    status_url = reverse('rental:sign_session_status', kwargs={'token': token})
    consume_response = client.get(f'{status_url}?consume=1')

    assert consume_response.status_code == 200
    data = consume_response.json()
    assert data['status'] == RentalSigningSessionStatus.SIGNED
    assert data['signature_svg'] == signature_svg
    assert data['signature_points'] == signature_points
    assert data['signature_metadata'] == signature_metadata
    assert data['signature_method'] == 'qr_phone'
    assert data['signed_at'] is not None
    assert RentalSigningSession.objects.filter(token=token).exists() is False
