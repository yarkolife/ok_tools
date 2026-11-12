"""
Sidebar navigation for the Unfold admin theme.

The menu is grouped by task instead of by Django app. It is built on every
request from ``admin.site.get_app_list()``, so it only shows what the user
may see and picks up new models without further work:

1. ``ModelAdmin.menu_section = "<section>"`` puts a model into a section
   (``"hidden"`` keeps it out of the sidebar; it stays reachable through
   "all applications", inlines and links).
2. Otherwise ``MODEL_SECTIONS`` / ``APP_SECTIONS`` below decide.
3. Otherwise a model whose class name ends in ``Config`` goes to settings.
4. Anything left gets a group named after its app, after the sections.
"""

from __future__ import annotations
from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static
from django.urls import get_resolver
from django.utils.translation import gettext_lazy as _
from typing import Any


# (key, title, icon, collapsible, superuser only). Icons are Material Symbols.
SECTIONS: list[tuple[str, Any, str, bool, bool]] = [
    ("work", _("Daily work"), "work", False, False),
    ("archive", _("Archive & media"), "video_library", False, False),
    ("people", _("Users & projects"), "group", False, False),
    ("rental", _("Rental & inventory"), "inventory_2", True, False),
    ("more", _("More"), "more_horiz", True, False),
    ("settings", _("Settings & reference data"), "settings", True, False),
    ("system", _("System"), "dns", True, True),
]

# "app_label.ObjectName" -> section. ObjectName is the model class name, or
# the object_name of the custom links added in ok_tools/admin.py.
MODEL_SECTIONS: dict[str, str] = {
    # Daily work
    "projects.Project": "work",
    "licenses.License": "work",
    "contributions.Contribution": "work",
    "planung.CalendarWeeksProxy": "work",
    "rental.RentalProcessProxy": "work",
    "inventory.InventoryItem": "work",
    "austausch.ExchangeFeed": "work",
    "contributions.DisaImport": "work",
    "tools.ToolsInterface": "work",
    "notifications.NotificationsFeed": "work",
    "dashboard.Dashboard": "work",
    # Background jobs (video render, imports): checked after starting one
    "django_celery_results.TaskResult": "work",
    # Archive & media
    "licenses.ArchiveMedium": "archive",
    "media_files.VideoFile": "archive",
    "media_files.StorageLocation": "archive",
    "austausch.ExchangeItem": "archive",
    "media_files.CoverTemplate": "archive",
    "media_files.CoverOverlay": "archive",
    "media_files.CoverOverlayRule": "archive",
    # Users & projects
    "registration.OKUser": "people",
    "registration.Profile": "people",
    "registration.MediaAuthority": "people",
    "auth.Group": "people",
    "projects.ProjectLeader": "people",
    "projects.MediaEducationSupervisor": "people",
    # Rental & inventory
    "rental.RentalRequest": "rental",
    "rental.RoomRental": "rental",
    "rental.Room": "rental",
    "rental.EquipmentSet": "rental",
    "rental.RentalConsumable": "rental",
    "inventory.Location": "rental",
    "inventory.Inspection": "rental",
    "inventory.Manufacturer": "rental",
    "inventory.Organization": "rental",
    # More: used now and then
    "planung.TagesPlan": "more",
    "planung.PlanTemplate": "more",
    "planung.ProgramMailProxy": "more",
    "notifications.ManualReminder": "more",
    "tools.SlideshowProject": "more",
    "tools.AudioNormalizeJob": "more",
    # Settings & reference data (the *Config models land here by rule)
    "registration.Configuration": "settings",
    "registration.Notification": "settings",
    "notifications.NotificationsSubscriptions": "settings",
    "notifications.NotificationsSettings": "settings",
    "notifications.Subscription": "settings",
    "notifications.NotificationSuppression": "settings",
    "licenses.Category": "settings",
    "licenses.YouthProtectionWindow": "settings",
    "rental.LabelFormat": "settings",
    "inventory.Category": "settings",
    "inventory.InventorySeries": "settings",
    "projects.ProjectCategory": "settings",
    "projects.TargetGroup": "settings",
    "tools.VideoEncodePreset": "settings",
    "tools.VideoPreset": "settings",
    "tools.PresetOverlay": "settings",
    # System: logs, imports, background jobs
    "notifications.NotificationsStats": "system",
    "notifications.NotificationEvent": "system",
    "media_files.FileOperation": "system",
    "media_files.SystemManagementProxy": "system",
    "inventory.AuditLog": "system",
    "inventory.InventoryImport": "system",
    "inventory.InspectionImport": "system",
    "austausch.ExchangeImport": "system",
    "austausch.ExportToServerRun": "system",
    "planung.PlanChangeLog": "system",
    "planung.ProgramMailLog": "system",
    # Only needed inside their parent record
    "rental.RentalItem": "hidden",
    "rental.RentalTransaction": "hidden",
    "rental.RentalIssue": "hidden",
    "inventory.InventoryItemImage": "hidden",
    "tools.SlideshowAudio": "hidden",
    "tools.SlideshowMedia": "hidden",
}

