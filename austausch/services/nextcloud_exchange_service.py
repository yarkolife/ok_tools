"""Service for WebDAV operations on Nextcloud exchange folders."""

import logging
import os
import re
import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin
from xml.etree import ElementTree as ET

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from ..models import ExchangeConfig

logger = logging.getLogger('django')


class NextcloudExchangeService:
    """Service for WebDAV operations on exchange folders."""
    
    # WebDAV namespaces
    DAV_NS = '{DAV:}'
    OC_NS = '{http://owncloud.org/ns}'
    
    def __init__(self, config: Optional[ExchangeConfig] = None):
        """
        Initialize Nextcloud exchange service.
        
        Args:
            config: ExchangeConfig instance. If None, will fetch singleton.
        """
        if config is None:
            config = ExchangeConfig.get_config()
        
        if not config.nextcloud_base_url:
            raise ImproperlyConfigured(
                _('Nextcloud base URL not configured in ExchangeConfig')
            )
        
        self.config = config
        self.base_url = config.nextcloud_base_url.rstrip('/')
        self.username = config.nextcloud_username
        self.password = config.nextcloud_password
        
        # Support both user files and GroupFolders
        # Try GroupFolders first (common for shared exchange folders)
        # Format: /remote.php/dav/files/{username}/GroupFolders/
        self.webdav_path = f"/remote.php/dav/files/{self.username}/"
        self.groupfolders_path = f"/remote.php/dav/files/{self.username}/GroupFolders/"
        
        # Construct WebDAV base URL
        self.webdav_url = urljoin(self.base_url, self.webdav_path)
        self.groupfolders_url = urljoin(self.base_url, self.groupfolders_path)
    
    def _get_auth(self):
        """Get authentication tuple for requests."""
        return (self.username, self.password)

    # --- Public share upload (same mechanism as UI upload) ---

    def _create_upload_share(self, folder_path: str, expire_hours: int = 2) -> Optional[Dict]:
        """
        Create temporary upload-only public share on a folder.
        Returns dict with share_id, token, upload_url or None on error.
        """
        from datetime import datetime, timedelta
        expire_date = (datetime.now() + timedelta(hours=expire_hours)).strftime('%Y-%m-%d')
        share_path = f'/{folder_path.strip("/")}'
        try:
            r = requests.post(
                f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares",
                auth=self._get_auth(),
                headers={'OCS-APIRequest': 'true', 'Accept': 'application/json'},
                data={
                    'path': share_path,
                    'shareType': 3,      # Public link
                    'permissions': 4,    # Upload only (create)
                    'expireDate': expire_date,
                },
                timeout=30,
            )
            if r.status_code not in (200, 201):
                logger.error("Create upload share failed: %s - %s", r.status_code, r.text[:300])
                return None
            data = r.json()
            share_data = data.get('ocs', {}).get('data', {})
            token = share_data.get('token')
            share_id = share_data.get('id')
            if not token:
                logger.error("No token in share response")
                return None
            return {
                'share_id': share_id,
                'token': token,
                'upload_url': f"{self.base_url}/public.php/webdav/",
            }
        except Exception as e:
            logger.error("Error creating upload share: %s", e, exc_info=True)
            return None

    def _delete_share(self, share_id) -> bool:
        """Delete a public share by ID."""
        try:
            r = requests.delete(
                f"{self.base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}",
                auth=self._get_auth(),
                headers={'OCS-APIRequest': 'true'},
                timeout=30,
            )
            return r.status_code in (200, 204, 404)
        except Exception:
            return False

    def _upload_via_public_share(self, local_path: str, filename: str, share_token: str) -> bool:
        """
        Upload file via public share WebDAV endpoint (like browser does).
        This bypasses proxy/PHP body limits that block direct WebDAV PUT.
        """
        upload_url = f"{self.base_url}/public.php/webdav/{quote(filename, safe='')}"
        file_size = os.path.getsize(local_path)
        headers = {
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(file_size),
        }
        try:
            with open(local_path, 'rb') as f:
                r = requests.put(
                    upload_url,
                    data=f,
                    auth=(share_token, ''),  # Basic auth: token with empty password
                    headers=headers,
                    timeout=1800,  # 30 min for large files
                )
            if r.status_code in (200, 201, 204):
                logger.info("Uploaded via public share: %s -> %s", local_path, filename)
                return True
            logger.error(
                "Public share upload failed %s: %s - %s",
                filename, r.status_code, r.text[:500] if r.text else r.reason,
            )
            return False
        except Exception as e:
            logger.error("Error uploading via public share: %s", e, exc_info=True)
            return False

    def get_webdav_url_for_path(self, file_path: str) -> str:
        """
        Get the correct WebDAV base URL for a given file path.
        Checks if path is in GroupFolders and returns appropriate base URL.
        
        Args:
            file_path: Relative path in Nextcloud
            
        Returns:
            WebDAV base URL (with trailing slash removed)
        """
        # Check if path starts with GroupFolders
        if 'GroupFolders' in file_path or file_path.startswith('GroupFolders/'):
            return self.groupfolders_url.rstrip('/')
        else:
            return self.webdav_url.rstrip('/')
    
    def list_root_folders(self) -> List[str]:
        """
        List folders in the root of WebDAV to help debug folder structure.
        
        Returns:
            List of folder names
        """
        try:
            response = requests.request(
                'PROPFIND',
                self.webdav_url.rstrip('/'),
                auth=self._get_auth(),
                headers={
                    'Depth': '1',
                },
                timeout=30
            )
            
            if response.status_code == 207:
                folders = []
                root = ET.fromstring(response.text)
                for response_elem in root.findall(f'.//{self.DAV_NS}response'):
                    href_elem = response_elem.find(f'{self.DAV_NS}href')
                    if href_elem is None:
                        continue
                    
                    href = href_elem.text
                    if not href:
                        continue
                    
                    # Extract folder name
                    if self.webdav_path in href:
                        relative_path = href.split(self.webdav_path, 1)[1]
                        if relative_path and relative_path != '/':
                            folder_name = relative_path.strip('/').split('/')[0]
                            # Decode URL-encoded folder name for display
                            from urllib.parse import unquote
                            decoded_name = unquote(folder_name)
                            if decoded_name and decoded_name not in folders:
                                folders.append(decoded_name)
                
                return folders
            return []
        except Exception as e:
            logger.error(f"Error listing root folders: {e}", exc_info=True)
            return []
    
    def list_exchange_folder(self, channel: str, date_folders: Optional[List[str]] = None) -> List[Dict]:
        """
        List files in exchange folder for a channel.
        
        Args:
            channel: Channel name
            date_folders: Optional list of date folder names (e.g., ['2025_12_05', '2025_12_06'])
                         If None, will scan today's and yesterday's folders.
                         If empty list, will scan all subfolders recursively.
            
        Returns:
            List of file metadata dictionaries with keys:
            - path: Full file path in Nextcloud
            - filename: Filename
            - size: File size in bytes
            - modified: Last modified datetime
            - is_dir: Whether it's a directory
        """
        # Build exchange folder path
        exchange_folder = self.config.exchange_folder_pattern.format(channel=channel)
        folder_path = exchange_folder.strip('/')
        logger.debug(f"Looking for exchange folder: '{folder_path}' for channel: '{channel}'")
        
        # Determine which date folders to scan
        if date_folders is None:
            # Default: scan recent date folders based on config
            from django.utils import timezone
            days_to_scan = getattr(self.config, 'sync_date_folders_days', 2)
            today = timezone.now().date()
            date_folders = []
            for i in range(days_to_scan):
                date = today - timedelta(days=i)
                date_folders.append(date.strftime('%Y_%m_%d'))
            logger.debug(f"Scanning {days_to_scan} recent date folders: {date_folders}")
        
        # URL encode the path to handle spaces and special characters
        from urllib.parse import quote
        path_parts = folder_path.split('/')
        encoded_parts = [quote(part, safe='') for part in path_parts]
        encoded_base_path = '/'.join(encoded_parts)
        
        # Try multiple locations: user files, GroupFolders
        locations_to_try = [
            (self.webdav_url, folder_path, encoded_base_path, "user files"),
            (self.groupfolders_url, folder_path, encoded_base_path, "GroupFolders"),
        ]
        
        all_files = []
        
        for base_url, path, enc_base_path, location_type in locations_to_try:
            base_full_url = f"{base_url.rstrip('/')}/{enc_base_path}"
            logger.debug(f"Trying {location_type}: {base_full_url}")
            
            # First check if base folder exists
            try:
                check_response = requests.request(
                    'PROPFIND',
                    base_full_url,
                    auth=self._get_auth(),
                    headers={'Depth': '0'},
                    timeout=10
                )
                if check_response.status_code != 207:
                    logger.debug(f"Base folder not found in {location_type}: {path}")
                    continue
            except Exception as e:
                logger.debug(f"Error checking base folder in {location_type}: {e}")
                continue
            
            # If date_folders is empty list, do recursive scan of all subfolders
            if date_folders == []:
                try:
                    response = requests.request(
                        'PROPFIND',
                        base_full_url,
                        auth=self._get_auth(),
                        headers={'Depth': 'infinity'},
                        timeout=60
                    )
                    if response.status_code == 207:
                        logger.info(f"Found exchange folder in {location_type}: {folder_path} (recursive scan)")
                        files = self._parse_propfind_response(response.text, folder_path)
                        all_files.extend(files)
                        break  # Found in this location, no need to try others
                except Exception as e:
                    logger.debug(f"Error in recursive scan: {e}", exc_info=True)
                    continue
            
            # Scan specific date folders
            for date_folder in date_folders:
                date_folder_encoded = quote(date_folder, safe='')
                date_folder_url = f"{base_full_url}/{date_folder_encoded}"
                
                try:
                    response = requests.request(
                        'PROPFIND',
                        date_folder_url,
                        auth=self._get_auth(),
                        headers={'Depth': '1'},  # Only direct children of date folder
                        timeout=30
                    )
                    
                    if response.status_code == 207:
                        logger.debug(f"Found date folder: {date_folder} in {location_type}")
                        # Parse response, but adjust base_path to include date folder
                        date_folder_path = f"{folder_path}/{date_folder}"
                        files = self._parse_propfind_response(response.text, date_folder_path)
                        all_files.extend(files)
                    elif response.status_code == 404:
                        logger.debug(f"Date folder not found: {date_folder} in {location_type}")
                    else:
                        logger.warning(
                            f"Unexpected response for date folder {date_folder}: "
                            f"{response.status_code}"
                        )
                except Exception as e:
                    logger.debug(f"Error scanning date folder {date_folder}: {e}")
                    continue
            
            # If we found files in this location, no need to try others
            if all_files:
                logger.info(f"Found {len(all_files)} files in {location_type} for channel {channel}")
                break
        
        if not all_files:
            logger.warning(
                f"No files found in exchange folder: {folder_path}. "
                f"Scanned date folders: {date_folders}"
            )
        
        return all_files
    
    def _parse_propfind_response(self, xml_content: str, base_path: str) -> List[Dict]:
        """
        Parse PROPFIND XML response.
        
        Args:
            xml_content: XML response body
            base_path: Base path of the folder
            
        Returns:
            List of file metadata dictionaries
        """
        files = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find all response elements
            for response in root.findall(f'.//{self.DAV_NS}response'):
                href_elem = response.find(f'{self.DAV_NS}href')
                if href_elem is None:
                    continue
                
                href = href_elem.text
                if not href:
                    continue
                
                # Extract relative path
                # href format: /remote.php/dav/files/username/path/to/file
                if self.webdav_path in href:
                    relative_path = href.split(self.webdav_path, 1)[1]
                else:
                    # Fallback: try to extract from href
                    parts = href.strip('/').split('/')
                    if len(parts) > 3:
                        relative_path = '/'.join(parts[3:])
                    else:
                        continue
                
                # Decode URL-encoded path
                from urllib.parse import unquote
                relative_path = unquote(relative_path)
                
                # Skip the folder itself
                base_path_clean = base_path.rstrip('/')
                relative_path_clean = relative_path.rstrip('/')
                if relative_path_clean == base_path_clean:
                    continue
                
                # For date folder scanning:
                # - base_path is like "OK Magdeburg - Austausch/2026_01_07"
                # - relative_path for files should be like "OK Magdeburg - Austausch/2026_01_07/filename.ext"
                # We want files that are direct children of the date folder
                if not relative_path_clean.startswith(base_path_clean + '/'):
                    # Not a file in this date folder, skip
                    continue
                
                # Extract filename (should be direct child of date folder)
                # relative_path: "OK Magdeburg - Austausch/2026_01_07/filename.ext"
                # We want just "filename.ext" part
                path_after_base = relative_path_clean[len(base_path_clean):].lstrip('/')
                # If there are more slashes, it's in a subfolder, skip for now
                if '/' in path_after_base:
                    continue
                
                # Get file properties
                propstat = response.find(f'{self.DAV_NS}propstat')
                if propstat is None:
                    continue
                
                prop = propstat.find(f'{self.DAV_NS}prop')
                if prop is None:
                    continue
                
                # Extract file metadata
                getcontentlength = prop.find(f'{self.DAV_NS}getcontentlength')
                size = int(getcontentlength.text) if getcontentlength is not None and getcontentlength.text else 0
                
                getlastmodified = prop.find(f'{self.DAV_NS}getlastmodified')
                modified = None
                if getlastmodified is not None and getcontentlength is not None:
                    try:
                        # Parse RFC 1123 date format (e.g., "Mon, 01 Jan 2024 12:00:00 GMT")
                        modified_str = getlastmodified.text.strip()
                        # Parse as naive datetime first
                        modified = datetime.strptime(
                            modified_str,
                            '%a, %d %b %Y %H:%M:%S %Z'
                        )
                        # Make it timezone-aware (RFC 1123 dates are typically GMT/UTC)
                        from django.utils import timezone as tz
                        if tz.is_naive(modified):
                            # Use UTC for GMT/UTC timezone strings
                            from datetime import timezone as dt_tz
                            modified = modified.replace(tzinfo=dt_tz.utc)
                    except (ValueError, AttributeError) as e:
                        logger.debug(f"Could not parse date '{getlastmodified.text}': {e}")
                        pass
                
                resourcetype = prop.find(f'{self.DAV_NS}resourcetype')
                is_dir = resourcetype.find(f'{self.DAV_NS}collection') is not None
                
                # Skip directories
                if is_dir:
                    continue
                
                filename = relative_path.split('/')[-1]
                
                files.append({
                    'path': relative_path,
                    'filename': filename,
                    'size': size,
                    'modified': modified,
                    'is_dir': False,
                })
        except ET.ParseError as e:
            logger.error(f"Error parsing PROPFIND response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing PROPFIND response: {e}", exc_info=True)
        
        return files
    
    def download_file(self, file_path: str, local_path: str, resume: bool = False) -> bool:
        """
        Download file from Nextcloud to local storage.
        Supports resume download if file partially exists.
        
        Args:
            file_path: Relative path in Nextcloud
            local_path: Local file path to save to
            resume: If True, resume download from existing file position
            
        Returns:
            True if successful, False otherwise
        """
        import os
        
        try:
            # Construct full WebDAV URL with proper encoding
            from urllib.parse import quote
            webdav_base = self.webdav_url.rstrip('/')
            file_path_clean = file_path.lstrip('/')
            # URL encode each path segment
            encoded_path = '/'.join(quote(part, safe='') for part in file_path_clean.split('/'))
            full_url = f"{webdav_base}/{encoded_path}"
            
            # Check if file exists and get its size for resume
            headers = {}
            initial_pos = 0
            if resume and os.path.exists(local_path):
                initial_pos = os.path.getsize(local_path)
                if initial_pos > 0:
                    headers['Range'] = f'bytes={initial_pos}-'
                    logger.info(f"Resuming download of {file_path} from byte {initial_pos}")
            
            # Download file
            response = requests.get(
                full_url,
                auth=self._get_auth(),
                headers=headers,
                timeout=300,  # 5 minutes for large files
                stream=True
            )
            
            # Handle successful responses (200 for new download, 206 for partial content)
            if response.status_code in (200, 206):
                # Open file in append mode if resuming, otherwise write mode
                mode = 'ab' if resume and initial_pos > 0 else 'wb'
                with open(local_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                if initial_pos > 0:
                    logger.info(
                        f"Resumed and completed download: {file_path} -> {local_path} "
                        f"(resumed from {initial_pos} bytes)"
                    )
                else:
                    logger.info(f"Downloaded file: {file_path} -> {local_path}")
                return True
            elif response.status_code == 416:  # Range Not Satisfiable
                # File already fully downloaded
                logger.info(f"File already fully downloaded: {local_path}")
                return True
            else:
                logger.error(
                    f"Failed to download file {file_path}: "
                    f"{response.status_code} - {response.text[:200]}"
                )
                return False
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {e}", exc_info=True)
            return False
    
    def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        """
        Get file metadata via PROPFIND.
        
        Args:
            file_path: Relative path in Nextcloud
            
        Returns:
            Dictionary with file metadata or None if not found
        """
        try:
            from urllib.parse import quote
            webdav_base = self.webdav_url.rstrip('/')
            file_path_clean = file_path.lstrip('/')
            # URL encode each path segment
            encoded_path = '/'.join(quote(part, safe='') for part in file_path_clean.split('/'))
            full_url = f"{webdav_base}/{encoded_path}"
            
            response = requests.request(
                'PROPFIND',
                full_url,
                auth=self._get_auth(),
                headers={
                    'Depth': '0',
                },
                timeout=30
            )
            
            if response.status_code == 207:
                # Parse single file response
                files = self._parse_propfind_response(response.text, '')
                if files:
                    return files[0]
            elif response.status_code == 404:
                return None
            else:
                logger.warning(
                    f"Unexpected response getting metadata for {file_path}: "
                    f"{response.status_code}"
                )
                return None
        except Exception as e:
            logger.error(f"Error getting file metadata for {file_path}: {e}")
            return None
    
    def check_file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in Nextcloud.

        Args:
            file_path: Relative path in Nextcloud

        Returns:
            True if file exists, False otherwise
        """
        metadata = self.get_file_metadata(file_path)
        return metadata is not None

    def ensure_directory(self, remote_path: str) -> bool:
        """
        Create remote directory and all parent directories (MKCOL).
        Skips 409 Conflict if collection already exists.

        Args:
            remote_path: Relative path in Nextcloud (e.g. GroupFolders/Upload/2026_01_31)

        Returns:
            True if directory exists or was created, False on error
        """
        from urllib.parse import quote
        path_clean = remote_path.strip('/')
        if not path_clean:
            return True
        parts = [p for p in path_clean.split('/') if p]
        base_url = self.get_webdav_url_for_path(path_clean).rstrip('/')
        for i in range(1, len(parts) + 1):
            segment_path = '/'.join(parts[:i])
            encoded_path = '/'.join(quote(p, safe='') for p in parts[:i])
            full_url = f"{base_url}/{encoded_path}"
            try:
                response = requests.request(
                    'MKCOL',
                    full_url,
                    auth=self._get_auth(),
                    timeout=30
                )
                if response.status_code in (201, 405):
                    # 201 Created or 405 Method Not Allowed (already exists)
                    continue
                if response.status_code == 409:
                    # Conflict - parent may not exist; try creating parents
                    continue
                logger.warning(
                    f"MKCOL {segment_path} returned {response.status_code}: {response.text[:200]}"
                )
                return False
            except Exception as e:
                logger.error(f"Error creating directory {segment_path}: {e}", exc_info=True)
                return False
        return True

    # Use Nextcloud chunked upload for files larger than this (avoids proxy/PHP body limits).
    CHUNKED_UPLOAD_THRESHOLD = 50 * 1024 * 1024  # 50 MB
    CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB (Nextcloud minimum per chunk; smaller may pass proxy limits)

    def _upload_file_chunked(self, local_path: str, remote_path: str, file_size: int) -> bool:
        """
        Upload file via Nextcloud chunked upload v2 (MKCOL, PUT chunks, MOVE).
        Use for large files so proxy/PHP does not drop the body (0 bytes received).
        """
        path_clean = remote_path.strip('/')
        parts = [p for p in path_clean.split('/') if p]
        if not parts:
            return False
        parent_path = '/'.join(parts[:-1])
        if parent_path and not self.ensure_directory(parent_path):
            return False
        base_url = self.get_webdav_url_for_path(path_clean).rstrip('/')
        encoded_path = '/'.join(quote(p, safe='') for p in parts)
        destination_url = f"{base_url}/{encoded_path}"
        uploads_base = urljoin(
            self.base_url + '/',
            f"remote.php/dav/uploads/{quote(self.username, safe='')}/"
        ).rstrip('/')
        upload_id = f"oktools-{uuid.uuid4()}"
        upload_folder_url = f"{uploads_base}/{upload_id}"
        try:
            # 1. MKCOL with Destination
            r = requests.request(
                'MKCOL',
                upload_folder_url,
                auth=self._get_auth(),
                headers={'Destination': destination_url},
                timeout=30,
            )
            if r.status_code not in (201, 405):
                logger.error("Chunked upload MKCOL failed: %s - %s", r.status_code, r.text[:200])
                return False
            # 2. PUT chunks (names 1..N, 5+ MB each except last)
            total_len = str(file_size)
            chunk_num = 1
            with open(local_path, 'rb') as f:
                while True:
                    chunk = f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    chunk_name = f"{chunk_num:05d}"
                    chunk_url = f"{upload_folder_url}/{chunk_name}"
                    headers = {
                        'Content-Type': 'application/octet-stream',
                        'Content-Length': str(len(chunk)),
                        'Destination': destination_url,
                        'OC-Total-Length': total_len,
                    }
                    r = requests.put(
                        chunk_url,
                        data=chunk,
                        auth=self._get_auth(),
                        headers=headers,
                        timeout=600,
                    )
                    if r.status_code not in (200, 201, 204):
                        err_snippet = (r.text or r.reason or '')[:500]
                        logger.error(
                            "Chunked upload PUT %s failed: %s (chunk size %s) - %s",
                            chunk_name, r.status_code, len(chunk), err_snippet,
                        )
                        if 'Expected filesize' in (r.text or '') and '0 bytes' in (r.text or ''):
                            logger.error(
                                "Nextcloud received 0 bytes: fix server/proxy (nginx client_max_body_size, "
                                "proxy_request_buffering, PHP upload_max_filesize). Or use in-app Upload Video."
                            )
                        return False
                    chunk_num += 1
                    if chunk_num > 10000:
                        logger.error("Chunked upload: too many chunks")
                        return False
            # 3. MOVE .file to assemble
            move_source = f"{upload_folder_url}/.file"
            r = requests.request(
                'MOVE',
                move_source,
                auth=self._get_auth(),
                headers={
                    'Destination': destination_url,
                    'OC-Total-Length': total_len,
                },
                timeout=120,
            )
            if r.status_code not in (200, 201, 204):
                logger.error("Chunked upload MOVE failed: %s - %s", r.status_code, r.text[:500])
                return False
            logger.info("Uploaded file (chunked): %s -> %s", local_path, remote_path)
            return True
        except Exception as e:
            logger.error("Chunked upload failed %s -> %s: %s", local_path, remote_path, e, exc_info=True)
            return False

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a local file to Nextcloud via public share WebDAV.

        Uses the same mechanism as UI video upload (public.php/webdav with share token).
        This bypasses proxy/PHP body limits that block direct WebDAV PUT to remote.php/dav.

        Args:
            local_path: Local file path to read from
            remote_path: Relative path in Nextcloud (e.g. OKMQ/INBOX/file.mp4)

        Returns:
            True if successful, False otherwise
        """
        if not os.path.isfile(local_path):
            logger.error("Upload failed: local file not found: %s", local_path)
            return False
        path_clean = remote_path.strip('/')
        parts = [p for p in path_clean.split('/') if p]
        if not parts:
            logger.error("Upload failed: remote_path is empty")
            return False
        # Ensure parent directory exists
        parent_path = '/'.join(parts[:-1])
        if parent_path and not self.ensure_directory(parent_path):
            return False
        filename = parts[-1]
        # Create temporary upload share on parent folder
        share_data = self._create_upload_share(parent_path, expire_hours=2)
        if not share_data:
            logger.error("Upload failed: could not create upload share for %s", parent_path)
            return False
        share_id = share_data['share_id']
        token = share_data['token']
        try:
            success = self._upload_via_public_share(local_path, filename, token)
            return success
        finally:
            # Always clean up the share
            self._delete_share(share_id)

    @staticmethod
    def parse_contribution_id(filename: str) -> Optional[int]:
        """
        Parse contribution ID from filename.
        
        Filenames from OK-Tools start with numeric ID: "{ID}_timestamp_filename.ext"
        
        Args:
            filename: Filename to parse
            
        Returns:
            Contribution ID as integer, or None if not found
        """
        # Pattern: number at the start of filename, followed by underscore
        match = re.match(r'^(\d+)_', filename)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None
    
    def parse_meta_json(self, file_path: str) -> Optional[Dict]:
        """
        Download and parse .meta.json file.
        
        Args:
            file_path: Path to .meta.json file in Nextcloud
            
        Returns:
            Dictionary with parsed metadata or None if file not found/invalid
            
        Expected JSON structure:
        {
            "name": "Title",
            "description": "Description text",
            "senderResponsible": "Author name",
            "category": 107,
            "targetChannel": "@ok_magdeburg@lokalmedial.de",
            "originallyPublishedAt": "2025-09-23T16:00:00Z",
            "thumbnail": "filename.jpg",
            "allowExchange": true,
            "saveToMediathek": true
        }
        """
        import json
        import tempfile
        import os
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                temp_path = f.name
            
            if not self.download_file(file_path, temp_path):
                logger.warning(f"Failed to download meta.json: {file_path}")
                return None
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            os.unlink(temp_path)
            
            # Validate and extract relevant fields
            if not isinstance(data, dict):
                logger.error(f"Invalid meta.json format: expected dict, got {type(data)}")
                return None
            
            # Extract and clean fields
            # Handle both formats:
            # 1. category can be string or number
            # 2. videoNumber can be used instead of category as number
            category_value = data.get('category')
            video_number = data.get('videoNumber')
            
            # If category is a string, use videoNumber as category_id
            # If category is a number, use it as category_id
            category_id = None
            if isinstance(category_value, int):
                category_id = category_value
            elif video_number:
                category_id = video_number
            elif isinstance(category_value, str):
                # Category is a string (like "Kurzfilm"), keep it for reference
                pass
            
            result = {
                'title': str(data.get('name', '')).strip(),
                'description': str(data.get('description', '')).strip(),
                'sender_responsible': str(data.get('senderResponsible', '')).strip(),
                'category_id': category_id,
                'category_name': str(category_value) if isinstance(category_value, str) else None,
                'target_channel': str(data.get('targetChannel', '')).strip(),
                'originally_published_at': data.get('originallyPublishedAt'),
                'thumbnail': str(data.get('thumbnail', '')).strip(),
                'allow_exchange': bool(data.get('allowExchange', False)),
                'save_to_mediathek': bool(data.get('saveToMediathek', False)),
                'tags': data.get('tags', []),  # Array of tags
                'youth_protection_necessary': bool(data.get('youthProtectionNecessary', False)),
                'youth_protection_category': str(data.get('youthProtectionCategory', '')).strip(),
                'video_number': video_number,  # Store videoNumber if present
            }
            
            logger.debug(
                f"Parsed meta.json from {file_path}: "
                f"title='{result['title']}', "
                f"author='{result['sender_responsible']}', "
                f"category_id={category_id}, "
                f"video_number={video_number}"
            )
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in meta.json {file_path}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Error parsing meta.json {file_path}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def detect_file_type(filename: str) -> str:
        """
        Detect file type from extension.
        
        Args:
            filename: Filename
            
        Returns:
            'video', 'pdf', 'json', 'image', or 'unknown'
        """
        filename_lower = filename.lower()
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.mxf', '.mpeg', '.mpg']
        pdf_extensions = ['.pdf']
        json_extensions = ['.json']
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif']
        
        for ext in video_extensions:
            if filename_lower.endswith(ext):
                return 'video'
        
        for ext in pdf_extensions:
            if filename_lower.endswith(ext):
                return 'pdf'
        
        for ext in json_extensions:
            if filename_lower.endswith(ext):
                return 'json'
        
        for ext in image_extensions:
            if filename_lower.endswith(ext):
                return 'image'
        
        return 'unknown'

