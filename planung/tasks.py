"""Celery tasks for planning integrations."""

from celery import shared_task
from datetime import date
from planung.services.anchor_render_service import _placeholder_video
from planung.services.anchor_render_service import get_anchor_job_status
from planung.services.anchor_render_service import render_anchor_preview
from planung.services.playout_import_service import fetch_playout_missing_media
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


@shared_task(name="planung.tasks.poll_anchor_render_job", bind=True, queue="anchor_render")
def poll_anchor_render_job(
    self,
    job_id: str,
    output_name: str = "",
    poll_interval: int = 15,
    max_attempts: int = 480,
) -> dict[str, Any]:
    """Poll the external anchor renderer until the render job is finished."""
    return _poll_anchor_render_job(
        job_id=job_id,
        output_name=output_name,
        poll_interval=poll_interval,
        max_attempts=max_attempts,
        update_state=self.update_state,
    )


def _poll_anchor_render_job(
    *,
    job_id: str,
    output_name: str = "",
    poll_interval: int = 15,
    max_attempts: int = 480,
    update_state=None,
) -> dict[str, Any]:
    """Poll renderer status; optionally report progress to the current Celery task."""
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
        if update_state:
            update_state(state="PROGRESS", meta=payload)

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
    """Wait until the copy task finished or all plan videos exist in PLAYOUT.

    A successful copy task is enough to proceed even when it returned warnings;
    missing videos are allowed only when no source video exists in CUSTOM/ARCHIVE.
    When no source VideoFile exists anywhere and a configured placeholder rule or
    default placeholder resolves for a missing number, that number is considered
    ready without waiting for a copy task.
    """
    from celery.result import AsyncResult
    from media_files.models import VideoFile
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
    missing = list(numbers)
    ready: list[int] = []
    while time.time() - start < timeout_seconds:
        plan = TagesPlan.objects.filter(datum=plan_date_obj).first()
        if not plan:
            return {"ready": False, "error": "plan_missing"}

        ready_numbers = set(
            VideoFile.objects.filter(
                number__in=numbers,
                storage_location__storage_type="PLAYOUT",
                is_available=True,
                is_preview=False,
            ).values_list("number", flat=True)
        )

        missing = [n for n in numbers if n not in ready_numbers]
        ready = [n for n in numbers if n in ready_numbers]
        if not missing:
            return {"ready": True, "elapsed": int(time.time() - start), "missing": [], "ready_numbers": ready}

        if missing:
            _resolve_placeholder_missing(plan, missing, ready_numbers)
            missing = [n for n in numbers if n not in ready_numbers]
            ready = [n for n in numbers if n in ready_numbers]
            if not missing:
                return {"ready": True, "elapsed": int(time.time() - start), "missing": [], "ready_numbers": ready}

        if plan.copy_task_id:
            async_result = AsyncResult(plan.copy_task_id)
            if async_result.state == "SUCCESS":
                missing_with_source = _numbers_with_source_videos(missing)
                if missing_with_source:
                    return {
                        "ready": False,
                        "error": "copy_incomplete_after_success",
                        "elapsed": int(time.time() - start),
                        "missing": missing,
                        "ready_numbers": ready,
                        "copy_task_state": "SUCCESS",
                        "missing_with_source": missing_with_source,
                    }
                return {
                    "ready": True,
                    "elapsed": int(time.time() - start),
                    "missing": missing,
                    "ready_numbers": ready,
                    "copy_task_state": "SUCCESS",
                }
            if async_result.state == "FAILURE":
                return {
                    "ready": False,
                    "error": "copy_failed",
                    "elapsed": int(time.time() - start),
                    "missing": missing,
                    "ready_numbers": ready,
                    "copy_task_state": "FAILURE",
                }

        time.sleep(15)

    return {
        "ready": False,
        "error": "timeout",
        "elapsed": int(time.time() - start),
        "missing": missing,
        "ready_numbers": ready,
    }


def _numbers_with_source_videos(numbers: list[int]) -> list[int]:
    """Return missing plan numbers that still have source videos outside PLAYOUT."""
    if not numbers:
        return []
    from media_files.models import VideoFile

    return list(
        VideoFile.objects.filter(
            number__in=numbers,
            is_available=True,
            is_preview=False,
        )
        .exclude(storage_location__storage_type="PLAYOUT")
        .values_list("number", flat=True)
        .distinct()
    )


def _resolve_placeholder_missing(
    plan: Any,
    missing: list[int],
    ready_numbers: set[int],
) -> None:
    """Check if any missing plan numbers without source videos can use placeholders.

    For each missing number that has NO available non-preview VideoFile anywhere,
    resolve a placeholder via PlanungConfig rules (mirrors _check_plan_copy_state).
    Resolved numbers are added to ready_numbers in-place.
    Numbers with a source VideoFile outside PLAYOUT remain missing.
    """
    if not missing:
        return
    from licenses.models import License
    from media_files.models import VideoFile
    from planung.models import PlanungConfig

    source_set = set(
        VideoFile.objects.filter(
            number__in=missing,
            is_available=True,
            is_preview=False,
        ).values_list("number", flat=True)
    )
    missing_without_source = [n for n in missing if n not in source_set]
    if not missing_without_source:
        return

    config = PlanungConfig.get_config()
    has_rules = isinstance(config.anchor_placeholder_rules, list) and bool(config.anchor_placeholder_rules)
    has_default = bool(str(config.anchor_default_placeholder_video or "").strip())
    if not has_rules and not has_default:
        return

    items = plan.json_plan.get("items", [])
    items_by_number = {item.get("number"): item for item in items if item.get("number")}
    license_objs = License.objects.filter(number__in=missing_without_source).select_related("profile")
    licenses_by_number = {lic.number: lic for lic in license_objs}

    for n in missing_without_source:
        item = items_by_number.get(n)
        if not item:
            continue
        license_obj = licenses_by_number.get(n)
        placeholder = _placeholder_video(license_obj, item, config)
        if placeholder:
            ready_numbers.add(n)


@shared_task(name="planung.tasks.anchor_render_chain", bind=True, queue="anchor_render")
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
    from django.contrib.auth import get_user_model
    from planung.models import TagesPlan
    from registration.models import Profile

    plan_date_obj = date.fromisoformat(plan_date_str)
    plan = TagesPlan.objects.filter(datum=plan_date_obj).first()
    if not plan:
        return {"status": "error", "error": "no_plan"}

    profile = None
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
            profile = Profile.objects.filter(okuser=user).first()
        except User.DoesNotExist:
            pass
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
    final = _poll_anchor_render_job(
        job_id=result.job_id,
        output_name=result.output_name,
        poll_interval=15,
        max_attempts=480,
        update_state=self.update_state,
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
