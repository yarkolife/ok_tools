"""Admin configuration for Tools module."""

import json
import logging
from ok_tools.admin_base import ModelAdmin
from ok_tools.admin_base import TabularInline
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    AudioNormalizeJob,
    InstagramPartner,
    ReelPost,
    PresetOverlay,
    POSITION_PRESET_CHOICES,
    SlideshowProject,
    SlideshowMedia,
    SlideshowAudio,
    ToolsConfig,
    VideoEncodePreset,
    VideoPreset,
)


# Hide models from admin - use custom interface instead
# Only register ToolsConfig for configuration

@admin.register(SlideshowProject)
class SlideshowProjectAdmin(ModelAdmin):
    """Admin interface for SlideshowProject - hidden from regular users."""
    
    def has_module_permission(self, request):
        """Hide from admin index for non-superusers."""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """Only superusers can view."""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """Only superusers can add."""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Only superusers can change."""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete."""
        return request.user.is_superuser


@admin.register(SlideshowMedia)
class SlideshowMediaAdmin(ModelAdmin):
    """Admin interface for SlideshowMedia - hidden from regular users."""
    
    list_display = ['id', 'name', 'media_type', 'is_library', 'project', 'order', 'uploaded_at']
    list_filter = ['is_library', 'media_type', 'uploaded_at']
    search_fields = ['name', 'project__name']
    readonly_fields = ['media_type', 'uploaded_at']
    list_editable = ['is_library', 'order']
    
    def has_module_permission(self, request):
        """Hide from admin index for non-superusers."""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """Only superusers can view."""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """Only superusers can add."""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Only superusers can change."""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete."""
        return request.user.is_superuser


@admin.register(SlideshowAudio)
class SlideshowAudioAdmin(ModelAdmin):
    """Admin interface for SlideshowAudio - hidden from regular users."""
    
    list_display = ['id', 'name', 'is_library', 'project', 'duration', 'created_at']
    list_filter = ['is_library', 'created_at']
    search_fields = ['name', 'project__name']
    readonly_fields = ['duration', 'created_at']
    list_editable = ['is_library']
    
    def has_module_permission(self, request):
        """Hide from admin index for non-superusers."""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """Only superusers can view."""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """Only superusers can add."""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Only superusers can change."""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete."""
        return request.user.is_superuser


