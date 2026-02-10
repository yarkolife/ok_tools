from . import views
from . import api
from django.urls import path


app_name = 'contributions'
urlpatterns = [
    path(
        '',
        views.ListContributionsView.as_view(),
        name='contributions'
    ),
    path(
        'api/program/',
        api.ProgramScheduleView.as_view(),
        name='api-program-schedule'
    ),
    path(
        'api/extract-dates/',
        views.extract_dates_from_file,
        name='extract_dates'
    ),
    path(
        'api/extract-dates/<int:pk>/',
        views.extract_dates_from_saved_file,
        name='extract_dates_saved'
    ),
]
