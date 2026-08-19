"""Tests for orphaned-Celery-task detection."""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django_celery_results.models import TaskResult
from ok_tools import celery_health
from unittest import mock
import json
import uuid


def _task_result(status='PROGRESS', age_hours=20, task_id=None):
    task_id = task_id or str(uuid.uuid4())
    result = TaskResult.objects.create(
        task_id=task_id,
        task_name='austausch.tasks.export_to_server',
        status=status,
    )
    TaskResult.objects.filter(pk=result.pk).update(
        date_created=timezone.now() - timedelta(hours=age_hours),
    )
    result.refresh_from_db()
    return result


class GetLiveTaskIdsTests(TestCase):

    def _inspector(self, active=None, reserved=None, scheduled=None):
        inspector = mock.Mock()
        inspector.active.return_value = active
        inspector.reserved.return_value = reserved
        inspector.scheduled.return_value = scheduled
        return inspector

    def test_collects_ids_from_all_buckets(self):
        inspector = self._inspector(
            active={'w1': [{'id': 'a'}]},
            reserved={'w1': [{'id': 'b'}]},
            scheduled={'w1': [{'eta': 'x', 'request': {'id': 'c'}}]},
        )
        with mock.patch('ok_tools.celery.app.control.inspect', return_value=inspector):
            self.assertEqual(celery_health.get_live_task_ids(), {'a', 'b', 'c'})

    def test_returns_none_when_no_worker_answers(self):
        inspector = self._inspector()
        with mock.patch('ok_tools.celery.app.control.inspect', return_value=inspector):
            self.assertIsNone(celery_health.get_live_task_ids())

    def test_returns_none_when_broker_is_unreachable(self):
        with mock.patch('ok_tools.celery.app.control.inspect', side_effect=OSError('down')):
            self.assertIsNone(celery_health.get_live_task_ids())


class OrphanDetectionTests(TestCase):

    def test_running_task_without_live_worker_is_orphaned(self):
        result = _task_result()
        orphans = celery_health.find_orphaned_task_results(60, live_task_ids=set())
        self.assertIn(result, orphans)

    def test_task_held_by_a_worker_is_not_orphaned(self):
        result = _task_result()
        orphans = celery_health.find_orphaned_task_results(
            60, live_task_ids={result.task_id})
        self.assertNotIn(result, orphans)

    def test_recent_task_is_left_alone(self):
        result = _task_result(age_hours=0)
        orphans = celery_health.find_orphaned_task_results(60, live_task_ids=set())
        self.assertNotIn(result, orphans)

    def test_finished_task_is_left_alone(self):
        result = _task_result(status='SUCCESS')
        orphans = celery_health.find_orphaned_task_results(60, live_task_ids=set())
        self.assertNotIn(result, orphans)

    def test_no_worker_answer_changes_nothing(self):
        result = _task_result()
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=None):
            summary = celery_health.cleanup_orphaned_task_results()
        result.refresh_from_db()
        self.assertTrue(summary['skipped'])
        self.assertEqual(result.status, 'PROGRESS')

    def test_orphan_is_closed_as_failure(self):
        result = _task_result()
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=set()):
            summary = celery_health.cleanup_orphaned_task_results()
        result.refresh_from_db()
        self.assertEqual(summary['closed'], 1)
        self.assertEqual(result.status, 'FAILURE')
        self.assertIn('OrphanedTask', result.traceback)
        self.assertTrue(json.loads(result.result)['orphaned'])
        self.assertIsNotNone(result.date_done)

    def test_dry_run_changes_nothing(self):
        result = _task_result()
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=set()):
            summary = celery_health.cleanup_orphaned_task_results(dry_run=True)
        result.refresh_from_db()
        self.assertEqual(summary['orphaned'], 1)
        self.assertEqual(summary['closed'], 0)
        self.assertEqual(result.status, 'PROGRESS')

    def test_open_export_run_is_closed_with_the_task(self):
        from austausch.models import ExportToServerRun

        result = _task_result()
        run = ExportToServerRun.objects.create(
            mode='licenses', total_count=4, details={'task_id': result.task_id},
        )
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=set()):
            celery_health.cleanup_orphaned_task_results()
        run.refresh_from_db()
        self.assertIsNotNone(run.completed_at)
        self.assertTrue(run.details['orphaned'])
        self.assertIn('error', run.details)


class OrphanHintTests(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.delete(celery_health.LIVE_TASK_IDS_CACHE_KEY)

    def test_hint_for_old_task_without_worker(self):
        result = _task_result()
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=set()):
            self.assertTrue(celery_health.is_orphaned_task_result(result))

    def test_no_hint_while_task_is_still_young(self):
        result = _task_result(age_hours=0)
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=set()):
            self.assertFalse(celery_health.is_orphaned_task_result(result))

    def test_no_hint_when_workers_cannot_be_inspected(self):
        result = _task_result()
        with mock.patch.object(celery_health, 'get_live_task_ids', return_value=None):
            self.assertFalse(celery_health.is_orphaned_task_result(result))
