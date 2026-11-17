"""What a borrower sees of their own rentals in the account."""

from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rental.models import RentalRequest
from rental.user_rentals import user_rental_counts
from rental.user_rentals import user_rentals
import pytest


def _rental(user, status, *, rental_type='equipment', end_in_days=2):
    now = timezone.now()
    return RentalRequest.objects.create(
        user=user, created_by=user, project_name=f'{status} {rental_type}', purpose='x',
        requested_start_date=now + timedelta(days=end_in_days - 1),
        requested_end_date=now + timedelta(days=end_in_days),
        rental_type=rental_type, status=status)


@pytest.fixture
def borrower(django_user_model):
    return django_user_model.objects.create_user(email='borrower@example.org', password='pwd')


@pytest.mark.django_db
def test_groups_match_what_the_borrower_expects(borrower, django_user_model):
    waiting = _rental(borrower, 'draft')
    picked_up = _rental(borrower, 'issued')
    returned = _rental(borrower, 'returned', end_in_days=-3)
    closed = _rental(borrower, 'closed', end_in_days=-3)
    late = _rental(borrower, 'issued', end_in_days=-1)
    room_over = _rental(borrower, 'reserved', rental_type='room', end_in_days=-0.01)
    denied = _rental(borrower, 'cancelled', end_in_days=-5)
    _rental(borrower, 'cancelled', end_in_days=-40)  # too long ago
    other = django_user_model.objects.create_user(email='other@example.org', password='pwd')
    _rental(other, 'issued')

    def ids(group):
        return set(user_rentals(borrower, group).values_list('id', flat=True))

    assert ids('active') == {waiting.id, picked_up.id}
    assert ids('returned') == {returned.id, closed.id}
    # A room booking ends by itself; it is never "overdue" for the borrower.
    assert ids('overdue') == {late.id}
    assert room_over.id not in set().union(*(ids(g) for g in ('active', 'returned', 'overdue')))
    assert ids('cancelled') == {denied.id}
    assert user_rental_counts(borrower) == {
        'active_rentals': 2, 'returned_rentals': 2, 'overdue_rentals': 1, 'cancelled_rentals': 1}


@pytest.mark.django_db
def test_api_gives_the_borrowers_status_words_and_a_link(client, borrower):
    waiting = _rental(borrower, 'draft')
    _rental(borrower, 'cancelled', end_in_days=-1)
    client.force_login(borrower)

    active = client.get(reverse('rental:api_user_rental_details'), {'type': 'active'}).json()
    cancelled = client.get(reverse('rental:api_user_rental_details'), {'type': 'cancelled'}).json()

    [row] = active['rentals']
    assert row['id'] == waiting.id
    assert row['status_display'] == 'Waiting for approval'
    assert row['detail_url'] == reverse('rental:user_rental_detail', args=[waiting.id])
    assert [r['status'] for r in cancelled['rentals']] == ['cancelled']
    assert client.get(reverse('rental:api_user_rental_details'), {'type': 'nope'}).status_code == 400


@pytest.mark.django_db
def test_booking_page_is_three_steps_with_a_clear_send_button(client, borrower, settings):
    settings.RENTAL_ENABLED = True
    client.force_login(borrower)
    page = client.get(reverse('rental_dashboard')).content.decode()

    for step in ('bookingStep1', 'bookingStep2', 'bookingStep3', 'pendingBookingBar',
                 'notSentNotice', 'addRoomAndSendBtn', 'data-mirror="project_name"'):
        assert step in page
    # The fields the script reads keep their names.
    for name in ('name="project_name"', 'name="purpose"', 'name="start_date"', 'name="end_date"'):
        assert page.count(name) == 1
