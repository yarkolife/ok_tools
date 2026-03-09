from . import forms
from .generate_file import generate_license_file
from .models import License
from .models import NextcloudVideoFile
from .models import SigningSession
from .models import SigningSessionStatus
from .models import YouthProtectionCategory
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import generic
from registration.models import Profile
from registration.views import _no_profile_error
from typing import Any
import base64
import datetime
import django.http as http
import io
import json
import logging
import qrcode
import uuid
import xml.etree.ElementTree as ET


User = get_user_model()
logger = logging.getLogger('django')
SIGNATURE_SVG_MAX_LENGTH = 50000
SIGNATURE_METADATA_MAX_LENGTH = 10000
SIGNATURE_POINTS_MAX_GROUPS = 200
SIGNATURE_POINTS_MAX_TOTAL_POINTS = 50000
SIGN_SESSION_RATE_LIMIT_ATTEMPTS = 20
SIGN_SESSION_RATE_LIMIT_WINDOW_SECONDS = 600


def _get_client_ip(request):
    """Get client IP from request headers."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _extract_signature_payload(data):
    """Extract signature payload from JSON/body dict."""
    signature_svg = data.get('signature_svg')
    signature_points = data.get('signature_points')
    signature_metadata = data.get('signature_metadata')
    signature_method = data.get('signature_method') or 'mouse'
    legacy_signature = data.get('legacy_signature')

    if isinstance(signature_points, str):
        signature_points = signature_points.strip()
        if signature_points:
            signature_points = json.loads(signature_points)
        else:
            signature_points = None

    if isinstance(signature_metadata, str):
        signature_metadata = signature_metadata.strip()
        if signature_metadata:
            signature_metadata = json.loads(signature_metadata)
        else:
            signature_metadata = None

    signature_svg = _sanitize_signature_svg(signature_svg)
    signature_points = _sanitize_signature_points(signature_points)
    signature_metadata = _sanitize_signature_metadata(signature_metadata)

    if signature_svg is not None and not isinstance(signature_svg, str):
        raise ValueError('signature_svg must be a string')
    if signature_points is not None and not isinstance(signature_points, list):
        raise ValueError('signature_points must be a list')
    if signature_metadata is not None and not isinstance(signature_metadata, dict):
        raise ValueError('signature_metadata must be an object')

    has_payload = bool(signature_svg) or bool(signature_points) or bool(legacy_signature)
    if not has_payload:
        raise ValueError('No signature payload provided')

    return {
        'signature_svg': signature_svg,
        'signature_points': signature_points,
        'signature_metadata': signature_metadata,
        'signature_method': signature_method,
        'legacy_signature': legacy_signature,
    }


def _is_sign_session_rate_limited(request, token):
    """Check and increment simple submit rate limit for signing sessions."""
    ip = _get_client_ip(request) or 'unknown'
    cache_key = f'sign-session-submit:{token}:{ip}'
    attempts = cache.get(cache_key, 0)
    if attempts >= SIGN_SESSION_RATE_LIMIT_ATTEMPTS:
        return True
    cache.set(cache_key, attempts + 1, timeout=SIGN_SESSION_RATE_LIMIT_WINDOW_SECONDS)
    return False


def _sanitize_signature_svg(signature_svg):
    """Validate and sanitize SVG signature payload."""
    if signature_svg is None:
        return None
    if not isinstance(signature_svg, str):
        raise ValueError('signature_svg must be a string')

    signature_svg = signature_svg.strip()
    if not signature_svg:
        return None
    if len(signature_svg) > SIGNATURE_SVG_MAX_LENGTH:
        raise ValueError('signature_svg is too large')

    lowered = signature_svg.lower()
    blocked_patterns = [
        '<script',
        'javascript:',
        'onload=',
        'onerror=',
        '<foreignobject',
        '<iframe',
        '<object',
        '<embed',
    ]
    if any(pattern in lowered for pattern in blocked_patterns):
        raise ValueError('signature_svg contains unsafe content')

    try:
        root = ET.fromstring(signature_svg)
    except ET.ParseError as e:
        raise ValueError('signature_svg is not valid XML') from e

    if not str(root.tag).lower().endswith('svg'):
        raise ValueError('signature_svg root element must be <svg>')

    return signature_svg


def _sanitize_signature_points(signature_points):
    """Validate biometric points payload shape and limits."""
    if signature_points is None:
        return None
    if not isinstance(signature_points, list):
        raise ValueError('signature_points must be a list')
    if len(signature_points) > SIGNATURE_POINTS_MAX_GROUPS:
        raise ValueError('Too many signature point groups')

    total_points = 0
    sanitized_groups: list[dict[str, Any]] = []

    for group in signature_points:
        if not isinstance(group, dict):
            raise ValueError('signature_points group must be an object')
        points = group.get('points', [])
        if not isinstance(points, list):
            raise ValueError('signature_points group points must be a list')

        clean_points = []
        for point in points:
            if not isinstance(point, dict):
                raise ValueError('signature point must be an object')
            try:
                x = float(point.get('x', 0))
                y = float(point.get('y', 0))
                t = float(point.get('time', 0))
                p = float(point.get('pressure', 0.5))
            except (TypeError, ValueError) as e:
                raise ValueError('signature point contains invalid numeric values') from e

            clean_points.append({
                'x': x,
                'y': y,
                'time': t,
                'pressure': p,
            })

        total_points += len(clean_points)
        if total_points > SIGNATURE_POINTS_MAX_TOTAL_POINTS:
            raise ValueError('Too many signature points')

        clean_group: dict[str, Any] = {}
        clean_group['points'] = clean_points
        if 'color' in group:
            clean_group['color'] = str(group['color'])[:32]
        if 'minWidth' in group:
            clean_group['minWidth'] = group['minWidth']
        if 'maxWidth' in group:
            clean_group['maxWidth'] = group['maxWidth']
        sanitized_groups.append(clean_group)

    return sanitized_groups


def _sanitize_signature_metadata(signature_metadata):
    """Validate metadata payload and apply size limits."""
    if signature_metadata is None:
        return None
    if not isinstance(signature_metadata, dict):
        raise ValueError('signature_metadata must be an object')

    serialized = json.dumps(signature_metadata)
    if len(serialized) > SIGNATURE_METADATA_MAX_LENGTH:
        raise ValueError('signature_metadata is too large')

    return signature_metadata


def _render_svg_to_png_data_url(signature_svg):
    """Render SVG string to PNG data URL for legacy compatibility."""
    try:
        from cairosvg import svg2png
    except Exception:
        return None

    png_bytes = svg2png(bytestring=signature_svg.encode('utf-8'))
    encoded = base64.b64encode(png_bytes).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def _apply_signature_to_license(license_obj, payload):
    """Apply new signature payload to license with legacy dual-write."""
    _populate_signature_fields(license_obj, payload)

    license_obj.save(update_fields=[
        'signature',
        'signature_svg',
        'signature_points',
        'signature_metadata',
        'signature_method',
        'signature_signed_at',
    ])


def _populate_signature_fields(license_obj, payload):
    """Populate signature fields on model instance without saving."""
    license_obj.signature_svg = payload.get('signature_svg') or None
    license_obj.signature_points = payload.get('signature_points') or None
    license_obj.signature_metadata = payload.get('signature_metadata') or None
    license_obj.signature_method = payload.get('signature_method') or 'mouse'
    license_obj.signature_signed_at = timezone.now()

    legacy_signature = payload.get('legacy_signature')
    if legacy_signature:
        license_obj.signature = legacy_signature
    elif license_obj.signature_svg:
        rendered = _render_svg_to_png_data_url(license_obj.signature_svg)
        if rendered:
            license_obj.signature = rendered


def _extract_signature_payload_from_form(form):
    """Build and validate signature payload from cleaned form data."""
    payload = {
        'signature_svg': form.cleaned_data.get('signature_svg'),
        'signature_points': form.cleaned_data.get('signature_points'),
        'signature_metadata': form.cleaned_data.get('signature_metadata'),
        'signature_method': form.cleaned_data.get('signature_method'),
        'legacy_signature': form.cleaned_data.get('signature'),
    }

    has_any = bool(payload['signature_svg']) or bool(payload['signature_points']) or bool(payload['legacy_signature'])
    if not has_any:
        return None

    return _extract_signature_payload(payload)


def _extract_signature_payload_from_session(token, user):
    """Load a signed QR session payload for create-form pre-submit flow."""
    if not token:
        return None

    session = SigningSession.objects.filter(token=token).first()
    if not session:
        raise ValueError(_('Signing session not found.'))

    owner = session.owner
    if owner is None and session.license_id:
        owner = session.license.profile.okuser
    if owner != user:
        raise ValueError(_('Not allowed to use this signing session.'))

    if session.status != SigningSessionStatus.SIGNED:
        raise ValueError(_('Signing session is not signed yet.'))

    payload = {
        'signature_svg': session.signature_svg,
        'signature_points': session.signature_points,
        'signature_metadata': session.signature_metadata,
        'signature_method': session.signature_method or 'qr_phone',
        'legacy_signature': None,
    }
    if not payload['signature_svg'] and not payload['signature_points']:
        raise ValueError(_('Signing session has no signature payload.'))
    return _extract_signature_payload(payload)


def _license_does_not_exist(request) -> http.HttpResponseRedirect:
    message = _('License not found.')
    logger.error(message)
    messages.error(request, message)
    return http.HttpResponseRedirect(
        request.META.get(
            'HTTP_REFERER', reverse_lazy('licenses:licenses')
        )
    )


@method_decorator(login_required, name='dispatch')
class ListLicensesView(generic.list.ListView):
    """List all licenses of the user."""

    template_name = 'licenses/list.html'
    model = License
    context_object_name = 'licenses'

    def get_context_data(self, **kwargs):
        """Add NEXTCLOUD_ENABLED to context."""
        context = super().get_context_data(**kwargs)
        context['NEXTCLOUD_ENABLED'] = settings.NEXTCLOUD_ENABLED
        return context
    
    def get_queryset(self):
        """List only the licenses of the logged in user."""
        try:
            # Get profile through OKUser -> Profile relationship
            profile = Profile.objects.get(okuser=self.request.user)
        except Profile.DoesNotExist:
            return self.model.objects.none()

        # Get all licenses for the user with prefetch for Nextcloud videos
        queryset = self.model.objects.filter(profile=profile).order_by('-created_at')
        
        # Prefetch Nextcloud videos to check if video exists
        if settings.NEXTCLOUD_ENABLED:
            from .models import NextcloudVideoFile
            queryset = queryset.prefetch_related(
                Prefetch(
                    'nextcloud_videos',
                    queryset=NextcloudVideoFile.objects.filter(is_deleted=False),
                    to_attr='active_videos'
                )
            )
        
        return queryset


@method_decorator(login_required, name='dispatch')
class CreateLicenseView(generic.CreateView):
    """Show view to create licenses."""

    model = License
    form_class = form = forms.CreateLicenseForm
    # TODO better success page
    template_name = 'licenses/create.html'

    success_url = reverse_lazy('licenses:licenses')

    def form_valid(self, form):
        """Handle form submission and return JSON response for AJAX."""
        sign_session_token = (self.request.POST.get('signing_session_token') or '').strip()

        try:
            signature_payload = _extract_signature_payload_from_form(form)
        except ValueError as e:
            form.add_error('signature', str(e))
            return self.form_invalid(form)

        if not signature_payload and sign_session_token:
            try:
                signature_payload = _extract_signature_payload_from_session(sign_session_token, self.request.user)
            except ValueError as e:
                form.add_error('signature', str(e))
                return self.form_invalid(form)

        if signature_payload:
            _populate_signature_fields(form.instance, signature_payload)

        response = super().form_valid(form)
        
        # Check if this is an AJAX request
        is_ajax = self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax:
            # Return JSON response for AJAX requests
            has_signature = self.object.has_any_signature()
            
            return JsonResponse({
                'success': True,
                'license_id': self.object.id,
                'license_number': self.object.number,
                'title': self.object.title,
                'has_signature': has_signature,
                'pdf_url': reverse('licenses:print', kwargs={'pk': self.object.pk}),
            })
        
        return response

    def get_success_url(self) -> str:
        """Show a message to confirm the creation."""
        messages.success(
            self.request, _('License %(license)s successfully created.') % {
                'license': str(self.object)})

        # Auto-open the generated PDF
        return reverse('licenses:print', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        """User of created License is current user."""
        form = super().get_form(form_class)

        # Add Bootstrap classes to form fields
        for field_name, field in form.fields.items():
            if hasattr(field.widget, 'attrs'):
                if hasattr(field.widget, 'input_type') and field.widget.input_type == 'checkbox':
                    field.widget.attrs.update({'class': 'form-check-input'})
                elif hasattr(field.widget, 'choices') or 'Select' in str(type(field.widget)):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})

        try:
            profile = Profile.objects.get(okuser=self.request.user)
            form.instance.profile = profile
        except Profile.DoesNotExist:
            pass
        return form

    def get_context_data(self, **kwargs):
        """Add NEXTCLOUD_ENABLED to context."""
        context = super().get_context_data(**kwargs)
        context['NEXTCLOUD_ENABLED'] = settings.NEXTCLOUD_ENABLED
        return context

    def get(self, request, *args, **kwargs) -> http.HttpResponse:
        """Get handler to create a LR."""
        try:
            Profile.objects.get(okuser=self.request.user)
        except Profile.DoesNotExist:
            return _no_profile_error(request)
        return super().get(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class CopyLicenseView(generic.CreateView):
    """Copy an existing license."""
    
    model = License
    form_class = forms.CreateLicenseForm
    template_name = 'licenses/create.html'
    success_url = reverse_lazy('licenses:licenses')
    
    def get_initial(self):
        """Pre-fill form with data from source license."""
        initial = super().get_initial()
        
        # Get source license to copy from
        source_pk = self.kwargs.get('pk')
        try:
            source_license = License.objects.get(pk=source_pk)
            
            # Verify user owns this license
            profile = Profile.objects.get(okuser=self.request.user)
            if source_license.profile != profile:
                return initial
                
            # Copy all fields except id, number, created_at, confirmed
            initial['title'] = source_license.title
            initial['subtitle'] = source_license.subtitle
            initial['description'] = source_license.description
            initial['further_persons'] = source_license.further_persons
            initial['duration'] = source_license.duration
            initial['suggested_date'] = source_license.suggested_date
            initial['repetitions_allowed'] = source_license.repetitions_allowed
            initial['media_authority_exchange_allowed'] = source_license.media_authority_exchange_allowed
            initial['media_authority_exchange_allowed_other_states'] = source_license.media_authority_exchange_allowed_other_states
            initial['youth_protection_necessary'] = source_license.youth_protection_necessary
            initial['youth_protection_category'] = source_license.youth_protection_category
            initial['store_in_ok_media_library'] = source_license.store_in_ok_media_library
            
            initial['tags'] = source_license.tags
                
            initial['category'] = source_license.category
            initial['is_screen_board'] = source_license.is_screen_board
            initial['infoblock'] = source_license.infoblock
            
        except (License.DoesNotExist, Profile.DoesNotExist):
            pass
            
        return initial
    
    def get_form(self, form_class=None):
        """User of created License is current user."""
        form = super().get_form(form_class)
        
        # Add Bootstrap classes to form fields
        for field_name, field in form.fields.items():
            if hasattr(field.widget, 'attrs'):
                if hasattr(field.widget, 'input_type') and field.widget.input_type == 'checkbox':
                    field.widget.attrs.update({'class': 'form-check-input'})
                elif hasattr(field.widget, 'choices') or 'Select' in str(type(field.widget)):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})

        try:
            profile = Profile.objects.get(okuser=self.request.user)
            form.instance.profile = profile
        except Profile.DoesNotExist:
            pass
        return form
    
    def get_success_url(self) -> str:
        """Show message confirming the copy."""
        messages.success(
            self.request, _('License %(license)s successfully copied.') % {
                'license': str(self.object)}
        )
        
        # Auto-open the generated PDF
        return reverse('licenses:print', kwargs={'pk': self.object.pk})


@method_decorator(login_required, name='dispatch')
class UpdateLicensesView(generic.edit.UpdateView):
    """Updates a License."""

    form = form_class = forms.CreateLicenseForm
    model = License
    template_name = 'licenses/update.html'
    success_url = reverse_lazy('licenses:licenses')

    def get_success_url(self) -> str:
        """Show a message to confirm the update."""
        messages.success(
            self.request, _('License %(license)s successfully updated.') % {
                'license': str(self.object)})

        # Auto-open the generated PDF
        return reverse('licenses:print', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        """Add NEXTCLOUD_ENABLED and existing video to context."""
        context = super().get_context_data(**kwargs)
        context['NEXTCLOUD_ENABLED'] = settings.NEXTCLOUD_ENABLED
        
        # Add existing Nextcloud video if exists
        if settings.NEXTCLOUD_ENABLED:
            context['nextcloud_video'] = NextcloudVideoFile.objects.filter(
                license=self.object,
                is_deleted=False
            ).first()
        
        return context

    def post(self, request, *args, **kwargs) -> http.HttpResponse:
        """Show error message for editing confirmed Licenses."""
        license = self.get_object()
        if license.confirmed:
            message = _('The License %(license)s is already confirmed and'
                        ' therefor no longer editable.') % {'license': license}
            logger.error(message)
            messages.error(request, message)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Screen Boards always have a fixed duration."""
        if form.instance.is_screen_board:
            from licenses.config import get_screen_board_duration
            form.instance.duration = datetime.timedelta(
                seconds=get_screen_board_duration())

        try:
            signature_payload = _extract_signature_payload_from_form(form)
        except ValueError as e:
            form.add_error('signature', str(e))
            return self.form_invalid(form)

        if signature_payload:
            _populate_signature_fields(form.instance, signature_payload)
        
        response = super().form_valid(form)
        
        # Video upload is now handled separately via UploadVideoView
        # No need to handle it here anymore
        
        return response


