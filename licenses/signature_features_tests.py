from django.urls import reverse
from licenses.models import SigningSession
from licenses.models import SigningSessionStatus
import json
import pytest


@pytest.mark.django_db
def test__licenses__License__has_any_signature_with_svg_only(license):
    license.signature = None
    license.signature_svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    license.signature_points = None
    license.save(update_fields=['signature', 'signature_svg', 'signature_points'])

    assert license.has_any_signature() is True


@pytest.mark.django_db
def test__licenses__SaveSignatureView__stores_svg_points_and_legacy(client, user, license):
    client.force_login(user)
    url = reverse('licenses:save_signature', kwargs={'pk': license.pk})
    payload = {
        'signature_svg': '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1 L2 2"/></svg>',
        'signature_points': [
            {
                'points': [
                    {'x': 1, 'y': 1, 'time': 1, 'pressure': 0.5},
                    {'x': 2, 'y': 2, 'time': 2, 'pressure': 0.6},
                ]
            }
        ],
        'signature_metadata': {'device': 'pytest'},
        'signature_method': 'mouse',
        'legacy_signature': 'data:image/png;base64,ZmFrZQ==',
    }

    response = client.post(
        url,
        data=json.dumps(payload),
        content_type='application/json',
    )

    assert response.status_code == 200
    license.refresh_from_db()
    assert license.signature_svg == payload['signature_svg']
    assert license.signature_points == payload['signature_points']
    assert license.signature_metadata == payload['signature_metadata']
    assert license.signature_method == 'mouse'
    assert license.signature == payload['legacy_signature']
    assert license.signature_signed_at is not None


@pytest.mark.django_db
def test__licenses__SaveSignatureView__rejects_unsafe_svg(client, user, license):
    client.force_login(user)
    url = reverse('licenses:save_signature', kwargs={'pk': license.pk})
    payload = {
        'signature_svg': '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        'legacy_signature': 'data:image/png;base64,ZmFrZQ==',
    }

    response = client.post(
        url,
        data=json.dumps(payload),
        content_type='application/json',
    )

    assert response.status_code == 400
    assert response.json()['success'] is False


@pytest.mark.django_db
def test__licenses__SigningSession__create_submit_and_status(client, user, license):
    client.force_login(user)

    create_url = reverse('licenses:create_sign_session', kwargs={'pk': license.pk})
    create_response = client.post(create_url)
    assert create_response.status_code == 200

    create_data = create_response.json()
    token = create_data['token']
    assert create_data['success'] is True

    submit_url = reverse('licenses:sign_session_submit', kwargs={'token': token})
    submit_payload = {
        'signature_svg': '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1 L3 3"/></svg>',
        'signature_points': json.dumps([
            {
                'points': [
                    {'x': 1, 'y': 1, 'time': 1, 'pressure': 0.3},
                    {'x': 3, 'y': 3, 'time': 2, 'pressure': 0.8},
                ]
            }
        ]),
        'signature_metadata': json.dumps({'source': 'phone'}),
        'signature_method': 'qr_phone',
        'legacy_signature': 'data:image/png;base64,ZmFrZQ==',
    }

    submit_response = client.post(submit_url, data=submit_payload)
    assert submit_response.status_code == 200
    assert submit_response.json()['success'] is True

    session = SigningSession.objects.get(token=token)
    assert session.status == SigningSessionStatus.SIGNED
    assert session.signed_at is not None

    status_url = reverse('licenses:sign_session_status', kwargs={'token': token})
    status_response = client.get(status_url)
    assert status_response.status_code == 200
    assert status_response.json()['status'] == SigningSessionStatus.SIGNED

    license.refresh_from_db()
    assert license.signature_svg == submit_payload['signature_svg']
    assert isinstance(license.signature_points, list)
    assert license.signature_method == 'qr_phone'


@pytest.mark.django_db
def test__licenses__PreLicenseSigningSession__create_submit_and_status(client, user):
    client.force_login(user)

    create_url = reverse('licenses:create_prelicense_sign_session')
    create_response = client.post(create_url)
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data['success'] is True
    token = create_data['token']

    submit_url = reverse('licenses:sign_session_submit', kwargs={'token': token})
    submit_payload = {
        'signature_svg': '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1 L3 3"/></svg>',
        'signature_points': json.dumps([
            {
                'points': [
                    {'x': 1, 'y': 1, 'time': 1, 'pressure': 0.3},
                    {'x': 3, 'y': 3, 'time': 2, 'pressure': 0.8},
                ]
            }
        ]),
        'signature_metadata': json.dumps({'source': 'phone'}),
        'signature_method': 'qr_phone',
    }

    submit_response = client.post(submit_url, data=submit_payload)
    assert submit_response.status_code == 200
    assert submit_response.json()['success'] is True

    session = SigningSession.objects.get(token=token)
    assert session.status == SigningSessionStatus.SIGNED
    assert session.license is None
    assert session.owner == user

    status_url = reverse('licenses:sign_session_status', kwargs={'token': token})
    status_response = client.get(status_url)
    assert status_response.status_code == 200
    assert status_response.json()['status'] == SigningSessionStatus.SIGNED


@pytest.mark.django_db
def test__austausch__license_has_pdf_supports_svg_without_legacy_signature(license):
    austausch_views = pytest.importorskip('austausch.views')

    license.signature = None
    license.signature_svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    license.signature_points = None
    license.save(update_fields=['signature', 'signature_svg', 'signature_points'])

    class DummyConfig:
        local_pdf_fallback_path = ''
        local_pdf_fallback_path_2 = ''

    assert austausch_views._license_has_pdf(license, DummyConfig()) is True
