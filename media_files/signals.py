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
    a matching License by number.
    """
    try:
        from licenses.models import License
        
        # Try to find or get existing license
        license = None
        if instance.license:
            license = instance.license
        else:
            try:
                license = License.objects.get(number=instance.number)
                # Use update to avoid triggering signal again
                VideoFile.objects.filter(pk=instance.pk).update(license=license)
                logger.info(f"Auto-linked VideoFile {instance.number} to License")
            except License.DoesNotExist:
                logger.debug(f"No License found for VideoFile number {instance.number}")
        
        # Sync duration from video to license if video has duration
        if license and instance.duration:
            # Round to seconds (hh:mm:ss format)
            from datetime import timedelta
            video_duration = instance.duration
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
    a matching VideoFile by number.
    """
    try:
        from licenses.models import License
        
        # Only process if this is a License instance
        if not isinstance(instance, License):
            return
            
        if created and instance.number:
            # Find video with same number
            video_file = VideoFile.objects.filter(number=instance.number).first()
            if video_file:
                # Link video to license
                video_file.license = instance
                video_file.save(update_fields=['license'])
                logger.info(f"Auto-linked License {instance.number} to VideoFile")
                
                # Sync duration from video to license if license has no duration
                if video_file.duration and not instance.duration:
                    from datetime import timedelta
                    rounded_duration = timedelta(seconds=int(video_file.duration.total_seconds()))
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
    """
    try:
        FileOperation.objects.create(
            video_file=instance,
            operation_type='DELETE',
            source_location=instance.storage_location,
            status='SUCCESS',
            details={'filename': instance.filename, 'path': instance.file_path}
        )
        logger.info(f"Logged deletion of VideoFile: {instance}")
    except Exception as e:
        logger.error(f"Error logging VideoFile deletion: {e}")

