"""Views for Tools module."""

from .models import AudioNormalizeJob
from .models import SlideshowAudio
from .models import SlideshowMedia
from .models import SlideshowProject
from .models import ToolsConfig
from .services.audio_normalizer import PresetError
from .services.audio_normalizer import load_audio_presets
from .utils import resolve_tools_output_path
from django.apps import apps
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured
from django.core.signing import BadSignature
from django.core.signing import SignatureExpired
from django.core.signing import TimestampSigner
from django.http import FileResponse
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import TemplateView
from pathlib import Path
import mimetypes
import re


REEL_PUBLIC_LINK_MAX_AGE_SECONDS = 60 * 60 * 24


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


def _reel_studio_configured() -> bool:
    """True if the Reel Studio is enabled and configured in ToolsConfig."""
    try:
        return ToolsConfig.get_config().is_reel_configured()
    except Exception:
        return False


def _reel_plan_info(license_obj):
    """Return the latest TagesPlan match as (date|None, item|None)."""
    if not (
        getattr(settings, "PLANUNG_ENABLED", False)
        and apps.is_installed("planung")
    ):
        return None, None

    try:
        from planung.models import TagesPlan
    except Exception:
        return None, None

    matchers = (
        ("license_id", getattr(license_obj, "id", None)),
        ("number", getattr(license_obj, "number", None)),
    )
    for key, value in matchers:
        if value is None:
            continue
        for plan in TagesPlan.objects.order_by("-datum"):
            plan_data = plan.json_plan or {}
            matches = [
                item for item in plan_data.get("items", [])
                if isinstance(item, dict) and item.get(key) == value
            ]
            if matches:
                return plan.datum, matches[-1]
            for item in plan_data.get("items", []):
                try:
                    if key == "number" and int(item.get(key)) == int(value):
                        return plan.datum, item
                except (TypeError, ValueError):
                    continue
    return None, None


def _reel_sendetermin(license_obj):
    """German broadcast day+date and time, e.g. ('Samstag, 27.06.', '18:00')."""
    plan_date, item = _reel_plan_info(license_obj)
    if not plan_date:
        return "", ""
    weekdays = [
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag",
    ]
    uhr = ((item or {}).get("start") or "")[:5]
    return f"{weekdays[plan_date.weekday()]}, {plan_date:%d.%m.}", uhr


def _reel_video_file(license_obj):
    """Pick the best source video for Reel Studio."""
    if not _media_files_available():
        return None
    try:
        from media_files.models import VideoFile
        from media_files.utils import is_reel_filename
        from tools.services.okmq_reel import share_prefix_for
    except Exception:
        return None

    def is_full_source(vf):
        return (
            vf is not None
            and bool(getattr(vf, "is_available", False))
            and not bool(getattr(vf, "is_preview", False))
            and not is_reel_filename(getattr(vf, "filename", "") or "")
            and not is_reel_filename(getattr(vf, "file_path", "") or "")
        )

    candidates = list(
        VideoFile.objects
        .filter(number=license_obj.number, is_available=True)
        .exclude(is_preview=True)
        .select_related("storage_location")
    )
    candidates = [vf for vf in candidates if is_full_source(vf)]

    try:
        primary = license_obj.get_video_file()
    except Exception:
        primary = None
    if is_full_source(primary) and primary not in candidates:
        candidates.append(primary)
    if not candidates:
        return None

    rank = {"playout": 0, "archive": 1}

    def sort_key(vf):
        prefix = share_prefix_for(getattr(vf, "storage_location", None))
        return (rank.get(prefix, 2), -(vf.id or 0))

    candidates.sort(key=sort_key)
    return candidates[0]


def _reel_output_name(config, number: int, plan_date) -> str:
    """Build the default reel output filename from the configured pattern."""
    pattern = config.reel_output_name_pattern or "{number}_Programmvorschau_Reel_{date:%y%m%d}"
    try:
        return pattern.format(number=number, date=plan_date)
    except Exception:
        return f"{number}_Programmvorschau_Reel_{plan_date:%y%m%d}"


