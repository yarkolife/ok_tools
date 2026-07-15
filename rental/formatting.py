"""Shared display helpers for rental periods."""

from django.utils import timezone


def format_booked_period(start_at, end_at):
    """
    Return a compact label for a booked period, in the viewer's timezone.

    Args:
        start_at: Aware datetime the booking starts at, or None
        end_at: Aware datetime the booking ends at, or None

    Returns:
        str: e.g. "16.07 12:00-16:00", "16.07 12:00 - 18.07 15:00", or ''
    """
    if not start_at or not end_at:
        return ''
    # Stored datetimes are UTC; the label has to read in local time.
    start_local = timezone.localtime(start_at)
    end_local = timezone.localtime(end_at)
    if start_local.date() == end_local.date():
        return f'{start_local:%d.%m %H:%M}–{end_local:%H:%M}'
    return f'{start_local:%d.%m %H:%M} – {end_local:%d.%m %H:%M}'
