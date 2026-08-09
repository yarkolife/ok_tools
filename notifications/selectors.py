"""Read side: what a given user sees on the summary and in the feed."""

from datetime import timedelta
from django.core.cache import cache
from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone
from django.utils.dateparse import parse_date
from notifications import config
from notifications import presets
from notifications import registry
from notifications.models import NotificationEvent
from notifications.models import Subscription
from notifications.models import UserNotification
from notifications.models import UserNotificationState
from notifications.services import backfill_action_items
from notifications.services import exclude_suppressed
from notifications.visibility import can_view
from notifications.visibility import permission_request
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
import logging


logger = logging.getLogger('django')

EXPECTATIONS_CACHE_SECONDS = 300


def allowed_types(user, request=None) -> List[registry.EventType]:
    """Return event types that are switched on and visible to the user."""
    check_request = request or permission_request(user)
    return [
        event_type for event_type in config.enabled_types()
        if can_view(user, event_type, check_request)
    ]


def subscribed_types(user, request=None) -> List[registry.EventType]:
    """Return the allowed types the user has actually subscribed to."""
    subscriptions = list(
        Subscription.objects.filter(user=user)
        .values_list('module', 'event_type'))
    if not subscriptions:
        return []
    modules = {module for module, event_type in subscriptions
               if event_type == Subscription.ALL_TYPES}
    codes = {event_type for _module, event_type in subscriptions
             if event_type != Subscription.ALL_TYPES}
    return [
        event_type for event_type in allowed_types(user, request)
        if event_type.module in modules or event_type.code in codes
    ]


def parse_filters(request) -> Dict[str, Any]:
    """Read the filter values of the feed page from the query string."""
    if request is None:
        return {}
    data = request.GET
    filters: Dict[str, Any] = {}
    for key in ('module', 'type', 'category'):
        value = (data.get(key) or '').strip()
        if value:
            filters[key] = value
    for key in ('date_from', 'date_to'):
        value = (data.get(key) or '').strip()
        parsed = parse_date(value) if value else None
        if parsed:
            filters[key] = parsed
    older = (data.get('older') or '').strip()
    if older.isdigit():
        filters['older'] = int(older)
    return filters


def parse_filters_from_query(query: str) -> Dict[str, Any]:
    """Read filter values from a raw query string (used on POST)."""
    return parse_filters(_QueryOnlyRequest(query))


class _QueryOnlyRequest:
    """Minimal stand-in exposing only GET, for reusing parse_filters()."""

    def __init__(self, query: str):
        self.GET = QueryDict(query or '')


def apply_filters(queryset, filters: Dict[str, Any], prefix: str = ''):
    """Narrow a queryset of events (or of rows pointing at events)."""
    if not filters:
        return queryset
    field = f'{prefix}__' if prefix else ''
    if filters.get('module'):
        queryset = queryset.filter(**{f'{field}module': filters['module']})
    if filters.get('type'):
        queryset = queryset.filter(**{f'{field}event_type': filters['type']})
    if filters.get('category'):
        queryset = queryset.filter(
            **{f'{field}category': filters['category']})
    if filters.get('date_from'):
        queryset = queryset.filter(
            **{f'{field}occurred_at__date__gte': filters['date_from']})
    if filters.get('date_to'):
        queryset = queryset.filter(
            **{f'{field}occurred_at__date__lte': filters['date_to']})
    if filters.get('older'):
        cutoff = timezone.now() - timedelta(days=filters['older'])
        queryset = queryset.filter(
            **{f'{field}occurred_at__lt': cutoff})
    return queryset


def feed(user, request=None, limit: int = 50, since=None,
         filters: Optional[Dict[str, Any]] = None):
    """Return the stored events the user is subscribed to, newest first."""
    codes = [event_type.code for event_type in subscribed_types(user, request)
             if not event_type.expectation]
    if not codes:
        return NotificationEvent.objects.none()
    queryset = (
        NotificationEvent.objects
        .filter(event_type__in=codes)
        .select_related('content_type')
    )
    if since is not None:
        queryset = queryset.filter(occurred_at__gt=since)
    queryset = apply_filters(queryset, filters or {})
    queryset = exclude_suppressed(queryset)
    if limit:
        return queryset[:limit]
    return queryset


def open_action_items(user, request=None,
                      filters: Optional[Dict[str, Any]] = None,
                      include_snoozed: bool = False):
    """Return the user's unfinished action items, newest first.

    Filtered by the current subscriptions, not only by what was assigned:
    unsubscribing from a module has to empty its counter, otherwise the
    subscription switch does nothing for the number people actually watch.
    Re-subscribing brings the open items back through the backfill.

    Postponed items are hidden until their moment has come.
    """
    codes = [event_type.code for event_type in subscribed_types(user, request)]
    if not codes:
        return UserNotification.objects.none()
    queryset = (
        UserNotification.objects
        .filter(user=user, dismissed_at__isnull=True,
                event__event_type__in=codes)
        .select_related('event', 'event__content_type')
    )
    if not include_snoozed:
        queryset = queryset.filter(
            Q(snoozed_until__isnull=True)
            | Q(snoozed_until__lte=timezone.now()))
    queryset = apply_filters(queryset, filters or {}, prefix='event')
    return exclude_suppressed(queryset, event_path='event')


def snoozed_action_items(user, request=None,
                          filters: Optional[Dict[str, Any]] = None):
    """Return the items that are currently postponed."""
    codes = [event_type.code for event_type in subscribed_types(user, request)]
    if not codes:
        return UserNotification.objects.none()
    queryset = (
        UserNotification.objects
        .filter(user=user, dismissed_at__isnull=True,
                snoozed_until__gt=timezone.now(),
                event__event_type__in=codes)
        .select_related('event', 'event__content_type')
    )
    queryset = apply_filters(queryset, filters or {}, prefix='event')
    return exclude_suppressed(queryset, event_path='event')


