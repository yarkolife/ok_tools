import pytest
from unittest.mock import patch

from austausch.models import ExchangeChannelAuth
from austausch.models import ExchangeConfig
from austausch.models import ExchangeItem
from austausch.models import ExchangeImport
from austausch.models import ImportedLicenseMapping
from austausch.services.import_service import ImportService
from licenses.models import Category
from licenses.models import License
from ok_tools.testing import create_user
from registration.models import Profile


@pytest.mark.django_db
class TestImportServiceIdentity:
    def _create_user_with_profile(self):
        user = create_user(
            {
                'email': 'importer@example.com',
                'first_name': 'Import',
                'last_name': 'User',
                'gender': 'none',
                'phone_number': '',
                'mobile_number': '',
                'birthday': '01.01.1990',
                'street': 'Teststreet',
                'house_number': '1',
                'zipcode': '12345',
                'city': 'Test City',
            },
            verified=True,
        )
        return user, Profile.objects.get(okuser=user)

    def _ensure_exchange_config(self):
        config = ExchangeConfig.get_config()
        config.nextcloud_base_url = 'https://cloud.example.com'
        config.nextcloud_username = 'exchange'
        config.nextcloud_password = 'secret'
        config.download_storage_path = '/tmp'
        config.upload_server_path = 'GroupFolders/Test-Upload'
        config.save()

    @patch('austausch.tasks.download_exchange_files_task.delay')
    def test_contribution_id_does_not_use_title_dedup(self, mocked_delay):
        self._ensure_exchange_config()
        user, profile = self._create_user_with_profile()
        category = Category.objects.create(name='Import Category')
        existing_license = License.objects.create(
            number=5000,
            title='Freiwillig in Magdeburg',
            description='Existing',
            duration='00:10:00',
            profile=profile,
            category=category,
        )

        item = ExchangeItem.objects.create(
            contribution_id=3738,
            filename='3738_video.mp4',
            file_path='/exchange/3738_video.mp4',
            channel='ok magdeburg',
            title='Freiwillig in Magdeburg',
            file_type='video',
            is_oktools_managed=True,
        )

        import_record, _duplicates = ImportService(item, user).import_item()

        assert import_record.license is not None
        assert import_record.license.id != existing_license.id
        assert import_record.status == 'pending_download'
        mocked_delay.assert_called_once()

    @patch('austausch.tasks.download_exchange_files_task.delay')
    @patch.object(ImportService, '_fetch_remote_metadata')
    def test_api_channel_reuses_mapping_for_same_remote_license(self, mocked_metadata, mocked_delay):
        self._ensure_exchange_config()
        user, _profile = self._create_user_with_profile()
        mocked_metadata.return_value = {
            'title': 'Remote Title',
            'description': 'Remote Description',
            'duration': '00:19:18',
        }

        ExchangeChannelAuth.objects.create(
            channel_name='ok magdeburg',
            supports_oktools_api=True,
            metadata_api_base_url='https://portal.ok-magdeburg.de',
            metadata_api_token='secret-token',
            is_active=True,
        )

        item1 = ExchangeItem.objects.create(
            contribution_id=3739,
            filename='3739_video.mp4',
            file_path='/exchange/3739_video.mp4',
            channel='OK Magdeburg',
            title='Freiwillig in Magdeburg',
            file_type='video',
            is_oktools_managed=True,
        )
        record1, _ = ImportService(item1, user).import_item()

        item2 = ExchangeItem.objects.create(
            contribution_id=3739,
            filename='3739_video_copy.mp4',
            file_path='/exchange/3739_video_copy.mp4',
            channel='ok magdeburg',
            title='Freiwillig in Magdeburg',
            file_type='video',
            is_oktools_managed=True,
        )
        record2, _ = ImportService(item2, user).import_item()

        assert record1.license is not None
        assert record2.license is not None
        assert record1.license_id == record2.license_id

        mappings = ImportedLicenseMapping.objects.filter(
            source_channel='ok magdeburg',
            remote_license_number=3739,
        )
        assert mappings.count() == 1
        assert mappings.first().local_license_id == record1.license_id

        assert ExchangeImport.objects.filter(status='pending_download').count() == 2
        assert mocked_metadata.call_count == 2
        assert mocked_delay.call_count == 2
