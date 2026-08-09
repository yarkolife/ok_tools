"""Creating events and fanning them out to the people who need them."""

from datetime import datetime
from datetime import time
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import Q
from django.utils import timezone
from notifications import config
from notifications import registry
from notifications.models import NotificationEvent
from notifications.models import NotificationSuppression
from notifications.models import Subscription
from notifications.models import UserNotification
from notifications.visibility import can_view
from notifications.visibility import permission_request
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
import logging


logger = logging.getLogger('django')


def build_dedup_key(code: str, obj=None, suffix: str = '') -> str:
    """Build the default deduplication key for an event."""
    parts = [code]
    if obj is not None:
        parts.append(f'{obj._meta.label_lower}:{obj.pk}')
    if suffix:
        parts.append(suffix)
    return '|'.join(parts)[:255]


def is_suppressed(code: str, obj) -> bool:
    """Return whether this object was permanently silenced for this type."""
    if obj is None:
        return False
    return NotificationSuppression.objects.filter(
        event_type=code,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
    ).exists()


def suppress(code: str, obj, *, user=None, reason: str = '') -> bool:
    """Silence one object for one event type, for everybody. Idempotent."""
    if obj is None:
        return False
    _row, created = NotificationSuppression.objects.get_or_create(
        event_type=code,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        defaults={'created_by': user, 'reason': reason},
    )
    return created


def exclude_suppressed(queryset, event_path: str = ''):
    """Drop rows whose event refers to a suppressed object."""
    prefix = f'{event_path}__' if event_path else ''
    suppressed = NotificationSuppression.objects.filter(
        event_type=OuterRef(f'{prefix}event_type'),
        content_type_id=OuterRef(f'{prefix}content_type_id'),
        object_id=OuterRef(f'{prefix}object_id'),
    )
    return queryset.annotate(
        _suppressed=Exists(suppressed)).filter(_suppressed=False)


def emit(code: str, *, obj=None, payload: Optional[Dict[str, Any]] = None,
         dedup_key: str = '', occurred_at=None,
         recipients: Optional[List[Any]] = None) -> Optional[NotificationEvent]:
    """Store an event and hand it to the subscribers that may see it.

    Returns the event, or None when the type is unknown, switched off or
    permanently suppressed for this object. Repeated calls with the same
    deduplication key are no-ops.

    ``recipients`` addresses named people instead of the subscribers, for
    results that only concern whoever started the job.
    """
    event_type = registry.get(code)
    if event_type is None:
        logger.warning('Unknown notification event type emitted: %s', code)
        return None
    if not config.is_enabled(code):
        return None
    if is_suppressed(code, obj):
        return None

    content_type = ContentType.objects.get_for_model(obj) if obj else None
    event, created = NotificationEvent.objects.get_or_create(
        dedup_key=dedup_key or build_dedup_key(code, obj),
        defaults={
            'module': event_type.module,
            'event_type': code,
            'category': event_type.category,
            'occurred_at': occurred_at or timezone.now(),
            'content_type': content_type,
            'object_id': obj.pk if obj else None,
            'payload': payload or {},
        },
    )
    if created and event_type.category == registry.CATEGORY_ACTION_REQUIRED:
        fan_out(event, event_type, recipients=recipients)
    return event


def emit_on_commit(code: str, **kwargs) -> None:  # noqa: D401
    """Emit the event once the surrounding transaction has been committed.

    Signals must never create a notification for an object that a rollback
    is about to undo.
    """
    transaction.on_commit(lambda: emit(code, **kwargs))


def subscribers(event_type: registry.EventType) -> List[Any]:
    """Return the staff users subscribed to this type and allowed to see it."""
    subscriptions = (
        Subscription.objects
        .filter(module=event_type.module)
        .filter(Q(event_type=Subscription.ALL_TYPES)
                | Q(event_type=event_type.code))
        .select_related('user')
    )
    result = []
    seen = set()
    for subscription in subscriptions:
        user = subscription.user
        if user.pk in seen or not user.is_active or not user.is_staff:
            continue
        seen.add(user.pk)
        if can_view(user, event_type, permission_request(user)):
            result.append(user)
    return result


