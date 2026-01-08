"""API endpoints for Austausch module."""

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import BasePermission
import logging

from licenses.models import License
from licenses.serializers import LicenseMetadataSerializer
from .models import ExchangeItem, ExchangeImport, ExchangeConfig
from .serializers import ExchangeItemSerializer, ExchangeImportSerializer
from .services.import_service import ImportService, similarity_ratio
from .services.nextcloud_exchange_service import NextcloudExchangeService

logger = logging.getLogger('django')


class IsStaffOnly(BasePermission):
    """
    Permission class: only staff members can access.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )


def check_austausch_enabled():
    """Check if Austausch module is enabled."""
    if not getattr(settings, 'AUSTAUSCH_ENABLED', False):
        raise ImproperlyConfigured(
            'Austausch module is disabled. Set AUSTAUSCH_ENABLED=true to enable.'
        )


class ExchangeDecisionView(APIView):
    """
    Extended Decision API for Nextcloud inspector.
    
    Returns routing decisions and metadata for contribution ID.
    This extends the existing LicenseMetadataSerializer with routing fields.
    
    Access: Authenticated users (for service tokens from Nextcloud scripts).
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, number):
        """
        Retrieve license metadata with routing decisions.
        
        Args:
            request: HTTP request
            number: License number (contribution ID)
            
        Returns:
            Response with license metadata and routing decisions
        """
        try:
            license = get_object_or_404(
                License.objects.select_related('profile', 'category'),
                number=number
            )
            
            # Get base metadata
            serializer = LicenseMetadataSerializer(license)
            data = serializer.data
            
            # Add routing decisions
            data['destination'] = self._determine_destination(license)
            data['allow_exchange'] = license.media_authority_exchange_allowed
            data['allow_mediathek'] = license.store_in_ok_media_library
            data['allow_peertube'] = not license.is_live  # Live broadcasts can't go to PeerTube
            
            # Log successful API access
            logger.info(
                f"Exchange Decision API: user={request.user.email}, "
                f"license={number}, destination={data['destination']}, "
                f"ip={request.META.get('REMOTE_ADDR')}"
            )
            
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Exchange Decision API error: user={request.user.email}, "
                f"license={number}, error={str(e)}"
            )
            raise
    
    def _determine_destination(self, license):
        """
        Determine routing destination based on license flags.
        
        Priority:
        1. Live broadcasts -> archiv
        2. Mediathek enabled -> mediathek
        3. Exchange allowed -> exchange
        4. Default -> archiv
        """
        if license.is_live:
            return 'archiv'  # Live broadcasts go to archive
        if license.store_in_ok_media_library:
            return 'mediathek'
        if license.media_authority_exchange_allowed:
            return 'exchange'
        return 'archiv'


class ImportExchangeItemView(APIView):
    """
    Trigger import of exchange item.
    
    Access: Staff members only.
    """
    
    permission_classes = [IsStaffOnly]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, item_id):
        """
        Import an exchange item into OK-Tools.
        
        Args:
            request: HTTP request
            item_id: ExchangeItem ID
            
        Returns:
            Response with import status
        """
        exchange_item = get_object_or_404(ExchangeItem, id=item_id)
        
        # Check if already imported
        existing_import = ExchangeImport.objects.filter(
            exchange_item=exchange_item,
            status='completed'
        ).first()
        
        if existing_import:
            return Response({
                'status': 'already_imported',
                'message': 'Item has already been imported',
                'import_id': existing_import.id,
                'license_id': existing_import.license.id if existing_import.license else None
            })
        
        # Run import via service
        try:
            import_service = ImportService(exchange_item, request.user)
            import_record, potential_duplicates = import_service.import_item()
            
            serializer = ExchangeImportSerializer(import_record)
            
            # Prepare duplicates data for response
            duplicates_data = None
            if potential_duplicates:
                duplicates_data = [
                    {
                        'id': dup.id,
                        'number': dup.number,
                        'title': dup.title,
                        'similarity': similarity_ratio(
                            exchange_item.title or '',
                            dup.title
                        ) * 100 if exchange_item.title else 0
                    }
                    for dup in potential_duplicates
                ]
            
            logger.info(
                f"Exchange import started: user={request.user.email}, "
                f"item_id={item_id}, import_id={import_record.id}, "
                f"license_id={import_record.license.id if import_record.license else None}, "
                f"duplicates_found={len(potential_duplicates) if potential_duplicates else 0}"
            )
            
            response_data = {
                'status': 'success',
                'import': serializer.data,
                'message': 'License created successfully. Files are being downloaded in the background.'
            }
            
            if duplicates_data:
                response_data['duplicates'] = duplicates_data
                response_data['warning'] = f'Found {len(duplicates_data)} potential duplicate license(s).'
            
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Exchange import failed: user={request.user.email}, "
                f"item_id={item_id}, error={str(e)}",
                exc_info=True
            )
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, item_id):
        """
        Convenience GET handler for admin links.
        Delegates to POST to trigger import.
        """
        return self.post(request, item_id)


