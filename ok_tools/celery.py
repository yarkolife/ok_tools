import os
from celery import Celery
from celery.schedules import crontab # Import crontab for scheduling

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ok_tools.settings')

app = Celery('ok_tools')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# --- Celery Beat Schedule Configuration ---
# This defines periodic tasks that Celery Beat will schedule.
# The schedule is a dictionary where keys are task names and values are dictionaries
# containing 'task' (the name of the task function) and 'schedule' (how often to run it).

# Example: Schedule the 'run_backup_db_task' to run every day at 3:00 AM.
# The task name corresponds to the module path and function name: 'ok_tools.tasks.run_backup_db_task'
# The schedule uses crontab notation: minute, hour, day of month, month, day of week.
# crontab(minute=0, hour=3) means "at 3:00 AM every day".

# Example: Schedule the 'run_expire_room_rentals_task' to run every 30 minutes.
# crontab(minute='*/30') means "every 30 minutes" (at 00 and 30 minutes past every hour).

# Example: Schedule the 'cleanup_old_backups_task' to run every day at 2:00 AM.
# crontab(minute=0, hour=2) means "at 2:00 AM every day".

# The beat schedule is now configured in Django settings with the CELERY_BEAT_SCHEDULE setting
# and loaded automatically when the app starts via config_from_object with namespace='CELERY'.

# Optional: Update other Celery configurations if needed
# app.conf.update(
#     # ... other settings
# )