def _reel_license_prefill(license_obj, config) -> dict:
    """Build the same Reel Studio prefill fields as the license admin action."""
    plan_date, _item = _reel_plan_info(license_obj)
    name_date = plan_date or timezone.now()
    se_tag, se_uhr = _reel_sendetermin(license_obj)

    duration = ""
    if license_obj.duration:
        duration = str(int(license_obj.duration.total_seconds()))

    autor = ""
    if license_obj.profile_id:
        autor = str(license_obj.profile).strip()

    sendung = ""
    if license_obj.category_id:
        sendung = str(getattr(license_obj.category, "name", "") or "").strip()

    prefill = {
        "title": license_obj.title or "",
        "output_name": _reel_output_name(config, license_obj.number, name_date),
        "autor": autor,
        "sendung": sendung,
        "description": license_obj.description or "",
        "dauer": duration,
        "se_tag": se_tag,
        "se_uhr": se_uhr,
    }
    video_file = _reel_video_file(license_obj)
    if video_file is not None and getattr(video_file, "id", None):
        from tools.services.okmq_reel import share_relative_path
        prefill["video"] = share_relative_path(
            getattr(video_file, "file_path", ""),
            getattr(video_file, "storage_location", None),
        )
        prefill["video_id"] = video_file.id
    return prefill


def _prefill_reel_from_license(prefill: dict, license_obj, config) -> None:
    """Apply license-derived defaults without overriding explicit query params."""
    if not license_obj:
        return
    for key, value in _reel_license_prefill(license_obj, config).items():
        if value and key in prefill and not prefill.get(key):
            prefill[key] = value


def _prefill_reel_from_video(prefill: dict, video_file, config) -> None:
    """Fill Reel Studio defaults from a selected VideoFile's license."""
    _prefill_reel_from_license(prefill, video_file.get_license(), config)


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
        context["reel_studio_enabled"] = _reel_studio_configured()
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


class ReelStudioView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """Reel Studio: operator form for the external OKMQ reel renderer."""

    template_name = "tools/reel_studio.html"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        check_tools_enabled()
        if not _reel_studio_configured():
            raise Http404(_("Reel Studio is not enabled"))
        self._warm_reel_model()
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _warm_reel_model():
        """Best-effort, non-blocking model warm-up while the operator edits.

        Runs in a daemon thread so the page is not delayed; errors are ignored.
        """
        from .services import okmq_reel
        import threading
        try:
            threading.Thread(target=okmq_reel.warmup, daemon=True).start()
        except Exception:
            pass

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = ToolsConfig.get_config()
        get = self.request.GET
        prefill = {
            "video": get.get("video", ""),
            "title": get.get("title", ""),
            "output_name": get.get("output_name", ""),
            "autor": get.get("autor", ""),
            "location": get.get("location", ""),
            "description": get.get("description", ""),
            "dauer": get.get("dauer", ""),
            "se_tag": get.get("se_tag", ""),
            "se_uhr": get.get("se_uhr", ""),
            "sendung": get.get("sendung", ""),
        }

        # Optional inline video player to pick the start second manually.
        context["stream_url"] = None
        context["browser_compatible"] = False
        context["video_duration"] = None
        video_id = get.get("video_id")
        if video_id and _media_files_available():
            try:
                from media_files.models import VideoFile
                video_file = VideoFile.objects.filter(id=video_id).first()
            except Exception:
                video_file = None
            if video_file:
                context["stream_url"] = reverse(
                    "admin:media_files_videofile_stream", args=[video_file.id])
                context["browser_compatible"] = bool(
                    getattr(video_file, "is_browser_compatible", False))
                if video_file.duration:
                    context["video_duration"] = int(
                        video_file.duration.total_seconds())
                # Fill in path/duration from the file when not given explicitly.
                if not prefill["video"]:
                    from .services.okmq_reel import share_relative_path
                    prefill["video"] = share_relative_path(
                        getattr(video_file, "file_path", ""),
                        getattr(video_file, "storage_location", None))
                if not prefill["dauer"] and context["video_duration"]:
                    prefill["dauer"] = str(context["video_duration"])
                _prefill_reel_from_video(prefill, video_file, config)

        context["prefill"] = prefill
        context["reel_mediathek_zeile1"] = config.reel_default_mediathek_zeile1
        context["reel_mediathek_zeile2"] = config.reel_default_mediathek_zeile2
        return context


