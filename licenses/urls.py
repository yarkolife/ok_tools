from . import api
from . import views
from django.urls import path


app_name = 'licenses'
urlpatterns = [
    path(
        '',
        views.ListLicensesView.as_view(),
        name='licenses',
    ),
    path(
        'create/',
        views.CreateLicenseView.as_view(),
        name='create',
    ),
    path(
        '<int:pk>/',
        views.DetailsLicensesView.as_view(),
        name='details',
    ),
    path(
        '<int:pk>/update/',
        views.UpdateLicensesView.as_view(),
        name='update',
    ),
    path(
        '<int:pk>/filled_license_file/',
        views.FilledLicenseFile.as_view(),
        name='print'
    ),
    path(
        'api/metadata/<int:number>/',
        api.LicenseMetadataView.as_view(),
        name='api-metadata'
    ),
    path(
        '<int:pk>/delete/',
        views.DeleteLicenseView.as_view(),
        name='delete'
    ),
    path(
        '<int:pk>/copy/',
        views.CopyLicenseView.as_view(),
        name='copy'
    ),
    path(
        '<int:pk>/upload-video/',
        views.UploadVideoView.as_view(),
        name='upload_video'
    ),
    path(
        'upload-progress/',
        views.UploadProgressView.as_view(),
        name='upload_progress'
    ),
    # Direct upload endpoints (bypasses Django server)
    path(
        '<int:pk>/get-upload-token/',
        views.GetUploadTokenView.as_view(),
        name='get_upload_token'
    ),
    path(
        '<int:pk>/confirm-upload/',
        views.ConfirmUploadView.as_view(),
        name='confirm_upload'
    ),
]
