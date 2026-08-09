"""Links to the screens people actually work in.

Rental, exchange and planning are not operated through the standard admin
changelists but through their own pages, so a notification must lead there.
Sending somebody to a change form nobody opens makes the entry useless.

Every function degrades to an empty string, which renders the entry without
a link instead of producing a broken one.
"""

from django.urls import NoReverseMatch
from django.urls import reverse
from typing import Optional
from urllib.parse import urlencode
import logging


logger = logging.getLogger('django')


def _reverse(name: str) -> str:
    """Reverse a URL name, returning an empty string when it is missing."""
    try:
        return reverse(name)
    except NoReverseMatch:
        return ''


def _with_query(url: str, **params) -> str:
    """Append the non-empty parameters to a URL."""
    if not url:
        return ''
    query = urlencode({key: value for key, value in params.items() if value})
    return f'{url}?{query}' if query else url


def rental_process_url() -> str:
    """Return the rental process page, where hand-out and return happen."""
    return _reverse('rental:admin_rental_process')


def rental_detail_url(rental_id) -> str:
    """Return one rental request, falling back to the process overview."""
    if not rental_id:
        return rental_process_url()
    try:
        return reverse('rental:rental_detail', args=[rental_id])
    except NoReverseMatch:
        return rental_process_url()


def exchange_feed_url(search: str = '', channel: str = '',
                      status: str = '') -> str:
    """Return the exchange feed, optionally filtered down to one item."""
    return _with_query(
        _reverse('austausch:feed'),
        search=search, channel=channel, status=status)


def planung_calendar_url(day=None) -> str:
    """Return the planning calendar, optionally starting at a given day."""
    url = _reverse('admin:calendar_weeks_view')
    if day is None:
        return url
    return _with_query(url, start=day.isoformat())


def work_url(default: str, resolved: Optional[str]) -> str:
    """Prefer the working screen, fall back to the admin change page."""
    return resolved or default
