"""Signal handlers for media files."""

import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import VideoFile, FileOperation


logger = logging.getLogger('django')


@receiver(post_save, sender=VideoFile)
def auto_link_to_license(sender, instance, created, **kwargs):
    """
    Automatically link VideoFile to License based on number.
    Also sync duration from video to license.
    
    This runs after VideoFile is saved and attempts to find
    a matching License by number. Only the newest VideoFile
    (by created_at or updated_at) will be linked to the License.
    """
    try:
        from licenses.models import License
        from django.db import transaction
        
        # Find license by number
        try:
            license = License.objects.get(number=instance.number)
        except License.DoesNotExist:
            logger.debug(f"No License found for VideoFile number {instance.number}")
            return
        
        # Find all VideoFiles with the same number
        # Find the newest VideoFile by updated_at (or created_at if updated_at is None)
        # Priority: updated_at > created_at
        newest_video = (
            VideoFile.objects
            .filter(number=instance.number)
            .order_by('-updated_at', '-created_at', '-id')
            .first()
        )
        
        if not newest_video:
            logger.debug(f"No VideoFile found for number {instance.number}")
            return
        
        # Check if license is already linked to a different VideoFile
        if license.video_file and license.video_file.id != newest_video.id:
            # newest_video is already the newest by order_by, so we should link it
            # Unlink old one and link new one
            current_video = license.video_file
            with transaction.atomic():
                VideoFile.objects.filter(pk=current_video.pk).update(license=None)
                VideoFile.objects.filter(pk=newest_video.pk).update(license=license)
            logger.info(f"Re-linked License #{license.number} from VideoFile {current_video.id} to newer VideoFile {newest_video.id}")
        elif not license.video_file:
            # License is not linked, link to newest video
            with transaction.atomic():
                VideoFile.objects.filter(pk=newest_video.pk).update(license=license)
            logger.info(f"Auto-linked VideoFile {newest_video.id} (number {instance.number}) to License #{license.number}")
        else:
            # License is already linked to the newest video, nothing to do
            logger.debug(f"License #{license.number} already linked to newest VideoFile {newest_video.id}")
        
        # Sync duration from newest video to license if video has duration
        if newest_video.duration:
            # Round to seconds (hh:mm:ss format)
            from datetime import timedelta
            video_duration = newest_video.duration
            # Round to nearest second
            rounded_duration = timedelta(seconds=int(video_duration.total_seconds()))
            
            # Only sync if difference is 1 second or more
            if license.duration:
                video_seconds = int(video_duration.total_seconds())
                license_seconds = int(license.duration.total_seconds())
                duration_diff = abs(video_seconds - license_seconds)
                
                if duration_diff >= 1:
                    license.duration = rounded_duration
                    license.save(update_fields=['duration'])
                    logger.info(f"Synced duration from VideoFile to License #{license.number}: {video_duration} → {rounded_duration}")
                else:
                    logger.debug(f"Duration difference < 1 second, no sync needed for License #{license.number}")
            else:
                # License has no duration, sync anyway
                license.duration = rounded_duration
                license.save(update_fields=['duration'])
                logger.info(f"Synced duration from VideoFile to License #{license.number}: {video_duration} → {rounded_duration}")
                
    except Exception as e:
        logger.error(f"Error in auto_link_to_license signal: {e}")


@receiver(post_save, sender='licenses.License')
def auto_link_license_to_video(sender, instance, created, **kwargs):
    """
    Automatically link License to VideoFile based on number.
    Also sync duration from video to license if video exists.
    
    This runs after License is saved and attempts to find
    a matching VideoFile by number. Only the newest VideoFile
    (by created_at or updated_at) will be linked to the License.
    """
    try:
        from licenses.models import License
        from django.db import transaction
        
        # Only process if this is a License instance
        if not isinstance(instance, License):
            return
            
        if instance.number:
            # Find all videos with same number
            # Find the newest VideoFile by updated_at (or created_at if updated_at is None)
            # Priority: updated_at > created_at
            newest_video = (
                VideoFile.objects
                .filter(number=instance.number)
                .order_by('-updated_at', '-created_at', '-id')
                .first()
            )
            
            if not newest_video:
                logger.debug(f"No VideoFile found for License number {instance.number}")
                return
            
            # Check if license is already linked to a different VideoFile
            if instance.video_file and instance.video_file.id != newest_video.id:
                # newest_video is already the newest by order_by, so we should link it
                # Unlink old one and link new one
                current_video = instance.video_file
                with transaction.atomic():
                    VideoFile.objects.filter(pk=current_video.pk).update(license=None)
                    VideoFile.objects.filter(pk=newest_video.pk).update(license=instance)
                logger.info(f"Re-linked License #{instance.number} from VideoFile {current_video.id} to newer VideoFile {newest_video.id}")
            elif not instance.video_file:
                # License is not linked, link to newest video
                with transaction.atomic():
                    VideoFile.objects.filter(pk=newest_video.pk).update(license=instance)
                logger.info(f"Auto-linked License {instance.number} to VideoFile {newest_video.id}")
            else:
                # License is already linked to the newest video, nothing to do
                logger.debug(f"License #{instance.number} already linked to newest VideoFile {newest_video.id}")
            
            # Sync duration from newest video to license if license has no duration
            if newest_video.duration and not instance.duration:
                from datetime import timedelta
                rounded_duration = timedelta(seconds=int(newest_video.duration.total_seconds()))
                instance.duration = rounded_duration
                instance.save(update_fields=['duration'])
                logger.info(f"Synced duration from VideoFile to License #{instance.number}: {rounded_duration}")
                
    except Exception as e:
        logger.error(f"Error in auto_link_license_to_video signal: {e}")


@receiver(pre_delete, sender=VideoFile)
def log_video_deletion(sender, instance, **kwargs):
    """
    Log VideoFile deletion to FileOperation.
    
    Note: This does NOT delete the physical file, only the database record.
    This signal runs before deletion, so we can still access the instance.
    
    Note: When deleting through admin, FileOperation records are deleted via raw SQL
    before this signal runs, so we skip logging in that case to avoid conflicts.
    """
    try:
        
        import os
        
        # Check if file exists on disk (handle read-only storage and missing paths gracefully)
        file_exists = False
        if instance.is_available:
            try:
                # Safely get full_path - may fail if storage_location is None or path is missing
                full_path = None
                try:
                    full_path = instance.full_path
                except (AttributeError, TypeError) as e:
                    logger.debug(f'Could not get full_path for video {instance.id} in signal: {e}')
                
                if full_path:
                    try:
                        file_exists = os.path.exists(full_path)
                    except (OSError, PermissionError, IOError):
                        # Storage might be read-only - that's OK
                        pass
            except Exception:
                # Any error - just skip file check
                pass
        
        # Create FileOperation record for deletion log
        # Note: This will be cascade deleted with VideoFile, but it's useful
        # for logging purposes before the actual deletion happens
        FileOperation.objects.create(
            video_file=instance,
            operation_type='DELETE',
            source_location=instance.storage_location,
            status='SUCCESS',
            details={
                'filename': instance.filename if instance.filename else '',
                'path': instance.file_path if instance.file_path else '',
                'file_existed_on_disk': file_exists,
                'note': 'Database record deleted' + (' (file was already removed from disk)' if not file_exists else '')
            }
        )
        logger.info(f"Logged deletion of VideoFile: {instance} (file existed: {file_exists})")
    except Exception as e:
        # Don't fail deletion if logging fails
        logger.error(f"Error logging VideoFile deletion: {e}")