# Whole apps that belong to one section.
APP_SECTIONS: dict[str, str] = {
    "authtoken": "system",
    "django_celery_beat": "system",
    "django_celery_results": "system",
}

# Per-item icons (Material Symbols). Items without one get their section's.
MODEL_ICONS: dict[str, str] = {
    "dashboard.Dashboard": "dashboard",
    "licenses.License": "verified",
    "contributions.Contribution": "live_tv",
    "planung.CalendarWeeksProxy": "calendar_month",
    "planung.ProgramMailProxy": "mail",
    "planung.TagesPlan": "today",
    "rental.RentalProcessProxy": "shopping_cart",
    "rental.RentalRequest": "assignment",
    "rental.RoomRental": "meeting_room",
    "austausch.ExchangeFeed": "swap_horiz",
    "notifications.NotificationsFeed": "notifications",
    "notifications.ManualReminder": "alarm",
    "licenses.ArchiveMedium": "album",
    "media_files.VideoFile": "movie",
    "media_files.StorageLocation": "hard_drive",
    "media_files.CoverTemplate": "image",
    "media_files.CoverOverlay": "layers",
    "media_files.CoverOverlayRule": "rule",
    "austausch.ExchangeItem": "cloud_download",
    "registration.OKUser": "person",
    "registration.Profile": "badge",
    "registration.MediaAuthority": "account_balance",
    "auth.Group": "groups",
    "projects.Project": "school",
    "projects.ProjectLeader": "co_present",
    "projects.MediaEducationSupervisor": "supervisor_account",
    "rental.Room": "door_front",
    "rental.EquipmentSet": "category",
    "rental.RentalConsumable": "battery_charging_full",
    "inventory.InventoryItem": "inventory",
    "inventory.Location": "location_on",
    "inventory.Inspection": "fact_check",
    "inventory.Manufacturer": "factory",
    "inventory.Organization": "corporate_fare",
    "tools.ToolsInterface": "handyman",
    "tools.SlideshowProject": "slideshow",
    "tools.AudioNormalizeJob": "graphic_eq",
    "planung.PlanTemplate": "view_timeline",
    "registration.Configuration": "tune",
    "notifications.NotificationsSubscriptions": "notifications_active",
    "notifications.NotificationsSettings": "edit_notifications",
    "licenses.Category": "label",
    "inventory.Category": "label",
    "licenses.YouthProtectionWindow": "shield",
    "rental.LabelFormat": "qr_code_2",
    "inventory.InventorySeries": "pin",
    "projects.ProjectCategory": "label",
    "projects.TargetGroup": "diversity_3",
    "tools.VideoEncodePreset": "video_settings",
    "tools.VideoPreset": "video_settings",
    "tools.PresetOverlay": "layers",
    "notifications.NotificationsStats": "monitoring",
    "media_files.FileOperation": "sync_alt",
    "media_files.SystemManagementProxy": "admin_panel_settings",
    "inventory.AuditLog": "history",
    "planung.PlanChangeLog": "history",
    "contributions.DisaImport": "upload_file",
    "django_celery_results.TaskResult": "task_alt",
    "authtoken.Token": "key",
    "authtoken.TokenProxy": "key",
}

# Menu titles that differ from the model's verbose name (e.g. apps
# without a German translation).
MODEL_TITLES: dict[str, Any] = {
    "django_celery_results.TaskResult": _("Background tasks"),
    "licenses.Category": _("Categories (licenses)"),
    "inventory.Category": _("Categories (inventory)"),
}

