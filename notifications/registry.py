"""Registry of notification event types.

Event types are declared in code, not in the database. The database only
stores per-type configuration (enabled flag and parameters), and those rows
are synchronised from this registry. Adding a new event type therefore needs
no migration.
"""

from dataclasses import dataclass
from dataclasses import field
from django.utils.translation import gettext_lazy as _
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple


# Categories -- see plans/notifications-digest-plan.md
CATEGORY_ACTION_REQUIRED = 'action_required'
CATEGORY_INFO = 'info'
CATEGORY_PROBLEM = 'problem'

CATEGORY_CHOICES = (
    (CATEGORY_ACTION_REQUIRED, _('Action required')),
    (CATEGORY_INFO, _('For information')),
    (CATEGORY_PROBLEM, _('Problem')),
)

# How an event is produced.
SOURCE_SIGNAL = 'signal'
SOURCE_SCAN = 'scan'

MODULE_LABELS: Dict[str, Any] = {
    'rental': _('Rental'),
    'licenses': _('Licenses'),
    'media_files': _('Media files'),
    'austausch': _('Austausch'),
    'planung': _('Planning'),
    'registration': _('Registration'),
    'tools': _('Tools'),
    'system': _('System'),
}


@dataclass(frozen=True)
class ParamSpec:
    """A single configurable number of a check."""

    name: str
    label: Any
    default: int
    help_text: Any = ''


@dataclass(frozen=True)
class EventType:
    """Declaration of one kind of notification event."""

    code: str
    module: str
    label: Any
    category: str
    source: str
    description: Any = ''
    # Format string filled from the payload at render time, so that the text
    # is produced in the reader's language instead of being stored.
    message: Any = ''
    # 'app_label.ModelName' -- used to mirror admin visibility.
    model: str = ''
    # Settings flag that must be truthy for this type to exist at all.
    settings_flag: str = ''
    # Only superusers may see events of this type.
    superuser_only: bool = False
    # Scan types only: results are recomputed on every render instead of
    # being stored as events (see "facts vs expectations" in the plan).
    expectation: bool = False
    params: Tuple[ParamSpec, ...] = field(default_factory=tuple)
    default_enabled: bool = True

    @property
    def module_label(self) -> Any:
        """Return the human readable name of the owning module."""
        return MODULE_LABELS.get(self.module, self.module)

    def default_params(self) -> Dict[str, int]:
        """Return the parameter defaults as a plain dict."""
        return {spec.name: spec.default for spec in self.params}


_REGISTRY: Dict[str, EventType] = {}
_CHECKS: Dict[str, Callable[..., List['Finding']]] = {}


@dataclass
class Finding:
    """One result produced by a scan check."""

    payload: Dict[str, Any]
    dedup_key: str = ''
    obj: Any = None
    occurred_at: Any = None


def register(event_type: EventType) -> EventType:
    """Add an event type to the registry."""
    if event_type.code in _REGISTRY:
        raise ValueError(f'Duplicate notification event type: {event_type.code}')
    _REGISTRY[event_type.code] = event_type
    return event_type


def scan_check(code: str) -> Callable:
    """Attach a scan callable to an already registered event type."""
    def decorator(func: Callable[..., List[Finding]]) -> Callable[..., List[Finding]]:
        if code not in _REGISTRY:
            raise ValueError(f'Unknown notification event type: {code}')
        _CHECKS[code] = func
        return func
    return decorator


def get(code: str) -> Optional[EventType]:
    """Return the event type with the given code, or None."""
    return _REGISTRY.get(code)


def get_check(code: str) -> Optional[Callable[..., List[Finding]]]:
    """Return the scan callable registered for the given code, or None."""
    return _CHECKS.get(code)


def all_types() -> List[EventType]:
    """Return every declared event type, ordered by module and code."""
    return sorted(_REGISTRY.values(), key=lambda t: (t.module, t.code))


def render_message(code: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Render the human readable line of an event in the current language."""
    event_type = _REGISTRY.get(code)
    if event_type is None:
        return code
    if not event_type.message:
        return str(event_type.label)
    try:
        return str(event_type.message).format(**(payload or {}))
    except (IndexError, KeyError):
        # A payload written by an older version may lack a placeholder.
        return str(event_type.label)


def modules() -> List[str]:
    """Return the module names that declare at least one event type."""
    seen: List[str] = []
    for event_type in all_types():
        if event_type.module not in seen:
            seen.append(event_type.module)
    return seen
