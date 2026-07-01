"""Tests for the Reel Studio integration (OKMQ reel renderer)."""

from datetime import date
from datetime import time
from datetime import timedelta
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from licenses.models import default_category
from ok_tools.testing import create_license
from ok_tools.testing import create_user
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
        self.assertContains(resp, 'id="customHookBuilder"')
        self.assertContains(resp, 'id="custom_hook_zeile1"')
        self.assertContains(resp, 'id="custom_hook_zeile2"')
        self.assertNotContains(resp, 'id="btnUseCustomHook"')
        self.assertContains(resp, 'searchMediaByNumber()')

    def test_prefill_from_query(self):
        _configure_reel()
        resp = self.client.get(
            reverse('tools:reel_studio'),
            {'video': 'playout/x.mp4', 'title': 'My Title'})
        self.assertEqual(resp.context['prefill']['video'], 'playout/x.mp4')
        self.assertEqual(resp.context['prefill']['title'], 'My Title')

    @override_settings(MEDIA_FILES_ENABLED=True, PLANUNG_ENABLED=True)
    def test_prefill_from_selected_video_license_and_plan(self):
        if not apps.is_installed('media_files'):
            self.skipTest('media_files app is not installed')
        if not apps.is_installed('planung'):
            self.skipTest('planung app is not installed')

        from media_files.models import StorageLocation
        from media_files.models import VideoFile
        from planung.models import TagesPlan

        _configure_reel()
        producer = create_user(
            {
                'email': 'producer@example.com',
                'first_name': 'Klaus',
                'last_name': 'Treuter',
                'gender': 'm',
                'phone_number': '',
                'mobile_number': '',
                'birthday': '01.01.1980',
                'street': 'Main',
                'house_number': '1',
                'zipcode': '12345',
                'city': 'Merseburg',
            },
            verified=True,
        )
        category = default_category()
        category_name = str(category.name)
        license_obj = create_license(
            producer.profile,
            {
                'category': category,
                'title': 'Festumzug Merseburg 2026',
                'subtitle': 'Merseburg Report',
                'description': 'Der Festumzug zum Schlossfest.',
                'further_persons': '',
                'duration': timedelta(minutes=20),
                'suggested_date': None,
                'repetitions_allowed': True,
                'media_authority_exchange_allowed': True,
                'youth_protection_necessary': False,
                'store_in_ok_media_library': True,
            },
        )
        storage = StorageLocation.objects.create(
            name='Playout',
            storage_type='PLAYOUT',
            path='/tmp',
            is_active=True,
        )
        video = VideoFile.objects.create(
            number=license_obj.number,
            filename=f'{license_obj.number}_Beitrag.mp4',
            storage_location=storage,
            file_path=f'2026_KW_24/{license_obj.number}_Beitrag.mp4',
            duration=timedelta(minutes=21),
            license=license_obj,
        )
        TagesPlan.objects.create(
            datum=date(2026, 2, 10),
            json_plan={
                'items': [
                    {
                        'number': license_obj.number,
                        'start': '18:30:00',
                        'duration': 1200,
                    },
                ],
            },
        )

        resp = self.client.get(reverse('tools:reel_studio'), {'video_id': video.id})

        prefill = resp.context['prefill']
        self.assertEqual(prefill['title'], 'Festumzug Merseburg 2026')
        self.assertEqual(prefill['sendung'], category_name)
        self.assertEqual(prefill['autor'], 'Klaus Treuter')
        self.assertEqual(prefill['description'], 'Der Festumzug zum Schlossfest.')
        self.assertEqual(prefill['se_tag'], 'Dienstag, 10.02.')
        self.assertEqual(prefill['se_uhr'], '18:30')
        self.assertEqual(prefill['output_name'], f'{license_obj.number}_Programmvorschau_Reel_260210')
        self.assertEqual(prefill['dauer'], '1260')

        lookup = self.client.get(
            reverse('tools:api_reel_license_prefill', args=[license_obj.number]))
        self.assertEqual(lookup.status_code, 200)
        lookup_prefill = lookup.json()['prefill']
        self.assertEqual(lookup_prefill['title'], 'Festumzug Merseburg 2026')
        self.assertEqual(lookup_prefill['sendung'], category_name)
        self.assertEqual(lookup_prefill['se_tag'], 'Dienstag, 10.02.')
        self.assertEqual(lookup_prefill['se_uhr'], '18:30')
        self.assertEqual(lookup_prefill['dauer'], '1260')
        self.assertEqual(lookup_prefill['video_id'], video.id)

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