class SyncExchangeView(APIView):
    """
    Trigger manual sync of exchange folders.
    
    Access: Staff members only.
    """
    
    permission_classes = [IsStaffOnly]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """
        Trigger manual sync of exchange folders.
        
        Returns:
            Response with sync status
        """
        from austausch.tasks import sync_exchange_folders_task
        
        try:
            logger.info(f"Manual sync triggered by user: {request.user.email}")
            
            # Run the sync task asynchronously via Celery
            result = sync_exchange_folders_task.delay()
            
            logger.info(
                f"Exchange sync task enqueued: user={request.user.email}, task_id={result.id}"
            )
            
            return Response({
                'status': 'success',
                'message': 'Exchange sync task has been enqueued. The sync is running in the background.',
                'task_id': result.id,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(
                f"Exchange sync failed: user={request.user.email}, error={str(e)}",
                exc_info=True
            )
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """Allow GET requests for button clicks."""
        return self.post(request)


class ExchangeItemListView(APIView):
    """
    List exchange items with filtering.
    
    Access: Staff members only.
    """
    
    permission_classes = [IsStaffOnly]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """
        Get list of exchange items with optional filters.
        
        Query parameters:
        - channel: Filter by channel name
        - status: Filter by import_status (new, imported, failed)
        - date_from: Filter items discovered after this date (ISO format)
        - oktools_only: Show only OK-Tools managed items (true/false)
        """
        queryset = ExchangeItem.objects.all()
        
        # Apply filters
        channel = request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(channel=channel)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(import_status=status_filter)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(discovered_at__gte=date_from)
        
        oktools_only = request.query_params.get('oktools_only', '').lower() == 'true'
        if oktools_only:
            queryset = queryset.filter(is_oktools_managed=True)
        
        # Order by discovery date (newest first)
        queryset = queryset.order_by('-discovered_at')
        
        # Serialize results
        serializer = ExchangeItemSerializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })


