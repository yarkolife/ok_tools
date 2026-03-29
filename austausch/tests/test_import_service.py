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
from media_files.models import StorageLocation
from media_files.models import VideoFile
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

    @patch('austausch.tasks.download_exchange_files_task.delay')
    @patch.object(ImportService, '_fetch_remote_metadata')
    def test_api_channel_maps_extended_remote_metadata_fields(self, mocked_metadata, mocked_delay):
        self._ensure_exchange_config()
        user, _profile = self._create_user_with_profile()

        remote_category = Category.objects.create(name='Remote Category')
        mocked_metadata.return_value = {
            'name': 'Remote API Title',
            'subtitle': 'Remote API Subtitle',
            'description': 'Remote API Description',
            'furtherPersons': 'Alice, Bob',
            'tags': ['alpha', 'beta', 'gamma'],
            'category': remote_category.name,
            'profile': 'Remote Author',
            'duration': '00:21:10',
            'repetitionsAllowed': True,
            'allowExchange': True,
            'allowExchangeOtherStates': True,
            'youthProtectionNecessary': True,
            'youthProtectionCategory': 'from_16',
            'saveToMediathek': True,
        }

        ExchangeChannelAuth.objects.create(
            channel_name='ok magdeburg',
            supports_oktools_api=True,
            metadata_api_base_url='https://portal.ok-magdeburg.de',
            metadata_api_token='secret-token',
            is_active=True,
        )

        item = ExchangeItem.objects.create(
            contribution_id=3740,
            filename='3740_video.mp4',
            file_path='/exchange/3740_video.mp4',
            channel='OK Magdeburg',
            title='Fallback Title',
            file_type='video',
            is_oktools_managed=True,
        )

        import_record, _ = ImportService(item, user).import_item()
        assert import_record.license is not None

        license_obj = import_record.license
        assert license_obj.title == 'Remote API Title'
        assert license_obj.subtitle == 'Remote API Subtitle'
        assert license_obj.description == 'Remote API Description'
        assert license_obj.further_persons == 'Alice, Bob'
        assert license_obj.tags == ['alpha', 'beta', 'gamma']
        assert license_obj.category.name == 'Remote Category'
        assert license_obj.duration.total_seconds() == 1270
        assert license_obj.repetitions_allowed is True
        assert license_obj.media_authority_exchange_allowed is True
        assert license_obj.media_authority_exchange_allowed_other_states is True
        assert license_obj.youth_protection_necessary is True
        assert license_obj.youth_protection_category == 'from_16'
        assert license_obj.store_in_ok_media_library is True
        assert license_obj.profile.first_name == 'Remote'
        assert license_obj.profile.last_name == 'Author'
        assert mocked_delay.call_count == 1

    @patch('austausch.tasks.download_exchange_files_task.delay')
    @patch.object(ImportService, '_fetch_remote_metadata')
    def test_api_channel_maps_nested_exchange_permissions(self, mocked_metadata, mocked_delay):
        self._ensure_exchange_config()
        user, _profile = self._create_user_with_profile()

        mocked_metadata.return_value = {
            'name': 'Nested API Title',
            'organization': {
                'bundesland': 'Sachsen-Anhalt',
                'bundesland_code': 'ST',
            },
            'license': {
                'allowExchange': True,
                'allowExchangeOtherStates': True,
            },
        }

        ExchangeChannelAuth.objects.create(
            channel_name='ok magdeburg',
            supports_oktools_api=True,
            metadata_api_base_url='https://portal.ok-magdeburg.de',
            metadata_api_token='secret-token',
            is_active=True,
        )

        item = ExchangeItem.objects.create(
            contribution_id=3741,
            filename='3741_video.mp4',
            file_path='/exchange/3741_video.mp4',
            channel='OK Magdeburg',
            title='Fallback Title',
            file_type='video',
            is_oktools_managed=True,
        )

        import_record, _ = ImportService(item, user).import_item()

        assert import_record.license is not None
        assert import_record.license.media_authority_exchange_allowed is True
        assert import_record.license.media_authority_exchange_allowed_other_states is True
        assert mocked_delay.call_count == 1


@pytest.mark.django_db
def test_create_video_file_reuses_scanned_record(tmp_path):
    config = ExchangeConfig.get_config()
    config.nextcloud_base_url = 'https://cloud.example.com'
    config.nextcloud_username = 'exchange'
    config.nextcloud_password = 'secret'
    config.download_storage_path = str(tmp_path)
    config.upload_server_path = 'GroupFolders/Test-Upload'
    config.save()

    user = create_user(
        {
            'email': 'scan-race@example.com',
            'first_name': 'Scan',
            'last_name': 'Race',
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
    profile = Profile.objects.get(okuser=user)
    category = Category.objects.create(name='Import Category')
    license_obj = License.objects.create(
        number=6123,
        title='Imported video',
        description='Existing license',
        profile=profile,
        category=category,
    )
    exchange_item = ExchangeItem.objects.create(
        contribution_id=6123,
        filename='6123_video.mp4',
        file_path='/exchange/6123_video.mp4',
        channel='ok magdeburg',
        title='Imported video',
        file_type='video',
        is_oktools_managed=True,
    )
    storage = StorageLocation.objects.create(
        name='Import Storage',
        storage_type='CUSTOM',
        path=str(tmp_path),
    )
    video_path = tmp_path / '6123_video.mp4'
    video_path.write_bytes(b'final-video-payload')

    scanned_video = VideoFile.objects.create(
        number=license_obj.number,
        filename=video_path.name,
        storage_location=storage,
        file_path=video_path.name,
        file_size=10,
        format='mp4',
        checksum='partial-checksum',
        is_available=True,
        video_codec='unknown',
        width=320,
        height=240,
    )

    service = ImportService(exchange_item, user)
    metadata = {
        'file_size': len(b'final-video-payload'),
        'format': 'mp4',
        'duration': None,
        'has_video': True,
        'video_codec': 'h264',
        'video_codec_long': 'H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10',
        'video_profile': 'High',
        'video_bitrate': 123456,
        'video_bitrate_mode': 'vbr',
        'fps': 25.0,
        'width': 1920,
        'height': 1080,
        'aspect_ratio': '16:9',
        'pixel_format': 'yuv420p',
        'color_space': 'bt709',
        'color_range': 'tv',
        'chroma_subsampling': '4:2:0',
        'has_audio': True,
        'audio_codec': 'aac',
        'audio_codec_long': 'AAC (Advanced Audio Coding)',
        'audio_bitrate': 128000,
        'audio_sample_rate': 48000,
        'audio_channels': 2,
        'audio_channel_layout': 'stereo',
        'total_bitrate': 251456,
    }

    with patch('media_files.utils.extract_video_metadata_fast', return_value=metadata), patch.object(
        ImportService,
        '_calculate_checksum',
        return_value='final-checksum',
    ):
        video_file = service._create_video_file(license_obj, str(video_path), storage)

    assert video_file.id == scanned_video.id
    assert VideoFile.objects.count() == 1

    video_file.refresh_from_db()
    assert video_file.license_id == license_obj.id
    assert video_file.checksum == 'final-checksum'
    assert video_file.file_size == len(b'final-video-payload')
    assert video_file.video_codec == 'h264'
    assert video_file.width == 1920
    assert video_file.height == 1080
