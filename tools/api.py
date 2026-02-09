"""API endpoints for Tools module."""

import logging
import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.db import models
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from .models import AudioNormalizeJob, SlideshowProject, SlideshowMedia, SlideshowAudio, ToolsConfig
from .utils import resolve_tools_file_path, resolve_tools_output_path
from .services.audio_normalizer import AudioNormalizerService, load_audio_presets
from .services.audio_waveform import WaveformError, load_or_generate_waveform
from .services.video_generator import VideoGenerator, VideoGeneratorError

logger = logging.getLogger('django')

def _media_root_abs() -> Path:
    media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
    if media_root.is_absolute():
        return media_root.resolve()
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return (base_dir / media_root).resolve()

def _media_files_available() -> bool:
    return bool(
        getattr(settings, 'MEDIA_FILES_ENABLED', False)
        and 'media_files' in getattr(settings, 'INSTALLED_APPS', [])
    )


def get_project_or_403(request, project_id):
    """Get project and check permissions (owner or superuser)."""
    project = get_object_or_404(SlideshowProject, id=project_id)
    if not request.user.is_superuser and project.created_by != request.user:
        raise PermissionDenied(_('You do not have permission to access this project.'))
    return project


def check_tools_enabled():
    """Check if Tools module is enabled."""
    if not getattr(settings, 'TOOLS_ENABLED', False):
        raise ImproperlyConfigured(
            _('Tools module is disabled. Set TOOLS_ENABLED=true to enable.')
        )


def _require_staff(request):
    if not request.user.is_staff:
        raise PermissionDenied(_('Only staff members can access this tool.'))


def get_audio_job_or_403(request, job_id: int) -> AudioNormalizeJob:
    job = get_object_or_404(AudioNormalizeJob, id=job_id)
    if not request.user.is_superuser and job.created_by != request.user:
        raise PermissionDenied(_('You do not have permission to access this job.'))
    return job