@admin.register(ToolsConfig)
class ToolsConfigAdmin(ModelAdmin):
    """Admin interface for ToolsConfig."""

    fieldsets = (
        (_('Storage'), {
            'fields': (
                'storage_path_storage',
                'storage_path',
                'output_path_storage',
                'output_path',
                'max_upload_size',
            ),
            'description': _(
                'Storage Location (optional): when set, overrides the path below. '
                'Storage Path and Output Path are required when no Storage Location is selected.'
            ),
        }),
        (_('Allowed formats'), {
            'fields': ('allowed_image_formats', 'allowed_video_formats', 'allowed_audio_formats'),
        }),
        (_('FFmpeg'), {
            'fields': ('ffmpeg_path', 'ffprobe_path'),
        }),
        (_('Audio normalize'), {
            'fields': (
                'audio_normalize_input_storage',
                'audio_normalize_input_path',
                'audio_normalize_output_storage',
                'audio_normalize_output_path',
                'audio_normalize_default_preset',
                'audio_normalize_default_bitrate',
                'arnndn_model_path',
            ),
            'description': _(
                'Storage Location (optional): when set, overrides the path below; output can be outside MEDIA_ROOT. '
                'Path fields are used when no storage is selected. Output path can be empty (output next to input). '
                'ARNNDN Model Path: default path to RNN model (.rnnn) for AI-based denoising. System automatically detects and uses recommended models (std.rnnn, bd.rnnn, lq.rnnn) from tools/rnn_models/ directory. Leave empty to use FFT-based denoising.'
            ),
        }),
        (_('Reel Studio'), {
            'fields': (
                'reel_studio_enabled',
                'reel_render_url',
                'reel_render_api_key',
                'reel_render_timeout',
                'reel_output_name_pattern',
                'reel_default_mediathek_zeile1',
                'reel_default_mediathek_zeile2',
                'reel_output_storage',
                'reel_output_subdir',
                'reel_reminder_enabled',
                'reel_reminder_recipient_email',
                'reel_reminder_time',
            ),
            'description': _(
                'External reel renderer. The tool card, page and license admin action '
                'are only shown when "Reel Studio enabled" is on AND URL + API key are set.'
            ),
        }),
        (_('Instagram'), {
            'fields': (
                'instagram_enabled',
                'instagram_api_host',
                'instagram_api_version',
                'instagram_account_id',
                'instagram_access_token',
                'instagram_token_refreshed_at',
                'instagram_post_time',
                'instagram_caption_template',
                'instagram_share_to_feed',
                'instagram_connection',
            ),
            'description': _(
                'Every rendered reel gets an Instagram post draft. Approved posts are '
                'published at their time. Instagram downloads the video from '
                'SITE_BASE_URL, so it must be a public https address.'
            ),
        }),
    )
    readonly_fields = ('instagram_token_refreshed_at', 'instagram_connection')

    def get_form(self, request, obj=None, **kwargs):
        """Never send the stored token back to the browser."""
        from django import forms

        form = super().get_form(request, obj, **kwargs)
        field = form.base_fields.get('instagram_access_token')
        if field is not None:
            field.widget = forms.PasswordInput(render_value=False, attrs={'autocomplete': 'off'})
            field.required = False
            if obj and obj.instagram_access_token:
                field.help_text = _('A token is stored. Leave empty to keep it; enter a new one to replace it.')
        return form

    def save_model(self, request, obj, form, change):
        from django.utils import timezone

        if not form.cleaned_data.get('instagram_access_token'):
            # An empty password field means "keep the stored token".
            obj.instagram_access_token = ToolsConfig.objects.filter(pk=obj.pk).values_list(
                'instagram_access_token', flat=True).first() or ''
        elif 'instagram_access_token' in form.changed_data:
            obj.instagram_token_refreshed_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.display(description=_('Connection'))
    def instagram_connection(self, obj):
        if not obj or not obj.is_instagram_configured():
            return _('Switch posting on and enter account ID and token first.')
        return format_html(
            '<a class="button" href="{}">{}</a>',
            reverse('admin:tools_toolsconfig_instagram_test'),
            _('Test connection'),
        )

    def get_urls(self):
        return [
            path('instagram-test/', self.admin_site.admin_view(self.instagram_test_view),
                 name='tools_toolsconfig_instagram_test'),
        ] + super().get_urls()

    def instagram_test_view(self, request):
        from .services import instagram

        if not request.user.is_superuser:
            messages.error(request, _('Only superusers may test the Instagram connection.'))
            return redirect('admin:index')
        config = ToolsConfig.get_config()
        try:
            info = instagram.account_info(config)
        except instagram.InstagramError as exc:
            messages.error(request, _('Instagram connection failed: %(error)s') % {'error': exc})
        else:
            text = _('Connected to Instagram account @%(username)s.') % {
                'username': info.get('username') or '?'}
            if info.get('quota_total'):
                text += ' ' + _('Posts in the last 24 hours: %(used)s of %(total)s.') % {
                    'used': info.get('quota_usage') or 0, 'total': info['quota_total']}
            messages.success(request, text)
        return redirect('admin:tools_toolsconfig_change', config.pk)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        storage_fields = (
            'storage_path_storage',
            'output_path_storage',
            'audio_normalize_input_storage',
            'audio_normalize_output_storage',
            'reel_output_storage',
        )
        if db_field.name in storage_fields:
            try:
                from media_files.models import StorageLocation
                kwargs.setdefault('queryset', StorageLocation.objects.filter(is_active=True).order_by('storage_type', 'name'))
            except Exception:
                pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        """Only one config instance allowed."""
        try:
            return not ToolsConfig.objects.exists()
        except Exception:
            # Table doesn't exist yet (migrations not applied)
            return True

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of config."""
        return False

    def has_module_permission(self, request):
        """Show config only to superusers."""
        return request.user.is_superuser


@admin.register(AudioNormalizeJob)
class AudioNormalizeJobAdmin(ModelAdmin):
    """Admin interface for AudioNormalizeJob - hidden from regular users."""

    list_display = [
        'id',
        'created_by',
        'status',
        'preset_id',
        'target',
        'progress',
        'created_at',
        'completed_at',
    ]
    list_filter = ['status', 'preset_id', 'target', 'created_at']
    search_fields = ['id', 'created_by__email']
    readonly_fields = ['created_at', 'started_at', 'completed_at', 'progress']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


logger = logging.getLogger("django")


class PresetOverlayInline(TabularInline):
    """Inline admin for preset overlays."""

    model = PresetOverlay
    extra = 0
    fields = [
        "segment",
        "order",
        "overlay_type",
        "text_template",
        "image_path",
        "position_preset",
        "animation",
        "start_time",
        "end_time",
    ]
    ordering = ["segment", "order"]


@admin.register(VideoPreset)
class VideoPresetAdmin(ModelAdmin):
    """Admin interface for video presets."""

    change_form_template = "admin/tools/videopreset/change_form.html"
    change_list_template = "admin/tools/videopreset/change_list.html"

    list_display = [
        "display_name",
        "name",
        "is_template",
        "is_public",
        "created_by",
        "overlay_count",
        "updated_at",
        "edit_in_ui",
    ]
    list_filter = ["is_template", "is_public"]
    search_fields = ["name", "display_name", "description"]
    readonly_fields = ["created_at", "updated_at", "overlay_count"]
    inlines = [PresetOverlayInline]

    fieldsets = (
        (None, {"fields": ("name", "display_name", "description")}),
        (
            _("Settings"),
            {
                "fields": (
                    "segment_duration",
                    "intro_clip_path",
                    "outro_clip_path",
                    "is_template",
                    "is_public",
                    "based_on",
                )
            },
        ),
        (_("Ownership"), {"fields": ("created_by",)}),
        (_("Information"), {"fields": ("overlay_count", "created_at", "updated_at")}),
    )

    def get_urls(self):
        """Add custom URLs for preset editor and import."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:object_id>/edit-preset/",
                self.admin_site.admin_view(self.preset_editor_view),
                name="tools_videopreset_edit_preset",
            ),
            path(
                "<int:object_id>/preset-load/",
                self.admin_site.admin_view(self.preset_load_view),
                name="tools_videopreset_preset_load",
            ),
            path(
                "<int:object_id>/preset-save/",
                self.admin_site.admin_view(self.preset_save_view),
                name="tools_videopreset_preset_save",
            ),
            path(
                "import-all/",
                self.admin_site.admin_view(self.import_all_presets_view),
                name="tools_videopreset_import_all",
            ),
            path(
                "import-single/<str:preset_name>/",
                self.admin_site.admin_view(self.import_single_preset_view),
                name="tools_videopreset_import_single",
            ),
        ]
        return custom_urls + urls

    def preset_editor_view(self, request, object_id: int):
        """Visual preset editor view in admin."""
        from licenses.models import License

        preset = get_object_or_404(VideoPreset, id=object_id)

        # Check permissions
        if not request.user.is_superuser and preset.created_by != request.user and not preset.is_public:
            messages.error(request, _("You do not have permission to edit this preset."))
            return redirect("admin:tools_videopreset_changelist")

        sample_license = License.objects.filter(title__isnull=False).first()

        context = {
            **self.admin_site.each_context(request),
            "title": _("Edit Preset"),
            "preset": preset,
            "sample_license": sample_license,
            "position_presets": POSITION_PRESET_CHOICES,
            "animation_choices": PresetOverlay._meta.get_field("animation").choices,
            "font_choices": [
                ("fonts/Roboto-Regular.ttf", "Roboto Regular"),
                ("fonts/Roboto-Bold.ttf", "Roboto Bold"),
            ],
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request, preset),
            "has_change_permission": self.has_change_permission(request, preset),
        }
        return render(request, "admin/tools/preset_editor.html", context)

    def preset_load_view(self, request, object_id: int):
        """Load preset data via AJAX."""
        from django.http import JsonResponse

        preset = get_object_or_404(VideoPreset, id=object_id)

        overlays = []
        for overlay in preset.overlays.all().order_by("segment", "order"):
            overlays.append(
                {
                    "id": overlay.id,
                    "type": overlay.overlay_type,
                    "segment": overlay.segment,
                    "order": overlay.order,
                    "text_template": overlay.text_template,
                    "image_path": overlay.image_path,
                    "image_width": overlay.image_width,
                    "image_height": overlay.image_height,
                    "position_preset": overlay.position_preset,
                    "x_position": overlay.x_position,
                    "y_position": overlay.y_position,
                    "start_time": overlay.start_time,
                    "end_time": overlay.end_time,
                    "animation": overlay.animation,
                    "fade_in_duration": overlay.fade_in_duration,
                    "fade_out_duration": overlay.fade_out_duration,
                    "font_file": overlay.font_file,
                    "font_size": overlay.font_size,
                    "font_color": overlay.font_color,
                    "has_box": overlay.has_box,
                    "box_color": overlay.box_color,
                    "box_border_width": overlay.box_border_width,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "preset": {
                    "id": preset.id,
                    "name": preset.name,
                    "display_name": preset.display_name,
                    "description": preset.description,
                    "segment_duration": preset.segment_duration,
                    "intro_clip_path": preset.intro_clip_path,
                    "outro_clip_path": preset.outro_clip_path,
                    "is_public": preset.is_public,
                    "overlays": overlays,
                },
            }
        )

    def preset_save_view(self, request, object_id: int):
        """Save preset via AJAX."""
        from django.http import JsonResponse

        if request.method != "POST":
            return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

        try:
            data = json.loads(request.body)
            preset = get_object_or_404(VideoPreset, id=object_id)

            # Check permissions
            if not request.user.is_superuser and preset.created_by != request.user:
                return JsonResponse({"success": False, "error": "Permission denied"}, status=403)

            # Update preset fields
            preset.name = data.get("name", preset.name)
            preset.display_name = data.get("display_name", preset.display_name)
            preset.description = data.get("description", preset.description)
            preset.segment_duration = float(data.get("segment_duration", preset.segment_duration))
            preset.intro_clip_path = data.get("intro_clip_path", preset.intro_clip_path)
            preset.outro_clip_path = data.get("outro_clip_path", preset.outro_clip_path)
            preset.is_public = data.get("is_public", preset.is_public)
            preset.save()

            # Delete existing overlays
            preset.overlays.all().delete()

            # Create new overlays
            for overlay_data in data.get("overlays", []):
                overlay = PresetOverlay(
                    preset=preset,
                    overlay_type=overlay_data.get("type", "text"),
                    segment=overlay_data.get("segment", "intro"),
                    order=overlay_data.get("order", 0),
                    text_template=overlay_data.get("text_template", ""),
                    image_path=overlay_data.get("image_path", ""),
                    image_width=overlay_data.get("image_width"),
                    image_height=overlay_data.get("image_height"),
                    position_preset=overlay_data.get("position_preset", "custom"),
                    x_position=overlay_data.get("x_position", "(w-text_w)/2"),
                    y_position=overlay_data.get("y_position", "(h-text_h)/2"),
                    start_time=float(overlay_data.get("start_time", 0.0)),
                    end_time=float(overlay_data.get("end_time", 5.0)),
                    animation=overlay_data.get("animation", "fade"),
                    fade_in_duration=float(overlay_data.get("fade_in_duration", 0.4)),
                    fade_out_duration=float(overlay_data.get("fade_out_duration", 0.4)),
                    font_file=overlay_data.get("font_file", "fonts/Roboto-Regular.ttf"),
                    font_size=int(overlay_data.get("font_size", 48)),
                    font_color=overlay_data.get("font_color", "white"),
                    has_box=overlay_data.get("has_box", False),
                    box_color=overlay_data.get("box_color", "black@0.5"),
                    box_border_width=int(overlay_data.get("box_border_width", 12)),
                )
                overlay.save()

            return JsonResponse({"success": True, "preset_id": preset.id, "message": _("Preset saved successfully")})
        except Exception as e:
            logger.exception("Error saving preset")
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    def overlay_count(self, obj):
        """Display count of overlays."""
        if obj.pk:
            return obj.overlays.count()
        return 0

    overlay_count.short_description = _("Overlays")

    def edit_in_ui(self, obj):
        """Link to visual editor."""
        if obj.pk:
            url = reverse("admin:tools_videopreset_edit_preset", args=[obj.id])
            return format_html('<a href="{}" class="button">🎨 {}</a>', url, _("Visual Editor"))
        return "-"

    edit_in_ui.short_description = _("Editor")

    def save_model(self, request, obj, form, change):
        """Set created_by on new presets."""
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        """Add available JSON presets to changelist context."""
        extra_context = extra_context or {}
        from tools.rendering.presets import list_style_presets

        extra_context["available_json_presets"] = list_style_presets()
        return super().changelist_view(request, extra_context=extra_context)

    def import_all_presets_view(self, request):
        """Import all JSON presets from video_presets/style directory."""
        from django.core.management import call_command

        try:
            call_command("import_json_presets")
            messages.success(request, _("All presets imported successfully"))
        except Exception as e:
            messages.error(request, _("Error importing presets: %s") % str(e))

        return redirect("admin:tools_videopreset_changelist")

    def import_single_preset_view(self, request, preset_name: str):
        """Import a single JSON preset by name."""
        from django.core.management import call_command

        try:
            call_command("import_json_presets", preset_name=preset_name)
            messages.success(request, _('Preset "%s" imported successfully') % preset_name)
        except Exception as e:
            messages.error(request, _('Error importing preset "%s": %s') % (preset_name, str(e)))

        return redirect("admin:tools_videopreset_changelist")


