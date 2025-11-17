# Diagnostic Commands for Server Issues

## Viewing Django Logs

### If running in Docker:
```bash
# View recent logs from Django container
docker-compose logs -f --tail=100 web

# View logs with timestamps
docker-compose logs -f --tail=100 web | grep -E "ERROR|WARNING|Traceback"

# View only errors from last hour
docker-compose logs --since 1h web | grep -E "ERROR|Traceback"
```

### If running directly on server:
```bash
# View Django debug log (from settings.py: ok_tools-debug.log)
tail -f ok_tools-debug.log

# View last 100 lines with errors
tail -100 ok_tools-debug.log | grep -A 20 -E "ERROR|Traceback"

# View errors from last 10 minutes
tail -1000 ok_tools-debug.log | grep -A 20 "$(date -d '10 minutes ago' '+%Y-%m-%d %H:%M')" | grep -E "ERROR|Traceback"
```

## Viewing Specific Error Types

### VideoFile deletion errors:
```bash
# In Docker
docker-compose logs web | grep -A 30 "delete_queryset\|delete_model\|Error deleting VideoFile"

# Direct
grep -A 30 "delete_queryset\|delete_model\|Error deleting VideoFile" ok_tools-debug.log | tail -50
```

### Filter errors (IsPrimaryVersionFilter):
```bash
# In Docker
docker-compose logs web | grep -A 20 "IsPrimaryVersionFilter\|Error loading videos"

# Direct
grep -A 20 "IsPrimaryVersionFilter\|Error loading videos" ok_tools-debug.log | tail -50
```

## Real-time Monitoring

### Watch logs in real-time:
```bash
# Docker
docker-compose logs -f web

# Direct
tail -f ok_tools-debug.log
```

### Filter for specific patterns:
```bash
# Watch for deletion attempts
docker-compose logs -f web | grep --line-buffered "delete_queryset\|delete_model"

# Watch for errors only
docker-compose logs -f web | grep --line-buffered -E "ERROR|Traceback|Exception"
```

## Check Django Admin Errors

### View recent 500 errors:
```bash
# In Docker
docker-compose logs web | grep -B 5 -A 30 "500\|Internal Server Error"

# Direct
grep -B 5 -A 30 "500\|Internal Server Error" ok_tools-debug.log | tail -100
```

## Database Connection Issues

```bash
# Check if database is accessible
docker-compose exec web python manage.py dbshell

# Test database connection
docker-compose exec web python manage.py check --database default
```

## Check File System Access

```bash
# Test if storage paths are accessible
docker-compose exec web python manage.py shell
# Then in Python shell:
# from media_files.models import StorageLocation
# for storage in StorageLocation.objects.all():
#     print(f"{storage.name}: {storage.path} - exists: {os.path.exists(storage.path)}")
```

## Enable Debug Mode Temporarily

If you need more detailed error information, you can temporarily enable DEBUG mode:

1. Edit `.env` file or environment variables
2. Set `DEBUG=True`
3. Restart the application
4. **Remember to disable it after debugging!**

## View Gunicorn/UWSGI Logs

### If using Gunicorn:
```bash
# View Gunicorn access logs
docker-compose logs web | grep gunicorn

# Or if logs are in separate file
tail -f /var/log/gunicorn/access.log
tail -f /var/log/gunicorn/error.log
```

## Check System Resources

```bash
# Check disk space
df -h

# Check memory usage
free -h

# Check if storage mounts are active
mount | grep -E "nfs|cifs|/mnt"
```

## Common Issues and Solutions

### 500 Error on Delete:
1. Check logs for specific error message
2. Verify database connection
3. Check file permissions on storage paths
4. Verify VideoFile records exist and are valid

### Filter Errors:
1. Check if queryset is too large (may need pagination)
2. Verify database indexes exist
3. Check for None values in related fields

### Read-only Storage Errors:
- These should be handled gracefully now
- Check logs for "read-only" or "Permission denied" messages
- Verify storage mounts are correctly configured

