"""Service for exporting video, PDF, JSON and optional thumbnails to Nextcloud."""

import glob
import json
import logging
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from django.utils import timezone

from ..models import ExchangeConfig
from .nextcloud_exchange_service import NextcloudExchangeService

logger = logging.getLogger('django')

# Image extensions for thumbnail matching
THUMBNAIL_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def _safe_channel_name(name: str) -> str:
    """Normalize channel/media authority name for use in path (letters, digits, underscore)."""
    if not name:
        return 'unknown'
    s = name.strip().replace(' ', '_').replace('-', '_')
    s = re.sub(r'[^\w]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s or 'unknown'


def _safe_filename(original: str) -> str:
    """Sanitize filename for upload (German umlauts, spaces, invalid chars)."""
    german = {'ü': 'ue', 'Ü': 'Ue', 'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ß': 'ss'}
    s = original
    for char, replacement in german.items():
        s = s.replace(char, replacement)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.replace(' ', '_')
    s = re.sub(r'[^\w\-.]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_.')
    return s or 'file'


def _find_pdf_fallback(number: int, directory: str) -> Optional[str]:
    """Find PDF in directory by pattern {number}_*.pdf. Returns first match path or None."""
    if not directory or not os.path.isdir(directory):
        return None
    pattern = os.path.join(directory, f'{number}_*.pdf')
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def _find_pdf_in_paths(number: int, paths: List[Optional[str]]) -> Optional[str]:
    """Search for PDF in multiple directories (pattern {number}_*.pdf). Returns first match path or None."""
    for path in paths:
        if not path:
            continue
        found = _find_pdf_fallback(number, path.strip())
        if found:
            return found
    return None


def _find_thumbnail(number: int, directory: str) -> Optional[str]:
    """Find image in directory by pattern {number}_* with allowed image extension. Returns first match path or None."""
    if not directory or not os.path.isdir(directory):
        return None
    for ext in THUMBNAIL_EXTENSIONS:
        pattern = os.path.join(directory, f'{number}_*{ext}')
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


class ExportToServerService:
    """Upload video, PDF, JSON and optional thumbnail for selected contributions or licenses to Nextcloud."""

    def __init__(self, user=None):
        self.config = ExchangeConfig.get_config()
        self.user = user
        self.service = NextcloudExchangeService(self.config)

    def run(
        self,
        selected_ids: List[int],
        mode: str,
    ) -> Dict[str, Any]:
        """
        Export items to server.

        Args:
            selected_ids: List of contribution IDs (mode=contributions) or license numbers (mode=licenses).
            mode: 'contributions' or 'licenses'.

        Returns:
            Dict with: success_count, failure_count, skipped_no_pdf_count,
            success_ids, failed (list of {id, reason}), skipped_no_pdf (list of id).
        """
        report: Dict[str, Any] = {
            'success_count': 0,
            'failure_count': 0,
            'skipped_no_pdf_count': 0,
            'success_ids': [],
            'failed': [],
            'skipped_no_pdf': [],
        }
        if not self.config.upload_server_path:
            logger.error('Export to server: upload_server_path not configured')
            report['failure_count'] = len(selected_ids)
            report['failed'] = [{'id': i, 'reason': 'upload_server_path not configured'} for i in selected_ids]
            return report

        for item_id in selected_ids:
            try:
                status, out_id, reason = self._export_one(item_id, mode)
                if status == 'success':
                    report['success_count'] += 1
                    report['success_ids'].append(out_id)
                elif status == 'skipped_no_pdf':
                    report['skipped_no_pdf_count'] += 1
                    report['skipped_no_pdf'].append(out_id)
                else:
                    report['failure_count'] += 1
                    report['failed'].append({'id': out_id, 'reason': reason or 'unknown'})
            except Exception as e:
                logger.exception('Export to server failed for %s id=%s: %s', mode, item_id, e)
                report['failure_count'] += 1
                report['failed'].append({'id': item_id, 'reason': str(e)})
        return report

    def _export_one(self, item_id: int, mode: str) -> Tuple[str, int, Optional[str]]:
        """Export one item. Returns (status, item_id, reason): status is 'success'|'skipped_no_pdf'|'failure'."""
        from contributions.models import Contribution
        from licenses.models import License
        from licenses.serializers import LicenseMetadataSerializer
        from licenses.generate_file import generate_license_pdf_bytes, normalize_filename

        license_obj = None
        broadcast_date = None

        if mode == 'contributions':
            contribution = (
                Contribution.objects
                .select_related('license', 'license__profile', 'license__profile__media_authority')
                .filter(pk=item_id)
                .first()
            )
            if not contribution:
                logger.warning('Contribution id=%s not found', item_id)
                return ('failure', item_id, 'Contribution not found')
            license_obj = contribution.license
            broadcast_date = contribution.broadcast_date
        else:
            license_obj = (
                License.objects
                .select_related('profile', 'profile__media_authority')
                .filter(number=item_id)
                .first()
            )
            if not license_obj:
                logger.warning('License number=%s not found', item_id)
                return ('failure', item_id, 'License not found')
            broadcast_date = timezone.now()

        video_file = license_obj.get_video_file()
        if not video_file:
            logger.warning('License %s has no video file, skip export', license_obj.number)
            return ('failure', item_id, 'No video file')
        video_file.refresh_from_db()
        if getattr(video_file, 'storage_location', None) is None:
            logger.warning('License %s video has no storage_location', license_obj.number)
            return ('failure', item_id, 'Video has no storage location')

        # Channel and date folder
        media_authority = (
            getattr(license_obj.profile, 'media_authority', None)
            or self.config.default_media_authority
        )
        channel = _safe_channel_name(media_authority.name if media_authority else 'unknown')
        if mode == 'licenses':
            date_folder = timezone.now().strftime('%Y_%m_%d')
        else:
            date_folder = broadcast_date.strftime('%Y_%m_%d')

        base = self.config.upload_server_path.strip('/')
        remote_base_path = f'{base}/{channel}/{date_folder}/'
        number = license_obj.number

        # PDF is required: resolve before uploading anything (no PDF -> skip entire item)
        pdf_source: Optional[Union[bytes, str]] = None  # bytes = generated from signature, str = local path
        pdf_remote_name: Optional[str] = None
        if license_obj.signature:
            pdf_bytes = generate_license_pdf_bytes(license_obj)
            pdf_source = pdf_bytes
            pdf_remote_name = f'{number}_{normalize_filename(license_obj.title or "license")}.pdf'
        else:
            pdf_paths = [
                getattr(self.config, 'local_pdf_fallback_path', None) or '',
                getattr(self.config, 'local_pdf_fallback_path_2', None) or '',
            ]
            pdf_local = _find_pdf_in_paths(number, pdf_paths)
            if pdf_local and os.path.isfile(pdf_local):
                pdf_source = pdf_local
                pdf_remote_name = os.path.basename(pdf_local)
        if not pdf_source or not pdf_remote_name:
            logger.warning(
                'License %s: no PDF (no signature and no file in fallback paths), skip export',
                number,
            )
            return ('skipped_no_pdf', item_id, 'No PDF (no signature and no file in fallback paths)')

        if not self.service.ensure_directory(remote_base_path):
            logger.error('Failed to ensure directory %s', remote_base_path)
            return ('failure', item_id, 'Failed to create remote directory')

        video_local = video_file.full_path
        if not os.path.isfile(video_local):
            logger.error('Video file not found: %s', video_local)
            return ('failure', item_id, 'Video file not found')

        video_remote_name = f'{number}_{_safe_filename(video_file.filename)}'
        video_remote_path = f'{remote_base_path}{video_remote_name}'
        if not self.service.upload_file(video_local, video_remote_path):
            return ('failure', item_id, 'Video upload failed')

        # JSON metadata
        meta_data = LicenseMetadataSerializer(license_obj).data
        base_video_name = Path(video_file.filename).stem
        json_remote_name = f'{number}_{base_video_name}.meta.json'
        json_remote_path = f'{remote_base_path}{json_remote_name}'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.meta.json', delete=False) as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
            tmp_json = f.name
        try:
            if not self.service.upload_file(tmp_json, json_remote_path):
                return ('failure', item_id, 'JSON upload failed')
        finally:
            try:
                os.unlink(tmp_json)
            except OSError:
                pass

        # PDF (already resolved above)
        if isinstance(pdf_source, bytes):
            pdf_remote_path = f'{remote_base_path}{pdf_remote_name}'
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(pdf_source)
                tmp_pdf = f.name
            try:
                if not self.service.upload_file(tmp_pdf, pdf_remote_path):
                    return ('failure', item_id, 'PDF upload failed')
            finally:
                try:
                    os.unlink(tmp_pdf)
                except OSError:
                    pass
        else:
            if not self.service.upload_file(pdf_source, f'{remote_base_path}{pdf_remote_name}'):
                return ('failure', item_id, 'PDF upload failed')

        # Thumbnail
        if self.config.upload_thumbnail_enabled and self.config.thumbnail_storage_path:
            thumb_local = _find_thumbnail(number, self.config.thumbnail_storage_path)
            if thumb_local and os.path.isfile(thumb_local):
                thumb_remote_name = os.path.basename(thumb_local)
                self.service.upload_file(thumb_local, f'{remote_base_path}{thumb_remote_name}')

        logger.info('Exported license %s to %s', number, remote_base_path)
        return ('success', item_id, None)