@method_decorator(login_required, name='dispatch')
class UploadVideoView(generic.View):
    """Separate view for uploading video to Nextcloud."""
    
    def post(self, request, *args, **kwargs):
        """Handle video upload separately from license update."""
        if not settings.NEXTCLOUD_ENABLED:
            return http.JsonResponse({
                'success': False,
                'error': _('Nextcloud integration is disabled.')
            }, status=400)
        
        license_pk = kwargs.get('pk')
        try:
            license = License.objects.get(pk=license_pk, profile__okuser=request.user)
        except License.DoesNotExist:
            return http.JsonResponse({
                'success': False,
                'error': _('License not found.')
            }, status=404)
        
        # Check if license is confirmed
        if license.confirmed:
            return http.JsonResponse({
                'success': False,
                'error': _('Cannot upload video to confirmed license.')
            }, status=400)
        
        # Check if video already exists
        existing_video = NextcloudVideoFile.objects.filter(
            license=license,
            is_deleted=False
        ).first()
        
        if existing_video:
            return http.JsonResponse({
                'success': False,
                'error': _('Video already uploaded. Cannot upload second video.')
            }, status=400)
        
        # Check if video file was provided
        if 'video_file' not in request.FILES:
            return http.JsonResponse({
                'success': False,
                'error': _('No video file provided.')
            }, status=400)
        
        video_file = request.FILES['video_file']
        
        # Validate file size (20GB limit)
        max_size = 20 * 1024 * 1024 * 1024  # 20GB in bytes
        if video_file.size > max_size:
            return http.JsonResponse({
                'success': False,
                'error': _('Video file is too large. Maximum size is 20GB.')
            }, status=400)
        
        # Validate file extension
        allowed_extensions = ['mp4', 'mov', 'avi', 'mkv', 'webm']
        file_extension = video_file.name.split('.')[-1].lower() if '.' in video_file.name else ''
        if file_extension not in allowed_extensions:
            return http.JsonResponse({
                'success': False,
                'error': _('Invalid file format. Supported formats: mp4, mov, avi, mkv, webm.')
            }, status=400)
        
        try:
            from .services.nextcloud_service import NextcloudService
            
            # Store upload session ID for progress tracking
            upload_session_id = f"upload_{license_pk}_{datetime.datetime.now().timestamp()}"
            request.session[f'upload_progress_{upload_session_id}'] = {
                'stage': 'uploading_to_nextcloud',
                'progress': 0,
                'total': video_file.size
            }
            request.session.modified = True
            
            # Progress callback for Nextcloud upload
            def progress_callback(bytes_sent, total_bytes):
                progress_percent = int((bytes_sent / total_bytes) * 100) if total_bytes > 0 else 0
                request.session[f'upload_progress_{upload_session_id}'] = {
                    'stage': 'uploading_to_nextcloud',
                    'progress': progress_percent,
                    'bytes_sent': bytes_sent,
                    'total': total_bytes
                }
                request.session.modified = True
            
            # Upload video to Nextcloud
            nextcloud_service = NextcloudService()
            upload_result = nextcloud_service.upload_video(
                file=video_file,
                license_number=license.number,
                filename=video_file.name,
                progress_callback=progress_callback
            )
            
            # Create NextcloudVideoFile record (user_uploaded=True: rightsholder initiated)
            NextcloudVideoFile.objects.create(
                license=license,
                nextcloud_file_id=upload_result['file_id'],
                nextcloud_url=upload_result['nextcloud_url'],
                filename=upload_result['filename'],
                file_size=video_file.size,
                user_uploaded=True,
            )
            
            logger.info(
                f'Video uploaded to Nextcloud for license {license.number}'
            )
            
            # Set progress to 100% and mark as completed before returning response
            request.session[f'upload_progress_{upload_session_id}'] = {
                'stage': 'completed',
                'progress': 100,
                'bytes_sent': video_file.size,
                'total': video_file.size
            }
            request.session.modified = True
            
            # Don't delete session data immediately - let client poll it first
            # It will be cleaned up on next upload or can be cleaned manually
            
            return http.JsonResponse({
                'success': True,
                'message': _('Video uploaded successfully.'),
                'filename': upload_result['filename'],
                'url': upload_result['nextcloud_url'],
                'session_id': upload_session_id
            })
            
        except Exception as e:
            logger.error(
                f'Error uploading video to Nextcloud for license {license.number}: {e}',
                exc_info=True
            )
            return http.JsonResponse({
                'success': False,
                'error': _('Failed to upload video: %(error)s') % {'error': str(e)}
            }, status=500)


