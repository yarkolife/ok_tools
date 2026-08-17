"""Current workflow state for stored action events.

Events are immutable facts, but an action item is only useful while its
underlying process condition is still true.  This module keeps the read side
current without rewriting event history or pretending that a user handled an
item which the workflow resolved automatically.
"""

from datetime import datetime
from datetime import timedelta
from django.apps import apps
from django.utils import timezone
from notifications import config
from notifications.models import NotificationEvent
from typing import Dict
from typing import Iterable
from typing import List
from typing import Set
import logging


logger = logging.getLogger('django')


PROCESS_EVENT_TYPES = {
    'rental.new_request',
    'rental.pickup_overdue',
    'rental.return_overdue',
    'rental.issue_reported',
    'licenses.new_unconfirmed',
    'licenses.unconfirmed_aging',
    'licenses.nextcloud_download_pending',
    'licenses.confirmed_without_video',
    'media_files.new_video',
    'media_files.orphan_video',
    'media_files.format_mismatch',
    'media_files.missing_reel',
    'media_files.missing_cover',
    'media_files.reel_post_today',
    'media_files.operation_failed',
    'media_files.storage_low',
    'media_files.storage_unavailable',
    'austausch.new_items',
    'austausch.import_failed',
    'planung.plan_missing',
    'planung.plan_missing_video',
    'planung.not_aired',
    'tools.job_finished',
    'tools.job_failed',
    'system.task_failures',
    'registration.new_profile',
    'registration.unverified_aging',
}


SCAN_STATE_EVENT_TYPES = {
    'rental.pickup_overdue',
    'rental.return_overdue',
    'licenses.unconfirmed_aging',
    'licenses.nextcloud_download_pending',
    'licenses.confirmed_without_video',
    'media_files.orphan_video',
    'media_files.format_mismatch',
    'media_files.reel_post_today',
    'media_files.storage_low',
    'media_files.storage_unavailable',
    'austausch.new_items',
    'planung.plan_missing',
    'planung.not_aired',
    'system.task_failures',
    'registration.unverified_aging',
}


