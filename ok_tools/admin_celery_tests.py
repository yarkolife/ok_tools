from django.test import SimpleTestCase
from ok_tools.admin_celery import PeriodicTaskAdmin
from ok_tools.admin_celery import ReadablePeriodicTaskNameFilter
from ok_tools.admin_celery import TaskResultAdmin
from ok_tools.admin_celery import _get_periodic_task_display_name


class CeleryAdminDisplayTests(SimpleTestCase):
    def test_periodic_task_name_uses_task_display_label(self):
        label = _get_periodic_task_display_name('auto_scan')

        self.assertEqual(str(label), 'Run automatic media scan')

    def test_periodic_task_result_filter_keeps_stored_query_parameter(self):
        self.assertEqual(ReadablePeriodicTaskNameFilter.parameter_name, 'periodic_task_name')

    def test_periodic_task_admin_replaces_raw_name_column(self):
        self.assertIn('readable_periodic_task_name', PeriodicTaskAdmin.list_display)
        self.assertNotIn('name', PeriodicTaskAdmin.list_display)

    def test_task_result_admin_replaces_raw_periodic_task_column(self):
        self.assertIn('readable_periodic_task_name', TaskResultAdmin.list_display)
        self.assertNotIn('periodic_task_name', TaskResultAdmin.list_display)


class CeleryTaskRouteTests(SimpleTestCase):
    def test_existing_long_running_routes_stay_isolated(self):
        from django.conf import settings

        self.assertEqual(
            settings.CELERY_TASK_ROUTES['licenses.tasks.download_nextcloud_video_file_to_storage']['queue'],
            'download',
        )
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['media_files.tasks.render_video_task']['queue'],
            'render',
        )

    def test_video_copy_uses_serial_copy_queue(self):
        from django.conf import settings

        self.assertEqual(
            settings.CELERY_TASK_ROUTES['media_files.tasks.copy_videos_for_plan']['queue'],
            'copy',
        )

    def test_anchor_render_uses_dedicated_external_queue(self):
        from django.conf import settings

        self.assertEqual(
            settings.CELERY_TASK_ROUTES['planung.tasks.anchor_render_chain']['queue'],
            'anchor_render',
        )
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['planung.tasks.poll_anchor_render_job']['queue'],
            'anchor_render',
        )
