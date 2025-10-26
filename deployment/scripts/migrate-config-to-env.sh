#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$(dirname "$SCRIPT_DIR")/configs"

echo "=========================================="
echo "Config Migration: .cfg → .env"
echo "=========================================="
echo ""

# Function to convert single .cfg to .env
convert_cfg_to_env() {
    local cfg_file="$1"
    local env_file="$2"
    
    echo "Converting $cfg_file → $env_file"
    
    # Backup existing .env if exists
    if [ -f "$env_file" ]; then
        backup_file="$env_file.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$env_file" "$backup_file"
        echo "  ✓ Backed up existing .env to $backup_file"
    fi
    
    # Use Python for actual conversion
    python3 << 'EOF'
import sys
import configparser
import os
from datetime import datetime

cfg_file = sys.argv[1]
env_file = sys.argv[2]

config = configparser.RawConfigParser()
config.read(cfg_file)

# Complete mapping from architectural decision
MAPPING = {
    # Django core
    ('django', 'secret_key'): 'DJANGO_SECRET_KEY',
    ('django', 'debug'): 'DEBUG',
    ('django', 'allowed_hosts'): 'ALLOWED_HOSTS',
    
    # Database
    ('django', 'db_name'): 'POSTGRES_DB',
    ('django', 'db_user'): 'POSTGRES_USER',
    ('django', 'db_pw'): 'POSTGRES_PASSWORD',
    ('django', 'db_host'): 'DB_HOST',
    ('django', 'db_port'): 'DB_PORT',
    
    # Django extended
    ('django', 'language'): 'DJANGO_LANGUAGE',
    ('django', 'timezone'): 'DJANGO_TIMEZONE',
    ('django', 'static'): 'DJANGO_STATIC_ROOT',
    ('django', 'media'): 'DJANGO_MEDIA_ROOT',
    ('django', 'use_secure_settings'): 'DJANGO_USE_SECURE_SETTINGS',
    ('django', 'mail_dev_settings'): 'MAIL_DEV_SETTINGS',
    
    # Email
    ('django', 'email_host'): 'EMAIL_HOST',
    ('django', 'email_port'): 'EMAIL_PORT',
    ('django', 'email_use_tls'): 'EMAIL_USE_TLS',
    ('django', 'email_host_user'): 'EMAIL_HOST_USER',
    ('django', 'email_host_password'): 'EMAIL_HOST_PASSWORD',
    ('django', 'default_from_email'): 'DEFAULT_FROM_EMAIL',
    
    # Organization
    ('organization', 'name'): 'ORG_NAME',
    ('organization', 'short_name'): 'ORG_SHORT_NAME',
    ('organization', 'website'): 'ORG_WEBSITE',
    ('organization', 'email'): 'ORG_EMAIL',
    ('organization', 'phone'): 'ORG_PHONE',
    ('organization', 'fax'): 'ORG_FAX',
    ('organization', 'address'): 'ORG_ADDRESS',
    ('organization', 'description'): 'ORG_DESCRIPTION',
    ('organization', 'opening_hours'): 'ORG_OPENING_HOURS',
    ('organization', 'organization_owner'): 'ORG_ORGANIZATION_OWNER',
    ('organization', 'broadcast_start'): 'ORG_BROADCAST_START',
    ('organization', 'broadcast_end'): 'ORG_BROADCAST_END',
    ('organization', 'state_media_institution'): 'STATE_MEDIA_INSTITUTION',
    ('organization', 'peertube_channel'): 'ORG_PEERTUBE_CHANNEL',
    
    # Media & NAS
    ('media', 'archive_path'): 'NAS_ARCHIVE_PATH',
    ('media', 'playout_path'): 'NAS_PLAYOUT_PATH',
    ('media', 'auto_scan'): 'MEDIA_AUTO_SCAN',
    ('media', 'auto_copy_on_schedule'): 'MEDIA_AUTO_COPY_ON_SCHEDULE',
    ('nas_storage', 'archive_unc_path'): 'NAS_ARCHIVE_UNC_PATH',
    ('nas_storage', 'playout_unc_path'): 'NAS_PLAYOUT_UNC_PATH',
    
    # Bootstrap
    ('bootstrap', 'version'): 'BOOTSTRAP_VERSION',
    ('bootstrap', 'icons_version'): 'BOOTSTRAP_ICONS_VERSION',
    
    # Video
    ('video', 'screen_board_duration'): 'VIDEO_SCREEN_BOARD_DURATION',
    ('video', 'supported_formats'): 'VIDEO_SUPPORTED_FORMATS',
    
    # I18n
    ('i18n', 'default_language'): 'I18N_DEFAULT_LANGUAGE',
    ('i18n', 'supported_languages'): 'I18N_SUPPORTED_LANGUAGES',
    ('i18n', 'locale_paths'): 'I18N_LOCALE_PATHS',
    ('i18n', 'phone_region'): 'I18N_PHONE_REGION',
    ('i18n', 'date_format'): 'I18N_DATE_FORMAT',
    
    # Celery
    ('celery', 'broker_url'): 'CELERY_BROKER_URL',
    ('celery', 'result_backend'): 'CELERY_RESULT_BACKEND',
    
    # Celery Beat
    ('celery_beat', 'expire_rentals_schedule'): 'CELERY_BEAT_EXPIRE_RENTALS',
    ('celery_beat', 'cleanup_old_backups_schedule'): 'CELERY_BEAT_CLEANUP_BACKUPS',
    ('celery_beat', 'run_backup_db_schedule'): 'CELERY_BEAT_BACKUP_DB',
    ('celery_beat', 'auto_scan_schedule'): 'CELERY_BEAT_AUTO_SCAN',
    ('celery_beat', 'link_orphan_licenses_schedule'): 'CELERY_BEAT_LINK_LICENSES',
    ('celery_beat', 'sync_licenses_videos_schedule'): 'CELERY_BEAT_SYNC_VIDEOS',
    ('celery_beat', 'update_video_metadata_schedule'): 'CELERY_BEAT_UPDATE_METADATA',
    
    # Logging
    ('logging', 'level'): 'DJANGO_LOG_LEVEL',
    ('logging', 'file'): 'LOGGING_FILE',
    
    # API
    ('api', 'page_size'): 'API_PAGE_SIZE',
    ('api', 'anon_rate_limit'): 'API_ANON_RATE_LIMIT',
    ('api', 'user_rate_limit'): 'API_USER_RATE_LIMIT',
    
    # Security
    ('security', 'session_timeout'): 'SECURITY_SESSION_TIMEOUT',
    ('security', 'password_min_length'): 'SECURITY_PASSWORD_MIN_LENGTH',
    ('security', 'csrf_cookie_age'): 'SECURITY_CSRF_COOKIE_AGE',
    
    # Static & Cache
    ('static', 'storage_backend'): 'STATIC_STORAGE_BACKEND',
    ('static', 'static_url'): 'STATIC_URL_PREFIX',
    ('cache', 'backend'): 'CACHE_BACKEND',
    ('cache', 'timeout'): 'CACHE_TIMEOUT',
}

def normalize_value(value, env_key):
    """Normalize value for .env format."""
    if not value:
        return value
    
    # Handle multiline values - keep \n escape sequences
    value = value.replace('\n', '\\n')
    
    # Special case: ALLOWED_HOSTS - convert space to comma
    if env_key == 'ALLOWED_HOSTS':
        value = value.replace(' ', ',')
    
    # Special case: Cron schedules - ensure 5 fields
    if env_key.startswith('CELERY_BEAT_'):
        parts = value.split()
        while len(parts) < 5:
            parts.append('*')
        value = ' '.join(parts[:5])
    
    # Special case: date format with %% -> %
    if '%' in value and not value.startswith('%'):
        value = value.replace('%%', '%')
    
    return value

with open(env_file, 'w') as f:
    f.write("# Migrated from .cfg file\n")
    f.write(f"# Source: {cfg_file}\n")
    f.write(f"# Migration date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("# \n")
    f.write("# This file was automatically generated by migrate-config-to-env.sh\n")
    f.write("# Review and adjust values as needed before deploying\n")
    f.write("\n")
    
    converted_count = 0
    skipped_count = 0
    
    for (section, key), env_name in sorted(MAPPING.items(), key=lambda x: x[1]):
        try:
            value = config.get(section, key)
            value = normalize_value(value, env_name)
            f.write(f"{env_name}={value}\n")
            converted_count += 1
        except:
            skipped_count += 1
            pass
    
    f.write("\n# Migration Statistics\n")
    f.write(f"# Converted: {converted_count} variables\n")
    f.write(f"# Skipped: {skipped_count} variables (not found in .cfg)\n")

print(f"  ✓ Migrated to {env_file}")
print(f"  ✓ Converted {converted_count} variables")
print(f"  ✓ Skipped {skipped_count} variables (not in source)")
EOF
    
    python3 - "$cfg_file" "$env_file"
}

# Main logic
echo "Scanning for .cfg files in: $CONFIGS_DIR"
echo ""

cfg_files=($(find "$CONFIGS_DIR" -name "*.cfg" -type f 2>/dev/null))

if [ ${#cfg_files[@]} -eq 0 ]; then
    echo "No .cfg files found in $CONFIGS_DIR"
    exit 1
fi

echo "Found ${#cfg_files[@]} .cfg file(s):"
for cfg in "${cfg_files[@]}"; do
    echo "  - $(basename "$cfg")"
done
echo ""

read -p "Proceed with migration? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled"
    exit 0
fi

echo ""
echo "Starting migration..."
echo ""

for cfg_file in "${cfg_files[@]}"; do
    basename=$(basename "$cfg_file" -production.cfg)
    basename=$(basename "$basename" .cfg)
    
    # Determine output filename
    if [[ "$cfg_file" == *"-production.cfg" ]]; then
        env_file="$CONFIGS_DIR/${basename}-production.env"
    else
        env_file="$CONFIGS_DIR/${basename}.env"
    fi
    
    convert_cfg_to_env "$cfg_file" "$env_file"
    echo ""
done

echo "=========================================="
echo "Migration Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review generated .env files in: $CONFIGS_DIR"
echo "2. Update any placeholder values (__REPLACE_ME__)"
echo "3. Test configuration with: docker compose config"
echo "4. Deploy to staging for testing"
echo ""
echo "Backup files created with .backup suffix"
echo "Original .cfg files remain unchanged"