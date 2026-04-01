"""Service for interacting with Nextcloud via WebDAV API."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
import logging
import os
import re
import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote


logger = logging.getLogger('django')


class NextcloudService:
    """Service class for Nextcloud WebDAV operations."""

    def __init__(self):
        """Initialize Nextcloud service."""
        if not settings.NEXTCLOUD_ENABLED:
            raise ImproperlyConfigured(
                _('Nextcloud integration is disabled. Set NEXTCLOUD_ENABLED=true to enable.')
            )

        self.base_url = settings.NEXTCLOUD_URL.rstrip('/')
        self.username = settings.NEXTCLOUD_USERNAME
        self.password = settings.NEXTCLOUD_PASSWORD
        self.upload_folder = settings.NEXTCLOUD_UPLOAD_FOLDER.strip('/')
        self.webdav_path = settings.NEXTCLOUD_WEBDAV_PATH.format(username=self.username)

        # Construct WebDAV base URL
        self.webdav_url = urljoin(self.base_url, self.webdav_path)

        # Ensure upload folder exists
        self._ensure_upload_folder_exists()

    def _ensure_upload_folder_exists(self):
        """Ensure the upload folder exists in Nextcloud."""
        # Create nested folders if path contains slashes
        folder_parts = [part for part in self.upload_folder.split('/') if part]
        
        current_path = self.webdav_url.rstrip('/')
        
        for folder_part in folder_parts:
            current_path = f"{current_path}/{folder_part}"
            try:
                # Try to create folder (MKCOL request)
                response = requests.request(
                    'MKCOL',
                    current_path,
                    auth=(self.username, self.password),
                    timeout=10
                )
                # 201 = created, 405 = already exists (both are OK)
                if response.status_code not in [201, 405]:
                    logger.warning(
                        f'Failed to create folder {folder_part}: {response.status_code} - {response.text}'
                    )
            except Exception as e:
                logger.error(f'Error creating folder {folder_part}: {e}')

    def _get_auth(self):
        """Get authentication tuple for requests."""
        return (self.username, self.password)

    def upload_video(self, file, license_number, filename, progress_callback=None):
        """
        Upload video file to Nextcloud.

        Args:
            file: Django UploadedFile object
            license_number: License number (int)
            filename: Original filename (str)
            progress_callback: Optional callback function(bytes_sent, total_bytes) for progress tracking

        Returns:
            dict with keys: file_id, file_url, nextcloud_url
        """
        try:
            # Generate filename without timestamp; resolve collisions without dates.
            unique_filename = self.generate_unique_filename(license_number, filename)

            # Construct full path in Nextcloud
            # Ensure proper path formatting
            upload_folder = self.upload_folder.strip('/')
            file_path = f"{upload_folder}/{unique_filename}" if upload_folder else unique_filename
            # Ensure webdav_url doesn't have trailing slash and file_path starts with /
            webdav_base = self.webdav_url.rstrip('/')
            full_url = f"{webdav_base}/{file_path}"

            # Read file content
            file.seek(0)  # Reset file pointer
            file_content = file.read()
            file_size = len(file_content)

            # Create a file-like object with progress tracking
            if progress_callback:
                class ProgressFile:
                    def __init__(self, content, callback, total_size):
                        self.content = content
                        self.callback = callback
                        self.total_size = total_size
                        self.bytes_sent = 0
                        self.position = 0
                        self.chunk_size = 1024 * 1024  # 1MB chunks for progress updates

                    def read(self, size=-1):
                        if size == -1:
                            # Read all remaining content
                            chunk = self.content[self.position:]
                            self.position = len(self.content)
                        else:
                            chunk = self.content[self.position:self.position + size]
                            self.position += len(chunk)
                        
                        self.bytes_sent += len(chunk)
                        if self.callback and len(chunk) > 0:
                            self.callback(self.bytes_sent, self.total_size)
                        return chunk

                    def __len__(self):
                        return len(self.content)
                    
                    def __iter__(self):
                        return self
                    
                    def __next__(self):
                        if self.position >= len(self.content):
                            raise StopIteration
                        chunk = self.read(min(self.chunk_size, len(self.content) - self.position))
                        return chunk

                progress_file = ProgressFile(file_content, progress_callback, file_size)
            else:
                progress_file = file_content

            # Upload via WebDAV PUT request
            # Use stream=True to enable progress tracking
            if progress_callback:
                # Use iterator for streaming upload with progress
                response = requests.put(
                    full_url,
                    data=progress_file,
                    auth=self._get_auth(),
                    headers={
                        'Content-Type': 'application/octet-stream',
                        'Content-Length': str(file_size),
                    },
                    timeout=300,  # 5 minutes for large files
                    stream=False  # requests will iterate over the data
                )
            else:
                response = requests.put(
                    full_url,
                    data=file_content,
                    auth=self._get_auth(),
                    headers={
                        'Content-Type': 'application/octet-stream',
                    },
                    timeout=300  # 5 minutes for large files
                )

            if response.status_code in [201, 204]:
                # File uploaded successfully
                # Try to get shareable URL (optional)
                share_url = self._get_share_url(file_path)

                logger.info(
                    f'Successfully uploaded video {unique_filename} to Nextcloud for license {license_number}'
                )

                return {
                    'file_id': file_path,
                    'file_url': full_url,
                    'nextcloud_url': share_url or full_url,
                    'filename': unique_filename,
                }
            else:
                error_msg = f'Failed to upload video to Nextcloud: {response.status_code} - {response.text}'
                logger.error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            logger.error(f'Error uploading video to Nextcloud: {e}')
            raise

    def delete_video(self, file_id):
        """
        Delete video file from Nextcloud.

        Args:
            file_id: File path in Nextcloud (str)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure proper path formatting
            webdav_base = self.webdav_url.rstrip('/')
            file_path = file_id.lstrip('/')
            full_url = f"{webdav_base}/{file_path}"

            response = requests.delete(
                full_url,
                auth=self._get_auth(),
                timeout=30
            )

            if response.status_code in [204, 404]:  # 404 = already deleted
                logger.info(f'Successfully deleted video {file_id} from Nextcloud')
                return True
            else:
                logger.warning(
                    f'Failed to delete video from Nextcloud: {response.status_code} - {response.text}'
                )
                return False

        except Exception as e:
            logger.error(f'Error deleting video from Nextcloud: {e}')
            return False

    def check_file_exists(self, file_id):
        """
        Check if file exists in Nextcloud.

        Args:
            file_id: File path in Nextcloud (str)

        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            # Ensure proper path formatting
            webdav_base = self.webdav_url.rstrip('/')
            file_path = file_id.lstrip('/')
            full_url = f"{webdav_base}/{file_path}"

            response = requests.head(
                full_url,
                auth=self._get_auth(),
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f'Error checking file existence in Nextcloud: {e}')
            return False

    def download_file(self, file_id: str, local_path: str, resume: bool = False) -> bool:
        """
        Download file from Nextcloud to local storage.
        Supports resume download if file partially exists.

        Args:
            file_id: File path in Nextcloud (str)
            local_path: Local file path to save to (str)
            resume: If True, resume download from existing file position

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Construct full WebDAV URL with proper encoding
            webdav_base = self.webdav_url.rstrip('/')
            file_path = (file_id or '').lstrip('/')
            encoded_path = '/'.join(quote(part, safe='') for part in file_path.split('/') if part != '')
            full_url = f"{webdav_base}/{encoded_path}" if encoded_path else webdav_base

            headers = {}
            initial_pos = 0
            if resume and os.path.exists(local_path):
                initial_pos = os.path.getsize(local_path)
                if initial_pos > 0:
                    headers['Range'] = f'bytes={initial_pos}-'
                    logger.info(f"Resuming download of {file_id} from byte {initial_pos}")

            response = requests.get(
                full_url,
                auth=self._get_auth(),
                headers=headers,
                timeout=300,
                stream=True,
            )

            # 200 = full content, 206 = partial content
            if response.status_code in (200, 206):
                mode = 'ab' if resume and initial_pos > 0 else 'wb'
                with open(local_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                if initial_pos > 0:
                    logger.info(
                        f"Resumed and completed download: {file_id} -> {local_path} "
                        f"(resumed from {initial_pos} bytes)"
                    )
                else:
                    logger.info(f"Downloaded file: {file_id} -> {local_path}")
                return True

            if response.status_code == 416:
                # Range Not Satisfiable: file already fully downloaded
                logger.info(f"File already fully downloaded: {local_path}")
                return True

            logger.error(
                f"Failed to download file {file_id}: "
                f"{response.status_code} - {response.text[:200]}"
            )
            return False
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}", exc_info=True)
            return False

    def get_file_url(self, file_id):
        """
        Get shareable/download URL for file.

        Args:
            file_id: File path in Nextcloud (str)

        Returns:
            str: Shareable URL or None
        """
        # For now, return the WebDAV URL
        # In the future, could create a public share and return that URL
        webdav_base = self.webdav_url.rstrip('/')
        file_path = file_id.lstrip('/')
        return f"{webdav_base}/{file_path}"

    def _get_share_url(self, file_path):
        """
        Try to create a public share and get shareable URL.

        Args:
            file_path: File path in Nextcloud (str)

        Returns:
            str: Shareable URL or None
        """
        # This is optional - could use Nextcloud Sharing API
        # For now, return None and use WebDAV URL
        return None

    def create_upload_share(self, license_number, expire_hours=24):
        """
        Create temporary upload-only share for direct client upload.
        
        This allows clients to upload files directly to Nextcloud without
        exposing service account credentials.

        Args:
            license_number: License number for subfolder naming
            expire_hours: Hours until share expires (default 24)

        Returns:
            dict with keys: share_id, token, upload_url, target_folder
        """
        try:
            expire_date = (datetime.now() + timedelta(hours=expire_hours)).strftime('%Y-%m-%d')
            
            # Create share on the upload folder
            share_path = f'/{self.upload_folder}'
            
            response = requests.post(
                f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares",
                auth=self._get_auth(),
                headers={
                    'OCS-APIRequest': 'true',
                    'Accept': 'application/json',
                },
                data={
                    'path': share_path,
                    'shareType': 3,      # Public link
                    'permissions': 4,    # Upload only (create)
                    'expireDate': expire_date,
                },
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                error_msg = f'Failed to create upload share: {response.status_code} - {response.text}'
                logger.error(error_msg)
                raise Exception(error_msg)
            
            data = response.json()
            
            # Handle OCS response format
            if 'ocs' in data and 'data' in data['ocs']:
                share_data = data['ocs']['data']
            else:
                error_msg = f'Unexpected response format: {data}'
                logger.error(error_msg)
                raise Exception(error_msg)
            
            share_id = share_data.get('id')
            token = share_data.get('token')
            
            if not token:
                error_msg = 'No token in share response'
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # WebDAV URL for public share upload (NC32+ format)
            upload_url = f"{self.base_url}/public.php/dav/files/{token}/"

            logger.info(
                f'Created upload share for license {license_number}, '
                f'share_id={share_id}, expires={expire_date}'
            )

            return {
                'share_id': share_id,
                'token': token,
                'upload_url': upload_url,
                'target_folder': self.upload_folder,
            }
            
        except Exception as e:
            logger.error(f'Error creating upload share: {e}')
            raise

    def delete_share(self, share_id):
        """
        Delete a share by its ID.

        Args:
            share_id: Share ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = requests.delete(
                f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}",
                auth=self._get_auth(),
                headers={
                    'OCS-APIRequest': 'true',
                },
                timeout=30
            )
            
            if response.status_code in [200, 204, 404]:
                logger.info(f'Deleted share {share_id}')
                return True
            else:
                logger.warning(
                    f'Failed to delete share {share_id}: {response.status_code} - {response.text}'
                )
                return False
                
        except Exception as e:
            logger.error(f'Error deleting share {share_id}: {e}')
            return False

    def verify_uploaded_file(self, filename):
        """
        Verify that a file was uploaded to the upload folder.

        Args:
            filename: Filename to check

        Returns:
            dict with file info if exists, None otherwise
        """
        try:
            file_path = f"{self.upload_folder}/{filename}"
            webdav_base = self.webdav_url.rstrip('/')
            full_url = f"{webdav_base}/{file_path}"
            
            # Use PROPFIND to get file info
            response = requests.request(
                'PROPFIND',
                full_url,
                auth=self._get_auth(),
                headers={
                    'Depth': '0',
                },
                timeout=30
            )
            
            if response.status_code == 207:  # Multi-Status = file exists
                # Parse size from response if needed
                content = response.text
                size = 0
                
                # Try to extract content-length from PROPFIND response
                import re
                size_match = re.search(r'<d:getcontentlength>(\d+)</d:getcontentlength>', content)
                if size_match:
                    size = int(size_match.group(1))
                
                logger.info(f'Verified file exists: {filename}, size={size}')
                return {
                    'exists': True,
                    'file_path': file_path,
                    'file_url': full_url,
                    'size': size,
                }
            elif response.status_code == 404:
                logger.warning(f'File not found: {filename}')
                return None
            else:
                logger.warning(
                    f'Unexpected response verifying file {filename}: {response.status_code}'
                )
                return None
                
        except Exception as e:
            logger.error(f'Error verifying uploaded file {filename}: {e}')
            return None

    def get_file_size(self, file_path):
        """
        Get the size of a file in Nextcloud.

        Args:
            file_path: Path to file in Nextcloud

        Returns:
            int: File size in bytes, or 0 if not found
        """
        try:
            webdav_base = self.webdav_url.rstrip('/')
            full_url = f"{webdav_base}/{file_path.lstrip('/')}"
            
            response = requests.head(
                full_url,
                auth=self._get_auth(),
                timeout=30
            )
            
            if response.status_code == 200:
                content_length = response.headers.get('Content-Length', '0')
                return int(content_length)
            return 0
            
        except Exception as e:
            logger.error(f'Error getting file size for {file_path}: {e}')
            return 0

    def generate_unique_filename(self, license_number, original_filename):
        """
        Generate a unique filename for upload.

        Args:
            license_number: License number
            original_filename: Original filename from client

        Returns:
            str: Unique sanitized filename
        """
        safe_filename = self._sanitize_filename(original_filename)
        base_name = f"{license_number}_{safe_filename}"

        # Check collisions in the upload folder and add suffix _2, _3, ...
        # without any timestamps to keep names stable/readable.
        candidate = base_name
        i = 2
        while self.check_file_exists(f"{self.upload_folder}/{candidate}"):
            name, ext = os.path.splitext(base_name)
            candidate = f"{name}_{i}{ext}"
            i += 1

            # Safety valve: avoid infinite loops if Nextcloud is misbehaving.
            if i > 1000:
                raise RuntimeError("Unable to generate unique filename (too many collisions)")

        return candidate

    def _sanitize_filename(self, filename):
        """
        Sanitize filename for safe upload.

        Args:
            filename: Original filename (str)

        Returns:
            str: Sanitized filename
        """
        # Remove path components
        filename = os.path.basename(filename)

        # Replace spaces and special characters
        # Keep alphanumeric, dots, hyphens, underscores
        import re
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext

        return filename