@admin.register(VideoEncodePreset)
class VideoEncodePresetAdmin(ModelAdmin):
    """Admin interface for video encode presets."""

    list_display = ["display_name", "name", "width", "height", "fps", "video_bitrate_k", "audio_bitrate_k", "updated_at"]
    list_filter = ["vcodec", "acodec", "x264_preset", "x264_profile"]
    search_fields = ["name", "display_name", "description"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("name", "display_name", "description")}),
        (
            _("Video Settings"),
            {"fields": ("width", "height", "fps", "vcodec", "video_bitrate_k", "pix_fmt", "x264_preset", "x264_profile")},
        ),
        (_("Audio Settings"), {"fields": ("acodec", "audio_bitrate_k", "audio_sample_rate", "audio_channels")}),
        (_("Information"), {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        """Auto-generate display_name if not provided and save to JSON file."""
        if not obj.display_name:
            obj.display_name = f"{obj.height}p ({obj.video_bitrate_k}k)"
        super().save_model(request, obj, form, change)

        # Export to JSON file after saving
        try:
            encode_dir = Path(settings.BASE_DIR) / "media_files" / "video_presets" / "encode"
            encode_dir.mkdir(parents=True, exist_ok=True)
            json_file = encode_dir / f"{obj.name}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(obj.to_json(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save encode preset to JSON: {e}")


@admin.register(PresetOverlay)
class PresetOverlayAdmin(ModelAdmin):
    """Admin interface for preset overlays."""

    list_display = ["preset", "segment", "order", "overlay_type", "preview_text", "animation", "timing"]
    list_filter = ["preset", "segment", "overlay_type", "animation"]
    search_fields = ["preset__name", "text_template", "image_path"]

    fieldsets = (
        (None, {"fields": ("preset", "segment", "order", "overlay_type")}),
        (_("Content"), {"fields": ("text_template", "image_path", "image_width", "image_height")}),
        (_("Position"), {"fields": ("position_preset", "x_position", "y_position")}),
        (_("Timing & Animation"), {"fields": ("start_time", "end_time", "animation", "fade_in_duration", "fade_out_duration")}),
        (
            _("Text Styling"),
            {"fields": ("font_file", "font_size", "font_color", "has_box", "box_color", "box_border_width")},
        ),
    )

    def preview_text(self, obj):
        """Show preview of text or image path."""
        if obj.overlay_type == "text":
            text = obj.text_template[:50]
            if len(obj.text_template) > 50:
                text += "..."
            return text
        return obj.image_path

    preview_text.short_description = _("Content")

    def timing(self, obj):
        """Show timing info."""
        return f"{obj.start_time}s - {obj.end_time}s"

    timing.short_description = _("Timing")


@admin.register(InstagramPartner)
class InstagramPartnerAdmin(ModelAdmin):
    """Partners whose reels are posted as an Instagram collab."""

    list_display = ['name', 'keywords', 'match_in', 'usernames', 'is_active']
    list_filter = ['is_active', 'match_in']
    search_fields = ['name', 'keywords', 'usernames']


@admin.register(ReelPost)
class ReelPostAdmin(ModelAdmin):
    """Instagram posts of rendered reels: check, approve, follow up."""

    list_display = ['filename', 'license_title', 'scheduled_at', 'status_badge',
                    'collaborators', 'instagram_link']
    list_filter = ['status', 'scheduled_at']
    search_fields = ['filename', 'caption', 'license__title', 'license__number']
    date_hierarchy = 'scheduled_at'
    raw_id_fields = ['license']
    actions = ['approve_action', 'publish_now_action', 'back_to_draft_action']
    readonly_fields = ['status', 'reel_preview', 'caption_info', 'approved_by', 'approved_at',
                       'instagram_link', 'published_at', 'media_id', 'container_id',
                       'error_message', 'created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('status', 'error_message', 'filename', 'license', 'reel_preview'),
        }),
        (_('Post'), {
            'fields': ('caption', 'caption_info', 'collaborators', 'share_to_feed',
                       'thumb_offset_ms', 'scheduled_at'),
        }),
        (_('Instagram'), {
            'fields': ('approved_by', 'approved_at', 'instagram_link', 'published_at',
                       'media_id', 'container_id', 'created_at', 'updated_at'),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in (ReelPost.STATUS_PUBLISHING, ReelPost.STATUS_PUBLISHED):
            # What is on Instagram (or on the way) can no longer be edited here.
            fields += ['filename', 'license', 'caption', 'collaborators', 'share_to_feed',
                       'thumb_offset_ms', 'scheduled_at']
        elif obj:
            fields.append('filename')
        return fields

    def save_model(self, request, obj, form, change):
        # An edited approved post needs a new approval.
        if change and obj.status == ReelPost.STATUS_APPROVED and form.changed_data:
            obj.status = ReelPost.STATUS_DRAFT
            obj.approved_by = None
            obj.approved_at = None
            messages.warning(request, _('The post was changed and is a draft again; approve it once more.'))
        super().save_model(request, obj, form, change)

    @admin.display(description=_('License'), ordering='license__number')
    def license_title(self, obj):
        if not obj.license:
            return '-'
        return f'{obj.license.number} {obj.license.title}'

    @admin.display(description=_('Status'), ordering='status')
    def status_badge(self, obj):
        colours = {
            ReelPost.STATUS_DRAFT: 'var(--ok-ink-3, #666)',
            ReelPost.STATUS_APPROVED: 'var(--ok-brand, #417690)',
            ReelPost.STATUS_PUBLISHING: 'var(--ok-warning-ink, #8a5a00)',
            ReelPost.STATUS_PUBLISHED: 'var(--ok-success-ink, #0a6b2d)',
            ReelPost.STATUS_FAILED: 'var(--ok-danger, #c62828)',
        }
        return format_html('<strong style="color:{}">{}</strong>',
                           colours.get(obj.status, 'inherit'), obj.get_status_display())

    @admin.display(description=_('Instagram link'))
    def instagram_link(self, obj):
        if not obj.permalink:
            return '-'
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>',
                           obj.permalink, _('Open'))

    @admin.display(description=_('Reel'))
    def reel_preview(self, obj):
        if not obj or not obj.filename:
            return '-'
        url = reverse('tools:reel_output_stream', args=[obj.filename])
        return format_html(
            '<video src="{}" controls preload="metadata" style="max-height:420px;max-width:100%;'
            'border-radius:8px;background:#000"></video>', url)

    @admin.display(description=_('Length'))
    def caption_info(self, obj):
        import re

        caption = (obj.caption if obj else '') or ''
        return _('%(chars)s of %(max_chars)s characters, %(tags)s of %(max_tags)s hashtags') % {
            'chars': len(caption), 'max_chars': ReelPost.CAPTION_MAX_LENGTH,
            'tags': len(re.findall(r'#\w', caption)), 'max_tags': ReelPost.MAX_HASHTAGS,
        }

    def _may_publish(self, request):
        if request.user.has_perm('tools.publish_reelpost'):
            return True
        self.message_user(request, _('You may not approve or publish Instagram posts.'),
                          level=messages.ERROR)
        return False

    def _approve(self, request, queryset, *, now):
        from django.core.exceptions import ValidationError

        from .reel_posts import approve
        if not self._may_publish(request):
            return
        done = 0
        for post in queryset.filter(status__in=[ReelPost.STATUS_DRAFT, ReelPost.STATUS_FAILED,
                                                ReelPost.STATUS_APPROVED]):
            try:
                approve(post, request.user, now=now)
            except ValidationError as exc:
                self.message_user(request, '%s: %s' % (post, '; '.join(exc.messages)),
                                  level=messages.ERROR)
                continue
            done += 1
        if not done:
            return
        if now:
            from .tasks import publish_due_reel_posts
            publish_due_reel_posts.delay()
            self.message_user(request, _('%(count)s post(s) are being published now.') % {'count': done})
        else:
            self.message_user(request, _('%(count)s post(s) approved; they are published at their time.') % {
                'count': done})

    @admin.action(description=_('Approve (publish at its time)'))
    def approve_action(self, request, queryset):
        self._approve(request, queryset, now=False)

    @admin.action(description=_('Publish now'))
    def publish_now_action(self, request, queryset):
        self._approve(request, queryset, now=True)

    @admin.action(description=_('Back to draft'))
    def back_to_draft_action(self, request, queryset):
        from .reel_posts import back_to_draft
        count = 0
        for post in queryset.filter(status__in=[ReelPost.STATUS_APPROVED, ReelPost.STATUS_FAILED]):
            back_to_draft(post)
            count += 1
        self.message_user(request, _('%(count)s post(s) are drafts again.') % {'count': count})
