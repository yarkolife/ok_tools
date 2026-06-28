"""Tests for the Reel Studio integration (OKMQ reel renderer)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.models import ToolsConfig
from tools.services import okmq_reel
from unittest import mock


def _configure_reel(**overrides):
    """Configure ToolsConfig so the reel service counts as enabled."""
    config = ToolsConfig.get_config()
    config.reel_studio_enabled = True
    config.reel_render_url = 'http://reel.example:8011'
    config.reel_render_api_key = 'secret-key'
    for k, v in overrides.items():
        setattr(config, k, v)
    config.save()
    return config


@override_settings(TOOLS_ENABLED=True)
class IsReelConfiguredTest(TestCase):
    """The is_reel_configured() gate requires enabled + url + key."""

    def test_disabled_by_default(self):
        self.assertFalse(ToolsConfig.get_config().is_reel_configured())

    def test_enabled_but_no_url(self):
        config = ToolsConfig.get_config()
        config.reel_studio_enabled = True
        config.reel_render_api_key = 'k'
        config.save()
        self.assertFalse(config.is_reel_configured())

    def test_fully_configured(self):
        self.assertTrue(_configure_reel().is_reel_configured())

    def test_flag_off_disables(self):
        config = _configure_reel(reel_studio_enabled=False)
        self.assertFalse(config.is_reel_configured())


@override_settings(TOOLS_ENABLED=True)
class ReelStudioViewTest(TestCase):
    """Page gating + prefill."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            email='staff@example.com', password='pw', is_staff=True)
        self.client.force_login(self.staff)

    def test_404_when_not_configured(self):
        resp = self.client.get(reverse('tools:reel_studio'))
        self.assertEqual(resp.status_code, 404)

    def test_200_when_configured(self):
        _configure_reel()
        resp = self.client.get(reverse('tools:reel_studio'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="mediaNumber"')
        self.assertContains(resp, 'searchMediaByNumber()')

    def test_prefill_from_query(self):
        _configure_reel()
        resp = self.client.get(
            reverse('tools:reel_studio'),
            {'video': 'playout/x.mp4', 'title': 'My Title'})
        self.assertEqual(resp.context['prefill']['video'], 'playout/x.mp4')
        self.assertEqual(resp.context['prefill']['title'], 'My Title')

    def test_index_card_hidden_when_disabled(self):
        resp = self.client.get(reverse('tools:index'))
        self.assertNotContains(resp, reverse('tools:reel_studio'))

    def test_index_card_shown_when_configured(self):
        _configure_reel()
        resp = self.client.get(reverse('tools:index'))
        self.assertContains(resp, reverse('tools:reel_studio'))


@override_settings(TOOLS_ENABLED=True)
class ReelApiTest(TestCase):
    """API endpoint validation and task-status mapping."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            email='staff2@example.com', password='pw', is_staff=True)
        self.client.force_login(self.staff)
        _configure_reel()

    def test_hooks_requires_valid_type(self):
        resp = self.client.post(
            reverse('tools:api_reel_hooks'),
            data={'title': 'T', 'hook_type': 'nope'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('tools.tasks.okmq_generate_hooks_task.delay')
    def test_hooks_enqueues_task(self, delay):
        delay.return_value = mock.Mock(id='task-123')
        resp = self.client.post(
            reverse('tools:api_reel_hooks'),
            data={'title': 'T', 'hook_type': 'frage'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()['task_id'], 'task-123')
        delay.assert_called_once()

    @mock.patch('tools.tasks.okmq_generate_hooks_task.delay')
    def test_hooks_accepts_sachlich_type(self, delay):
        delay.return_value = mock.Mock(id='task-sachlich')
        resp = self.client.post(
            reverse('tools:api_reel_hooks'),
            data={'title': 'T', 'hook_type': 'sachlich'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 202)
        _, kwargs = delay.call_args
        self.assertEqual(kwargs['hook_type'], 'sachlich')

    def test_render_requires_fields(self):
        resp = self.client.post(
            reverse('tools:api_reel_render'),
            data={'video': 'x.mp4'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('tools.tasks.okmq_render_reel_task.delay')
    def test_render_enqueues_task(self, delay):
        delay.return_value = mock.Mock(id='task-render')
        resp = self.client.post(
            reverse('tools:api_reel_render'),
            data={
                'video': 'playout/x.mp4',
                'hook': {'zeile1': 'a', 'zeile2': 'b'},
                'hook_type': 'frage',
                'output_name': 'out',
            },
            content_type='application/json')
        self.assertEqual(resp.status_code, 202)
        delay.assert_called_once()
        # payload mapping
        _, kwargs = delay.call_args
        self.assertEqual(kwargs['payload']['hook_type'], 'frage')

    def test_404_when_not_configured(self):
        ToolsConfig.get_config().__class__.objects.update(reel_studio_enabled=False)
        resp = self.client.get(reverse('tools:api_reel_cta'))
        self.assertEqual(resp.status_code, 404)

    @mock.patch('tools.api._reel_task_status')
    def test_task_status_passthrough(self, status_fn):
        status_fn.return_value = {'task_id': 'x', 'state': 'done', 'result': {'file': 'f'}}
        resp = self.client.get(reverse('tools:api_reel_task', args=['x']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['state'], 'done')


class OkmqReelClientTest(TestCase):
    """Client builds requests correctly and maps the camelCase hookType."""

    def setUp(self):
        _configure_reel()

    def test_auto_start_seconds(self):
        # middle minus half the reel length (15/2)
        self.assertEqual(okmq_reel.auto_start_seconds(620), 302.5)
        self.assertEqual(okmq_reel.auto_start_seconds(5), 0.0)

    @mock.patch('tools.services.okmq_reel._session')
    def test_start_reel_maps_hooktype_camelcase(self, session):
        session.post.return_value = mock.Mock(
            status_code=200, ok=True,
            json=mock.Mock(return_value={'job_id': 'j1'}))
        job_id = okmq_reel.start_reel(
            video='v.mp4', hook={'zeile1': 'a', 'zeile2': 'b'},
            hook_type='naehe', output_name='o')
        self.assertEqual(job_id, 'j1')
        _, kwargs = session.post.call_args
        self.assertEqual(kwargs['json']['hookType'], 'naehe')
        self.assertEqual(kwargs['headers']['X-API-Key'], 'secret-key')

    @mock.patch('tools.services.okmq_reel._session')
    def test_unreachable_raises(self, session):
        import requests
        session.get.side_effect = requests.RequestException('boom')
        with self.assertRaises(okmq_reel.OkmqError):
            okmq_reel.list_cta('frage')


@override_settings(TOOLS_ENABLED=True, MEDIA_FILES_ENABLED=True)
class ReelRenderRecordTest(TestCase):
    """Rendered reels are registered as non-version preview clips."""

    def test_record_rendered_reel_marks_video_as_preview(self):
        from media_files.models import StorageLocation
        from media_files.models import VideoFile
        from tools.tasks import _record_rendered_reel_video

        with TemporaryDirectory() as tmpdir:
            storage = StorageLocation.objects.create(
                name='Reel Output',
                storage_type='PLAYOUT',
                path=tmpdir,
                is_active=True)
            Path(tmpdir, '18480_Reel_260627.mp4').write_bytes(b'reel')
            _configure_reel(reel_output_storage=storage)

            _record_rendered_reel_video({}, {'file': '18480_Reel_260627.mp4'})

            video = VideoFile.objects.get(number=18480)
            self.assertTrue(video.is_preview)
            self.assertEqual(video.filename, '18480_Reel_260627.mp4')


@override_settings(TOOLS_ENABLED=True)
class LicenseReelActionTest(TestCase):
    """License admin action visibility and prefill redirect."""

    def test_reel_enabled_helper(self):
        from licenses.admin import LicenseAdmin
        self.assertFalse(LicenseAdmin._reel_enabled())
        _configure_reel()
        self.assertTrue(LicenseAdmin._reel_enabled())
