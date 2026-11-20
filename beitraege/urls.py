"""URLs of posts."""

from . import views
from django.urls import path


app_name = 'beitraege'

urlpatterns = [
    path('neu/', views.neu, name='neu'),
    path('<int:pk>/eingereicht/', views.eingereicht, name='eingereicht'),
    path('<int:pk>/pruefen/', views.pruefen, name='pruefen'),
    path('freigabe/<str:token>/', views.freigabe, name='freigabe'),
    path('foto/<str:token>/<str:variant>.jpg', views.foto, name='foto'),
]
