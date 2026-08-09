"""Who "we" are, for telling own productions from other channels' material."""

from django.apps import apps
from typing import Optional
import logging


logger = logging.getLogger('django')


def own_media_authority():
    """Return the media authority this installation represents, or None.

    The value belongs to the organization, not to the exchange module: a
    channel may not use the exchange at all. Deployments that only ever
    filled in ``ExchangeConfig.default_media_authority`` keep working
    through the fallback, and the data migration copies it over once.
    """
    from registration.models import OrganizationConfig

    authority = OrganizationConfig.get_config().media_authority
    if authority is not None:
        return authority

    if not apps.is_installed('austausch'):
        return None
    from austausch.models import ExchangeConfig

    config = ExchangeConfig.objects.exclude(
        default_media_authority__isnull=True).first()
    return config.default_media_authority if config else None


def own_license_numbers(numbers) -> Optional[set]:
    """Narrow license numbers down to the ones produced by our own authors.

    Returns None when the own authority is not configured, so a caller can
    tell "nothing matched" from "the question cannot be answered yet".
    """
    numbers = list(numbers or [])
    if not numbers:
        return set()
    authority = own_media_authority()
    if authority is None:
        return None

    from licenses.models import License

    return set(
        License.objects
        .filter(number__in=numbers, profile__media_authority=authority)
        .values_list('number', flat=True)
    )