def fan_out(event: NotificationEvent, event_type: registry.EventType,
            recipients: Optional[List[Any]] = None) -> int:
    """Create per-user copies of an action item. Returns how many were made."""
    if recipients is not None:
        users = [
            user for user in recipients
            if user is not None and user.is_active and user.is_staff
        ]
    else:
        users = subscribers(event_type)
    if not users:
        return 0
    UserNotification.objects.bulk_create(
        [UserNotification(user=user, event=event) for user in users],
        ignore_conflicts=True,
    )
    return len(users)


def backfill_action_items(user, codes: List[str]) -> int:
    """Create the missing action items after a subscription change.

    Fan-out happens when an event is created, so somebody who subscribes
    later would otherwise never see the items that are still open.
    """
    if not codes:
        return 0
    existing = set(
        UserNotification.objects
        .filter(user=user, event__event_type__in=codes)
        .values_list('event_id', flat=True)
    )
    events = exclude_suppressed(
        NotificationEvent.objects
        .filter(event_type__in=codes,
                category=registry.CATEGORY_ACTION_REQUIRED)
        .exclude(id__in=existing)
    )
    rows = [UserNotification(user=user, event=event) for event in events]
    if not rows:
        return 0
    UserNotification.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def mark_done(user, event_ids: List[int]) -> int:
    """Mark action items as handled. Returns how many rows changed."""
    if not event_ids:
        return 0
    now = timezone.now()
    return (
        UserNotification.objects
        .filter(user=user, event_id__in=event_ids, dismissed_at__isnull=True)
        .update(dismissed_at=now, read_at=now)
    )


def next_digest_moment() -> Any:
    """Return tomorrow at the time the daily summary is built.

    Postponing means "show it in tomorrow's summary", not "in 24 hours":
    the summary time is the point of reference of the working day.
    """
    from notifications.models import NotificationConfig

    digest_time = NotificationConfig.get_config().digest_time or time(10, 0)
    tomorrow = timezone.localdate() + timedelta(days=1)
    return timezone.make_aware(
        datetime.combine(tomorrow, digest_time),
        timezone.get_current_timezone(),
    )


def snooze(user, event_ids: List[int], until=None) -> int:
    """Hide action items until tomorrow's summary. Returns how many."""
    if not event_ids:
        return 0
    return (
        UserNotification.objects
        .filter(user=user, event_id__in=event_ids, dismissed_at__isnull=True)
        .update(snoozed_until=until or next_digest_moment())
    )


def reopen(user, event_ids: List[int]) -> int:
    """Undo "handled". Returns how many rows changed.

    Marking as handled has to be reversible: it is one click, often a bulk
    one, and without an undo a mistake silently removes the work.
    """
    if not event_ids:
        return 0
    return (
        UserNotification.objects
        .filter(user=user, event_id__in=event_ids,
                dismissed_at__isnull=False)
        .update(dismissed_at=None, read_at=None, snoozed_until=None)
    )


def wake(user, event_ids: List[int]) -> int:
    """Bring postponed items back into the list. Returns how many."""
    if not event_ids:
        return 0
    return (
        UserNotification.objects
        .filter(user=user, event_id__in=event_ids,
                snoozed_until__isnull=False)
        .update(snoozed_until=None)
    )


def suppress_events(event_ids: List[int], *, user=None,
                    reason: str = '') -> int:
    """Silence the objects behind the given events. Returns how many."""
    if not event_ids:
        return 0
    events = NotificationEvent.objects.filter(
        id__in=event_ids, content_type__isnull=False, object_id__isnull=False)
    rows = [
        NotificationSuppression(
            event_type=event.event_type,
            content_type_id=event.content_type_id,
            object_id=event.object_id,
            created_by=user,
            reason=reason,
        )
        for event in events
    ]
    if not rows:
        return 0
    NotificationSuppression.objects.bulk_create(rows, ignore_conflicts=True)
    # A suppressed finding must disappear for everybody, not only later on.
    now = timezone.now()
    UserNotification.objects.filter(
        event_id__in=event_ids, dismissed_at__isnull=True
    ).update(dismissed_at=now, read_at=now)
    return len(rows)
