import pytest

from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from austausch.models import ExchangeConfig
from austausch.models import ExchangeItem
from austausch.views import ExchangeFeedView
from registration.models import OrganizationConfig


@pytest.mark.django_db
@override_settings(AUSTAUSCH_ENABLED=True)
class TestExchangeFeedVisibility(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        config = OrganizationConfig.get_config()
        config.bundesland = 'Sachsen-Anhalt'
        config.save()

    def _build_view(self):
        request = self.factory.get('/austausch/')
        request.user = type('User', (), {'is_authenticated': True, 'is_staff': True})()
        view = ExchangeFeedView()
        view.request = request
        view.kwargs = {}
        return view

    def test_shows_same_state_video_when_allow_exchange_true(self):
        visible = ExchangeItem.objects.create(
            filename='same-state.mp4',
            file_path='/exchange/same-state.mp4',
            channel='ok',
            file_type='video',
            allow_exchange=True,
            allow_exchange_other_states=False,
            bundesland='Sachsen-Anhalt',
            bundesland_code='ST',
        )
        ExchangeItem.objects.create(
            filename='same-state-hidden.mp4',
            file_path='/exchange/same-state-hidden.mp4',
            channel='ok',
            file_type='video',
            allow_exchange=False,
            allow_exchange_other_states=False,
            bundesland='Sachsen-Anhalt',
            bundesland_code='ST',
        )

        qs = self._build_view().get_queryset()

        self.assertQuerySetEqual(qs.order_by('id'), [visible], transform=lambda item: item)

    def test_shows_other_state_video_only_when_allow_exchange_other_states_true(self):
        visible = ExchangeItem.objects.create(
            filename='other-state.mp4',
            file_path='/exchange/other-state.mp4',
            channel='ok',
            file_type='video',
            allow_exchange=False,
            allow_exchange_other_states=True,
            bundesland='Sachsen',
            bundesland_code='SN',
        )
        ExchangeItem.objects.create(
            filename='other-state-hidden.mp4',
            file_path='/exchange/other-state-hidden.mp4',
            channel='ok',
            file_type='video',
            allow_exchange=True,
            allow_exchange_other_states=False,
            bundesland='Sachsen',
            bundesland_code='SN',
        )

        qs = self._build_view().get_queryset()

        self.assertQuerySetEqual(qs.order_by('id'), [visible], transform=lambda item: item)

    def test_shows_exception_channel_as_same_state_without_matching_bundesland_code(self):
        exchange_config = ExchangeConfig.get_config()
        exchange_config.nextcloud_base_url = 'https://cloud.example.com'
        exchange_config.nextcloud_username = 'exchange'
        exchange_config.nextcloud_password = 'secret'
        exchange_config.download_storage_path = '/tmp'
        exchange_config.upload_server_path = 'GroupFolders/Test-Upload'
        exchange_config.same_state_channel_exceptions = 'OK Magdeburg\nOK Dessau'
        exchange_config.save()

        visible = ExchangeItem.objects.create(
            filename='exception-channel.mp4',
            file_path='/exchange/exception-channel.mp4',
            channel='ok magdeburg',
            file_type='video',
            allow_exchange=True,
            allow_exchange_other_states=False,
            bundesland='Sachsen',
            bundesland_code='SN',
        )
        ExchangeItem.objects.create(
            filename='other-channel-hidden.mp4',
            file_path='/exchange/other-channel-hidden.mp4',
            channel='ok leipzig',
            file_type='video',
            allow_exchange=True,
            allow_exchange_other_states=False,
            bundesland='Sachsen',
            bundesland_code='SN',
        )

        qs = self._build_view().get_queryset()

        self.assertQuerySetEqual(qs.order_by('id'), [visible], transform=lambda item: item)