class UploadProgressView(generic.View):
    """View to check upload progress."""
    
    def get(self, request, *args, **kwargs):
        """Get current upload progress."""
        upload_session_id = request.GET.get('session_id')
        if not upload_session_id:
            return http.JsonResponse({
                'error': _('Session ID required.')
            }, status=400)
        
        progress_key = f'upload_progress_{upload_session_id}'
        progress_data = request.session.get(progress_key, {})
        
        if not progress_data:
            return http.JsonResponse({
                'error': _('Upload session not found.')
            }, status=404)
        
        return http.JsonResponse({
            'progress': progress_data.get('progress', 0),
            'stage': progress_data.get('stage', 'unknown'),
            'bytes_sent': progress_data.get('bytes_sent', 0),
            'total': progress_data.get('total', 0)
        })


@method_decorator(login_required, name='dispatch')
class GetUploadTokenView(generic.View):
    """
    Get a temporary upload token for direct Nextcloud upload.
    
    This creates a temporary upload-only share in Nextcloud,
    allowing the client to upload directly without going through Django.
    """
    
    def get(self, request, *args, **kwargs):
        """Return upload token and URL for direct Nextcloud upload."""
        if not settings.NEXTCLOUD_ENABLED:
            return http.JsonResponse({
                'success': False,
                'error': _('Nextcloud integration is disabled.')
            }, status=400)
        
        license_pk = kwargs.get('pk')
        try:
            license = License.objects.get(pk=license_pk, profile__okuser=request.user)
        except License.DoesNotExist:
            return http.JsonResponse({
                'success': False,
                'error': _('License not found.')
            }, status=404)
        
        # Check if license is confirmed
        if license.confirmed:
            return http.JsonResponse({
                'success': False,
                'error': _('Cannot upload video to confirmed license.')
            }, status=400)
        
        # Check if video already exists
        existing_video = NextcloudVideoFile.objects.filter(
            license=license,
            is_deleted=False
        ).first()
        
        if existing_video:
            return http.JsonResponse({
                'success': False,
                'error': _('Video already uploaded. Cannot upload second video.')
            }, status=400)
        
        try:
            from .services.nextcloud_service import NextcloudService
            
            nextcloud_service = NextcloudService()
            
            # Create upload share (expires in 24 hours)
            share_data = nextcloud_service.create_upload_share(
                license_number=license.number,
                expire_hours=24
            )
            
            # Store share info in session for later cleanup
            upload_session_id = f"direct_upload_{license_pk}_{datetime.datetime.now().timestamp()}"
            request.session[f'upload_share_{upload_session_id}'] = {
                'share_id': share_data['share_id'],
                'license_pk': license_pk,
                'created_at': datetime.datetime.now().isoformat(),
            }
            request.session.modified = True
            
            logger.info(
                f'Created upload token for license {license.number}, '
                f'session={upload_session_id}'
            )
            
            return http.JsonResponse({
                'success': True,
                'token': share_data['token'],
                'upload_url': share_data['upload_url'],
                'session_id': upload_session_id,
                'license_number': license.number,
            })
            
        except Exception as e:
            logger.error(
                f'Error creating upload token for license {license.number}: {e}',
                exc_info=True
            )
            return http.JsonResponse({
                'success': False,
                'error': _('Failed to create upload token: %(error)s') % {'error': str(e)}
            }, status=500)


