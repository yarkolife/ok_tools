from . import views
from . import users
from . import statistics
from . import notifications
from django.urls import path


app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_main, name='main'),
    path('users/', views.dashboard_users, name='users'),
    path('licenses/', views.dashboard_licenses, name='licenses'),
    path('contributions/', views.dashboard_contributions, name='contributions'),
    path('projects/', views.dashboard_projects, name='projects'),
    path('inventory/', views.dashboard_inventory, name='inventory'),
    path('notifications/', views.dashboard_notifications, name='notifications'),
    path('funnel/', views.dashboard_funnel, name='funnel'),
    path('media-data/', views.dashboard_media_data, name='media_data'),

    # API endpoints - Users
    path('api/users-statistics/', users.api_users_statistics, name='api_users_statistics'),
    path('api/recent-users/', users.api_recent_users, name='api_recent_users'),
    path('api/users-detail/', users.api_users_detail, name='api_users_detail'),

    # API endpoints - Statistics
    path('api/licenses-statistics/', statistics.api_licenses_statistics, name='api_licenses_statistics'),
    path('api/contributions-statistics/', statistics.api_contributions_statistics, name='api_contributions_statistics'),
    path('api/media-data-statistics/', statistics.api_media_data_statistics, name='api_media_data_statistics'),
    path('api/projects-statistics/', statistics.api_projects_statistics, name='api_projects_statistics'),
    path('api/inventory-statistics/', statistics.api_inventory_statistics, name='api_inventory_statistics'),
    path('api/filters-data/', statistics.api_filters_data, name='api_filters_data'),
    path('api/recent-licenses/', statistics.api_recent_licenses, name='api_recent_licenses'),
    path('api/system-status/', statistics.api_system_status, name='api_system_status'),
    path('api/quick-stats/', statistics.api_quick_stats, name='api_quick_stats'),
    
    # Detail view API endpoints - Statistics
    path('api/licenses-detail/', statistics.api_licenses_detail, name='api_licenses_detail'),
    path('api/contributions-detail/', statistics.api_contributions_detail, name='api_contributions_detail'),
    path('api/projects-detail/', statistics.api_projects_detail, name='api_projects_detail'),
    path('api/inventory-detail/', statistics.api_inventory_detail, name='api_inventory_detail'),
    
    # API endpoints - Funnel
    path('api/funnel-metrics/', statistics.api_funnel_metrics, name='api_funnel_metrics'),
    path('api/funnel-breakdown/', statistics.api_funnel_breakdown, name='api_funnel_breakdown'),
    path('api/funnel-trends/', statistics.api_funnel_trends, name='api_funnel_trends'),
    path('api/funnel-detail/', statistics.api_funnel_detail, name='api_funnel_detail'),

    # API endpoints - Notifications
    path('api/notifications-statistics/', notifications.api_notifications_statistics, name='api_notifications_statistics'),
    path('api/notifications-detail/', notifications.api_notifications_detail, name='api_notifications_detail'),
    path('api/notifications-toggle/<int:notification_id>/', notifications.api_notifications_toggle, name='api_notifications_toggle'),
    
    # API endpoints - Alerts and Thresholds
    path('api/alerts-list/', notifications.api_alerts_list, name='api_alerts_list'),
    path('api/alerts-resolve/<int:alert_id>/', notifications.api_alerts_resolve, name='api_alerts_resolve'),
    path('api/thresholds/<int:threshold_id>/', notifications.api_threshold_update, name='api_threshold_update'),
    path('api/thresholds/<int:threshold_id>/toggle/', notifications.api_threshold_toggle, name='api_threshold_toggle'),
]
