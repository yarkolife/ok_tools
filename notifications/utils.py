"""Small helpers shared by the checks and the signal handlers."""

from django.urls import NoReverseMatch
from django.urls import reverse


def admin_url(obj) -> str:
    """Return the admin change URL of an object, or an empty string.

    An empty string simply renders the entry without a link, which is what
    should happen for a model that is not registered in the admin.
    """
    if obj is None:
        return ''
    meta = obj._meta
    try:
        return reverse(
            f'admin:{meta.app_label}_{meta.model_name}_change', args=[obj.pk])
    except NoReverseMatch:
        return ''
