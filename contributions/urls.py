from . import views
from django.urls import path


app_name = 'contributions'
urlpatterns = [
    path(
        '',
        views.ListContributionsView.as_view(),
        name='contributions'
    ),
]
