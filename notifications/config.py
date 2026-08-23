"""Access to the channel level configuration of event types.

Level 1 of the gate chain is the module flag in settings, level 2 is the
``enabled`` column synchronised from the registry. Level 3 (per user
subscriptions) lives in :mod:`notifications.selectors`.
"""

from django.conf import settings
from notifications import registry
from notifications.models import NotificationEventTypeConfig
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


def sync_event_type_configs() -> Dict[str, int]:
    """Create missing configuration rows for every declared event type.

    Existing rows are left untouched: they carry administrator decisions.
    Returns a summary usable by management commands.
    """
    existing = set(
        NotificationEventTypeConfig.objects.values_list('code', flat=True))
    to_create = [
        NotificationEventTypeConfig(
            code=event_type.code,
            enabled=event_type.default_enabled,
            params=event_type.default_params(),
        )
        for event_type in registry.all_types()
        if event_type.code not in existing
    ]
    if to_create:
        NotificationEventTypeConfig.objects.bulk_create(
            to_create, ignore_conflicts=True)
    return {'created': len(to_create), 'existing': len(existing)}


def module_flag_enabled(event_type: registry.EventType) -> bool:
    """Return whether the settings flag of the owning module is on."""
    if not event_type.settings_flag:
        return True
    return bool(getattr(settings, event_type.settings_flag, False))


def get_type_config(code: str) -> Optional[NotificationEventTypeConfig]:
    """Return the stored configuration row for a code, creating it if needed."""
    event_type = registry.get(code)
    if event_type is None:
        return None
    config, _created = NotificationEventTypeConfig.objects.get_or_create(
        code=code,
        defaults={
            'enabled': event_type.default_enabled,
            'params': event_type.default_params(),
        },
    )
    return config


def is_enabled(code: str) -> bool:
    """Return whether the event type passes gate levels 1 and 2."""
    event_type = registry.get(code)
    if event_type is None:
        return False
    if not module_flag_enabled(event_type):
        return False
    config = get_type_config(code)
    return bool(config and config.enabled)


def get_params(code: str) -> Dict[str, Any]:
    """Return the effective parameters: registry defaults plus stored values."""
    event_type = registry.get(code)
    if event_type is None:
        return {}
    params = event_type.default_params()
    specs = {spec.name: spec for spec in event_type.params}
    config = get_type_config(code)
    if config and isinstance(config.params, dict):
        for key, value in config.params.items():
            if key in params:
                spec = specs[key]
                if spec.kind == 'storage_locations':
                    if not isinstance(value, (list, tuple)):
                        continue
                    params[key] = [
                        int(item) for item in value
                        if str(item).isdigit()
                    ]
                    continue
                if spec.kind == 'choice':
                    # A value that is no longer offered falls back to the
                    # default rather than reaching the check.
                    if value in {option for option, _label in spec.choices}:
                        params[key] = value
                    continue
                try:
                    params[key] = int(value)
                except (TypeError, ValueError):
                    continue
    return params


def enabled_types() -> List[registry.EventType]:
    """Return every event type that currently passes gates 1 and 2."""
    return [
        event_type for event_type in registry.all_types()
        if is_enabled(event_type.code)
    ]