class CreateSlideshowProjectView(APIView):
    """Create a new slideshow project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """Create a new slideshow project."""
        name = request.data.get('name', _('Untitled Slideshow'))
        
        project = SlideshowProject.objects.create(
            name=name,
            created_by=request.user
        )
        
        logger.info(f"Slideshow project created: id={project.id}, user={request.user.email}")
        
        return Response({
            'status': 'success',
            'project_id': project.id,
            'name': project.name
        }, status=status.HTTP_201_CREATED)


class UploadMediaView(APIView):
    """Upload media files to slideshow project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, project_id):
        """Upload media files."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        files = request.FILES.getlist('files')
        if not files:
            return Response({
                'error': _('No files provided')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get storage path from config
        config = ToolsConfig.get_config()
        storage_path = config.get_effective_storage_path()
        
        uploaded = []
        errors = []
        
        for file in files:
            try:
                # Get current max order
                max_order = SlideshowMedia.objects.filter(project=project).aggregate(
                    max_order=models.Max('order')
                )['max_order'] or 0
                
                # Save file to mounted storage path if configured
                if storage_path:
                    # Use mounted path
                    storage_base = Path(storage_path)
                    media_dir = storage_base / f"tools/slideshow/{project.id}/media"
                    media_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Save file directly to mounted path
                    filename = Path(file.name).name
                    # Ensure unique filename
                    file_path = media_dir / filename
                    counter = 1
                    while file_path.exists():
                        stem = Path(filename).stem
                        ext = Path(filename).suffix
                        file_path = media_dir / f"{stem}_{counter}{ext}"
                        counter += 1
                    
                    # Write file to mounted path
                    with open(file_path, 'wb') as dest:
                        for chunk in file.chunks():
                            dest.write(chunk)
                    
                    # Create SlideshowMedia with file stored in mounted path
                    # Store relative path in FileField (will be resolved in video_generator)
                    rel_path = f"tools/slideshow/{project.id}/media/{file_path.name}"
                    # Create SlideshowMedia without saving file again (file already saved to mounted path)
                    media = SlideshowMedia(project=project, order=max_order + 1)
                    # Set file name directly to avoid Django trying to save it again
                    media.file.name = rel_path
                    media.save()
                else:
                    # Fallback to default MEDIA_ROOT behavior
                    media = SlideshowMedia.objects.create(
                        project=project,
                        file=file,
                        order=max_order + 1
                    )
                
                uploaded.append({
                    'id': media.id,
                    'filename': Path(media.file.name).name,
                    'media_type': media.media_type,
                    'order': media.order
                })
            except Exception as e:
                logger.error(f"Failed to upload media: {e}", exc_info=True)
                errors.append(f"{file.name}: {str(e)}")
        
        return Response({
            'status': 'success',
            'uploaded': uploaded,
            'errors': errors if errors else None
        }, status=status.HTTP_200_OK)


class UploadAudioView(APIView):
    """Upload audio file to slideshow project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, project_id):
        """Upload audio file."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES.get('file')
        if not file:
            return Response({
                'error': _('No file provided')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        name = request.data.get('name', Path(file.name).stem)
        
        # Remove existing audio files for this project
        SlideshowAudio.objects.filter(project=project).delete()
        
        # Get storage path from config
        config = ToolsConfig.get_config()
        storage_path = config.get_effective_storage_path()
        
        # Save file to mounted storage path if configured
        if storage_path:
            # Use mounted path
            storage_base = Path(storage_path)
            audio_dir = storage_base / f"tools/slideshow/{project.id}/audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file directly to mounted path
            filename = Path(file.name).name
            # Ensure unique filename
            file_path = audio_dir / filename
            counter = 1
            while file_path.exists():
                stem = Path(filename).stem
                ext = Path(filename).suffix
                file_path = audio_dir / f"{stem}_{counter}{ext}"
                counter += 1
            
            # Write file to mounted path
            with open(file_path, 'wb') as dest:
                for chunk in file.chunks():
                    dest.write(chunk)
            
            # Create SlideshowAudio with file stored in mounted path
            rel_path = f"tools/slideshow/{project.id}/audio/{file_path.name}"
            audio = SlideshowAudio(project=project, name=name)
            # Set file name directly to avoid Django trying to save it again
            audio.file.name = rel_path
            audio.save()
        else:
            # Fallback to default MEDIA_ROOT behavior
            audio = SlideshowAudio.objects.create(
                project=project,
                file=file,
                name=name
            )
        
        # Try to get duration
        try:
            generator = VideoGenerator(project)
            audio_path = resolve_tools_file_path(audio.file, config)
            duration = generator.get_audio_duration(audio_path)
            audio.duration = duration
            audio.save(update_fields=['duration'])
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
        
        return Response({
            'status': 'success',
            'audio': {
                'id': audio.id,
                'name': audio.name,
                'duration': audio.duration
            }
        }, status=status.HTTP_200_OK)


class DeleteAudioView(APIView):
    """Delete audio file from slideshow project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, project_id):
        """Delete audio file."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete all audio files for this project
        deleted_count = SlideshowAudio.objects.filter(project=project).delete()[0]
        
        return Response({
            'status': 'success',
            'message': _('Deleted {count} audio file(s)').format(count=deleted_count)
        }, status=status.HTTP_200_OK)


class UpdateProjectSettingsView(APIView):
    """Update slideshow project settings."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def put(self, request, project_id):
        """Update project settings."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update allowed fields
        allowed_fields = [
            'name', 'slide_duration', 'fps', 'width', 'height',
            'use_transitions', 'transition_type', 'transition_duration',
            'video_bitrate', 'audio_bitrate', 'video_codec'
        ]
        
        for field in allowed_fields:
            if field in request.data:
                setattr(project, field, request.data[field])
        
        project.save()
        
        return Response({
            'status': 'success',
            'message': _('Settings updated')
        }, status=status.HTTP_200_OK)


class GenerateSlideshowView(APIView):
    """Generate slideshow video."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, project_id):
        """Start slideshow generation."""
        from .tasks import generate_slideshow_task
        
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Project is already being processed')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate project has required files
        if not project.media_files.exists():
            return Response({
                'error': _('No media files in project')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not project.audio_files.exists():
            return Response({
                'error': _('No audio file in project')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start async task
        task = generate_slideshow_task.delay(project.id)
        
        logger.info(f"Slideshow generation started: project_id={project.id}, task_id={task.id}, user={request.user.email}")
        
        return Response({
            'status': 'success',
            'message': _('Generation started'),
            'task_id': task.id
        }, status=status.HTTP_200_OK)


class ProjectStatusView(APIView):
    """Get slideshow project status."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, project_id):
        """Get project status."""
        project = get_project_or_403(request, project_id)
        
        return Response({
            'status': project.status,
            'error_message': project.error_message,
            'output_file': project.output_file.url if project.output_file else None,
            'output_stream_url': reverse('tools:slideshow_output_stream', args=[project.id])
            if project.output_file else None,
            'created_at': project.created_at,
            'updated_at': project.updated_at,
            'completed_at': project.completed_at
        }, status=status.HTTP_200_OK)


class DownloadSlideshowView(APIView):
    """Download generated slideshow video."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, project_id):
        """Download generated video."""
        project = get_project_or_403(request, project_id)
        
        if not project.output_file:
            raise Http404(_("Video not generated yet"))
        
        try:
            output_path = resolve_tools_output_path(project.output_file)
        except Exception:
            raise Http404(_("Video file not found"))
        if not output_path.exists():
            raise Http404(_("Video file not found"))
        
        return FileResponse(
            open(output_path, 'rb'),
            content_type='video/mp4',
            filename=Path(project.output_file.name).name
        )


class DeleteProjectView(APIView):
    """Delete slideshow project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, project_id):
        """Delete project."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot delete project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        project_id = project.id
        project.delete()
        
        logger.info(f"Slideshow project deleted: id={project_id}, user={request.user.email}")
        
        return Response({
            'status': 'success',
            'message': _('Project deleted')
        }, status=status.HTTP_200_OK)


class LibraryAudioListView(APIView):
    """List library audio files."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get list of library audio files."""
        audio_files = SlideshowAudio.objects.filter(is_library=True).order_by('name')
        
        return Response({
            'count': audio_files.count(),
            'results': [
                {
                    'id': audio.id,
                    'name': audio.name,
                    'duration': audio.duration,
                    'url': audio.get_file_url() if audio.file else None
                }
                for audio in audio_files
            ]
        }, status=status.HTTP_200_OK)


class UpdateMediaOrderView(APIView):
    """Update media file order."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, project_id):
        """Update media order."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        order_mapping = request.data.get('order', {})
        if not isinstance(order_mapping, dict):
            return Response({
                'error': _('Invalid order format')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update order for each media file
        updated_count = 0
        for media_id_str, new_order in order_mapping.items():
            try:
                # Convert media_id to int (may come as string from JavaScript)
                media_id = int(media_id_str)
                new_order = int(new_order)  # Ensure order is int
                media = SlideshowMedia.objects.get(id=media_id, project=project)
                old_order = media.order
                media.order = new_order
                media.save(update_fields=['order'])
                updated_count += 1
                logger.debug(f"Updated media {media_id} order from {old_order} to {new_order} for project {project_id}")
            except (ValueError, SlideshowMedia.DoesNotExist) as e:
                logger.warning(f"Failed to update order for media_id={media_id_str}: {e}")
                continue
        
        logger.info(f"Updated order for {updated_count} media files in project {project_id}")
        
        return Response({
            'status': 'success',
            'message': _('Order updated'),
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)


class DeleteMediaView(APIView):
    """Delete media file from project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, project_id, media_id):
        """Delete media file."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        media = get_object_or_404(SlideshowMedia, id=media_id, project=project)
        media.delete()
        
        return Response({
            'status': 'success',
            'message': _('Media deleted')
        }, status=status.HTTP_200_OK)


class MakeProjectMediaLibraryView(APIView):
    """Make a project media file available in the library."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, project_id, media_id):
        """Create a library entry from a project media file."""
        project = get_project_or_403(request, project_id)

        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)

        media = get_object_or_404(SlideshowMedia, id=media_id, project=project)

        existing = SlideshowMedia.objects.filter(
            is_library=True,
            file=media.file
        ).first()
        if existing:
            return Response({
                'status': 'success',
                'library_media_id': existing.id,
                'message': _('Media already in library')
            }, status=status.HTTP_200_OK)

        library_media = SlideshowMedia.objects.create(
            project=None,
            file=media.file,
            name=media.name,
            media_type=media.media_type,
            order=0,
            is_library=True
        )

        return Response({
            'status': 'success',
            'library_media_id': library_media.id,
            'message': _('Media added to library')
        }, status=status.HTTP_200_OK)


class LibraryMediaListView(APIView):
    """List library media files."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get list of library media files."""
        media_type = request.GET.get('type', None)  # 'image' or 'video'
        
        queryset = SlideshowMedia.objects.filter(is_library=True)
        if media_type in ['image', 'video']:
            queryset = queryset.filter(media_type=media_type)
        
        media_files = queryset.order_by('-uploaded_at')
        
        return Response({
            'count': media_files.count(),
            'results': [
                {
                    'id': media.id,
                    'name': media.name or Path(media.file.name).name,
                    'media_type': media.media_type,
                    'url': media.get_file_url() if media.file else None,
                    'uploaded_at': media.uploaded_at
                }
                for media in media_files
            ]
        }, status=status.HTTP_200_OK)


class UploadLibraryMediaView(APIView):
    """Upload media files to library."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """Upload media files to library."""
        if not request.user.is_staff:
            raise PermissionDenied(_('Only staff members can upload to library.'))
        
        files = request.FILES.getlist('files')
        if not files:
            return Response({
                'error': _('No files provided')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded = []
        errors = []
        
        for file in files:
            try:
                name = request.data.get('name', Path(file.name).stem)
                
                media = SlideshowMedia.objects.create(
                    file=file,
                    name=name,
                    is_library=True,
                    project=None
                )
                uploaded.append({
                    'id': media.id,
                    'name': media.name,
                    'media_type': media.media_type,
                    'url': media.get_file_url()
                })
            except Exception as e:
                logger.error(f"Failed to upload library media: {e}", exc_info=True)
                errors.append(f"{file.name}: {str(e)}")
        
        return Response({
            'status': 'success',
            'uploaded': uploaded,
            'errors': errors if errors else None
        }, status=status.HTTP_200_OK)


class AddLibraryMediaToProjectView(APIView):
    """Add media from library to project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, project_id):
        """Add library media to project."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        library_media_ids = request.data.get('media_ids', [])
        if not library_media_ids:
            return Response({
                'error': _('No media IDs provided')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        added = []
        errors = []
        
        # Get current max order
        max_order = SlideshowMedia.objects.filter(project=project).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0
        
        for media_id in library_media_ids:
            try:
                # Get library media file
                library_media = SlideshowMedia.objects.get(id=media_id, is_library=True)
                
                # Create a copy for this project (copy file reference, not the file itself)
                media = SlideshowMedia.objects.create(
                    project=project,
                    file=library_media.file,  # Reference same file
                    name=library_media.name,
                    media_type=library_media.media_type,
                    order=max_order + 1,
                    is_library=False
                )
                max_order += 1
                
                added.append({
                    'id': media.id,
                    'name': media.name,
                    'media_type': media.media_type,
                    'order': media.order
                })
            except SlideshowMedia.DoesNotExist:
                errors.append(_("Media {media_id} not found in library").format(media_id=media_id))
            except Exception as e:
                logger.error(f"Failed to add library media to project: {e}", exc_info=True)
                errors.append(_("Media {media_id}: {error}").format(media_id=media_id, error=str(e)))
        
        return Response({
            'status': 'success',
            'added': added,
            'errors': errors if errors else None
        }, status=status.HTTP_200_OK)


class DeleteLibraryMediaView(APIView):
    """Delete media file from library."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, media_id):
        """Delete library media file."""
        if not request.user.is_staff:
            raise PermissionDenied(_('Only staff members can delete library files.'))
        
        media = get_object_or_404(SlideshowMedia, id=media_id, is_library=True)
        media.delete()
        
        return Response({
            'status': 'success',
            'message': _('Library media deleted')
        }, status=status.HTTP_200_OK)


class AddLibraryAudioToProjectView(APIView):
    """Add audio from library to project."""
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, project_id):
        """Add library audio to project."""
        project = get_project_or_403(request, project_id)
        
        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        library_audio_id = request.data.get('audio_id')
        if not library_audio_id:
            return Response({
                'error': _('No audio ID provided')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get library audio file
            library_audio = SlideshowAudio.objects.get(id=library_audio_id, is_library=True)
            
            # Remove existing audio files for this project
            SlideshowAudio.objects.filter(project=project).delete()
            
            # Create a copy for this project (reference same file)
            audio = SlideshowAudio.objects.create(
                project=project,
                file=library_audio.file,  # Reference same file
                name=library_audio.name,
                duration=library_audio.duration,
                is_library=False
            )
            
            return Response({
                'status': 'success',
                'audio': {
                    'id': audio.id,
                    'name': audio.name,
                    'duration': audio.duration
                }
            }, status=status.HTTP_200_OK)
            
        except SlideshowAudio.DoesNotExist:
            return Response({
                'error': _('Audio {audio_id} not found in library').format(audio_id=library_audio_id)
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to add library audio to project: {e}", exc_info=True)
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MakeProjectAudioLibraryView(APIView):
    """Make a project audio file available in the library."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, project_id, audio_id):
        """Create a library entry from a project audio file."""
        project = get_project_or_403(request, project_id)

        if project.status == 'processing':
            return Response({
                'error': _('Cannot modify project while processing')
            }, status=status.HTTP_400_BAD_REQUEST)

        audio = get_object_or_404(SlideshowAudio, id=audio_id, project=project)

        existing = SlideshowAudio.objects.filter(
            is_library=True,
            file=audio.file
        ).first()
        if existing:
            return Response({
                'status': 'success',
                'library_audio_id': existing.id,
                'message': _('Audio already in library')
            }, status=status.HTTP_200_OK)

        library_audio = SlideshowAudio.objects.create(
            project=None,
            file=audio.file,
            name=audio.name,
            duration=audio.duration,
            is_library=True
        )

        return Response({
            'status': 'success',
            'library_audio_id': library_audio.id,
            'message': _('Audio added to library')
        }, status=status.HTTP_200_OK)


class AudioPresetsView(APIView):
    """List available audio normalization presets."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        _require_staff(request)
        presets_json = load_audio_presets()
        presets = presets_json.get('presets', [])
        return Response({
            'version': presets_json.get('version'),
            'defaults': presets_json.get('defaults', {}),
            'results': [
                {
                    'id': p.get('id'),
                    'title': p.get('title'),
                    'tags': p.get('tags', []),
                }
                for p in presets
            ]
        }, status=status.HTTP_200_OK)


class MediaFilesByNumberView(APIView):
    """Search media_files.VideoFile by number; returns files under MEDIA_ROOT or in storage locations."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        _require_staff(request)

        if not _media_files_available():
            raise Http404(_("Media files module is not available"))

        number_raw = (request.GET.get('number') or '').strip()
        if not number_raw.isdigit():
            return Response({'error': _('Invalid number')}, status=status.HTTP_400_BAD_REQUEST)
        number = int(number_raw)

        try:
            from media_files.models import VideoFile  # type: ignore
        except Exception:
            raise Http404(_("Media files module is not available"))

        qs = (
            VideoFile.objects
            .filter(number=number, is_available=True)
            .select_related('storage_location')
        )
        versions = list(qs)

        media_root_abs = _media_root_abs()
        results = []
        for v in versions:
            if not v.storage_location or not getattr(v.storage_location, 'path', None):
                continue
            base = Path(v.storage_location.path)
            rel = str(v.file_path or '').lstrip('/\\')
            abs_path = (base / rel).resolve()
            if not abs_path.exists() or not abs_path.is_file():
                continue

            try:
                relpath = str(abs_path.relative_to(media_root_abs)).replace("\\", "/")
                under_media = True
            except ValueError:
                relpath = None
                under_media = False

            stream_url = reverse("admin:media_files_videofile_stream", args=[v.id])
            results.append({
                'id': v.id,
                'number': v.number,
                'filename': v.filename,
                'storage_location': str(getattr(v.storage_location, 'name', '') or ''),
                'relpath': relpath,
                'url': f"/media/{relpath}" if relpath else None,
                'external': not under_media,
                'video_file_id': v.id,
                'stream_url': stream_url,
                'is_primary': bool(getattr(v, 'is_primary_version', lambda: False)()),
                'total_bitrate': getattr(v, 'total_bitrate', None),
            })

        # Prefer primary version, otherwise highest bitrate
        def _sort_key(x):
            return (
                1 if x.get('is_primary') else 0,
                int(x.get('total_bitrate') or 0),
            )
        results.sort(key=_sort_key, reverse=True)

        return Response({
            'count': len(results),
            'results': results,
        }, status=status.HTTP_200_OK)


class VideoRenderSearchView(APIView):
    """Search media_files.VideoFile by number for the video render tool."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        _require_staff(request)

        if not _media_files_available():
            raise Http404(_("Media files module is not available"))

        number_raw = (request.GET.get("number") or "").strip()
        if not number_raw.isdigit():
            return Response({"error": _("Invalid number")}, status=status.HTTP_400_BAD_REQUEST)
        number = int(number_raw)

        try:
            from media_files.models import VideoFile  # type: ignore
        except Exception:
            raise Http404(_("Media files module is not available"))

        qs = (
            VideoFile.objects
            .filter(number=number, is_available=True)
            .select_related("storage_location")
            .order_by("-created_at")
        )
        results = []
        for v in qs:
            results.append(
                {
                    "id": v.id,
                    "number": v.number,
                    "filename": v.filename,
                    "storage_location": str(getattr(v.storage_location, "name", "") or ""),
                    "admin_url": reverse("admin:media_files_videofile_change", args=[v.id]),
                    "stream_url": reverse("admin:media_files_videofile_stream", args=[v.id]),
                    "file_path": getattr(v, "file_path", ""),
                }
            )

        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)


class VideoRenderSubmitView(APIView):
    """Submit a video render job (creates VideoFile + FileOperation, queues Celery task)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        _require_staff(request)

        if not _media_files_available():
            raise Http404(_("Media files module is not available"))

        try:
            from media_files.models import VideoFile, FileOperation  # type: ignore
            from licenses.models import License  # type: ignore
        except Exception:
            raise Http404(_("Media files module is not available"))

        video_id_raw = str(request.data.get("video_id") or "").strip()
        if not video_id_raw.isdigit():
            return Response({"success": False, "error": _("Missing required parameters: video_id")}, status=status.HTTP_400_BAD_REQUEST)
        video_id = int(video_id_raw)

        try:
            selected_video = VideoFile.objects.get(id=video_id)
        except VideoFile.DoesNotExist:
            return Response({"success": False, "error": _("Video not found")}, status=status.HTTP_404_NOT_FOUND)

        license_obj = selected_video.get_license()
        if not license_obj:
            return Response({"success": False, "error": _("License not found for this video")}, status=status.HTTP_404_NOT_FOUND)

        encode_name = (request.data.get("encoding") or "1080p25_9000k").strip()
        is_preview = str(request.data.get("preview") or "false").lower() in ("true", "1", "yes", "on")
        use_intro_outro = str(request.data.get("use_intro_outro") or "false").lower() in ("true", "1", "yes", "on")
        invert_text_color = str(request.data.get("invert_text_color") or "false").lower() in ("true", "1", "yes", "on")
        output_filename_raw = (request.data.get("output_filename") or "").strip()

        show_title = str(request.data.get("show_title") or "false").lower() in ("true", "1", "yes", "on")
        show_subtitle = str(request.data.get("show_subtitle") or "false").lower() in ("true", "1", "yes", "on")
        show_broadcast_resp = str(request.data.get("show_broadcast_resp") or "false").lower() in ("true", "1", "yes", "on")
        show_media_authority = str(request.data.get("show_media_authority") or "false").lower() in ("true", "1", "yes", "on")

        style_title = (request.data.get("style_title") or "").strip() or None
        style_subtitle = (request.data.get("style_subtitle") or "").strip() or None
        style_broadcast = (request.data.get("style_broadcast") or "").strip() or None
        style_authority = (request.data.get("style_authority") or "").strip() or None

        overlay_text_title = (request.data.get("overlay_text_title") or "").strip() or None
        overlay_text_subtitle = (request.data.get("overlay_text_subtitle") or "").strip() or None
        overlay_text_broadcast = (request.data.get("overlay_text_broadcast") or "").strip() or None
        overlay_text_authority = (request.data.get("overlay_text_authority") or "").strip() or None

        if not (show_title or show_subtitle or show_broadcast_resp or show_media_authority):
            return Response({"success": False, "error": _("Please select at least one element to show")}, status=status.HTTP_400_BAD_REQUEST)

        if not any(
            [
                (show_title and style_title),
                (show_subtitle and style_subtitle),
                (show_broadcast_resp and style_broadcast),
                (show_media_authority and style_authority),
            ]
        ):
            return Response({"success": False, "error": _("Please select styles for each selected element.")}, status=status.HTTP_400_BAD_REQUEST)

        # Pick a source video: prefer a non-rendered version for this license number
        source_video = None
        try:
            all_videos = (
                VideoFile.objects
                .filter(number=license_obj.number, is_available=True)
                .order_by("-created_at")
            )
            for v in all_videos:
                if not (v.file_path or "").startswith("rendered/"):
                    source_video = v
                    break
        except Exception:
            source_video = None

        if not source_video:
            # Fallback to selected video if it is not in rendered/
            if selected_video.file_path and not selected_video.file_path.startswith("rendered/"):
                source_video = selected_video

        if not source_video:
            return Response(
                {
                    "success": False,
                    "error": _("Source video file not found. Please ensure there is an original (non-rendered) video file available."),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build combined style name for logging/traceability
        style_name_parts = []
        if show_title and style_title:
            style_name_parts.append(f"t_{style_title}")
        if show_subtitle and style_subtitle:
            style_name_parts.append(f"s_{style_subtitle}")
        if show_broadcast_resp and style_broadcast:
            style_name_parts.append(f"b_{style_broadcast}")
        if show_media_authority and style_authority:
            style_name_parts.append(f"a_{style_authority}")
        combined_style_name = "_".join(style_name_parts) if style_name_parts else "custom"

        # Prepare output path: save in the same directory as source, with version suffix
        storage_root = Path(source_video.storage_location.path)
        source_rel_path = Path(source_video.file_path)
        rel_dir = source_rel_path.parent
        src_stem = Path(source_video.filename).stem

        base_suffix = ".mp4"
        base_stem = f"{src_stem}_preview" if is_preview else src_stem

        # If output filename is explicitly provided, use it (ensure .mp4 and keep it in the same directory)
        explicit_output = None
        if output_filename_raw:
            safe_name = Path(output_filename_raw).name  # strip any path parts
            if not safe_name.lower().endswith(".mp4"):
                safe_name = f"{Path(safe_name).stem}.mp4"
            if not safe_name or safe_name in (".mp4",):
                return Response({"success": False, "error": _("Invalid output filename")}, status=status.HTTP_400_BAD_REQUEST)
            explicit_output = rel_dir / safe_name

        def is_path_taken(candidate_rel: Path) -> bool:
            cand_str = str(candidate_rel).replace("\\", "/")
            if VideoFile.objects.filter(storage_location=source_video.storage_location, file_path=cand_str).exists():
                return True
            abs_candidate = storage_root / candidate_rel
            return abs_candidate.exists()

        if explicit_output is not None:
            # If taken, append _vN before extension
            if not is_path_taken(explicit_output):
                rel_out = explicit_output
            else:
                stem2 = explicit_output.stem
                version = 1
                while version < 1000:
                    candidate = rel_dir / f"{stem2}_v{version}{base_suffix}"
                    if not is_path_taken(candidate):
                        rel_out = candidate
                        break
                    version += 1
                else:
                    return Response({"success": False, "error": _("Could not find a free output filename (too many versions exist).")}, status=status.HTTP_400_BAD_REQUEST)
        else:
            version = 1
            while version < 1000:
                candidate_name = f"{base_stem}_v{version}{base_suffix}"
                rel_out = rel_dir / candidate_name
                if not is_path_taken(rel_out):
                    break
                version += 1
            else:
                return Response({"success": False, "error": _("Could not find a free output filename (too many versions exist).")}, status=status.HTTP_400_BAD_REQUEST)

        abs_out = storage_root / rel_out
        abs_out.parent.mkdir(parents=True, exist_ok=True)

        new_video = VideoFile.objects.create(
            number=source_video.number,
            filename=abs_out.name,
            file_path=str(rel_out).replace("\\", "/"),
            storage_location=source_video.storage_location,
            is_available=False,
            is_preview=is_preview,
        )

        operation = FileOperation.objects.create(
            video_file=new_video,
            operation_type="RENDER",
            source_location=source_video.storage_location,
            destination_location=source_video.storage_location,
            performed_by=request.user,
            status="IN_PROGRESS",
            details={
                "source": "tools_video_render",
                "source_video_id": source_video.id,
                "license_number": license_obj.number,
                "style": combined_style_name,
                "encode": encode_name,
                "preview": is_preview,
                "use_intro_outro": use_intro_outro,
                "invert_text_color": invert_text_color,
                "elements": {
                    "title": show_title,
                    "subtitle": show_subtitle,
                    "broadcast_resp": show_broadcast_resp,
                    "media_authority": show_media_authority,
                },
                "styles": {
                    "title": style_title,
                    "subtitle": style_subtitle,
                    "broadcast": style_broadcast,
                    "authority": style_authority,
                },
                "overlay_texts": {
                    "title": overlay_text_title,
                    "subtitle": overlay_text_subtitle,
                    "broadcast": overlay_text_broadcast,
                    "authority": overlay_text_authority,
                },
            },
        )

        from media_files.tasks import render_video_task  # type: ignore
        render_video_task.delay(operation.id)

        return Response(
            {
                "success": True,
                "video_id": new_video.id,
                "operation_id": operation.id,
                "message": _("Video rendering started. You can track progress in File Operations."),
                "redirect_url": reverse("tools:video_render_jobs") + f"?op={operation.id}",
            },
            status=status.HTTP_200_OK,
        )


class VideoRenderUploadView(APIView):
    """Upload a local video into Media Files and open the render tool for it."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        _require_staff(request)

        if not _media_files_available():
            raise Http404(_("Media files module is not available"))

        try:
            from media_files.models import StorageLocation, VideoFile  # type: ignore
            from licenses.models import License  # type: ignore
        except Exception:
            raise Http404(_("Media files module is not available"))

        number_raw = (request.data.get("license_number") or request.data.get("number") or "").strip()
        if not str(number_raw).isdigit():
            return Response({"success": False, "error": _("Invalid number")}, status=status.HTTP_400_BAD_REQUEST)
        number = int(number_raw)

        try:
            License.objects.get(number=number)
        except License.DoesNotExist:
            return Response({"success": False, "error": _("License not found")}, status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get("file")
        if not file:
            return Response({"success": False, "error": _("No file provided")}, status=status.HTTP_400_BAD_REQUEST)

        media_root_abs = _media_root_abs()
        rel_dir = Path("tools/video_render/input")
        abs_dir = (media_root_abs / rel_dir).resolve()
        abs_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(getattr(file, "name", "upload.mp4")).name
        stem = Path(original_name).stem
        ext = Path(original_name).suffix or ".mp4"
        safe_ext = ext if ext.lower() in [".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"] else ".mp4"

        def _pick_unique_filename() -> str:
            candidate = f"{stem}{safe_ext}"
            if not (abs_dir / candidate).exists():
                return candidate
            for i in range(1, 200):
                cand = f"{stem}_v{i}{safe_ext}"
                if not (abs_dir / cand).exists():
                    return cand
            return f"{stem}_v{number}{safe_ext}"

        filename = _pick_unique_filename()
        abs_path = abs_dir / filename

        with open(abs_path, "wb") as out:
            for chunk in file.chunks():
                out.write(chunk)

        storage_location, _created = StorageLocation.objects.get_or_create(
            path=str(media_root_abs),
            defaults={
                "name": "Media (Local)",
                "storage_type": "CUSTOM",
                "is_active": True,
            },
        )

        rel_path = str((rel_dir / filename).as_posix())

        video = VideoFile.objects.create(
            number=number,
            filename=filename,
            file_path=rel_path,
            storage_location=storage_location,
            is_available=True,
        )

        return Response(
            {
                "success": True,
                "video_id": video.id,
                "redirect_url": reverse("tools:video_render", args=[video.id]),
            },
            status=status.HTTP_201_CREATED,
        )


class CreateAudioNormalizeJobView(APIView):
    """Create a new audio normalization job (upload input file)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        _require_staff(request)

        config = ToolsConfig.get_config()

        def _media_root_abs() -> Path:
            media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
            if media_root.is_absolute():
                return media_root.resolve()
            base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
            return (base_dir / media_root).resolve()

        def _resolve_existing_input(rel_or_url: str) -> str:
            """
            Resolve an existing file path under MEDIA_ROOT and return a FileField name (relative to MEDIA_ROOT).
            Accepts '/media/<path>' or '<path>'.
            """
            value = (rel_or_url or "").strip()
            if value.startswith("/media/"):
                value = value[len("/media/"):]
            value = value.lstrip("/\\")
            if not value or ".." in Path(value).parts:
                raise ValueError("Invalid input path")
            media_root_abs = _media_root_abs()
            abs_path = (media_root_abs / value).resolve()
            if not abs_path.exists():
                raise FileNotFoundError("Input file not found")
            # Ensure within media root
            abs_path.relative_to(media_root_abs)
            return str(abs_path.relative_to(media_root_abs)).replace("\\", "/")

        existing_input = (request.data.get("input_path") or request.data.get("input_file_url") or "").strip()
        input_media_file_id_raw = request.data.get("input_media_file_id")
        try:
            input_media_file_id = int(input_media_file_id_raw) if input_media_file_id_raw not in (None, "") else None
        except (TypeError, ValueError):
            input_media_file_id = None
        file = request.FILES.get('file')
        if not file and not existing_input and not input_media_file_id:
            return Response({'error': _('No file provided')}, status=status.HTTP_400_BAD_REQUEST)

        preset_id = request.data.get('preset_id', 'tv_natural')
        target = request.data.get('target', 'tv')
        audio_bitrate = request.data.get('audio_bitrate', '192k')
        sample_rate = int(request.data.get('sample_rate', 48000))
        force_stereo = str(request.data.get('force_stereo', 'false')).lower() in ('1', 'true', 'yes', 'on')
        output_filename = (request.data.get('output_filename') or '').strip()
        
        # Log preset_id for debugging
        logger.info("Creating audio normalize job with preset_id: %s (from request: %s)", preset_id, request.data.get('preset_id'))

        # Resolve input: (1) by media_files.VideoFile id (can be outside MEDIA_ROOT),
        # (2) existing path under MEDIA_ROOT, (3) upload.
        input_file_value = None
        input_path_external = ""
        input_media_file_id_save = None
        input_stream_url = None

        if input_media_file_id:
            try:
                from media_files.models import VideoFile  # type: ignore
                v = VideoFile.objects.select_related('storage_location').get(id=input_media_file_id, is_available=True)
            except Exception:
                return Response({'error': _('Input file not found')}, status=status.HTTP_400_BAD_REQUEST)
            if not v.storage_location or not getattr(v.storage_location, 'path', None):
                return Response({'error': _('Input file not found')}, status=status.HTTP_400_BAD_REQUEST)
            abs_path = (Path(v.storage_location.path) / (v.file_path or '').lstrip('/\\')).resolve()
            if not abs_path.exists() or not abs_path.is_file():
                return Response({'error': _('Input file not found')}, status=status.HTTP_400_BAD_REQUEST)
            input_path_external = str(abs_path)
            input_media_file_id_save = v.id
            input_stream_url = reverse("admin:media_files_videofile_stream", args=[v.id])
        elif existing_input:
            try:
                input_file_value = _resolve_existing_input(existing_input)
            except Exception:
                return Response({'error': _('Input file not found')}, status=status.HTTP_400_BAD_REQUEST)
        elif file:
            # If the same file already exists under configured input storage/path (or MEDIA_ROOT), reuse it to avoid duplicates.
            media_root_abs = _media_root_abs()
            storage = getattr(config, "audio_normalize_input_storage", None)
            if storage and getattr(storage, "path", None):
                base_path = Path(storage.path).resolve()
            else:
                base = (config.audio_normalize_input_path or "").strip()
                if base:
                    base_path = Path(base)
                    if not base_path.is_absolute():
                        base_path = (media_root_abs / base.lstrip("/\\")).resolve()
                    else:
                        base_path = base_path.resolve()
                else:
                    base_path = media_root_abs

            candidate = (base_path / Path(file.name).name).resolve()
            try:
                if candidate.exists() and candidate.is_file():
                    try:
                        if int(candidate.stat().st_size) == int(getattr(file, "size", -1)):
                            # Reuse only if it's also within MEDIA_ROOT (so we can serve it)
                            input_file_value = str(candidate.relative_to(media_root_abs)).replace("\\", "/")
                    except Exception:
                        pass
            except Exception:
                pass

        job = AudioNormalizeJob.objects.create(
            created_by=request.user,
            preset_id=preset_id,
            target=target,
            audio_bitrate=audio_bitrate,
            sample_rate=sample_rate,
            force_stereo=force_stereo,
            output_filename=output_filename,
            input_file=input_file_value or file or '',
            input_path_external=input_path_external or '',
            input_media_file_id=input_media_file_id_save,
        )

        return Response({
            'status': 'success',
            'job_id': job.id,
            'input_stream_url': input_stream_url,
        }, status=status.HTTP_201_CREATED)


class AnalyzeOnlyView(APIView):
    """Run analysis only (ffprobe + loudnorm pass 1)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        if job.status in ('analyzing', 'processing'):
            return Response({'error': _('Job is already running')}, status=status.HTTP_400_BAD_REQUEST)

        from .tasks import analyze_audio_normalize_job_task
        task = analyze_audio_normalize_job_task.delay(job.id)
        return Response({
            'status': 'success',
            'message': _('Analysis started'),
            'task_id': task.id,
        }, status=status.HTTP_200_OK)


class StartNormalizeView(APIView):
    """Start full audio normalization job."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        if job.status in ('analyzing', 'processing'):
            return Response({'error': _('Job is already running')}, status=status.HTTP_400_BAD_REQUEST)

        # Update job settings from request before starting (user may have changed preset after analysis)
        updated_fields = []
        if 'preset_id' in request.data:
            job.preset_id = request.data['preset_id']
            updated_fields.append('preset_id')
        if 'audio_bitrate' in request.data:
            job.audio_bitrate = request.data['audio_bitrate']
            updated_fields.append('audio_bitrate')
        if 'sample_rate' in request.data:
            job.sample_rate = int(request.data['sample_rate'])
            updated_fields.append('sample_rate')
        if 'force_stereo' in request.data:
            job.force_stereo = str(request.data['force_stereo']).lower() in ('1', 'true', 'yes', 'on')
            updated_fields.append('force_stereo')
        
        if updated_fields:
            job.save(update_fields=updated_fields)
            logger.info("Updated job %s settings before normalize: %s", job_id, updated_fields)

        from .tasks import normalize_audio_task
        task = normalize_audio_task.delay(job.id)
        return Response({
            'status': 'success',
            'message': _('Normalization started'),
            'task_id': task.id,
        }, status=status.HTTP_200_OK)


class AudioJobStatusView(APIView):
    """Get job status and report."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        recommendations = []
        noise_analysis = None
        normalization_type = None
        normalization_warning = None
        if job.input_metadata and isinstance(job.input_metadata, dict):
            noise_analysis = job.input_metadata.get("noise_analysis")
            normalization_type = job.input_metadata.get("normalization_type")
            normalization_warning = job.input_metadata.get("normalization_warning")
        if job.analysis_before:
            try:
                recommendations = AudioNormalizerService(job).get_recommendations(job.analysis_before, noise_analysis)
            except Exception:
                recommendations = []

        input_stream_url = None
        if getattr(job, 'input_media_file_id', None):
            try:
                from media_files.models import VideoFile  # type: ignore
                v = VideoFile.objects.get(id=job.input_media_file_id)
                input_stream_url = reverse("admin:media_files_videofile_stream", args=[v.id])
            except Exception:
                pass

        return Response({
            'id': job.id,
            'status': job.status,
            'progress': job.progress,
            'preset_id': job.preset_id,
            'target': job.target,
            'audio_bitrate': job.audio_bitrate,
            'sample_rate': job.sample_rate,
            'force_stereo': job.force_stereo,
            'output_filename': job.output_filename,
            'input_file': Path(job.input_file.name).name if job.input_file else None,
            'input_file_url': job.input_file.url if job.input_file else None,
            'input_stream_url': input_stream_url,
            'output_file': job.output_file.url if job.output_file else None,
            'output_path_external': (job.output_path_external or '').strip() or None,
            'output_stream_url': reverse('tools:api_audio_stream_output', args=[job.id])
            if (getattr(job, 'output_path_external', '') or '').strip() else None,
            'error_message': job.error_message,
            'ffmpeg_log_tail': (job.ffmpeg_log or '')[-5000:],
            'input_metadata': job.input_metadata,
            'analysis_before': job.analysis_before,
            'analysis_after': job.analysis_after,
            'noise_analysis': noise_analysis,
            'normalization_type': normalization_type,
            'normalization_warning': normalization_warning,
            'recommendations': recommendations,
            'created_at': job.created_at,
            'started_at': job.started_at,
            'completed_at': job.completed_at,
        }, status=status.HTTP_200_OK)


class AudioWaveformView(APIView):
    """Get cached waveform peaks for before/after audio."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        kind = request.GET.get('kind', 'before')
        if kind not in ('before', 'after'):
            return Response({'error': _('Invalid kind')}, status=status.HTTP_400_BAD_REQUEST)

        if kind == 'before':
            ext = (getattr(job, 'input_path_external', '') or '').strip()
            if ext:
                input_path = Path(ext)
            elif job.input_file and (job.input_file.name or '').strip():
                input_path = Path(job.input_file.path)
            else:
                raise Http404(_("Input file not found"))
        else:
            ext_out = (getattr(job, 'output_path_external', '') or '').strip()
            if ext_out:
                input_path = Path(ext_out)
            elif job.output_file and (job.output_file.name or '').strip():
                input_path = Path(job.output_file.path)
            else:
                raise Http404(_("Output file not found"))

        service = AudioNormalizerService(job)
        try:
            meta, probe = service.probe(input_path)
            duration_sec = probe.duration_sec
        except Exception:
            duration_sec = 0.0
            meta = {}

        try:
            data = load_or_generate_waveform(job, kind, input_path, duration_sec)
        except WaveformError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        data['source'] = kind
        data['file'] = Path(input_path.name).name
        if meta:
            data['metadata'] = {
                'duration': meta.get('format', {}).get('duration'),
                'format': meta.get('format', {}).get('format_name'),
            }

        return Response(data, status=status.HTTP_200_OK)


class StreamOutputView(APIView):
    """Stream output file from output_path_external with HTTP Range support (for video preview)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        ext = (getattr(job, 'output_path_external', '') or '').strip()
        if not ext:
            raise Http404(_("Output file not found"))
        abs_path = Path(ext).resolve()
        if not abs_path.exists() or not abs_path.is_file():
            raise Http404(_("Output file not found"))

        size = abs_path.stat().st_size
        content_type = mimetypes.guess_type(str(abs_path))[0] or "video/mp4"

        range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
        if not range_header:
            resp = FileResponse(open(abs_path, "rb"), content_type=content_type)
            resp["Accept-Ranges"] = "bytes"
            resp["Content-Length"] = str(size)
            return resp

        m = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
        if not m:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            return resp
        start_s, end_s = m.groups()
        if start_s == "" and end_s == "":
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            return resp
        if start_s == "":
            suffix_len = int(end_s)
            if suffix_len <= 0:
                resp = HttpResponse(status=416)
                resp["Content-Range"] = f"bytes */{size}"
                return resp
            start = max(0, size - suffix_len)
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        if start < 0 or start >= size or end < start:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            return resp
        end = min(end, size - 1)
        length = end - start + 1

        def iterator(path: Path, offset: int, count: int, chunk_size: int = 1024 * 512):
            f = open(path, "rb")
            try:
                f.seek(offset)
                remaining = count
                while remaining > 0:
                    data = f.read(min(chunk_size, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
            finally:
                try:
                    f.close()
                except Exception:
                    pass

        resp = StreamingHttpResponse(iterator(abs_path, start, length), status=206, content_type=content_type)
        resp["Accept-Ranges"] = "bytes"
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp["Content-Length"] = str(length)
        return resp


class DownloadNormalizedView(APIView):
    """Download normalized output file."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        ext = (getattr(job, 'output_path_external', '') or '').strip()
        if ext:
            abs_path = Path(ext).resolve()
            if not abs_path.exists() or not abs_path.is_file():
                raise Http404(_("Output file not found"))
            fname = job.output_filename or abs_path.name
            ct = mimetypes.guess_type(str(abs_path))[0] or 'video/mp4'
            return FileResponse(
                open(abs_path, 'rb'),
                content_type=ct,
                as_attachment=True,
                filename=Path(fname).name
            )
        if not job.output_file:
            raise Http404(_("Output file not generated yet"))
        if not job.output_file.path or not Path(job.output_file.path).exists():
            raise Http404(_("Output file not found"))
        return FileResponse(
            open(job.output_file.path, 'rb'),
            content_type='video/mp4',
            as_attachment=True,
            filename=Path(job.output_file.name).name
        )


class DeleteAudioJobView(APIView):
    """Delete audio normalization job and its files."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, job_id):
        _require_staff(request)
        job = get_audio_job_or_403(request, job_id)

        if job.status in ('analyzing', 'processing'):
            return Response({'error': _('Cannot delete job while processing')}, status=status.HTTP_400_BAD_REQUEST)

        # Do not delete media files (input/output) here.
        # Best-effort cleanup of waveform cache.
        try:
            base = Path(settings.MEDIA_ROOT) / f"tools/audio_normalize/{job.id}/waveform"
            for f in (base / "before.json", base / "after.json"):
                if f.exists():
                    f.unlink()
            # Remove empty dir
            if base.exists() and base.is_dir() and not any(base.iterdir()):
                base.rmdir()
        except Exception:
            pass

        job.delete()
        return Response({'status': 'success', 'message': _('Job deleted')}, status=status.HTTP_200_OK)