@method_decorator(login_required, name='dispatch')
class ConfirmUploadView(generic.View):
    """
    Confirm that a direct upload to Nextcloud has completed.
    
    This verifies the file exists, creates the database record,
    and cleans up the temporary share.
    """
    
    def post(self, request, *args, **kwargs):
        """Confirm upload completion and create database record."""
        if not settings.NEXTCLOUD_ENABLED:
            return http.JsonResponse({
                'success': False,
                'error': _('Nextcloud integration is disabled.')
            }, status=400)
        
        license_pk = kwargs.get('pk')
        try:
            license = License.objects.get(pk=license_pk, profile__okuser=request.user)
        except License.DoesNotExist:
            return http.JsonResponse({
                'success': False,
                'error': _('License not found.')
            }, status=404)
        
        # Get filename and session_id from request
        import json
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            filename = data.get('filename')
            session_id = data.get('session_id')
            file_size = int(data.get('file_size', 0))
        except (json.JSONDecodeError, ValueError) as e:
            return http.JsonResponse({
                'success': False,
                'error': _('Invalid request data.')
            }, status=400)
        
        if not filename:
            return http.JsonResponse({
                'success': False,
                'error': _('Filename is required.')
            }, status=400)
        
        # Check if video already exists
        existing_video = NextcloudVideoFile.objects.filter(
            license=license,
            is_deleted=False
        ).first()
        
        if existing_video:
            return http.JsonResponse({
                'success': False,
                'error': _('Video already uploaded. Cannot upload second video.')
            }, status=400)
        
        try:
            from .services.nextcloud_service import NextcloudService
            
            nextcloud_service = NextcloudService()
            
            # Verify file exists in Nextcloud
            file_info = nextcloud_service.verify_uploaded_file(filename)
            
            if not file_info:
                return http.JsonResponse({
                    'success': False,
                    'error': _('File not found in Nextcloud. Upload may have failed.')
                }, status=400)
            
            # Use file size from verification or from client
            actual_size = file_info.get('size', 0) or file_size
            
            # Create NextcloudVideoFile record (user_uploaded=True: rightsholder confirmed upload)
            NextcloudVideoFile.objects.create(
                license=license,
                nextcloud_file_id=file_info['file_path'],
                nextcloud_url=file_info['file_url'],
                filename=filename,
                file_size=actual_size,
                user_uploaded=True,
            )
            
            logger.info(
                f'Video upload confirmed for license {license.number}, '
                f'filename={filename}, size={actual_size}'
            )
            
            # Clean up the share if session_id provided
            if session_id:
                share_key = f'upload_share_{session_id}'
                share_data = request.session.get(share_key, {})
                
                if share_data and share_data.get('share_id'):
                    nextcloud_service.delete_share(share_data['share_id'])
                    del request.session[share_key]
                    request.session.modified = True
            
            return http.JsonResponse({
                'success': True,
                'message': _('Video uploaded successfully.'),
                'filename': filename,
                'file_size': actual_size,
            })
            
        except Exception as e:
            logger.error(
                f'Error confirming upload for license {license.number}: {e}',
                exc_info=True
            )
            return http.JsonResponse({
                'success': False,
                'error': _('Failed to confirm upload: %(error)s') % {'error': str(e)}
            }, status=500)


