# Periodic Tasks Management Guide

This guide explains how to check and manage periodic tasks (Celery Beat) in OK Tools.

## Overview

OK Tools uses `django-celery-beat` with `DatabaseScheduler` to manage periodic tasks. This means:
- Tasks are stored in the database
- Tasks can be managed via Django admin interface
- Tasks can be enabled/disabled without code changes
- Task schedules can be modified via admin interface

## Available Periodic Tasks

- **run_backup_db**: Database backup task (runs every 30 minutes by default)
- **expire_rentals**: Expire room rentals task
- **cleanup_old_backups**: Cleanup old backup files
- **auto_scan**: Automatic media file scanning
- **link_orphan_licenses**: Link orphan licenses to videos
- **sync_licenses_videos**: Sync licenses with videos
- **update_video_metadata**: Update video metadata

## Checking Task Status

### 1. Via Django Admin Interface

1. Login to Django admin: `http://your-server/admin/`
2. Navigate to **PERIODIC TASKS** → **Periodic tasks**
3. Find the task "run_backup_db"
4. Check:
   - **Enabled**: Should be checked (✓)
   - **Schedule**: Should show the cron schedule (e.g., `*/30 * * * *`)
   - **Last run at**: Shows when the task last ran
   - **Total run count**: Number of times the task has executed

### 2. Via Docker Logs

```bash
# Check Celery Beat logs
docker compose logs celery_beat --tail=100

# Follow logs in real-time
docker compose logs -f celery_beat

# Check Celery Worker logs (where tasks actually execute)
docker compose logs celery_worker --tail=100 | grep backup

# Check application logs
docker compose logs web --tail=50 | grep backup
```

### 3. Via Django Shell

```bash
# Enter Django shell
docker compose exec web python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask

# Check task status
task = PeriodicTask.objects.get(name='run_backup_db')
print(f"Task: {task.name}")
print(f"Enabled: {task.enabled}")
print(f"Schedule: {task.crontab}")
print(f"Last run: {task.last_run_at}")
print(f"Total runs: {task.total_run_count}")
```

## Running Tasks Manually

### 1. Via Django Admin

1. Go to **PERIODIC TASKS** → **Periodic tasks**
2. Select the task(s) you want to run (check the checkbox next to the task name)
3. From the "Action" dropdown at the top of the list, select **"Run selected periodic tasks now"**
4. Click **"Go"** button
5. The task will be executed asynchronously and you'll see a message with the Task ID

**Alternative method:**
- You can also see task execution history in the "Task Results" column
- Click on the "View Results" link to see all execution logs for that task

### 2. Via Django Shell

```bash
docker compose exec web python manage.py shell
```

```python
from ok_tools.tasks import run_backup_db_task

# Run task asynchronously (recommended)
result = run_backup_db_task.delay()
print(f"Task ID: {result.id}")
print(f"Task state: {result.state}")

# Or run synchronously (for testing)
run_backup_db_task()
```

### 3. Via Management Command

```bash
# Run the backup command directly
docker compose exec web python manage.py backup_db --compress

# Or call the task via shell
docker compose exec web python manage.py shell -c "from ok_tools.tasks import run_backup_db_task; run_backup_db_task()"
```

## Verifying Task Execution

### 1. Check Backup Files

```bash
# Check backup files in container
docker compose exec web ls -lah /app/backups/

# Or on host (if directory is mounted)
ls -lah ~/docker/ok_tools_production/data/backups/
```

### 2. Check Task Results in Database

**Via Django Admin:**
1. Go to **CELERY RESULTS** → **Task results**
2. Filter by task name: `ok_tools.tasks.run_backup_db_task`
3. View execution history, status, and results

**Via Django Shell:**
```bash
docker compose exec web python manage.py shell
```

```python
from django_celery_results.models import TaskResult
from ok_tools.tasks import run_backup_db_task

# Get task name
task_name = run_backup_db_task.name

# Check recent task results
results = TaskResult.objects.filter(task_name=task_name).order_by('-date_created')[:5]
for result in results:
    print(f"Date: {result.date_created}")
    print(f"Status: {result.status}")
    print(f"Result: {result.result}")
    if result.traceback:
        print(f"Traceback: {result.traceback}")
    print("---")
```

### 3. Check Application Logs

```bash
# Check logs for backup-related messages
docker compose logs web | grep -i "backup\|database backup"

# Check Celery worker logs
docker compose logs celery_worker | grep -i "backup\|database backup"
```

## Enabling/Disabling Tasks

### Via Django Admin

1. Go to **PERIODIC TASKS** → **Periodic tasks**
2. Select the task you want to enable/disable
3. Check/uncheck the **"Enabled"** checkbox
4. Click **"Save"**

### Via Django Shell

```bash
docker compose exec web python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask

# Disable task
task = PeriodicTask.objects.get(name='run_backup_db')
task.enabled = False
task.save()

# Enable task
task.enabled = True
task.save()
```

## Modifying Task Schedule

