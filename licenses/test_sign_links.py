"""QR signing: configurable lifetime and long links for one license."""

from datetime import timedelta
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from licenses.models import LicensesConfig
from licenses.models import SigningSession
from licenses.models import SigningSessionStatus
from licenses.services import signing
import pytest


SVG = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1 L2 2"/></svg>'
PAYLOAD = {
    'signature_svg': SVG,
    'signature_points': '[{"points": [{"x": 1, "y": 1, "time": 1, "pressure": 0.3}]}]',
    'signature_metadata': '{"source": "phone"}',
    'signature_method': 'qr_phone',
}


@pytest.fixture
def staff_client(client, django_user_model):
    staff = django_user_model.objects.create_superuser(
        email='staff.mustermann@example.com', password='x')
    client.force_login(staff)
    return client


def _create_url(license_obj):
    return reverse('admin:licenses_license_create_sign_link', args=[license_obj.pk])


def _minutes(session):
    return round((session.expires_at - session.created_at).total_seconds() / 60)


@pytest.mark.django_db
def test__licenses__sign_session__uses_configured_minutes(client, user, license):
    config = LicensesConfig.get_config()
    config.sign_session_minutes = 30
    config.save()
    client.force_login(user)

    token = client.post(
        reverse('licenses:create_sign_session', kwargs={'pk': license.pk})).json()['token']
    pre_token = client.post(reverse('licenses:create_prelicense_sign_session')).json()['token']

    assert _minutes(SigningSession.objects.get(token=token)) == 30
    assert _minutes(SigningSession.objects.get(token=pre_token)) == 30


@pytest.mark.django_db
def test__licenses__sign_session__default_is_ten_minutes(client, user, license):
    client.force_login(user)
    token = client.post(reverse('licenses:create_prelicense_sign_session')).json()['token']
    assert _minutes(SigningSession.objects.get(token=token)) == 10


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def test__licenses__admin_sign_link__long_link_mailed_and_signed_later(
        staff_client, client, license):
    response = staff_client.post(_create_url(license), {'days': '3', 'send_email': '1'})

    data = response.json()
    assert data['success'] is True
    assert data['emailed_to'] == license.profile.okuser.email
    session = SigningSession.objects.get(token=data['token'])
    assert session.license == license
    assert session.expires_at - timezone.now() > timedelta(days=2, hours=23)
    assert len(mail.outbox) == 1
    assert data['sign_url'] in mail.outbox[0].body
    assert str(license.number) in mail.outbox[0].subject

    # Two days later the signer opens the link; no staff page is open.
    SigningSession.objects.filter(pk=session.pk).update(
        created_at=timezone.now() - timedelta(days=2))
    submit = client.post(
        reverse('licenses:sign_session_submit', kwargs={'token': session.token}), data=PAYLOAD)
    assert submit.status_code == 200
    license.refresh_from_db()
    assert license.signature_svg == SVG
    assert license.signature_method == 'qr_phone'


@pytest.mark.django_db
def test__licenses__admin_sign_link__only_offered_lifetimes(staff_client, license):
    response = staff_client.post(_create_url(license), {'days': '30'})
    assert response.status_code == 400
    assert not SigningSession.objects.filter(license=license).exists()


@pytest.mark.django_db
def test__licenses__admin_sign_link__refused_for_confirmed_license(staff_client, license):
    license.confirmed = True
    license.save()
    response = staff_client.post(_create_url(license), {'days': '1'})
    assert response.status_code == 400


@pytest.mark.django_db
def test__licenses__admin_sign_link__not_for_regular_users(client, user, license):
    client.force_login(user)
    response = client.post(_create_url(license), {'days': '3'})
    assert response.status_code in (302, 403)
    assert not SigningSession.objects.filter(license=license).exists()


@pytest.mark.django_db
def test__licenses__admin_sign_link__revoked_link_cannot_be_signed(staff_client, client, license):
    token = staff_client.post(_create_url(license), {'days': '1'}).json()['token']

    revoke = staff_client.post(reverse(
        'admin:licenses_license_revoke_sign_link', args=[license.pk, token]))
    assert revoke.json()['success'] is True

    submit = client.post(
        reverse('licenses:sign_session_submit', kwargs={'token': token}), data=PAYLOAD)
    assert submit.status_code == 400
    assert SigningSession.objects.get(token=token).status == SigningSessionStatus.CANCELLED


@pytest.mark.django_db
def test__licenses__sign_link__confirmed_meanwhile_is_refused(staff_client, client, license):
    token = staff_client.post(_create_url(license), {'days': '3'}).json()['token']
    license.confirmed = True
    license.save()

    submit = client.post(
        reverse('licenses:sign_session_submit', kwargs={'token': token}), data=PAYLOAD)

    assert submit.status_code == 400
    license.refresh_from_db()
    assert not license.signature_svg


@pytest.mark.django_db
def test__licenses__admin_change_page__lists_open_links(staff_client, license):
    session = signing.create_long_link(license, None, 3)
    response = staff_client.get(reverse('admin:licenses_license_change', args=[license.pk]))
    assert response.status_code == 200
    assert session.token in response.content.decode()


@pytest.mark.django_db
def test__licenses__cleanup__keeps_open_long_link(license):
    session = signing.create_long_link(license, None, 7)
    old_done = signing.create_session(None, license)
    SigningSession.objects.filter(pk__in=[session.pk, old_done.pk]).update(
        created_at=timezone.now() - timedelta(days=8))
    SigningSession.objects.filter(pk=old_done.pk).update(
        status=SigningSessionStatus.SIGNED)
    # Pretend the long link was made 8 days ago and still runs a day.
    SigningSession.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() + timedelta(days=1))

    call_command('cleanup_signing_sessions')

    assert SigningSession.objects.filter(pk=session.pk).exists()
    assert not SigningSession.objects.filter(pk=old_done.pk).exists()
