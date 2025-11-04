#!/bin/bash
set -e

# Update script for OK Tools production environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"

if [ ! -d "$PRODUCTION_DIR" ]; then
    echo "Error: Production directory not found at $PRODUCTION_DIR"
    echo "Please run install.sh first"
    exit 1
fi

echo "=========================================="
echo "OK Tools Production Update"
echo "=========================================="
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
    echo "Note: .env file check completed"
fi

# Validate .env file before proceeding
if ! validate_env_file "$PRODUCTION_DIR/.env"; then
    echo ""
    echo "⚠️  .env file validation failed. Please review and fix errors."
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Update cancelled."
        exit 1
    fi
fi

# Pull latest code
echo "Pulling latest code from repository..."
cd "$PROJECT_DIR"
git pull

# Update docker-compose files and configs in production directory
echo "Updating docker-compose files and configs..."
cd "$PROJECT_DIR"

# Determine which docker-compose file to use based on existing installation
# Enhanced detection logic from install.sh
INSTALL_TYPE=""
if grep -q "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" && [ ! -z "$(grep '^DOMAIN_NAME=' "$PRODUCTION_DIR/.env" | cut -d'=' -f2)" ]; then
    echo "Detected: Production with Nginx and SSL"
    INSTALL_TYPE="1"
    cp -f deployment/docker-compose.production.yml "$PRODUCTION_DIR/docker-compose.yml"
    cp -f deployment/nginx.conf.template "$PRODUCTION_DIR/"
    cp -f deployment/nginx-entrypoint.sh "$PRODUCTION_DIR/"
    chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
else
    # Check if it's Local Network or Localhost
    if grep -q "127.0.0.1" "$PRODUCTION_DIR/.env" && grep -q "localhost" "$PRODUCTION_DIR/.env"; then
        echo "Detected: Localhost (Development on a single machine)"
        INSTALL_TYPE="3"
    else
        echo "Detected: Local Network (LAN access, no domain or SSL)"
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

# Ensure all required directories exist with proper permissions
echo "Creating required directories if they don't exist..."
mkdir -p "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
chmod 755 "$PRODUCTION_DIR/data/static" "$PRODUCTION_DIR/data/media"
chmod 755 "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/backups"
echo "✓ Directories checked and permissions set"

# Stop containers before rebuilding
echo "Stopping containers..."
cd "$PRODUCTION_DIR"
docker compose down

# Rebuild Docker images
echo "Rebuilding Docker images..."
docker compose build --no-cache

# Start containers
echo "Starting containers..."
docker compose up -d --build

# Wait for containers to be ready
echo "Waiting for containers to be ready..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker compose exec -T web python manage.py migrate --noinput

# Compile translation messages
echo "Compiling translation messages..."
if ! docker compose exec -T web python manage.py compilemessages; then
    echo "Warning: Failed to compile translation messages, continuing..."
else
    echo "Translation messages compiled successfully"
fi

# Collect static files
echo "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput

# Run post-update diagnostics (from install.sh)
echo -e "\nRunning post-update diagnostics..."

# Color variables for diagnostics
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==========================================${NC}"
echo -e "${YELLOW} OK Tools System Diagnostics${NC}"
echo -e "${YELLOW}==========================================${NC}"

# 1. Check container status
echo -e "\n${YELLOW}1. Checking container status...${NC}"
if ! docker compose ps --format "table {{.Service}}\t{{.Status}}"; then
    echo -e "${RED}Error: Failed to get container status. Is Docker running?${NC}"
    exit 1
fi

UNHEALTHY_CONTAINERS=$(docker compose ps --format "{{.Service}}" --filter "health=unhealthy")
if [ -n "$UNHEALTHY_CONTAINERS" ]; then
    echo -e "\n${RED}Warning: The following containers are unhealthy:${NC}"
    echo "$UNHEALTHY_CONTAINERS"
    echo -e "${YELLOW}This might indicate a problem. Check logs with: docker compose logs -f <service_name>${NC}"
else
    echo -e "\n${GREEN}✓ All containers are running and healthy.${NC}"
fi

# 2. Check web service logs for errors
echo -e "\n${YELLOW}2. Checking web service logs for recent errors...${NC}"
if docker compose logs --tail=50 web | grep -i -E "error|traceback"; then
    echo -e "\n${RED}Warning: Potential errors found in web service logs.${NC}"
    echo -e "${YELLOW}Please review logs above carefully.${NC}"
else
    echo -e "\n${GREEN}✓ No critical errors found in recent web service logs.${NC}"
fi

echo ""
echo "=========================================="
echo "Update Complete!"
echo "=========================================="
echo "Production directory: $PRODUCTION_DIR"
echo ""

# Display access information based on installation type
case $INSTALL_TYPE in
    1)
        # Production with SSL
        DOMAIN_NAME=$(grep "^DOMAIN_NAME=" "$PRODUCTION_DIR/.env" | cut -d'=' -f2)
        echo "Access admin panel: https://$DOMAIN_NAME/admin"
        ;;
    2)
        # Local Network - detect IP
        LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || \
                  ip route get 1.1.1.1 | awk '{print $7}' 2>/dev/null || \
                  ipconfig getifaddr en0 2>/dev/null || \
                  echo "127.0.0.1")
        echo "Access admin panel: http://$LOCAL_IP:8010/admin"
        ;;
    3)
        # Localhost
        echo "Access admin panel: http://localhost:8010/admin"
        ;;
    *)
        echo "Access admin panel: http://localhost:8010/admin"
        ;;
esac

echo ""
echo "Next steps:"
echo "1. Check container status: docker compose ps"
echo "2. View logs: docker compose logs -f web"
echo "3. If issues occur, run rollback script: $SCRIPT_DIR/rollback.sh"

echo -e "\n${YELLOW}==========================================${NC}"
echo -e "${GREEN}Diagnostics complete.${NC}"
echo -e "${YELLOW}==========================================${NC}"