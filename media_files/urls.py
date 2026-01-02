"""URLs for media files app."""

from django.urls import path
from django.shortcuts import redirect

from . import views


app_name = 'media_files'


def redirect_to_admin_preset_edit(request, preset_id):
    """Redirect old preset edit URLs to admin."""
    from django.urls import reverse
    admin_url = reverse('admin:media_files_videopreset_edit_preset', args=[preset_id])
    return redirect(admin_url, permanent=True)


urlpatterns = [
    # Video rendering
    path('render/submit/', views.render_video, name='render_submit'),
    path('render/video/<int:video_id>/', views.render_video_admin, name='render_video_admin'),
    
    # Preset management - redirect to admin
    path('presets/<int:preset_id>/edit/', redirect_to_admin_preset_edit, name='preset_edit'),
]