@method_decorator(login_required, name='dispatch')
class SaveSignatureView(generic.View):
    """Persist SVG/biometric signature payload for an existing license."""

    def post(self, request, *args, **kwargs):
        license_pk = kwargs.get('pk')
        try:
            license_obj = License.objects.get(pk=license_pk, profile__okuser=request.user)
        except License.DoesNotExist:
            return JsonResponse({'success': False, 'error': _('License not found.')}, status=404)

        if license_obj.confirmed:
            return JsonResponse({'success': False, 'error': _('Cannot update a confirmed license.')}, status=400)

        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            payload = _extract_signature_payload(data)
            _apply_signature_to_license(license_obj, payload)
        except (json.JSONDecodeError, ValueError) as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error('Failed to save signature for license %s: %s', license_obj.number, e, exc_info=True)
            return JsonResponse({'success': False, 'error': _('Failed to save signature.')}, status=500)

        return JsonResponse({'success': True, 'has_signature': license_obj.has_any_signature()})


@method_decorator(login_required, name='dispatch')
class CreateSigningSessionView(generic.View):
    """Create QR signing session for cross-device signature capture."""

    def post(self, request, *args, **kwargs):
        license_pk = kwargs.get('pk')
        try:
            license_obj = License.objects.get(pk=license_pk, profile__okuser=request.user)
        except License.DoesNotExist:
            return JsonResponse({'success': False, 'error': _('License not found.')}, status=404)

        if license_obj.confirmed:
            return JsonResponse({'success': False, 'error': _('Cannot sign a confirmed license.')}, status=400)

        expires_at = timezone.now() + datetime.timedelta(minutes=10)
        session = SigningSession.objects.create(
            license=license_obj,
            owner=request.user,
            token=uuid.uuid4().hex,
            status=SigningSessionStatus.PENDING,
            expires_at=expires_at,
        )
        sign_url = request.build_absolute_uri(reverse('licenses:sign_session_page', kwargs={'token': session.token}))
        qr_url = reverse('licenses:sign_session_qr', kwargs={'token': session.token})
        return JsonResponse({
            'success': True,
            'token': session.token,
            'status': session.status,
            'expires_at': expires_at.isoformat(),
            'sign_url': sign_url,
            'qr_url': qr_url,
        })