def _number(value):
    """Return an integer payload value, or None for old/malformed events."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _payload_date(value):
    """Return the date stored in a missing-asset payload."""
    try:
        return datetime.strptime(str(value), '%d.%m.%Y').date()
    except (TypeError, ValueError):
        return None


def _scan_activity(events: List[NotificationEvent]) -> Set[int]:
    """Return scan findings that still match the current domain state."""
    if not events:
        return set()
    from notifications import registry

    grouped: Dict[str, List[NotificationEvent]] = {}
    for event in events:
        if event.event_type in SCAN_STATE_EVENT_TYPES:
            grouped.setdefault(event.event_type, []).append(event)
    active = set()
    for code, rows in grouped.items():
        check = registry.get_check(code)
        if check is None:
            continue
        try:
            current_keys = {
                finding.dedup_key
                for finding in check(config.get_params(code))
            }
        except Exception:
            logger.exception(
                'Could not evaluate notification process state: %s', code)
            # A temporary read failure must not make a real task disappear.
            active.update(event.pk for event in rows)
            continue
        active.update(
            event.pk for event in rows if event.dedup_key in current_keys)
    return active


def _latest_active_per_object(
        active: Set[int], events: List[NotificationEvent]) -> Set[int]:
    """Keep one current row when repeated scans describe the same task."""
    latest = {}
    for event in events:
        if event.pk not in active:
            continue
        key = (
            event.event_type,
            event.content_type_id,
            event.object_id if event.object_id is not None else event.dedup_key,
        )
        previous = latest.get(key)
        if previous is None or event.occurred_at > previous.occurred_at:
            latest[key] = event
    keep = {event.pk for event in latest.values()}
    return (active - {event.pk for event in events}) | keep


def _supersede(
        active: Set[int], grouped: Dict[str, List[NotificationEvent]],
        older_code: str, newer_code: str) -> Set[int]:
    """Hide an earlier workflow label when its escalation is active."""
    newer_objects = {
        event.object_id for event in grouped.get(newer_code, [])
        if event.pk in active and event.object_id is not None
    }
    if not newer_objects:
        return active
    obsolete = {
        event.pk for event in grouped.get(older_code, [])
        if event.object_id in newer_objects
    }
    return active - obsolete


def _license_activity(events: List[NotificationEvent]) -> Set[int]:
    """Return active signal-based license workflow event ids."""
    if not events:
        return set()
    License = apps.get_model('licenses.License')
    states = {
        row['id']: row
        for row in License.objects.filter(
            id__in={event.object_id for event in events if event.object_id})
        .values('id', 'number', 'confirmed', 'is_live')
    }
    active = set()
    for event in events:
        state = states.get(event.object_id)
        if state is None:
            continue
        if (event.event_type == 'licenses.new_unconfirmed'
                and not state['confirmed']):
            active.add(event.pk)
    return active


def _new_video_activity(events: List[NotificationEvent]) -> Set[int]:
    """New files are facts; automation decides whether attention is needed."""
    return set()


def _planned_entries(dates) -> List[Dict]:
    """Return only committed broadcast-plan entries for the given dates."""
    if not dates or not apps.is_installed('planung'):
        return []
    from planung.selectors import planned_entries

    return [
        entry for entry in planned_entries(dates)
        if entry['plan'].json_plan.get('planned') is True
        and entry['plan'].json_plan.get('draft') is not True
    ]


def _missing_asset_activity(events: List[NotificationEvent]) -> Set[int]:
    """Return planned asset findings whose complete prerequisite chain holds."""
    if not events or not apps.is_installed('media_files'):
        return set()
    today = timezone.localdate()
    event_dates = {
        event.pk: _payload_date((event.payload or {}).get('date'))
        for event in events
    }
    eligible_dates = set()
    for event in events:
        day = event_dates[event.pk]
        horizon = max(int(config.get_params(event.event_type).get(
            'horizon_days', 3)), 0)
        if day is not None and today <= day <= today + timedelta(days=horizon):
            eligible_dates.add(day)
    entries = _planned_entries(eligible_dates)
    planned_keys = {
        (entry['date'], entry['number']) for entry in entries
    }
    numbers = {number for _day, number in planned_keys}
    if not numbers:
        return set()

    from media_files.utils import numbers_with_cover
    from media_files.utils import numbers_with_reel
    from media_files.utils import numbers_with_video
    from notifications.org import own_license_numbers

    own = own_license_numbers(numbers)
    if own is None:
        return set()
    License = apps.get_model('licenses.License')
    confirmed = set(
        License.objects.filter(
            number__in=own, confirmed=True, is_live=False)
        .values_list('number', flat=True)
    )
    eligible_numbers = confirmed & numbers_with_video(confirmed)
    Contribution = apps.get_model('contributions.Contribution')
    repeated_numbers = set(
        Contribution.objects.filter(license__number__in=eligible_numbers)
        .values_list('license__number', flat=True)
    )
    premiere_numbers = eligible_numbers - repeated_numbers
    missing_by_type = {
        'media_files.missing_reel': (
            eligible_numbers - numbers_with_reel(eligible_numbers)),
        'media_files.missing_cover': (
            premiere_numbers - numbers_with_cover(premiere_numbers)),
    }
    active = set()
    for event in events:
        day = event_dates[event.pk]
        number = _number((event.payload or {}).get('number'))
        if ((day, number) in planned_keys
                and number in missing_by_type[event.event_type]):
            active.add(event.pk)
    return active


def _plan_missing_video_activity(
        events: List[NotificationEvent]) -> Set[int]:
    """Return plan findings that still need a physical video file."""
    if not events or not apps.is_installed('planung'):
        return set()
    today = timezone.localdate()
    horizon = max(int(config.get_params(
        'planung.plan_missing_video').get('horizon_days', 3)), 0)
    dates = [today + timedelta(days=offset)
             for offset in range(horizon + 1)]
    entries = _planned_entries(dates)
    planned_keys = {
        (entry['date'], entry['number']) for entry in entries
    }
    numbers = {number for _day, number in planned_keys}
    License = apps.get_model('licenses.License')
    live_numbers = set(
        License.objects.filter(number__in=numbers, is_live=True)
        .values_list('number', flat=True))
    with_video = set()
    if apps.is_installed('media_files'):
        from media_files.utils import numbers_with_video

        with_video = numbers_with_video(numbers)
    active = set()
    for event in events:
        day = _payload_date((event.payload or {}).get('date'))
        number = _number((event.payload or {}).get('number'))
        if ((day, number) in planned_keys
                and number not in live_numbers
                and number not in with_video):
            active.add(event.pk)
    return active


def _rental_signal_activity(
        grouped: Dict[str, List[NotificationEvent]]) -> Set[int]:
    """Return rental requests and reported issues still needing staff."""
    if not apps.is_installed('rental'):
        return set()
    active = set()
    request_events = grouped.get('rental.new_request', [])
    RentalRequest = apps.get_model('rental.RentalRequest')
    draft_ids = set(
        RentalRequest.objects.filter(
            pk__in={event.object_id for event in request_events},
            status='draft',
        ).values_list('pk', flat=True)
    )
    active.update(
        event.pk for event in request_events if event.object_id in draft_ids)

    issue_events = grouped.get('rental.issue_reported', [])
    RentalIssue = apps.get_model('rental.RentalIssue')
    unresolved_ids = set(
        RentalIssue.objects.filter(
            pk__in={event.object_id for event in issue_events},
            resolved=False,
        ).values_list('pk', flat=True)
    )
    active.update(
        event.pk for event in issue_events
        if event.object_id in unresolved_ids)
    return active


def _registration_signal_activity(
        grouped: Dict[str, List[NotificationEvent]]) -> Set[int]:
    """Return new profiles that have not yet been verified."""
    events = grouped.get('registration.new_profile', [])
    if not events:
        return set()
    Profile = apps.get_model('registration.Profile')
    pending_ids = set(
        Profile.objects.filter(
            pk__in={event.object_id for event in events},
            verified=False,
        ).values_list('pk', flat=True)
    )
    return {event.pk for event in events if event.object_id in pending_ids}


def _operation_id(event: NotificationEvent):
    """Return the operation primary key encoded in a signal dedup key."""
    try:
        return int(event.dedup_key.rsplit('|', 1)[-1])
    except (TypeError, ValueError):
        return None


def _media_operation_activity(events: List[NotificationEvent]) -> Set[int]:
    """Keep a failed file operation only until a successful retry exists."""
    if not events or not apps.is_installed('media_files'):
        return set()
    FileOperation = apps.get_model('media_files.FileOperation')
    operations = {
        item.pk: item for item in FileOperation.objects.filter(
            pk__in={_operation_id(event) for event in events})
    }
    active = set()
    for event in events:
        operation = operations.get(_operation_id(event))
        if operation is None or str(operation.status).lower() != 'failed':
            continue
        recovered = FileOperation.objects.filter(
            video_file_id=operation.video_file_id,
            operation_type=operation.operation_type,
            status='SUCCESS',
            performed_at__gt=operation.performed_at,
        ).exists()
        if not recovered:
            active.add(event.pk)
    return active


def _exchange_import_activity(events: List[NotificationEvent]) -> Set[int]:
    """Keep an Austausch failure only until a later import succeeds."""
    if not events or not apps.is_installed('austausch'):
        return set()
    ExchangeImport = apps.get_model('austausch.ExchangeImport')
    operations = {
        item.pk: item for item in ExchangeImport.objects.filter(
            pk__in={_operation_id(event) for event in events})
    }
    active = set()
    for event in events:
        operation = operations.get(_operation_id(event))
        if operation is None or operation.status != 'failed':
            continue
        recovered = ExchangeImport.objects.filter(
            exchange_item_id=operation.exchange_item_id,
            status='completed',
            created_at__gt=operation.created_at,
        ).exists()
        if not recovered:
            active.add(event.pk)
    return active


def _tools_failure_activity(events: List[NotificationEvent]) -> Set[int]:
    """Return addressed tool jobs whose current status is still failed."""
    active = set()
    for event in events:
        model = event.content_type.model_class() if event.content_type else None
        if model is None or event.object_id is None:
            continue
        status = model.objects.filter(pk=event.object_id).values_list(
            'status', flat=True).first()
        if status == 'failed':
            active.add(event.pk)
    return active


def inactive_event_ids(events: Iterable[NotificationEvent]) -> Set[int]:
    """Return ids whose workflow condition is no longer true."""
    process_events = [
        event for event in events if event.event_type in PROCESS_EVENT_TYPES
    ]
    if not process_events:
        return set()
    grouped: Dict[str, List[NotificationEvent]] = {}
    for event in process_events:
        grouped.setdefault(event.event_type, []).append(event)

    active = _scan_activity(process_events)
    active = _latest_active_per_object(active, process_events)
    active |= _rental_signal_activity(grouped)
    active |= _registration_signal_activity(grouped)
    active |= _license_activity(
        grouped.get('licenses.new_unconfirmed', []))
    active |= _new_video_activity(grouped.get('media_files.new_video', []))
    asset_events = [
        event for code in (
            'media_files.missing_reel', 'media_files.missing_cover')
        for event in grouped.get(code, [])
    ]
    active |= _missing_asset_activity(asset_events)
    active |= _plan_missing_video_activity(
        grouped.get('planung.plan_missing_video', []))
    active |= _media_operation_activity(
        grouped.get('media_files.operation_failed', []))
    active |= _exchange_import_activity(
        grouped.get('austausch.import_failed', []))
    active |= _tools_failure_activity(grouped.get('tools.job_failed', []))
    active = _supersede(
        active, grouped,
        'licenses.new_unconfirmed', 'licenses.unconfirmed_aging')
    active = _supersede(
        active, grouped,
        'registration.new_profile', 'registration.unverified_aging')
    return {event.pk for event in process_events} - active


def exclude_inactive_events(queryset):
    """Exclude resolved process events from an event queryset."""
    candidates = queryset.filter(event_type__in=PROCESS_EVENT_TYPES)
    return queryset.exclude(id__in=inactive_event_ids(candidates))


def exclude_inactive_action_items(queryset):
    """Exclude resolved process events from a UserNotification queryset."""
    candidates = NotificationEvent.objects.filter(
        id__in=queryset.values_list('event_id', flat=True),
        event_type__in=PROCESS_EVENT_TYPES,
    )
    return queryset.exclude(event_id__in=inactive_event_ids(candidates))


def refresh_missing_asset_events() -> int:
    """Store current cover/reel findings after plan or video changes."""
    from notifications import registry
    from notifications.services import emit

    created = 0
    for code in (
            'media_files.missing_reel',
            'media_files.missing_cover',
            'media_files.reel_post_today'):
        if not config.is_enabled(code):
            continue
        check = registry.get_check(code)
        if check is None:
            continue
        for finding in check(config.get_params(code)):
            event = emit(
                code,
                obj=finding.obj,
                payload=finding.payload,
                dedup_key=finding.dedup_key,
                occurred_at=finding.occurred_at,
            )
            if event is not None:
                created += 1
    return created
