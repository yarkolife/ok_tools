"""Service for exporting video, PDF, JSON and optional thumbnails to configured destination."""

import fcntl
import glob
import json
import logging
import os
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import models
from django.utils import timezone

from ..models import ExchangeConfig, ExportedLicense
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
    """Export video, PDF, JSON and optional thumbnail for selected contributions or licenses."""

    def __init__(self, user=None):
        self.config = ExchangeConfig.get_config()
        self.user = user
        self.destination = getattr(self.config, 'export_destination', 'nextcloud')
        self.service = NextcloudExchangeService(self.config) if self.destination == 'nextcloud' else None
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set callback for progress updates during file uploads.

        Callback receives: (chunk_num, total_chunks, percent)
        """
        self._progress_callback = callback

    def _record_exported_license(self, license_number: int) -> None:
        """Record successful export in ExportedLicense table."""
        try:
            obj, created = ExportedLicense.objects.get_or_create(
                license_number=license_number,
                defaults={'export_count': 1}
            )
            if not created:
                # Increment export_count
                ExportedLicense.objects.filter(license_number=license_number).update(
                    export_count=models.F('export_count') + 1
                )
        except Exception:
            # Don't fail export if recording fails
            logger.exception('Failed to record exported license %s', license_number)

    def _network_share_export_dir(self) -> str:
        """Return absolute export directory for network share destination."""
        base_path = (getattr(self.config, 'network_share_base_path', '') or '').strip()
        subfolder = (getattr(self.config, 'network_share_subfolder', '') or '').strip().strip('/\\')
        if subfolder:
            return os.path.join(base_path, subfolder)
        return base_path

    def _validate_destination(self, selected_ids: List[int], report: Dict[str, Any]) -> bool:
        """Validate export destination settings and return False if invalid."""
        if self.destination == 'nextcloud':
            if not self.config.upload_server_path:
                logger.error('Export to server: upload_server_path not configured')
                report['failure_count'] = len(selected_ids)
                report['failed'] = [{'id': i, 'reason': 'upload_server_path not configured'} for i in selected_ids]
                return False
            return True

        if self.destination == 'network_share':
            export_dir = self._network_share_export_dir()
            if not export_dir:
                logger.error('Export to server: network_share_base_path not configured')
                report['failure_count'] = len(selected_ids)
                report['failed'] = [{'id': i, 'reason': 'network_share_base_path not configured'} for i in selected_ids]
                return False
            if not os.path.isdir(export_dir):
                logger.error('Export to server: network share export path does not exist: %s', export_dir)
                report['failure_count'] = len(selected_ids)
                report['failed'] = [{'id': i, 'reason': f'Network share path not found: {export_dir}'} for i in selected_ids]
                return False
            return True

        logger.error('Export to server: unknown destination: %s', self.destination)
        report['failure_count'] = len(selected_ids)
        report['failed'] = [{'id': i, 'reason': f'Unknown export destination: {self.destination}'} for i in selected_ids]
        return False

    @staticmethod
    def _write_bytes_atomic(file_path: str, data: bytes) -> bool:
        """Write bytes atomically using temporary file and replace."""
        tmp_path = None
        target_dir = os.path.dirname(file_path)
        try:
            os.makedirs(target_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target_dir, prefix='.tmp_', delete=False) as tmp:
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name
            os.replace(tmp_path, file_path)
            return True
        except Exception:
            logger.exception('Failed to atomically write file: %s', file_path)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return False

    @staticmethod
    def _copy_file_atomic(source_path: str, target_path: str) -> bool:
        """Copy file atomically using temporary file and replace."""
        tmp_path = None
        target_dir = os.path.dirname(target_path)
        try:
            os.makedirs(target_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target_dir, prefix='.tmp_', delete=False) as tmp:
                tmp_path = tmp.name
            shutil.copy2(source_path, tmp_path)
            os.replace(tmp_path, target_path)
            return True
        except Exception:
            logger.exception('Failed to atomically copy file %s -> %s', source_path, target_path)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return False

    def _build_windows_files_txt_entry(self, filename: str) -> str:
        """Build files.txt line using configured windows root path."""
        windows_root = (getattr(self.config, 'network_share_windows_root', '') or '').strip()
        if windows_root:
            windows_root = windows_root.rstrip('\\/')
            full_path = f'{windows_root}\\{filename}'
        else:
            full_path = filename
        return f'"{full_path}"'

    def _append_to_files_txt(self, export_dir: str, filename: str) -> bool:
        """Append one line to files.txt with locking to avoid mixed writes between workers."""
        files_txt_path = os.path.join(export_dir, 'files.txt')
        line = self._build_windows_files_txt_entry(filename)
        try:
            os.makedirs(export_dir, exist_ok=True)
            with open(files_txt_path, 'a+', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.seek(0, os.SEEK_END)
                    f.write(f'{line}\n')
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return True
        except Exception:
            logger.exception('Failed to append files.txt entry for %s', filename)
            return False

    def _upload_or_copy_file(self, local_path: str, remote_base_path: str, file_name: str) -> bool:
        """Upload to Nextcloud or copy to network share based on destination."""
        if self.destination == 'nextcloud':
            remote_path = f'{remote_base_path}{file_name}'
            return self.service.upload_file_direct(local_path, remote_path, self._progress_callback)

        export_dir = remote_base_path
        target_path = os.path.join(export_dir, file_name)
        if not self._copy_file_atomic(local_path, target_path):
            return False
        return self._append_to_files_txt(export_dir, file_name)

    def _write_json_to_destination(self, meta_data: Dict[str, Any], remote_base_path: str, json_file_name: str) -> bool:
        """Write JSON metadata to destination."""
        if self.destination == 'nextcloud':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.meta.json', delete=False) as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
                tmp_json = f.name
            try:
                return self._upload_or_copy_file(tmp_json, remote_base_path, json_file_name)
            finally:
                try:
                    os.unlink(tmp_json)
                except OSError:
                    pass

        payload = json.dumps(meta_data, ensure_ascii=False, indent=2).encode('utf-8')
        target_path = os.path.join(remote_base_path, json_file_name)
        if not self._write_bytes_atomic(target_path, payload):
            return False
        return self._append_to_files_txt(remote_base_path, json_file_name)

    def _write_pdf_to_destination(
        self,
        pdf_source: Union[bytes, str],
        remote_base_path: str,
        pdf_remote_name: str,
    ) -> bool:
        """Write PDF to destination."""
        if isinstance(pdf_source, bytes):
            if self.destination == 'nextcloud':
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(pdf_source)
                    tmp_pdf = f.name
                try:
                    return self._upload_or_copy_file(tmp_pdf, remote_base_path, pdf_remote_name)
                finally:
                    try:
                        os.unlink(tmp_pdf)
                    except OSError:
                        pass

            target_path = os.path.join(remote_base_path, pdf_remote_name)
            if not self._write_bytes_atomic(target_path, pdf_source):
                return False
            return self._append_to_files_txt(remote_base_path, pdf_remote_name)

        return self._upload_or_copy_file(pdf_source, remote_base_path, pdf_remote_name)

    def run(
        self,
        selected_ids: List[int],
        mode: str,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Export items to server.

        Args:
            selected_ids: List of contribution IDs (mode=contributions) or license numbers (mode=licenses).
            mode: 'contributions' or 'licenses'.
            progress_callback: Optional callback function(current, total, status, item_id) for progress updates.

        Returns:
            Dict with: success_count, failure_count, skipped_no_pdf_count,
            success_ids, failed (list of {id, reason}), skipped_no_pdf (list of id).
        """
        report: Dict[str, Any] = {
            'success_count': 0,
            'failure_count': 0,
            'skipped_no_pdf_count': 0,
            'success_ids': [],
            'success_license_numbers': [],
            'failed': [],
            'skipped_no_pdf': [],
        }
        if not self._validate_destination(selected_ids, report):
            return report

        total = len(selected_ids)
        for idx, item_id in enumerate(selected_ids, start=1):
            # Report progress before processing each item
            if progress_callback:
                progress_callback(idx, total, 'processing', item_id)

            try:
                status, out_id, reason = self._export_one(item_id, mode)
                if status == 'success':
                    report['success_count'] += 1
                    report['success_ids'].append(out_id)
                    # Record the license number for duplicate prevention
                    if mode == 'contributions':
                        # Get license number from contribution
                        from contributions.models import Contribution
                        contribution = Contribution.objects.filter(pk=item_id).first()
                        if contribution and contribution.license:
                            report['success_license_numbers'].append(contribution.license.number)
                            self._record_exported_license(contribution.license.number)
                    else:
                        # mode == 'licenses', item_id is already the license number
                        report['success_license_numbers'].append(out_id)
                        self._record_exported_license(out_id)
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

        # Report final progress
        if progress_callback:
            progress_callback(total, total, 'completed', None)

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

        # Upload directly into configured path (no channel/date subfolders)
        if self.destination == 'nextcloud':
            base = self.config.upload_server_path.strip('/')
            remote_base_path = f'{base}/'
        else:
            remote_base_path = self._network_share_export_dir()

        number = license_obj.number

        # PDF is required: resolve before uploading anything (no PDF -> skip entire item)
        pdf_source: Optional[Union[bytes, str]] = None  # bytes = generated from signature, str = local path
        pdf_remote_name: Optional[str] = None
        has_signature = False
        if hasattr(license_obj, 'has_any_signature') and license_obj.has_any_signature():
            has_signature = True
        elif license_obj.signature or getattr(license_obj, 'signature_svg', None) or getattr(license_obj, 'signature_points', None):
            has_signature = True

        if has_signature:
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

        if self.destination == 'nextcloud':
            if not self.service.ensure_directory(remote_base_path):
                logger.error('Failed to ensure directory %s', remote_base_path)
                return ('failure', item_id, 'Failed to create remote directory')
        else:
            try:
                os.makedirs(remote_base_path, exist_ok=True)
            except Exception:
                logger.exception('Failed to create network share directory %s', remote_base_path)
                return ('failure', item_id, 'Failed to create network share directory')

        video_local = video_file.full_path
        if not os.path.isfile(video_local):
            logger.error('Video file not found: %s', video_local)
            return ('failure', item_id, 'Video file not found')

        video_remote_name = _safe_filename(video_file.filename)
        if not self._upload_or_copy_file(video_local, remote_base_path, video_remote_name):
            return ('failure', item_id, 'Video upload failed')

        # JSON metadata
        meta_data = LicenseMetadataSerializer(license_obj).data
        base_video_name = Path(video_file.filename).stem
        json_remote_name = f'{_safe_filename(base_video_name)}.meta.json'
        if not self._write_json_to_destination(meta_data, remote_base_path, json_remote_name):
            return ('failure', item_id, 'JSON upload failed')

        # PDF (already resolved above)
        if not self._write_pdf_to_destination(pdf_source, remote_base_path, pdf_remote_name):
            return ('failure', item_id, 'PDF upload failed')

        # Auto-generate a cover into the hand-off directory so the thumbnail
        # block below can upload it. Failure here must never fail the export.
        if self.config.upload_thumbnail_enabled and self.config.thumbnail_storage_path:
            try:
                from media_files.covers.config import get_cover_config
                from media_files.covers.service import generate_cover
                cover_config = get_cover_config()
                if cover_config.enabled:
                    generate_cover(video_file, config=cover_config)
            except Exception:
                logger.exception('Cover generation failed for license %s', number)

        # Thumbnail
        if self.config.upload_thumbnail_enabled and self.config.thumbnail_storage_path:
            thumb_local = _find_thumbnail(number, self.config.thumbnail_storage_path)
            if thumb_local and os.path.isfile(thumb_local):
                thumb_remote_name = os.path.basename(thumb_local)
                self._upload_or_copy_file(thumb_local, remote_base_path, thumb_remote_name)

        logger.info('Exported license %s to %s', number, remote_base_path)
        return ('success', item_id, None)
