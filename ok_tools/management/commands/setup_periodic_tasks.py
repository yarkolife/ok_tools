"""
Management command to create periodic tasks in django-celery-beat.

This command migrates tasks from CELERY_BEAT_SCHEDULE to django-celery-beat
PeriodicTask model, making them visible and manageable in Django admin.
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.utils import timezone
from django.conf import settings
from celery.schedules import crontab
from ok_tools.settings import get_env
import json


def get_crontab_string_from_env(env_key, default):
    """Get crontab string directly from environment variable."""
    return get_env(env_key, default=default)


class Command(BaseCommand):
    help = 'Create periodic tasks in django-celery-beat from CELERY_BEAT_SCHEDULE'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing tasks if they already exist',
        )

    def handle(self, *args, **options):
        update = options['update']
        
        # Get schedule from settings
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        
        if not beat_schedule:
            self.stdout.write(self.style.WARNING('No CELERY_BEAT_SCHEDULE found in settings'))
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        # Map task names to their environment variable keys
        task_env_map = {
            'expire_rentals': ('CELERY_BEAT_EXPIRE_RENTALS', '*/30 * * * *'),
            'cleanup_old_backups': ('CELERY_BEAT_CLEANUP_OLD_BACKUPS', '0 2 * * *'),
            'run_backup_db': ('CELERY_BEAT_RUN_BACKUP_DB', '0 3 * * *'),
            'auto_scan': ('CELERY_BEAT_AUTO_SCAN', '0 */2 * * *'),
            'link_orphan_licenses': ('CELERY_BEAT_LINK_ORPHAN_LICENSES', '0 3 * * *'),
            'sync_licenses_videos': ('CELERY_BEAT_SYNC_LICENSES_VIDEOS', '0 4 * * *'),
            'update_video_metadata': ('CELERY_BEAT_UPDATE_VIDEO_METADATA', '0 1 1 * *'),
            'cleanup_old_file_operations': ('CELERY_BEAT_CLEANUP_OLD_FILE_OPERATIONS', '0 1 * * 0'),
            'cleanup_missing_files': ('CELERY_BEAT_CLEANUP_MISSING_FILES', '0 5 * * 0'),
            'cleanup_deleted_nextcloud_videos': ('CELERY_BEAT_CLEANUP_DELETED_NEXTCLOUD_VIDEOS', '0 2 * * *'),
        }

        for task_name, task_config in beat_schedule.items():
            task_path = task_config['task']
            schedule = task_config['schedule']
            kwargs = task_config.get('kwargs', {})
            
            # Parse crontab schedule - get original string from env if available
            if isinstance(schedule, crontab):
                # Get original crontab string from environment variable
                env_key, default = task_env_map.get(task_name, (None, None))
                if env_key:
                    crontab_string = get_crontab_string_from_env(env_key, default)
                    parts = crontab_string.split()
                    # Ensure we have exactly 5 parts
                    while len(parts) < 5:
                        parts.append('*')
                    
                    crontab_schedule, created = CrontabSchedule.objects.get_or_create(
                        minute=parts[0],
                        hour=parts[1],
                        day_of_month=parts[2],
                        month_of_year=parts[3],
                        day_of_week=parts[4],
                        timezone=settings.CELERY_TIMEZONE,
                    )
                else:
                    # Fallback: convert crontab object values
                    minute_str = str(schedule.minute) if schedule.minute else '*'
                    hour_str = str(schedule.hour) if schedule.hour else '*'
                    day_of_week_str = str(schedule.day_of_week) if schedule.day_of_week else '*'
                    day_of_month_str = str(schedule.day_of_month) if schedule.day_of_month else '*'
                    month_of_year_str = str(schedule.month_of_year) if schedule.month_of_year else '*'
                    
                    crontab_schedule, created = CrontabSchedule.objects.get_or_create(
                        minute=minute_str,
                        hour=hour_str,
                        day_of_week=day_of_week_str,
                        day_of_month=day_of_month_str,
                        month_of_year=month_of_year_str,
                        timezone=settings.CELERY_TIMEZONE,
                    )
                schedule_obj = crontab_schedule
            elif hasattr(schedule, 'every'):
                # It's an interval schedule
                interval, created = IntervalSchedule.objects.get_or_create(
                    every=schedule.every,
                    period=schedule.period,
                )
                schedule_obj = interval
            else:
                self.stdout.write(
                    self.style.WARNING(f'Unknown schedule type for {task_name}, skipping')
                )
                skipped_count += 1
                continue

            # Create or update periodic task
            task_kwargs = json.dumps(kwargs) if kwargs else '{}'
            
            if update:
                task, task_created = PeriodicTask.objects.update_or_create(
                    name=task_name,
                    defaults={
                        'task': task_path,
                        'crontab': schedule_obj if isinstance(schedule_obj, CrontabSchedule) else None,
                        'interval': schedule_obj if isinstance(schedule_obj, IntervalSchedule) else None,
                        'kwargs': task_kwargs,
                        'enabled': True,
                        'last_run_at': None,
                    }
                )
                if task_created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Created task: {task_name}'))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Updated task: {task_name}'))
            else:
                task, task_created = PeriodicTask.objects.get_or_create(
                    name=task_name,
                    defaults={
                        'task': task_path,
                        'crontab': schedule_obj if isinstance(schedule_obj, CrontabSchedule) else None,
                        'interval': schedule_obj if isinstance(schedule_obj, IntervalSchedule) else None,
                        'kwargs': task_kwargs,
                        'enabled': True,
                    }
                )
                if task_created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Created task: {task_name}'))
                else:
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(f'Task {task_name} already exists, skipping (use --update to update)'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}'
            )
        )