@override_settings(
    TOOLS_ENABLED=True,
    MEDIA_FILES_ENABLED=True,
    PLANUNG_ENABLED=True,
    SITE_BASE_URL='https://portal.example',
    LANGUAGE_CODE='de',
)
class DailyReelReminderTest(TestCase):
    """Daily reel reminder email uses planning metadata and schedule order."""

    def setUp(self):
        if not apps.is_installed('media_files'):
            self.skipTest('media_files app is not installed')
        if not apps.is_installed('planung'):
            self.skipTest('planung app is not installed')

        from media_files.models import StorageLocation

        self.storage = StorageLocation.objects.create(
            name='Reel Output',
            storage_type='PLAYOUT',
            path='/tmp',
            is_active=True,
        )
        _configure_reel(
            reel_output_storage=self.storage,
            reel_reminder_enabled=True,
            reel_reminder_recipient_email='social@example.com',
            reel_reminder_time=time(9, 15),
        )

    def _license(self, email, title, tags=None, mediathek_url=''):
        producer = create_user(
            {
                'email': email,
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'gender': 'f',
                'phone_number': '',
                'mobile_number': '',
                'birthday': '01.01.1980',
                'street': 'Main',
                'house_number': '1',
                'zipcode': '12345',
                'city': 'Merseburg',
            },
            verified=True,
        )
        license_obj = create_license(
            producer.profile,
            {
                'category': default_category(),
                'title': title,
                'subtitle': '',
                'description': 'Description',
                'further_persons': '',
                'duration': timedelta(minutes=20),
                'suggested_date': None,
                'repetitions_allowed': True,
                'media_authority_exchange_allowed': True,
                'youth_protection_necessary': False,
                'store_in_ok_media_library': True,
            },
        )
        license_obj.tags = tags or []
        license_obj.mediathek_url = mediathek_url
        license_obj.save(update_fields=['tags', 'mediathek_url'])
        return license_obj

    def _reel_video(self, license_obj, filename):
        from media_files.models import VideoFile

        return VideoFile.objects.create(
            number=license_obj.number,
            filename=filename,
            storage_location=self.storage,
            file_path=filename,
            license=None,
            is_preview=True,
            is_available=True,
        )

    def test_context_sorts_by_first_planning_time_and_keeps_other_times(self):
        from planung.models import TagesPlan
        from tools.tasks import build_daily_reel_reminder_context

        plan_date = date(2026, 7, 4)
        first = self._license(
            'first@example.com',
            'First Title',
            tags=['Tag A', 'Tag B'],
            mediathek_url='https://lokalmedial.example/w/first',
        )
        second = self._license('second@example.com', 'Second Title')
        self._reel_video(first, f'{first.number}_Reel_260704.mp4')
        self._reel_video(second, f'{second.number}_Reel_260704.mp4')
        TagesPlan.objects.create(
            datum=plan_date,
            json_plan={
                'items': [
                    {'number': second.number, 'start': '09:30:00'},
                    {'number': first.number, 'start': '11:00:00'},
                    {
                        'number': first.number,
                        'start': '08:00:00',
                        'sender_responsible': 'Plan Sender',
                    },
                ],
            },
        )

        context = build_daily_reel_reminder_context(plan_date)

        self.assertEqual([item['number'] for item in context['reels']], [first.number, second.number])
        self.assertEqual(context['reels'][0]['start_time'], '08:00')
        self.assertEqual(context['reels'][0]['other_times'], ['11:00'])
        self.assertEqual(context['reels'][0]['title'], 'First Title')
        self.assertEqual(context['reels'][0]['sender_responsible'], 'Plan Sender')
        self.assertEqual(context['reels'][0]['tags'], ['Tag A', 'Tag B'])
        self.assertEqual(context['reels'][0]['mediathek_url'], 'https://lokalmedial.example/w/first')
        self.assertIn('token=', context['reels'][0]['download_url'])

    def test_context_warns_when_reel_has_no_planning_entry(self):
        from tools.tasks import build_daily_reel_reminder_context

        plan_date = date(2026, 7, 4)
        license_obj = self._license('missing-plan@example.com', 'Missing Plan')
        self._reel_video(license_obj, f'{license_obj.number}_Reel_260704.mp4')

        context = build_daily_reel_reminder_context(plan_date)

        self.assertEqual(context['reels'][0]['start_time'], '')
        self.assertIn('Sendezeit oder Reel prüfen', str(context['reels'][0]['warnings'][0]))

    def test_task_sends_email_with_links_after_tags(self):
        from planung.models import TagesPlan
        from tools.tasks import send_daily_reel_reminder

        plan_date = date(2026, 7, 4)
        license_obj = self._license(
            'email-order@example.com',
            'Email Order',
            tags=['Selbstbestimmung'],
            mediathek_url='https://lokalmedial.example/w/order',
        )
        self._reel_video(license_obj, f'{license_obj.number}_Reel_260704.mp4')
        TagesPlan.objects.create(
            datum=plan_date,
            json_plan={'items': [{'number': license_obj.number, 'start': '09:00:00'}]},
        )

        result = send_daily_reel_reminder(plan_date.isoformat())

        self.assertEqual(result['status'], 'sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['social@example.com'])
        body = mail.outbox[0].body
        self.assertLess(body.index('Tags:'), body.index('Reel-Download:'))
        self.assertLess(body.index('Reel-Download:'), body.index('Mediathek:'))


@override_settings(TOOLS_ENABLED=True)
class LicenseReelActionTest(TestCase):
    """License admin action visibility and prefill redirect."""

    def test_reel_enabled_helper(self):
        from licenses.admin import LicenseAdmin
        self.assertFalse(LicenseAdmin._reel_enabled())
        _configure_reel()
        self.assertTrue(LicenseAdmin._reel_enabled())
