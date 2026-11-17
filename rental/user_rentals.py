"""The borrower's own rentals, grouped the way the account pages show them.

One definition for the account start page, the booking page and its API,
so the numbers on the cards and the lists behind them always agree.
"""

from datetime import timedelta
from django.db.models import QuerySet
from django.utils import timezone


GROUPS = ('active', 'returned', 'overdue', 'cancelled')

# Cancelled or denied requests stay visible this long.
CANCELLED_VISIBLE_DAYS = 30


def user_rentals(user, group: str) -> QuerySet:
    """Rental requests of ``user`` in one of ``GROUPS``."""
    from .models import RentalRequest

    now = timezone.now()
    rentals = RentalRequest.objects.filter(user=user)
    if group == 'active':
        # Waiting for approval, reserved or picked up, and not over yet.
        return rentals.filter(
            status__in=['draft', 'reserved', 'issued'],
            requested_end_date__isnull=False,
            requested_end_date__gte=now,
        )
    if group == 'returned':
        # "closed" is a return that staff also closed; for the user it is returned.
        return rentals.filter(status__in=['returned', 'closed'])
    if group == 'overdue':
        # Room-only bookings end by themselves (expire_room_rentals), so they
        # are never overdue for the user.
        return rentals.filter(
            status__in=['reserved', 'issued'],
            requested_end_date__isnull=False,
            requested_end_date__lt=now,
        ).exclude(rental_type='room')
    if group == 'cancelled':
        return rentals.filter(
            status='cancelled',
            requested_end_date__gte=now - timedelta(days=CANCELLED_VISIBLE_DAYS),
        )
    raise ValueError(f'Unknown rental group: {group}')


def user_rental_counts(user) -> dict:
    """``{'active_rentals': n, 'returned_rentals': n, ...}`` for the templates."""
    return {f'{group}_rentals': user_rentals(user, group).count() for group in GROUPS}
