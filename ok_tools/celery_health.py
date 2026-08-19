"""Detect and close out Celery tasks whose worker disappeared.

When a worker container is restarted (deploy, OOM kill) while it is running a
task, nothing writes a terminal state for that task: the ``TaskResult`` row
stays in ``PROGRESS``/``STARTED`` forever and every screen keeps reporting the
task as still running. These helpers ask the live workers which task ids they
actually hold and treat anything else that has been "running" for a while as
orphaned.
"""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import datetime
import json
import logging


logger = logging.getLogger(__name__)

# Celery states that claim a worker is holding the task right now. ``RETRY`` is
# included because a retry that was scheduled by a worker which then died is
# just as orphaned; a retry owned by a live worker shows up in ``scheduled()``.
RUNNING_STATES = ('STARTED', 'RECEIVED', 'RETRY', 'PROGRESS')

ORPHAN_TRACEBACK = (
    'OrphanedTask: the Celery worker that was running this task no longer '
    'exists (worker restart, deployment or OOM kill). No result was ever '
    'written, so the task has been closed as FAILURE by '
    'ok_tools.tasks.cleanup_stale_task_results_task.'
)


def get_live_task_ids(timeout=5.0):
    """Return the set of task ids currently held by live workers.

    Returns ``None`` when no worker answered at all — the broker may simply be
    unreachable, and failing every running task on a transient inspect error
    would be worse than leaving them alone.
    """
    from ok_tools.celery import app

    try:
        inspector = app.control.inspect(timeout=timeout)
        buckets = [inspector.active(), inspector.reserved(), inspector.scheduled()]
    except Exception as error:  # broker down, transport error, …
        logger.warning('Cannot inspect Celery workers: %s', error)
        return None

    task_ids = set()
    answered = False
    for bucket in buckets:
        if not bucket:
            continue
        for entries in bucket.values():
            answered = True
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                # scheduled() wraps the payload in {'eta': …, 'request': {…}}
                request = entry.get('request') if isinstance(entry.get('request'), dict) else entry
                task_id = request.get('id')
                if task_id:
                    task_ids.add(str(task_id))
    if not answered:
        logger.warning('No Celery worker answered the inspect ping; skipping orphan detection.')
        return None
    return task_ids


LIVE_TASK_IDS_CACHE_KEY = 'celery_health:live_task_ids'
LIVE_TASK_IDS_CACHE_TTL = 30


def get_live_task_ids_cached():
    """Cached ``get_live_task_ids`` for per-row checks in list views."""
    from django.core.cache import cache

    cached = cache.get(LIVE_TASK_IDS_CACHE_KEY)
    if cached is not None:
        return set(cached['ids']) if cached['ok'] else None
    task_ids = get_live_task_ids(timeout=2.0)
    cache.set(
        LIVE_TASK_IDS_CACHE_KEY,
        {'ok': task_ids is not None, 'ids': sorted(task_ids or ())},
        LIVE_TASK_IDS_CACHE_TTL,
    )
    return task_ids


def is_orphaned_task_result(task_result):
    """Whether this row claims to be running while its worker is gone."""
    from django.conf import settings

    if task_result.status not in RUNNING_STATES:
        return False
    created = task_result.date_created
    if not created:
        return False
    hint_minutes = getattr(settings, 'CELERY_STALE_TASK_HINT_MINUTES', 15)
    if created > timezone.now() - datetime.timedelta(minutes=hint_minutes):
        return False
    live_task_ids = get_live_task_ids_cached()
    if live_task_ids is None:
        return False
    return str(task_result.task_id) not in live_task_ids


def find_orphaned_task_results(older_than_minutes=60, live_task_ids=None):
    """Return TaskResult rows that claim to be running but have no live worker."""
    from django_celery_results.models import TaskResult

    if live_task_ids is None:
        return TaskResult.objects.none()

    cutoff = timezone.now() - datetime.timedelta(minutes=older_than_minutes)
    stale = TaskResult.objects.filter(
        status__in=RUNNING_STATES,
        date_created__lt=cutoff,
    ).exclude(task_id__in=live_task_ids)
    return stale.order_by('date_created')


def close_orphaned_task_result(task_result):
    """Mark one orphaned TaskResult as FAILURE with an explanatory traceback."""
    task_result.status = 'FAILURE'
    task_result.traceback = ORPHAN_TRACEBACK
    task_result.result = json.dumps({
        'exc_type': 'OrphanedTask',
        'exc_message': str(_('The worker running this task no longer exists.')),
        'orphaned': True,
    })
    task_result.date_done = timezone.now()
    task_result.save(update_fields=['status', 'traceback', 'result', 'date_done'])
    _close_related_export_run(task_result.task_id)


def _close_related_export_run(task_id):
    """Close an ExportToServerRun that was left open by the same orphaned task."""
    try:
        from austausch.models import ExportToServerRun
    except Exception:
        return
    for run in ExportToServerRun.objects.filter(completed_at__isnull=True).order_by('-started_at')[:50]:
        if (run.details or {}).get('task_id') != str(task_id):
            continue
        details = dict(run.details or {})
        details['error'] = str(_('The worker running this export no longer exists; '
                                 'the export was interrupted.'))
        details['orphaned'] = True
        run.details = details
        run.completed_at = timezone.now()
        run.save(update_fields=['details', 'completed_at'])


def cleanup_orphaned_task_results(older_than_minutes=60, dry_run=False):
    """Close out every orphaned TaskResult. Returns a summary dict."""
    live_task_ids = get_live_task_ids()
    if live_task_ids is None:
        return {'live_tasks': 0, 'orphaned': 0, 'closed': 0, 'skipped': True}

    orphans = list(find_orphaned_task_results(older_than_minutes, live_task_ids))
    closed = 0
    for task_result in orphans:
        logger.warning(
            'Closing orphaned Celery task %s (%s, status %s, created %s)',
            task_result.task_id, task_result.task_name, task_result.status,
            task_result.date_created,
        )
        if not dry_run:
            close_orphaned_task_result(task_result)
            closed += 1
    return {
        'live_tasks': len(live_task_ids),
        'orphaned': len(orphans),
        'closed': closed,
        'skipped': False,
    }
