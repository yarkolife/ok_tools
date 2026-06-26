"""URL configuration for Tools module."""

from django.urls import path
from . import views, api

app_name = 'tools'

urlpatterns = [
    # UI views
    path('', views.ToolsIndexView.as_view(), name='index'),
    path('media/<path:relpath>/', views.tools_media_stream, name='media_stream'),
    path('slideshow/<int:project_id>/output/stream/', views.slideshow_output_stream, name='slideshow_output_stream'),
    path('slideshow/', views.SlideshowListView.as_view(), name='slideshow_list'),
    path('slideshow/create/', views.SlideshowCreatorView.as_view(), name='slideshow_create'),
    path('slideshow/<int:project_id>/', views.SlideshowDetailView.as_view(), name='slideshow_detail'),
    path('slideshow/<int:project_id>/edit/', views.SlideshowCreatorView.as_view(), name='slideshow_edit'),

    # Audio normalize tool (jobs + new)
    path('audio-normalize/', views.AudioNormalizeJobListView.as_view(), name='audio_normalize'),
    path('audio-normalize/new/', views.AudioNormalizeView.as_view(), name='audio_normalize_new'),
    path('audio-normalize/<int:job_id>/', views.AudioNormalizeJobDetailView.as_view(), name='audio_normalize_job_detail'),

    # Reel studio tool (external OKMQ reel renderer)
    path('reel-studio/', views.ReelStudioView.as_view(), name='reel_studio'),

    # Video render tool (select + deep link)
    path('video-render/', views.VideoRenderSelectView.as_view(), name='video_render_select'),
    path('video-render/<int:video_id>/', views.VideoRenderView.as_view(), name='video_render'),
    path('video-render/jobs/', views.VideoRenderJobsView.as_view(), name='video_render_jobs'),
    
    # API endpoints
    path('api/slideshow/create/', api.CreateSlideshowProjectView.as_view(), name='api_create'),
    path('api/slideshow/<int:project_id>/upload-media/', api.UploadMediaView.as_view(), name='api_upload_media'),
    path('api/slideshow/<int:project_id>/upload-audio/', api.UploadAudioView.as_view(), name='api_upload_audio'),
    path('api/slideshow/<int:project_id>/delete-audio/', api.DeleteAudioView.as_view(), name='api_delete_audio'),
    path('api/slideshow/<int:project_id>/settings/', api.UpdateProjectSettingsView.as_view(), name='api_update_settings'),
    path('api/slideshow/<int:project_id>/generate/', api.GenerateSlideshowView.as_view(), name='api_generate'),
    path('api/slideshow/<int:project_id>/status/', api.ProjectStatusView.as_view(), name='api_status'),
    path('api/slideshow/<int:project_id>/download/', api.DownloadSlideshowView.as_view(), name='api_download'),
    path('api/slideshow/<int:project_id>/', api.DeleteProjectView.as_view(), name='api_delete'),
    path('api/slideshow/<int:project_id>/copy/', api.CopySlideshowProjectView.as_view(), name='api_copy'),
    path('api/slideshow/<int:project_id>/media/<int:media_id>/', api.DeleteMediaView.as_view(), name='api_delete_media'),
    path('api/slideshow/<int:project_id>/media/<int:media_id>/make-library/', api.MakeProjectMediaLibraryView.as_view(), name='api_make_library_media'),
    path('api/slideshow/<int:project_id>/order/', api.UpdateMediaOrderView.as_view(), name='api_update_order'),
    path('api/slideshow/<int:project_id>/add-library-media/', api.AddLibraryMediaToProjectView.as_view(), name='api_add_library_media'),
    path('api/slideshow/<int:project_id>/add-library-audio/', api.AddLibraryAudioToProjectView.as_view(), name='api_add_library_audio'),
    path('api/slideshow/<int:project_id>/audio/<int:audio_id>/make-library/', api.MakeProjectAudioLibraryView.as_view(), name='api_make_library_audio'),
    path('api/slideshow/<int:project_id>/media/bulk-delete/', api.BulkDeleteMediaView.as_view(), name='api_bulk_delete_media'),
    path('api/slideshow/<int:project_id>/media/bulk-make-library/', api.BulkMakeLibraryView.as_view(), name='api_bulk_make_library'),
    
    # Library endpoints
    path('api/library/audio/', api.LibraryAudioListView.as_view(), name='api_library_audio'),
    path('api/library/media/', api.LibraryMediaListView.as_view(), name='api_library_media'),
    path('api/library/media/upload/', api.UploadLibraryMediaView.as_view(), name='api_upload_library_media'),
    path('api/library/media/<int:media_id>/', api.DeleteLibraryMediaView.as_view(), name='api_delete_library_media'),
    path('api/library/audio/<int:audio_id>/', api.DeleteLibraryAudioView.as_view(), name='api_delete_library_audio'),

    # Audio normalize API
    path('api/audio-normalize/presets/', api.AudioPresetsView.as_view(), name='api_audio_presets'),
    path('api/audio-normalize/media-files/', api.MediaFilesByNumberView.as_view(), name='api_audio_media_files'),
    path('api/audio-normalize/create/', api.CreateAudioNormalizeJobView.as_view(), name='api_audio_create'),
    path('api/audio-normalize/<int:job_id>/analyze/', api.AnalyzeOnlyView.as_view(), name='api_audio_analyze'),
    path('api/audio-normalize/<int:job_id>/start/', api.StartNormalizeView.as_view(), name='api_audio_start'),
    path('api/audio-normalize/<int:job_id>/status/', api.AudioJobStatusView.as_view(), name='api_audio_status'),
    path('api/audio-normalize/<int:job_id>/waveform/', api.AudioWaveformView.as_view(), name='api_audio_waveform'),
    path('api/audio-normalize/<int:job_id>/stream-output/', api.StreamOutputView.as_view(), name='api_audio_stream_output'),
    path('api/audio-normalize/<int:job_id>/download/', api.DownloadNormalizedView.as_view(), name='api_audio_download'),
    path('api/audio-normalize/<int:job_id>/', api.DeleteAudioJobView.as_view(), name='api_audio_delete'),

    # Reel studio API
    path('api/reels/hooks/', api.ReelHooksView.as_view(), name='api_reel_hooks'),
    path('api/reels/cta/', api.ReelCtaView.as_view(), name='api_reel_cta'),
    path('api/reels/render/', api.ReelRenderView.as_view(), name='api_reel_render'),
    path('api/reels/tasks/<str:task_id>/', api.ReelTaskStatusView.as_view(), name='api_reel_task'),

    # Video render API
    path('api/video-render/search/', api.VideoRenderSearchView.as_view(), name='api_video_render_search'),
    path('api/video-render/upload/', api.VideoRenderUploadView.as_view(), name='api_video_render_upload'),
    path('api/video-render/submit/', api.VideoRenderSubmitView.as_view(), name='api_video_render_submit'),
]
