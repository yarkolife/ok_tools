"""Auto-copy side-effects for planning saves."""

from __future__ import annotations

from datetime import date
import logging


logger = logging.getLogger(__name__)


def trigger_auto_copy_for_plan(*, plan_date: date, plan_data: dict, user_id: int | None = None) -> None:
    """Trigger copy-to-playout/archive if feature flags and payload allow it."""
    from media_files.config import (
        get_video_auto_copy_on_schedule,
        get_video_auto_copy_to_archive,
        get_video_auto_copy_to_playout,
    )

    auto_copy_enabled = get_video_auto_copy_on_schedule()
    copy_to_archive = get_video_auto_copy_to_archive()
    copy_to_playout = get_video_auto_copy_to_playout()

    if bool(plan_data.get("draft")):
        return
    if not auto_copy_enabled:
        return
    if not (copy_to_archive or copy_to_playout):
        return

    numbers = [item.get("number") for item in plan_data.get("items", []) if item.get("number")]
    if not numbers:
        return

    try:
        from media_files.tasks import copy_videos_for_plan
    except ImportError:
        logger.warning("media_files module not available, skipping auto-copy")
        return

    logger.info(
        "Triggering auto-copy for %s videos for plan %s (archive=%s, playout=%s)",
        len(numbers),
        plan_date,
        copy_to_archive,
        copy_to_playout,
    )
    try:
        copy_videos_for_plan.delay(numbers, plan_date, user_id=user_id)
    except AttributeError:
        copy_videos_for_plan(numbers, plan_date, user_id=user_id)

