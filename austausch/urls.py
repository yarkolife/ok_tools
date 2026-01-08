"""URL configuration for Austausch module."""

from django.urls import path
from . import views, api

app_name = 'austausch'

urlpatterns = [
    # UI views
    path('feed/', views.ExchangeFeedView.as_view(), name='feed'),
    
    # API endpoints
    path('api/decision/<int:number>/', api.ExchangeDecisionView.as_view(), name='api_decision'),
    path('api/items/', api.ExchangeItemListView.as_view(), name='api_items'),
    path('api/import/<int:item_id>/', api.ImportExchangeItemView.as_view(), name='api_import'),
    path('api/import/batch/', api.ImportBatchExchangeItemsView.as_view(), name='api_import_batch'),
    path('api/download/<int:item_id>/<str:file_type>/', api.DownloadExchangeFileView.as_view(), name='api_download'),
    path('api/sync/', api.SyncExchangeView.as_view(), name='api_sync'),
]

