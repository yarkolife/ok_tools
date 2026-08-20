"""Validation helpers for incoming planning payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
import re


TIME_RE = re.compile(r"^(?P<h>\d{2}):(?P<m>\d{2})(:(?P<s>\d{2}))?$")


class PlanningValidationError(Exception):
    """Structured validation error container."""

    def __init__(self, errors: list[dict], warnings: list[dict] | None = None):
        super().__init__("Invalid planning payload")
        self.errors = errors
        self.warnings = warnings or []


@dataclass(frozen=True)
class ValidatedPlanPayload:
    """Normalized, validated payload for save operations."""

    plan_date: date
    items: list[dict]
    draft: bool
    planned: bool
    comment: str
    warnings: list[dict]


def _time_to_seconds(value: str) -> int:
    """Convert HH:MM or HH:MM:SS into absolute seconds from 00:00:00."""
    match = TIME_RE.match(value or "")
    if not match:
        raise ValueError("invalid time format")
    h = int(match.group("h"))
    m = int(match.group("m"))
    s = int(match.group("s") or "0")
    if h > 23 or m > 59 or s > 59:
        raise ValueError("time out of range")
    return h * 3600 + m * 60 + s


def _seconds_to_label(seconds: int) -> str:
    """Render absolute seconds as HH:MM, wrapping past midnight."""
    seconds = int(seconds) % 86400
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def check_youth_protection(items: list[dict]) -> list[dict]:
    """Return errors for items scheduled outside their allowed window.

    The age rating comes from the licence; the window it may be aired in is
    configured per rating in the admin. Material that may not be shown during
    the day is rejected here rather than after it has gone out.
    """
    from licenses.models import License
    from licenses.models import YouthProtectionWindow

    windows = YouthProtectionWindow.enforced_windows()
    if not windows or not items:
        return []

    numbers = {item["number"] for item in items}
    categories = dict(
        License.objects.filter(number__in=numbers)
        .values_list("number", "youth_protection_category")
    )

    errors: list[dict] = []
    for idx, item in enumerate(items):
        window = windows.get(categories.get(item["number"]))
        if window is None:
            continue
        start_seconds = _time_to_seconds(item["start"])
        if window.allows(start_seconds, item["duration"]):
            continue
        end_label = _seconds_to_label(start_seconds + item["duration"])
        errors.append({
            "field": f"items[{idx}].start",
            "message": _(
                "%(title)s (%(number)s) is rated %(rating)s and may only be "
                "broadcast between %(from)s and %(to)s. Planned "
                "%(start)s-%(end)s."
            ) % {
                "title": item.get("title") or item["number"],
                "number": item["number"],
                "rating": window.get_category_display(),
                "from": window.start_time.strftime("%H:%M"),
                "to": window.end_time.strftime("%H:%M"),
                "start": _seconds_to_label(start_seconds),
                "end": end_label,
            },
            "youth_protection": {
                "category": window.category,
                "allowed_from": window.start_time.strftime("%H:%M"),
                "allowed_until": window.end_time.strftime("%H:%M"),
            },
        })
    return errors


def validate_day_plan_payload(data: dict) -> ValidatedPlanPayload:
    """Validate and normalize payload used by day-plan API."""
    errors: list[dict] = []
    warnings: list[dict] = []

    parsed_date = parse_date((data or {}).get("date") or "")
    if not parsed_date:
        errors.append({"field": "date", "message": _("Invalid date")})

    items = (data or {}).get("items", [])
    if not isinstance(items, list):
        errors.append({"field": "items", "message": _("Items must be a list")})
        items = []

    normalized_items: list[dict] = []
    seen_numbers: set[int] = set()
    schedule_slots: list[tuple[int, int, int]] = []

    for idx, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            errors.append({"field": f"items[{idx}]", "message": _("Item must be an object")})
            continue

        number = raw_item.get("number")
        start = (raw_item.get("start") or "").strip()
        duration = raw_item.get("duration")

        try:
            number_int = int(number)
        except Exception:
            errors.append({"field": f"items[{idx}].number", "message": _("License number must be an integer")})
            continue

        try:
            duration_int = int(duration)
        except Exception:
            errors.append({"field": f"items[{idx}].duration", "message": _("Duration must be an integer in seconds")})
            continue

        if duration_int <= 0:
            errors.append({"field": f"items[{idx}].duration", "message": _("Duration must be greater than zero")})
            continue

        try:
            start_seconds = _time_to_seconds(start)
        except ValueError:
            errors.append({"field": f"items[{idx}].start", "message": _("Start time must be HH:MM or HH:MM:SS")})
            continue

        if number_int in seen_numbers:
            warnings.append({
                "field": f"items[{idx}].number",
                "message": _("Duplicate license number in one day plan"),
            })
        seen_numbers.add(number_int)

        schedule_slots.append((idx, start_seconds, start_seconds + duration_int))

        normalized_items.append(
            {
                **raw_item,
                "number": number_int,
                "start": start,
                "duration": duration_int,
            }
        )

    # Overlap detection
    schedule_slots.sort(key=lambda x: x[1])
    for i in range(1, len(schedule_slots)):
        prev_idx, prev_start, prev_end = schedule_slots[i - 1]
        cur_idx, cur_start, cur_end = schedule_slots[i]
        if cur_start < prev_end:
            errors.append(
                {
                    "field": f"items[{cur_idx}].start",
                    "message": _("Time overlap detected with another item"),
                    "conflicts_with": prev_idx,
                }
            )

    # Youth protection needs the licences, so it runs once the items are
    # normalized and only when the payload is otherwise sound.
    if not errors:
        errors.extend(check_youth_protection(normalized_items))

    if errors:
        raise PlanningValidationError(errors=errors, warnings=warnings)

    return ValidatedPlanPayload(
        plan_date=parsed_date,
        items=normalized_items,
        draft=bool((data or {}).get("draft", False)),
        planned=bool((data or {}).get("planned", False)),
        comment=((data or {}).get("comment") or ""),
        warnings=warnings,
    )
