"""Scheduled work of the notification system.

The daily task does not deliver anything: it produces the events that no
signal can produce (overdue items, deadlines, missing plans) and marks the
start of the working day. Delivery is the rendering of the admin page.
"""

from celery import shared_task
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from notifications import config
from notifications import registry
from notifications.models import NotificationConfig
from notifications.models import NotificationEvent
from notifications.services import emit
from typing import Any
from typing import Dict
import logging


logger = logging.getLogger('django')


def run_scan() -> Dict[str, Any]:
    """Run every enabled scan check that stores its findings."""
    created = 0
    skipped = 0
    per_type: Dict[str, int] = {}

    for event_type in registry.all_types():
        if event_type.source != registry.SOURCE_SCAN:
            continue
        if event_type.expectation:
            # Expectations are recomputed on render, never stored.
            cache.delete(f'notifications:expectation:{event_type.code}')
            continue
        if not config.is_enabled(event_type.code):
            # A disabled check is not executed at all.
            skipped += 1
            continue

        check = registry.get_check(event_type.code)
        if check is None:
            logger.warning(
                'Notification event type %s has no check', event_type.code)
            continue

        try:
            findings = check(config.get_params(event_type.code))
        except Exception:
            logger.exception(
                'Notification check failed: %s', event_type.code)
            continue

        for finding in findings:
            event = emit(
                event_type.code,
                obj=finding.obj,
                payload=finding.payload,
                dedup_key=finding.dedup_key,
                occurred_at=finding.occurred_at,
            )
            if event is not None:
                created += 1
                per_type[event_type.code] = per_type.get(event_type.code, 0) + 1

    return {'created': created, 'skipped': skipped, 'per_type': per_type}


@shared_task(name='notifications.tasks.build_daily_digest')
def build_daily_digest() -> Dict[str, Any]:
    """Build the day marker: run the scans and refresh the expectations."""
    notification_config = NotificationConfig.get_config()
    if not notification_config.enabled:
        return {'enabled': False}

    config.sync_event_type_configs()
    result = run_scan()
    result['enabled'] = True
    result['date'] = timezone.localdate().isoformat()
    logger.info('Notification digest built: %s', result)
    return result


@shared_task(name='notifications.tasks.cleanup_old_events')
def cleanup_old_events(older_than_days: int = 0) -> Dict[str, Any]:
    """Delete events past the retention period."""
    notification_config = NotificationConfig.get_config()
    days = older_than_days or notification_config.retention_days
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _details = NotificationEvent.objects.filter(
        occurred_at__lt=cutoff).delete()
    logger.info('Deleted %s notification events older than %s days',
                deleted, days)
    return {'deleted': deleted, 'days': days}
