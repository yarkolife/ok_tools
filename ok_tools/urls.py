"""ok_tools URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from . import accessibility_views
from . import views
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views.generic.base import TemplateView
from django.views.i18n import JavaScriptCatalog
from registration.views import PasswordResetConfirmView
from registration.views import PasswordResetView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

# Import custom admin configurations to ensure they are loaded
from .admin_imports import register_custom_admin
register_custom_admin()

# Import Celery admin customizations after all apps are loaded
# This ensures django_celery_beat is already registered
try:
    from . import admin_celery  # noqa: F401
except ImportError:
    # If admin_celery fails to import, log but don't crash
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Failed to import admin_celery", exc_info=True)

# Serve static files in debug mode
from django.conf import settings
from django.conf.urls.static import static


# Keep default admin site; ordering handled elsewhere

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "profile/reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("profile/password_reset/", PasswordResetView.as_view(), name="password_reset"),
    # This includes upstream passsword reset, login/out views.
    path("profile/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("profile/", include("registration.urls")),
    path(
        "privacy_policy/",
        TemplateView.as_view(template_name="privacy_policy.html"),
        name="privacy_policy",
    ),
    # JavaScript translations
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    # Accessibility URLs
    path('accessibility-statement/', accessibility_views.accessibility_statement, name='accessibility_statement'),
    path('accessibility-feedback/', accessibility_views.accessibility_feedback, name='accessibility_feedback'),
    path('health/', views.health, name='health'),
    path('prometheus/', include('django_prometheus.urls')),
    # API Schema and Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Dashboard (admin analytics) URLs
if getattr(settings, 'DASHBOARD_ENABLED', False):
    urlpatterns.append(
        path("admin-dashboard/", include("dashboard.urls", namespace="dashboard")),
    )

# Licenses + Contributions URLs (contributions depends on licenses)
if getattr(settings, 'LICENSES_ENABLED', True):
    urlpatterns.append(
        path("licenses/", include("licenses.urls")),
    )
    urlpatterns.append(
        path("contributions/", include("contributions.urls")),
    )

# Rental + Inventory URLs
if getattr(settings, 'INVENTORY_ENABLED', False):
    urlpatterns.append(
        path('inventory/', include('inventory.urls', namespace='inventory')),
    )
if getattr(settings, 'RENTAL_ENABLED', False):
    urlpatterns.append(
        path("rental/", views.RentalDashboardView.as_view(), name="rental_dashboard"),
    )
    urlpatterns.append(
        path('rental/', include('rental.urls', namespace='rental')),
    )

# Planning URLs
if getattr(settings, 'PLANUNG_ENABLED', False):
    urlpatterns.append(
        path("planung/", include("planung.urls")),
    )
    urlpatterns.append(
        path("api/", include("planung.urls")),
    )

# Media Files URLs
if getattr(settings, 'MEDIA_FILES_ENABLED', False):
    urlpatterns.append(
        path('media-files/', include('media_files.urls', namespace='media_files')),
    )

# Add Austausch URLs if module is enabled
if getattr(settings, 'AUSTAUSCH_ENABLED', False):
    urlpatterns.append(
        path('austausch/', include('austausch.urls', namespace='austausch')),
    )

# Add Tools URLs if module is enabled
if getattr(settings, 'TOOLS_ENABLED', False):
    urlpatterns.append(
        path('tools/', include('tools.urls', namespace='tools')),
    )

# Serve static files in debug mode
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
