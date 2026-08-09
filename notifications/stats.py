"""Adoption figures for the notification system.

Stage 4 of ``plans/notifications-digest-plan.md`` asks two questions that
only data can answer: does anybody open the page, and do the action items
actually get closed. Everything needed is already recorded -- the read
marker, the dismissal and snooze timestamps and the suppressions -- so this
module only reads and aggregates.

Read the numbers with the observation window in mind: a type that was
switched on yesterday cannot have a completion rate.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from notifications import registry
from notifications.models import NotificationEvent
from notifications.models import NotificationEventTypeConfig
from notifications.models import NotificationSuppression
from notifications.models import Subscription
from notifications.models import UserNotification
from notifications.models import UserNotificationState
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


def _median(values: List[float]) -> Optional[float]:
    """Return the median of a list, or None when it is empty."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def per_type_report(days: int = 30) -> List[Dict[str, Any]]:
    """Return volume and completion figures per event type."""
    since = timezone.now() - timedelta(days=days)
    enabled = dict(
        NotificationEventTypeConfig.objects.values_list('code', 'enabled'))

    events = dict(
        NotificationEvent.objects
        .filter(occurred_at__gte=since)
        .values_list('event_type')
        .annotate(count=Count('id'))
        .values_list('event_type', 'count')
    )
    suppressions = dict(
        NotificationSuppression.objects
        .values_list('event_type')
        .annotate(count=Count('id'))
        .values_list('event_type', 'count')
    )

    items = (
        UserNotification.objects
        .filter(event__occurred_at__gte=since)
        .values('event__event_type')
        .annotate(
            total=Count('id'),
            dismissed=Count('id', filter=Q(dismissed_at__isnull=False)),
            snoozed=Count('id', filter=Q(dismissed_at__isnull=True,
                                         snoozed_until__gt=timezone.now())),
        )
    )
    by_type = {row['event__event_type']: row for row in items}

    # Time to close, computed in python: a median is awkward in SQL and the
    # window keeps the number of rows small.
    durations: Dict[str, List[float]] = {}
    closed = (
        UserNotification.objects
        .filter(dismissed_at__isnull=False, event__occurred_at__gte=since)
        .values_list('event__event_type', 'event__occurred_at', 'dismissed_at')
    )
    for code, occurred_at, dismissed_at in closed:
        durations.setdefault(code, []).append(
            (dismissed_at - occurred_at).total_seconds() / 3600)

    report = []
    for event_type in registry.all_types():
        code = event_type.code
        row = by_type.get(code, {})
        total = row.get('total', 0)
        dismissed = row.get('dismissed', 0)
        report.append({
            'code': code,
            'module': event_type.module,
            'module_label': event_type.module_label,
            'label': event_type.label,
            'category': event_type.category,
            'expectation': event_type.expectation,
            'enabled': enabled.get(code, event_type.default_enabled),
            'events': events.get(code, 0),
            'items': total,
            'dismissed': dismissed,
            'snoozed': row.get('snoozed', 0),
            'open': total - dismissed,
            'suppressed': suppressions.get(code, 0),
            'closed_share': round(dismissed * 100 / total) if total else None,
            'median_hours': (
                round(value, 1)
                if (value := _median(durations.get(code, []))) is not None
                else None
            ),
        })
    return report


def per_user_report() -> List[Dict[str, Any]]:
    """Return who reads the page and how much is waiting for them."""
    User = get_user_model()
    now = timezone.now()

    seen = dict(
        UserNotificationState.objects.values_list('user_id', 'last_seen_at'))
    subscriptions = dict(
        Subscription.objects
        .values_list('user_id')
        .annotate(count=Count('id'))
        .values_list('user_id', 'count')
    )
    open_items = dict(
        UserNotification.objects
        .filter(dismissed_at__isnull=True)
        .values_list('user_id')
        .annotate(count=Count('id'))
        .values_list('user_id', 'count')
    )
    dismissed = dict(
        UserNotification.objects
        .filter(dismissed_at__isnull=False)
        .values_list('user_id')
        .annotate(count=Count('id'))
        .values_list('user_id', 'count')
    )

    report = []
    for user in User.objects.filter(is_staff=True, is_active=True):
        last_seen = seen.get(user.pk)
        report.append({
            'email': user.email,
            'is_superuser': user.is_superuser,
            'subscriptions': subscriptions.get(user.pk, 0),
            'last_seen_at': last_seen,
            'days_since': (
                (now - last_seen).days if last_seen is not None else None),
            'open_items': open_items.get(user.pk, 0),
            'dismissed_items': dismissed.get(user.pk, 0),
        })
    return sorted(
        report,
        key=lambda row: (row['days_since'] is None,
                         row['days_since'] or 0, row['email']),
    )


def summary(days: int = 30) -> Dict[str, Any]:
    """Return the headline figures the stage 4 decision rests on."""
    users = per_user_report()
    types = per_type_report(days)
    week_ago_days = 7

    total_items = sum(row['items'] for row in types)
    total_dismissed = sum(row['dismissed'] for row in types)
    return {
        'days': days,
        'staff': len(users),
        'with_subscriptions': sum(
            1 for row in users if row['subscriptions']),
        'ever_opened': sum(
            1 for row in users if row['last_seen_at'] is not None),
        'opened_last_week': sum(
            1 for row in users
            if row['days_since'] is not None
            and row['days_since'] <= week_ago_days),
        'events': sum(row['events'] for row in types),
        'action_items': total_items,
        'dismissed': total_dismissed,
        'closed_share': (
            round(total_dismissed * 100 / total_items)
            if total_items else None),
        'suppressed': sum(row['suppressed'] for row in types),
        'enabled_types': sum(1 for row in types if row['enabled']),
        'types': len(types),
    }


def full_report(days: int = 30) -> Dict[str, Any]:
    """Return everything the stats page and the command need."""
    return {
        'summary': summary(days),
        'types': per_type_report(days),
        'users': per_user_report(),
    }