### Via Django Admin

1. Go to **PERIODIC TASKS** → **Periodic tasks**
2. Select the task "run_backup_db"
3. Modify the **Crontab schedule** or **Interval schedule**
4. Click **"Save"**

### Via Environment Variable

1. Edit `.env` file:
   ```bash
   CELERY_BEAT_RUN_BACKUP_DB=*/30 * * * *
   ```

2. Update the task in database:
   ```bash
   docker compose exec web python manage.py setup_periodic_tasks --update
   ```

3. Restart Celery Beat:
   ```bash
   docker compose restart celery_beat
   ```

## Troubleshooting

### Task Not Running

1. **Check if Celery Beat is running**:
   ```bash
   docker compose ps celery_beat
   docker compose logs celery_beat --tail=50
   ```

2. **Check if task is enabled**:
   ```bash
   docker compose exec web python manage.py shell -c "from django_celery_beat.models import PeriodicTask; print(PeriodicTask.objects.get(name='run_backup_db').enabled)"
   ```

3. **Check if Celery Worker is running**:
   ```bash
   docker compose ps celery_worker
   docker compose logs celery_worker --tail=50
   ```

4. **Check Redis connection**:
   ```bash
   docker compose exec redis redis-cli ping
   ```

### Task Failing

1. **Check task logs**:
   ```bash
   docker compose logs celery_worker | grep -i error
   ```

2. **Check application logs**:
   ```bash
   docker compose logs web | grep -i error
   ```

3. **Check task results**:
   ```bash
   docker compose exec web python manage.py shell
   ```
   ```python
   from django_celery_results.models import TaskResult
   from ok_tools.tasks import run_backup_db_task
   
   results = TaskResult.objects.filter(task_name=run_backup_db_task.name).order_by('-date_created')[:1]
   if results:
       print(results[0].traceback)
   ```

### Recreating Tasks

If tasks are missing from the database:

```bash
# Create tasks from CELERY_BEAT_SCHEDULE
docker compose exec web python manage.py setup_periodic_tasks

# Update existing tasks
docker compose exec web python manage.py setup_periodic_tasks --update
```

## Monitoring

### Check Task Execution Frequency

```bash
docker compose exec web python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask
from datetime import datetime, timedelta

task = PeriodicTask.objects.get(name='run_backup_db')
print(f"Last run: {task.last_run_at}")
print(f"Total runs: {task.total_run_count}")

# Check if task ran in last hour
if task.last_run_at:
    time_since_last_run = datetime.now(task.last_run_at.tzinfo) - task.last_run_at
    print(f"Time since last run: {time_since_last_run}")
    if time_since_last_run > timedelta(hours=1):
        print("WARNING: Task hasn't run in over an hour!")
```

### Check Celery Beat Schedule

```bash
docker compose exec web python manage.py shell
```

```python
from django_celery_beat.models import PeriodicTask, CrontabSchedule

task = PeriodicTask.objects.get(name='run_backup_db')
if task.crontab:
    print(f"Schedule: {task.crontab.minute} {task.crontab.hour} {task.crontab.day_of_month} {task.crontab.month_of_year} {task.crontab.day_of_week}")
    print(f"Timezone: {task.crontab.timezone}")
```

## Quick Reference

### Common Commands

```bash
# Check Celery Beat status
docker compose ps celery_beat

# View Celery Beat logs
docker compose logs celery_beat --tail=100

# Restart Celery Beat
docker compose restart celery_beat

# Run task manually
docker compose exec web python manage.py shell -c "from ok_tools.tasks import run_backup_db_task; run_backup_db_task()"

# Check backup files
ls -lah ~/docker/ok_tools_production/data/backups/

# Update periodic tasks
docker compose exec web python manage.py setup_periodic_tasks --update
```

### Django Admin URLs

- Periodic Tasks: `http://your-server/admin/django_celery_beat/periodictask/`
  - **Features**: Run tasks manually, view last run time, view task results link
- Crontab Schedules: `http://your-server/admin/django_celery_beat/crontabschedule/`
- Task Results: `http://your-server/admin/django_celery_results/taskresult/`
  - **Features**: Filter by task name, status, date; view execution logs and tracebacks

## Notes

- Tasks are stored in the `django_celery_beat_periodictask` table
- Task schedules are stored in `django_celery_beat_crontabschedule` or `django_celery_beat_intervalschedule` tables
- Task results are stored in `django_celery_results_taskresult` table
- **Task results are automatically saved** when tasks are executed via Celery Beat or manually via admin
- Changes to tasks in Django admin take effect immediately (no restart needed)
- Celery Beat reads the schedule from the database every minute
- Make sure Celery Beat and Celery Worker containers are running for tasks to execute
- **To view task execution logs**: Go to Periodic Tasks → select a task → click "View Results" link in the "Task Results" column
- **To run a task manually**: Select the task(s) in the list → choose "Run selected periodic tasks now" from Actions dropdown → click "Go"