@method_decorator(login_required, name='dispatch')
class CreatePreLicenseSigningSessionView(generic.View):
    """Create QR signing session before license is submitted on create page."""

    def post(self, request, *args, **kwargs):
        expires_at = timezone.now() + datetime.timedelta(minutes=10)
        session = SigningSession.objects.create(
            owner=request.user,
            token=uuid.uuid4().hex,
            status=SigningSessionStatus.PENDING,
            expires_at=expires_at,
        )
        sign_url = request.build_absolute_uri(reverse('licenses:sign_session_page', kwargs={'token': session.token}))
        qr_url = reverse('licenses:sign_session_qr', kwargs={'token': session.token})
        return JsonResponse({
            'success': True,
            'token': session.token,
            'status': session.status,
            'expires_at': expires_at.isoformat(),
            'sign_url': sign_url,
            'qr_url': qr_url,
        })


@method_decorator(login_required, name='dispatch')
class SigningSessionStatusView(generic.View):
    """Poll status for QR signing session."""

    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        session = SigningSession.objects.select_related('license', 'license__profile', 'license__profile__okuser').filter(token=token).first()
        if not session:
            return JsonResponse({'success': False, 'error': _('Signing session not found.')}, status=404)

        owner = session.owner
        if owner is None and session.license_id:
            owner = session.license.profile.okuser
        if owner != request.user:
            return JsonResponse({'success': False, 'error': _('Not allowed.')}, status=403)

        if session.status == SigningSessionStatus.PENDING and session.is_expired():
            session.status = SigningSessionStatus.EXPIRED
            session.save(update_fields=['status'])

        response_payload = {
            'success': True,
            'status': session.status,
            'expires_at': session.expires_at.isoformat(),
            'signed_at': session.signed_at.isoformat() if session.signed_at else None,
            'signature_svg': session.signature_svg,
            'signature_points': session.signature_points,
            'signature_metadata': session.signature_metadata,
            'signature_method': session.signature_method,
        }

        consume_flag = str(request.GET.get('consume', '')).lower() in {'1', 'true', 'yes'}
        if consume_flag and session.status == SigningSessionStatus.SIGNED:
            session.delete()

        return JsonResponse(response_payload)