def handled_action_items(user, request=None,
                         filters: Optional[Dict[str, Any]] = None):
    """Return the items this user already closed, newest first."""
    codes = [event_type.code for event_type in subscribed_types(user, request)]
    if not codes:
        return UserNotification.objects.none()
    queryset = (
        UserNotification.objects
        .filter(user=user, dismissed_at__isnull=False,
                event__event_type__in=codes)
        .select_related('event', 'event__content_type')
        .order_by('-dismissed_at')
    )
    queryset = apply_filters(queryset, filters or {}, prefix='event')
    return exclude_suppressed(queryset, event_path='event')


def status_by_event(user, events) -> Dict[int, str]:
    """Return the personal state of each given event.

    Without it the feed shows entries that were long since dealt with and
    looks like a list nobody can act on.
    """
    ids = [event.pk for event in events]
    if not ids:
        return {}
    now = timezone.now()
    rows = UserNotification.objects.filter(
        user=user, event_id__in=ids
    ).values_list('event_id', 'dismissed_at', 'snoozed_until')

    result = {}
    for event_id, dismissed_at, snoozed_until in rows:
        if dismissed_at is not None:
            result[event_id] = 'handled'
        elif snoozed_until is not None and snoozed_until > now:
            result[event_id] = 'snoozed'
        else:
            result[event_id] = 'open'
    return result


def action_count(user, request=None) -> int:
    """Return how many action items are waiting for this user."""
    return open_action_items(user, request).count()


def get_state(user) -> UserNotificationState:
    """Return (creating if needed) the read marker of the user."""
    state, _created = UserNotificationState.objects.get_or_create(user=user)
    return state


def new_count(user, request=None) -> int:
    """Return how many stored events appeared since the last visit."""
    state = get_state(user)
    if state.last_seen_at is None:
        return feed(user, request, limit=100).count()
    return feed(user, request, limit=100, since=state.last_seen_at).count()


def mark_seen(user) -> None:
    """Move the read marker to now."""
    state = get_state(user)
    state.last_seen_at = timezone.now()
    state.save(update_fields=['last_seen_at'])


def run_expectation_check(event_type: registry.EventType) -> List[Dict[str, Any]]:
    """Run one expectation check, using a short lived cache.

    Expectations are never stored: a rental moved to another day must
    disappear from the summary without leaving a stale row behind.
    """
    cache_key = f'notifications:expectation:{event_type.code}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    check = registry.get_check(event_type.code)
    if check is None:
        return []
    params = config.get_params(event_type.code)
    try:
        findings = check(params)
    except Exception:
        logger.exception(
            'Notification check failed: %s', event_type.code)
        return []
    payloads = [finding.payload for finding in findings]
    cache.set(cache_key, payloads, EXPECTATIONS_CACHE_SECONDS)
    return payloads


def expectations(user, request=None) -> List[Dict[str, Any]]:
    """Return today's expectations the user is subscribed to."""
    result = []
    for event_type in subscribed_types(user, request):
        if not event_type.expectation:
            continue
        payloads = run_expectation_check(event_type)
        if not payloads:
            continue
        result.append({
            'code': event_type.code,
            'label': event_type.label,
            'module': event_type.module,
            'module_label': event_type.module_label,
            'category': event_type.category,
            'items': [
                {
                    # Rendered per reader: the cache holds payloads only.
                    'message': registry.render_message(
                        event_type.code, payload),
                    'url': payload.get('url', ''),
                    'payload': payload,
                }
                for payload in payloads
            ],
        })
    return result


def subscription_matrix(user, request=None) -> List[Dict[str, Any]]:
    """Return the subscription state per module for the settings page."""
    subscribed = {
        (module, event_type)
        for module, event_type
        in Subscription.objects.filter(user=user).values_list(
            'module', 'event_type')
    }
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for event_type in allowed_types(user, request):
        grouped.setdefault(event_type.module, []).append({
            'code': event_type.code,
            'label': event_type.label,
            'category': event_type.category,
            'subscribed': (
                (event_type.module, Subscription.ALL_TYPES) in subscribed
                or (event_type.module, event_type.code) in subscribed
            ),
        })
    return [
        {
            'module': module,
            'module_label': registry.MODULE_LABELS.get(module, module),
            'whole_module': (module, Subscription.ALL_TYPES) in subscribed,
            'types': types,
        }
        for module, types in grouped.items()
    ]


def set_subscriptions(user, modules: List[str], codes: List[str]) -> None:
    """Replace the user's subscriptions with the given selection."""
    Subscription.objects.filter(user=user).delete()
    rows = [
        Subscription(user=user, module=module,
                     event_type=Subscription.ALL_TYPES)
        for module in modules
    ]
    for code in codes:
        event_type = registry.get(code)
        if event_type is None or event_type.module in modules:
            continue
        rows.append(Subscription(
            user=user, module=event_type.module, event_type=code))
    if rows:
        Subscription.objects.bulk_create(rows, ignore_conflicts=True)
    backfill_action_items(
        user,
        [event_type.code for event_type in subscribed_types(user)
         if event_type.category == registry.CATEGORY_ACTION_REQUIRED
         and not event_type.expectation],
    )


def apply_preset(user, name: str) -> Optional[List[str]]:
    """Subscribe the user to every module of a preset. Returns the modules."""
    modules = presets.get_modules(name)
    if not modules:
        return None
    set_subscriptions(user, modules, [])
    return modules
