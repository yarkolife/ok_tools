from __future__ import annotations
from django.apps import apps as django_apps
from django.contrib import admin
from django.contrib.admin.sites import site as default_site
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from typing import Any
from typing import Dict
from typing import List


# Custom order of models inside apps on Django admin index.
# Keys are app labels, values are lists of model class names in desired order.
ADMIN_MODEL_ORDER: Dict[str, List[str]] = {
    "inventory": [
        "InventoryItem",
        "Location",
        "InventoryImport",
        "Inspection",
        "InspectionImport",
        "Manufacturer",
        "Organization",
        "AuditLog",
    ],
    # Licenses first; the archive carriers belong to them. The other models
    # keep their alphabetical order after these two.
    "licenses": [
        "License",
        "ArchiveMedium",
    ],
    "rental": [
        "RentalProcessProxy",  # This will be the first item - our custom rental process link
        "Room",
        "EquipmentSet",
        "RentalIssue",
        "RentalItem",
        "RentalRequest",
        "RoomRental",
        "RentalTransaction",
    ],
}


def _is_config_model(model) -> bool:
    """Configuration models keep exactly one row, reached through ``get_config()``."""
    return callable(getattr(model, "get_config", None))


def configuration_entries(request) -> List[Dict[str, Any]]:
    """Every settings form the user may open, for the one configuration page."""
    from django.utils.text import capfirst

    entries = []
    for model, model_admin in default_site._registry.items():
        if not _is_config_model(model):
            continue
        if not model_admin.has_module_permission(request):
            continue
        if not (model_admin.has_view_permission(request)
                or model_admin.has_change_permission(request)):
            continue
        opts = model._meta
        entries.append({
            "title": capfirst(opts.verbose_name),
            "app": capfirst(opts.app_config.verbose_name),
            "url": reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"),
        })
    if django_apps.is_installed("notifications") and request.user.is_superuser:
        entries.append({
            "title": _("Notification settings"),
            "app": _("Notifications"),
            "url": reverse("admin:notifications_settings"),
        })
    entries.sort(key=lambda entry: (str(entry["app"]), str(entry["title"])))
    return entries


def configuration_index_view(request):
    """One page with all settings forms; each card opens its form directly."""
    context = {
        **default_site.each_context(request),
        "title": _("Configuration"),
        "config_links": configuration_entries(request),
    }
    return TemplateResponse(request, "admin/configuration_index.html", context)


def _open_singleton_form(model_admin):
    """Make the list of a one-row configuration model open its form instead.

    Every ``*Config`` model keeps exactly one row (``get_config()``); a list
    with that single row is only a detour on the way to the settings.
    """
    original = model_admin.changelist_view

    def changelist_view(request, extra_context=None):
        if not (model_admin.has_view_permission(request)
                or model_admin.has_change_permission(request)):
            return original(request, extra_context)
        config = model_admin.model.get_config()
        opts = model_admin.model._meta
        return HttpResponseRedirect(
            reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[config.pk]))

    model_admin.changelist_view = changelist_view


def _install_singleton_forms(site: admin.AdminSite) -> None:
    for model, model_admin in site._registry.items():
        if _is_config_model(model) and not getattr(
                model_admin, "_opens_singleton_form", False):
            _open_singleton_form(model_admin)
            model_admin._opens_singleton_form = True


def _reorder_app_list(app_list: List[Dict[str, Any]], request=None) -> List[Dict[str, Any]]:
    if request is None:
        return _sort_models(app_list)
    # All settings forms are reached through the one configuration page.
    config_names = {
        model.__name__ for model in default_site._registry if _is_config_model(model)
    } | {"NotificationsSettings"}
    for app in app_list:
        app["models"] = [
            model for model in app.get("models", [])
            if model.get("object_name") not in config_names
        ]
    if configuration_entries(request):
        hub = {
            "name": _("Configuration"),
            "object_name": "Configuration",
            "admin_url": reverse("admin:configuration"),
            "add_url": None,
            "view_only": True,
        }
        registration = next(
            (app for app in app_list if app.get("app_label") == "registration"), None)
        if registration is None:
            registration = {
                "name": _("Configuration"),
                "app_label": "registration",
                "app_url": reverse("admin:configuration"),
                "has_module_perms": True,
                "models": [],
            }
            app_list.append(registration)
        registration["models"].insert(0, hub)
    app_list = [app for app in app_list if app.get("models")]
    return _sort_models(app_list)


