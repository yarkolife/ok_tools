# Environment Variables Reference

> **Version:** 1.0  
> **Last Updated:** 2025-10-26  
> **Status:** Complete

This document provides comprehensive reference for all environment variables used by OK-Tools application.

## Table of Contents

- [Core Django Settings](#core-django-settings)
- [Database Configuration](#database-configuration)
- [Django Extended Configuration](#django-extended-configuration)
- [Email Configuration](#email-configuration)
- [Organization Settings](#organization-settings)
- [Media & NAS Storage](#media--nas-storage)
- [Bootstrap Configuration](#bootstrap-configuration)
- [Video Configuration](#video-configuration)
- [I18n Configuration](#i18n-configuration)
- [API Configuration](#api-configuration)
- [Security Configuration](#security-configuration)
- [Static Files Configuration](#static-files-configuration)
- [Cache Configuration](#cache-configuration)
- [Celery Configuration](#celery-configuration)
- [Celery Beat Schedules](#celery-beat-schedules)
- [Logging Configuration](#logging-configuration)
- [Backup Configuration](#backup-configuration)
- [Gunicorn Configuration](#gunicorn-configuration)
- [System Configuration](#system-configuration)
- [Backward Compatibility](#backward-compatibility)

---

## Core Django Settings

### DJANGO_SECRET_KEY
- **Description:** Secret key for Django cryptographic signing
- **Type:** String
- **Required:** Yes
- **Default:** None (must be set)
- **Example:** `DJANGO_SECRET_KEY=your-very-long-random-secret-key-here`
- **Notes:** 
  - Generate with: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
  - Keep this value secret and secure
  - Different for each environment

### DEBUG
- **Description:** Enable/disable Django debug mode
- **Type:** Boolean
- **Required:** No
- **Default:** `False`
- **Example:** `DEBUG=False`
- **Notes:**
  - Set to `False` in production
  - Enables detailed error pages when `True`
  - Performance impact when enabled

### ALLOWED_HOSTS
- **Description:** Comma-separated list of allowed hostnames/domains
- **Type:** List (comma-separated)
- **Required:** No
- **Default:** `localhost`
- **Example:** `ALLOWED_HOSTS=okmq.de,www.okmq.de,localhost`
- **Notes:**
  - Supports both comma and space separation
  - Include all domains that will access the application
  - Required for Django security

### DJANGO_SETTINGS_MODULE
- **Description:** Django settings module to use
- **Type:** String
- **Required:** No
- **Default:** `ok_tools.settings`
- **Example:** `DJANGO_SETTINGS_MODULE=ok_tools.settings`
- **Notes:** Usually doesn't need to be changed

---

## Database Configuration

### POSTGRES_DB
- **Description:** PostgreSQL database name
- **Type:** String
- **Required:** Yes
- **Default:** `oktools`
- **Example:** `POSTGRES_DB=oktools_production`
- **Notes:** Database must exist or be configured for auto-creation

### POSTGRES_USER
- **Description:** PostgreSQL database user
- **Type:** String
- **Required:** Yes
- **Default:** `oktools`
- **Example:** `POSTGRES_USER=oktools_user`
- **Notes:** User must have necessary permissions on the database

### POSTGRES_PASSWORD
- **Description:** PostgreSQL database password
- **Type:** String
- **Required:** Yes
- **Default:** None (must be set)
- **Example:** `POSTGRES_PASSWORD=secure-database-password`
- **Notes:** Keep this value secret and secure

### DB_HOST
- **Description:** Database server hostname
- **Type:** String
- **Required:** No
- **Default:** `localhost`
- **Example:** `DB_HOST=db` (for Docker) or `DB_HOST=192.168.1.100`
- **Notes:** Use `db` when using Docker Compose

### DB_PORT
- **Description:** Database server port
- **Type:** Integer
- **Required:** No
- **Default:** `5432`
- **Example:** `DB_PORT=5432`
- **Notes:** Standard PostgreSQL port

---

## Django Extended Configuration

### DJANGO_LOG_LEVEL
- **Description:** Django logging level
- **Type:** String
- **Required:** No
- **Default:** `INFO`
- **Example:** `DJANGO_LOG_LEVEL=DEBUG`
- **Valid Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Notes:** Use `DEBUG` only in development

### DJANGO_LANGUAGE
- **Description:** Default language code for Django
- **Type:** String
- **Required:** No
- **Default:** `de-de`
- **Example:** `DJANGO_LANGUAGE=en-us`
- **Notes:** Format: `language-region` (e.g., `de-de`, `en-us`)

### DJANGO_TIMEZONE
- **Description:** Default timezone for Django
- **Type:** String
- **Required:** No
- **Default:** `Europe/Berlin`
- **Example:** `DJANGO_TIMEZONE=UTC`
- **Notes:** Use IANA timezone names (e.g., `Europe/Berlin`, `America/New_York`)

### DJANGO_STATIC_ROOT
- **Description:** Directory for static files collection
- **Type:** String
- **Required:** No
- **Default:** `/app/staticfiles/`
- **Example:** `DJANGO_STATIC_ROOT=/var/www/static/`
- **Notes:** Absolute path to static files directory

### DJANGO_MEDIA_ROOT
- **Description:** Directory for user-uploaded media files
- **Type:** String
- **Required:** No
- **Default:** `/app/media/`
- **Example:** `DJANGO_MEDIA_ROOT=/var/www/media/`
- **Notes:** Absolute path to media files directory

### DJANGO_USE_SECURE_SETTINGS
- **Description:** Enable security-related Django settings
- **Type:** Boolean
- **Required:** No
- **Default:** `False`
- **Example:** `DJANGO_USE_SECURE_SETTINGS=True`
- **Notes:** When enabled, sets CSRF, SSL, and other security settings

---

## Email Configuration

### EMAIL_HOST
- **Description:** SMTP server hostname
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `EMAIL_HOST=smtp.your-provider.de`
- **Notes:** Required for email functionality

### EMAIL_PORT
- **Description:** SMTP server port
- **Type:** Integer
- **Required:** No
- **Default:** `587`
- **Example:** `EMAIL_PORT=587`
- **Notes:** Standard SMTP port with TLS

### EMAIL_USE_TLS
- **Description:** Use TLS encryption for SMTP
- **Type:** Boolean
- **Required:** No
- **Default:** `True`
- **Example:** `EMAIL_USE_TLS=True`
- **Notes:** Enable for secure email transmission

### EMAIL_HOST_USER
- **Description:** SMTP authentication username
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `EMAIL_HOST_USER=noreply@your-domain.com`
- **Notes:** Required for SMTP authentication

### EMAIL_HOST_PASSWORD
- **Description:** SMTP authentication password
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `EMAIL_HOST_PASSWORD=your-smtp-password`
- **Notes:** Keep this value secret and secure

### DEFAULT_FROM_EMAIL
- **Description:** Default email address for outgoing messages
- **Type:** String
- **Required:** No
- **Default:** `webmaster@localhost`
- **Example:** `DEFAULT_FROM_EMAIL=noreply@your-domain.com`
- **Notes:** Used as sender for system-generated emails

### MAIL_DEV_SETTINGS
- **Description:** Use development email backend
- **Type:** Boolean
- **Required:** No
- **Default:** `True`
- **Example:** `MAIL_DEV_SETTINGS=False`
- **Notes:** When `True`, emails are printed to console instead of sending

---

## Organization Settings

### ORG_NAME
- **Description:** Full organization name
- **Type:** String
- **Required:** No
- **Default:** `Open Channel Merseburg-Querfurt e.V.`
- **Example:** `ORG_NAME=Your Organization Name`
- **Notes:** Displayed throughout the application

### ORG_SHORT_NAME
- **Description:** Short organization name
- **Type:** String
- **Required:** No
- **Default:** `OK Merseburg`
- **Example:** `ORG_SHORT_NAME=YourOrg`
- **Notes:** Used in headers and limited space contexts

### ORG_WEBSITE
- **Description:** Organization website URL
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_WEBSITE=https://your-website.com`
- **Notes:** Include protocol (http:// or https://)

### ORG_EMAIL
- **Description:** Organization contact email
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_EMAIL=contact@your-organization.com`
- **Notes:** Public contact email for the organization

### ORG_PHONE
- **Description:** Organization contact phone
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_PHONE=+49 123 456789`
- **Notes:** Include country code for international format

### ORG_FAX
- **Description:** Organization fax number
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_FAX=+49 123 456788`
- **Notes:** Include country code for international format

### ORG_ADDRESS
- **Description:** Organization postal address
- **Type:** String (multiline)
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_ADDRESS=Street 123\\nCity\\nCountry`
- **Notes:** Use `\\n` for line breaks in .env files

### ORG_DESCRIPTION
- **Description:** Organization description
- **Type:** String (multiline)
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_DESCRIPTION=Your organization description\\nMultiple lines supported`
- **Notes:** Use `\\n` for line breaks in .env files

### ORG_OPENING_HOURS
- **Description:** Organization opening hours
- **Type:** String (multiline)
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_OPENING_HOURS=Mon-Fri: 9:00-17:00\\nSat: 10:00-14:00`
- **Notes:** Use `\\n` for line breaks in .env files

### ORG_ORGANIZATION_OWNER
- **Description:** Organization owner identifier
- **Type:** String
- **Required:** No
- **Default:** `OKMQ`
- **Example:** `ORG_ORGANIZATION_OWNER=YOUR_ORG`
- **Notes:** Used for internal identification

### ORG_BROADCAST_START
- **Description:** Start time for broadcast schedule
- **Type:** String (time)
- **Required:** No
- **Default:** `18:00`
- **Example:** `ORG_BROADCAST_START=06:00`
- **Notes:** Format: HH:MM (24-hour format)

### ORG_BROADCAST_END
- **Description:** End time for broadcast schedule
- **Type:** String (time)
- **Required:** No
- **Default:** `19:45`
- **Example:** `ORG_BROADCAST_END=23:00`
- **Notes:** Format: HH:MM (24-hour format)

### STATE_MEDIA_INSTITUTION
- **Description:** State media institution code
- **Type:** String
- **Required:** No
- **Default:** `MSA`
- **Example:** `STATE_MEDIA_INSTITUTION=YOUR_CODE`
- **Notes:** Used for regulatory compliance

### ORG_PEERTUBE_CHANNEL
- **Description:** Peertube channel URL
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `ORG_PEERTUBE_CHANNEL=https://peertube.example.com/c/your-channel`
- **Notes:** Include full URL to Peertube channel

---

## Media & NAS Storage

### NAS_ARCHIVE_PATH
- **Description:** Local path to archive storage
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `NAS_ARCHIVE_PATH=/mnt/nas/archive/`
- **Notes:** Must be accessible by the application

### NAS_PLAYOUT_PATH
- **Description:** Local path to playout storage
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `NAS_PLAYOUT_PATH=/mnt/nas/playout/`
- **Notes:** Must be accessible by the application

### NAS_ARCHIVE_UNC_PATH
- **Description:** UNC path to archive storage (Windows)
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `NAS_ARCHIVE_UNC_PATH=\\\\server\\share\\archive`
- **Notes:** Windows network share format

### NAS_PLAYOUT_UNC_PATH
- **Description:** UNC path to playout storage (Windows)
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `NAS_PLAYOUT_UNC_PATH=\\\\server\\share\\playout`
- **Notes:** Windows network share format

### MEDIA_AUTO_SCAN
- **Description:** Enable automatic media scanning
- **Type:** Boolean
- **Required:** No
- **Default:** `False`
- **Example:** `MEDIA_AUTO_SCAN=True`
- **Notes:** Enables periodic scanning of media directories

### MEDIA_AUTO_COPY_ON_SCHEDULE
- **Description:** Enable scheduled media copying
- **Type:** Boolean
- **Required:** No
- **Default:** `True`
- **Example:** `MEDIA_AUTO_COPY_ON_SCHEDULE=False`
- **Notes:** Controls automatic media file operations

---

## Bootstrap Configuration

### BOOTSTRAP_VERSION
- **Description:** Bootstrap CSS framework version
- **Type:** String
- **Required:** No
- **Default:** `5.3.3`
- **Example:** `BOOTSTRAP_VERSION=5.3.2`
- **Notes:** Must match available CDN version

### BOOTSTRAP_ICONS_VERSION
- **Description:** Bootstrap Icons version
- **Type:** String
- **Required:** No
- **Default:** `1.11.0`
- **Example:** `BOOTSTRAP_ICONS_VERSION=1.10.0`
- **Notes:** Must match available CDN version

### DASHBOARD_THEME
- **Description:** Color theme for user dashboard
- **Type:** String
- **Required:** No
- **Default:** `default`
- **Example:** `DASHBOARD_THEME=default` or `DASHBOARD_THEME=dark` or `DASHBOARD_THEME=vibrant`
- **Notes:**
  - Available themes: `default` (blue), `dark` (dark background with orange accents), `vibrant` (purple)
  - Affects colors, gradients, and styling of the user dashboard interface

---

## Video Configuration

### VIDEO_SUPPORTED_FORMATS
- **Description:** Comma-separated list of supported video formats
- **Type:** List (comma-separated)
- **Required:** No
- **Default:** `mp4,mov,mpeg,mpg`
- **Example:** `VIDEO_SUPPORTED_FORMATS=mp4,avi,mov,mkv`
- **Notes:** Used for file upload validation

### VIDEO_SCREEN_BOARD_DURATION
- **Description:** Duration for screen board display (seconds)
- **Type:** Integer
- **Required:** No
- **Default:** `20`
- **Example:** `VIDEO_SCREEN_BOARD_DURATION=30`
- **Notes:** Display time in seconds

---

## Video Storage Automation Configuration

### VIDEO_AUTO_COPY_ON_SCHEDULE
- **Description:** Enable automatic video copying when saving broadcast plans in planung module
- **Type:** Boolean
- **Required:** No
- **Default:** `false`
- **Example:** `VIDEO_AUTO_COPY_ON_SCHEDULE=true`
- **Notes:**
  - Only works if plan is not in draft mode
  - Requires `VIDEO_AUTO_COPY_TO_ARCHIVE` or `VIDEO_AUTO_COPY_TO_PLAYOUT` to be enabled
  - Requires ARCHIVE and/or PLAYOUT storage locations to be configured
  - Set to `false` for installations without archive/playout workflow

### VIDEO_AUTO_COPY_TO_ARCHIVE
- **Description:** Automatically copy videos to archive storage when planning
- **Type:** Boolean
- **Required:** No
- **Default:** `false`
- **Example:** `VIDEO_AUTO_COPY_TO_ARCHIVE=true`
- **Notes:**
  - Requires ARCHIVE storage location to be configured
  - Videos are copied to archive before being copied to playout
  - Skips if video already exists in archive
  - Set to `false` for installations without archive storage

### VIDEO_AUTO_COPY_TO_PLAYOUT
- **Description:** Automatically copy videos to playout storage when planning
- **Type:** Boolean
- **Required:** No
- **Default:** `false`
- **Example:** `VIDEO_AUTO_COPY_TO_PLAYOUT=true`
- **Notes:**
  - Requires PLAYOUT storage location to be configured
  - Uses weekly folders if `VIDEO_USE_WEEKLY_FOLDERS=true`
  - Skips if video already exists in target weekly folder
  - Set to `false` for installations without playout storage

### VIDEO_USE_WEEKLY_FOLDERS
- **Description:** Use weekly folders (YYYY_KW_WW format) in playout storage
- **Type:** Boolean
- **Required:** No
- **Default:** `true`
- **Example:** `VIDEO_USE_WEEKLY_FOLDERS=true`
- **Notes:**
  - Creates folders like `2025_KW_41` for week 41 of 2025
  - Automatically determines week from planning date
  - Recommended for organized playout storage
  - Set to `false` to store videos directly in playout root

### VIDEO_ARCHIVE_PROTECTED
- **Description:** Protect ARCHIVE storage from deletion
- **Type:** Boolean
- **Required:** No
- **Default:** `true`
- **Example:** `VIDEO_ARCHIVE_PROTECTED=true`
- **Notes:**
  - When enabled: videos in ARCHIVE can be read and copied, but not deleted
  - Prevents accidental data loss
  - Deletion is disabled in admin interface for ARCHIVE storage
  - Set to `false` to allow deletion from archive (not recommended)

### VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS
- **Description:** Number of days to consider CUSTOM storage files as "recent"
- **Type:** Integer
- **Required:** No
- **Default:** `7`
- **Example:** `VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS=7`
- **Notes:**
  - Recent CUSTOM files are preferred over ARCHIVE when selecting source
  - Files updated within this period are considered "freshly processed"
  - Older files use ARCHIVE as preferred source
  - Adjust based on your workflow (how long files stay in CUSTOM before archiving)

### VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME
- **Description:** Name of default playout storage for main broadcasts
- **Type:** String
- **Required:** No
- **Default:** `None` (auto-detects)
- **Example:** `VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME=Sendungen`
- **Notes:**
  - Used to select which PLAYOUT storage to use when multiple playout storages exist
  - Searches for storage location with name containing this value (case-insensitive)
  - If not set, auto-detects storage containing "000_Sendungen" in path or "Sendungen" in name
  - Falls back to first available PLAYOUT storage if nothing matches

### VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH
- **Description:** Path pattern to identify default playout storage
- **Type:** String
- **Required:** No
- **Default:** `None` (auto-detects)
- **Example:** `VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH=000_Sendungen`
- **Notes:**
  - Used to select which PLAYOUT storage to use when multiple playout storages exist
  - Searches for storage location with path containing this value (case-insensitive)
  - Checked after `VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME` if name is not set
  - If not set, auto-detects storage containing "000_Sendungen" in path
  - Falls back to first available PLAYOUT storage if nothing matches

### VIDEO_AUTO_DELETE_FROM_CUSTOM
- **Description:** Automatically delete videos from CUSTOM storage after successful copy
- **Type:** Boolean
- **Required:** No
- **Default:** `true`
- **Example:** `VIDEO_AUTO_DELETE_FROM_CUSTOM=true`
- **Notes:**
  - When enabled: videos are moved (deleted from CUSTOM) after successful copy to archive and playout
  - Only deletes if source was CUSTOM storage and all required copies succeeded
  - Prevents duplicate records and keeps CUSTOM storage (entry point) clean
  - Deletes both physical file and VideoFile database record
  - Creates FileOperation record for deletion tracking
  - Set to `false` to keep videos in CUSTOM storage after copying

### VIDEO_COPY_VERIFY_CHECKSUM
- **Description:** Verify checksum during video copy operations
- **Type:** Boolean
- **Required:** No
- **Default:** `true`
- **Example:** `VIDEO_COPY_VERIFY_CHECKSUM=true`
- **Notes:**
  - When enabled: uses SHA256 checksum verification (secure but slower for large files)
  - When disabled: skips checksum verification (faster but less secure)
  - Recommended: `true` for CUSTOM sources, `false` or use MD5 for ARCHIVE sources
  - For large files (3-4 GB), checksum calculation can take 1-2 minutes per file
  - Set to `false` to significantly speed up copying (especially for ARCHIVE sources)

### VIDEO_COPY_USE_MD5_FOR_ARCHIVE
- **Description:** Use faster MD5 checksum for ARCHIVE sources instead of SHA256
- **Type:** Boolean
- **Required:** No
- **Default:** `true`
- **Example:** `VIDEO_COPY_USE_MD5_FOR_ARCHIVE=true`
- **Notes:**
  - When enabled: uses MD5 algorithm for ARCHIVE sources (faster, less secure)
  - When disabled: uses SHA256 for all sources (slower, more secure)
  - MD5 is 2-3x faster than SHA256 but less secure (sufficient for integrity check)
  - Recommended: `true` to speed up copying from archive (files already verified)
  - Only applies when `VIDEO_COPY_VERIFY_CHECKSUM=true`
  - CUSTOM sources always use SHA256 when verification is enabled

---

## I18n Configuration

### I18N_DEFAULT_LANGUAGE
- **Description:** Default interface language
- **Type:** String
- **Required:** No
- **Default:** `de`
- **Example:** `I18N_DEFAULT_LANGUAGE=en`
- **Notes:** Language code (e.g., `de`, `en`, `fr`)

### I18N_SUPPORTED_LANGUAGES
- **Description:** Comma-separated list of supported languages
- **Type:** List (comma-separated)
- **Required:** No
- **Default:** `de,en`
- **Example:** `I18N_SUPPORTED_LANGUAGES=de,en,fr,es`
- **Notes:** Language codes (e.g., `de`, `en`, `fr`)

### I18N_LOCALE_PATHS
- **Description:** Path to translation files
- **Type:** String
- **Required:** No
- **Default:** `ok_tools/locale`
- **Example:** `I18N_LOCALE_PATHS=locale`
- **Notes:** Relative or absolute path to locale directory

### I18N_PHONE_REGION
- **Description:** Default region for phone numbers
- **Type:** String
- **Required:** No
- **Default:** `DE`
- **Example:** `I18N_PHONE_REGION=US`
- **Notes:** ISO 3166-1 alpha-2 country code

### I18N_DATE_FORMAT
- **Description:** Default date format
- **Type:** String
- **Required:** No
- **Default:** `%d.%m.%Y`
- **Example:** `I18N_DATE_FORMAT=%m/%d/%Y`
- **Notes:** Python datetime format codes

---

## API Configuration

### API_PAGE_SIZE
- **Description:** Default page size for API responses
- **Type:** Integer
- **Required:** No
- **Default:** `20`
- **Example:** `API_PAGE_SIZE=50`
- **Notes:** Number of items per API page

### API_ANON_RATE_LIMIT
- **Description:** Rate limit for anonymous API users
- **Type:** String
- **Required:** No
- **Default:** `100/hour`
- **Example:** `API_ANON_RATE_LIMIT=50/hour`
- **Notes:** Format: `number/period` (e.g., `100/hour`, `1000/day`)

### API_USER_RATE_LIMIT
- **Description:** Rate limit for authenticated API users
- **Type:** String
- **Required:** No
- **Default:** `1000/hour`
- **Example:** `API_USER_RATE_LIMIT=5000/hour`
- **Notes:** Format: `number/period` (e.g., `100/hour`, `1000/day`)

---

## Security Configuration

### SECURITY_SESSION_TIMEOUT
- **Description:** User session timeout (seconds)
- **Type:** Integer
- **Required:** No
- **Default:** `1200`
- **Example:** `SECURITY_SESSION_TIMEOUT=3600`
- **Notes:** Session duration in seconds (1200 = 20 minutes)

### SECURITY_PASSWORD_MIN_LENGTH
- **Description:** Minimum password length
- **Type:** Integer
- **Required:** No
- **Default:** `8`
- **Example:** `SECURITY_PASSWORD_MIN_LENGTH=12`
- **Notes:** Minimum characters required for passwords

### SECURITY_CSRF_COOKIE_AGE
- **Description:** CSRF cookie lifetime (seconds)
- **Type:** Integer
- **Required:** No
- **Default:** `31449600`
- **Example:** `SECURITY_CSRF_COOKIE_AGE=86400`
- **Notes:** CSRF cookie duration in seconds (31449600 = 1 year)

---

## Static Files Configuration

### STATIC_STORAGE_BACKEND
- **Description:** Django static files storage backend
- **Type:** String
- **Required:** No
- **Default:** `whitenoise.storage.CompressedManifestStaticFilesStorage`
- **Example:** `STATIC_STORAGE_BACKEND=django.contrib.staticfiles.storage.StaticFilesStorage`
- **Notes:** Python import path to storage class

### STATIC_URL_PREFIX
- **Description:** URL prefix for static files
- **Type:** String
- **Required:** No
- **Default:** `static/`
- **Example:** `STATIC_URL_PREFIX=assets/`
- **Notes:** URL path prefix (not including domain)

---

## Cache Configuration

### CACHE_BACKEND
- **Description:** Django cache backend
- **Type:** String
- **Required:** No
- **Default:** `django.core.cache.backends.locmem.LocMemCache`
- **Example:** `CACHE_BACKEND=django.core.cache.backends.redis.RedisCache`
- **Notes:** Python import path to cache backend

### CACHE_TIMEOUT
- **Description:** Default cache timeout (seconds)
- **Type:** Integer
- **Required:** No
- **Default:** `300`
- **Example:** `CACHE_TIMEOUT=600`
- **Notes:** Cache duration in seconds (300 = 5 minutes)

---

## Celery Configuration

### CELERY_BROKER_URL
- **Description:** Celery message broker URL
- **Type:** String
- **Required:** No
- **Default:** `redis://127.0.0.1:6379/0`
- **Example:** `CELERY_BROKER_URL=redis://redis:6379/0`
- **Notes:** Use `redis:6379/0` when using Docker Compose

### CELERY_RESULT_BACKEND
- **Description:** Celery result backend URL
- **Type:** String
- **Required:** No
- **Default:** `redis://127.0.0.1:6379/0`
- **Example:** `CELERY_RESULT_BACKEND=redis://redis:6379/0`
- **Notes:** Use `redis:6379/0` when using Docker Compose

### CELERY_DOWNLOAD_WORKER_CONCURRENCY
- **Description:** Number of parallel processes for the dedicated `download` queue worker
- **Type:** Integer
- **Required:** No
- **Default:** `1`
- **Example:** `CELERY_DOWNLOAD_WORKER_CONCURRENCY=1`
- **Notes:** Keep this at `1` to prevent multiple long Nextcloud downloads from occupying general-purpose Celery workers.

### CELERY_ANCHOR_RENDER_WORKER_CONCURRENCY
- **Description:** Number of parallel processes for the dedicated `anchor_render` queue worker
- **Type:** Integer
- **Required:** No
- **Default:** `1`
- **Example:** `CELERY_ANCHOR_RENDER_WORKER_CONCURRENCY=1`
- **Notes:** Keep this at `1` unless the external renderer can safely handle multiple programme preview chains at once.

### OKTOOLS_RENDER_TIMEOUT_SECONDS
- **Description:** Base timeout for FFmpeg render subprocesses (seconds)
- **Type:** Integer
- **Required:** No
- **Default:** `21600`
- **Example:** `OKTOOLS_RENDER_TIMEOUT_SECONDS=21600`
- **Notes:**
  - Used by render pipeline in [`media_files/rendering/ffmpeg.py`](media_files/rendering/ffmpeg.py:35)
  - Independent from [`GUNICORN_TIMEOUT`](deployment/docs/ENV_VARIABLES.md:860)
  - Effective timeout is dynamic: `max(OKTOOLS_RENDER_TIMEOUT_SECONDS, segment_duration * OKTOOLS_RENDER_TIMEOUT_FACTOR)`

### OKTOOLS_RENDER_TIMEOUT_FACTOR
- **Description:** Multiplier for dynamic FFmpeg render timeout by segment duration
- **Type:** Float
- **Required:** No
- **Default:** `3.0`
- **Example:** `OKTOOLS_RENDER_TIMEOUT_FACTOR=3.0`
- **Notes:**
  - Helps long renders avoid premature `TimeoutExpired`
  - Increase when render speed is below realtime due to CPU/NAS load

---

## Celery Beat Schedules

All Celery Beat schedule variables use standard cron format: `minute hour day month weekday`

### CELERY_BEAT_EXPIRE_RENTALS
- **Description:** Schedule for expiring room rentals
- **Type:** String (cron)
- **Required:** No
- **Default:** `*/30 * * * *`
- **Example:** `CELERY_BEAT_EXPIRE_RENTALS=0 */2 * * *`
- **Notes:** Every 30 minutes by default

### CELERY_BEAT_CLEANUP_BACKUPS
- **Description:** Schedule for cleaning old backups
- **Type:** String (cron)
- **Required:** No
- **Default:** `0 2 * * *`
- **Example:** `CELERY_BEAT_CLEANUP_BACKUPS=0 3 * * 0`
- **Notes:** Daily at 2:00 AM by default (Sunday at 3:00 AM in example)

### CELERY_BEAT_BACKUP_DB
- **Description:** Schedule for database backups
- **Type:** String (cron)
- **Required:** No
- **Default:** `0 3 * * *`
- **Example:** `CELERY_BEAT_BACKUP_DB=0 4 * * *`
- **Notes:** Daily at 3:00 AM by default

### CELERY_BEAT_AUTO_SCAN
- **Description:** Schedule for automatic media scanning
- **Type:** String (cron)
- **Required:** No
- **Default:** `0 */2 * * *`
- **Example:** `CELERY_BEAT_AUTO_SCAN=*/15 * * * *`
- **Notes:** Every 2 hours by default

### CELERY_BEAT_LINK_LICENSES
- **Description:** Schedule for linking orphan licenses
- **Type:** String (cron)
- **Required:** No
- **Default:** `0 4 * * *`
- **Example:** `CELERY_BEAT_LINK_LICENSES=0 5 * * *`
- **Notes:** Daily at 4:00 AM by default

### CELERY_BEAT_SYNC_VIDEOS
- **Description:** Schedule for syncing license videos
- **Type:** String (cron)
- **Required:** No
- **Default:** `0 5 * * *`
- **Example:** `CELERY_BEAT_SYNC_VIDEOS=0 6 * * *`
- **Notes:** Daily at 5:00 AM by default

### CELERY_BEAT_UPDATE_METADATA
- **Description:** Schedule for updating video metadata
- **Type:** String (cron)
- **Required:** No
- **Default:** `0 1 1 * *`
- **Example:** `CELERY_BEAT_UPDATE_METADATA=0 2 1 * *`
- **Notes:** Monthly on 1st at 1:00 AM by default

---

## Logging Configuration

### LOGGING_FILE
- **Description:** Path to application log file
- **Type:** String
- **Required:** No
- **Default:** `/app/logs/oktools.log`
- **Example:** `LOGGING_FILE=/var/log/oktools/app.log`
- **Notes:** Must be writable by the application

---

## Backup Configuration

### BACKUP_DIR
- **Description:** Directory for database backups
- **Type:** String
- **Required:** No
- **Default:** `backups/`
- **Example:** `BACKUP_DIR=/var/backups/oktools/`
- **Notes:** Must be writable by the application

---

## Gunicorn Configuration

### GUNICORN_WORKERS
- **Description:** Number of Gunicorn worker processes
- **Type:** Integer
- **Required:** No
- **Default:** (calculated based on CPU cores)
- **Example:** `GUNICORN_WORKERS=4`
- **Notes:** Typically 2-4 workers per CPU core

### GUNICORN_THREADS
- **Description:** Number of threads per Gunicorn worker
- **Type:** Integer
- **Required:** No
- **Default:** `1`
- **Example:** `GUNICORN_THREADS=2`
- **Notes:** Increase for I/O-bound applications

### GUNICORN_TIMEOUT
- **Description:** Gunicorn worker timeout (seconds)
- **Type:** Integer
- **Required:** No
- **Default:** `30`
- **Example:** `GUNICORN_TIMEOUT=60`
- **Notes:** Maximum time for request processing

---

## System Configuration

### PYTHONUNBUFFERED
- **Description:** Disable Python output buffering
- **Type:** Boolean
- **Required:** No
- **Default:** `1`
- **Example:** `PYTHONUNBUFFERED=1`
- **Notes:** Recommended for containerized applications

### PYTHONPATH
- **Description:** Python module search path
- **Type:** String
- **Required:** No
- **Default:** `/app`
- **Example:** `PYTHONPATH=/app`
- **Notes:** Application directory in container

---

## Backward Compatibility

### OKTOOLS_CONFIG_FILE
- **Description:** Path to legacy .cfg configuration file
- **Type:** String
- **Required:** No
- **Default:** (empty)
- **Example:** `OKTOOLS_CONFIG_FILE=/app/configs/production.cfg`
- **Notes:** 
  - **Deprecated:** Will be removed in version 2.0
  - Used only for migration period
  - Environment variables take precedence

---

## Configuration Examples

### Development Environment
```bash
# Core Django
DJANGO_SECRET_KEY=dev-secret-key-not-for-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=oktools_dev
POSTGRES_USER=oktools
POSTGRES_PASSWORD=dev-password
DB_HOST=localhost
DB_PORT=5432

# Email (development)
MAIL_DEV_SETTINGS=True

# Organization
ORG_NAME=OK Tools Development
ORG_SHORT_NAME=OK-Dev

# Logging
DJANGO_LOG_LEVEL=DEBUG
```

### Production Environment
```bash
# Core Django
DJANGO_SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
POSTGRES_DB=oktools_production
POSTGRES_USER=oktools
POSTGRES_PASSWORD=secure-production-password
DB_HOST=db
DB_PORT=5432

# Email
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=your-smtp-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
MAIL_DEV_SETTINGS=False

# Security
DJANGO_USE_SECURE_SETTINGS=True

# Organization
ORG_NAME=Your Organization
ORG_SHORT_NAME=YourOrg
ORG_WEBSITE=https://yourdomain.com
ORG_EMAIL=contact@yourdomain.com
```

## Migration from .cfg Files

For existing deployments using .cfg files:

1. **Run migration script:**
   ```bash
   ./deployment/scripts/migrate-config-to-env.sh
   ```

2. **Review generated .env file:**
   ```bash
   nano deployment/configs/your-env-file.env
   ```

3. **Update any __REPLACE_ME__ placeholders**

4. **Deploy with new configuration:**
   ```bash
   docker compose -f deployment/docker-compose.production.yml --env-file deployment/configs/your-env-file.env up -d
   ```

## Security Considerations

### Sensitive Variables
These variables contain sensitive information and should be protected:
- `DJANGO_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `EMAIL_HOST_PASSWORD`

### Best Practices
1. **File Permissions:** Set `.env` files to `600` (read/write by owner only)
2. **Version Control:** Never commit `.env` files with real secrets to Git
3. **Secret Management:** Use secret management systems in production
4. **Environment Separation:** Use different `.env` files for different environments

### Example File Permissions
```bash
# Set secure permissions
chmod 600 .env
chown $USER:$USER .env

# Verify permissions
ls -la .env
# Should show: -rw------- 1 user user 1234 Oct 26 20:47 .env
```

## Troubleshooting

### Common Issues

#### Variable Not Loading
**Symptoms:** Application using default values
**Solutions:**
- Check variable name spelling
- Verify .env file is in correct location
- Ensure no syntax errors in .env file

#### Type Conversion Errors
**Symptoms:** Configuration value type errors
**Solutions:**
- Verify boolean values are `True`/`False`
- Check integer values are numeric
- Ensure lists use comma separation

#### Permission Issues
**Symptoms:** "Permission denied" errors
**Solutions:**
```bash
chmod 600 .env
chown $USER:$USER .env
```

### Validation Commands
```bash
# Validate .env syntax
docker compose --env-file .env config

# Check Django configuration
docker compose exec web python manage.py check --deploy

# Test specific variable
docker compose exec web python -c "from django.conf import settings; print(settings.DATABASES)"
```

---

**Document prepared:** 2025-10-26  
**Version:** 1.0  
**Status:** Complete  
**Next Review:** After Phase 3 (Staging Deployment)
