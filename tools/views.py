"""Views for Tools module."""

import mimetypes
import re
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, StreamingHttpResponse, FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .models import AudioNormalizeJob, SlideshowProject, SlideshowMedia, SlideshowAudio, ToolsConfig
from .utils import resolve_tools_output_path
from .services.audio_normalizer import load_audio_presets, PresetError


def check_tools_enabled():
    """Check if Tools module is enabled."""
    if not getattr(settings, 'TOOLS_ENABLED', False):
        raise ImproperlyConfigured(
            _('Tools module is disabled. Set TOOLS_ENABLED=true to enable.')
        )


def _media_files_available() -> bool:
    return bool(
        getattr(settings, "MEDIA_FILES_ENABLED", False)
        and "media_files" in getattr(settings, "INSTALLED_APPS", [])
    )


class ToolsIndexView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """Tools landing page (catalog)."""

    template_name = 'tools/index.html'
    
    def test_func(self):
        """Check if user is staff member."""
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        context['tools_enabled'] = True
        context["media_files_enabled"] = _media_files_available()
        return context


class SlideshowListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    """List all slideshow projects for current user."""
    
    model = SlideshowProject
    template_name = 'tools/slideshow_list.html'
    context_object_name = 'projects'
    paginate_by = 20
    
    def test_func(self):
        """Check if user is staff member."""
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Get projects for current user (or all for superusers)."""
        qs = SlideshowProject.objects.all()
        
        # Regular staff see only their projects, superusers see all
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        
        # Filter by status if provided
        status_filter = self.request.GET.get('status')
        if status_filter in ['draft', 'processing', 'completed', 'failed']:
            qs = qs.filter(status=status_filter)
        
        return qs.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.request.GET.get('status', '')
        context['tools_enabled'] = True
        return context


class SlideshowDetailView(UserPassesTestMixin, LoginRequiredMixin, DetailView):
    """View details of a slideshow project."""
    
    model = SlideshowProject
    template_name = 'tools/slideshow_detail.html'
    context_object_name = 'project'
    pk_url_kwarg = 'project_id'
    
    def get_object(self, queryset=None):
        """Get project by project_id from URL."""
        project_id = self.kwargs.get('project_id')
        if project_id is None:
            raise Http404("No project found matching the query")
        
        queryset = queryset or self.get_queryset()
        try:
            project = queryset.get(id=project_id)
        except SlideshowProject.DoesNotExist:
            raise Http404("No project found matching the query")
        
        return project
    
    def test_func(self):
        """Check if user is staff member and owns the project."""
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            return False
        
        # Get project for permission check
        project_id = self.kwargs.get('project_id')
        if not project_id:
            return False
        
        try:
            project = SlideshowProject.objects.get(id=project_id)
        except SlideshowProject.DoesNotExist:
            return False
        
        # Superusers can view any project
        if self.request.user.is_superuser:
            return True
        
        # Regular users can only view their own projects
        return project.created_by == self.request.user
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Get media files ordered by order field
        context['media_files'] = project.media_files.all().order_by('order', 'uploaded_at')
        
        # Get audio files
        context['audio_files'] = project.audio_files.all()
        
        context['tools_enabled'] = True
        return context


class SlideshowCreatorView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """Create or edit a slideshow project."""
    
    template_name = 'tools/slideshow_creator.html'
    
    def test_func(self):
        """Check if user is staff member and has access to project."""
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            return False
        
        # If editing, check project access
        project_id = self.kwargs.get('project_id')
        if project_id:
            try:
                project = SlideshowProject.objects.get(id=project_id)
                # Superusers can edit any project, regular users only their own
                if not self.request.user.is_superuser:
                    return project.created_by == self.request.user
                return True
            except SlideshowProject.DoesNotExist:
                return False
        
        # Creating new project - allowed for all staff
        return True
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled."""
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add context data."""
        context = super().get_context_data(**kwargs)
        
        # Get project if editing
        project_id = self.kwargs.get('project_id')
        if project_id:
            # Get project with proper access check
            if self.request.user.is_superuser:
                project = get_object_or_404(SlideshowProject, id=project_id)
            else:
                project = get_object_or_404(
                    SlideshowProject,
                    id=project_id,
                    created_by=self.request.user
                )
            context['project'] = project
            context['media_files'] = project.media_files.all().order_by('order', 'uploaded_at')
            context['audio_files'] = project.audio_files.all()
        else:
            context['project'] = None
            context['media_files'] = []
            context['audio_files'] = []
        
        # Get library files
        context['library_audio'] = SlideshowAudio.objects.filter(is_library=True).order_by('name')
        context['library_media'] = SlideshowMedia.objects.filter(is_library=True).order_by('-uploaded_at')
        context['library_media_images'] = SlideshowMedia.objects.filter(is_library=True, media_type='image').order_by('-uploaded_at')
        context['library_media_videos'] = SlideshowMedia.objects.filter(is_library=True, media_type='video').order_by('-uploaded_at')
        
        # Transition choices
        context['transition_choices'] = SlideshowProject.TRANSITION_CHOICES
        
        context['tools_enabled'] = True
        return context


class AudioNormalizeView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """Audio normalization (R128) tool UI."""

    template_name = 'tools/audio_normalize.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            presets_json = load_audio_presets()
            context['audio_presets'] = presets_json.get('presets', [])
            context['audio_defaults'] = presets_json.get('defaults', {})
        except PresetError as e:
            # Log error but don't crash - show empty presets
            import logging
            logger = logging.getLogger('django')
            logger.error(f"Failed to load audio presets: {e}")
            context['audio_presets'] = []
            context['audio_defaults'] = {}
        job_id = self.request.GET.get('job')
        context['initial_job_id'] = int(job_id) if job_id and str(job_id).isdigit() else None
        # Optional integration with media_files module (search by VideoFile.number).
        context['media_files_enabled'] = bool(
            getattr(settings, 'MEDIA_FILES_ENABLED', False)
            and 'media_files' in getattr(settings, 'INSTALLED_APPS', [])
        )
        context['tools_enabled'] = True
        return context


class VideoRenderSelectView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """Video render tool: select a video by number/id."""

    template_name = "tools/video_render.html"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        if not _media_files_available():
            raise Http404(_("Media files module is not available"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tools_enabled"] = True
        context["media_files_enabled"] = True
        context["video"] = None
        context["license"] = None
        context["encodings"] = []
        context["styles"] = []
        context["title_styles"] = []
        context["subtitle_styles"] = []
        context["broadcast_styles"] = []
        context["authority_styles"] = []
        return context


class VideoRenderView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """Video render tool: render overlays for a specific VideoFile."""

    template_name = "tools/video_render.html"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        if not _media_files_available():
            raise Http404(_("Media files module is not available"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from django.db.models import Q
        from tools.rendering.presets import (
            list_encode_presets,
            list_style_presets,
            load_style_preset,
            load_style_preset_from_db,
        )
        from tools.models import VideoPreset
        from media_files.models import VideoFile

        context = super().get_context_data(**kwargs)

        video_id = self.kwargs.get("video_id")
        video = get_object_or_404(VideoFile, id=video_id)

        license_obj = video.get_license()
        if not license_obj:
            raise Http404(_("License not found for this video"))
        
        # Build default overlay texts (matching format used in render_text_template)
        profile = license_obj.profile
        media_authority = getattr(profile, "media_authority", None)
        authority_name = getattr(media_authority, "name", "") or ""
        authority_full_name = getattr(media_authority, "full_name", "") or ""
        from django.conf import settings as django_settings
        organization_name = getattr(django_settings, 'OK_NAME', 'Offener Kanal Merseburg-Querfurt e.V.')
        final_full_name = authority_full_name or authority_name or organization_name
        
        default_broadcast_text = f"{_('Sendeverantwortung')}: {profile}" if profile else ""
        default_authority_text = f"{final_full_name}, {license_obj.created_at.year}" if final_full_name and license_obj.created_at else ""

        # DB presets (templates/public/user-owned)
        db_presets = (
            VideoPreset.objects.filter(
                Q(is_template=True) | Q(is_public=True) | Q(created_by=self.request.user)
            )
            .distinct()
            .order_by("display_name")
        )

        # JSON presets
        json_presets_list = list_style_presets()

        available_presets = list(db_presets)
        for json_preset_data in json_presets_list:
            if db_presets.filter(name=json_preset_data["id"]).exists():
                continue

            class MockPreset:
                def __init__(self, data):
                    self.name = data["id"]
                    self.display_name = data["name"]
                    self.description = data.get("description", "")
                    self.id = None
                    self.is_template = True
                    self.is_public = True
                    self.created_by = None

            available_presets.append(MockPreset(json_preset_data))

        def determine_preview_type(preset, style_preset):
            name_lower = preset.name.lower()
            all_overlays = style_preset.intro_overlays + style_preset.outro_overlays
            templates = [o.template.lower() for o in all_overlays if o.type == "text" and o.template]
            templates_str = " ".join(templates)

            if "film_title" in name_lower:
                return "film_title"
            if "modern" in name_lower:
                return "modern_title"
            if "overlay" in name_lower:
                if "_right" in name_lower:
                    return "overlay_right"
                if "_left" in name_lower:
                    return "overlay_left"
                return "overlay"
            if "lower_third" in name_lower or ("lower" in name_lower and "third" in name_lower):
                if "_right" in name_lower:
                    return "lower_third_right"
                if "_left" in name_lower:
                    return "lower_third_left"
                return "lower_third"
            if "caption" in name_lower:
                return "caption"
            if "broadcast" in name_lower or "{labels.broadcast_responsibility" in templates_str:
                return "broadcast"
            if ("media" in name_lower and "authority" in name_lower) or "{profile.media_authority" in templates_str:
                return "media_authority"
            if "subtitle" in name_lower or "{license.subtitle" in templates_str:
                return "subtitle"
            if "{license.title" in templates_str or "title" in name_lower:
                return "title"
            return "default"

        def filter_presets_by_element(presets, element_type):
            filtered = []
            for preset in presets:
                try:
                    if hasattr(preset, "id") and preset.id is not None:
                        style_preset = load_style_preset_from_db(preset)
                        is_db_preset = True
                        preset_id = preset.id
                        description = preset.description or ""
                    else:
                        style_preset = load_style_preset(preset.name)
                        is_db_preset = False
                        preset_id = None
                        description = preset.description or ""

                    has_element = False
                    all_overlays = style_preset.intro_overlays + style_preset.outro_overlays
                    for overlay in all_overlays:
                        if overlay.type == "text" and overlay.template:
                            template = overlay.template.lower()
                            if element_type == "title":
                                if "{license.title" in template or "{license.title_line_wrapped" in template:
                                    has_element = True
                                    break
                            elif element_type == "subtitle":
                                if "{license.subtitle" in template:
                                    has_element = True
                                    break
                            elif element_type == "broadcast_resp":
                                if "{labels.broadcast_responsibility" in template or "{profile.display}" in template:
                                    has_element = True
                                    break
                            elif element_type == "media_authority":
                                if "{profile.media_authority_full_name" in template or "{license.created_year}" in template:
                                    has_element = True
                                    break

                    if has_element:
                        preview_type = determine_preview_type(preset, style_preset)
                        filtered.append(
                            {
                                "id": preset.name,
                                "name": preset.display_name,
                                "description": description,
                                "preset_id": preset_id,
                                "is_db_preset": is_db_preset,
                                "preview_type": preview_type,
                            }
                        )
                except Exception:
                    continue
            return filtered

        all_styles = []
        for preset in available_presets:
            try:
                if hasattr(preset, "id") and preset.id is not None:
                    style_preset = load_style_preset_from_db(preset)
                    is_db_preset = True
                    preset_id = preset.id
                    description = preset.description or ""
                else:
                    style_preset = load_style_preset(preset.name)
                    is_db_preset = False
                    preset_id = None
                    description = preset.description or ""

                preview_type = determine_preview_type(preset, style_preset)
            except Exception:
                preview_type = "default"
                is_db_preset = hasattr(preset, "id") and preset.id is not None
                preset_id = preset.id if is_db_preset else None
                description = preset.description if hasattr(preset, "description") else ""

            all_styles.append(
                {
                    "id": preset.name,
                    "name": preset.display_name,
                    "description": description,
                    "preset_id": preset_id,
                    "is_db_preset": is_db_preset,
                    "preview_type": preview_type,
                }
            )

        title_styles = filter_presets_by_element(available_presets, "title") or all_styles
        subtitle_styles = filter_presets_by_element(available_presets, "subtitle") or all_styles
        broadcast_styles = filter_presets_by_element(available_presets, "broadcast_resp") or all_styles
        authority_styles = filter_presets_by_element(available_presets, "media_authority") or all_styles

        encodings = list_encode_presets()

        # Video preview stream URL (admin endpoint supports Range requests)
        stream_url = reverse("admin:media_files_videofile_stream", args=[video.id])
        mime_type, _enc = mimetypes.guess_type(video.filename or "")
        mime_type = mime_type or "video/mp4"

        context.update(
            {
                "tools_enabled": True,
                "media_files_enabled": True,
                "video": video,
                "license": license_obj,
                "styles": all_styles,
                "title_styles": title_styles,
                "subtitle_styles": subtitle_styles,
                "broadcast_styles": broadcast_styles,
                "authority_styles": authority_styles,
                "encodings": encodings,
                "video_stream_url": stream_url,
                "video_mime_type": mime_type,
                "video_admin_url": reverse("admin:media_files_videofile_change", args=[video.id]),
                "initial_output_filename": (self.request.GET.get("output_filename") or "").strip(),
                "default_broadcast_text": default_broadcast_text,
                "default_authority_text": default_authority_text,
            }
        )
        return context


class VideoRenderJobsView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    """List video render operations created via the Tools video render UI."""

    template_name = "tools/video_render_job_list.html"
    context_object_name = "operations"
    paginate_by = 30

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        if not _media_files_available():
            raise Http404(_("Media files module is not available"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from media_files.models import FileOperation  # type: ignore

        qs = FileOperation.objects.filter(
            operation_type="RENDER",
            details__source="tools_video_render",
        ).select_related("video_file", "performed_by")

        # Regular staff: show only own operations
        if not self.request.user.is_superuser:
            qs = qs.filter(performed_by=self.request.user)

        status_filter = (self.request.GET.get("status") or "").strip().upper()
        if status_filter in ("IN_PROGRESS", "SUCCESS", "FAILED"):
            qs = qs.filter(status=status_filter)

        return qs.order_by("-performed_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tools_enabled"] = True
        context["current_status"] = (self.request.GET.get("status") or "").strip().upper()
        op = self.request.GET.get("op")
        context["highlight_operation_id"] = int(op) if op and str(op).isdigit() else None
        context["any_in_progress"] = any(
            getattr(o, "status", None) == "IN_PROGRESS" for o in context.get("operations", [])
        )
        return context


class AudioNormalizeJobListView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    """List audio normalization jobs (queue/history)."""

    model = AudioNormalizeJob
    template_name = 'tools/audio_normalize_job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = AudioNormalizeJob.objects.all()
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)

        status_filter = self.request.GET.get('status')
        if status_filter in ['pending', 'analyzing', 'processing', 'completed', 'failed']:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.request.GET.get('status', '')
        context['tools_enabled'] = True
        return context


class AudioNormalizeJobDetailView(UserPassesTestMixin, LoginRequiredMixin, DetailView):
    """View details of an audio normalization job."""

    model = AudioNormalizeJob
    template_name = 'tools/audio_normalize_job_detail.html'
    context_object_name = 'job'
    pk_url_kwarg = 'job_id'

    def test_func(self):
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            return False
        job_id = self.kwargs.get('job_id')
        if not job_id:
            return False
        try:
            job = AudioNormalizeJob.objects.get(id=job_id)
        except AudioNormalizeJob.DoesNotExist:
            return False
        if self.request.user.is_superuser:
            return True
        return job.created_by == self.request.user

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tools_enabled'] = True
        return context


def _media_root_abs() -> Path:
    media_root = Path(getattr(settings, "MEDIA_ROOT", "media/"))
    if media_root.is_absolute():
        return media_root.resolve()
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return (base_dir / media_root).resolve()


def tools_media_stream(request, relpath: str):
    """
    Stream a file from MEDIA_ROOT or mounted storage with HTTP Range support.

    This is required for HTML5 video seeking, because Django's debug static view
    (used for /media/*) does not support byte-range requests.
    """
    check_tools_enabled()

    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404("Not found")

    relpath = (relpath or "").lstrip("/\\")
    if not relpath or ".." in Path(relpath).parts:
        raise Http404("Not found")

    # First try mounted storage path
    config = ToolsConfig.get_config()
    storage_path = config.get_effective_storage_path()
    
    abs_path = None
    if storage_path:
        # Check if file exists in mounted storage
        storage_base = Path(storage_path)
        mounted_path = (storage_base / relpath).resolve()
        try:
            # Ensure path is within storage_base
            mounted_path.relative_to(storage_base.resolve())
            if mounted_path.exists() and mounted_path.is_file():
                abs_path = mounted_path
        except (ValueError, OSError):
            pass
    
    # Fallback to MEDIA_ROOT if not found in mounted storage
    if abs_path is None:
        media_root = _media_root_abs()
        abs_path = (media_root / relpath).resolve()
        try:
            abs_path.relative_to(media_root)
        except Exception:
            raise Http404("Not found")

    if not abs_path.exists() or not abs_path.is_file():
        raise Http404("Not found")

    size = abs_path.stat().st_size
    content_type, _enc = mimetypes.guess_type(str(abs_path))
    content_type = content_type or "application/octet-stream"

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
        # Suffix range: bytes=-N
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


def slideshow_output_stream(request, project_id: int):
    """Stream slideshow output video with Range support."""
    check_tools_enabled()

    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404("Not found")

    project = get_object_or_404(SlideshowProject, id=project_id)
    if not project.output_file:
        raise Http404("Not found")

    try:
        abs_path = resolve_tools_output_path(project.output_file)
    except Exception:
        raise Http404("Not found")

    if not abs_path.exists() or not abs_path.is_file():
        raise Http404("Not found")

    size = abs_path.stat().st_size
    content_type, _enc = mimetypes.guess_type(str(abs_path))
    content_type = content_type or "video/mp4"

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
