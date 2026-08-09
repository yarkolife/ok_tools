"""Template tags that surface notifications inside the admin.

The tags live in ``ok_tools`` because the admin base templates load them
unconditionally while the app itself is optional. The templates they render
live in the ``notifications`` app, which is where their strings belong: the
tags return an empty string when the app is not installed, so those
templates are never looked up in that case.
"""

from django import template
from django.apps import apps
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
import logging


logger = logging.getLogger('django')

register = template.Library()


def _staff_user(context):
    """Return the staff user of the current request, or None."""
    if not apps.is_installed('notifications'):
        return None
    request = context.get('request')
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_staff:
        return None
    return user


@register.simple_tag(takes_context=True)
def notifications_summary(context):
    """Render today's summary block for the admin index page."""
    user = _staff_user(context)
    if user is None:
        return ''

    from notifications import selectors
    request = context.get('request')
    try:
        payload = {
            'expectations': selectors.expectations(user, request),
            'action_items': selectors.open_action_items(user, request)[:10],
            'action_count': selectors.action_count(user, request),
            'new_count': selectors.new_count(user, request),
            'feed': selectors.feed(user, request, limit=10),
            'has_subscriptions': bool(selectors.subscribed_types(user, request)),
        }
    except Exception:
        logger.exception('Could not build the notification summary block')
        return ''

    return mark_safe(render_to_string(
        'notifications/summary_block.html', payload, request=request))


@register.simple_tag(takes_context=True)
def notifications_badge(context):
    """Render the header indicator with the number of open action items."""
    user = _staff_user(context)
    if user is None:
        return ''

    from notifications import selectors
    request = context.get('request')
    try:
        count = selectors.action_count(user, request)
        new_count = selectors.new_count(user, request)
    except Exception:
        logger.exception('Could not build the notification badge')
        return ''

    return mark_safe(render_to_string(
        'notifications/badge.html',
        {'count': count, 'new_count': new_count},
        request=request,
    ))