def _sort_models(app_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for app in app_list:
        desired = ADMIN_MODEL_ORDER.get(app.get("app_label"))
        if not desired:
            continue
        order_index = {name: idx for idx, name in enumerate(desired)}

        app["models"].sort(
            key=lambda m: (
                order_index.get(m.get("object_name"), 10_000),
                m.get("name", ""),
            )
        )
    return app_list


# Monkey-patch the existing default admin.site instance so all registrations remain valid
_original_get_app_list = default_site.get_app_list


def _custom_get_app_list(self: admin.AdminSite, request, app_label=None):  # type: ignore[override]
    app_list = list(_original_get_app_list(app_label=app_label, request=request))

    # Add dashboard link to the beginning of the list
    if app_label is None:  # Only on the main admin page
        dashboard_app = {
            'name': _('Dashboard'),
            'app_label': 'dashboard',
            'app_url': '/admin-dashboard/',
            'has_module_perms': True,
            'models': [
                {
                    'name': _('Main Dashboard'),
                    'object_name': 'Dashboard',
                    'admin_url': '/admin-dashboard/',
                    'add_url': None,
                    'view_only': True,
                }
            ]
        }
        from django.conf import settings
        if getattr(settings, 'DASHBOARD_ENABLED', False):
            app_list.insert(0, dashboard_app)

        # Notifications: personal feed first, configuration for superusers.
        # The app may already be in the list because of its admin models --
        # in that case the custom pages are prepended to it.
        if django_apps.is_installed('notifications'):
            custom_models = [
                {
                    'name': _('My notifications'),
                    'object_name': 'NotificationsFeed',
                    'admin_url': reverse('admin:notifications_feed'),
                    'add_url': None,
                    'view_only': True,
                },
                {
                    'name': _('My subscriptions'),
                    'object_name': 'NotificationsSubscriptions',
                    'admin_url': reverse('admin:notifications_subscriptions'),
                    'add_url': None,
                    'view_only': True,
                },
            ]
            if request.user.is_superuser:
                custom_models.append({
                    'name': _('Notification settings'),
                    'object_name': 'NotificationsSettings',
                    'admin_url': reverse('admin:notifications_settings'),
                    'add_url': None,
                    'view_only': True,
                })
                custom_models.append({
                    'name': _('Notification statistics'),
                    'object_name': 'NotificationsStats',
                    'admin_url': reverse('admin:notifications_stats'),
                    'add_url': None,
                    'view_only': True,
                })

            existing = next(
                (app for app in app_list
                 if app.get('app_label') == 'notifications'),
                None,
            )
            if existing is not None:
                existing['models'] = custom_models + existing.get('models', [])
                app_list.remove(existing)
                app_list.insert(0, existing)
            else:
                app_list.insert(0, {
                    'name': _('Notifications'),
                    'app_label': 'notifications',
                    'app_url': reverse('admin:notifications_feed'),
                    'has_module_perms': True,
                    'models': custom_models,
                })
        
        # Add Exchange Feed link to Austausch app if module is enabled
        if getattr(settings, 'AUSTAUSCH_ENABLED', False):
            # Find Austausch app in the list
            for app in app_list:
                if app.get('app_label') == 'austausch':
                    # Add Exchange Feed link as first model
                    feed_model = {
                        'name': _('Exchange Feed'),
                        'object_name': 'ExchangeFeed',
                        'admin_url': '/austausch/feed/',
                        'add_url': None,
                        'view_only': True,
                    }
                    app['models'].insert(0, feed_model)
                    break
        
        # Add Tools interface link to Tools app if module is enabled
        if getattr(settings, 'TOOLS_ENABLED', False):
            # Find Tools app in the list
            for app in app_list:
                if app.get('app_label') == 'tools':
                    # Add Tools interface link as first model
                    tools_model = {
                        'name': _('All Tools'),
                        'object_name': 'ToolsInterface',
                        'admin_url': '/tools/',
                        'add_url': None,
                        'view_only': True,
                    }
                    app['models'].insert(0, tools_model)
                    break

    return _reorder_app_list(app_list, request if app_label is None else None)


_original_get_urls = default_site.get_urls


def _custom_get_urls(self: admin.AdminSite):  # type: ignore[override]
    # Before the model URLs are built, so they point at the redirecting views.
    _install_singleton_forms(self)
    urls = _original_get_urls()
    custom_urls = [
        path(
            "configuration/",
            self.admin_view(configuration_index_view),
            name="configuration",
        ),
    ]
    if django_apps.is_installed("notifications"):
        from notifications.views import feed_view
        from notifications.views import settings_view
        from notifications.views import stats_view
        from notifications.views import subscriptions_view

        custom_urls += [
            path(
                "notifications/",
                self.admin_view(feed_view),
                name="notifications_feed",
            ),
            path(
                "notifications/subscriptions/",
                self.admin_view(subscriptions_view),
                name="notifications_subscriptions",
            ),
            path(
                "notifications/settings/",
                self.admin_view(settings_view),
                name="notifications_settings",
            ),
            path(
                "notifications/stats/",
                self.admin_view(stats_view),
                name="notifications_stats",
            ),
        ]
    return custom_urls + urls


default_site.get_app_list = _custom_get_app_list.__get__(default_site, admin.AdminSite)
default_site.get_urls = _custom_get_urls.__get__(default_site, admin.AdminSite)