# Position of a model inside its section: the order of MODEL_SECTIONS.
_ORDER = {key: index for index, key in enumerate(MODEL_SECTIONS)}


def _section_for(app_label: str, model: dict[str, Any]) -> str | None:
    object_name = model.get("object_name") or ""
    model_cls = model.get("model")
    if model_cls is not None:
        model_admin = admin.site._registry.get(model_cls)
        section = getattr(model_admin, "menu_section", None)
        if section:
            return section
    key = f"{app_label}.{object_name}"
    if key in MODEL_SECTIONS:
        return MODEL_SECTIONS[key]
    if app_label in APP_SECTIONS:
        return APP_SECTIONS[app_label]
    if object_name.endswith("Config"):
        return "settings"
    return None


def _item(app_label: str, model: dict[str, Any], default_icon: str) -> dict[str, Any]:
    key = f"{app_label}.{model.get('object_name')}"
    return {
        "title": MODEL_TITLES.get(key, model["name"]),
        "link": model["admin_url"],
        "icon": MODEL_ICONS.get(key, default_icon),
        "_order": _ORDER.get(key, len(_ORDER)),
    }


def navigation(request) -> list[dict[str, Any]]:
    """Return Unfold's SIDEBAR["navigation"] for this request."""
    # ok_tools/urls.py registers some admins (Token, Celery) when it is
    # imported. Load the URLconf first, otherwise the reverse() calls in
    # get_app_list() import it while the registry is iterated
    # ("dictionary changed size during iteration").
    get_resolver().url_patterns
    sections: dict[str, list[dict[str, Any]]] = {key: [] for key, *_ in SECTIONS}
    section_icons = {key: icon for key, _title, icon, *_ in SECTIONS}
    leftovers: list[dict[str, Any]] = []

    for app in admin.site.get_app_list(request):
        app_label = app.get("app_label", "")
        app_items = []
        for model in app.get("models", []):
            if not model.get("admin_url"):
                continue
            section = _section_for(app_label, model)
            if section == "hidden":
                continue
            if section in sections:
                sections[section].append(
                    _item(app_label, model, section_icons[section]))
            else:
                app_items.append(_item(app_label, model, "folder"))
        for item in app_items:
            item.pop("_order")
        if app_items:
            leftovers.append({
                "title": app["name"],
                "collapsible": True,
                "separator": True,
                "items": app_items,
            })

    groups = []
    for key, title, _icon, collapsible, superuser_only in SECTIONS:
        if not sections[key]:
            continue
        if superuser_only and not request.user.is_superuser:
            continue
        groups.append({
            "title": title,
            "collapsible": collapsible,
            "separator": bool(groups),
            "items": sorted(sections[key], key=lambda item: item.pop("_order")),
        })
    return groups + leftovers


def environment_callback(request) -> list[str] | None:
    """Label in the header so the test server is not mistaken for production."""
    label = getattr(settings, "ADMIN_ENVIRONMENT_LABEL", "") or ""
    if not label and settings.DEBUG:
        label = "Development"
    if not label:
        return None
    color = "danger" if label.lower().startswith(("prod", "live")) else "warning"
    return [label, color]


def site_logo(request) -> str:
    """The organisation's large logo, or the bundled OK Tools logo."""
    from registration.organization_config import get_organization_logo_large_url
    return get_organization_logo_large_url() or static("img/logo.png")


def favicon(request) -> str:
    return static("img/favicon.ico")


def theme_stylesheet(request) -> str:
    """Shared light/dark tokens (also used by the pages outside the admin)."""
    return _versioned("ok_tools/css/ok_theme.css")


def theme_script(request) -> str:
    return _versioned("ok_tools/js/ok_theme.js")


def select2_i18n_script(request) -> str:
    """German texts for the select2 dropdowns of the change list filters."""
    return _versioned("ok_tools/js/select2_i18n.js")


def override_stylesheet(request) -> str:
    """CSS that fits the classic admin markup of our templates into Unfold."""
    return _versioned("ok_tools/css/unfold_overrides.css")


def _versioned(path: str) -> str:
    """static() URL plus the file's mtime, so browsers drop stale copies
    in development (production URLs are hashed by the storage anyway)."""
    from django.contrib.staticfiles import finders
    import os
    url = static(path)
    found = finders.find(path)
    if found:
        url += f"?v={int(os.path.getmtime(found))}"
    return url
