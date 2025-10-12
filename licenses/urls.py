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
]
