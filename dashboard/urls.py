from django.urls import path
from . import views
from . import api

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_main, name='main'),
    path('users/', views.dashboard_users, name='users'),
    path('licenses/', views.dashboard_licenses, name='licenses'),
    path('contributions/', views.dashboard_contributions, name='contributions'),
    path('projects/', views.dashboard_projects, name='projects'),
    path('inventory/', views.dashboard_inventory, name='inventory'),
    path('notifications/', views.dashboard_notifications, name='notifications'),
    
    # API endpoints
    path('api/users-statistics/', api.api_users_statistics, name='api_users_statistics'),
    path('api/licenses-statistics/', api.api_licenses_statistics, name='api_licenses_statistics'),
    path('api/contributions-statistics/', api.api_contributions_statistics, name='api_contributions_statistics'),
    path('api/projects-statistics/', api.api_projects_statistics, name='api_projects_statistics'),
    path('api/inventory-statistics/', api.api_inventory_statistics, name='api_inventory_statistics'),
    path('api/notifications-statistics/', api.api_notifications_statistics, name='api_notifications_statistics'),
    path('api/filters-data/', api.api_filters_data, name='api_filters_data'),
]
