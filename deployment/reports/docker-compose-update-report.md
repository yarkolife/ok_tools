# Docker Compose Configuration Update Report

## Overview

This report documents the updates made to Docker Compose configuration files as part of Phase 1, Task 3 of the configuration migration to .env files. The updates ensure that all new environment variables are properly passed to the containers.

## Files Modified

1. [`deployment/docker-compose.production.yml`](deployment/docker-compose.production.yml:1)
2. [`deployment/docker-compose.production.no-nginx.yml`](deployment/docker-compose.production.no-nginx.yml:1)

## Summary of Changes

### Added Environment Variables

The following environment variables were added to the `web`, `celery_worker`, and `celery_beat` services:

#### Django Extended Configuration
- `DJANGO_LOG_LEVEL` (default: INFO)
- `DJANGO_LANGUAGE` (default: de-de)
- `DJANGO_TIMEZONE` (default: Europe/Berlin)
- `DJANGO_STATIC_ROOT` (default: /app/staticfiles/)
- `DJANGO_MEDIA_ROOT` (default: /app/media/)
- `DJANGO_USE_SECURE_SETTINGS` (default: True)

#### Database Extended Configuration
- `DB_HOST` (default: db)
- `DB_PORT` (default: 5432)

#### Email Configuration
- `EMAIL_HOST` (default: empty)
- `EMAIL_PORT` (default: 587)
- `EMAIL_USE_TLS` (default: True)
- `EMAIL_HOST_USER` (default: empty)
- `EMAIL_HOST_PASSWORD` (default: empty)
- `DEFAULT_FROM_EMAIL` (default: empty)
- `MAIL_DEV_SETTINGS` (default: False)

#### Organization Extended Configuration
- `ORG_ORGANIZATION_OWNER` (default: empty)
- `ORG_BROADCAST_START` (default: 18:00)
- `ORG_BROADCAST_END` (default: 19:45)
- `ORG_PEERTUBE_CHANNEL` (default: empty)

#### NAS Storage Configuration
- `NAS_ARCHIVE_UNC_PATH` (default: empty)
- `NAS_PLAYOUT_UNC_PATH` (default: empty)
- `MEDIA_AUTO_SCAN` (default: False)
- `MEDIA_AUTO_COPY_ON_SCHEDULE` (default: True)

#### Logging Configuration
- `LOGGING_FILE` (default: /app/logs/oktools.log)

#### Bootstrap Configuration
- `BOOTSTRAP_VERSION` (default: 5.3.3)
- `BOOTSTRAP_ICONS_VERSION` (default: 1.11.0)

#### API Configuration
- `API_PAGE_SIZE` (default: 20)
- `API_ANON_RATE_LIMIT` (default: 100/hour)
- `API_USER_RATE_LIMIT` (default: 1000/hour)

#### Security Configuration
- `SECURITY_SESSION_TIMEOUT` (default: 1200)
- `SECURITY_PASSWORD_MIN_LENGTH` (default: 8)
- `SECURITY_CSRF_COOKIE_AGE` (default: 31449600)

#### Video Configuration
- `VIDEO_SUPPORTED_FORMATS` (default: mp4,mov,mpeg,mpg)
- `VIDEO_SCREEN_BOARD_DURATION` (default: 20)

#### I18n Configuration
- `I18N_DEFAULT_LANGUAGE` (default: de)
- `I18N_SUPPORTED_LANGUAGES` (default: de,en)
- `I18N_LOCALE_PATHS` (default: ok_tools/locale)
- `I18N_PHONE_REGION` (default: DE)
- `I18N_DATE_FORMAT` (default: %d.%m.%Y)

#### Static Files Configuration
- `STATIC_STORAGE_BACKEND` (default: whitenoise.storage.CompressedManifestStaticFilesStorage)
- `STATIC_URL_PREFIX` (default: static/)

#### Cache Configuration
- `CACHE_BACKEND` (default: django.core.cache.backends.locmem.LocMemCache)
- `CACHE_TIMEOUT` (default: 300)

