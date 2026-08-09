"""Subscription presets.

Django groups are not used anywhere in this project, so a "role" here is
just a button that ticks a set of checkboxes. It grants nothing.
"""

from django.utils.translation import gettext_lazy as _
from typing import Dict
from typing import List
from typing import Tuple


PRESETS: Dict[str, Tuple[object, List[str]]] = {
    'verleih': (_('Verleih'), ['rental']),
    'redaktion': (_('Redaktion'), ['licenses', 'planung', 'austausch']),
    'technik': (_('Technik'), ['media_files', 'tools', 'system']),
    'verwaltung': (_('Verwaltung'), ['registration']),
}


def get_modules(name: str) -> List[str]:
    """Return the modules of a preset, or an empty list for unknown names."""
    preset = PRESETS.get(name)
    return list(preset[1]) if preset else []


def choices() -> List[Tuple[str, object]]:
    """Return (name, label) pairs for rendering the preset buttons."""
    return [(name, preset[0]) for name, preset in PRESETS.items()]