@require_GET
@staff_member_required
def reel_license_prefill(request, number: int):
    """Return Reel Studio prefill data for a license number."""
    check_tools_enabled()
    if not _reel_studio_configured():
        raise Http404(_("Reel Studio is not enabled"))

    try:
        from licenses.models import License
    except Exception:
        raise Http404(_("License module is not available"))

    license_obj = get_object_or_404(
        License.objects.select_related("profile", "category"),
        number=number,
    )
    prefill = _reel_license_prefill(license_obj, ToolsConfig.get_config())
    params = {k: v for k, v in prefill.items() if v}
    url = f"{reverse('tools:reel_studio')}?{urlencode(params)}"
    return JsonResponse({"prefill": prefill, "url": url})


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
        from media_files.models import VideoFile
        from tools.models import VideoPreset
        from tools.rendering.presets import list_encode_presets
        from tools.rendering.presets import list_style_presets
        from tools.rendering.presets import load_style_preset
        from tools.rendering.presets import load_style_preset_from_db

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


def _serve_file_with_range(request, abs_path: Path, as_attachment: bool = False,
                           download_name: str | None = None):
    """Serve a file with HTTP Range support (for HTML5 video seeking)."""
    size = abs_path.stat().st_size
    content_type, _enc = mimetypes.guess_type(str(abs_path))
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
    if not range_header:
        resp = FileResponse(
            open(abs_path, "rb"), content_type=content_type,
            as_attachment=as_attachment, filename=download_name or abs_path.name)
        resp["Accept-Ranges"] = "bytes"
        resp["Content-Length"] = str(size)
        return resp

    m = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
    if not m:
        resp = HttpResponse(status=416)
        resp["Content-Range"] = f"bytes */{size}"
        return resp
    start_s, end_s = m.groups()
    if start_s == "":
        suffix_len = int(end_s or 0)
        if suffix_len <= 0:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            return resp
        start, end = max(0, size - suffix_len), size - 1
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
        with open(path, "rb") as f:
            f.seek(offset)
            remaining = count
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    resp = StreamingHttpResponse(
        iterator(abs_path, start, length), status=206, content_type=content_type)
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Range"] = f"bytes {start}-{end}/{size}"
    resp["Content-Length"] = str(length)
    return resp


def reel_output_stream(request, filename: str):
    """Stream (or download) a finished reel from the output storage."""
    check_tools_enabled()
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404("Not found")
    if not _reel_studio_configured():
        raise Http404("Not found")

    config = ToolsConfig.get_config()
    abs_path = config.resolve_reel_output_file(filename)
    if abs_path is None:
        raise Http404(_("Rendered reel not found"))

    as_attachment = request.GET.get("download") in ("1", "true", "yes")
    return _serve_file_with_range(request, abs_path, as_attachment=as_attachment)


def reel_public_output_stream(request, filename: str):
    """Stream a finished reel through a signed 24-hour public download URL."""
    check_tools_enabled()
    if not _reel_studio_configured():
        raise Http404("Not found")

    token = request.GET.get("token", "")
    signer = TimestampSigner(salt="tools.reel_public_output")
    try:
        signed_filename = signer.unsign(
            token,
            max_age=REEL_PUBLIC_LINK_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        raise Http404("Not found")
    if signed_filename != filename:
        raise Http404("Not found")

    config = ToolsConfig.get_config()
    abs_path = config.resolve_reel_output_file(filename)
    if abs_path is None:
        raise Http404(_("Rendered reel not found"))

    return _serve_file_with_range(request, abs_path, as_attachment=True)


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
