"""Celery tasks for planning integrations."""

from celery import shared_task
from planung.services.playout_import_service import fetch_playout_missing_media
from typing import Any
import logging


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
