"""Views for media files app."""

import json
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _

from .models import VideoPreset, PresetOverlay, VideoFile, FileOperation
from licenses.models import License


logger = logging.getLogger('django')


def render_video_admin(request, video_id):
    """Render form for specific video (admin only)."""
    from django.contrib.admin.views.decorators import staff_member_required
    from licenses.models import License
    
    # Check if user is staff
    if not request.user.is_staff:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # Get video
    video = get_object_or_404(VideoFile, id=video_id)
    
    # Get license
    license_obj = video.get_license()
    if not license_obj:
        messages.error(request, _('License not found for this video'))
        return redirect('admin:media_files_videofile_change', video_id)
    
    # Load available presets from database (templates and public) and JSON files
    from django.db.models import Q
    from media_files.rendering.presets import load_style_preset_from_db, load_style_preset, list_style_presets
    
    # Get presets from database
    db_presets = VideoPreset.objects.filter(
        Q(is_template=True) | Q(is_public=True) | Q(created_by=request.user)
    ).distinct().order_by('display_name')
    
    # Get presets from JSON files
    json_presets_list = list_style_presets()
    json_preset_names = {p['id'] for p in json_presets_list}
    
    # Combine: database presets + JSON presets (excluding those already in DB)
    available_presets = list(db_presets)
    for json_preset_data in json_presets_list:
        # Skip if already in database
        if not db_presets.filter(name=json_preset_data['id']).exists():
            # Create a mock preset object for JSON presets
            class MockPreset:
                def __init__(self, data):
                    self.name = data['id']
                    self.display_name = data['name']
                    self.description = data.get('description', '')
                    self.id = None
                    self.is_template = True
                    self.is_public = True
                    self.created_by = None
            available_presets.append(MockPreset(json_preset_data))
    
    def determine_preview_type(preset, style_preset):
        """Determine preview type for a preset based on its content and name."""
        name_lower = preset.name.lower()
        
        # Check overlays to understand what the preset contains
        all_overlays = style_preset.intro_overlays + style_preset.outro_overlays
        templates = [o.template.lower() for o in all_overlays if o.type == "text" and o.template]
        templates_str = " ".join(templates)
        
        # Priority order: specific patterns first, then generic
        
        # Film title (title + subtitle)
        if "film_title" in name_lower:
            return "film_title"
        
        # Modern title (specific design)
        if "modern" in name_lower:
            return "modern_title"
        
        # Overlay styles - distinguish between left and right
        if "overlay" in name_lower:
            if "_right" in name_lower:
                return "overlay_right"
            elif "_left" in name_lower:
                return "overlay_left"
            else:
                return "overlay"
        
        # Lower third styles - distinguish between left and right
        if "lower_third" in name_lower or ("lower" in name_lower and "third" in name_lower):
            if "_right" in name_lower:
                return "lower_third_right"
            elif "_left" in name_lower:
                return "lower_third_left"
            else:
                return "lower_third"
        
        # Caption styles (web caption, etc.)
        if "caption" in name_lower:
            return "caption"
        
        # Broadcast responsibility
        if "broadcast" in name_lower or "{labels.broadcast_responsibility" in templates_str:
            return "broadcast"
        
        # Media authority
        if ("media" in name_lower and "authority" in name_lower) or "{profile.media_authority" in templates_str:
            return "media_authority"
        
        # Subtitle
        if "subtitle" in name_lower or "{license.subtitle" in templates_str:
            return "subtitle"
        
        # Title (generic - check by template variables)
        if "{license.title" in templates_str or "title" in name_lower:
            return "title"
        
        # Default fallback
        return "default"
    
    def filter_presets_by_element(presets, element_type):
        """Filter presets to only include those with overlays for the specified element type."""
        filtered = []
        for preset in presets:
            try:
                # Load preset - from DB or JSON
                if hasattr(preset, 'id') and preset.id is not None:
                    # Database preset
                    style_preset = load_style_preset_from_db(preset)
                    is_db_preset = True
                    preset_id = preset.id
                    description = preset.description or ''
                else:
                    # JSON preset
                    style_preset = load_style_preset(preset.name)
                    is_db_preset = False
                    preset_id = None
                    description = preset.description or ''
                
                has_element = False
                
                # Check intro and outro overlays
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
                    # Determine preview type based on preset content/name
                    preview_type = determine_preview_type(preset, style_preset)
                    filtered.append({
                        'id': preset.name,
                        'name': preset.display_name,
                        'description': description,
                        'preset_id': preset_id,
                        'is_db_preset': is_db_preset,
                        'preview_type': preview_type,
                    })
            except Exception:
                # Skip presets that can't be loaded
                continue
        
        return filtered
    
    # Filter presets for each element type
    title_styles = filter_presets_by_element(available_presets, "title")
    subtitle_styles = filter_presets_by_element(available_presets, "subtitle")
    broadcast_styles = filter_presets_by_element(available_presets, "broadcast_resp")
    authority_styles = filter_presets_by_element(available_presets, "media_authority")
    
    # Fallback to all presets if no filtered presets found
    all_styles = []
    for preset in available_presets:
        try:
            # Load preset - from DB or JSON
            if hasattr(preset, 'id') and preset.id is not None:
                # Database preset
                style_preset = load_style_preset_from_db(preset)
                is_db_preset = True
                preset_id = preset.id
                description = preset.description or ''
            else:
                # JSON preset
                style_preset = load_style_preset(preset.name)
                is_db_preset = False
                preset_id = None
                description = preset.description or ''
            
            preview_type = determine_preview_type(preset, style_preset)
        except Exception:
            preview_type = "default"
            is_db_preset = hasattr(preset, 'id') and preset.id is not None
            preset_id = preset.id if is_db_preset else None
            description = preset.description if hasattr(preset, 'description') else ''
        
        all_styles.append({
            'id': preset.name,
            'name': preset.display_name,
            'description': description,
            'preset_id': preset_id,
            'is_db_preset': is_db_preset,
            'preview_type': preview_type,
        })
    
    # Use filtered styles, or fallback to all if empty
    title_styles = title_styles if title_styles else all_styles
    subtitle_styles = subtitle_styles if subtitle_styles else all_styles
    broadcast_styles = broadcast_styles if broadcast_styles else all_styles
    authority_styles = authority_styles if authority_styles else all_styles
    
    # Keep old 'styles' for backward compatibility (used in template)
    styles = all_styles
    
    # Encoding presets - load dynamically from encode directory
    from media_files.rendering.presets import list_encode_presets
    encodings = list_encode_presets()
    
    context = {
        'video': video,
        'license': license_obj,
        'styles': styles,  # For backward compatibility
        'title_styles': title_styles,
        'subtitle_styles': subtitle_styles,
        'broadcast_styles': broadcast_styles,
        'authority_styles': authority_styles,
        'encodings': encodings,
        'is_admin': True,
    }
    return render(request, 'media_files/render_video_admin.html', context)


