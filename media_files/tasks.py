"""Celery tasks for the media_files app."""

from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task(name="media_files.tasks.run_auto_scan")
def run_auto_scan_task():
    """Run the auto_scan management command."""
    logger.info("Starting auto_scan task...")
    call_command("auto_scan")
    logger.info("Finished auto_scan task.")


@shared_task(name="media_files.tasks.run_link_orphan_licenses")
def run_link_orphan_licenses_task():
    """Run the link_orphan_licenses management command."""
    logger.info("Starting link_orphan_licenses task...")
    call_command("link_orphan_licenses")
    logger.info("Finished link_orphan_licenses task.")


@shared_task(name="media_files.tasks.run_sync_licenses_videos")
def run_sync_licenses_videos_task():
    """Run the sync_licenses_videos management command."""
    logger.info("Starting sync_licenses_videos task...")
    call_command("sync_licenses_videos")
    logger.info("Finished sync_licenses_videos task.")


@shared_task(name="media_files.tasks.run_update_video_metadata")
def run_update_video_metadata_task(**kwargs):
    """Run the update_video_metadata management command."""
    logger.info(f"Starting update_video_metadata task with args: {kwargs}")
    args = ["--all"]
    if kwargs.get("missing_only"):
        args.append("--missing-only")
    call_command("update_video_metadata", *args)
    logger.info("Finished update_video_metadata task.")
