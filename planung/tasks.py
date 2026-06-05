"""Celery tasks for planning integrations."""

from celery import shared_task
from datetime import date
from planung.services.playout_import_service import fetch_playout_missing_media
from planung.services.anchor_render_service import get_anchor_job_status
from planung.services.anchor_render_service import render_anchor_preview
from typing import Any
import logging
import time


logger = logging.getLogger(__name__)


@shared_task(name="planung.tasks.sync_playout_missing_media")
def sync_playout_missing_media(page_size: int | None = None) -> dict[str, Any]:
    """Query playout for files that are still missing metadata."""
    result = fetch_playout_missing_media(page=1, page_size=page_size)
    if result.error:
        logger.warning("Playout missing metadata sync failed: %s", result.error)
    elif result.configured:
        logger.info(
            "Playout missing metadata sync found %s files missing metadata",
            result.total,
        )
    return {
        "configured": result.configured,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "error": result.error,
    }


@shared_task(name="planung.tasks.poll_anchor_render_job", bind=True)
def poll_anchor_render_job(
    self,
    job_id: str,
    output_name: str = "",
    poll_interval: int = 15,
    max_attempts: int = 480,
) -> dict[str, Any]:
    """Poll the external anchor renderer until the render job is finished."""
    safe_interval = max(1, int(poll_interval))
    safe_attempts = max(1, int(max_attempts))

    for attempt in range(1, safe_attempts + 1):
        result = get_anchor_job_status(job_id)
        payload = {
            "job_id": result.job_id,
            "status": result.status,
            "file": result.file,
            "error": result.error,
            "output_name": output_name,
            "attempt": attempt,
            "max_attempts": safe_attempts,
        }
        self.update_state(state="PROGRESS", meta=payload)

        if result.status == "done":
            logger.info("Anchor render job %s finished: %s", job_id, result.file)
            return payload
        if result.status == "error" or result.error:
            logger.warning("Anchor render job %s failed: %s", job_id, result.error)
            return payload

        time.sleep(safe_interval)

    error_payload = {
        "job_id": job_id,
        "status": "timeout",
        "file": "",
        "error": "status_polling_timeout",
        "output_name": output_name,
        "attempt": safe_attempts,
        "max_attempts": safe_attempts,
    }
    logger.warning("Anchor render job %s polling timed out", job_id)
    return error_payload


def _wait_for_copy_in_chain(plan_date_obj: date, timeout_seconds: int = 1800) -> dict[str, Any]:
    """Poll VideoFile records until all plan items exist in PLAOUT storage.

    Returns {"ready": True, "elapsed": int} on success,
    {"ready": False, "error": str, "missing": [...]} on failure.
    Falls back to direct VideoFile check — independent of Celery result expiry.
    """
    from planung.models import TagesPlan

    plan = TagesPlan.objects.filter(datum=plan_date_obj).first()
    if not plan:
        return {"ready": False, "error": "plan_missing"}

    numbers = [
        item.get("number")
        for item in plan.json_plan.get("items", [])
        if item.get("number")
    ]
    if not numbers:
        return {"ready": True, "elapsed": 0}

    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            from media_files.models import VideoFile

            ready_numbers = set(
                VideoFile.objects.filter(
                    number__in=numbers,
                    storage_location__storage_type="PLAYOUT",
                    is_available=True,
                    is_preview=False,
                ).values_list("number", flat=True)
            )
        except Exception:
            ready_numbers = set()

        missing = [n for n in numbers if n not in ready_numbers]
        if not missing:
            return {"ready": True, "elapsed": int(time.time() - start)}

        time.sleep(15)

    return {
        "ready": False,
        "error": "timeout",
        "elapsed": int(time.time() - start),
        "missing": missing,
    }


@shared_task(name="planung.tasks.anchor_render_chain", bind=True)
def anchor_render_chain(
    self,
    plan_date_str: str,
    force: bool = False,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Wait for copy_videos_for_plan → render → poll job.

    Runs entirely inside Celery so the user can close the browser tab.
    Frontend polls TaskResult via /api/planning/anchor/render/status/<task_id>/
    """
    from planung.models import TagesPlan
    from registration.models import Profile

    plan_date_obj = date.fromisoformat(plan_date_str)
    plan = TagesPlan.objects.filter(datum=plan_date_obj).first()
    if not plan:
        return {"status": "error", "error": "no_plan"}

    profile = Profile.objects.filter(user_id=user_id).first() if user_id else None
    if not profile:
        return {"status": "error", "error": "no_profile"}

    self.update_state(state="PROGRESS", meta={"phase": "waiting_for_copy"})
    copy_state = _wait_for_copy_in_chain(plan_date_obj, timeout_seconds=1800)
    if not copy_state["ready"]:
        return {"status": "error", "error": "copy_timeout", "details": copy_state}

    self.update_state(state="PROGRESS", meta={"phase": "rendering"})
    result = render_anchor_preview(
        plan_date=plan_date_obj,
        plan_items=plan.json_plan.get("items", []),
        profile=profile,
        force=force,
    )
    if result.error:
        return {
            "status": "error",
            "error": result.error,
            "configured": result.configured,
            "sent": result.sent,
            "license_id": result.license_id,
            "license_number": result.license_number,
            "output_name": result.output_name,
        }

    if not result.job_id or result.status in {"done", "error"}:
        return {
            "status": "done",
            "configured": result.configured,
            "sent": result.sent,
            "license_id": result.license_id,
            "license_number": result.license_number,
            "output_name": result.output_name,
            "job_id": result.job_id,
            "file": result.file,
            "error": result.error,
            "license_created": result.license_created,
            "video_exists": result.video_exists,
        }

    self.update_state(state="PROGRESS", meta={"phase": "polling", "job_id": result.job_id})
    final = poll_anchor_render_job(
        job_id=result.job_id,
        output_name=result.output_name,
        poll_interval=15,
        max_attempts=480,
    )
    return {
        "status": final.get("status", "done"),
        "configured": result.configured,
        "sent": result.sent,
        "license_id": result.license_id,
        "license_number": result.license_number,
        "output_name": result.output_name,
        "job_id": final.get("job_id", result.job_id),
        "file": final.get("file", ""),
        "error": final.get("error", ""),
        "license_created": result.license_created,
        "video_exists": result.video_exists,
    }
