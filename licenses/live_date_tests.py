"""Suggested broadcast date and time in the user's license form."""

from datetime import datetime
from django.urls import reverse
from django.utils import timezone
from licenses.forms import CreateLicenseForm
from licenses.models import default_category
import pytest


def _data(**extra):
    data = {
        'title': 'Stadtrat live (Demo)',
        'description': 'Sitzung',
        'category': default_category().pk,
        'duration': '01:30:00',
        'repetitions_allowed': '1',
        'store_in_ok_media_library': '1',
        'media_authority_exchange_allowed': '1',
        'media_authority_exchange_allowed_other_states': '1',
        'youth_protection_necessary': '0',
        'youth_protection_category': 'none',
        'suggested_date_0': '2026-11-23',
        'suggested_date_1': '',
    }
    data.update(extra)
    return data


@pytest.mark.django_db
def test_the_broadcast_time_is_kept():
    form = CreateLicenseForm(data=_data(suggested_date_1='18:30'))
    assert form.is_valid(), form.errors
    assert timezone.localtime(form.cleaned_data['suggested_date']) == timezone.make_aware(
        datetime(2026, 11, 23, 18, 30))


@pytest.mark.django_db
def test_without_live_the_time_may_stay_empty():
    form = CreateLicenseForm(data=_data())
    assert form.is_valid(), form.errors
    assert timezone.localtime(form.cleaned_data['suggested_date']) == timezone.make_aware(
        datetime(2026, 11, 23, 0, 0))

    form = CreateLicenseForm(data=_data(suggested_date_0=''))
    assert form.is_valid(), form.errors
    assert form.cleaned_data['suggested_date'] is None


@pytest.mark.django_db
@pytest.mark.parametrize('day, moment', [('2026-11-23', ''), ('', '18:30'), ('', '')])
def test_live_needs_date_and_time(day, moment):
    form = CreateLicenseForm(data=_data(is_live='on', suggested_date_0=day, suggested_date_1=moment))
    assert not form.is_valid()
    assert 'suggested_date' in form.errors


@pytest.mark.django_db
def test_live_with_date_and_time_is_saved_with_the_time():
    form = CreateLicenseForm(data=_data(is_live='on', suggested_date_1='18:30'))
    assert form.is_valid(), form.errors
    assert timezone.localtime(form.cleaned_data['suggested_date']).time().strftime('%H:%M') == '18:30'


@pytest.mark.django_db
def test_create_page_reports_errors_as_json_instead_of_reloading(client, user):
    client.force_login(user)
    response = client.post(
        reverse('licenses:create'), _data(is_live='on'),
        HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert response.status_code == 400
    body = response.json()
    assert body['success'] is False
    assert 'suggested_date' in body['fields']
    assert body['error']


@pytest.mark.django_db
def test_editing_shows_the_stored_time_so_it_survives_the_next_save(license):
    license.suggested_date = timezone.make_aware(datetime(2026, 11, 23, 18, 30))
    license.save()
    html = str(CreateLicenseForm(instance=license)['suggested_date'])
    assert 'value="2026-11-23"' in html
    assert 'value="18:30"' in html
