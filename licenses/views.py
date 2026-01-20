from . import forms
from .generate_file import generate_license_file
from .models import License
from .models import NextcloudVideoFile
from .models import YouthProtectionCategory
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import generic
from registration.models import Profile
from registration.views import _no_profile_error
import datetime
import django.http as http
import logging


User = get_user_model()
logger = logging.getLogger('django')


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
        """Handle form submission and video upload if enabled."""
        response = super().form_valid(form)
        
        # Video upload is now handled separately after license creation
        # No need to handle it here
        
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
            
            # Create NextcloudVideoFile record
            NextcloudVideoFile.objects.create(
                license=license,
                nextcloud_file_id=upload_result['file_id'],
                nextcloud_url=upload_result['nextcloud_url'],
                filename=upload_result['filename'],
                file_size=video_file.size,
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
            
            # Create NextcloudVideoFile record
            NextcloudVideoFile.objects.create(
                license=license,
                nextcloud_file_id=file_info['file_path'],
                nextcloud_url=file_info['file_url'],
                filename=filename,
                file_size=actual_size,
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

        return generate_license_file(license)
