#!/bin/bash
set -e

# Update script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

# Color functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

# Logging setup
LOG_FILE="/var/log/ok-tools-update.log"
# Create log file if it doesn't exist and set permissions
sudo touch "$LOG_FILE" 2>/dev/null || touch "$LOG_FILE" 2>/dev/null || true
sudo chmod 644 "$LOG_FILE" 2>/dev/null || chmod 644 "$LOG_FILE" 2>/dev/null || true

# Redirect output to both terminal and log file
exec > >(tee -a "$LOG_FILE") 2>&1

print_header "OK Tools Production Update"
print_info "Log file: $LOG_FILE"

if [ ! -d "$PRODUCTION_DIR" ]; then
    print_error "Production directory not found at $PRODUCTION_DIR"
    print_info "Please run install.sh first"
    exit 1
fi

echo ""

# Helper function to escape special characters for sed
escape_for_sed() {
    echo "$1" | sed -e 's/[]\/$*.^[]/\\&/g'
}

# Function to validate .env file (from install.sh)
validate_env_file() {
    local env_file="$1"
    local errors=0
    local warnings=0
    
    echo ""
    echo "Validating .env file..."
    echo "======================"
    
    # Critical variables that must exist and have values
    local critical_vars=(
        "POSTGRES_PASSWORD"
        "POSTGRES_DB"
        "POSTGRES_USER"
        "DATABASE_URL"
        "DJANGO_SECRET_KEY"
        "ALLOWED_HOSTS"
    )
    
    # Check if file exists
    if [ ! -f "$env_file" ]; then
        echo "❌ ERROR: .env file not found at $env_file"
        return 1
    fi
    
    # Check each critical variable
    for var in "${critical_vars[@]}"; do
        # Extract the value for this variable
        local value=$(grep "^${var}=" "$env_file" | head -1 | cut -d'=' -f2-)
        
        # Check if variable exists
        if [ -z "$value" ]; then
            echo "❌ ERROR: $var is missing or empty"
            errors=$((errors+1))
            continue
        fi
        
        # Check if value is a placeholder
        if [[ "$value" == *"__REPLACE_ME__"* ]]; then
            echo "❌ ERROR: $var still contains __REPLACE_ME__ placeholder"
            errors=$((errors+1))
            continue
        fi
        
        # Check if value contains inline comments
        if [[ "$value" =~ [[:space:]]+# ]]; then
            echo "⚠️  WARNING: $var contains inline comment - value may be malformed"
            warnings=$((warnings+1))
        fi
        
        # Special validation for specific variables
        case "$var" in
            "DATABASE_URL")
                if [[ ! "$value" =~ ^postgresql:// ]]; then
                    echo "❌ ERROR: DATABASE_URL must start with postgresql://"
                    errors=$((errors+1))
                fi
                ;;
            "ALLOWED_HOSTS")
                if [[ -z "$value" ]] || [[ "$value" == "localhost" ]]; then
                    echo "⚠️  WARNING: ALLOWED_HOSTS should include your domain/IP"
                    warnings=$((warnings+1))
                fi
                ;;
        esac
        
        echo "✓ $var: OK"
    done
    
    # Check for concatenated lines (common issue) - IMPROVED DETECTION
    # Only flag as error if it's clearly a concatenation of separate variables
    local concatenated=$(grep -E '^[A-Z_][A-Z0-9_]*=[^=]*[A-Z_][A-Z0-9_]*=' "$env_file" | wc -l | tr -d ' ')
    if [ "$concatenated" -gt 0 ]; then
        echo "❌ ERROR: Found $concatenated line(s) with concatenated variables"
        echo "   This usually means line breaks are missing in .env file"
        errors=$((errors+1))
        
        # Show problematic lines
        echo "   Problematic lines:"
        grep -E '^[A-Z_][A-Z0-9_]*=[^=]*[A-Z_][A-Z0-9_]*=' "$env_file" | head -5 | sed 's/^/   /'
    fi
    
    # Summary
    echo ""
    echo "Validation Summary:"
    echo "==================="
    echo "Errors: $errors"
    echo "Warnings: $warnings"
    
    if [ $errors -gt 0 ]; then
        echo ""
        echo "❌ Validation FAILED - please fix errors before proceeding"
        return 1
    elif [ $warnings -gt 0 ]; then
        echo ""
        echo "⚠️  Validation passed with warnings - review before production use"
        return 0
    else
        echo ""
        echo "✅ Validation PASSED - .env file is properly configured"
        return 0
    fi
}

# IMPROVED Function to detect and repair corrupted .env files
# Only repairs actual corruption, not legitimate values with '='
repair_env_file() {
    local env_file="$PRODUCTION_DIR/.env"
    
    if [ ! -f "$env_file" ]; then
        echo "Warning: .env file not found at $env_file"
        return 1
    fi
    
    # Check for corruption pattern: ONLY flag clear concatenations of separate variables
    # Pattern: KEY1=VALUE1KEY2=VALUE2 (no space between VALUE1 and KEY2)
    local corrupted_lines=$(grep -E '^[A-Z_][A-Z0-9_]*=[^=]*[A-Z_][A-Z0-9_]*=' "$env_file" | wc -l)
    
    if [ "$corrupted_lines" -gt 0 ]; then
        echo "Detected corruption in .env file ($corrupted_lines corrupted lines)"
        echo "Creating backup..."
        cp "$env_file" "$env_file.backup.$(date +%Y%m%d_%H%M%S)"
        
        echo "Repairing .env file..."
        
        # Create temporary file for repaired content
        local temp_file="/tmp/repaired_env.tmp"
        
        # Process each line to fix concatenated variables
        while IFS= read -r line; do
            # Skip comments and empty lines
            if [[ $line =~ ^# ]] || [[ -z "$line" ]]; then
                echo "$line" >> "$temp_file"
                continue
            fi
            
            # Check if line contains ACTUAL concatenated variables (not just = in values)
            if [[ $line =~ ^([^=]+)=(.*) ]]; then
                local key="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                
                # Check if this is actually a concatenation by looking for pattern: VALUEKEY2=
                # where KEY2 starts with uppercase letter and is followed by =
                if [[ $value =~ ([^=]*[A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
                    # This is a concatenation, split it
                    local first_value="${BASH_REMATCH[1]}"
                    local remaining="${BASH_REMATCH[2]}"
                    
                    # Write the first key-value pair
                    echo "$key=$first_value" >> "$temp_file"
                    
                    # Try to extract the second key-value pair
                    if [[ $remaining =~ ^([^=]+)=(.*)$ ]]; then
                        local second_key="${BASH_REMATCH[1]}"
                        local second_value="${BASH_REMATCH[2]}"
                        echo "$second_key=$second_value" >> "$temp_file"
                    fi
                else
                    # Line is not corrupted, write as-is
                    echo "$line" >> "$temp_file"
                fi
            else
                # Line is not corrupted, write as-is
                echo "$line" >> "$temp_file"
            fi
        done < "$env_file"
        
        # Replace original file with repaired version
        mv "$temp_file" "$env_file"
        chmod 600 "$env_file"
        
        echo "✓ .env file repaired successfully"
        return 0
    else
        echo "✓ .env file appears to be valid"
        return 0
    fi
}

# Check and repair .env file if needed
if ! repair_env_file; then
    print_info "Note: .env file check completed"
fi

# Validate .env file before proceeding
if ! validate_env_file "$PRODUCTION_DIR/.env"; then
    echo ""
    print_warning ".env file validation failed. Please review and fix errors"
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Update cancelled"
        exit 1
    fi
fi

# Create backup before update
print_header "Creating Backup Before Update"
BACKUP_DIR="$PRODUCTION_DIR/backups/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

print_info "Backing up database..."
cd "$PRODUCTION_DIR"
if docker compose ps db | grep -q "Up"; then
    if docker compose exec -T db pg_dump -U oktools oktools > "$BACKUP_DIR/database.sql" 2>/dev/null; then
        print_success "Database backup created"
    else
        print_warning "Database backup failed (container may not be running)"
    fi
else
    print_warning "Database container is not running, skipping database backup"
fi

print_info "Backing up configuration..."
cp "$PRODUCTION_DIR/.env" "$BACKUP_DIR/.env.backup" 2>/dev/null || true
cp "$PRODUCTION_DIR/docker-compose.yml" "$BACKUP_DIR/docker-compose.yml.backup" 2>/dev/null || true
print_success "Configuration backup created"

# Backup rotation - keep only last 5
print_info "Rotating backups (keeping last 5)..."
BACKUP_COUNT=$(ls -1d "$PRODUCTION_DIR/backups/backup-"* 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKUP_COUNT" -gt 5 ]; then
    OLD_BACKUPS=$(ls -1td "$PRODUCTION_DIR/backups/backup-"* | tail -n +6)
    for old_backup in $OLD_BACKUPS; do
        rm -rf "$old_backup"
        print_info "Removed old backup: $(basename "$old_backup")"
    done
fi
print_success "Backup rotation completed (kept 5 most recent)"

# Pull latest code
print_info "Pulling latest code from repository..."
cd "$PROJECT_DIR"
git pull

# Update docker-compose files and configs in production directory
print_info "Updating docker-compose files and configs..."
cd "$PROJECT_DIR"

# Determine which docker-compose file to use based on existing installation
# Enhanced detection logic from install.sh
INSTALL_TYPE=""
if grep -q "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" && [ ! -z "$(grep '^DOMAIN_NAME=' "$PRODUCTION_DIR/.env" | cut -d'=' -f2)" ]; then
    print_info "Detected: Production with Nginx and SSL"
    INSTALL_TYPE="1"
    cp -f deployment/docker-compose.production.yml "$PRODUCTION_DIR/docker-compose.yml"
    cp -f deployment/nginx.conf.template "$PRODUCTION_DIR/"
    cp -f deployment/nginx-entrypoint.sh "$PRODUCTION_DIR/"
    chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
else
    # Check if it's Local Network or Localhost
    if grep -q "127.0.0.1" "$PRODUCTION_DIR/.env" && grep -q "localhost" "$PRODUCTION_DIR/.env"; then
        print_info "Detected: Localhost (Development on a single machine)"
        INSTALL_TYPE="3"
    else
        print_info "Detected: Local Network (LAN access, no domain or SSL)"
        INSTALL_TYPE="2"
    fi
    cp -f deployment/docker-compose.production.no-nginx.yml "$PRODUCTION_DIR/docker-compose.yml"
fi

cp -f deployment/production.Dockerfile "$PRODUCTION_DIR/"
cp -f deployment/entrypoint.production.sh "$PRODUCTION_DIR/"

# Create configs directory if it doesn't exist and copy config files
# BUT DON'T COPY .env TEMPLATES to avoid overwriting existing .env
mkdir -p "$PRODUCTION_DIR/configs"
# Copy only non-.env template files to avoid overwriting existing .env
find deployment/configs -type f ! -name "*.env.template" -exec cp -f {} "$PRODUCTION_DIR/configs/" \;

# Update .env file with new variables if they don't exist
echo "Checking for missing environment variables..."
ENV_FILE="$PRODUCTION_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    # Backup current .env
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✓ Backed up .env file"
    
    # Function to add variable if not exists
    add_env_var_if_missing() {
        local key="$1"
        local value="$2"
        
        if ! grep -q "^${key}=" "$ENV_FILE"; then
            echo "$key=$value" >> "$ENV_FILE"
            echo "  + Added $key"
        else
            echo "  ✓ $key already exists, keeping current value"
        fi
    }
    
    # Add new ENV variables with defaults
    add_env_var_if_missing "DJANGO_LOG_LEVEL" "INFO"
    add_env_var_if_missing "DJANGO_LANGUAGE" "de-de"
    add_env_var_if_missing "DJANGO_TIMEZONE" "Europe/Berlin"
    add_env_var_if_missing "DJANGO_STATIC_ROOT" "/app/staticfiles/"
    add_env_var_if_missing "DJANGO_MEDIA_ROOT" "/app/media/"
    add_env_var_if_missing "DJANGO_USE_SECURE_SETTINGS" "True"
    add_env_var_if_missing "MAIL_DEV_SETTINGS" "False"
    add_env_var_if_missing "MEDIA_AUTO_SCAN" "False"
    add_env_var_if_missing "MEDIA_AUTO_COPY_ON_SCHEDULE" "True"
    add_env_var_if_missing "BOOTSTRAP_VERSION" "5.3.3"
    add_env_var_if_missing "BOOTSTRAP_ICONS_VERSION" "1.11.0"
    add_env_var_if_missing "API_PAGE_SIZE" "20"
    add_env_var_if_missing "VIDEO_SCREEN_BOARD_DURATION" "20"
    add_env_var_if_missing "I18N_PHONE_REGION" "DE"
    add_env_var_if_missing "I18N_DATE_FORMAT" "%d.%m.%Y"
    add_env_var_if_missing "CELERY_BROKER_URL" "redis://redis:6379/0"
    add_env_var_if_missing "CELERY_RESULT_BACKEND" "redis://redis:6379/0"
    add_env_var_if_missing "CELERY_BEAT_EXPIRE_RENTALS" "*/30 * * * *"
    add_env_var_if_missing "CELERY_BEAT_CLEANUP_BACKUPS" "0 2 * * *"
    add_env_var_if_missing "CELERY_BEAT_BACKUP_DB" "0 3 * * *"
    add_env_var_if_missing "CELERY_BEAT_AUTO_SCAN" "0 */2 * * *"
    add_env_var_if_missing "CELERY_BEAT_LINK_LICENSES" "0 4 * * *"
    add_env_var_if_missing "CELERY_BEAT_SYNC_VIDEOS" "0 5 * * *"
    add_env_var_if_missing "CELERY_BEAT_UPDATE_METADATA" "0 1 1 * *"
    add_env_var_if_missing "LOGGING_FILE" "/app/logs/oktools.log"
    
    echo "✓ Environment variables updated"
else
    echo "Warning: .env file not found at $ENV_FILE"
fi

# Check if migration from volumes to bind mounts is needed
print_info "Checking for volume migration..."
MIGRATION_NEEDED=false
cd "$PRODUCTION_DIR"

# Check if old docker-compose.yml uses named volumes
if [ -f "docker-compose.yml" ]; then
    if grep -q "static_volume:\|media_volume:" "docker-compose.yml"; then
        MIGRATION_NEEDED=true
        print_warning "Detected old volume-based configuration - migration required"
    fi
fi

# Migrate from volumes to bind mounts if needed
if [ "$MIGRATION_NEEDED" = true ]; then
    print_header "Migrating from Volumes to Bind Mounts"
    
    # Stop containers first
    print_info "Stopping containers..."
    docker compose down || true
    
    # Create directories
    print_info "Creating bind mount directories..."
    mkdir -p "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
    chmod 755 "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media"
    chmod 755 "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
    
    # Create temporary container to copy data from volumes
    print_info "Copying data from volumes to bind mounts..."
    
    # Get project name
    PROJECT_NAME=$(grep -m1 "^COMPOSE_PROJECT_NAME=" "$PRODUCTION_DIR/.env" 2>/dev/null | cut -d'=' -f2 || echo "oktools")
    PROJECT_NAME=${PROJECT_NAME:-oktools}
    
    # Copy static files if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_static_volume\|static_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_static_volume|static_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying static files from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/data/static:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Static files migrated"
        fi
    fi
    
    # Copy media files if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_media_volume\|media_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_media_volume|media_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying media files from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/data/media:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Media files migrated"
        fi
    fi
    
    # Copy logs if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_logs_volume\|logs_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_logs_volume|logs_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying logs from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/logs:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Logs migrated"
        fi
    fi
    
    # Copy backups if volume exists
    if docker volume ls | grep -q "${PROJECT_NAME}_backups_volume\|backups_volume"; then
        VOLUME_NAME=$(docker volume ls | grep -E "${PROJECT_NAME}_backups_volume|backups_volume" | awk '{print $2}' | head -1)
        if [ -n "$VOLUME_NAME" ]; then
            print_info "  Copying backups from volume: $VOLUME_NAME"
            docker run --rm -v "$VOLUME_NAME:/source:ro" -v "$PRODUCTION_DIR/backups:/dest" alpine sh -c "cp -a /source/. /dest/ 2>/dev/null || true"
            print_success "  Backups migrated"
        fi
    fi
    
    print_success "Migration completed"
    print_warning "Old volumes will be removed after successful startup"
    print_info "You can manually remove them later with: docker volume prune"
    echo ""
fi

# Ensure all required directories exist with proper permissions
print_info "Ensuring required directories exist..."
mkdir -p "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
chmod 755 "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media"
chmod 755 "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"

# Check if static directory is empty (bind mount will hide container files if host dir is empty)
if [ -z "$(ls -A "$PRODUCTION_DIR/data/static" 2>/dev/null)" ]; then
    print_warning "Static directory is empty on host"
    print_info "Files will be created after container starts and collectstatic runs"
fi

print_success "Directories checked and permissions set"

# Stop containers before rebuilding (if not already stopped)
if [ "$MIGRATION_NEEDED" != true ]; then
    print_info "Stopping containers..."
    cd "$PRODUCTION_DIR"
    docker compose down
fi

# Rebuild Docker images
print_info "Rebuilding Docker images..."
docker compose build --no-cache

# Start containers
print_info "Starting containers..."
docker compose up -d --build

# Wait for containers to be ready
print_info "Waiting for containers to be ready..."
sleep 10

# Run migrations
print_info "Running database migrations..."
docker compose exec -T web python manage.py migrate --noinput

# Compile translation messages
print_info "Compiling translation messages..."
if ! docker compose exec -T web python manage.py compilemessages; then
    print_warning "Failed to compile translation messages, continuing..."
else
    print_success "Translation messages compiled successfully"
fi

# Collect static files
print_info "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput

# Verify static files are present and accessible
print_info "Verifying static files..."
STATIC_COUNT=$(docker compose exec -T web sh -c "find /app/staticfiles -type f 2>/dev/null | wc -l" | tr -d ' ' || echo "0")
if [ "$STATIC_COUNT" -gt 0 ]; then
    print_success "Found $STATIC_COUNT static files in container"
    
    # Wait a moment for filesystem sync
    sleep 2
    
    # Check if files are visible on host
    HOST_STATIC_COUNT=$(find "$PRODUCTION_DIR/data/static" -type f 2>/dev/null | wc -l || echo "0")
    if [ "$HOST_STATIC_COUNT" -gt 0 ]; then
        print_success "Static files are accessible on host: $HOST_STATIC_COUNT files found"
    else
        print_warning "Static files not visible on host"
        print_info "This may be a permissions issue. Checking..."
        echo "   Container files: $STATIC_COUNT"
        echo "   Host files: $HOST_STATIC_COUNT"
        print_info "Trying to fix permissions..."
        
        # Try to fix permissions - run as root in container to ensure access
        docker compose exec -T --user root web sh -c "chown -R app:app /app/staticfiles && chmod -R 755 /app/staticfiles" || true
        
        # Check again after permission fix
        sleep 1
        HOST_STATIC_COUNT_AFTER=$(find "$PRODUCTION_DIR/data/static" -type f 2>/dev/null | wc -l || echo "0")
        if [ "$HOST_STATIC_COUNT_AFTER" -gt 0 ]; then
            print_success "Permission fix successful: $HOST_STATIC_COUNT_AFTER files now visible"
        else
            print_warning "Files still not visible. This may be normal if running in a restricted environment"
            print_info "Static files are available inside the container and will be served by Django/WhiteNoise"
        fi
    fi
else
    print_warning "No static files found in container after collectstatic"
    print_info "This may indicate a problem with static files configuration"
fi

# Cleanup Docker resources
print_info "Cleaning up unused Docker resources..."
docker image prune -f > /dev/null 2>&1
docker volume prune -f > /dev/null 2>&1
print_success "Docker cleanup completed"

# Health check
print_info "Checking web service availability on port 8010..."
for i in {1..30}; do
    if curl -s http://localhost:8010/health > /dev/null 2>&1; then
        print_success "Web service is available"
        break
    elif [ $i -eq 30 ]; then
        print_warning "Web service health check timeout"
    else
        sleep 2
    fi
done

# Check logs for errors
print_info "Checking logs for errors..."
ERROR_LINES=$(docker compose logs web 2>&1 | grep -iE "(error|exception|traceback)" | grep -vE "(ERROR|WARNING|INFO|DEBUG)\s*\:" | grep -vE "No valid legacy config|Validation|migration" | tail -10)
if [ -n "$ERROR_LINES" ]; then
    print_warning "Potential errors found in logs:"
    echo "$ERROR_LINES" | head -5 | sed 's/^/  /'
    print_info "Full logs: docker compose logs web"
else
    print_success "No critical errors in logs"
fi

# Clean up old volumes after successful update (if migration was performed)
if [ "$MIGRATION_NEEDED" = true ]; then
    echo ""
    print_info "Cleaning up old volumes..."
    # Remove old named volumes (non-destructive - only removes if not in use)
    docker volume ls | grep -E "${PROJECT_NAME}_static_volume|static_volume|${PROJECT_NAME}_media_volume|media_volume|${PROJECT_NAME}_logs_volume|logs_volume|${PROJECT_NAME}_backups_volume|backups_volume" | awk '{print $2}' | while read vol; do
        if docker volume inspect "$vol" >/dev/null 2>&1; then
            print_info "  Removing old volume: $vol"
            docker volume rm "$vol" 2>/dev/null || print_info "    (Volume may still be in use, will be cleaned up later)"
        fi
    done
    print_success "Volume cleanup completed"
fi

# Run post-update diagnostics
print_header "Running Post-Update Diagnostics"

# 1. Check container status
print_info "1. Checking container status..."
if ! docker compose ps --format "table {{.Service}}\t{{.Status}}"; then
    print_error "Failed to get container status. Is Docker running?"
    exit 1
fi

UNHEALTHY_CONTAINERS=$(docker compose ps --format "table {{.Service}}\t{{.Status}}" | grep -i "unhealthy" | awk '{print $1}' | grep -v "SERVICE")
if [ -n "$UNHEALTHY_CONTAINERS" ]; then
    print_warning "The following containers are unhealthy:"
    echo "$UNHEALTHY_CONTAINERS"
    print_info "Check logs with: docker compose logs -f <service_name>"
else
    print_success "All containers are running and healthy"
fi

# 2. Check web service logs for errors
print_info "2. Checking web service logs for recent errors..."
ERROR_LINES=$(docker compose logs --tail=50 web 2>&1 | grep -iE "(error|exception|traceback)" | grep -vE "(ERROR|WARNING|INFO|DEBUG)\s*\:" | grep -vE "No valid legacy config|Validation|migration|Your models.*have changes")
if [ -n "$ERROR_LINES" ]; then
    print_warning "Potential errors found in web service logs:"
    echo "$ERROR_LINES" | head -5 | sed 's/^/  /'
    print_info "Please review logs above carefully"
else
    print_success "No critical errors found in recent web service logs"
fi

print_header "Update Complete!"
echo "Production directory: $PRODUCTION_DIR"
echo ""

# Display access information based on installation type
case $INSTALL_TYPE in
    1)
        # Production with SSL
        DOMAIN_NAME=$(grep "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" | cut -d'=' -f2)
        print_info "Access admin panel: https://$DOMAIN_NAME/admin"
        ;;
    2)
        # Local Network - detect IP
        LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || \
                  ip route get 1.1.1.1 | awk '{print $7}' 2>/dev/null || \
                  ipconfig getifaddr en0 2>/dev/null || \
                  echo "127.0.0.1")
        print_info "Access admin panel: http://$LOCAL_IP:8010/admin"
        ;;
    3)
        # Localhost
        print_info "Access admin panel: http://localhost:8010/admin"
        ;;
    *)
        print_info "Access admin panel: http://localhost:8010/admin"
        ;;
esac

echo ""
print_info "Next steps:"
echo "1. Check container status: docker compose ps"
echo "2. View logs: docker compose logs -f web"
echo "3. If issues occur, run rollback script: $SCRIPT_DIR/rollback.sh"

print_header "Diagnostics Complete"