@login_required
@require_http_methods(["POST"])
def render_video(request):
    """Start video rendering task asynchronously via Celery."""
    from pathlib import Path
    
    try:
        license_number = request.POST.get('license_number')
        encode_name = request.POST.get('encoding', '1080p25_9000k')
        is_preview = request.POST.get('preview') == 'true'
        use_intro_outro = request.POST.get('use_intro_outro') == 'true'
        
        # Get elements to show and their styles
        show_title = request.POST.get('show_title') == 'true'
        show_subtitle = request.POST.get('show_subtitle') == 'true'
        show_broadcast_resp = request.POST.get('show_broadcast_resp') == 'true'
        show_media_authority = request.POST.get('show_media_authority') == 'true'
        
        style_title = request.POST.get('style_title')
        style_subtitle = request.POST.get('style_subtitle')
        style_broadcast = request.POST.get('style_broadcast')
        style_authority = request.POST.get('style_authority')
        
        if not license_number:
            return JsonResponse({'success': False, 'error': _('Missing required parameters: license_number')}, status=400)
        
        # Check if at least one element is selected
        if not (show_title or show_subtitle or show_broadcast_resp or show_media_authority):
            return JsonResponse({'success': False, 'error': _('Please select at least one element to show')}, status=400)
        
        # Get license and video
        try:
            license_obj = License.objects.get(number=int(license_number))
        except License.DoesNotExist:
            return JsonResponse({'success': False, 'error': _('License not found')}, status=404)
        
        # Get the original source video (not rendered versions)
        # Rendered videos have file_path starting with "rendered/"
        all_videos = VideoFile.objects.filter(
            number=license_obj.number,
            is_available=True
        ).order_by('-created_at')
        
        # Find source video (not in rendered/ directory)
        source_video = None
        for video in all_videos:
            # Skip videos in rendered directory
            if video.file_path.startswith('rendered/'):
                continue
            source_video = video
            break
        
        # If no source video found, try license-linked video
        if not source_video and hasattr(license_obj, 'video_file') and license_obj.video_file:
            linked_video = license_obj.video_file
            if linked_video.file_path and not linked_video.file_path.startswith('rendered/'):
                source_video = linked_video
        
        if not source_video:
            return JsonResponse({
                'success': False,
                'error': _('Source video file not found. Please ensure there is an original (non-rendered) video file available.')
            }, status=404)
        
        # Validation: check if at least one element and style is selected
        if not any([
            (show_title and style_title),
            (show_subtitle and style_subtitle),
            (show_broadcast_resp and style_broadcast),
            (show_media_authority and style_authority),
        ]):
            return JsonResponse({
                'success': False,
                'error': _('No valid presets found for selected elements. Please select styles for each element.')
            }, status=400)
        
        # Create a combined style name for logging
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
        rel_dir = source_rel_path.parent  # Same directory as source
        src_stem = Path(source_video.filename).stem
        
        # Base filename with version suffix (_v1, _v2, etc.)
        # Always use version suffix for rendered files to distinguish from source
        if is_preview:
            base_stem = f"{src_stem}_preview"
        else:
            base_stem = src_stem
        base_suffix = ".mp4"
        
        def is_path_taken(candidate_rel: Path) -> bool:
            """Check if path is taken (exists in DB or filesystem)."""
            cand_str = str(candidate_rel).replace("\\", "/")
            # Check database
            if VideoFile.objects.filter(
                storage_location=source_video.storage_location,
                file_path=cand_str
            ).exists():
                return True
            # Check filesystem
            abs_candidate = storage_root / candidate_rel
            if abs_candidate.exists():
                return True
            return False
        
        # Find first available version starting from _v1
        version = 1
        while version < 1000:
            candidate_name = f"{base_stem}_v{version}{base_suffix}"
            rel_out = rel_dir / candidate_name
            if not is_path_taken(rel_out):
                break
            version += 1
        else:
            return JsonResponse({
                'success': False,
                'error': _('Could not find a free output filename (too many versions exist).')
            }, status=400)
        
        abs_out = storage_root / rel_out
        abs_out.parent.mkdir(parents=True, exist_ok=True)
        
        # Create VideoFile record (mark as not available until rendering is complete)
        new_video = VideoFile.objects.create(
            number=source_video.number,
            filename=abs_out.name,
            file_path=str(rel_out).replace("\\", "/"),
            storage_location=source_video.storage_location,
            is_available=False,  # Will be set to True after rendering completes
        )
        
        # Create operation record
        operation = FileOperation.objects.create(
            video_file=new_video,
            operation_type="RENDER",
            source_location=source_video.storage_location,
            destination_location=source_video.storage_location,
            performed_by=request.user,
            status="IN_PROGRESS",
            details={
                "source_video_id": source_video.id,
                "license_number": license_obj.number,
                "style": combined_style_name,
                "encode": encode_name,
                "preview": is_preview,
                "use_intro_outro": use_intro_outro,
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
                }
            },
        )
        
        # Start async rendering task via Celery
        from media_files.tasks import render_video_task
        render_video_task.delay(operation.id)
        
        return JsonResponse({
            'success': True,
            'video_id': new_video.id,
            'operation_id': operation.id,
            'message': _('Video rendering started. You can track progress in File Operations.')
        })
    
    except Exception as e:
        logger.exception("Error in render_video")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

