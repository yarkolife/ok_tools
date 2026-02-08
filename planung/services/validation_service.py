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