@method_decorator(login_required, name='dispatch')
class SigningSessionQRCodeView(generic.View):
    """Render QR PNG for signing session URL."""

    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        session = SigningSession.objects.select_related('license', 'license__profile', 'license__profile__okuser').filter(token=token).first()
        if not session:
            return http.HttpResponseNotFound()
        owner = session.owner
        if owner is None and session.license_id:
            owner = session.license.profile.okuser
        if owner != request.user:
            return http.HttpResponseForbidden()

        sign_url = request.build_absolute_uri(reverse('licenses:sign_session_page', kwargs={'token': token}))
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(sign_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, 'PNG')
        return http.HttpResponse(buffer.getvalue(), content_type='image/png')


class SigningSessionPageView(generic.TemplateView):
    """Public page used on phone to capture and submit a signature."""

    template_name = 'licenses/sign_session.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = kwargs.get('token')
        session = SigningSession.objects.select_related('license').filter(token=token).first()
        context['session'] = session
        context['is_valid_session'] = bool(session and session.status == SigningSessionStatus.PENDING and not session.is_expired())
        return context


class SubmitSigningSessionView(generic.View):
    """Submit signed payload from phone and finalize session."""

    def post(self, request, *args, **kwargs):
        token = kwargs.get('token')

        if _is_sign_session_rate_limited(request, token):
            return JsonResponse({'success': False, 'error': _('Too many requests. Please try again later.')}, status=429)

        session = SigningSession.objects.select_related('license').filter(token=token).first()
        if not session:
            return JsonResponse({'success': False, 'error': _('Signing session not found.')}, status=404)

        if session.status != SigningSessionStatus.PENDING:
            return JsonResponse({'success': False, 'error': _('Signing session is not active.')}, status=400)
        if session.is_expired():
            session.status = SigningSessionStatus.EXPIRED
            session.save(update_fields=['status'])
            return JsonResponse({'success': False, 'error': _('Signing session expired.')}, status=400)

        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            payload = _extract_signature_payload(data)
        except (json.JSONDecodeError, ValueError) as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

        if not payload.get('signature_method'):
            payload['signature_method'] = 'qr_phone'

        session.signature_svg = payload.get('signature_svg')
        session.signature_points = payload.get('signature_points')
        session.signature_metadata = payload.get('signature_metadata')
        session.signature_method = payload.get('signature_method') or 'qr_phone'
        session.signer_ip = _get_client_ip(request)
        session.signer_user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:512]
        session.signed_at = timezone.now()
        session.status = SigningSessionStatus.SIGNED
        session.save(update_fields=[
            'signature_svg',
            'signature_points',
            'signature_metadata',
            'signature_method',
            'signer_ip',
            'signer_user_agent',
            'signed_at',
            'status',
        ])

        if session.license_id:
            _apply_signature_to_license(session.license, payload)
        return JsonResponse({'success': True, 'status': session.status})


