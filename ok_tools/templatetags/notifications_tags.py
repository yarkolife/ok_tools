"""Template tag that surfaces notifications inside the admin.

The tag lives in ``ok_tools`` because the admin base templates load it
unconditionally while the app itself is optional. The template it renders
lives in the ``notifications`` app, which is where its strings belong: the
tag returns an empty string when the app is not installed, so that template
is never looked up in that case.

The admin index carries no summary block: the bell in the header and the
``Benachrichtigungen`` menu are the two ways into the notification centre,
and a third copy of today's list on the dashboard only repeated them.
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
