"""Celery tasks for planning integrations."""

from celery import shared_task
from planung.services.playout_import_service import fetch_playout_missing_media
from planung.services.anchor_render_service import get_anchor_job_status
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
    poll_interval: int = 5,
    max_attempts: int = 180,
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