@method_decorator(login_required, name='dispatch')
class DetailsLicensesView(generic.detail.DetailView):
    """Details of a License."""

    template_name = 'licenses/details.html'
    model = License
    form = form_class = forms.CreateLicenseForm

    def ypc_title(self, value):
        """Return title for YPC license."""
        return YouthProtectionCategory.verbose_name(value)

    def get_context_data(self, **kwargs):
        """Add the LicenseForm to context."""
        context = super().get_context_data(**kwargs)
        context['form'] = forms.CreateLicenseForm(instance=self.object)
        context['ypc_title'] = YouthProtectionCategory.verbose_name(self.object.youth_protection_category)
        
        # Add Nextcloud video if exists
        if settings.NEXTCLOUD_ENABLED:
            context['nextcloud_video'] = NextcloudVideoFile.objects.filter(
                license=self.object,
                is_deleted=False
            ).first()
        
        return context




@method_decorator(login_required, name='dispatch')
class DeleteLicenseView(generic.DeleteView):
    """View to delete an unconfirmed license."""
    model = License
    success_url = reverse_lazy('licenses:licenses')
    
    def delete(self, request, *args, **kwargs):
        """Only allow deleting unconfirmed licenses."""
        self.object = self.get_object()

        if self.object.confirmed:
            messages.error(
                self.request,
                _('Cannot delete confirmed license %(license)s') % {'license': str(self.object)}
            )
            return http.HttpResponseRedirect(reverse('licenses:licenses'))

        try:
            from dashboard.models import UserJourney

            # Clear the license_id reference in UserJourney records
            UserJourney.objects.filter(license_id=self.object.id).update(license_id=None)
        except Exception:
            pass

        messages.success(
            self.request,
            _('License %(license)s successfully deleted.') % {'license': str(self.object)}
        )
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class FilledLicenseFile(generic.View):
    """View to deliver a filled license document."""

    def get(self, request, pk):
        """Print a license file of the current license."""
        try:
            license = License.objects.get(pk=pk)
        except License.DoesNotExist:
            return _license_does_not_exist(request)

        if (not license.profile.okuser or
                license.profile.okuser != request.user):
            return _license_does_not_exist(request)

        # Generate PDF - if signature exists, it will be embedded in the PDF
        # This allows users to download their signed document
        return generate_license_file(license)