class ImportBatchExchangeItemsView(APIView):
    """
    Import multiple exchange items in batch.
    
    Access: Staff members only.
    """
    
    permission_classes = [IsStaffOnly]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """
        Import multiple exchange items.
        
        Body:
        {
            "item_ids": [1, 2, 3, ...]
        }
        
        Returns:
            Response with import status
        """
        item_ids = request.data.get('item_ids', [])
        if not item_ids or not isinstance(item_ids, list):
            return Response(
                {'error': 'item_ids must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get items
        items = ExchangeItem.objects.filter(id__in=item_ids, import_status='new')
        if not items.exists():
            return Response({
                'status': 'error',
                'error': 'No new items found to import'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Import each item
        imported_count = 0
        errors = []
        
        for item in items:
            try:
                # Check if already imported
                existing_import = ExchangeImport.objects.filter(
                    exchange_item=item,
                    status='completed'
                ).first()
                
                if existing_import:
                    continue
                
                # Run import via service
                from .services.import_service import ImportService
                import_service = ImportService(item, request.user)
                import_service.import_item()
                imported_count += 1
                
            except Exception as e:
                logger.error(
                    f"Exchange batch import failed: user={request.user.email}, "
                    f"item_id={item.id}, error={str(e)}",
                    exc_info=True
                )
                errors.append(f"Item {item.id}: {str(e)}")
        
        logger.info(
            f"Exchange batch import completed: user={request.user.email}, "
            f"imported={imported_count}, errors={len(errors)}"
        )
        
        return Response({
            'status': 'success',
            'count': imported_count,
            'errors': errors if errors else None
        }, status=status.HTTP_200_OK)


class DownloadExchangeFileView(APIView):
    """
    Download file from Nextcloud for preview.
    
    Access: Staff members only.
    """
    
    permission_classes = [IsStaffOnly]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def _generate_thumbnail(self, exchange_item, service):
        """
        Generate thumbnail from video file.
        
        Returns:
            FileResponse with thumbnail if successful, None otherwise
        """
        from pathlib import Path
        from django.http import FileResponse
        from urllib.parse import quote
        from media_files.utils import generate_thumbnail_from_http_url, generate_thumbnail_from_http_range
        
        logger.info(f"Generating thumbnail for exchange_item {exchange_item.id}, video: {exchange_item.file_path}")
        
        # Create thumbnail directory
        thumbnail_dir = Path(settings.MEDIA_ROOT) / 'exchange_thumbnails'
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate thumbnail filename
        thumbnail_filename = f"exchange_{exchange_item.id}.jpg"
        local_thumbnail_path = thumbnail_dir / thumbnail_filename
        
        # Check if thumbnail already exists locally
        if local_thumbnail_path.exists():
            logger.info(f"Thumbnail already exists locally: {local_thumbnail_path}")
            relative_thumbnail_path = f"exchange_thumbnails/{thumbnail_filename}"
            exchange_item.thumbnail_path = relative_thumbnail_path
            exchange_item.save(update_fields=['thumbnail_path'])
            return FileResponse(
                open(local_thumbnail_path, 'rb'),
                content_type='image/jpeg'
            )
        
        # Build WebDAV URL for video file
        webdav_base = service.get_webdav_url_for_path(exchange_item.file_path)
        video_path_clean = exchange_item.file_path.lstrip('/')
        encoded_path = '/'.join(quote(part, safe='') for part in video_path_clean.split('/'))
        video_url = f"{webdav_base}/{encoded_path}"
        
        logger.info(f"Generating thumbnail from URL: {video_url} (masked)")
        
        # Generate thumbnail using HTTP URL
        timestamp = '00:00:05'
        auth = service._get_auth()
        
        # Try direct HTTP input first, then fallback to range download
        success = generate_thumbnail_from_http_url(
            video_url, str(local_thumbnail_path), timestamp, auth=auth
        )
        if not success:
            logger.info(f"Direct HTTP failed, trying range download for exchange_item {exchange_item.id}")
            success = generate_thumbnail_from_http_range(
                video_url, str(local_thumbnail_path), timestamp, auth=auth
            )
        
        if success:
            logger.info(f"Successfully generated thumbnail: {local_thumbnail_path}")
            relative_thumbnail_path = f"exchange_thumbnails/{thumbnail_filename}"
            exchange_item.thumbnail_path = relative_thumbnail_path
            exchange_item.save(update_fields=['thumbnail_path'])
            return FileResponse(
                open(local_thumbnail_path, 'rb'),
                content_type='image/jpeg'
            )
        else:
            logger.error(f"Failed to generate thumbnail for exchange_item {exchange_item.id} (both methods failed)")
            return None
    
    def get(self, request, item_id, file_type):
        """
        Download file from Nextcloud.
        
        Args:
            item_id: ExchangeItem ID
            file_type: 'video' or 'pdf'
        """
        from django.http import StreamingHttpResponse
        import os
        
        exchange_item = get_object_or_404(ExchangeItem, id=item_id)
        config = ExchangeConfig.get_config()
        service = NextcloudExchangeService(config)
        
        # Determine file to download
        file_path = None  # Initialize to avoid UnboundLocalError
        if file_type == 'video':
            # Use video file path directly (stored in file_path)
            file_path = exchange_item.file_path
        elif file_type == 'thumbnail':
            # Check if thumbnail is available locally or in Nextcloud
            from pathlib import Path
            from django.http import FileResponse
            
            logger.info(f"Thumbnail request for exchange_item {exchange_item.id}, thumbnail_path: {exchange_item.thumbnail_path}")
            
            # Check if thumbnail_path is a local path (starts with exchange_thumbnails/)
            if exchange_item.thumbnail_path and exchange_item.thumbnail_path.startswith('exchange_thumbnails/'):
                # Local thumbnail path
                local_thumbnail_path = Path(settings.MEDIA_ROOT) / exchange_item.thumbnail_path
                if local_thumbnail_path.exists():
                    logger.info(f"Serving local thumbnail: {local_thumbnail_path}")
                    return FileResponse(
                        open(local_thumbnail_path, 'rb'),
                        content_type='image/jpeg'
                    )
                else:
                    # Local path doesn't exist, need to generate
                    logger.warning(f"Local thumbnail path doesn't exist: {local_thumbnail_path}, clearing path")
                    exchange_item.thumbnail_path = ''  # Clear invalid path
                    exchange_item.save(update_fields=['thumbnail_path'])
            
            # If thumbnail_path exists and is not local, try to download from Nextcloud
            # But don't check existence here - let streaming code handle 404 and fallback to generation
            if exchange_item.thumbnail_path and not exchange_item.thumbnail_path.startswith('exchange_thumbnails/'):
                logger.info(f"Using Nextcloud thumbnail path: {exchange_item.thumbnail_path}")
                # Set file_path - streaming code will handle 404 and fallback to generation
                file_path = exchange_item.thumbnail_path
                # Will be handled by streaming code below (with fallback to generation on 404)
            
            # Generate thumbnail if file_path is not set (no valid thumbnail found)
            # This includes: no thumbnail_path, invalid local path, or Nextcloud file not found
            if not file_path:
                result = self._generate_thumbnail(exchange_item, service)
                if result:
                    return result
                else:
                    return Response(
                        {'error': 'Failed to generate thumbnail'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        elif file_type == 'pdf':
            # Use PDF path from exchange_item (if part of package)
            if exchange_item.pdf_path:
                file_path = exchange_item.pdf_path
            else:
                # Fallback: try to find PDF by base filename
                base_name = '.'.join(exchange_item.filename.split('.')[:-1])
                folder_path = exchange_item.file_path.rsplit('/', 1)[0]
                pdf_filename = base_name + '.pdf'
                pdf_path = f"{folder_path}/{pdf_filename}"
                if service.check_file_exists(pdf_path):
                    file_path = pdf_path
                else:
                    return Response(
                        {'error': 'PDF file not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        else:
            return Response(
                {'error': 'Invalid file type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Stream directly from Nextcloud without downloading completely
        # file_path should be set at this point
        if not file_path:
            return Response(
                {'error': 'File path not determined'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        import os
        import requests
        
        # Determine content type based on file extension
        # For thumbnails, use the thumbnail file extension, not the video filename
        if file_type == 'thumbnail':
            file_extension = os.path.splitext(file_path)[1].lower() if file_path else '.jpg'
        else:
            file_extension = os.path.splitext(exchange_item.filename)[1].lower()
        content_types = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.mpeg': 'video/mpeg',
            '.mpg': 'video/mpeg',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
        }
        content_type = content_types.get(file_extension, 'application/octet-stream')
        
        # Build WebDAV URL for direct streaming
        from urllib.parse import quote
        webdav_base = service.get_webdav_url_for_path(file_path)
        file_path_clean = file_path.lstrip('/')
        encoded_path = '/'.join(quote(part, safe='') for part in file_path_clean.split('/'))
        stream_url = f"{webdav_base}/{encoded_path}"
        
        # Get file metadata first to determine size
        file_metadata = service.get_file_metadata(file_path)
        file_size = file_metadata.get('size', 0) if file_metadata else 0
        
        # Handle Range requests for video streaming
        range_header = request.META.get('HTTP_RANGE', '').strip()
        headers = {}
        
        if range_header:
            headers['Range'] = range_header
        
        try:
            # Make the request to Nextcloud first to get headers
            nc_response = requests.get(
                stream_url,
                auth=service._get_auth(),
                headers=headers,
                stream=True,
                timeout=300
            )
            
            if nc_response.status_code not in (200, 206):
                logger.error(f"Nextcloud returned status {nc_response.status_code} for {file_path}: {nc_response.text[:200]}")
                # If thumbnail file not found, try to generate it
                if file_type == 'thumbnail' and nc_response.status_code == 404:
                    logger.info(f"Thumbnail file not found in Nextcloud, generating from video")
                    # Clear invalid thumbnail_path
                    exchange_item.thumbnail_path = ''
                    exchange_item.save(update_fields=['thumbnail_path'])
                    
                    # Generate thumbnail using shared method
                    result = self._generate_thumbnail(exchange_item, service)
                    if result:
                        return result
                    else:
                        return Response(
                            {'error': 'Failed to generate thumbnail'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                return Response(
                    {'error': f'Failed to stream from Nextcloud: {nc_response.status_code}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create streaming generator
            def stream_chunks():
                for chunk in nc_response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            # Create streaming response with proper headers
            if nc_response.status_code == 206:  # Partial Content
                response = StreamingHttpResponse(
                    stream_chunks(),
                    status=status.HTTP_206_PARTIAL_CONTENT,
                    content_type=content_type
                )
                # Copy headers from Nextcloud response
                if 'Content-Range' in nc_response.headers:
                    response['Content-Range'] = nc_response.headers['Content-Range']
                if 'Content-Length' in nc_response.headers:
                    response['Content-Length'] = nc_response.headers['Content-Length']
            else:
                response = StreamingHttpResponse(
                    stream_chunks(),
                    content_type=content_type
                )
                if 'Content-Length' in nc_response.headers:
                    response['Content-Length'] = nc_response.headers['Content-Length']
                elif file_size > 0:
                    response['Content-Length'] = str(file_size)
            
            # Set common headers
            response['Accept-Ranges'] = 'bytes'
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(exchange_item.filename)}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Error streaming file from Nextcloud: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

