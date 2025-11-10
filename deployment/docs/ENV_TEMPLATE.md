# Environment Variables Template

> **Version:** 3.0  
> **Last Updated:** 2025-11-10  
> **Status:** Current

This document provides a complete reference for all environment variables used in OK Tools production environment. Use this as a template when creating your `.env` file.

## Quick Start

1. Copy one of the template files from `deployment/configs/`:
   ```bash
   cp deployment/configs/ok-bayern.env.template .env
   ```

2. Edit `.env` and replace all `__REPLACE_ME__` placeholders with your actual values

3. See sections below for detailed descriptions of each variable

---

## Table of Contents

- [Database Configuration](#database-configuration)
- [Django Core Settings](#django-core-settings)
- [Organization Configuration](#organization-configuration)
- [Superuser Configuration](#superuser-configuration)
- [Application Configuration](#application-configuration)
- [Gunicorn Configuration](#gunicorn-configuration)
- [Redis Configuration](#redis-configuration)
- [SSL/HTTPS Configuration](#sslhttps-configuration)
- [Logging Configuration](#logging-configuration)
- [Backup Configuration](#backup-configuration)
- [Volume Mounts Configuration](#volume-mounts-configuration)
- [Django Extended Configuration](#django-extended-configuration)
- [Email Configuration](#email-configuration)
- [Organization Extended Configuration](#organization-extended-configuration)
- [Bootstrap Configuration](#bootstrap-configuration)
- [API Configuration](#api-configuration)
- [Security Configuration](#security-configuration)
- [Video Configuration](#video-configuration)
- [I18n Configuration](#i18n-configuration)
- [Static Files Configuration](#static-files-configuration)
- [Cache Configuration](#cache-configuration)
- [Celery Configuration](#celery-configuration)
- [Celery Beat Schedules](#celery-beat-schedules)

---

## Database Configuration

### POSTGRES_DB
- **Description:** PostgreSQL database name
- **Type:** String
- **Required:** Yes
- **Default:** `oktools`
- **Example:** `POSTGRES_DB=oktools`
- **Notes:** Database will be created automatically if it doesn't exist

### POSTGRES_USER
- **Description:** PostgreSQL database user name
- **Type:** String
- **Required:** Yes
- **Default:** `oktools`
- **Example:** `POSTGRES_USER=oktools`
- **Notes:** User will be created automatically with necessary permissions

### POSTGRES_PASSWORD
- **Description:** PostgreSQL database user password
- **Type:** String
- **Required:** Yes
- **Default:** None (must be set)
- **Example:** `POSTGRES_PASSWORD=your-secure-password-here`
- **Notes:** 
  - Use a strong password in production
  - Must match password in `DATABASE_URL`

### POSTGRES_HOST
- **Description:** PostgreSQL database host
- **Type:** String
- **Required:** No
- **Default:** `db` (Docker service name)
- **Example:** `POSTGRES_HOST=db`
- **Notes:** For Docker Compose, use service name `db`

### POSTGRES_PORT
- **Description:** PostgreSQL database port
- **Type:** Integer
- **Required:** No
- **Default:** `5432`
- **Example:** `POSTGRES_PORT=5432`

### DATABASE_URL
- **Description:** Full PostgreSQL connection URL
- **Type:** String (URL)
- **Required:** No (auto-generated if not set)
- **Default:** Auto-generated from POSTGRES_* variables
- **Example:** `DATABASE_URL=postgresql://oktools:password@db:5432/oktools`
- **Notes:** Format: `postgresql://user:password@host:port/database`

---

## Django Core Settings

### DJANGO_SETTINGS_MODULE
- **Description:** Django settings module path
- **Type:** String
- **Required:** No
- **Default:** `ok_tools.settings`
- **Example:** `DJANGO_SETTINGS_MODULE=ok_tools.settings`
- **Notes:** Usually doesn't need to be changed

### DJANGO_SECRET_KEY
- **Description:** Secret key for Django cryptographic signing and sessions
- **Type:** String
- **Required:** Yes
- **Default:** None (must be set)
- **Example:** `DJANGO_SECRET_KEY=django-insecure-...`
- **Notes:** 
  - Generate with: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
  - Keep this value secret and secure
  - Must be unique for each environment
  - Never commit to version control

### DEBUG
- **Description:** Enable Django debug mode
- **Type:** Boolean (`True`/`False`)
- **Required:** No
- **Default:** `False`
- **Example:** `DEBUG=False`
- **Notes:**
  - **Always set to `False` in production**
  - Enables detailed error pages and debug toolbar when `True`
  - Has significant performance impact

### ALLOWED_HOSTS
- **Description:** Comma-separated list of allowed hostnames/domains/IPs
- **Type:** String (comma-separated)
- **Required:** Yes (for production)
- **Default:** `localhost`
- **Example:** `ALLOWED_HOSTS=okmq.de,www.okmq.de,192.168.1.100,localhost`
- **Notes:**
  - Include all domains and IPs that will access the application
  - Required for Django security (prevents Host header attacks)
  - Supports both comma and space separation

---

## Organization Configuration

### ORG_NAME
- **Description:** Full name of the organization
- **Type:** String
- **Required:** No
- **Default:** `Open Channel Merseburg-Querfurt e.V.`
- **Example:** `ORG_NAME=Bayern Community Media Organization e.V.`
- **Notes:** Displayed in templates and admin interface

### ORG_SHORT_NAME
- **Description:** Short name/abbreviation of the organization
- **Type:** String
- **Required:** No
- **Default:** `OK Merseburg`
- **Example:** `ORG_SHORT_NAME=Bayern CMO`
- **Notes:** Used in compact displays and headers

### ORG_WEBSITE
- **Description:** Organization website URL
- **Type:** String (URL)
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_WEBSITE=https://okmq.de`
- **Notes:** 
  - If empty, "Website" menu item will be hidden
  - Should include protocol (`http://` or `https://`)

### ORG_EMAIL
- **Description:** Organization contact email address
- **Type:** String (email)
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_EMAIL=info@okmq.de`

### ORG_ADDRESS
- **Description:** Organization physical address
- **Type:** String (multiline supported with `\n`)
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_ADDRESS=Street 123\nCity, Postal Code`
- **Notes:** Use `\n` for line breaks

### ORG_PHONE
- **Description:** Organization phone number
- **Type:** String
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_PHONE=+49 123 456789`

### ORG_FAX
- **Description:** Organization fax number
- **Type:** String
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_FAX=+49 123 456790`

### ORG_DESCRIPTION
- **Description:** Organization description/description
- **Type:** String
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_DESCRIPTION=Welcome to our Community Media Organization!`

### ORG_OPENING_HOURS
- **Description:** Organization opening hours
- **Type:** String (multiline supported with `\n`)
- **Required:** No
- **Default:** Empty string
- **Example:** `ORG_OPENING_HOURS=Mon: 13:00 – 16:00\nTue – Thu: 10:00 – 18:00`
- **Notes:** Use `\n` for line breaks

### STATE_MEDIA_INSTITUTION
- **Description:** State media institution code
- **Type:** String
- **Required:** No
- **Default:** `MSA`
- **Example:** `STATE_MEDIA_INSTITUTION=MSA`
- **Notes:** Used for regulatory compliance

---

## Superuser Configuration

These variables are used during initial setup to create the Django superuser account.

### SUPERUSER_USERNAME
- **Description:** Django superuser username
- **Type:** String
- **Required:** No
- **Default:** `admin`
- **Example:** `SUPERUSER_USERNAME=admin`
- **Notes:** Used only during initial setup

### SUPERUSER_EMAIL
- **Description:** Django superuser email address
- **Type:** String (email)
- **Required:** No
- **Default:** None
- **Example:** `SUPERUSER_EMAIL=admin@okmq.de`

### SUPERUSER_PASSWORD
- **Description:** Django superuser password
- **Type:** String
- **Required:** No
- **Default:** None
- **Example:** `SUPERUSER_PASSWORD=your-secure-password`
- **Notes:** 
  - Use a strong password
  - Can be changed later via Django admin

---

## Application Configuration

### PYTHONPATH
- **Description:** Python module search path
- **Type:** String (path)
- **Required:** No
- **Default:** `/app`
- **Example:** `PYTHONPATH=/app`
- **Notes:** Usually doesn't need to be changed

### PYTHONUNBUFFERED
- **Description:** Disable Python output buffering
- **Type:** Integer (`0` or `1`)
- **Required:** No
- **Default:** `1`
- **Example:** `PYTHONUNBUFFERED=1`
- **Notes:** Ensures logs appear immediately

---

## Gunicorn Configuration

### GUNICORN_WORKERS
- **Description:** Number of Gunicorn worker processes
- **Type:** Integer
- **Required:** No
- **Default:** `4`
- **Example:** `GUNICORN_WORKERS=4`
- **Notes:** 
  - Recommended: `(2 × CPU cores) + 1`
  - More workers = more memory usage

### GUNICORN_THREADS
- **Description:** Number of threads per worker
- **Type:** Integer
- **Required:** No
- **Default:** `2`
- **Example:** `GUNICORN_THREADS=2`
- **Notes:** Useful for I/O-bound applications

### GUNICORN_TIMEOUT
- **Description:** Worker timeout in seconds
- **Type:** Integer
- **Required:** No
- **Default:** `120`
- **Example:** `GUNICORN_TIMEOUT=120`
- **Notes:** Workers killed if request takes longer

### GUNICORN_MAX_REQUESTS
- **Description:** Maximum requests per worker before restart
- **Type:** Integer
- **Required:** No
- **Default:** `1000`
- **Example:** `GUNICORN_MAX_REQUESTS=1000`
- **Notes:** Helps prevent memory leaks

### GUNICORN_MAX_REQUESTS_JITTER
- **Description:** Random jitter for max requests
- **Type:** Integer
- **Required:** No
- **Default:** `100`
- **Example:** `GUNICORN_MAX_REQUESTS_JITTER=100`
- **Notes:** Prevents all workers restarting simultaneously

---

## Redis Configuration

### REDIS_URL
- **Description:** Redis connection URL
- **Type:** String (URL)
- **Required:** No
- **Default:** `redis://redis:6379/0`
- **Example:** `REDIS_URL=redis://redis:6379/0`
- **Notes:** 
  - Format: `redis://host:port/db`
  - For Docker Compose, use service name `redis`
  - Used for caching and Celery broker

---

## SSL/HTTPS Configuration

### SSL_ENABLED
- **Description:** Enable SSL/HTTPS support
- **Type:** Boolean (`true`/`false`)
- **Required:** No
- **Default:** `false`
- **Example:** `SSL_ENABLED=true`
- **Notes:** 
  - Requires `DOMAIN_NAME` to be set
  - Enables Let's Encrypt certificate generation

### SSL_CERT_PATH
- **Description:** Path to SSL certificate file
- **Type:** String (path)
- **Required:** No
- **Default:** `/etc/nginx/ssl/cert.pem`
- **Example:** `SSL_CERT_PATH=/etc/nginx/ssl/cert.pem`
- **Notes:** Used when SSL_ENABLED=true

### SSL_KEY_PATH
- **Description:** Path to SSL private key file
- **Type:** String (path)
- **Required:** No
- **Default:** `/etc/nginx/ssl/key.pem`
- **Example:** `SSL_KEY_PATH=/etc/nginx/ssl/key.pem`
- **Notes:** Used when SSL_ENABLED=true

---

## Logging Configuration

### LOG_LEVEL
- **Description:** Application log level
- **Type:** String
- **Required:** No
- **Default:** `info`
- **Example:** `LOG_LEVEL=info`
- **Valid values:** `debug`, `info`, `warning`, `error`, `critical`

### LOGGING_FILE
- **Description:** Path to application log file
- **Type:** String (path)
- **Required:** No
- **Default:** `/app/logs/oktools.log`
- **Example:** `LOGGING_FILE=/app/logs/oktools.log`
- **Notes:** Log file location inside container

---

## Backup Configuration

### BACKUP_DIR
- **Description:** Directory for database backups
- **Type:** String (path)
- **Required:** No
- **Default:** `/app/backups`
- **Example:** `BACKUP_DIR=/app/backups`
- **Notes:** 
  - Path inside container
  - Mounted to host directory `./backups` in docker-compose.yml

---

## Volume Mounts Configuration

These variables control Docker volume mounts via `docker-compose.override.yml`. See [VOLUME_MOUNTS.md](./VOLUME_MOUNTS.md) for detailed instructions.

### NAS_MOUNT_PATH
- **Description:** Host path to NAS storage mount point
- **Type:** String (path)
- **Required:** No
- **Default:** Empty (not mounted)
- **Example:** `NAS_MOUNT_PATH=/mnt/nas`
- **Notes:** 
  - Leave empty if not using NAS
  - Must exist on host system
  - Mounted to `/mnt/nas` inside containers

### NAS_MOUNT_MODE
- **Description:** Mount mode for NAS storage
- **Type:** String (`ro` or `rw`)
- **Required:** No
- **Default:** `ro` (read-only)
- **Example:** `NAS_MOUNT_MODE=ro`
- **Notes:** 
  - `ro` = read-only (recommended for most cases)
  - `rw` = read-write

### CUSTOM_MOUNT_N_PATH
- **Description:** Host path for custom mount #N (N = 1-10)
- **Type:** String (path)
- **Required:** No
- **Default:** Empty
- **Example:** `CUSTOM_MOUNT_1_PATH=/mnt/storage1`
- **Notes:** For additional storage mounts beyond NAS

### CUSTOM_MOUNT_N_CONTAINER_PATH
- **Description:** Container path for custom mount #N
- **Type:** String (path)
- **Required:** No (required if CUSTOM_MOUNT_N_PATH is set)
- **Default:** Empty
- **Example:** `CUSTOM_MOUNT_1_CONTAINER_PATH=/mnt/storage1`

### CUSTOM_MOUNT_N_MODE
- **Description:** Mount mode for custom mount #N
- **Type:** String (`ro` or `rw`)
- **Required:** No
- **Default:** `ro`
- **Example:** `CUSTOM_MOUNT_1_MODE=ro`

### CUSTOM_MOUNT_N_SERVICES
- **Description:** Comma-separated list of services to mount to
- **Type:** String (comma-separated)
- **Required:** No
- **Default:** `web,celery_worker`
- **Example:** `CUSTOM_MOUNT_1_SERVICES=web,celery_worker`
- **Valid services:** `web`, `celery_worker`, `celery_beat`

---

## Django Extended Configuration

### DJANGO_LOG_LEVEL
- **Description:** Django logging level
- **Type:** String
- **Required:** No
- **Default:** `INFO`
- **Example:** `DJANGO_LOG_LEVEL=INFO`
- **Valid values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### DJANGO_LANGUAGE
- **Description:** Django language code
- **Type:** String (locale code)
- **Required:** No
- **Default:** `de-de`
- **Example:** `DJANGO_LANGUAGE=de-de`
- **Notes:** Format: `language-country` (e.g., `de-de`, `en-us`)

### DJANGO_TIMEZONE
- **Description:** Django timezone
- **Type:** String (timezone name)
- **Required:** No
- **Default:** `Europe/Berlin`
- **Example:** `DJANGO_TIMEZONE=Europe/Berlin`
- **Notes:** Use IANA timezone database names

### DJANGO_STATIC_ROOT
- **Description:** Directory for collected static files
- **Type:** String (path)
- **Required:** No
- **Default:** `/app/staticfiles/`
- **Example:** `DJANGO_STATIC_ROOT=/app/staticfiles/`
- **Notes:** Path inside container

### DJANGO_MEDIA_ROOT
- **Description:** Directory for user-uploaded media files
- **Type:** String (path)
- **Required:** No
- **Default:** `/app/media/`
- **Example:** `DJANGO_MEDIA_ROOT=/app/media/`
- **Notes:** Path inside container

### DJANGO_USE_SECURE_SETTINGS
- **Description:** Enable secure Django settings (HTTPS cookies, etc.)
- **Type:** Boolean (`True`/`False`)
- **Required:** No
- **Default:** `True`
- **Example:** `DJANGO_USE_SECURE_SETTINGS=True`
- **Notes:** Set to `True` when using HTTPS

---

## Email Configuration

### EMAIL_HOST
- **Description:** SMTP server hostname
- **Type:** String
- **Required:** No
- **Default:** Empty
- **Example:** `EMAIL_HOST=smtp.gmail.com`
- **Notes:** Your email provider's SMTP server

### EMAIL_PORT
- **Description:** SMTP server port
- **Type:** Integer
- **Required:** No
- **Default:** `587` (TLS) or `465` (SSL)
- **Example:** `EMAIL_PORT=587`
- **Notes:** 
  - `587` for TLS
  - `465` for SSL

### EMAIL_USE_TLS
- **Description:** Use TLS encryption for SMTP
- **Type:** Boolean (`True`/`False`)
- **Required:** No
- **Default:** `True`
- **Example:** `EMAIL_USE_TLS=True`
- **Notes:** Use with port 587

### EMAIL_HOST_USER
- **Description:** SMTP authentication username
- **Type:** String (email)
- **Required:** No
- **Default:** Empty
- **Example:** `EMAIL_HOST_USER=noreply@okmq.de`
- **Notes:** Usually your email address

### EMAIL_HOST_PASSWORD
- **Description:** SMTP authentication password
- **Type:** String
- **Required:** No
- **Default:** Empty
- **Example:** `EMAIL_HOST_PASSWORD=your-app-password`
- **Notes:** 
  - Use app-specific password for Gmail
  - Keep secure, never commit to git

### DEFAULT_FROM_EMAIL
- **Description:** Default sender email address
- **Type:** String (email)
- **Required:** No
- **Default:** Empty
- **Example:** `DEFAULT_FROM_EMAIL=noreply@okmq.de`
- **Notes:** Shown as sender in outgoing emails

### MAIL_DEV_SETTINGS
- **Description:** Use development email backend (console output)
- **Type:** Boolean (`True`/`False`)
- **Required:** No
- **Default:** `False`
- **Example:** `MAIL_DEV_SETTINGS=False`
- **Notes:** 
  - Set to `True` for development/testing
  - Emails printed to console instead of sent

---

## Organization Extended Configuration

### ORG_ORGANIZATION_OWNER
- **Description:** Organization owner identifier
- **Type:** String
- **Required:** No
- **Default:** `OKMQ`
- **Example:** `ORG_ORGANIZATION_OWNER=OK Bayern`
- **Notes:** Used for equipment ownership tracking

### ORG_BROADCAST_START
- **Description:** Daily broadcast start time
- **Type:** String (time format `HH:MM`)
- **Required:** No
- **Default:** `06:00`
- **Example:** `ORG_BROADCAST_START=18:00`
- **Notes:** Used for planning and scheduling

### ORG_BROADCAST_END
- **Description:** Daily broadcast end time
- **Type:** String (time format `HH:MM`)
- **Required:** No
- **Default:** `23:00`
- **Example:** `ORG_BROADCAST_END=19:45`
- **Notes:** Used for planning and scheduling

### ORG_PEERTUBE_CHANNEL
- **Description:** Peertube channel URL or identifier
- **Type:** String (URL)
- **Required:** No
- **Default:** Empty
- **Example:** `ORG_PEERTUBE_CHANNEL=https://peertube.example.com/c/okmq`
- **Notes:** For video platform integration

---

## Bootstrap Configuration

### BOOTSTRAP_VERSION
- **Description:** Bootstrap CSS framework version
- **Type:** String (version)
- **Required:** No
- **Default:** `5.3.3`
- **Example:** `BOOTSTRAP_VERSION=5.3.3`
- **Notes:** Used for frontend styling

### BOOTSTRAP_ICONS_VERSION
- **Description:** Bootstrap Icons version
- **Type:** String (version)
- **Required:** No
- **Default:** `1.11.0`
- **Example:** `BOOTSTRAP_ICONS_VERSION=1.11.0`
- **Notes:** Used for icon library

---

## API Configuration

### API_PAGE_SIZE
- **Description:** Default page size for API pagination
- **Type:** Integer
- **Required:** No
- **Default:** `20`
- **Example:** `API_PAGE_SIZE=20`
- **Notes:** Number of items per page in API responses

### API_ANON_RATE_LIMIT
- **Description:** API rate limit for anonymous users
- **Type:** String (rate limit format)
- **Required:** No
- **Default:** `100/hour`
- **Example:** `API_ANON_RATE_LIMIT=100/hour`
- **Notes:** Format: `number/period` (e.g., `100/hour`, `1000/day`)

### API_USER_RATE_LIMIT
- **Description:** API rate limit for authenticated users
- **Type:** String (rate limit format)
- **Required:** No
- **Default:** `1000/hour`
- **Example:** `API_USER_RATE_LIMIT=1000/hour`
- **Notes:** Format: `number/period`

---

## Security Configuration

### SECURITY_SESSION_TIMEOUT
- **Description:** Session timeout in seconds
- **Type:** Integer
- **Required:** No
- **Default:** `1200` (20 minutes)
- **Example:** `SECURITY_SESSION_TIMEOUT=1200`
- **Notes:** Users logged out after inactivity

### SECURITY_PASSWORD_MIN_LENGTH
- **Description:** Minimum password length
- **Type:** Integer
- **Required:** No
- **Default:** `8`
- **Example:** `SECURITY_PASSWORD_MIN_LENGTH=8`
- **Notes:** Enforced during password creation/change

### SECURITY_CSRF_COOKIE_AGE
- **Description:** CSRF cookie age in seconds
- **Type:** Integer
- **Required:** No
- **Default:** `31449600` (1 year)
- **Example:** `SECURITY_CSRF_COOKIE_AGE=31449600`
- **Notes:** How long CSRF tokens remain valid

---

## Video Configuration

### VIDEO_SUPPORTED_FORMATS
- **Description:** Comma-separated list of supported video formats
- **Type:** String (comma-separated)
- **Required:** No
- **Default:** `mp4,mov,mpeg,mpg`
- **Example:** `VIDEO_SUPPORTED_FORMATS=mp4,mov,mpeg,mpg`
- **Notes:** File extensions allowed for video uploads

### VIDEO_SCREEN_BOARD_DURATION
- **Description:** Screen board display duration in seconds
- **Type:** Integer
- **Required:** No
- **Default:** `20`
- **Example:** `VIDEO_SCREEN_BOARD_DURATION=20`
- **Notes:** Used for video planning

---

## I18n Configuration

### I18N_DEFAULT_LANGUAGE
- **Description:** Default application language code
- **Type:** String (language code)
- **Required:** No
- **Default:** `de`
- **Example:** `I18N_DEFAULT_LANGUAGE=de`
- **Notes:** Two-letter ISO 639-1 code

### I18N_SUPPORTED_LANGUAGES
- **Description:** Comma-separated list of supported languages
- **Type:** String (comma-separated)
- **Required:** No
- **Default:** `de,en`
- **Example:** `I18N_SUPPORTED_LANGUAGES=de,en`
- **Notes:** Languages available in the application

### I18N_LOCALE_PATHS
- **Description:** Path to locale/translation files
- **Type:** String (path)
- **Required:** No
- **Default:** `ok_tools/locale`
- **Example:** `I18N_LOCALE_PATHS=ok_tools/locale`
- **Notes:** Relative to project root

### I18N_PHONE_REGION
- **Description:** Default phone number region code
- **Type:** String (country code)
- **Required:** No
- **Default:** `DE`
- **Example:** `I18N_PHONE_REGION=DE`
- **Notes:** Two-letter ISO 3166-1 alpha-2 code

### I18N_DATE_FORMAT
- **Description:** Default date format string
- **Type:** String (format)
- **Required:** No
- **Default:** `%d.%m.%Y`
- **Example:** `I18N_DATE_FORMAT=%d.%m.%Y`
- **Notes:** Python strftime format (e.g., `%d.%m.%Y` = `31.12.2024`)

---

## Static Files Configuration

### STATIC_STORAGE_BACKEND
- **Description:** Django static files storage backend class
- **Type:** String (Python class path)
- **Required:** No
- **Default:** `whitenoise.storage.CompressedManifestStaticFilesStorage`
- **Example:** `STATIC_STORAGE_BACKEND=whitenoise.storage.CompressedManifestStaticFilesStorage`
- **Notes:** Used for static file serving and compression

### STATIC_URL_PREFIX
- **Description:** URL prefix for static files
- **Type:** String (URL path)
- **Required:** No
- **Default:** `static/`
- **Example:** `STATIC_URL_PREFIX=static/`
- **Notes:** URL path where static files are served

---

## Cache Configuration

### CACHE_TIMEOUT
- **Description:** Default cache timeout in seconds
- **Type:** Integer
- **Required:** No
- **Default:** `300` (5 minutes)
- **Example:** `CACHE_TIMEOUT=300`
- **Notes:** How long cached data remains valid

---

## Celery Configuration

### CELERY_BROKER_URL
- **Description:** Celery message broker URL
- **Type:** String (URL)
- **Required:** No
- **Default:** `redis://redis:6379/0`
- **Example:** `CELERY_BROKER_URL=redis://redis:6379/0`
- **Notes:** 
  - Format: `redis://host:port/db`
  - For Docker Compose, use service name `redis`
  - Used for task queue

### CELERY_RESULT_BACKEND
- **Description:** Celery result backend
- **Type:** String
- **Required:** No
- **Default:** `django-db`
- **Example:** `CELERY_RESULT_BACKEND=django-db`
- **Notes:** 
  - `django-db` = store results in Django database (recommended)
  - `redis://redis:6379/0` = store in Redis
  - Results visible in Django admin when using `django-db`

---

## Celery Beat Schedules

These variables define cron schedules for periodic tasks. Format: `minute hour day month weekday`

### CELERY_BEAT_EXPIRE_RENTALS
- **Description:** Schedule for expiring room rentals
- **Type:** String (cron format)
- **Required:** No
- **Default:** `*/30 * * * *` (every 30 minutes)
- **Example:** `CELERY_BEAT_EXPIRE_RENTALS=*/30 * * * *`
- **Notes:** Checks and expires room rentals

### CELERY_BEAT_CLEANUP_BACKUPS
- **Description:** Schedule for cleaning up old backups
- **Type:** String (cron format)
- **Required:** No
- **Default:** `0 2 * * *` (daily at 2:00 AM)
- **Example:** `CELERY_BEAT_CLEANUP_BACKUPS=0 2 * * *`
- **Notes:** Removes old backup files

### CELERY_BEAT_BACKUP_DB
- **Description:** Schedule for database backups
- **Type:** String (cron format)
- **Required:** No
- **Default:** `0 3 * * *` (daily at 3:00 AM)
- **Example:** `CELERY_BEAT_BACKUP_DB=0 3 * * *`
- **Notes:** Creates PostgreSQL database backup

### CELERY_BEAT_AUTO_SCAN
- **Description:** Schedule for automatic video storage scanning
- **Type:** String (cron format)
- **Required:** No
- **Default:** `0 */2 * * *` (every 2 hours)
- **Example:** `CELERY_BEAT_AUTO_SCAN=0 */2 * * *`
- **Notes:** Scans NAS/storage for new video files

### CELERY_BEAT_LINK_LICENSES
- **Description:** Schedule for linking licenses
- **Type:** String (cron format)
- **Required:** No
- **Default:** `0 4 * * *` (daily at 4:00 AM)
- **Example:** `CELERY_BEAT_LINK_LICENSES=0 4 * * *`

### CELERY_BEAT_SYNC_VIDEOS
- **Description:** Schedule for video synchronization
- **Type:** String (cron format)
- **Required:** No
- **Default:** `0 5 * * *` (daily at 5:00 AM)
- **Example:** `CELERY_BEAT_SYNC_VIDEOS=0 5 * * *`

### CELERY_BEAT_UPDATE_METADATA
- **Description:** Schedule for updating video metadata
- **Type:** String (cron format)
- **Required:** No
- **Default:** `0 1 1 * *` (monthly on 1st at 1:00 AM)
- **Example:** `CELERY_BEAT_UPDATE_METADATA=0 1 1 * *`

---

## Cron Format Reference

Cron format: `minute hour day month weekday`

- **minute:** 0-59
- **hour:** 0-23
- **day:** 1-31
- **month:** 1-12
- **weekday:** 0-7 (0 and 7 = Sunday)

**Examples:**
- `*/30 * * * *` = every 30 minutes
- `0 */2 * * *` = every 2 hours
- `0 3 * * *` = daily at 3:00 AM
- `0 1 1 * *` = monthly on 1st at 1:00 AM
- `0 0 * * 0` = weekly on Sunday at midnight

---

## Additional Notes

### Variable Priority

Some variables support both `ORG_*` and `OK_*` prefixes for backward compatibility:
- `ORG_NAME` / `OK_NAME` → `ORG_NAME` takes priority
- `ORG_WEBSITE` / `OK_WEBSITE` → `ORG_WEBSITE` takes priority
- `ORG_BROADCAST_START` / `BROADCAST_START` → `ORG_BROADCAST_START` takes priority

### Security Best Practices

1. **Never commit `.env` files to git** - they contain sensitive information
2. **Use strong passwords** for database and superuser accounts
3. **Generate unique `DJANGO_SECRET_KEY`** for each environment
4. **Set `DEBUG=False`** in production
5. **Configure `ALLOWED_HOSTS`** properly for production
6. **Use `ro` (read-only) mounts** for NAS storage when possible

### Docker Compose Integration

- Service names (`db`, `redis`) are resolved automatically in Docker Compose
- Volume mounts are configured via `docker-compose.override.yml` (auto-generated)
- See [VOLUME_MOUNTS.md](./VOLUME_MOUNTS.md) for volume mount configuration

### Getting Help

- See [VOLUME_MOUNTS.md](./VOLUME_MOUNTS.md) for volume mount configuration
- See [PERIODIC_TASKS.md](./PERIODIC_TASKS.md) for Celery periodic tasks management
- Check application logs: `docker compose logs -f web`

---

**Last Updated:** 2025-11-10  
**Template Version:** 3.0

