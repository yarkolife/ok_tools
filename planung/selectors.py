"""Read-only lookups into the day plans.

The payload shape is documented in ``plans/planung_json_schema.md``. These
helpers exist so that everything asking "what is planned and when" reads the
JSON in one place instead of parsing it again per caller.
"""

from datetime import date
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional


def plan_items(plan) -> List[Dict[str, Any]]:
    """Return the item list of a day plan, tolerating a malformed payload."""
    payload = getattr(plan, 'json_plan', None)
    if not isinstance(payload, dict):
        return []
    items = payload.get('items')
    return items if isinstance(items, list) else []


def plans_for(dates: Iterable[date]) -> Dict[date, Any]:
    """Return the existing plans for the given days, keyed by date."""
    from planung.models import TagesPlan

    days = list(dates or [])
    if not days:
        return {}
    return {plan.datum: plan for plan in TagesPlan.objects.filter(
        datum__in=days)}


def planned_entries(dates: Iterable[date]) -> List[Dict[str, Any]]:
    """Return one entry per planned item on the given days.

    Each entry carries the plan object, the license number and the fields
    needed to render a readable line.
    """
    entries: List[Dict[str, Any]] = []
    for day, plan in sorted(plans_for(dates).items()):
        for position, item in enumerate(plan_items(plan)):
            if not isinstance(item, dict):
                continue
            try:
                number = int(item.get('number'))
            except (TypeError, ValueError):
                continue
            entries.append({
                'plan': plan,
                'date': day,
                'number': number,
                'start': item.get('start') or '',
                'title': item.get('title') or '',
                'position': position,
            })
    return entries


def planned_numbers(dates: Iterable[date]) -> List[int]:
    """Return the license numbers planned on the given days."""
    return [entry['number'] for entry in planned_entries(dates)]


def is_planned(number: int, dates: Iterable[date]) -> Optional[Dict[str, Any]]:
    """Return the first entry for a number on the given days, or None."""
    for entry in planned_entries(dates):
        if entry['number'] == number:
            return entry
    return None
