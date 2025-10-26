#!/bin/bash
set -e

# Interactive installation script for OK Tools production environment with hybrid logic
# Supports both template-based installation and manual configuration

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
PRODUCTION_DIR="$(dirname "$PROJECT_DIR")/ok_tools_production"
CONFIGS_DIR="$PROJECT_DIR/deployment/configs"

echo "=========================================="
echo "OK Tools Installation (Hybrid)"
echo "=========================================="
echo ""

echo "Choose installation type:"
echo "1. Production (Public server with Domain, Nginx, and SSL)"
echo "2. Local Network (LAN access, no domain or SSL)"
echo "3. Localhost (Development on a single machine)"
read -p "Enter your choice (1, 2, or 3): " INSTALL_TYPE
echo ""

# Function to display available templates
show_templates() {
    echo "Available configuration templates:"
    local templates=($(ls "$CONFIGS_DIR"/*.env.template 2>/dev/null))
    if [ ${#templates[@]} -eq 0 ]; then
        echo "  No templates found in $CONFIGS_DIR"
        return 1
    fi
    
    local i=1
    for template in "${templates[@]}"; do
        template_name=$(basename "$template" .env.template)
        echo " $i. $template_name"
        i=$((i+1))
    done
    return 0
}

# Function to validate .env file
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
    
    # Check for concatenated lines (common issue)
    local concatenated=$(grep -E '^[A-Z_]+=.*[A-Z_]+=' "$env_file" | wc -l | tr -d ' ')
    if [ "$concatenated" -gt 0 ]; then
        echo "❌ ERROR: Found $concatenated line(s) with concatenated variables"
        echo "   This usually means line breaks are missing in the .env file"
        errors=$((errors+1))
        
        # Show problematic lines
        echo "   Problematic lines:"
        grep -E '^[A-Z_]+=.*[A-Z_]+=' "$env_file" | head -5 | sed 's/^/   /'
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

# Function to prompt for secrets based on template
prompt_secrets() {
    local template="$1"
    local output_file="$2"
    local secrets_file="${output_file%.env}_secrets.txt"
    
    echo "" >&2
    echo "Processing template: $(basename "$template")" >&2
    echo "Please enter values (press Enter to auto-generate):" >&2
    echo "====================================================" >&2
    
    # Copy template to output file
    cp "$template" "$output_file"
    
    # Create secrets file
    echo "# Generated Secrets - $(date)" > "$secrets_file"
    echo "# KEEP THIS FILE SECURE!" >> "$secrets_file"
    echo "" >> "$secrets_file"
    
    # POSTGRES_PASSWORD
    echo "" >&2
    echo -n "POSTGRES_PASSWORD (or press Enter to generate): " >&2
    read -s postgres_pass
    echo "" >&2
    if [ -z "$postgres_pass" ]; then
        postgres_pass=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
        echo "Generated POSTGRES_PASSWORD: $postgres_pass" >&2
        echo "POSTGRES_PASSWORD=$postgres_pass" >> "$secrets_file"
    fi
    sed -i.bak "s|POSTGRES_PASSWORD=__REPLACE_ME__|POSTGRES_PASSWORD=$postgres_pass|" "$output_file"
    sed -i.bak "s|postgresql://oktools:__REPLACE_ME__@db:5432/oktools|postgresql://oktools:$postgres_pass@db:5432/oktools|g" "$output_file"
    
    # DJANGO_SECRET_KEY
    echo -n "DJANGO_SECRET_KEY (or press Enter to generate): " >&2
    read -s django_key
    echo "" >&2
    if [ -z "$django_key" ]; then
        django_key=$(openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
        echo "Generated DJANGO_SECRET_KEY: $django_key" >&2
        echo "DJANGO_SECRET_KEY=$django_key" >> "$secrets_file"
    fi
    sed -i.bak "s|DJANGO_SECRET_KEY=__REPLACE_ME__|DJANGO_SECRET_KEY=$django_key|" "$output_file"
    
    # ALLOWED_HOSTS
    echo -n "ALLOWED_HOSTS (comma-separated, or press Enter for localhost): " >&2
    read allowed_hosts
    if [ -z "$allowed_hosts" ]; then
        allowed_hosts="localhost,127.0.0.1"
        echo "Using default: $allowed_hosts" >&2
    fi
    sed -i.bak "s|ALLOWED_HOSTS=localhost,127.0.1,__REPLACE_ME__|ALLOWED_HOSTS=$allowed_hosts|" "$output_file"
    sed -i.bak "s|ALLOWED_HOSTS=__REPLACE_ME__|ALLOWED_HOSTS=$allowed_hosts|" "$output_file"
    
    # SUPERUSER_PASSWORD
    echo -n "SUPERUSER_PASSWORD (or press Enter to generate): " >&2
    read -s superuser_pass
    echo "" >&2
    if [ -z "$superuser_pass" ]; then
        superuser_pass=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
        echo "Generated SUPERUSER_PASSWORD: $superuser_pass" >&2
        echo "SUPERUSER_PASSWORD=$superuser_pass" >> "$secrets_file"
    fi
    sed -i.bak "s|SUPERUSER_PASSWORD=__REPLACE_ME__|SUPERUSER_PASSWORD=$superuser_pass|" "$output_file"
    
    # EMAIL_HOST_PASSWORD
    echo -n "EMAIL_HOST_PASSWORD (or press Enter to generate): " >&2
    read -s email_pass
    echo "" >&2
    if [ -z "$email_pass" ]; then
        email_pass=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
        echo "Generated EMAIL_HOST_PASSWORD: $email_pass" >&2
        echo "EMAIL_HOST_PASSWORD=$email_pass" >> "$secrets_file"
    fi
    sed -i.bak "s|EMAIL_HOST_PASSWORD=__REPLACE_ME__|EMAIL_HOST_PASSWORD=$email_pass|" "$output_file"
    
    # Remove backup files
    rm -f "$output_file.bak"
    
    chmod 600 "$secrets_file"
    echo "" >&2
    echo "✓ Configuration completed" >&2
    echo "✓ Secrets saved to: $secrets_file" >&2
    echo "" >&2
}

# Check if production directory already exists
if [ -d "$PRODUCTION_DIR" ]; then
    echo "Production directory already exists at: $PRODUCTION_DIR"
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create production directory
mkdir -p "$PRODUCTION_DIR"/{data/postgres,data/static,data/media,logs,backups}

# Ask user for installation mode
echo "Choose installation mode:"
echo "1. Use existing template"
echo "2. Manual configuration"
echo ""
read -p "Enter your choice (1 or 2): " INSTALL_MODE

# Process installation based on type
case $INSTALL_TYPE in
    1)
        echo "Selected: Production (Public server with Domain, Nginx, and SSL)"
        ;;
    2)
        echo "Selected: Local Network (LAN access, no domain or SSL)"
        ;;
    3)
        echo "Selected: Localhost (Development on a single machine)"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

if [ "$INSTALL_MODE" = "1" ]; then
    # Template-based installation
    if ! show_templates; then
        echo "No templates available. Switching to manual configuration."
        INSTALL_MODE="2"
    else
        echo ""
        read -p "Enter template number (or name): " TEMPLATE_CHOICE
        
        # Check if user entered a number or name
        if [[ $TEMPLATE_CHOICE =~ ^[0-9]+$ ]]; then
            # User entered a number
            templates=($(ls "$CONFIGS_DIR"/*.env.template))
            if [ $TEMPLATE_CHOICE -ge 1 ] && [ $TEMPLATE_CHOICE -le ${#templates[@]} ]; then
                TEMPLATE_FILE="${templates[$((TEMPLATE_CHOICE-1))]}"
            else
                echo "Invalid template number."
                exit 1
            fi
        else
            # User entered a name
            TEMPLATE_FILE="$CONFIGS_DIR/$TEMPLATE_CHOICE.env.template"
            if [ ! -f "$TEMPLATE_FILE" ]; then
                echo "Template $TEMPLATE_CHOICE not found."
                exit 1
            fi
        fi
        
        echo "Using template: $TEMPLATE_FILE"
        
        # Prompt for secrets and create .env file directly
        ENV_FILE="$PRODUCTION_DIR/.env"
        prompt_secrets "$TEMPLATE_FILE" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        
        echo "✓ Created .env file at: $ENV_FILE"
        
        # Validate the generated .env file
        if ! validate_env_file "$PRODUCTION_DIR/.env"; then
            echo ""
            echo "⚠️  .env file validation failed. Please review and fix errors."
            read -p "Do you want to continue anyway? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Installation cancelled."
                exit 1
            fi
        fi
        
        # Copy necessary files based on installation type
        echo ""
        echo "Copying deployment files..."
        if [ "$INSTALL_TYPE" = "1" ]; then
            # Production: use nginx-enabled compose file and copy nginx files
            cp "$PROJECT_DIR/deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml"
            cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template"
            cp "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/nginx-entrypoint.sh"
            chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
        else
            # Local Network or Localhost: use compose file without nginx
            cp "$PROJECT_DIR/deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml"
        fi
        cp "$PROJECT_DIR/deployment/production.Dockerfile" "$PRODUCTION_DIR/Dockerfile"
        cp "$PROJECT_DIR/deployment/entrypoint.production.sh" "$PRODUCTION_DIR/entrypoint.sh"
        chmod +x "$PRODUCTION_DIR/entrypoint.sh"
        
        # NOTE: The deployment directory is no longer copied to ensure Dockerfile is in root
        # This ensures docker-compose.yml can find the Dockerfile in the root directory
        # and that entrypoint.sh is properly included in the build context
        
        if [ "$INSTALL_TYPE" = "1" ]; then
            echo "✓ Copied docker-compose.yml (with nginx)"
            echo "✓ Copied nginx.conf.template"
            echo "✓ Copied nginx-entrypoint.sh"
        else
            echo "✓ Copied docker-compose.yml (without nginx)"
        fi
        echo "✓ Copied Dockerfile"
        echo "✓ Copied entrypoint.sh"
        echo "✓ Copied deployment directory"
        
        # Copy source files to destination directory
        echo "Copying source files..."
        cp "$PROJECT_DIR/requirements.txt" "$PRODUCTION_DIR/requirements.txt"
        cp -r "$PROJECT_DIR/ok_tools" "$PRODUCTION_DIR/ok_tools"
        # Add other necessary directories for the application
        cp -r "$PROJECT_DIR/contributions" "$PRODUCTION_DIR/contributions"
        cp -r "$PROJECT_DIR/dashboard" "$PRODUCTION_DIR/dashboard"
        cp -r "$PROJECT_DIR/inventory" "$PRODUCTION_DIR/inventory"
        cp -r "$PROJECT_DIR/licenses" "$PRODUCTION_DIR/licenses"
        cp -r "$PROJECT_DIR/media_files" "$PRODUCTION_DIR/media_files"
        cp -r "$PROJECT_DIR/planung" "$PRODUCTION_DIR/planung"
        cp -r "$PROJECT_DIR/projects" "$PRODUCTION_DIR/projects"
        cp -r "$PROJECT_DIR/registration" "$PRODUCTION_DIR/registration"
        cp -r "$PROJECT_DIR/rental" "$PRODUCTION_DIR/rental"
        cp "$PROJECT_DIR/manage.py" "$PRODUCTION_DIR/manage.py"
        
    fi
elif [ "$INSTALL_MODE" = "2" ]; then
    # Manual configuration
    echo "Step 1: Organization Configuration"
    echo "===================================="
    read -p "Organization name (e.g., 'Your Community Media Organization e.V.'): " ORG_NAME
    read -p "Organization short name (e.g., 'Your CMO'): " ORG_SHORT_NAME
    read -p "Organization website (e.g., 'https://your-domain.com'): " ORG_WEBSITE
    read -p "Organization email: " ORG_EMAIL
    read -p "Organization phone: " ORG_PHONE
    read -p "Organization address (use \\n for line breaks): " ORG_ADDRESS
    read -p "State media institution (MSA/LFK/BLM/etc.): " STATE_MEDIA_INSTITUTION

    echo ""
    echo "Step 2: Database Configuration"
    echo "=============================="
    read -p "Database password (leave empty for auto-generated): " DB_PASSWORD
    if [ -z "$DB_PASSWORD" ]; then
        DB_PASSWORD=$(openssl rand -base64 32)
        echo "Generated database password: $DB_PASSWORD"
    fi

    echo ""
    echo "Step 3: Superuser Configuration"
    echo "==============================="
    read -p "Superuser username (default: admin): " SUPERUSER_USERNAME
    SUPERUSER_USERNAME=${SUPERUSER_USERNAME:-admin}
    read -p "Superuser email: " SUPERUSER_EMAIL
    read -p "Superuser password (leave empty for auto-generated): " SUPERUSER_PASSWORD
    if [ -z "$SUPERUSER_PASSWORD" ]; then
        SUPERUSER_PASSWORD=$(openssl rand -base64 32)
        echo "Generated superuser password: $SUPERUSER_PASSWORD"
    fi

    echo ""
    echo "Step 4: Django Configuration"
    echo "============================"
    DJANGO_SECRET_KEY=$(openssl rand -base64 50)
    
    # Set ALLOWED_HOSTS based on installation type
    if [ "$INSTALL_TYPE" = "1" ]; then
        # Production: use domain name
        read -p "Allowed hosts (comma-separated, e.g., 'localhost,your-domain.com'): " ALLOWED_HOSTS
    elif [ "$INSTALL_TYPE" = "2" ]; then
        # Local Network: ask for IP address
        read -p "Server IP address in local network (e.g., 192.168.1.100): " SERVER_IP
        ALLOWED_HOSTS="$SERVER_IP"
    else
        # Localhost: automatically set
        ALLOWED_HOSTS="localhost,127.0.1"
    fi
    
    # Additional configuration for backup directory
    BACKUP_DIR="/app/backups"
    echo "Using default backup directory: $BACKUP_DIR"

    echo ""
    # SSL Configuration - only for Production mode
    if [ "$INSTALL_TYPE" = "1" ]; then
        echo "Step 5: SSL Configuration"
        echo "========================="
        read -p "Enable SSL with Certbot (Let's Encrypt)? (y/n): " ENABLE_SSL
        if [[ $ENABLE_SSL =~ ^[Yy]$ ]]; then
            read -p "Enter your domain name (e.g., your-domain.com): " DOMAIN_NAME
            read -p "Enter your email for Let's Encrypt registration: " SSL_EMAIL
            SSL_ENABLED=true
        else
            SSL_ENABLED=false
            DOMAIN_NAME=""
            SSL_EMAIL=""
        fi
    else
        # For Local Network or Localhost, skip SSL configuration
        SSL_ENABLED=false
        DOMAIN_NAME=""
        SSL_EMAIL=""
    fi

    echo ""
    echo "Step 5: Extended Configuration"
    echo "==============================="
    read -p "Django log level (INFO/DEBUG/WARNING/ERROR) [INFO]: " DJANGO_LOG_LEVEL
    DJANGO_LOG_LEVEL=${DJANGO_LOG_LEVEL:-INFO}

    read -p "Email host (SMTP server) [smtp.your-provider.de]: " EMAIL_HOST
    EMAIL_HOST=${EMAIL_HOST:-smtp.your-provider.de}

    read -p "Email port [587]: " EMAIL_PORT
    EMAIL_PORT=${EMAIL_PORT:-587}

    read -p "Organization owner name: " ORG_ORGANIZATION_OWNER

    read -p "Broadcast start time (HH:MM) [18:00]: " ORG_BROADCAST_START
    ORG_BROADCAST_START=${ORG_BROADCAST_START:-18:00}

    read -p "Broadcast end time (HH:MM) [19:45]: " ORG_BROADCAST_END
    ORG_BROADCAST_END=${ORG_BROADCAST_END:-19:45}

    # Generate .env file using echo commands to avoid heredoc issues
    ENV_FILE="$PRODUCTION_DIR/.env"
    
    # Create header
    echo "# OK Tools Environment Configuration" > "$ENV_FILE"
    echo "# Generated: $(date)" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Database Configuration
    echo "# Database Configuration" >> "$ENV_FILE"
    echo "POSTGRES_DB=oktools" >> "$ENV_FILE"
    echo "POSTGRES_USER=oktools" >> "$ENV_FILE"
    echo "POSTGRES_PASSWORD=$DB_PASSWORD" >> "$ENV_FILE"
    echo "DATABASE_URL=postgresql://oktools:$DB_PASSWORD@db:5432/oktools" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Django Configuration
    echo "# Django Configuration" >> "$ENV_FILE"
    echo "DJANGO_SETTINGS_MODULE=ok_tools.settings" >> "$ENV_FILE"
    echo "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" >> "$ENV_FILE"
    echo "DEBUG=False" >> "$ENV_FILE"
    echo "ALLOWED_HOSTS=$ALLOWED_HOSTS" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Organization Configuration
    echo "# Organization Configuration" >> "$ENV_FILE"
    echo "ORG_NAME=$ORG_NAME" >> "$ENV_FILE"
    echo "ORG_SHORT_NAME=$ORG_SHORT_NAME" >> "$ENV_FILE"
    echo "ORG_WEBSITE=$ORG_WEBSITE" >> "$ENV_FILE"
    echo "ORG_EMAIL=$ORG_EMAIL" >> "$ENV_FILE"
    echo "ORG_PHONE=$ORG_PHONE" >> "$ENV_FILE"
    # Handle ORG_ADDRESS with proper escaping
    echo "ORG_ADDRESS=$ORG_ADDRESS" | sed 's/\\n/\n/g' >> "$ENV_FILE"
    echo "STATE_MEDIA_INSTITUTION=$STATE_MEDIA_INSTITUTION" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Superuser Configuration
    echo "# Superuser Configuration" >> "$ENV_FILE"
    echo "SUPERUSER_USERNAME=$SUPERUSER_USERNAME" >> "$ENV_FILE"
    echo "SUPERUSER_EMAIL=$SUPERUSER_EMAIL" >> "$ENV_FILE"
    echo "SUPERUSER_PASSWORD=$SUPERUSER_PASSWORD" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Application Configuration
    echo "# Application Configuration" >> "$ENV_FILE"
    echo "PYTHONPATH=/app" >> "$ENV_FILE"
    echo "PYTHONUNBUFFERED=1" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Gunicorn Configuration
    echo "# Gunicorn Configuration" >> "$ENV_FILE"
    echo "GUNICORN_WORKERS=4" >> "$ENV_FILE"
    echo "GUNICORN_THREADS=2" >> "$ENV_FILE"
    echo "GUNICORN_TIMEOUT=120" >> "$ENV_FILE"
    echo "GUNICORN_MAX_REQUESTS=1000" >> "$ENV_FILE"
    echo "GUNICORN_MAX_REQUESTS_JITTER=100" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # Redis Configuration
    echo "# Redis Configuration" >> "$ENV_FILE"
    echo "REDIS_URL=redis://redis:6379/0" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    # NAS/Network Storage Configuration
    echo "# NAS/Network Storage Configuration (optional)" >> "$ENV_FILE"
    echo "NAS_PLAYOUT_PATH=/mnt/nas/playout" >> "$ENV_FILE"
    echo "NAS_ARCHIVE_PATH=/mnt/nas/archive" >> "$ENV_FILE"
    echo "NAS_MOUNT_ENABLED=false" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Add SSL configuration only for Production mode
    if [ "$INSTALL_TYPE" = "1" ]; then
        echo "# SSL/HTTPS Configuration" >> "$ENV_FILE"
        echo "SSL_ENABLED=$SSL_ENABLED" >> "$ENV_FILE"
        echo "SSL_CERT_PATH=/etc/nginx/ssl/cert.pem" >> "$ENV_FILE"
        echo "SSL_KEY_PATH=/etc/nginx/ssl/key.pem" >> "$ENV_FILE"
        echo "DOMAIN_NAME=$DOMAIN_NAME" >> "$ENV_FILE"
        echo "" >> "$ENV_FILE"
    fi

    # Logging and Backup Configuration
    echo "# Logging Configuration" >> "$ENV_FILE"
    echo "LOG_LEVEL=info" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"
    
    echo "# Backup Configuration" >> "$ENV_FILE"
    echo "BACKUP_DIR=$BACKUP_DIR" >> "$ENV_FILE"
    echo "# Set Docker Compose project name" >> "$ENV_FILE"
    echo "COMPOSE_PROJECT_NAME=oktools" >> "$ENV_FILE"
    
    # Django Extended Configuration
    echo "# Django Extended Configuration" >> "$ENV_FILE"
    echo "DJANGO_LOG_LEVEL=$DJANGO_LOG_LEVEL" >> "$ENV_FILE"
    echo "DJANGO_LANGUAGE=de-de" >> "$ENV_FILE"
    echo "DJANGO_TIMEZONE=Europe/Berlin" >> "$ENV_FILE"
    echo "DJANGO_STATIC_ROOT=/app/staticfiles/" >> "$ENV_FILE"
    echo "DJANGO_MEDIA_ROOT=/app/media/" >> "$ENV_FILE"
    echo "DJANGO_USE_SECURE_SETTINGS=True" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Email Configuration
    echo "# Email Configuration" >> "$ENV_FILE"
    echo "EMAIL_HOST=$EMAIL_HOST" >> "$ENV_FILE"
    echo "EMAIL_PORT=$EMAIL_PORT" >> "$ENV_FILE"
    echo "EMAIL_USE_TLS=True" >> "$ENV_FILE"
    echo "EMAIL_HOST_USER=noreply@your-domain.com" >> "$ENV_FILE"
    echo "EMAIL_HOST_PASSWORD=__REPLACE_ME__" >> "$ENV_FILE"
    echo "DEFAULT_FROM_EMAIL=noreply@your-domain.com" >> "$ENV_FILE"
    echo "MAIL_DEV_SETTINGS=False" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Organization Extended
    echo "# Organization Extended" >> "$ENV_FILE"
    echo "ORG_ORGANIZATION_OWNER=$ORG_ORGANIZATION_OWNER" >> "$ENV_FILE"
    echo "ORG_BROADCAST_START=$ORG_BROADCAST_START" >> "$ENV_FILE"
    echo "ORG_BROADCAST_END=$ORG_BROADCAST_END" >> "$ENV_FILE"
    echo "ORG_PEERTUBE_CHANNEL=" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # NAS Storage Extended
    echo "# NAS Storage Extended" >> "$ENV_FILE"
    echo "NAS_ARCHIVE_UNC_PATH=" >> "$ENV_FILE"
    echo "NAS_PLAYOUT_UNC_PATH=" >> "$ENV_FILE"
    echo "MEDIA_AUTO_SCAN=False" >> "$ENV_FILE"
    echo "MEDIA_AUTO_COPY_ON_SCHEDULE=True" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Logging
    echo "# Logging" >> "$ENV_FILE"
    echo "LOGGING_FILE=/app/logs/oktools.log" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Bootstrap
    echo "# Bootstrap" >> "$ENV_FILE"
    echo "BOOTSTRAP_VERSION=5.3.3" >> "$ENV_FILE"
    echo "BOOTSTRAP_ICONS_VERSION=1.11.0" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # API Configuration
    echo "# API Configuration" >> "$ENV_FILE"
    echo "API_PAGE_SIZE=20" >> "$ENV_FILE"
    echo "API_ANON_RATE_LIMIT=100/hour" >> "$ENV_FILE"
    echo "API_USER_RATE_LIMIT=1000/hour" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Security
    echo "# Security" >> "$ENV_FILE"
    echo "SECURITY_SESSION_TIMEOUT=1200" >> "$ENV_FILE"
    echo "SECURITY_PASSWORD_MIN_LENGTH=8" >> "$ENV_FILE"
    echo "SECURITY_CSRF_COOKIE_AGE=31449600" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Video
    echo "# Video" >> "$ENV_FILE"
    echo "VIDEO_SUPPORTED_FORMATS=mp4,mov,mpeg,mpg" >> "$ENV_FILE"
    echo "VIDEO_SCREEN_BOARD_DURATION=20" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # I18n
    echo "# I18n" >> "$ENV_FILE"
    echo "I18N_DEFAULT_LANGUAGE=de" >> "$ENV_FILE"
    echo "I18N_SUPPORTED_LANGUAGES=de,en" >> "$ENV_FILE"
    echo "I18N_LOCALE_PATHS=ok_tools/locale" >> "$ENV_FILE"
    echo "I18N_PHONE_REGION=DE" >> "$ENV_FILE"
    echo "I18N_DATE_FORMAT=%d.%m.%Y" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Static Files
    echo "# Static Files" >> "$ENV_FILE"
    echo "STATIC_STORAGE_BACKEND=whitenoise.storage.CompressedManifestStaticFilesStorage" >> "$ENV_FILE"
    echo "STATIC_URL_PREFIX=static/" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Cache
    echo "# Cache" >> "$ENV_FILE"
    echo "CACHE_BACKEND=django.core.cache.backends.locmem.LocMemCache" >> "$ENV_FILE"
    echo "CACHE_TIMEOUT=300" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Celery Extended
    echo "# Celery Extended" >> "$ENV_FILE"
    echo "CELERY_BROKER_URL=redis://redis:6379/0" >> "$ENV_FILE"
    echo "CELERY_RESULT_BACKEND=redis://redis:6379/0" >> "$ENV_FILE"
    echo "" >> "$ENV_FILE"

    # Celery Beat Schedules
    echo "# Celery Beat Schedules" >> "$ENV_FILE"
    echo "CELERY_BEAT_EXPIRE_RENTALS=*/30 * * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_CLEANUP_BACKUPS=0 2 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_BACKUP_DB=0 3 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_AUTO_SCAN=0 */2 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_LINK_LICENSES=0 4 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_SYNC_VIDEOS=0 5 * * *" >> "$ENV_FILE"
    echo "CELERY_BEAT_UPDATE_METADATA=0 1 1 * *" >> "$ENV_FILE"

    chmod 600 "$ENV_FILE"
    echo "✓ Created .env file at: $ENV_FILE"

    # Validate the generated .env file
    if ! validate_env_file "$ENV_FILE"; then
        echo ""
        echo "⚠️  .env file validation failed. Please review and fix errors."
        read -p "Do you want to continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            exit 1
        fi
    fi

    # Copy necessary files based on installation type
    echo ""
    echo "Copying deployment files..."
    if [ "$INSTALL_TYPE" = "1" ]; then
        # Production: use nginx-enabled compose file and copy nginx files
        cp "$PROJECT_DIR/deployment/docker-compose.production.yml" "$PRODUCTION_DIR/docker-compose.yml"
        cp "$PROJECT_DIR/deployment/nginx.conf.template" "$PRODUCTION_DIR/nginx.conf.template"
        cp "$PROJECT_DIR/deployment/nginx-entrypoint.sh" "$PRODUCTION_DIR/nginx-entrypoint.sh"
        chmod +x "$PRODUCTION_DIR/nginx-entrypoint.sh"
    else
        # Local Network or Localhost: use compose file without nginx
        cp "$PROJECT_DIR/deployment/docker-compose.production.no-nginx.yml" "$PRODUCTION_DIR/docker-compose.yml"
    fi
    cp "$PROJECT_DIR/deployment/production.Dockerfile" "$PRODUCTION_DIR/Dockerfile"
    cp "$PROJECT_DIR/deployment/entrypoint.production.sh" "$PRODUCTION_DIR/entrypoint.sh"
    chmod +x "$PRODUCTION_DIR/entrypoint.sh"
    
    # NOTE: The deployment directory is no longer copied to ensure Dockerfile is in root
    # This ensures docker-compose.yml can find the Dockerfile in the root directory
    # and that entrypoint.sh is properly included in the build context

    if [ "$INSTALL_TYPE" = "1" ]; then
        echo "✓ Copied docker-compose.yml (with nginx)"
        echo "✓ Copied nginx.conf.template"
        echo "✓ Copied nginx-entrypoint.sh"
    else
        echo "✓ Copied docker-compose.yml (without nginx)"
    fi
    echo "✓ Copied Dockerfile"
    echo "✓ Copied entrypoint.sh"
    echo "✓ Copied deployment directory"
else
    echo "Invalid choice. Exiting."
    exit 1
fi

# Request SSL certificate if enabled (only for Production)
if [ "$INSTALL_TYPE" = "1" ] && [ "$SSL_ENABLED" = true ]; then
    echo ""
    echo "Requesting SSL certificate for $DOMAIN_NAME..."
    docker compose run --rm --entrypoint "\
      certbot certonly --webroot -w /var/www/certbot \
        --email $SSL_EMAIL --agree-tos --no-eff-email \
        -d $DOMAIN_NAME" certbot
    echo "✓ SSL certificate obtained successfully."
fi

# Copy source files to destination directory (outside conditional blocks)
echo ""
echo "Copying source files..."
cp "$PROJECT_DIR/requirements.txt" "$PRODUCTION_DIR/requirements.txt"
cp -r "$PROJECT_DIR/ok_tools" "$PRODUCTION_DIR/ok_tools"
# Add other necessary directories for the application
cp -r "$PROJECT_DIR/contributions" "$PRODUCTION_DIR/contributions"
cp -r "$PROJECT_DIR/dashboard" "$PRODUCTION_DIR/dashboard"
cp -r "$PROJECT_DIR/inventory" "$PRODUCTION_DIR/inventory"
cp -r "$PROJECT_DIR/licenses" "$PRODUCTION_DIR/licenses"
cp -r "$PROJECT_DIR/media_files" "$PRODUCTION_DIR/media_files"
cp -r "$PROJECT_DIR/planung" "$PRODUCTION_DIR/planung"
cp -r "$PROJECT_DIR/projects" "$PRODUCTION_DIR/projects"
cp -r "$PROJECT_DIR/registration" "$PRODUCTION_DIR/registration"
cp -r "$PROJECT_DIR/rental" "$PRODUCTION_DIR/rental"
cp "$PROJECT_DIR/manage.py" "$PRODUCTION_DIR/manage.py"

# Start containers
echo ""
echo "Starting Docker containers..."
cd "$PRODUCTION_DIR" || { echo "Failed to change directory to $PRODUCTION_DIR"; exit 1; }
echo "Current directory: $(pwd)"
echo "Checking files..."
ls -la docker-compose.yml Dockerfile entrypoint.sh
echo ""
docker compose --project-directory . up -d --build

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo "Production directory: $PRODUCTION_DIR"
echo "Configuration file: $PRODUCTION_DIR/.env"
echo ""
echo "Next steps:"
echo "1. Check container status: docker compose ps"
echo "2. View logs: docker compose logs -f web"
if [ "$INSTALL_TYPE" = "1" ] && [ "$SSL_ENABLED" = true ]; then
    echo "3. Access admin panel: https://$DOMAIN_NAME/admin"
elif [ "$INSTALL_TYPE" = "2" ]; then
    echo "3. Access admin panel: http://$SERVER_IP:8000/admin"
else
    echo "3. Access admin panel: http://localhost:8000/admin"
fi
echo "   Username: $SUPERUSER_USERNAME (or as configured)"
echo "   Password: As configured during setup"
echo ""
echo "To update application, run: $SCRIPT_DIR/update.sh"
echo "To configure post-deployment settings, run: $SCRIPT_DIR/configure.sh"