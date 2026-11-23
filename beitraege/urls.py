"""URLs of posts."""

from . import pwa
from . import views
from django.urls import path


app_name = 'beitraege'

urlpatterns = [
    path('', views.meine, name='meine'),
    path('neu/', views.neu, name='neu'),
    path('<int:pk>/eingereicht/', views.eingereicht, name='eingereicht'),
    path('<int:pk>/pruefen/', views.pruefen, name='pruefen'),
    path('<int:pk>/bearbeiten/', views.bearbeiten, name='bearbeiten'),
    path('<int:pk>/loeschen/', views.loeschen, name='loeschen'),
    path('freigabe/<str:token>/', views.freigabe, name='freigabe'),
    path('freigabe/<str:token>/bearbeiten/', views.freigabe_bearbeiten, name='freigabe_bearbeiten'),
    path('freigabe/<str:token>/zurueckziehen/', views.freigabe_zurueckziehen,
         name='freigabe_zurueckziehen'),
    path('<int:pk>/zurueckziehen/', views.zurueckziehen, name='zurueckziehen'),
    path('foto/<str:token>/<str:variant>.jpg', views.foto, name='foto'),
    path('manifest.webmanifest', pwa.manifest, name='manifest'),
    path('sw.js', pwa.service_worker, name='sw'),
    path('icon-<int:size>.png', pwa.icon, name='icon'),
    path('offline/', pwa.offline, name='offline'),
    path('teilen/', pwa.teilen, name='teilen'),
]
