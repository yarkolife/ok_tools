"""Celery tasks for the media_files app."""

from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task(name="media_files.tasks.run_auto_scan")
def run_auto_scan_task(**kwargs):
    """Run the auto_scan management command."""
    logger.info("Starting auto_scan task...")
    
    args = []
    if kwargs.get("delete_missing"):
        args.append("--delete-missing")
    if kwargs.get("force"):
        args.append("--force")
    if kwargs.get("skip_metadata"):
        args.append("--skip-metadata")
    if kwargs.get("strict_check"):
        args.append("--strict-check")
    if kwargs.get("calculate_checksums"):
        args.append("--calculate-checksums")
    if kwargs.get("storage_type"):
        args.extend(["--storage-type", kwargs["storage_type"]])
    
    call_command("auto_scan", *args)
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


@shared_task(name="media_files.tasks.run_cleanup_old_file_operations")
def run_cleanup_old_file_operations_task(**kwargs):
    """Run the cleanup_old_file_operations management command."""
    logger.info("Starting cleanup_old_file_operations task...")
    older_than_days = kwargs.get("older_than_days", 30)
    keep_failed = kwargs.get("keep_failed", True)
    
    args = []
    if older_than_days:
        args.extend(["--older-than-days", str(older_than_days)])
    if keep_failed:
        args.append("--keep-failed")
    
    call_command("cleanup_old_file_operations", *args)
    logger.info("Finished cleanup_old_file_operations task.")


@shared_task(name="media_files.tasks.run_cleanup_missing_files")
def run_cleanup_missing_files_task(**kwargs):
    """Run the cleanup_missing_files management command."""
    logger.info("Starting cleanup_missing_files task...")
    
    args = []
    if kwargs.get("all_storages"):
        args.append("--all-storages")
    elif kwargs.get("storage_id"):
        args.extend(["--storage-id", str(kwargs["storage_id"])])
    else:
        # Default: check all storages
        args.append("--all-storages")
    
    if kwargs.get("mark_unavailable"):
        args.append("--mark-unavailable")
    
    call_command("cleanup_missing_files", *args)
    logger.info("Finished cleanup_missing_files task.")
