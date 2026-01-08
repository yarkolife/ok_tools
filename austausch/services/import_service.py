"""Service for importing exchange items into OK-Tools."""

import os
import hashlib
import logging
from pathlib import Path
from typing import Tuple, Optional, List
from difflib import SequenceMatcher
from django.utils import timezone
from django.core.exceptions import ValidationError

from licenses.models import License, Category
from licenses.admin import get_profile_by_name, create_profile_by_name, get_category_by_id, get_category_by_name
from media_files.models import VideoFile, StorageLocation
from registration.models import Profile
from ..models import ExchangeItem, ExchangeImport, ExchangeConfig
from .nextcloud_exchange_service import NextcloudExchangeService

logger = logging.getLogger('django')


def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings (0.0 to 1.0)."""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower().strip(), str2.lower().strip()).ratio()


def find_potential_duplicates(title, profile, threshold=0.8):
    """
    Find potential duplicate licenses by title and profile.
    
    Args:
        title: License title to check
        profile: Profile object to check
        threshold: Similarity threshold (default 0.8 = 80%)
    
    Returns:
        QuerySet of potential duplicate licenses
    """
    if not title or not profile:
        return License.objects.none()
    
    # Get all licenses for this profile
    profile_licenses = License.objects.filter(profile=profile)
    
    # Find licenses with similar titles
    potential_duplicates = []
    for license_obj in profile_licenses:
        similarity = similarity_ratio(title, license_obj.title)
        if similarity >= threshold:
            potential_duplicates.append(license_obj.id)
    
    return License.objects.filter(id__in=potential_duplicates)


class ImportService:
    """Handles import of exchange items into OK-Tools."""
    
    def __init__(self, exchange_item: ExchangeItem, user):
        """
        Initialize import service.
        
        Args:
            exchange_item: ExchangeItem to import
            user: User performing the import
        """
        self.exchange_item = exchange_item
        self.user = user
        self.config = ExchangeConfig.get_config()
        self.service = NextcloudExchangeService(self.config)
    
    def import_item(self, check_duplicates: bool = True) -> Tuple[ExchangeImport, Optional[List[License]]]:
        """
        Main import method - idempotent.
        
        Process:
        1. Check for duplicates (optional)
        2. Create License (without files)
        3. Return import record and duplicate list (if any)
        4. Files will be downloaded via Celery task
        
        Args:
            check_duplicates: Whether to check for potential duplicates
            
        Returns:
            Tuple of (ExchangeImport record, list of potential duplicate licenses)
            
        Raises:
            Exception: If import fails
        """
        # Check if already imported or in progress
        existing_import = ExchangeImport.objects.filter(
            exchange_item=self.exchange_item,
            status__in=['completed', 'pending_download', 'downloading', 'processing']
        ).first()
        
        if existing_import:
            logger.info(f"Item {self.exchange_item.id} already imported or in progress (status: {existing_import.status})")
            return existing_import, None
        
        # Check if exchange item already has a linked license
        if self.exchange_item.imported_license:
            logger.info(f"Item {self.exchange_item.id} already has license {self.exchange_item.imported_license.number}")
            # Create import record pointing to existing license
            import_record = ExchangeImport.objects.create(
                exchange_item=self.exchange_item,
                imported_by=self.user,
                status='pending_download',
                license=self.exchange_item.imported_license
            )
            # Enqueue Celery task to download files (if not already downloaded)
            from ..tasks import download_exchange_files_task
            download_exchange_files_task.delay(import_record.id)
            return import_record, None
        
        # Create import record
        import_record = ExchangeImport.objects.create(
            exchange_item=self.exchange_item,
            imported_by=self.user,
            status='pending'
        )
        
        try:
            import_record.status = 'processing'
            import_record.save()
            
            # Get or create profile for duplicate checking
            profile = self._get_or_create_profile()
            
            # Check for potential duplicates before creating license
            potential_duplicates = None
            exact_match_license = None
            
            if check_duplicates and self.exchange_item.title and profile:
                potential_duplicates = find_potential_duplicates(
                    self.exchange_item.title,
                    profile,
                    threshold=0.8
                )
                if potential_duplicates.exists():
                    logger.warning(
                        f"Found {potential_duplicates.count()} potential duplicates "
                        f"for exchange item {self.exchange_item.id}"
                    )
                    
                    # Check for exact match (100% similarity)
                    for dup_license in potential_duplicates:
                        similarity = similarity_ratio(
                            self.exchange_item.title or '',
                            dup_license.title or ''
                        )
                        if similarity >= 0.99:  # 99% or more = exact match
                            exact_match_license = dup_license
                            logger.info(
                                f"Found exact match (similarity: {similarity*100:.1f}%) "
                                f"for license {dup_license.number}, using existing license"
                            )
                            break
            
            # Create or get License (without downloading files yet)
            if exact_match_license:
                # Use existing license if exact match found
                license = exact_match_license
                logger.info(
                    f"Using existing license {license.number} "
                    f"instead of creating new one for exchange item {self.exchange_item.id}"
                )
            elif self.exchange_item.contribution_id:
                license = self._get_or_create_license(profile)
            else:
                license = self._create_legacy_license(profile)
            
            # Update import record with license
            import_record.license = license
            import_record.status = 'pending_download'  # Will be completed after Celery task
            import_record.save()
            
            # Update exchange item
            self.exchange_item.import_status = 'imported'
            self.exchange_item.imported_at = timezone.now()
            self.exchange_item.imported_license = license
            self.exchange_item.save()
            
            # Enqueue Celery task to download files
            from ..tasks import download_exchange_files_task
            download_exchange_files_task.delay(import_record.id)
            
            logger.info(
                f"License {license.id} created for exchange item {self.exchange_item.id}, "
                f"download task enqueued"
            )
            
            # Return duplicates as list for API response
            duplicates_list = list(potential_duplicates) if potential_duplicates and potential_duplicates.exists() else None
            
            return import_record, duplicates_list
            
        except Exception as e:
            import_record.status = 'failed'
            import_record.error_message = str(e)
            import_record.save()
            
            self.exchange_item.import_status = 'failed'
            self.exchange_item.save()
            
            logger.error(
                f"Import failed for exchange item {self.exchange_item.id}: {e}",
                exc_info=True
            )
            raise
    
    def _get_or_create_profile(self) -> Profile:
        """
        Get or create profile from sendeverantwortung.
        
        Returns:
            Profile instance
        """
        profile = None
        if self.exchange_item.sendeverantwortung:
            profile = get_profile_by_name(self.exchange_item.sendeverantwortung)
            if not profile:
                # Create new profile if not found
                profile = create_profile_by_name(self.exchange_item.sendeverantwortung)
        
        # Fallback: use user's profile or first available profile
        if not profile:
            try:
                # Try to get profile from current user
                profile = Profile.objects.get(okuser=self.user)
            except Profile.DoesNotExist:
                # Use first available profile as last resort
                profile = Profile.objects.first()
                if not profile:
                    raise Exception("No profile found. Please create at least one profile.")
        
        return profile
    
    def _download_files(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Download video and PDF files from Nextcloud.
        
        Files are saved with license number prefix: {number}_{original_filename}
        Spaces in filenames are replaced with underscores.
        Supports resume download if file partially exists.
        
        Returns:
            Tuple of (video_path, pdf_path) local file paths
        """
        download_dir = Path(self.config.download_storage_path)
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Get license number for filename prefix
        license_number = None
        if hasattr(self, 'license') and self.license:
            license_number = self.license.number
        elif self.exchange_item.imported_license:
            license_number = self.exchange_item.imported_license.number
        elif self.exchange_item.contribution_id:
            license_number = self.exchange_item.contribution_id
        
        video_path = None
        pdf_path = None
        
        def format_filename(original_filename: str) -> str:
            """Format filename with license number prefix and replace spaces."""
            # Replace spaces with underscores
            safe_name = original_filename.replace(' ', '_')
            
            # Add license number prefix if available
            if license_number:
                # Extract extension
                name_parts = safe_name.rsplit('.', 1)
                if len(name_parts) == 2:
                    base_name, extension = name_parts
                    return f"{license_number}_{base_name}.{extension}"
                else:
                    return f"{license_number}_{safe_name}"
            return safe_name
        
        # Download video file (main file)
        video_file_path = self.exchange_item.file_path
        original_video_filename = self.exchange_item.filename
        formatted_video_filename = format_filename(original_video_filename)
        local_video_path = download_dir / formatted_video_filename
        
        # Check if video already exists and has correct size
        if local_video_path.exists():
            local_size = local_video_path.stat().st_size
            remote_size = self.exchange_item.file_size
            if remote_size and local_size >= remote_size:
                video_path = str(local_video_path)
                logger.info(f"Video already exists: {video_path} (size: {local_size})")
            else:
                # File exists but incomplete, resume download
                if self.service.download_file(video_file_path, str(local_video_path), resume=True):
                    video_path = str(local_video_path)
                    logger.info(f"Resumed video download: {video_file_path} -> {video_path}")
                else:
                    raise Exception(f"Failed to resume video file: {video_file_path}")
        else:
            if self.service.download_file(video_file_path, str(local_video_path), resume=True):
                video_path = str(local_video_path)
                logger.info(f"Downloaded video: {video_file_path} -> {video_path}")
            else:
                raise Exception(f"Failed to download video file: {video_file_path}")
        
        # Download PDF file if it's part of the package
        if self.exchange_item.pdf_path:
            pdf_file_path = self.exchange_item.pdf_path
            # Extract PDF filename from path
            original_pdf_filename = pdf_file_path.rsplit('/', 1)[-1]
            formatted_pdf_filename = format_filename(original_pdf_filename)
            local_pdf_path = download_dir / formatted_pdf_filename
            
            # Check if PDF already exists
            if local_pdf_path.exists() and local_pdf_path.stat().st_size > 0:
                pdf_path = str(local_pdf_path)
                logger.info(f"PDF already exists: {pdf_path}")
            elif self.service.download_file(pdf_file_path, str(local_pdf_path), resume=True):
                pdf_path = str(local_pdf_path)
                logger.info(f"Downloaded PDF: {pdf_file_path} -> {pdf_path}")
            else:
                logger.warning(f"Failed to download PDF file: {pdf_file_path}")
        else:
            # Fallback: try to find PDF by base filename (for backward compatibility)
            base_filename = '.'.join(self.exchange_item.filename.split('.')[:-1])
            folder_path = self.exchange_item.file_path.rsplit('/', 1)[0]
            pdf_filename = base_filename + '.pdf'
            pdf_file_path = f"{folder_path}/{pdf_filename}"
            
            if self.service.check_file_exists(pdf_file_path):
                original_pdf_filename = pdf_filename
                formatted_pdf_filename = format_filename(original_pdf_filename)
                local_pdf_path = download_dir / formatted_pdf_filename
                
                # Check if PDF already exists
                if local_pdf_path.exists() and local_pdf_path.stat().st_size > 0:
                    pdf_path = str(local_pdf_path)
                    logger.info(f"PDF already exists (fallback): {pdf_path}")
                elif self.service.download_file(pdf_file_path, str(local_pdf_path), resume=True):
                    pdf_path = str(local_pdf_path)
                    logger.info(f"Downloaded PDF (fallback): {pdf_file_path} -> {pdf_path}")
        
        return video_path, pdf_path
    
    def _verify_files(self, video_path: str, pdf_path: Optional[str]):
        """
        Verify downloaded files (checksums, size, etc.).
        
        Args:
            video_path: Path to video file
            pdf_path: Path to PDF file (optional)
        """
        # Verify video file exists and has content
        if not video_path or not os.path.exists(video_path):
            raise Exception("Video file not found after download")
        
        video_size = os.path.getsize(video_path)
        if video_size == 0:
            raise Exception("Video file is empty")
        
        # Verify PDF if provided
        if pdf_path and os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            if pdf_size == 0:
                logger.warning("PDF file is empty, but continuing import")
        
        # TODO: Verify checksums if available in ExchangeItem
        # For now, we rely on file size verification
    
    def _get_or_create_license(self, profile: Profile) -> License:
        """
        Get existing license or create new one for OK-Tools managed item.
        
        Args:
            profile: Profile instance (already obtained)
        
        Returns:
            License instance
        """
        contribution_id = self.exchange_item.contribution_id
        
        try:
            # Try to get existing license
            license = License.objects.get(number=contribution_id)
            logger.info(f"Found existing license {license.id} for contribution_id {contribution_id}")
            return license
        except License.DoesNotExist:
            # Create new license from exchange item metadata
            logger.info(f"Creating new license for contribution_id {contribution_id}")
            
            # Get category from meta.json or use default
            # Try to parse .meta.json if available
            meta_data = {}
            if self.exchange_item.file_path:
                # Try to find and parse .meta.json file
                try:
                    base_name = '.'.join(self.exchange_item.filename.split('.')[:-1])
                    folder_path = self.exchange_item.file_path.rsplit('/', 1)[0]
                    meta_json_path = f"{folder_path}/{base_name}.meta.json"
                    
                    if self.service.check_file_exists(meta_json_path):
                        meta_data = self.service.parse_meta_json(meta_json_path) or {}
                except Exception as e:
                    logger.warning(f"Could not parse meta.json for exchange item {self.exchange_item.id}: {e}")
            
            category = None
            if meta_data.get('category_id'):
                category = get_category_by_id(meta_data['category_id'])
            
            if not category:
                # Use default category
                try:
                    category = Category.objects.first()
                    if not category:
                        # Create default category if none exists
                        from django.utils.translation import gettext_lazy as _
                        category = Category.objects.get_or_create(name=_('Gastbeitrag'))[0]
                except Category.DoesNotExist:
                    from django.utils.translation import gettext_lazy as _
                    category = Category.objects.get_or_create(name=_('Gastbeitrag'))[0]
            
            # Create license with metadata from exchange item (similar to import_json_view)
            license = License.objects.create(
                number=contribution_id,
                title=self.exchange_item.title or f"Imported from Exchange - {contribution_id}",
                description=self.exchange_item.description or "",
                duration=self.exchange_item.duration or timezone.timedelta(seconds=0),
                profile=profile,
                category=category,
                # Set exchange flags based on source
                media_authority_exchange_allowed=meta_data.get('allow_exchange', True),
                store_in_ok_media_library=meta_data.get('save_to_mediathek', False),
                repetitions_allowed=False,
                media_authority_exchange_allowed_other_states=False,
                youth_protection_necessary=meta_data.get('youth_protection_necessary', False),
                youth_protection_category=meta_data.get('youth_protection_category', 'none'),
                is_screen_board=False,
                infoblock=False,
                confirmed=False,
            )
            
            logger.info(f"Created new license {license.id} for contribution_id {contribution_id}")
            return license
    
    def _create_legacy_license(self, profile: Profile) -> License:
        """
        Create license for legacy (non-OK-Tools) item.
        
        Args:
            profile: Profile instance (already obtained)
        
        Returns:
            License instance
        """
        logger.info(f"Creating legacy license for exchange item {self.exchange_item.id}")
        
        # Try to parse .meta.json if available
        meta_data = {}
        if self.exchange_item.file_path:
            # Try to find and parse .meta.json file
            try:
                base_name = '.'.join(self.exchange_item.filename.split('.')[:-1])
                folder_path = self.exchange_item.file_path.rsplit('/', 1)[0]
                meta_json_path = f"{folder_path}/{base_name}.meta.json"
                
                if self.service.check_file_exists(meta_json_path):
                    meta_data = self.service.parse_meta_json(meta_json_path) or {}
            except Exception as e:
                logger.warning(f"Could not parse meta.json for exchange item {self.exchange_item.id}: {e}")
        
        # Get default category
        try:
            category = Category.objects.first()
            if not category:
                from django.utils.translation import gettext_lazy as _
                category = Category.objects.get_or_create(name=_('Gastbeitrag'))[0]
        except Category.DoesNotExist:
            from django.utils.translation import gettext_lazy as _
            category = Category.objects.get_or_create(name=_('Gastbeitrag'))[0]
        
        # Generate a unique sequential number for legacy items
        # Get the highest license number and increment by 1
        last_license = License.objects.order_by('-number').first()
        if last_license:
            new_number = last_license.number + 1
        else:
            new_number = 1
        
        license = License.objects.create(
            number=new_number,
            title=self.exchange_item.title or f"Legacy Import - {self.exchange_item.filename}",
            description=self.exchange_item.description or f"Imported from exchange folder: {self.exchange_item.channel}",
            duration=self.exchange_item.duration or timezone.timedelta(seconds=0),
            profile=profile,
            category=category,
            media_authority_exchange_allowed=meta_data.get('allow_exchange', True),
            store_in_ok_media_library=meta_data.get('save_to_mediathek', False),
            repetitions_allowed=False,
            media_authority_exchange_allowed_other_states=False,
            youth_protection_necessary=meta_data.get('youth_protection_necessary', False),
            youth_protection_category=meta_data.get('youth_protection_category', 'none'),
            is_screen_board=False,
            infoblock=False,
            confirmed=False,
        )
        
        logger.info(f"Created legacy license {license.id} with number {new_number}")
        return license
    
    def _get_import_storage_location(self) -> StorageLocation:
        """
        Get or create storage location for imported files.
        
        Returns:
            StorageLocation instance
        """
        # Try to find existing CUSTOM storage for imports
        storage = StorageLocation.objects.filter(
            storage_type='CUSTOM',
            name__icontains='import'
        ).first()
        
        if not storage:
            # Create new storage location
            storage_path = self.config.download_storage_path
            storage = StorageLocation.objects.create(
                name='Exchange Imports',
                storage_type='CUSTOM',
                path=storage_path,
                is_active=True,
                scan_enabled=False,
            )
            logger.info(f"Created new storage location for imports: {storage.id}")
        
        return storage
    
    def _create_video_file(
        self,
        license: License,
        video_path: str,
        storage_location: StorageLocation
    ) -> VideoFile:
        """
        Create VideoFile record for imported video with full metadata extraction.
        
        VideoFile is automatically linked to License via signals (auto_link_to_license)
        based on the number field.
        
        Args:
            license: License instance
            video_path: Local path to video file
            storage_location: StorageLocation instance
            
        Returns:
            VideoFile instance
        """
        from media_files.utils import extract_video_metadata_fast
        from django.utils import timezone
        
        video_file_path = Path(video_path)
        relative_path = video_file_path.name  # Just filename for now
        
        # Extract comprehensive video metadata
        try:
            metadata = extract_video_metadata_fast(video_path)
            logger.info(f"Extracted metadata for {video_path}")
        except Exception as e:
            logger.warning(f"Failed to extract metadata for {video_path}: {e}")
            metadata = {}
        
        # Calculate checksum
        checksum = self._calculate_checksum(video_path)
        
        # Get file size (use from metadata if available, otherwise from filesystem)
        file_size = metadata.get('file_size') or os.path.getsize(video_path)
        
        # Get format (use from metadata if available, otherwise from extension)
        file_format = metadata.get('format') or video_file_path.suffix.lstrip('.').lower()
        
        # Get duration (prefer metadata, then exchange_item, then None)
        duration = metadata.get('duration') or self.exchange_item.duration
        
        # Create VideoFile record with all metadata
        video_file = VideoFile.objects.create(
            number=license.number,
            filename=video_file_path.name,
            storage_location=storage_location,
            file_path=relative_path,
            file_size=file_size,
            format=file_format,
            checksum=checksum,
            license=license,  # Explicitly set, signals will ensure it's the newest
            is_available=True,
            duration=duration,
            # Video metadata
            has_video=metadata.get('has_video', False),
            video_codec=metadata.get('video_codec', ''),
            video_codec_long=metadata.get('video_codec_long', ''),
            video_profile=metadata.get('video_profile', ''),
            video_bitrate=metadata.get('video_bitrate'),
            video_bitrate_mode=metadata.get('video_bitrate_mode', ''),
            fps=metadata.get('fps'),
            width=metadata.get('width'),
            height=metadata.get('height'),
            aspect_ratio=metadata.get('aspect_ratio', ''),
            pixel_format=metadata.get('pixel_format', ''),
            color_space=metadata.get('color_space', ''),
            color_range=metadata.get('color_range', ''),
            chroma_subsampling=metadata.get('chroma_subsampling', ''),
            # Audio metadata
            has_audio=metadata.get('has_audio', False),
            audio_codec=metadata.get('audio_codec', ''),
            audio_codec_long=metadata.get('audio_codec_long', ''),
            audio_bitrate=metadata.get('audio_bitrate'),
            audio_sample_rate=metadata.get('audio_sample_rate'),
            audio_channels=metadata.get('audio_channels'),
            audio_channel_layout=metadata.get('audio_channel_layout', ''),
            # Overall metadata
            total_bitrate=metadata.get('total_bitrate'),
            last_scanned=timezone.now(),
        )
        
        logger.info(
            f"Created VideoFile {video_file.id} for license {license.number} "
            f"with full metadata (codec: {video_file.video_codec}, "
            f"resolution: {video_file.width}x{video_file.height}, "
            f"fps: {video_file.fps})"
        )
        return video_file
    
    def _calculate_checksum(self, file_path: str) -> str:
        """
        Calculate SHA256 checksum of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of SHA256 checksum
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _store_pdf(self, license: License, pdf_path: str):
        """
        Store PDF file (link to license).
        
        For now, we just log it. PDF storage can be implemented later
        if needed (similar to how videos are stored).
        
        Args:
            license: License instance
            pdf_path: Path to PDF file
        """
        # TODO: Implement PDF storage if needed
        # For now, PDFs are downloaded but not stored in a separate model
        logger.info(f"PDF file stored for license {license.id}: {pdf_path}")
    
    def _enqueue_peertube_upload(self, video_file: VideoFile):
        """
        Enqueue PeerTube upload task (optional).
        
        Args:
            video_file: VideoFile instance
        """
        # TODO: Integrate with existing PeerTube upload pipeline
        # This would typically call a Celery task from media_files.tasks
        logger.info(f"PeerTube upload enqueued for video_file {video_file.id} (not implemented yet)")