#### Celery Extended Configuration
- `CELERY_BROKER_URL` (default: redis://redis:6379/0)
- `CELERY_RESULT_BACKEND` (default: redis://redis:6379/0)

#### Celery Beat Schedules
- `CELERY_BEAT_EXPIRE_RENTALS` (default: */30 * * * *)
- `CELERY_BEAT_CLEANUP_BACKUPS` (default: 0 2 * * *)
- `CELERY_BEAT_BACKUP_DB` (default: 0 3 * * *)
- `CELERY_BEAT_AUTO_SCAN` (default: 0 */2 * * *)
- `CELERY_BEAT_LINK_LICENSES` (default: 0 4 * * *)
- `CELERY_BEAT_SYNC_VIDEOS` (default: 0 5 * * *)
- `CELERY_BEAT_UPDATE_METADATA` (default: 0 1 1 * *)

#### Backward Compatibility
- `OKTOOLS_CONFIG_FILE` (default: empty) - for backward compatibility with existing .cfg files

### Key Implementation Details

1. **Default Values**: All new variables use the `${VAR:-default}` syntax to provide sensible defaults
2. **Grouping**: Variables are organized into logical groups with comments for better readability
3. **Service Coverage**: All variables are added to `web`, `celery_worker`, and `celery_beat` services
4. **Nginx Service**: The nginx service only retains the `DOMAIN_NAME` variable as it doesn't need Django-specific settings
5. **Database and Redis Services**: These services only retain their specific environment variables

## Diff Summary

### docker-compose.production.yml
- Lines increased from 170 to 334
- Added 164 new environment variable definitions across web, celery_worker, and celery_beat services
- Maintained all existing configuration and structure

### docker-compose.production.no-nginx.yml
- Lines increased from 138 to 302
- Added 164 new environment variable definitions across web, celery_worker, and celery_beat services
- Maintained all existing configuration and structure

## Testing Instructions

### Prerequisites
1. Ensure you have updated `.env` files based on the templates
2. Verify that all required variables are set for your specific deployment

### Testing Steps
1. **Validate Configuration**:
   ```bash
   docker-compose -f deployment/docker-compose.production.yml config
   ```

2. **Test Service Startup**:
   ```bash
   docker-compose -f deployment/docker-compose.production.yml up --no-deps web
   ```

3. **Verify Environment Variables**:
   ```bash
   docker-compose -f deployment/docker-compose.production.yml exec web env | grep -E "(DJANGO_|CELERY_|EMAIL_|ORG_)"
   ```

4. **Test Celery Services**:
   ```bash
   docker-compose -f deployment/docker-compose.production.yml up --no-deps celery_worker
   docker-compose -f deployment/docker-compose.production.yml up --no-deps celery_beat
   ```

## Migration Checklist

- [x] All new environment variables added to web service
- [x] All new environment variables added to celery_worker service
- [x] All new environment variables added to celery_beat service
- [x] Variables grouped by category with comments
- [x] Default values provided using `${VAR:-default}` syntax
- [x] Backward compatibility maintained with OKTOOLS_CONFIG_FILE
- [x] Existing variables preserved
- [x] Both docker-compose files updated consistently
- [x] Nginx service configuration unchanged (only needs DOMAIN_NAME)
- [x] Database and Redis services unchanged

## Next Steps

1. Test the updated configuration in a development environment
2. Update deployment documentation to reflect the new environment variables
3. Consider creating a migration script for existing deployments
4. Update monitoring and logging configurations to utilize the new variables

## Notes

- The configuration maintains backward compatibility with existing `.cfg` files through the `OKTOOLS_CONFIG_FILE` variable
- All new variables have sensible defaults to ensure containers can start even if not explicitly set in `.env` files
- The grouping and commenting structure makes the configuration more maintainable and easier to understand
- Both Docker Compose files are kept in sync to ensure consistency across deployment options